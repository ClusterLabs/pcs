import math
import time

from pcs import settings
from pcs.common import report_codes
from pcs.common.reports import SimpleReportProcessor
from pcs.common import ssl
from pcs.lib import reports, node_communication_format
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.tools import (
    get_fencing_topology,
    get_resources,
)
from pcs.lib.communication import cluster
from pcs.lib.communication.nodes import (
    CheckPacemakerStarted,
    DistributeFilesWithoutForces,
    EnableCluster,
    GetHostInfo,
    RemoveFilesWithoutForces,
    SendPcsdSslCertAndKey,
    StartCluster,
    UpdateKnownHosts,
)
from pcs.lib.communication.tools import (
    run as run_com,
    run_and_raise,
)
from pcs.lib.corosync import (
    config_facade,
    config_validators,
    constants as corosync_constants
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
from pcs.lib.tools import generate_binary_key


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

    _report_processor = SimpleReportProcessor(env.report_processor)
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
    _report_processor.report_list(target_report_list)

    # Use an address defined in known-hosts for each node with no addresses
    # specified. This allows users not to specify node addresses at all which
    # simplifies the whole cluster setup command / form significantly.
    addrs_defaulter = _get_addrs_defaulter(
        _report_processor,
        {target.label: target for target in target_list}
    )
    nodes = [
        _set_defaults_in_dict(node, {"addrs": addrs_defaulter})
        for node in nodes
    ]

    # Validate inputs.
    _report_processor.report_list(config_validators.create(
        cluster_name, nodes, transport_type,
        force_unresolvable=force_unresolvable
    ))
    if transport_type in corosync_constants.TRANSPORTS_KNET:
        max_link_number = max(
            [len(node["addrs"]) for node in nodes],
            default=0
        )
        _report_processor.report_list(
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
        _report_processor.report_list(
            config_validators.create_transport_udp(
                transport_options,
                compression_options,
                crypto_options
            )
            +
            config_validators.create_link_list_udp(link_list)
        )
    _report_processor.report_list(
        config_validators.create_totem(totem_options)
        +
        # We are creating the config and we know there is no qdevice in it.
        config_validators.create_quorum_options(quorum_options, False)
    )

    try:
        if wait is False:
            wait_timeout = False
        else:
            if not start:
                _report_processor.report(
                    reports.wait_for_node_startup_without_start()
                )
            wait_timeout = get_valid_timeout_seconds(wait)
    except LibraryError as e:
        _report_processor.report_list(e.args)

    # Validate the nodes.
    com_cmd = GetHostInfo(_report_processor)
    com_cmd.set_targets(target_list)
    _report_processor.report_list(
        _host_check_cluster_setup(
            run_com(env.get_node_communicator(), com_cmd), force
        )
    )

    if _report_processor.has_errors:
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
    _report_processor.report(
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
        # Large clusters take longer time to start up. So we make the timeout
        # longer for each 8 nodes:
        #  1 -  8 nodes: 1 * timeout
        #  9 - 16 nodes: 2 * timeout
        # 17 - 24 nodes: 3 * timeout
        # and so on ...
        # Users can override this and set their own timeout by specifying
        # the --request-timeout option.
        timeout = int(
            settings.default_request_timeout * math.ceil(len(nodes) / 8.0)
        )
        com_cmd = StartCluster(env.report_processor)
        com_cmd.set_targets(target_list)
        run_and_raise(
            env.get_node_communicator(request_timeout=timeout),
            com_cmd
        )
        if wait_timeout is not False:
            env.report_processor.process_list(
                _wait_for_pacemaker_to_start(
                    env.get_node_communicator(),
                    env.report_processor,
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


def _host_check_cluster_setup(host_info_dict, force):
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
            running_service_list = [
                service for service in required_as_stopped_service_list
                if services[service]["running"]
            ]
            if running_service_list:
                cluster_exists_on_nodes = True
                report_list.append(
                    reports.host_already_in_cluster_services(
                        host_name,
                        running_service_list,
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
