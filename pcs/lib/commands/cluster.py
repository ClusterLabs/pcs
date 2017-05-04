from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib import reports, nodes_task, node_communication_format
from pcs.lib.node import NodeAddresses, NodeAddressesList
from pcs.lib.tools import generate_key
from pcs.lib.cib.resource import guest_node, primitive, remote_node
from pcs.lib.cib.tools import get_resources, find_element_by_tag_and_id
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker import state
from pcs.lib.pacemaker.live import remove_node

def _ensure_can_add_node_to_remote_cluster(env, node_addresses):
    report_items = []
    nodes_task.check_can_add_node_to_cluster(
        env.node_communicator(),
        node_addresses,
        report_items,
        check_response=nodes_task.availability_checker_remote_node
    )
    env.report_processor.process_list(report_items)

def _share_authkey(
    env, candidate_node_addresses, allow_incomplete_distribution=False
):
    if env.pacemaker.has_authkey:
        authkey_content = env.pacemaker.get_authkey_content()
        node_addresses_list = NodeAddressesList([candidate_node_addresses])
    else:
        authkey_content = generate_key()
        node_addresses_list = env.nodes.all + [candidate_node_addresses]

    nodes_task.distribute_files(
        env.node_communicator(),
        env.report_processor,
        node_communication_format.pcmk_authkey_file(authkey_content),
        node_addresses_list,
        allow_incomplete_distribution
    )

def _start_and_enable_pacemaker_remote(env, node_list, allow_fails=False):
    nodes_task.run_actions_on_multiple_nodes(
        env.node_communicator(),
        env.report_processor,
        node_communication_format.create_pcmk_remote_actions([
            "start",
            "enable",
        ]),
        lambda key, response: response.code == "success",
        node_list,
        allow_fails,
    )

def _prepare_pacemaker_remote_environment(
    env, node_host, allow_incomplete_distribution, allow_fails
):
    if not env.is_cib_live:
        env.report_processor.process(
            reports.actions_skipped_when_no_live_environment([
                "pacemaker authkey distribution",
                "start pacemaker_remote on '{0}'".format(node_host),
                "enable pacemaker_remote on '{0}'".format(node_host),
            ])
        )
        return

    candidate_node = NodeAddresses(node_host)
    _ensure_can_add_node_to_remote_cluster(env, candidate_node)
    _share_authkey(env, candidate_node, allow_incomplete_distribution)
    _start_and_enable_pacemaker_remote(env, [candidate_node], allow_fails)

def _ensure_resource_running(env, resource_id):
    env.report_processor.process(
        state.ensure_resource_running(env.get_cluster_state(), resource_id)
    )

def node_add_remote(
    env, host, node_name, operations, meta_attributes, instance_attributes,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    wait=False,
):
    env.ensure_wait_satisfiable(wait)

    report_list = remote_node.validate_host_not_ambiguous(
        instance_attributes,
        host,
    )
    enriched_instance_attributes = remote_node.prepare_instance_atributes(
        instance_attributes, host
    )

    cib = env.get_cib()

    report_list.extend(remote_node.validate_parts(
        env.nodes.all,
        node_name,
        enriched_instance_attributes
    ))

    try:
        remote_resource_element = remote_node.create(
            env.report_processor,
            env.cmd_runner(),
            get_resources(cib),
            node_name,
            operations,
            meta_attributes,
            enriched_instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
    except LibraryError as e:
        report_list.extend(e.args)

    env.report_processor.process_list(report_list)

    _prepare_pacemaker_remote_environment(
        env,
        host,
        allow_incomplete_distribution,
        allow_pacemaker_remote_service_fail,
    )
    env.push_cib(cib, wait)
    if wait:
        _ensure_resource_running(env, remote_resource_element.attrib["id"])

def node_add_guest(
    env, resource_id, options,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False, wait=False,
):
    env.ensure_wait_satisfiable(wait)

    cib = env.get_cib()
    report_list = guest_node.validate_parts(
        cib,
        env.nodes.all,
        resource_id,
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

    guest_node.set_as_guest(resource_element, options)

    _prepare_pacemaker_remote_environment(
        env,
        guest_node.get_host_from_options(options),
        allow_incomplete_distribution,
        allow_pacemaker_remote_service_fail,
    )
    env.push_cib(cib, wait)
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

def _remove_pcmk_remote(
    nodes, resource_element_list, get_host, remove_resource
):
    node_addresses_set = set()
    for resource_element in resource_element_list:
        for node in nodes:
            if get_host(resource_element) == node.ring0:
                node_addresses_set.add(node)
        remove_resource(resource_element)

    return sorted(node_addresses_set, key=lambda node: node.ring0)

def _destroy_pcmk_remote_env(env, node_addresses_list, allow_fails):
    if not env.is_cib_live:
        formated_node_host_list = ", ".join([
            "'{0}'".format(node_addresses.ring0)
            for node_addresses in node_addresses_list
        ])
        env.report_processor.process(
            reports.actions_skipped_when_no_live_environment([
                "pacemaker_remote authkey remove",
                "stop pacemaker_remote on {0}".format(formated_node_host_list),
                "disable pacemaker_remote on {0}".format(
                    formated_node_host_list
                ),
            ])
        )
        return

    actions = node_communication_format.create_pcmk_remote_actions([
        "stop",
        "disable",
    ])
    actions["pacemaker_remote authkey remove"] = {
        "type": "remove_pcmk_remote_authkey"
    }

    def is_success(key, response):
        if key == "pacemaker_remote authkey remove":
            return response.code in ["deleted", "not_found"]
        return response.code == "success"

    nodes_task.run_actions_on_multiple_nodes(
        env.node_communicator(),
        env.report_processor,
        actions,
        is_success,
        node_addresses_list,
        allow_fails,
    )

def node_remove_remote(
    env, node_identifier, remove_resource,
    allow_remove_multiple_nodes=False,
    allow_pacemaker_remote_service_fail=False
):

    resource_element_list = _find_resources_to_remove(
        env.get_cib(),
        env.report_processor,
        "remote",
        node_identifier,
        allow_remove_multiple_nodes,
        remote_node.find_node_resources,
    )
    node_addresses_list = _remove_pcmk_remote(
        env.nodes.remote,
        resource_element_list,
        remote_node.get_host,
        lambda resource_element: remove_resource(
            resource_element.attrib["id"],
            is_remove_remote_context=True,
        )
    )
    _destroy_pcmk_remote_env(
        env,
        node_addresses_list,
        allow_pacemaker_remote_service_fail
    )

def node_remove_guest(
    env, node_identifier,
    allow_remove_multiple_nodes=False,
    allow_pacemaker_remote_service_fail=False,
    wait=False,
):
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

    node_addresses_list =  _remove_pcmk_remote(
        env.nodes.guest,
        resource_element_list,
        guest_node.get_host,
        guest_node.unset_guest,
    )
    env.push_cib(cib, wait)
    for node_addresses in node_addresses_list:
        remove_node(env.cmd_runner(), node_addresses.name)

    _destroy_pcmk_remote_env(
        env,
        node_addresses_list,
        allow_pacemaker_remote_service_fail
    )

def node_clear(env, node_name):
    remove_node(env.cmd_runner(), node_name)
