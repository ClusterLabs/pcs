import re
from typing import Optional

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.str_tools import join_multilines
from pcs.lib import sbd
from pcs.lib.communication import qdevice as qdevice_com
from pcs.lib.communication import qdevice_net as qdevice_net_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import config_validators as corosync_conf_validators
from pcs.lib.corosync import live as corosync_live
from pcs.lib.corosync import (
    qdevice_client,
    qdevice_net,
)
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfFacade
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names


def get_config(lib_env: LibraryEnvironment):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    cfg = lib_env.get_corosync_conf()
    device = None
    qd_model = cfg.get_quorum_device_model()
    if qd_model is not None:
        (
            qd_model_options,
            qd_generic_options,
            qd_heuristics_options,
        ) = cfg.get_quorum_device_settings()
        device = dict(
            model=qd_model,
            model_options=qd_model_options,
            generic_options=qd_generic_options,
            heuristics_options=qd_heuristics_options,
        )
    return {
        "options": cfg.get_quorum_options(),
        "device": device,
    }


def _check_if_atb_can_be_disabled(
    service_manager: ServiceManagerInterface,
    report_processor: reports.ReportProcessor,
    corosync_conf: CorosyncConfFacade,
    was_enabled: bool,
    force: bool = False,
) -> None:
    """
    Check whenever auto_tie_breaker can be changed without affecting SBD.
    Raises LibraryError if change of ATB will affect SBD functionality.

    service_manager --
    report_processor -- report processor
    corosync_conf -- corosync conf facade
    was_enabled -- True if ATB was enabled, False otherwise
    force -- force change
    """
    if (
        was_enabled
        and not corosync_conf.is_enabled_auto_tie_breaker()
        and sbd.is_auto_tie_breaker_needed(service_manager, corosync_conf)
    ):
        report_processor.report(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    force,
                ),
                message=(
                    reports.messages.CorosyncQuorumAtbCannotBeDisabledDueToSbd()
                ),
            )
        )
        if report_processor.has_errors:
            raise LibraryError()


def set_options(
    lib_env: LibraryEnvironment,
    options,
    skip_offline_nodes=False,
    force=False,
):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live

    LibraryEnvironment lib_env
    dict options -- quorum options
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    bool force -- force changes
    """
    cfg = lib_env.get_corosync_conf()
    if lib_env.report_processor.report_list(
        corosync_conf_validators.update_quorum_options(
            options,
            cfg.get_quorum_device_model() is not None,
            cfg.get_quorum_options(),
        )
    ).has_errors:
        raise LibraryError()
    cfg.set_quorum_options(options)
    if lib_env.is_corosync_conf_live:
        _check_if_atb_can_be_disabled(
            lib_env.service_manager,
            lib_env.report_processor,
            cfg,
            cfg.is_enabled_auto_tie_breaker(),
            force,
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)


def status_text(lib_env):
    """
    Get quorum runtime status in plain text
    """
    try:
        return corosync_live.get_quorum_status_text(lib_env.cmd_runner())
    except corosync_live.QuorumStatusReadException as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.CorosyncQuorumGetStatusError(e.reason)
            )
        ) from e


def status_device_text(lib_env, verbose=False):
    """
    Get quorum device client runtime status in plain text
    bool verbose get more detailed output
    """
    return qdevice_client.get_status_text(lib_env.cmd_runner(), verbose)


def add_device(
    lib_env: LibraryEnvironment,
    model,
    model_options,
    generic_options,
    heuristics_options,
    force_model=False,
    force_options=False,
    skip_offline_nodes=False,
):
    # pylint: disable=too-many-locals
    """
    Add a quorum device to a cluster, distribute and reload configs if live

    string model -- quorum device model
    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    bool force_model -- continue even if the model is not valid
    bool force_options -- continue even if options are not valid
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if cfg.get_quorum_device_model():
        raise LibraryError(
            reports.ReportItem.error(reports.messages.QdeviceAlreadyDefined())
        )

    report_processor = lib_env.report_processor
    report_processor.report_list(
        corosync_conf_validators.add_quorum_device(
            model,
            model_options,
            generic_options,
            heuristics_options,
            [node.nodeid for node in cfg.get_nodes() if node.nodeid],
            force_model=force_model,
            force_options=force_options,
        )
    )

    if lib_env.is_corosync_conf_live:
        cluster_nodes_names, report_list = get_existing_nodes_names(
            cfg,
            # Pcs is unable to communicate with nodes missing names. It cannot
            # send new corosync.conf to them. That might break the cluster.
            # Hence we error out.
            error_on_missing_name=True,
        )
        report_processor.report_list(report_list)

    if report_processor.has_errors:
        raise LibraryError()

    cfg.add_quorum_device(
        model,
        model_options,
        generic_options,
        heuristics_options,
    )
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.CorosyncQuorumHeuristicsEnabledWithNoExec()
            )
        )

    # First setup certificates for qdevice, then send corosync.conf to nodes.
    # If anything fails, nodes will not have corosync.conf with qdevice in it,
    # so there is no effect on the cluster.
    if lib_env.is_corosync_conf_live:
        target_factory = lib_env.get_node_target_factory()
        target_list = target_factory.get_target_list(
            cluster_nodes_names,
            skip_non_existing=skip_offline_nodes,
        )
        # Do model specific configuration.
        # If the model is not known to pcs and was forced, do not configure
        # anything else than corosync.conf, as we do not know what to do
        # anyway.
        if model == "net":
            qdevice_net.set_up_client_certificates(
                lib_env.cmd_runner(),
                lib_env.report_processor,
                lib_env.communicator_factory,
                # We are sure the "host" key is there, it has been validated
                # above.
                target_factory.get_target_from_hostname(model_options["host"]),
                cfg.get_cluster_name(),
                target_list,
                skip_offline_nodes,
            )

        lib_env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionStarted(
                    reports.const.SERVICE_ACTION_ENABLE, "corosync-qdevice"
                )
            )
        )
        com_cmd = qdevice_com.Enable(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # everything set up, it's safe to tell the nodes to use qdevice
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

    # Now, when corosync.conf has been reloaded, we can start qdevice service.
    if lib_env.is_corosync_conf_live:
        lib_env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionStarted(
                    reports.const.SERVICE_ACTION_START, "corosync-qdevice"
                )
            )
        )
        com_cmd_start = qdevice_com.Start(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_start.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_start)


def update_device(
    lib_env: LibraryEnvironment,
    model_options,
    generic_options,
    heuristics_options,
    force_options=False,
    skip_offline_nodes=False,
):
    """
    Change quorum device settings, distribute and reload configs if live

    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    bool force_options -- continue even if options are not valid
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    model = cfg.get_quorum_device_model()
    if not model:
        raise LibraryError(
            reports.ReportItem.error(reports.messages.QdeviceNotDefined())
        )
    if lib_env.report_processor.report_list(
        corosync_conf_validators.update_quorum_device(
            model,
            model_options,
            generic_options,
            heuristics_options,
            [node.nodeid for node in cfg.get_nodes() if node.nodeid],
            force_options=force_options,
        )
    ).has_errors:
        raise LibraryError()
    cfg.update_quorum_device(model_options, generic_options, heuristics_options)
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.CorosyncQuorumHeuristicsEnabledWithNoExec()
            )
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)


def remove_device_heuristics(lib_env, skip_offline_nodes=False):
    """
    Stop using quorum device heuristics, distribute and reload configs if live

    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    if not cfg.get_quorum_device_model():
        raise LibraryError(
            reports.ReportItem.error(reports.messages.QdeviceNotDefined())
        )
    cfg.remove_quorum_device_heuristics()
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)


def remove_device(lib_env: LibraryEnvironment, skip_offline_nodes=False):
    """
    Stop using quorum device, distribute and reload configs if live
    skip_offline_nodes continue even if not all nodes are accessible
    """
    cfg = lib_env.get_corosync_conf()
    model = cfg.get_quorum_device_model()
    if not model:
        raise LibraryError(
            reports.ReportItem.error(reports.messages.QdeviceNotDefined())
        )
    cfg.remove_quorum_device()

    if lib_env.is_corosync_conf_live:
        report_processor = lib_env.report_processor
        # get nodes for communication
        cluster_nodes_names, report_list = get_existing_nodes_names(
            cfg,
            # Pcs is unable to communicate with nodes missing names. It cannot
            # send new corosync.conf to them. That might break the cluster.
            # Hence we error out.
            error_on_missing_name=True,
        )
        if report_processor.report_list(report_list).has_errors:
            raise LibraryError()
        target_list = lib_env.get_node_target_factory().get_target_list(
            cluster_nodes_names,
            skip_non_existing=skip_offline_nodes,
        )
        # fix quorum options for SBD to work properly
        if sbd.atb_has_to_be_enabled(lib_env.service_manager, cfg):
            lib_env.report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbd()
                )
            )
            cfg.set_quorum_options({"auto_tie_breaker": "1"})

        # disable qdevice
        lib_env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionStarted(
                    reports.const.SERVICE_ACTION_DISABLE, "corosync-qdevice"
                )
            )
        )
        com_cmd_disable = qdevice_com.Disable(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_disable.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_disable)
        # stop qdevice
        lib_env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionStarted(
                    reports.const.SERVICE_ACTION_STOP, "corosync-qdevice"
                )
            )
        )
        com_cmd_stop = qdevice_com.Stop(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd_stop.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd_stop)
        # handle model specific configuration
        if model == "net":
            lib_env.report_processor.report(
                reports.ReportItem.info(
                    reports.messages.QdeviceCertificateRemovalStarted()
                )
            )
            com_cmd_client_destroy = qdevice_net_com.ClientDestroy(
                lib_env.report_processor, skip_offline_nodes
            )
            com_cmd_client_destroy.set_targets(target_list)
            run_and_raise(
                lib_env.get_node_communicator(), com_cmd_client_destroy
            )

    lib_env.push_corosync_conf(cfg, skip_offline_nodes)


def _ensure_live(lib_env: LibraryEnvironment) -> None:
    if not lib_env.is_corosync_conf_live:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.LiveEnvironmentRequired(
                    [file_type_codes.COROSYNC_CONF]
                )
            )
        )
        raise LibraryError()


def device_net_certificate_setup_local(
    lib_env: LibraryEnvironment,
    qnetd_host: str,
    cluster_name: str,
) -> None:
    """
    Set up qdevice model net certificates on the local node

    qnetd_host -- address of a qnetd host
    cluster_name -- local node cluster name
    """
    _ensure_live(lib_env)
    runner = lib_env.cmd_runner()
    qnetd_target = lib_env.get_node_target_factory().get_target_from_hostname(
        qnetd_host
    )

    # get qnetd CA certificate
    com_cmd_1 = qdevice_net_com.GetCaCert(lib_env.report_processor)
    com_cmd_1.set_targets([qnetd_target])
    qnetd_ca_cert = run_and_raise(
        lib_env.communicator_factory.get_communicator(), com_cmd_1
    )[0][1]
    # init certificate storage on local node
    qdevice_net.client_setup(runner, qnetd_ca_cert)
    # create client certificate request
    cert_request = qdevice_net.client_generate_certificate_request(
        runner, cluster_name
    )
    # sign the request on qnetd host
    com_cmd_2 = qdevice_net_com.SignCertificate(lib_env.report_processor)
    com_cmd_2.add_request(qnetd_target, cert_request, cluster_name)
    signed_certificate = run_and_raise(
        lib_env.communicator_factory.get_communicator(), com_cmd_2
    )[0][1]
    # transform the signed certificate to pk12 format which can sent to nodes
    pk12 = qdevice_net.client_cert_request_to_pk12(runner, signed_certificate)
    # store final certificate
    qdevice_net.client_import_certificate_and_key(runner, pk12)


def device_net_certificate_check_local(
    lib_env: LibraryEnvironment,
    qnetd_host: str,
    cluster_name: str,
) -> bool:
    """
    Check if the local node already has qdevice model net certificates

    qnetd_host -- address of a qnetd host
    cluster_name -- local node cluster name
    """

    def get_certificate_data(text: str) -> Optional[str]:
        match = re.search(
            r"-----BEGIN CERTIFICATE-----([a-zA-Z0-9/+=]+)-----END CERTIFICATE-----",
            "".join(text.splitlines()),
        )
        return match.group(1) if match else None

    _ensure_live(lib_env)
    runner = lib_env.cmd_runner()
    qnetd_target = lib_env.get_node_target_factory().get_target_from_hostname(
        qnetd_host
    )

    if not qdevice_net.client_initialized():
        return False

    # check if certificates are present
    list_certs_cmd = [
        settings.certutil_exec,
        "-d",
        settings.corosync_qdevice_net_client_certs_dir,
        "-L",
    ]
    stdout, stderr, retval = runner.run(list_certs_cmd)
    if retval != 0:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateReadError(
                    join_multilines([stderr, stdout])
                )
            )
        )
        raise LibraryError()
    for certname in ["QNet CA", "Cluster Cert"]:
        if not re.search(rf"^{certname}\s*\S*,.*,.*$", stdout, re.MULTILINE):
            return False

    # check cluster name
    stdout, stderr, retval = runner.run(list_certs_cmd + ["-n", "Cluster Cert"])
    if retval != 0:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateReadError(
                    join_multilines([stderr, stdout])
                )
            )
        )
        raise LibraryError()
    if not re.search(
        rf'^\s*Subject: "CN={cluster_name}"$', stdout, re.MULTILINE
    ):
        return False

    # get qnetd CA certificate from qnetd host
    com_cmd = qdevice_net_com.GetCaCert(lib_env.report_processor)
    com_cmd.set_targets([qnetd_target])
    qnetd_ca_cert_text = run_and_raise(
        lib_env.communicator_factory.get_communicator(), com_cmd
    )[0][1]
    qnetd_ca_cert = get_certificate_data(qnetd_ca_cert_text.decode())
    if qnetd_ca_cert is None:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateBadFormat()
            )
        )
        raise LibraryError()

    # get qnetd CA certificate from local node
    stdout, stderr, retval = runner.run(
        list_certs_cmd + ["-n", "QNet CA", "-a"]
    )
    if retval != 0:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateReadError(
                    join_multilines([stderr, stdout])
                )
            )
        )
        raise LibraryError()
    local_ca_cert = get_certificate_data(stdout)
    if local_ca_cert is None:
        lib_env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.QdeviceCertificateBadFormat()
            )
        )
        raise LibraryError()

    return qnetd_ca_cert == local_ca_cert


def set_expected_votes_live(lib_env, expected_votes):
    """
    set expected votes in live cluster to specified value
    numeric expected_votes desired value of expected votes
    """
    try:
        votes_int = int(expected_votes)
        if votes_int < 1:
            raise ValueError()
    except ValueError:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "expected votes", expected_votes, "positive integer"
                )
            )
        ) from None

    corosync_live.set_expected_votes(lib_env.cmd_runner(), votes_int)
