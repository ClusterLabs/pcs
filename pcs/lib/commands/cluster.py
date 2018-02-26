import math
import time

from pcs import settings
from pcs.common import report_codes
from pcs.lib import reports, node_communication_format
from pcs.lib.cib import fencing_topology
from pcs.lib.cib.tools import (
    generate_binary_key,
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
    StartCluster,
    UpdateKnownHosts,
)
from pcs.lib.communication.tools import (
    run as run_com,
    run_and_raise,
)
from pcs.lib.env_tools import get_nodes
from pcs.lib.errors import LibraryError
from pcs.lib.node import (
    node_addresses_contain_name,
    node_addresses_contain_host,
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

    current_nodes = get_nodes(env.get_corosync_conf(), env.get_cib())
    if(
        node_addresses_contain_name(current_nodes, node_name)
        or
        node_addresses_contain_host(current_nodes, node_name)
    ):
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
    env, cluster_name, nodes, transport_type, transport_options, link_list,
    cryptio_options, totem_options, quorum_options,
    wait=False, start=False, enable=False, force=False,
):
    # TODO: do some validations of inputs
    node_name_list = list(nodes.keys())
    report_list, target_list = (
        env.get_node_target_factory().get_target_list_with_reports(
            node_name_list, allow_skip=False,
        )
    )
    com_cmd = GetHostInfo(env.report_processor)
    com_cmd.set_targets(target_list)
    host_info_dict = run_com(env.get_node_communicator(), com_cmd)
    report_list.extend(
        com_cmd.error_list + _host_check_cluster_setup(host_info_dict, force)
    )
    if report_list:
        env.report_processor.process_list(report_list)

    com_cmd = cluster.Destroy(env.report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)
    # TODO: create corosync conf (only in memory)
    corosync_conf_text = ""
    corosync_authkey = generate_binary_key(random_bytes_count=128)
    pcmk_authkey = generate_binary_key(random_bytes_count=128)
    actions = {}
    actions.update(
        node_communication_format.corosync_authkey_file(corosync_authkey)
    )
    actions.update(
        node_communication_format.pcmk_authkey_file(pcmk_authkey)
    )

    com_cmd = UpdateKnownHosts(
        env.report_processor,
        known_hosts_to_add=env.get_known_hosts(
            [target.label for target in target_list]
        ),
        known_hosts_to_remove=[],
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = DistributeFilesWithoutForces(env.report_processor, actions)
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = RemoveFilesWithoutForces(
        env.report_processor, {"pcsd settings": {"type": "pcsd_settings"}},
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = DistributeFilesWithoutForces(
        env.report_processor,
        node_communication_format.corosync_conf_file(corosync_conf_text),
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    # TODO: distribute and reload pcsd certs

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
        # the --request-timeout option (see utils.sendHTTPRequest).
        timeout = int(
            settings.default_request_timeout * math.ceil(len(nodes) / 8.0)
        )
        com_cmd = StartCluster(env.report_processor)
        com_cmd.set_targets(target_list)
        run_and_raise(
            env.get_node_communicator(request_timeout=timeout), com_cmd
        )
        if wait:
            env.report_processor.process_list(
                _wait_for_pacemaker_to_start(
                    env.get_node_communicator(),
                    env.report_processor,
                    target_list,
                    wait if wait is not True else None,
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
            report_processor.process(reports.wait_for_node_startup_timed_out())
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
    service_version_dict = {
        "pacemaker": {},
        "corosync": {},
        "pcsd": {},
    }
    required_service_list = ["pacemaker", "corosync"]
    required_as_stopped_service_list = (
        required_service_list + ["pacemaker_remote"]
    )
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
            for service, version_dict in service_version_dict.items():
                version_dict[host_name] = services[service]["version"]
            missing_service_list = [
                service for service in required_service_list
                if not services[service]["installed"]
            ]
            running_service_list = [
                service for service in required_as_stopped_service_list
                if service[service]["running"]
            ]
            if missing_service_list:
                report_list.append(reports.service_not_installed(
                    host_name, missing_service_list
                ))
            if running_service_list:
                report_list.append(reports.service_running_unexpectedly(
                    host_name, running_service_list
                ))
            if host_info["cluster_configuration_exist"]:
                report_list.append(reports.host_already_in_cluster(host_name))
        except KeyError:
            report_list.append(reports.invalid_response_format(host_name))

    for service, version_dict in service_version_dict:
        report_list.append(
            _check_for_not_matching_service_versions(service, version_dict)
        )
    return report_list


def _check_for_not_matching_service_versions(service, service_version_dict):
    unique_service_version_set = set(service_version_dict.values())
    if len(unique_service_version_set) <= 1:
        return []
    hosts_to_version_dict = {
        version: [
            host_name for host_name, _version in service_version_dict.items()
            if version == _version
        ] for version in unique_service_version_set
    }
    return reports.service_version_mismatch(service, hosts_to_version_dict)
