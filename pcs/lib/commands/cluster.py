import math
import os.path
import time

from pcs import settings
from pcs.common import (
    env_file_role_codes,
    report_codes,
)
from pcs.common.tools import format_environment_error
from pcs.common.reports import SimpleReportProcessor
from pcs.common import ssl
from pcs.lib import reports, node_communication_format, sbd
from pcs.lib.booth import sync as booth_sync
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.resource.remote_node import find_node_list as get_remote_nodes
from pcs.lib.cib.resource.guest_node import find_node_list as get_guest_nodes
from pcs.lib.cib.tools import (
    get_fencing_topology,
    get_resources,
)
from pcs.lib.communication import cluster
from pcs.lib.communication.corosync import (
    CheckCorosyncOffline,
    DistributeCorosyncConf,
    ReloadCorosyncConf,
)
from pcs.lib.communication.nodes import (
    CheckPacemakerStarted,
    DistributeFilesWithoutForces,
    EnableCluster,
    GetHostInfo,
    GetOnlineTargets,
    RemoveFilesWithoutForces,
    SendPcsdSslCertAndKey,
    StartCluster,
    UpdateKnownHosts,
)
from pcs.lib.communication.sbd import (
    CheckSbd,
    SetSbdConfig,
    EnableSbdService,
    DisableSbdService,
)
from pcs.lib.communication.tools import (
    run as run_com,
    run_and_raise,
)
from pcs.lib.corosync import (
    config_facade,
    config_validators,
    constants as corosync_constants,
    qdevice_net,
)
from pcs.lib.env_tools import get_existing_nodes_names
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity,
)
from pcs.lib.pacemaker.live import (
    get_cib,
    get_cib_xml,
    get_cib_xml_cmd_results,
    get_cluster_status_xml,
    remove_node,
    verify as verify_cmd,
)
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.tools import (
    environment_file_to_dict,
    generate_binary_key,
)


def node_clear(env, node_name, allow_clear_cluster_node=False):
    """
    Remove specified node from various cluster caches.

    LibraryEnvironment env provides all for communication with externals
    string node_name
    bool allow_clear_cluster_node -- flag allows to clear node even if it's
        still in a cluster
    """
    mocked_envs = []
    if not env.is_cib_live:
        mocked_envs.append("CIB")
    if not env.is_corosync_conf_live:
        mocked_envs.append("COROSYNC_CONF")
    if mocked_envs:
        raise LibraryError(reports.live_environment_required(mocked_envs))

    current_nodes = get_existing_nodes_names(
        env.get_corosync_conf(),
        env.get_cib()
    )
    if node_name in current_nodes:
        env.report_processor.process(
            reports.get_problem_creator(
                report_codes.FORCE_CLEAR_CLUSTER_NODE,
                allow_clear_cluster_node
            )(
                reports.node_to_clear_is_still_in_cluster,
                node_name
            )
        )

    remove_node(env.cmd_runner(), node_name)

def verify(env, verbose=False):
    runner = env.cmd_runner()
    dummy_stdout, verify_stderr, verify_returncode = verify_cmd(
        runner,
        verbose=verbose,
    )

    #1) Do not even try to think about upgrading!
    #2) We do not need cib management in env (no need for push...).
    #So env.get_cib is not best choice here (there were considerations to
    #upgrade cib at all times inside env.get_cib). Go to a lower level here.
    if verify_returncode != 0:
        env.report_processor.append(reports.invalid_cib_content(verify_stderr))

        #Cib is sometimes loadable even if `crm_verify` fails (e.g. when
        #fencing topology is invalid). On the other hand cib with id duplication
        #is not loadable.
        #We try extra checks when cib is possible to load.
        cib_xml, dummy_stderr, returncode = get_cib_xml_cmd_results(runner)
        if returncode != 0:
            #can raise; raise LibraryError is better but in this case we prefer
            #be consistent with raising below
            env.report_processor.send()
    else:
        cib_xml = get_cib_xml(runner)

    cib = get_cib(cib_xml)
    fencing_topology.verify(
        env.report_processor,
        get_fencing_topology(cib),
        get_resources(cib),
        ClusterState(get_cluster_status_xml(runner)).node_section.nodes
    )
    #can raise
    env.report_processor.send()

def setup(
    env, cluster_name, nodes,
    transport_type=None, transport_options=None, link_list=None,
    compression_options=None, crypto_options=None, totem_options=None,
    quorum_options=None, wait=False, start=False, enable=False, force=False,
    force_unresolvable=False
):
    """
    Set up cluster on specified nodes.
    Validation of the inputs is done here. Possible existing clusters are
    destroyed (when using force). Authkey files for corosync and pacemaer,
    known hosts and and newly generated corosync.conf are distributed to all
    nodes.
    Raise LibraryError on any error.

    env LibraryEnvironment
    cluster_name string -- name of a cluster to set up
    nodes list -- list of dicts which represents node.
        Supported keys are: name (required), addrs
    transport_type string -- transport type of a cluster
    transport_options dict -- transport specific options
    link_list list of dict -- list of links, depends of transport_type
    compression_options dict -- only available for transport_type == 'knet'. In
        corosync.conf they are prefixed 'knet_compression_'
    crypto_options dict -- only available for transport_type == 'knet'. In
        corosync.conf they are prefixed 'crypto_'
    totem_options dict -- options of section 'totem' in corosync.conf
    quorum_options dict -- options of section 'quorum' in corosync.conf
    wait -- specifies if command should try to wait for cluster to start up.
        Has no effect start is False. If set to False command will not wait for
        cluster to start. If None command will wait for some default timeout.
        If int wait set timeout to int value of seconds.
    start bool -- if True start cluster when it is set up
    enable bool -- if True enable cluster when it is set up
    force bool -- if True some validations errors are treated as warnings
    force_unresolvable bool -- if True not resolvable addresses of nodes are
        treated as warnings
    """
    transport_options = transport_options or {}
    link_list = link_list or []
    compression_options = compression_options or {}
    crypto_options = crypto_options or {}
    totem_options = totem_options or {}
    quorum_options = quorum_options or {}
    nodes = [
        _normalize_dict(node, {"addrs"}) for node in nodes
    ]

    report_processor = SimpleReportProcessor(env.report_processor)
    target_factory = env.get_node_target_factory()

    # Get targets for all nodes and report unknown (== not-authorized) nodes.
    # If a node doesn't contain the 'name' key, validation of inputs reports it.
    # That means we don't report missing names but cannot rely on them being
    # present either.
    target_report_list, target_list = (
        target_factory.get_target_list_with_reports(
            [node["name"] for node in nodes if "name" in node],
            allow_skip=False,
        )
    )
    report_processor.report_list(target_report_list)

    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole cluster setup command / form significantly.
    addrs_defaulter = _get_addrs_defaulter(
        report_processor,
        {target.label: target for target in target_list}
    )
    nodes = [
        _set_defaults_in_dict(node, {"addrs": addrs_defaulter})
        for node in nodes
    ]

    # Validate inputs.
    report_processor.report_list(config_validators.create(
        cluster_name, nodes, transport_type,
        force_unresolvable=force_unresolvable
    ))
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        max_link_number = max(
            [len(node["addrs"]) for node in nodes],
            default=0
        )
        report_processor.report_list(
            config_validators.create_transport_knet(
                transport_options,
                compression_options,
                crypto_options
            )
            +
            config_validators.create_link_list_knet(
                link_list,
                max_link_number
            )
        )
    elif transport_type in corosync_constants.TRANSPORTS_UDP:
        report_processor.report_list(
            config_validators.create_transport_udp(
                transport_options,
                compression_options,
                crypto_options
            )
            +
            config_validators.create_link_list_udp(link_list)
        )
    report_processor.report_list(
        config_validators.create_totem(totem_options)
        +
        # We are creating the config and we know there is no qdevice in it.
        config_validators.create_quorum_options(quorum_options, False)
    )

    # Validate flags
    wait_timeout = _get_validated_wait_timeout(report_processor, wait, start)

    # Validate the nodes
    com_cmd = GetHostInfo(report_processor)
    com_cmd.set_targets(target_list)
    report_processor.report_list(
        _host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd), force
        )
    )

    if report_processor.has_errors:
        raise LibraryError()

    # Validation done. If errors occured, an exception has been raised and we
    # don't get below this line.

    # Destroy cluster on all nodes.
    com_cmd = cluster.Destroy(env.report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute auth tokens.
    com_cmd = UpdateKnownHosts(
        env.report_processor,
        known_hosts_to_add=env.get_known_hosts(
            [target.label for target in target_list]
        ),
        known_hosts_to_remove=[],
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute configuration files except corosync.conf. Sending
    # corosync.conf serves as a "commit" as its presence on a node marks the
    # node as a part of a cluster.
    corosync_authkey = generate_binary_key(random_bytes_count=128)
    pcmk_authkey = generate_binary_key(random_bytes_count=128)
    actions = {}
    actions.update(
        node_communication_format.corosync_authkey_file(corosync_authkey)
    )
    actions.update(
        node_communication_format.pcmk_authkey_file(pcmk_authkey)
    )
    com_cmd = DistributeFilesWithoutForces(env.report_processor, actions)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)
    # TODO This should be in the previous call but so far we don't have a call
    # which allows to save and delete files at the same time.
    com_cmd = RemoveFilesWithoutForces(
        env.report_processor, {"pcsd settings": {"type": "pcsd_settings"}},
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute and reload pcsd SSL certificate
    report_processor.report(
        reports.pcsd_ssl_cert_and_key_distribution_started(
            [target.label for target in target_list]
        )
    )
    ssl_key_raw = ssl.generate_key()
    ssl_key = ssl.dump_key(ssl_key_raw)
    ssl_cert = ssl.dump_cert(
        ssl.generate_cert(ssl_key_raw, target_list[0].label)
    )
    com_cmd = SendPcsdSslCertAndKey(env.report_processor, ssl_cert, ssl_key)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # Create and distribute corosync.conf. Once a node saves corosync.conf it
    # is considered to be in a cluster.
    corosync_conf = config_facade.ConfigFacade.create(
        cluster_name, nodes, transport_type
    )
    corosync_conf.set_totem_options(totem_options)
    corosync_conf.set_quorum_options(quorum_options)
    corosync_conf.create_link_list(link_list)
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        corosync_conf.set_transport_knet_options(
            transport_options, compression_options, crypto_options
        )
    elif transport_type in corosync_constants.TRANSPORTS_UDP:
        corosync_conf.set_transport_udp_options(transport_options)

    com_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.corosync_conf_file(
            corosync_conf.config.export()
        ),
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    env.report_processor.process(reports.cluster_setup_success())

    # Optionally enable and start cluster services.
    if enable:
        com_cmd = EnableCluster(env.report_processor)
        com_cmd.set_targets(target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)
    if start:
        _start_cluster(
            env.communicator_factory,
            env.report_processor,
            target_list,
            wait_timeout=wait_timeout,
        )

def add_nodes(
    env, nodes, wait=False, start=False, enable=False, force=False,
    force_unresolvable=False, skip_offline_nodes=False
):
    """
    Add specified nodes to the local cluster
    Raise LibraryError on any error.

    env LibraryEnvironment
    nodes list -- list of dicts which represents node.
        Supported keys are: name (required), addrs (list), devices (list),
        watchdog
    wait -- specifies if command should try to wait for cluster to start up.
        Has no effect start is False. If set to False command will not wait for
        cluster to start. If None command will wait for some default timeout.
        If int wait set timeout to int value of seconds.
    start bool -- if True start cluster when it is set up
    enable bool -- if True enable cluster when it is set up
    force bool -- if True some validations errors are treated as warnings
    force_unresolvable bool -- if True not resolvable addresses of nodes are
        treated as warnings
    skip_offline_nodes bool -- if True non fatal connection failures to other
        hosts are treated as warnings
    """
    new_nodes = [
        _normalize_dict(node, {"addrs", "devices", "watchdog"})
        for node in nodes
    ]

    report_processor = SimpleReportProcessor(env.report_processor)
    target_factory = env.get_node_target_factory()
    is_sbd_enabled = sbd.is_sbd_enabled(env.cmd_runner())
    corosync_conf = env.get_corosync_conf()
    cluster_nodes_names = corosync_conf.get_nodes_names()

    # get targets for existing nodes
    target_report_list, cluster_nodes_target_list = (
        target_factory.get_target_list_with_reports(
            cluster_nodes_names,
            skip_non_existing=skip_offline_nodes,
        )
    )
    report_processor.report_list(target_report_list)

    # Get targets for new nodes and report unknown (== not-authorized) nodes.
    # If a node doesn't contain the 'name' key, validation of inputs reports it.
    # That means we don't report missing names but cannot rely on them being
    # present either.
    target_report_list, new_nodes_target_list = (
        target_factory.get_target_list_with_reports(
            [node["name"] for node in new_nodes if "name" in node],
            allow_skip=False,
        )
    )
    report_processor.report_list(target_report_list)

    # Set default values for not-specified node options.
    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole node add command / form significantly.
    new_nodes_target_dict = {
        target.label: target for target in new_nodes_target_list
    }
    addrs_defaulter = _get_addrs_defaulter(
        report_processor,
        new_nodes_target_dict
    )
    watchdog_defaulter = _get_watchdog_defaulter(
        report_processor,
        new_nodes_target_dict,
        is_sbd_enabled
    )
    new_nodes = [
        _set_defaults_in_dict(node, {
            "addrs": addrs_defaulter,
            "devices": lambda _: [],
            "watchdog": watchdog_defaulter,
        })
        for node in new_nodes
    ]
    new_nodes_dict = {node["name"]: node for node in new_nodes}

    # Validate inputs - corosync part
    cib = env.get_cib()
    # corosync validator rejects non-corosync keys
    new_nodes_corosync = [
        {key: node[key] for key in ("name", "addrs") if key in node}
        for node in new_nodes
    ]
    report_processor.report_list(config_validators.add_nodes(
        new_nodes_corosync,
        corosync_conf.get_nodes(),
        get_remote_nodes(cib) + get_guest_nodes(cib),
        force_unresolvable=force_unresolvable
    ))

    # Validate inputs - SBD part
    report_processor.report_list(
        sbd.validate_new_nodes_devices(
            is_sbd_enabled,
            {
                node["name"]: node["devices"]
                for node in new_nodes if "name" in node
            }
        )
    )

    # Validate inputs - flags part
    wait_timeout = _get_validated_wait_timeout(report_processor, wait, start)

    # Get online cluster nodes
    # This is the only call in which we accept skip_offline_nodes option for the
    # cluster nodes. In all the other actions we communicate only with the
    # online nodes. This allows us to simplify code as any communication issue
    # is considered an error, ends the commande processing and is not possible
    # to skip it by skip_offline_nodes. We do not have to care about a situation
    # when a communication command cannot connect to some nodes and then the
    # next command can connect but fails due to the previous one did not
    # succeed.
    com_cmd = GetOnlineTargets(
        report_processor, ignore_offline_targets=skip_offline_nodes,
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    online_cluster_target_list = run_com(env.get_node_communicator(), com_cmd)
    offline_cluster_target_list = [
        target for target in cluster_nodes_target_list
        if target not in online_cluster_target_list
    ]
    if len(online_cluster_target_list) == 0:
        # TODO: report (error) that no cluster node is online
        # report_processor.report(None)
        pass
    elif offline_cluster_target_list and skip_offline_nodes:
        # TODO: report (warn) how to fix offline nodes when they come online
        # report_processor.report(None)
        pass

    # Validate existing cluster nodes status
    atb_has_to_be_enabled = sbd.atb_has_to_be_enabled(
        env.cmd_runner(), corosync_conf, len(new_nodes)
    )
    if atb_has_to_be_enabled:
        report_processor.report(
            reports.corosync_quorum_atb_will_be_enabled_due_to_sbd()
        )
        com_cmd = CheckCorosyncOffline(
            report_processor, allow_skip_offline=False,
        )
        com_cmd.set_targets(online_cluster_target_list)
        run_com(env.get_node_communicator(), com_cmd)

    # Validate new nodes. All new nodes have to be online.
    com_cmd = GetHostInfo(report_processor)
    com_cmd.set_targets(new_nodes_target_list)
    report_processor.report_list(
        _host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd),
            force,
            # version of services may not be the same across the existing
            # cluster nodes, so it's not easy to make this check properly
            check_services_versions=False,
        )
    )

    # Validate SBD on new nodes
    if is_sbd_enabled:
        com_cmd = CheckSbd(report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            com_cmd.add_request(
                new_node_target,
                watchdog=new_node["watchdog"],
                device_list=new_node["devices"],
            )
        run_com(env.get_node_communicator(), com_cmd)
    else:
        # TODO validate that "watchdog" and "devices" options are not set
        # Note that the watchdogs and the devices are initialized by some
        # defaults if not specified by the user, therefore this check has to be
        # performed before the actual initilization
        pass

    if report_processor.has_errors:
        raise LibraryError()

    # Validation done. If errors occured, an exception has been raised and we
    # don't get below this line.

    # First set up everything else than corosync. Once the new nodes are present
    # in corosync.conf, they're considered part of a cluster and the node add
    # command cannot be run again. So we need to minimize the amout of actions
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
    qdevice_model, qdevice_model_options, _, _ = (
        corosync_conf.get_quorum_device_settings()
    )
    if qdevice_model == "net":
        qdevice_net.set_up_client_certificates(
            env.cmd_runner(),
            env.report_processor,
            env.communicator_factory,
            target_factory.get_target_from_hostname(
                qdevice_model_options["host"]
            ),
            corosync_conf.get_cluster_name(),
            new_nodes_target_list,
            # we don't want to allow skiping offline nodes which are being
            # added, otherwise qdevice will not work properly
            skip_offline_nodes=False
        )

    # sbd setup
    if is_sbd_enabled:
        sbd_cfg = environment_file_to_dict(sbd.get_local_sbd_config())

        com_cmd = SetSbdConfig(env.report_processor)
        for new_node_target in new_nodes_target_list:
            new_node = new_nodes_dict[new_node_target.label]
            com_cmd.add_request(
                new_node_target,
                sbd.create_sbd_config(
                    sbd_cfg,
                    new_node["name"],
                    watchdog=new_node["watchdog"],
                    device_list=new_node["devices"],
                )
            )
        run_and_raise(env.get_node_communicator(), com_cmd)

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

    # distribute corosync and pacemaker authkeys
    files_action = {}
    forceable_io_error_creator = reports.get_problem_creator(
        report_codes.SKIP_FILE_DISTRIBUTION_ERRORS, force
    )
    if os.path.isfile(settings.corosync_authkey_file):
        try:
            files_action.update(
                node_communication_format.corosync_authkey_file(
                    open(settings.corosync_authkey_file, "rb").read()
                )
            )
        except EnvironmentError as e:
            report_processor.report(forceable_io_error_creator(
                reports.file_io_error,
                env_file_role_codes.COROSYNC_AUTHKEY,
                file_path=settings.corosync_authkey_file,
                operation="read",
                reason=format_environment_error(e)
            ))

    if os.path.isfile(settings.pacemaker_authkey_file):
        try:
            files_action.update(
                node_communication_format.pcmk_authkey_file(
                    open(settings.pacemaker_authkey_file, "rb").read()
                )
            )
        except EnvironmentError as e:
            report_processor.report(forceable_io_error_creator(
                reports.file_io_error,
                env_file_role_codes.PACEMAKER_AUTHKEY,
                file_path=settings.pacemaker_authkey_file,
                operation="read",
                reason=format_environment_error(e)
            ))

    # pcs_settings.conf was previously synced using pcsdcli send_local_configs.
    # This has been changed temporarily until new system for distribution and
    # syncronization of configs will be introduced.
    if os.path.isfile(settings.pcsd_settings_conf_location):
        try:
            files_action.update(
                node_communication_format.pcs_settings_conf_file(
                    open(settings.pcsd_settings_conf_location, "r").read()
                )
            )
        except EnvironmentError as e:
            report_processor.report(forceable_io_error_creator(
                reports.file_io_error,
                env_file_role_codes.PCS_SETTINGS_CONF,
                file_path=settings.pcsd_settings_conf_location,
                operation="read",
                reason=format_environment_error(e)
            ))

    # stop here if one of the files could not be loaded and it was not forced
    if report_processor.has_errors:
        raise LibraryError()

    if files_action:
        com_cmd = DistributeFilesWithoutForces(
            env.report_processor,
            files_action
        )
        com_cmd.set_targets(new_nodes_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # Distribute and reload pcsd SSL certificate
    report_processor.report(
        reports.pcsd_ssl_cert_and_key_distribution_started(
            [target.label for target in new_nodes_target_list]
        )
    )

    try:
        with open(settings.pcsd_cert_location, "r") as f:
            ssl_cert = f.read()
    except EnvironmentError as e:
        report_processor.report(
            reports.file_io_error(
                env_file_role_codes.PCSD_SSL_CERT,
                file_path=settings.pcsd_cert_location,
                reason=format_environment_error(e),
                operation="read",
            )
        )
    try:
        with open(settings.pcsd_key_location, "r") as f:
            ssl_key = f.read()
    except EnvironmentError as e:
        report_processor.report(
            reports.file_io_error(
                env_file_role_codes.PCSD_SSL_KEY,
                file_path=settings.pcsd_key_location,
                reason=format_environment_error(e),
                operation="read",
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
        _start_cluster(
            env.communicator_factory,
            env.report_processor,
            new_nodes_target_list,
            wait_timeout=wait_timeout,
        )

def _start_cluster(
    communicator_factory, report_processor, target_list, wait_timeout=False,
):
    # Large clusters take longer time to start up. So we make the timeout
    # longer for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on ...
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option.
    timeout = int(
        settings.default_request_timeout * math.ceil(len(target_list) / 8.0)
    )
    com_cmd = StartCluster(report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(
        communicator_factory.get_communicator(request_timeout=timeout), com_cmd
    )
    if wait_timeout is not False:
        report_processor.process_list(
            _wait_for_pacemaker_to_start(
                communicator_factory.get_communicator(),
                report_processor,
                target_list,
                timeout=wait_timeout, # wait_timeout is either None or a timeout
            )
        )

def _wait_for_pacemaker_to_start(
    node_communicator, report_processor, target_list, timeout=None
):
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = time.time() + timeout
    report_processor.process(
        reports.wait_for_node_startup_started(
            [target.label for target in target_list]
        )
    )
    error_report_list = []
    while target_list:
        if time.time() > stop_at:
            error_report_list.append(reports.wait_for_node_startup_timed_out())
            break
        time.sleep(interval)
        com_cmd = CheckPacemakerStarted(report_processor)
        com_cmd.set_targets(target_list)
        target_list = run_com(node_communicator, com_cmd)
        error_report_list.extend(com_cmd.error_list)

    if error_report_list:
        error_report_list.append(reports.wait_for_node_startup_error())
    return error_report_list

def _host_check_cluster_setup(
    host_info_dict, force, check_services_versions=True
):
    report_list = []
    # We only care about services which matter for creating a cluster. It does
    # not make sense to check e.g. booth when a) it will never be used b) it
    # will be used in a year - which means we should do the check in a year.
    service_version_dict = {
        "pacemaker": {},
        "corosync": {},
        "pcsd": {},
    }
    required_service_list = ["pacemaker", "corosync"]
    required_as_stopped_service_list = (
        required_service_list + ["pacemaker_remote"]
    )
    report_severity = (
        ReportItemSeverity.ERROR if not force else ReportItemSeverity.WARNING
    )
    cluster_exists_on_nodes = False
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
            if check_services_versions:
                for service, version_dict in service_version_dict.items():
                    version_dict[host_name] = services[service]["version"]
            missing_service_list = [
                service for service in required_service_list
                if not services[service]["installed"]
            ]
            if missing_service_list:
                report_list.append(reports.service_not_installed(
                    host_name, missing_service_list
                ))
            cannot_be_running_service_list = [
                service for service in required_as_stopped_service_list
                if service in services and services[service]["running"]
            ]
            if cannot_be_running_service_list:
                cluster_exists_on_nodes = True
                report_list.append(
                    reports.host_already_in_cluster_services(
                        host_name,
                        cannot_be_running_service_list,
                        severity=report_severity,
                    )
                )
            if host_info["cluster_configuration_exists"]:
                cluster_exists_on_nodes = True
                report_list.append(
                    reports.host_already_in_cluster_config(
                        host_name,
                        severity=report_severity,
                    )
                )
        except KeyError:
            report_list.append(reports.invalid_response_format(host_name))

    if check_services_versions:
        for service, version_dict in service_version_dict.items():
            report_list.extend(
                _check_for_not_matching_service_versions(service, version_dict)
            )

    if cluster_exists_on_nodes and not force:
        report_list.append(reports.cluster_will_be_destroyed())
    return report_list

def _check_for_not_matching_service_versions(service, service_version_dict):
    if len(set(service_version_dict.values())) <= 1:
        return []
    return [
        reports.service_version_mismatch(service, service_version_dict)
    ]

def _normalize_dict(input_dict, required_keys):
    normalized = dict(input_dict)
    for key in required_keys:
        if key not in normalized:
            normalized[key] = None
    return normalized

def _set_defaults_in_dict(input_dict, defaults):
    completed = dict(input_dict)
    for key, factory in defaults.items():
        if completed[key] is None:
            completed[key] = factory(input_dict)
    return completed

def _get_addrs_defaulter(
    report_processor: SimpleReportProcessor, targets_dict
):
    def defaulter(node):
        if "name" not in node:
            return []
        target = targets_dict.get(node["name"])
        if target:
            report_processor.report(
                reports.using_known_host_address_for_host(
                    node["name"], target.first_addr
                )
            )
            return [target.first_addr]
        return []
    return defaulter

def _get_watchdog_defaulter(
    report_processor: SimpleReportProcessor, targets_dict, is_sbd_enabled
):
    def defaulter(node):
        if is_sbd_enabled:
            report_processor.report(reports.using_default_watchdog(
                settings.sbd_watchdog_default,
                node["name"],
            ))
            return settings.sbd_watchdog_default
        return None
    return defaulter

def _get_validated_wait_timeout(report_processor, wait, start):
    try:
        if wait is False:
            return False
        if not start:
            report_processor.report(
                reports.wait_for_node_startup_without_start()
            )
        return get_valid_timeout_seconds(wait)
    except LibraryError as e:
        report_processor.report_list(e.args)
    return None
