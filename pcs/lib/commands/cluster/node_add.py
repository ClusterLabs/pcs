import os.path

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.node_communicator import HostNotFound
from pcs.common.reports import ReportProcessor
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import (
    ReportItem,
)
from pcs.common.tools import format_os_error
from pcs.lib import (
    node_communication_format,
    sbd,
    validate,
)
from pcs.lib.booth import sync as booth_sync
from pcs.lib.cib.resource.guest_node import find_node_list as get_guest_nodes
from pcs.lib.cib.resource.remote_node import (
    find_node_list as get_remote_nodes,
)
from pcs.lib.commands.cluster.common import (
    ensure_live_env,
    get_validated_wait_timeout,
    is_ssl_cert_sync_enabled,
    start_cluster,
    verify_corosync_conf,
)
from pcs.lib.commands.cluster.node_provisioning import (
    get_addrs_defaulter,
    host_check_cluster_setup,
    normalize_dict,
    set_defaults_in_dict,
)
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
    ReloadCorosyncConf,
)
from pcs.lib.communication.nodes import (
    DistributeFilesWithoutForces,
    EnableCluster,
    GetHostInfo,
    GetOnlineTargets,
    SendPcsdSslCertAndKey,
    UpdateKnownHosts,
)
from pcs.lib.communication.sbd import (
    CheckSbd,
    DisableSbdService,
    EnableSbdService,
    SetSbdConfig,
)
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    run_and_raise,
)
from pcs.lib.communication.tools import run as run_com
from pcs.lib.corosync import (
    config_validators,
    qdevice_net,
)
from pcs.lib.env import (
    LibraryEnvironment,
)
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.tools import (
    environment_file_to_dict,
)


def add_nodes(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    nodes,
    wait=False,
    start=False,
    enable=False,
    no_watchdog_validation=False,
    force_flags: reports.types.ForceFlags = (),
):
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Add specified nodes to the local cluster
    Raise LibraryError on any error.

    env LibraryEnvironment
    nodes list -- list of dicts which represents node.
        Supported keys are: name (required), addrs (list), devices (list),
        watchdog. See note below.
    wait -- specifies if command should try to wait for cluster to start up.
        Has no effect start is False. If set to False command will not wait for
        cluster to start. If None command will wait for some default timeout.
        If int wait set timeout to int value of seconds.
    start bool -- if True start cluster when it is set up
    enable bool -- if True enable cluster when it is set up
    no_watchdog_validation bool -- if True do not validate specified watchdogs
        on remote hosts
    force_flags list -- list of flags codes

    The command is defaulting node addresses if they are not specified. The
    defaulting is done for each node individually if and only if the "addrs" key
    is not present for the node. If the "addrs" key is present and holds an
    empty list, no defaulting is done.
    This will default addresses for node2 and won't modify addresses for other
    nodes (no addresses will be defined for node3):
    nodes=[
        {"name": "node1", "addrs": ["node1-addr"]},
        {"name": "node2"},
        {"name": "node3", "addrs": []},
    ]
    """
    ensure_live_env(env)  # raises if env is not live

    force = report_codes.FORCE in force_flags
    skip_offline_nodes = report_codes.SKIP_OFFLINE_NODES in force_flags

    report_processor = env.report_processor
    target_factory = env.get_node_target_factory()
    is_sbd_enabled = sbd.is_sbd_enabled(env.service_manager)
    corosync_conf = env.get_corosync_conf()
    corosync_node_options = {"name", "addrs"}
    sbd_node_options = {"devices", "watchdog"}

    keys_to_normalize = {"addrs"}
    if is_sbd_enabled:
        keys_to_normalize |= sbd_node_options
    new_nodes = [normalize_dict(node, keys_to_normalize) for node in nodes]

    # get targets for existing nodes
    cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        corosync_conf,
        # Pcs is unable to communicate with nodes missing names. It cannot send
        # new corosync.conf to them. That might break the cluster. Hence we
        # error out.
        error_on_missing_name=True,
    )
    report_processor.report_list(nodes_report_list)
    (
        target_report_list,
        cluster_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        cluster_nodes_names,
        skip_non_existing=skip_offline_nodes,
    )
    report_processor.report_list(target_report_list)

    # get a target for qnetd if needed
    if corosync_conf.get_quorum_device_model() == "net":
        (
            qdevice_model_options,
            _,
            _,
        ) = corosync_conf.get_quorum_device_settings()
        try:
            qnetd_target = target_factory.get_target(
                qdevice_model_options["host"]
            )
        except HostNotFound:
            report_processor.report(
                ReportItem.error(
                    reports.messages.HostNotFound(
                        [qdevice_model_options["host"]]
                    )
                )
            )

    # Get targets for new nodes and report unknown (== not-authorized) nodes.
    # If a node doesn't contain the 'name' key, validation of inputs reports it.
    # That means we don't report missing names but cannot rely on them being
    # present either.
    (
        target_report_list,
        new_nodes_target_list,
    ) = target_factory.get_target_list_with_reports(
        [node["name"] for node in new_nodes if "name" in node],
        allow_skip=False,
    )
    report_processor.report_list(target_report_list)

    # Set default values for not-specified node options.
    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole node add command / form significantly.
    new_nodes_target_dict = {
        target.label: target for target in new_nodes_target_list
    }
    addrs_defaulter = get_addrs_defaulter(
        report_processor, new_nodes_target_dict
    )
    new_nodes_defaulters = {"addrs": addrs_defaulter}
    if is_sbd_enabled:
        watchdog_defaulter = _get_watchdog_defaulter(
            report_processor, new_nodes_target_dict
        )
        new_nodes_defaulters["devices"] = lambda _: []
        new_nodes_defaulters["watchdog"] = watchdog_defaulter
    new_nodes = [
        set_defaults_in_dict(node, new_nodes_defaulters) for node in new_nodes
    ]
    new_nodes_dict = {
        node["name"]: node for node in new_nodes if "name" in node
    }

    # Validate inputs - node options names
    # We do not want to make corosync validators know about SBD options and
    # vice versa. Therefore corosync and SBD validators get only valid corosync
    # and SBD options respectively, and we need to check for any surplus
    # options here.
    report_processor.report_list(
        validate.NamesIn(
            corosync_node_options | sbd_node_options, option_type="node"
        ).validate(
            {
                # Get a dict containing options of all nodes. Values don't
                # matter for validate.NamesIn validator.
                option_name: ""
                for node_option_names in [node.keys() for node in new_nodes]
                for option_name in node_option_names
            }
        )
    )

    # Validate inputs - corosync part
    try:
        cib = env.get_cib()
        cib_nodes = get_remote_nodes(cib) + get_guest_nodes(cib)
    except LibraryError:
        cib_nodes = []
        report_processor.report(
            ReportItem(
                reports.item.get_severity(report_codes.FORCE, force),
                reports.messages.CibLoadErrorGetNodesForValidation(),
            )
        )
    # corosync validator rejects non-corosync keys
    new_nodes_corosync = [
        {key: node[key] for key in corosync_node_options if key in node}
        for node in new_nodes
    ]
    report_processor.report_list(
        config_validators.add_nodes(
            new_nodes_corosync,
            corosync_conf.get_nodes(),
            cib_nodes,
            force_unresolvable=force,
        )
    )

    # Validate inputs - SBD part
    if is_sbd_enabled:
        report_processor.report_list(
            sbd.validate_new_nodes_devices(
                {
                    node["name"]: node["devices"]
                    for node in new_nodes
                    if "name" in node
                }
            )
        )
    else:
        for node in new_nodes:
            sbd_options = sbd_node_options.intersection(node.keys())
            if sbd_options and "name" in node:
                report_processor.report(
                    ReportItem.error(
                        reports.messages.SbdNotUsedCannotSetSbdOptions(
                            sorted(sbd_options), node["name"]
                        )
                    )
                )

    # Validate inputs - flags part
    wait_timeout = get_validated_wait_timeout(report_processor, wait, start)

    # Get online cluster nodes
    # This is the only call in which we accept skip_offline_nodes option for the
    # cluster nodes. In all the other actions we communicate only with the
    # online nodes. This allows us to simplify code as any communication issue
    # is considered an error, ends the command processing and is not possible
    # to skip it by skip_offline_nodes. We do not have to care about a situation
    # when a communication command cannot connect to some nodes and then the
    # next command can connect but fails due to the previous one did not
    # succeed.
    online_cluster_target_list = []
    if cluster_nodes_target_list:
        com_cmd: AllSameDataMixin = GetOnlineTargets(
            report_processor,
            ignore_offline_targets=skip_offline_nodes,
        )
        com_cmd.set_targets(cluster_nodes_target_list)
        online_cluster_target_list = run_com(
            env.get_node_communicator(), com_cmd
        )
        offline_cluster_target_list = [
            target
            for target in cluster_nodes_target_list
            if target not in online_cluster_target_list
        ]
        if not online_cluster_target_list:
            report_processor.report(
                ReportItem.error(
                    reports.messages.UnableToPerformOperationOnAnyNode()
                )
            )
        elif offline_cluster_target_list and skip_offline_nodes:
            # TODO: report (warn) how to fix offline nodes when they come online
            # report_processor.report(None)
            pass

    # Validate existing cluster nodes status
    atb_has_to_be_enabled = sbd.atb_has_to_be_enabled(
        env.service_manager, corosync_conf, len(new_nodes)
    )
    if atb_has_to_be_enabled:
        if online_cluster_target_list:
            com_cmd = CheckCorosyncOffline(
                report_processor, allow_skip_offline=False
            )
            com_cmd.set_targets(online_cluster_target_list)
            cluster_running_target_list = run_com(
                env.get_node_communicator(), com_cmd
            )
            if cluster_running_target_list:
                report_processor.report(
                    ReportItem.error(
                        reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbdClusterIsRunning()
                    )
                )
            else:
                report_processor.report(
                    ReportItem.warning(
                        reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbd()
                    )
                )

    # Validate new nodes. All new nodes have to be online.
    com_cmd = GetHostInfo(report_processor)
    com_cmd.set_targets(new_nodes_target_list)
    report_processor.report_list(
        host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd),
            force,
            # version of services may not be the same across the existing
            # cluster nodes, so it's not easy to make this check properly
            check_services_versions=False,
        )
    )

    # Validate SBD on new nodes
    if is_sbd_enabled:
        if no_watchdog_validation:
            report_processor.report(
                ReportItem.warning(
                    reports.messages.SbdWatchdogValidationInactive()
                )
            )
        com_cmd_sbd = CheckSbd(report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            # Do not send watchdog if validation is turned off. Listing of
            # available watchdogs in pcsd may restart the machine in some
            # corner cases.
            com_cmd_sbd.add_request(
                new_node_target,
                watchdog="" if no_watchdog_validation else new_node["watchdog"],
                device_list=new_node["devices"],
            )
        run_com(env.get_node_communicator(), com_cmd_sbd)

    # If there is an error reading the file, this will report it and exit
    # safely before any change is made to the nodes.
    sync_ssl_certs = is_ssl_cert_sync_enabled(report_processor)

    if report_processor.has_errors:
        raise LibraryError()

    # Validation done. If errors occurred, an exception has been raised and we
    # don't get below this line.

    # First set up everything else than corosync. Once the new nodes are present
    # in corosync.conf, they're considered part of a cluster and the node add
    # command cannot be run again. So we need to minimize the amount of actions
    # (and therefore possible failures) after adding the nodes to corosync.

    # distribute auth tokens of all cluster nodes (including the new ones) to
    # all new nodes
    com_cmd = UpdateKnownHosts(
        env.report_processor,
        known_hosts_to_add=env.get_known_hosts(
            cluster_nodes_names + list(new_nodes_dict.keys())
        ),
        known_hosts_to_remove=[],
    )
    com_cmd.set_targets(new_nodes_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # qdevice setup
    if corosync_conf.get_quorum_device_model() == "net":
        qdevice_net.set_up_client_certificates(
            env.cmd_runner(),
            env.report_processor,
            env.communicator_factory,
            qnetd_target,
            corosync_conf.get_cluster_name(),
            new_nodes_target_list,
            # we don't want to allow skipping offline nodes which are being
            # added, otherwise qdevice will not work properly
            skip_offline_nodes=False,
            allow_skip_offline=False,
        )

    # sbd setup
    if is_sbd_enabled:
        sbd_cfg = environment_file_to_dict(sbd.get_local_sbd_config())

        com_cmd_sbd_cfg = SetSbdConfig(env.report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            com_cmd_sbd_cfg.add_request(
                new_node_target,
                sbd.create_sbd_config(
                    sbd_cfg,
                    new_node["name"],
                    watchdog=new_node["watchdog"],
                    device_list=new_node["devices"],
                ),
            )
        run_and_raise(env.get_node_communicator(), com_cmd_sbd_cfg)

        com_cmd = EnableSbdService(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    else:
        com_cmd = DisableSbdService(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # booth setup
    booth_sync.send_all_config_to_node(
        env.get_node_communicator(),
        env.report_processor,
        new_nodes_target_list,
        rewrite_existing=force,
        skip_wrong_config=force,
    )

    # distribute corosync and pacemaker authkeys and other config files
    files_action = {}
    severity = reports.item.get_severity(reports.codes.FORCE, force)
    if os.path.isfile(settings.corosync_authkey_file):
        try:
            with open(
                settings.corosync_authkey_file, "rb"
            ) as corosync_authkey_file:
                files_action.update(
                    node_communication_format.corosync_authkey_file(
                        corosync_authkey_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.COROSYNC_AUTHKEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.corosync_authkey_file,
                    ),
                )
            )

    if os.path.isfile(settings.pacemaker_authkey_file):
        try:
            with open(
                settings.pacemaker_authkey_file, "rb"
            ) as pcmk_authkey_file:
                files_action.update(
                    node_communication_format.pcmk_authkey_file(
                        pcmk_authkey_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PACEMAKER_AUTHKEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pacemaker_authkey_file,
                    ),
                )
            )

    if os.path.isfile(settings.pcsd_dr_config_location):
        try:
            with open(
                settings.pcsd_dr_config_location, "rb"
            ) as pcs_dr_config_file:
                files_action.update(
                    node_communication_format.pcs_dr_config_file(
                        pcs_dr_config_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PCS_DR_CONFIG,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_dr_config_location,
                    ),
                )
            )

    # pcs_settings.conf was previously synced using pcsdcli send_local_configs.
    # This has been changed temporarily until new system for distribution and
    # synchronization of configs will be introduced.
    if os.path.isfile(settings.pcsd_settings_conf_location):
        try:
            with open(
                settings.pcsd_settings_conf_location, "r"
            ) as pcs_settings_conf_file:
                files_action.update(
                    node_communication_format.pcs_settings_conf_file(
                        pcs_settings_conf_file.read()
                    )
                )
        except OSError as e:
            report_processor.report(
                ReportItem(
                    severity,
                    reports.messages.FileIoError(
                        file_type_codes.PCS_SETTINGS_CONF,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_settings_conf_location,
                    ),
                )
            )

    # stop here if one of the files could not be loaded and it was not forced
    if report_processor.has_errors:
        raise LibraryError()

    if files_action:
        com_cmd = DistributeFilesWithoutForces(
            env.report_processor, files_action
        )
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute and reload pcsd SSL certificate
    if sync_ssl_certs:
        report_processor.report(
            ReportItem.info(
                reports.messages.PcsdSslCertAndKeyDistributionStarted(
                    sorted([target.label for target in new_nodes_target_list])
                )
            )
        )

        try:
            with open(settings.pcsd_cert_location, "r") as file:
                ssl_cert = file.read()
        except OSError as e:
            report_processor.report(
                ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.PCSD_SSL_CERT,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_cert_location,
                    )
                )
            )
        try:
            with open(settings.pcsd_key_location, "r") as file:
                ssl_key = file.read()
        except OSError as e:
            report_processor.report(
                ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.PCSD_SSL_KEY,
                        RawFileError.ACTION_READ,
                        format_os_error(e),
                        file_path=settings.pcsd_key_location,
                    )
                )
            )
        if report_processor.has_errors:
            raise LibraryError()

        com_cmd = SendPcsdSslCertAndKey(env.report_processor, ssl_cert, ssl_key)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # When corosync >= 2 is in use, the procedure for adding a node is:
    # 1. add the new node to corosync.conf on all existing nodes
    # 2. reload corosync.conf before the new node is started
    # 3. start the new node
    # If done otherwise, membership gets broken and qdevice hangs. Cluster
    # will recover after a minute or so but still it's a wrong way.

    corosync_conf.add_nodes(new_nodes_corosync)
    if atb_has_to_be_enabled:
        corosync_conf.set_quorum_options(dict(auto_tie_breaker="1"))

    # TODO why this does not use push_corosync_conf?
    verify_corosync_conf(corosync_conf)  # raises if corosync not valid
    com_cmd = DistributeCorosyncConf(
        env.report_processor,
        corosync_conf.config.export(),
        allow_skip_offline=False,
    )
    com_cmd.set_targets(online_cluster_target_list + new_nodes_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = ReloadCorosyncConf(env.report_processor)
    com_cmd.set_targets(online_cluster_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Optionally enable and start cluster services.
    if enable:
        com_cmd = EnableCluster(env.report_processor)
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    if start:
        start_cluster(
            env.communicator_factory,
            env.report_processor,
            new_nodes_target_list,
            wait_timeout=wait_timeout,
        )


def _get_watchdog_defaulter(report_processor: ReportProcessor, targets_dict):
    del targets_dict

    def defaulter(node):
        report_processor.report(
            ReportItem.info(
                reports.messages.UsingDefaultWatchdog(
                    settings.sbd_watchdog_default,
                    node["name"],
                )
            )
        )
        return settings.sbd_watchdog_default

    return defaulter
