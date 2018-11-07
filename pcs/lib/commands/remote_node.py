from pcs.common import report_codes
from pcs.common.reports import SimpleReportProcessor
from pcs.lib import reports, node_communication_format
from pcs.lib.tools import generate_key
from pcs.lib.cib.resource import guest_node, primitive, remote_node
from pcs.lib.cib.tools import get_resources, find_element_by_tag_and_id
from pcs.lib.communication.nodes import (
    DistributeFiles,
    GetHostInfo,
    GetOnlineTargets,
    RemoveFiles,
    ServiceAction,
)
from pcs.lib.communication.tools import (
    run as run_com,
    run_and_raise,
)
from pcs.lib.env_tools import get_existing_nodes_names_addrs
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker import state
from pcs.lib.pacemaker.live import remove_node

def _reports_skip_new_node(new_node_name, reason_type):
    assert reason_type in {"unreachable", "not_live_cib"}
    return [
        reports.files_distribution_skipped(
            reason_type,
            ["pacemaker authkey"],
            [new_node_name]
        ),
        reports.service_commands_on_nodes_skipped(
            reason_type,
            ["pacemaker_remote start", "pacemaker_remote enable"],
            [new_node_name]
        ),
    ]

def _get_targets_for_add(
    target_factory, report_processor, existing_nodes_names, new_nodes_names,
    skip_offline_nodes
):
    # Get targets for all existing nodes and report unknown (not-authorized)
    # nodes.
    target_report_list, existing_target_list = (
        target_factory.get_target_list_with_reports(
            existing_nodes_names,
            skip_non_existing=skip_offline_nodes
        )
    )
    report_processor.report_list(target_report_list)
    # Get a target for the new node.
    target_report_list, new_target_list = (
        target_factory.get_target_list_with_reports(
            new_nodes_names,
            skip_non_existing=skip_offline_nodes,
            # continue even if the new node is unknown when skip is True
            report_none_host_found=False
        )
    )
    report_processor.report_list(target_report_list)
    return existing_target_list, new_target_list

def _host_check_remote_node(host_info_dict):
    # Version of services may not be the same across the existing cluster
    # nodes, so it's not easy to make this check properly.
    report_list = []
    required_service_list = ["pacemaker_remote"]
    required_as_stopped_service_list = (
        required_service_list + ["pacemaker", "corosync"]
    )
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
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
                report_list.append(
                    reports.host_already_in_cluster_services(
                        host_name,
                        cannot_be_running_service_list,
                    )
                )
            if host_info["cluster_configuration_exists"]:
                report_list.append(
                    reports.host_already_in_cluster_config(host_name)
                )
        except (KeyError, TypeError):
            report_list.append(reports.invalid_response_format(host_name))
    return report_list

def _prepare_pacemaker_remote_environment(
    env, report_processor, existing_nodes_target_list, new_node_target,
    new_node_name, skip_offline_nodes, allow_incomplete_distribution,
    allow_fails
):
    if new_node_target:
        com_cmd = GetOnlineTargets(
            report_processor,
            ignore_offline_targets=skip_offline_nodes,
        )
        com_cmd.set_targets([new_node_target])
        online_new_target_list = run_com(env.get_node_communicator(), com_cmd)
        if not online_new_target_list and not skip_offline_nodes:
            raise LibraryError()
    else:
        online_new_target_list = []

    # check new nodes
    if online_new_target_list:
        com_cmd = GetHostInfo(report_processor)
        com_cmd.set_targets(online_new_target_list)
        report_processor.report_list(
            _host_check_remote_node(
                run_com(env.get_node_communicator(), com_cmd)
            )
        )
        if report_processor.has_errors:
            raise LibraryError()
    else:
        report_processor.report_list(
            _reports_skip_new_node(new_node_name, "unreachable")
        )

    # share pacemaker authkey
    if env.pacemaker.has_authkey:
        authkey_content = env.pacemaker.get_authkey_content()
        authkey_targets = online_new_target_list
    else:
        authkey_content = generate_key()
        authkey_targets = existing_nodes_target_list + online_new_target_list
    if authkey_targets:
        com_cmd = DistributeFiles(
            report_processor,
            node_communication_format.pcmk_authkey_file(authkey_content),
            skip_offline_targets=skip_offline_nodes,
            allow_fails=allow_incomplete_distribution,
        )
        com_cmd.set_targets(authkey_targets)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # start and enable pacemaker_remote
    if online_new_target_list:
        com_cmd = ServiceAction(
            report_processor,
            node_communication_format.create_pcmk_remote_actions([
                "start",
                "enable",
            ]),
            allow_fails=allow_fails,
        )
        com_cmd.set_targets(online_new_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)

def _ensure_resource_running(env, resource_id):
    env.report_processor.process(
        state.ensure_resource_running(env.get_cluster_state(), resource_id)
    )

def node_add_remote(
    env, node_name, node_addr, operations, meta_attributes, instance_attributes,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    wait=False,
):
    """
    create an ocf:pacemaker:remote resource and use it as a remote node

    LibraryEnvironment env -- provides all for communication with externals
    string node_name -- the name of the new node
    mixed node_addr -- the address of the new node or None for default
    list of dict operations -- attributes for each entered operation
    dict meta_attributes -- attributes for primitive/meta_attributes
    dict instance_attributes -- attributes for primitive/instance_attributes
    bool skip_offline_nodes -- if True, ignore when some nodes are offline
    bool allow_incomplete_distribution -- if True, allow this command to
        finish successfully even if file distribution did not succeed
    bool allow_pacemaker_remote_service_fail -- if True, allow this command to
        finish successfully even if starting/enabling pacemaker_remote did not
        succeed
    bool allow_invalid_operation -- if True, allow to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes -- if True, allow to use instance
        attributes that are not listed in a resource agent metadata and allow to
        omit required instance_attributes
    bool use_default_operations -- if True, add operations specified in
        a resource agent metadata to the resource
    mixed wait -- a flag for controlling waiting for pacemaker idle mechanism
    """
    env.ensure_wait_satisfiable(wait)

    report_processor = SimpleReportProcessor(env.report_processor)
    target_factory = env.get_node_target_factory()
    cib = env.get_cib()
    if env.is_cib_live:
        corosync_conf = env.get_corosync_conf()
    else:
        corosync_conf = None
        report_processor.report(
            reports.corosync_node_conflict_check_skipped("not_live_cib")
        )
    existing_nodes_names, existing_nodes_addrs = get_existing_nodes_names_addrs(
       corosync_conf,
       cib
    )
    resource_agent = remote_node.get_agent(
        env.report_processor,
        env.cmd_runner()
    )

    existing_target_list = []
    if env.is_cib_live:
        existing_target_list, new_target_list = _get_targets_for_add(
            target_factory, report_processor, existing_nodes_names, [node_name],
            skip_offline_nodes
        )
        new_target = new_target_list[0] if new_target_list else None
        # default node_addr to an address from known-hosts
        if node_addr is None:
            node_addr = new_target.first_addr if new_target else node_name
            report_processor.report(
                reports.using_known_host_address_for_host(node_name, node_addr)
            )
    else:
        # default node_addr to an address from known-hosts
        if node_addr is None:
            known_hosts = env.get_known_hosts([node_name])
            node_addr = known_hosts[0].dest.addr if known_hosts else node_name
            report_processor.report(
                reports.using_known_host_address_for_host(node_name, node_addr)
            )

    # validate inputs
    report_list = remote_node.validate_create(
        existing_nodes_names,
        existing_nodes_addrs,
        resource_agent,
        node_name,
        node_addr,
        instance_attributes
    )
    # validation + cib setup
    # TODO extract the validation to a separate function
    try:
        remote_resource_element = remote_node.create(
            env.report_processor,
            resource_agent,
            get_resources(cib),
            node_addr,
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

    report_processor.report_list(report_list)
    if report_processor.has_errors:
        raise LibraryError()

    # everything validated, let's set it up
    if env.is_cib_live:
        _prepare_pacemaker_remote_environment(
            env,
            report_processor,
            existing_target_list,
            new_target,
            node_name,
            skip_offline_nodes,
            allow_incomplete_distribution,
            allow_pacemaker_remote_service_fail,
        )
    else:
        report_processor.report_list(
            _reports_skip_new_node(node_name, "not_live_cib")
        )

    env.push_cib(wait=wait)
    if wait:
        _ensure_resource_running(env, remote_resource_element.attrib["id"])

def node_add_guest(
    env, node_name, resource_id, options,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    wait=False,
):
    """
    Make a guest node from the specified resource

    LibraryEnvironment env -- provides all for communication with externals
    string node_name -- name of the guest node
    string resource_id -- specifies resource that should become a guest node
    dict options -- guest node options (remote-port, remote-addr,
        remote-connect-timeout)
    bool skip_offline_nodes -- if True, ignore when some nodes are offline
    bool allow_incomplete_distribution -- if True, allow this command to
        finish successfully even if file distribution did not succeed
    bool allow_pacemaker_remote_service_fail -- if True, allow this command to
        finish successfully even if starting/enabling pacemaker_remote did not
        succeed
    mixed wait -- a flag for controlling waiting for pacemaker idle mechanism
    """
    env.ensure_wait_satisfiable(wait)

    report_processor = SimpleReportProcessor(env.report_processor)
    target_factory = env.get_node_target_factory()
    cib = env.get_cib()
    if env.is_cib_live:
        corosync_conf = env.get_corosync_conf()
    else:
        corosync_conf = None
        report_processor.report(
            reports.corosync_node_conflict_check_skipped("not_live_cib")
        )
    existing_nodes_names, existing_nodes_addrs = get_existing_nodes_names_addrs(
       corosync_conf,
       cib
    )

    existing_target_list = []
    if env.is_cib_live:
        existing_target_list, new_target_list = _get_targets_for_add(
            target_factory, report_processor, existing_nodes_names, [node_name],
            skip_offline_nodes
        )
        new_target = new_target_list[0] if new_target_list else None
        # default remote-addr to an address from known-hosts
        if "remote-addr" not in options or options["remote-addr"] is None:
            new_addr = new_target.first_addr if new_target else node_name
            options["remote-addr"] = new_addr
            report_processor.report(
                reports.using_known_host_address_for_host(node_name, new_addr)
            )
    else:
        # default remote-addr to an address from known-hosts
        if "remote-addr" not in options or options["remote-addr"] is None:
            known_hosts = env.get_known_hosts([node_name])
            new_addr = known_hosts[0].dest.addr if known_hosts else node_name
            options["remote-addr"] = new_addr
            report_processor.report(
                reports.using_known_host_address_for_host(node_name, new_addr)
            )

    # validate inputs
    report_list = guest_node.validate_set_as_guest(
        cib,
        existing_nodes_names,
        existing_nodes_addrs,
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

    report_processor.report_list(report_list)
    if report_processor.has_errors:
        raise LibraryError()

    # everything validated, let's set it up
    guest_node.set_as_guest(
        resource_element,
        node_name,
        options.get("remote-addr", None),
        options.get("remote-port", None),
        options.get("remote-connect-timeout", None),
    )

    if env.is_cib_live:
        _prepare_pacemaker_remote_environment(
            env,
            report_processor,
            existing_target_list,
            new_target,
            node_name,
            skip_offline_nodes,
            allow_incomplete_distribution,
            allow_pacemaker_remote_service_fail,
        )
    else:
        report_processor.report_list(
            _reports_skip_new_node(node_name, "not_live_cib")
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

def _destroy_pcmk_remote_env(
    env, node_names_list, skip_offline_nodes, allow_fails
):
    actions = node_communication_format.create_pcmk_remote_actions([
        "stop",
        "disable",
    ])
    files = {
        "pacemaker_remote authkey": {"type": "pcmk_remote_authkey"},
    }
    target_list = env.get_node_target_factory().get_target_list(
        node_names_list,
        skip_non_existing=skip_offline_nodes,
    )

    com_cmd = ServiceAction(
        env.report_processor,
        actions,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = RemoveFiles(
        env.report_processor,
        files,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

def _report_skip_live_parts_in_remove(node_names_list):
    return [
        reports.service_commands_on_nodes_skipped(
            "not_live_cib",
            ["pacemaker_remote stop", "pacemaker_remote disable"],
            node_names_list
        ),
        reports.files_remove_from_nodes_skipped(
            "not_live_cib",
            ["pacemaker authkey"],
            node_names_list
        )
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

    cib = env.get_cib()
    resource_element_list = _find_resources_to_remove(
        cib,
        env.report_processor,
        "remote",
        node_identifier,
        allow_remove_multiple_nodes,
        remote_node.find_node_resources,
    )

    node_names_list = sorted({
        remote_node.get_node_name_from_resource(node_element)
        for node_element in resource_element_list
    })

    if not env.is_cib_live:
        env.report_processor.process_list(
            _report_skip_live_parts_in_remove(node_names_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_names_list,
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

    node_names_list = sorted({
        guest_node.get_node_name_from_resource(node_element)
        for node_element in resource_element_list
    })

    if not env.is_cib_live:
        env.report_processor.process_list(
            _report_skip_live_parts_in_remove(node_names_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_names_list,
            skip_offline_nodes,
            allow_pacemaker_remote_service_fail
        )

    for resource_element in resource_element_list:
        guest_node.unset_guest(resource_element)

    env.push_cib(wait=wait)

    #remove node from pcmk caches
    if env.is_cib_live:
        for node_name in node_names_list:
            remove_node(env.cmd_runner(), node_name)
