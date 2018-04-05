from pcs.common import report_codes
from pcs.lib import reports, sbd
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.lib.communication import (
    qdevice as qdevice_com,
    qdevice_net as qdevice_net_com,
)
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import (
    config_validators as corosync_conf_validators,
    live as corosync_live,
    qdevice_net,
    qdevice_client
)


def get_config(lib_env):
    """
    Extract and return quorum configuration from corosync.conf
    lib_env LibraryEnvironment
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    device = None
    if cfg.has_quorum_device():
        model, model_options, generic_options, heuristics_options = (
            cfg.get_quorum_device_settings()
        )
        device = {
            "model": model,
            "model_options": model_options,
            "generic_options": generic_options,
            "heuristics_options": heuristics_options,
        }
    return {
        "options": cfg.get_quorum_options(),
        "device": device,
    }


def _check_if_atb_can_be_disabled(
    runner, report_processor, corosync_conf, was_enabled, force=False
):
    """
    Check whenever auto_tie_breaker can be changed without affecting SBD.
    Raises LibraryError if change of ATB will affect SBD functionality.

    runner -- CommandRunner
    report_processor -- report processor
    corosync_conf -- corosync conf facade
    was_enabled -- True if ATB was enabled, False otherwise
    force -- force change
    """
    if (
        was_enabled
        and
        not corosync_conf.is_enabled_auto_tie_breaker()
        and
        sbd.is_auto_tie_breaker_needed(runner, corosync_conf)
    ):
        report_processor.process(reports.quorum_cannot_disable_atb_due_to_sbd(
            ReportItemSeverity.WARNING if force else ReportItemSeverity.ERROR,
            None if force else report_codes.FORCE_OPTIONS
        ))


def set_options(lib_env, options, skip_offline_nodes=False, force=False):
    """
    Set corosync quorum options, distribute and reload corosync.conf if live

    LibraryEnvironment lib_env
    dict options -- quorum options
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    bool force -- force changes
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    lib_env.report_processor.process_list(
        corosync_conf_validators.update_quorum_options(
            options,
            cfg.has_quorum_device(),
            cfg.get_quorum_options()
        )
    )
    cfg.set_quorum_options(options)
    if lib_env.is_corosync_conf_live:
        _check_if_atb_can_be_disabled(
            lib_env.cmd_runner(),
            lib_env.report_processor,
            cfg,
            cfg.is_enabled_auto_tie_breaker(),
            force
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def status_text(lib_env):
    """
    Get quorum runtime status in plain text
    """
    __ensure_not_cman(lib_env)
    return corosync_live.get_quorum_status_text(lib_env.cmd_runner())

def status_device_text(lib_env, verbose=False):
    """
    Get quorum device client runtime status in plain text
    bool verbose get more detailed output
    """
    __ensure_not_cman(lib_env)
    return qdevice_client.get_status_text(lib_env.cmd_runner(), verbose)

def add_device(
    lib_env, model, model_options, generic_options, heuristics_options,
    force_model=False, force_options=False, skip_offline_nodes=False
):
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
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    if cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_already_defined())
    lib_env.report_processor.process_list(
        corosync_conf_validators.add_quorum_device(
            model,
            model_options,
            generic_options,
            heuristics_options,
            [node.id for node in cfg.get_nodes()],
            force_model=force_model,
            force_options=force_options
        )
    )
    cfg.add_quorum_device(
        model,
        model_options,
        generic_options,
        heuristics_options,
    )
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.process(
            reports.corosync_quorum_heuristics_enabled_with_no_exec()
        )

    # First setup certificates for qdevice, then send corosync.conf to nodes.
    # If anything fails, nodes will not have corosync.conf with qdevice in it,
    # so there is no effect on the cluster.
    if lib_env.is_corosync_conf_live:
        target_factory = lib_env.get_node_target_factory()
        target_list = target_factory.get_target_list(
            cfg.get_nodes().labels, skip_non_existing=skip_offline_nodes,
        )
        # Do model specific configuration.
        # If the model is not known to pcs and was forced, do not configure
        # anything else than corosync.conf, as we do not know what to do
        # anyway.
        if model == "net":
            _add_device_model_net(
                lib_env,
                # We are sure the "host" key is there, it has been validated
                # above.
                target_factory.get_target_from_hostname(model_options["host"]),
                cfg.get_cluster_name(),
                target_list,
                skip_offline_nodes
            )

        lib_env.report_processor.process(
            reports.service_enable_started("corosync-qdevice")
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
        lib_env.report_processor.process(
            reports.service_start_started("corosync-qdevice")
        )
        com_cmd = qdevice_com.Start(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)

def _add_device_model_net(
    lib_env, qnetd_target, cluster_name, cluster_nodes_target_list,
    skip_offline_nodes,
):
    """
    setup cluster nodes for using qdevice model net
    string qnetd_host address of qdevice provider (qnetd host)
    string cluster_name name of the cluster to which qdevice is being added
    NodeAddressesList cluster_nodes list of cluster nodes addresses
    bool skip_offline_nodes continue even if not all nodes are accessible
    """
    runner = lib_env.cmd_runner()
    reporter = lib_env.report_processor

    reporter.process(
        reports.qdevice_certificate_distribution_started()
    )
    # get qnetd CA certificate
    com_cmd = qdevice_net_com.GetCaCert(reporter)
    com_cmd.set_targets([qnetd_target])
    qnetd_ca_cert = run_and_raise(
        lib_env.get_node_communicator(), com_cmd
    )[0][1]
    # init certificate storage on all nodes
    com_cmd = qdevice_net_com.ClientSetup(
        reporter, qnetd_ca_cert, skip_offline_nodes
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)
    # create client certificate request
    cert_request = qdevice_net.client_generate_certificate_request(
        runner,
        cluster_name
    )
    # sign the request on qnetd host
    com_cmd = qdevice_net_com.SignCertificate(reporter)
    com_cmd.add_request(qnetd_target, cert_request, cluster_name)
    signed_certificate = run_and_raise(
        lib_env.get_node_communicator(), com_cmd
    )[0][1]
    # transform the signed certificate to pk12 format which can sent to nodes
    pk12 = qdevice_net.client_cert_request_to_pk12(runner, signed_certificate)
    # distribute final certificate to nodes
    com_cmd = qdevice_net_com.ClientImportCertificateAndKey(
        reporter, pk12, skip_offline_nodes
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

def update_device(
    lib_env, model_options, generic_options, heuristics_options,
    force_options=False, skip_offline_nodes=False
):
    """
    Change quorum device settings, distribute and reload configs if live

    dict model_options -- model specific options
    dict generic_options -- generic quorum device options
    dict heuristics_options -- heuristics options
    bool force_options -- continue even if options are not valid
    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    lib_env.report_processor.process_list(
        corosync_conf_validators.update_quorum_device(
            cfg.get_quorum_device_model(),
            model_options,
            generic_options,
            heuristics_options,
            [node.id for node in cfg.get_nodes()],
            force_options=force_options
        )
    )
    cfg.update_quorum_device(
        model_options,
        generic_options,
        heuristics_options
    )
    if cfg.is_quorum_device_heuristics_enabled_with_no_exec():
        lib_env.report_processor.process(
            reports.corosync_quorum_heuristics_enabled_with_no_exec()
        )
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def remove_device_heuristics(lib_env, skip_offline_nodes=False):
    """
    Stop using quorum device heuristics, distribute and reload configs if live

    bool skip_offline_nodes -- continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)
    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    cfg.remove_quorum_device_heuristics()
    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def remove_device(lib_env, skip_offline_nodes=False):
    """
    Stop using quorum device, distribute and reload configs if live
    skip_offline_nodes continue even if not all nodes are accessible
    """
    __ensure_not_cman(lib_env)

    cfg = lib_env.get_corosync_conf()
    if not cfg.has_quorum_device():
        raise LibraryError(reports.qdevice_not_defined())
    model = cfg.get_quorum_device_model()
    cfg.remove_quorum_device()

    if lib_env.is_corosync_conf_live:
        target_list = lib_env.get_node_target_factory().get_target_list(
            cfg.get_nodes().labels, skip_non_existing=skip_offline_nodes,
        )
        # fix quorum options for SBD to work properly
        if sbd.atb_has_to_be_enabled(lib_env.cmd_runner(), cfg):
            lib_env.report_processor.process(reports.sbd_requires_atb())
            cfg.set_quorum_options({"auto_tie_breaker": "1"})

        # disable qdevice
        lib_env.report_processor.process(
            reports.service_disable_started("corosync-qdevice")
        )
        com_cmd = qdevice_com.Disable(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)
        # stop qdevice
        lib_env.report_processor.process(
            reports.service_stop_started("corosync-qdevice")
        )
        com_cmd = qdevice_com.Stop(
            lib_env.report_processor, skip_offline_nodes
        )
        com_cmd.set_targets(target_list)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)
        # handle model specific configuration
        if model == "net":
            lib_env.report_processor.process(
                reports.qdevice_certificate_removal_started()
            )
            com_cmd = qdevice_net_com.ClientDestroy(
                lib_env.report_processor, skip_offline_nodes
            )
            com_cmd.set_targets(target_list)
            run_and_raise(lib_env.get_node_communicator(), com_cmd)

    lib_env.push_corosync_conf(cfg, skip_offline_nodes)

def set_expected_votes_live(lib_env, expected_votes):
    """
    set expected votes in live cluster to specified value
    numeric expected_votes desired value of expected votes
    """
    if lib_env.is_cman_cluster:
        raise LibraryError(reports.cman_unsupported_command())

    try:
        votes_int = int(expected_votes)
        if votes_int < 1:
            raise ValueError()
    except ValueError:
        raise LibraryError(reports.invalid_option_value(
            "expected votes",
            expected_votes,
            "positive integer"
        ))

    corosync_live.set_expected_votes(lib_env.cmd_runner(), votes_int)

def __ensure_not_cman(lib_env):
    if lib_env.is_corosync_conf_live and lib_env.is_cman_cluster:
        raise LibraryError(reports.cman_unsupported_command())
