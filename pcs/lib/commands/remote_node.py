from pcs.common import report_codes
from pcs.lib import reports, node_communication_format
from pcs.lib.node import(
    NodeAddresses,
    NodeAddressesList,
)
from pcs.lib.tools import generate_key
from pcs.lib.cib.resource import guest_node, primitive, remote_node
from pcs.lib.cib.tools import get_resources, find_element_by_tag_and_id
from pcs.lib.communication.nodes import (
    availability_checker_remote_node,
    DistributeFiles,
    PrecheckNewNode,
    RemoveFiles,
    ServiceAction,
)
from pcs.lib.communication.tools import run, run_and_raise
from pcs.lib.env_tools import get_nodes, get_nodes_remote, get_nodes_guest
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker import state
from pcs.lib.pacemaker.live import remove_node

def _ensure_can_add_node_to_remote_cluster(
    env, node_addresses, warn_on_communication_exception=False
):
    report_items = []
    com_cmd = PrecheckNewNode(
        report_items,
        availability_checker_remote_node,
        skip_offline_targets=warn_on_communication_exception,
    )
    com_cmd.add_request(
        env.get_node_target_factory().get_target(node_addresses)
    )
    run(env.get_node_communicator(), com_cmd)
    env.report_processor.process_list(report_items)

def _share_authkey(
    env, current_nodes, candidate_node_addresses,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False
):
    if env.pacemaker.has_authkey:
        authkey_content = env.pacemaker.get_authkey_content()
        node_addresses_list = NodeAddressesList([candidate_node_addresses])
    else:
        authkey_content = generate_key()
        node_addresses_list = current_nodes + [candidate_node_addresses]

    com_cmd = DistributeFiles(
        env.report_processor,
        node_communication_format.pcmk_authkey_file(authkey_content),
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_incomplete_distribution,
        description="remote node configuration files",
    )
    com_cmd.set_targets(
        env.get_node_target_factory().get_target_list(node_addresses_list)
    )
    run_and_raise(env.get_node_communicator(), com_cmd)

def _start_and_enable_pacemaker_remote(
    env, node_list, skip_offline_nodes=False, allow_fails=False
):
    com_cmd = ServiceAction(
        env.report_processor,
        node_communication_format.create_pcmk_remote_actions([
            "start",
            "enable",
        ]),
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
        description="start of service pacemaker_remote"
    )
    com_cmd.set_targets(
        env.get_node_target_factory().get_target_list(node_list)
    )
    run_and_raise(env.get_node_communicator(), com_cmd)

def _prepare_pacemaker_remote_environment(
    env, current_nodes, node_host, skip_offline_nodes,
    allow_incomplete_distribution, allow_fails
):
    if not env.is_corosync_conf_live:
        env.report_processor.process_list([
            reports.nolive_skip_files_distribution(
                ["pacemaker authkey"],
                [node_host]
            ),
            reports.nolive_skip_service_command_on_nodes(
                "pacemaker_remote",
                "start",
                [node_host]
            ),
            reports.nolive_skip_service_command_on_nodes(
                "pacemaker_remote",
                "enable",
                [node_host]
            ),
        ])
        return

    candidate_node = NodeAddresses(node_host)
    _ensure_can_add_node_to_remote_cluster(
        env,
        candidate_node,
        skip_offline_nodes
    )
    _share_authkey(
        env,
        current_nodes,
        candidate_node,
        skip_offline_nodes,
        allow_incomplete_distribution
    )
    _start_and_enable_pacemaker_remote(
        env,
        [candidate_node],
        skip_offline_nodes,
        allow_fails
    )

def _ensure_resource_running(env, resource_id):
    env.report_processor.process(
        state.ensure_resource_running(env.get_cluster_state(), resource_id)
    )

def _ensure_consistently_live_env(env):
    if env.is_cib_live and env.is_corosync_conf_live:
        return

    #we accept is as well, we need it for tests
    if not env.is_cib_live and not env.is_corosync_conf_live:
        return

    raise LibraryError(reports.live_environment_required([
        "CIB" if not env.is_cib_live else "COROSYNC_CONF"
    ]))


def node_add_remote(
    env, host, node_name, operations, meta_attributes, instance_attributes,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    wait=False,
):
    """
    create resource ocf:pacemaker:remote and use it as remote node

    LibraryEnvironment env provides all for communication with externals
    list of dict operations contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    bool skip_offline_nodes -- a flag for ignoring when some nodes are offline
    bool allow_incomplete_distribution -- is a flag for allowing successfully
        finish this command even if is file distribution not succeeded
    bool allow_pacemaker_remote_service_fail -- is a flag for allowing
        successfully finish this command even if starting/enabling
        pacemaker_remote not succeeded
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
    """
    _ensure_consistently_live_env(env)
    env.ensure_wait_satisfiable(wait)

    cib = env.get_cib()
    current_nodes = get_nodes(env.get_corosync_conf(), cib)

    resource_agent = remote_node.get_agent(
        env.report_processor,
        env.cmd_runner()
    )

    report_list = remote_node.validate_create(
        current_nodes,
        resource_agent,
        host,
        node_name,
        instance_attributes
    )

    try:
        remote_resource_element = remote_node.create(
            env.report_processor,
            resource_agent,
            get_resources(cib),
            host,
            node_name,
            operations,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
    except LibraryError as e:
        #Check unique id conflict with check against nodes. Until validation
        #resource create is not separated, we need to make unique post
        #validation.
        already_exists = []
        unified_report_list = []
        for report in report_list + list(e.args):
            if report.code != report_codes.ID_ALREADY_EXISTS:
                unified_report_list.append(report)
            elif report.info["id"] not in already_exists:
                unified_report_list.append(report)
                already_exists.append(report.info["id"])
        report_list = unified_report_list

    env.report_processor.process_list(report_list)

    _prepare_pacemaker_remote_environment(
        env,
        current_nodes,
        host,
        skip_offline_nodes,
        allow_incomplete_distribution,
        allow_pacemaker_remote_service_fail,
    )
    env.push_cib(wait=wait)
    if wait:
        _ensure_resource_running(env, remote_resource_element.attrib["id"])

def node_add_guest(
    env, node_name, resource_id, options,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False, wait=False,
):

    """
    setup resource (resource_id) as guest node and setup node as guest

    LibraryEnvironment env provides all for communication with externals
    string resource_id -- specifies resource that should be guest node
    dict options could contain keys remote-node, remote-port, remote-addr,
        remote-connect-timeout
    bool skip_offline_nodes -- a flag for ignoring when some nodes are offline
    bool allow_incomplete_distribution -- is a flag for allowing successfully
        finish this command even if is file distribution not succeeded
    bool allow_pacemaker_remote_service_fail -- is a flag for allowing
        successfully finish this command even if starting/enabling
        pacemaker_remote not succeeded
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
    """
    _ensure_consistently_live_env(env)
    env.ensure_wait_satisfiable(wait)

    cib = env.get_cib()
    current_nodes = get_nodes(env.get_corosync_conf(), cib)

    report_list = guest_node.validate_set_as_guest(
        cib,
        current_nodes,
        node_name,
        options
    )
    try:
        resource_element = find_element_by_tag_and_id(
            primitive.TAG,
            get_resources(cib),
            resource_id
        )
        report_list.extend(guest_node.validate_is_not_guest(resource_element))
    except LibraryError as e:
        report_list.extend(e.args)

    env.report_processor.process_list(report_list)

    guest_node.set_as_guest(
        resource_element,
        node_name,
        options.get("remote-addr", None),
        options.get("remote-port", None),
        options.get("remote-connect-timeout", None),
    )

    _prepare_pacemaker_remote_environment(
        env,
        current_nodes,
        guest_node.get_host_from_options(node_name, options),
        skip_offline_nodes,
        allow_incomplete_distribution,
        allow_pacemaker_remote_service_fail,
    )

    env.push_cib(wait=wait)
    if wait:
        _ensure_resource_running(env, resource_id)

def _find_resources_to_remove(
    cib, report_processor,
    node_type, node_identifier, allow_remove_multiple_nodes,
    find_resources
):
    resource_element_list = find_resources(get_resources(cib), node_identifier)

    if not resource_element_list:
        raise LibraryError(reports.node_not_found(node_identifier, node_type))

    if len(resource_element_list) > 1:
        report_processor.process(
            reports.get_problem_creator(
                report_codes.FORCE_REMOVE_MULTIPLE_NODES,
                allow_remove_multiple_nodes
            )(
                reports.multiple_result_found,
                "resource",
                [resource.attrib["id"] for resource in resource_element_list],
                node_identifier
            )
        )

    return resource_element_list

def _get_node_addresses_from_resources(nodes, resource_element_list, get_host):
    node_addresses_set = set()
    for resource_element in resource_element_list:
        for node in nodes:
            #remote nodes uses ring0 only
            if get_host(resource_element) == node.ring0:
                node_addresses_set.add(node)
    return sorted(node_addresses_set, key=lambda node: node.ring0)

def _destroy_pcmk_remote_env(
    env, node_addresses_list, skip_offline_nodes, allow_fails
):
    actions = node_communication_format.create_pcmk_remote_actions([
        "stop",
        "disable",
    ])
    files = {
        "pacemaker_remote authkey": {"type": "pcmk_remote_authkey"},
    }
    target_list = env.get_node_target_factory().get_target_list(
        node_addresses_list
    )

    com_cmd = ServiceAction(
        env.report_processor,
        actions,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
        description="stop of service pacemaker_remote",
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = RemoveFiles(
        env.report_processor,
        files,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
        description="remote node files",
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def _report_skip_live_parts_in_remove(node_addresses_list):
    #remote nodes uses ring0 only
    node_host_list = [addresses.ring0 for addresses in node_addresses_list]
    return [
        reports.nolive_skip_service_command_on_nodes(
            "pacemaker_remote",
            "stop",
            node_host_list
        ),
        reports.nolive_skip_service_command_on_nodes(
            "pacemaker_remote",
            "disable",
            node_host_list
        ),
        reports.nolive_skip_files_remove(["pacemaker authkey"], node_host_list)
    ]

def node_remove_remote(
    env, node_identifier, remove_resource,
    skip_offline_nodes=False,
    allow_remove_multiple_nodes=False,
    allow_pacemaker_remote_service_fail=False
):
    """
    remove a resource representing remote node and destroy remote node

    LibraryEnvironment env provides all for communication with externals
    string node_identifier -- node name or hostname
    callable remove_resource -- function for remove resource
    bool skip_offline_nodes -- a flag for ignoring when some nodes are offline
    bool allow_remove_multiple_nodes -- is a flag for allowing
        remove unexpected multiple occurence of remote node for node_identifier
    bool allow_pacemaker_remote_service_fail -- is a flag for allowing
        successfully finish this command even if stoping/disabling
        pacemaker_remote not succeeded
    """

    _ensure_consistently_live_env(env)
    cib = env.get_cib()
    resource_element_list = _find_resources_to_remove(
        cib,
        env.report_processor,
        "remote",
        node_identifier,
        allow_remove_multiple_nodes,
        remote_node.find_node_resources,
    )

    node_addresses_list = _get_node_addresses_from_resources(
        get_nodes_remote(cib),
        resource_element_list,
        remote_node.get_host,
    )

    if not env.is_corosync_conf_live:
        env.report_processor.process_list(
            _report_skip_live_parts_in_remove(node_addresses_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_addresses_list,
            skip_offline_nodes,
            allow_pacemaker_remote_service_fail
        )

    #remove node from pcmk caches is currently integrated in remove_resource
    #function
    for resource_element in resource_element_list:
        remove_resource(
            resource_element.attrib["id"],
            is_remove_remote_context=True,
        )

def node_remove_guest(
    env, node_identifier,
    skip_offline_nodes=False,
    allow_remove_multiple_nodes=False,
    allow_pacemaker_remote_service_fail=False,
    wait=False,
):
    """
    remove a resource representing remote node and destroy remote node

    LibraryEnvironment env provides all for communication with externals
    string node_identifier -- node name, hostname or resource id
    bool skip_offline_nodes -- a flag for ignoring when some nodes are offline
    bool allow_remove_multiple_nodes -- is a flag for allowing
        remove unexpected multiple occurence of remote node for node_identifier
    bool allow_pacemaker_remote_service_fail -- is a flag for allowing
        successfully finish this command even if stoping/disabling
        pacemaker_remote not succeeded
    """
    _ensure_consistently_live_env(env)
    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()

    resource_element_list = _find_resources_to_remove(
        cib,
        env.report_processor,
        "guest",
        node_identifier,
        allow_remove_multiple_nodes,
        guest_node.find_node_resources,
    )

    node_addresses_list = _get_node_addresses_from_resources(
        get_nodes_guest(cib),
        resource_element_list,
        guest_node.get_host,
    )

    if not env.is_corosync_conf_live:
        env.report_processor.process_list(
            _report_skip_live_parts_in_remove(node_addresses_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_addresses_list,
            skip_offline_nodes,
            allow_pacemaker_remote_service_fail
        )

    for resource_element in resource_element_list:
        guest_node.unset_guest(resource_element)

    env.push_cib(wait=wait)

    #remove node from pcmk caches
    if env.is_cib_live:
        for node_addresses in node_addresses_list:
            remove_node(env.cmd_runner(), node_addresses.name)
