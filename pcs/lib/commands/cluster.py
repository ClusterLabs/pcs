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

def _start_and_enable_pacemaker_remote(
    env, candidate_node, allow_pacemaker_remote_service_fail=False
):
    actions = {
        "pacemaker_remote start": node_communication_format.service_cmd_format(
            "pacemaker_remote",
            "start"
        ),
        "pacemaker_remote enable": node_communication_format.service_cmd_format(
            "pacemaker_remote",
            "enable"
        ),
    }

    response = nodes_task.run_action_on_node(
        env.node_communicator(),
        env.report_processor,
        candidate_node,
        actions=actions,
    )

    success, errors = node_communication_format.responses_to_report_infos(
        {candidate_node: response},
        is_success=lambda key, response: response.code == "success",
        get_node_label=lambda node: node.label
    )

    if success:
        env.report_processor.process(reports.actions_on_nodes_success(success))

    if errors:
        env.report_processor.process(
            reports.get_problem_creator(
                report_codes.SKIP_ACTION_ON_NODES_ERRORS,
                allow_pacemaker_remote_service_fail
            )(reports.actions_on_nodes_error, errors)
        )

def _prepare_pacemaker_remote_environment(
    env, node_host, allow_incomplete_distribution,
    allow_pacemaker_remote_service_fail
):
    if env.is_cib_live:
        candidate_node = NodeAddresses(node_host)
        _ensure_can_add_node_to_remote_cluster(env, candidate_node)
        _share_authkey(env, candidate_node, allow_incomplete_distribution)
        _start_and_enable_pacemaker_remote(
            env,
            candidate_node,
            allow_pacemaker_remote_service_fail
        )
    else:
        env.report_processor.process(
            reports.actions_skipped_when_no_live_environment([
                "pacemaker authkey distribution",
                "start pacemaker_remote on '{0}'".format(node_host),
                "enable pacemaker_remote on '{0}'".format(node_host),
            ])
        )

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
    wait=False,
):
    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()

    report_list = remote_node.validate_host_not_ambiguous(
        host,
        instance_attributes
    )
    try:
        remote_resource_element = remote_node.create(
            env.report_processor,
            env.cmd_runner(),
            get_resources(cib),
            node_name,
            operations,
            meta_attributes,
            remote_node.prepare_instance_atributes(instance_attributes, host),
            allow_invalid_operation,
            allow_invalid_instance_attributes,
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

    report_list = guest_node.validate_options(options)
    try:
        resource_element = find_element_by_tag_and_id(
            primitive.TAG,
            get_resources(cib),
            resource_id
        )
    except LibraryError as e:
        raise LibraryError(*(list(e.args) + report_list))

    env.report_processor.process_list(
        report_list
        +
        guest_node.validate_is_not_guest(resource_element)
    )

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
