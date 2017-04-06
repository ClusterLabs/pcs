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
from pcs.lib.resource_agent import find_valid_resource_agent_by_name
from pcs.lib.cib import resource
from pcs.lib.cib.tools import get_resources
from pcs.lib.errors import LibraryError


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

    authkey_key = "pacemaker_remote authkey"

    #TODO do only when authkey is live
    response_map = nodes_task.distribute_files(
        env.node_communicator(),
        env.report_processor,
        {authkey_key: node_communication_format.pcmk_authkey_format(
            authkey_content
        )},
        node_addresses_list,
        allow_incomplete_distribution
    )

    success, errors = node_communication_format.responses_to_report_infos(
        response_map,
        is_success=(
            lambda key, response: response.code in ["written", "rewritten"]
        ),
        get_node_label=lambda node: node.label
    )

    if success:
        env.report_processor.process(reports.files_distribution_success(success))

    if errors:
        env.report_processor.process(
            reports.get_problem_creator(
                report_codes.SKIP_FILE_DISTRIBUTION_ERRORS,
                allow_incomplete_distribution
            )(reports.files_distribution_error, errors)
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

def node_add_remote(
    env, node_host, node_name, operations, meta_attributes, instance_attributes,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    wait=False,
):
    cib = env.get_cib()
    if instance_attributes.get("server", node_host) != node_host:
        raise LibraryError(reports.ambiguous_host_specification(
            [node_host, instance_attributes["server"]]
        ))

    instance_attributes["server"] = node_host
    resource.primitive.create(
        env.report_processor,
        get_resources(cib),
        node_name,
        find_valid_resource_agent_by_name(
            env.report_processor,
            env.cmd_runner(),
            "ocf:pacemaker:remote",
        ),
        operations,
        meta_attributes,
        instance_attributes,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
    )

    candidate_node = NodeAddresses(node_host)

    _ensure_can_add_node_to_remote_cluster(env, candidate_node)
    _share_authkey(env, candidate_node, allow_incomplete_distribution)
    _start_and_enable_pacemaker_remote(
        env,
        candidate_node,
        allow_pacemaker_remote_service_fail
    )

    env.push_cib(cib, wait)
