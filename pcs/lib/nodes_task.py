from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json

from pcs.common import report_codes
from pcs.common.tools import run_parallel as tools_run_parallel
from pcs.lib import reports, node_communication_format
from pcs.lib.errors import LibraryError, ReportItemSeverity, ReportListAnalyzer
from pcs.lib.external import (
    NodeCommunicator,
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
    parallel_nodes_communication_helper,
)
from pcs.lib.corosync import (
    live as corosync_live,
    qdevice_client,
)


def _call_for_json(
    node_communicator, node, request_path, report_items,
    data=None, request_timeout=None
):
    """
    Return python object parsed from a json call response.
    """
    try:
        return json.loads(node_communicator.call_node(
            node,
            request_path,
            data=None if data is None
                else NodeCommunicator.format_data_dict(data)
            ,
            request_timeout=request_timeout
        ))
    except NodeCommunicationException as e:
        report_items.append(
            node_communicator_exception_to_report_item(
                e,
                ReportItemSeverity.ERROR,
            )
        )
    except ValueError:
        #e.g. response is not in json format
        report_items.append(reports.invalid_response_format(node.label))


def distribute_corosync_conf(
    node_communicator, reporter, node_addr_list, config_text,
    skip_offline_nodes=False
):
    """
    Send corosync.conf to several cluster nodes
    node_addr_list nodes to send config to (NodeAddressesList instance)
    config_text text of corosync.conf
    skip_offline_nodes don't raise an error if a node communication error occurs
    """
    failure_severity = ReportItemSeverity.ERROR
    failure_forceable = report_codes.SKIP_OFFLINE_NODES
    if skip_offline_nodes:
        failure_severity = ReportItemSeverity.WARNING
        failure_forceable = None
    report_items = []

    def _parallel(node):
        try:
            corosync_live.set_remote_corosync_conf(
                node_communicator,
                node,
                config_text
            )
            reporter.process(
                reports.corosync_config_accepted_by_node(node.label)
            )
        except NodeCommunicationException as e:
            report_items.append(
                node_communicator_exception_to_report_item(
                    e,
                    failure_severity,
                    failure_forceable
                )
            )
            report_items.append(
                reports.corosync_config_distribution_node_error(
                    node.label,
                    failure_severity,
                    failure_forceable
                )
            )

    reporter.process(reports.corosync_config_distribution_started())
    tools_run_parallel(
        _parallel,
        [((node, ), {}) for node in node_addr_list]
    )
    reporter.process_list(report_items)

def check_corosync_offline_on_nodes(
    node_communicator, reporter, node_addr_list, skip_offline_nodes=False
):
    """
    Check corosync is not running on cluster nodes
    node_addr_list nodes to send config to (NodeAddressesList instance)
    skip_offline_nodes don't raise an error if a node communication error occurs
    """
    failure_severity = ReportItemSeverity.ERROR
    failure_forceable = report_codes.SKIP_OFFLINE_NODES
    if skip_offline_nodes:
        failure_severity = ReportItemSeverity.WARNING
        failure_forceable = None
    report_items = []

    def _parallel(node):
        try:
            status = node_communicator.call_node(node, "remote/status", None)
            if not json.loads(status)["corosync"]:
                reporter.process(
                    reports.corosync_not_running_on_node_ok(node.label)
                )
            else:
                report_items.append(
                    reports.corosync_running_on_node_fail(node.label)
                )
        except NodeCommunicationException as e:
            report_items.append(
                node_communicator_exception_to_report_item(
                    e,
                    failure_severity,
                    failure_forceable
                )
            )
            report_items.append(
                reports.corosync_not_running_check_node_error(
                    node.label,
                    failure_severity,
                    failure_forceable
                )
            )
        except (ValueError, LookupError):
            report_items.append(
                reports.corosync_not_running_check_node_error(
                    node.label,
                    failure_severity,
                    failure_forceable
                )
            )

    reporter.process(reports.corosync_not_running_check_started())
    tools_run_parallel(
        _parallel,
        [((node, ), {}) for node in node_addr_list]
    )
    reporter.process_list(report_items)

def qdevice_reload_on_nodes(
    node_communicator, reporter, node_addr_list, skip_offline_nodes=False
):
    """
    Reload corosync-qdevice configuration on cluster nodes
    NodeAddressesList node_addr_list nodes to reload config on
    bool skip_offline_nodes don't raise an error on node communication errors
    """
    reporter.process(reports.qdevice_client_reload_started())
    parallel_params = [
        [(reporter, node_communicator, node), {}]
        for node in node_addr_list
    ]
    # catch an exception so we try to start qdevice on nodes where we stopped it
    report_items = []
    try:
        parallel_nodes_communication_helper(
            qdevice_client.remote_client_stop,
            parallel_params,
            reporter,
            skip_offline_nodes
        )
    except LibraryError as e:
        report_items.extend(e.args)
    try:
        parallel_nodes_communication_helper(
            qdevice_client.remote_client_start,
            parallel_params,
            reporter,
            skip_offline_nodes
        )
    except LibraryError as e:
        report_items.extend(e.args)
    reporter.process_list(report_items)

def node_check_auth(communicator, node):
    """
    Check authentication and online status of 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    communicator.call_node(
        node,
        "remote/check_auth",
        NodeCommunicator.format_data_dict({"check_auth_only": 1})
    )

def availability_checker_node(availability_info, report_items, node_label):
    if availability_info["node_available"]:
        return

    if not availability_info.get("pacemaker_remote", False):
        report_items.append(reports.cannot_add_node_is_in_cluster(node_label))
        return

    report_items.append(reports.cannot_add_node_is_running_service(
        node_label,
        "pacemaker_remote"
    ))

def availability_checker_remote_node(
    availability_info, report_items, node_label
):
    if (
        availability_info["node_available"]
        and
        availability_info.get("pacemaker_running", False)
    ):
        report_items.append(reports.cannot_add_node_is_running_service(
            node_label,
            "pacemaker"
        ))
        return

    if (
        not availability_info["node_available"]
        and
        not availability_info.get("pacemaker_remote", False)
    ):
        report_items.append(reports.cannot_add_node_is_in_cluster(node_label))

def check_can_add_node_to_cluster(
    node_communicator, node, report_items,
    check_response=availability_checker_node
):
    """
    Analyze result of node_available check if it is possible use the node as
    cluster node.

    NodeCommunicator node_communicator is an object for making the http request
    NodeAddresses node specifies the destination url
    list report_items is place where report items should be collected
    """
    safe_report_items = []
    availability_info = _call_for_json(
        node_communicator,
        node,
        "remote/node_available",
        safe_report_items
    )
    report_items.extend(safe_report_items)

    if ReportListAnalyzer(safe_report_items).error_list:
        return

    is_in_expected_format = (
        isinstance(availability_info, dict)
        and
        #node_available is a mandatory field
        availability_info.has_key("node_available")
    )

    if not is_in_expected_format:
        report_items.append(reports.invalid_response_format(node.label))
        return

    check_response(availability_info, report_items, node.label)

def run_action_on_node(node_communicator, report_processor, node, actions):
    """
    NodeCommunicator node_communicator is an object for making the http request
    NodeAddresses node specifies the destination url
    dict actions has key that identifies the action and value is a dict
        with a data that are specific per action type. Mandatory keys there are:
        * type - is type of file like "booth_autfile" or "pcmk_remote_authkey"
          For type == 'service_command' are mandatory
            * service - specify the service (eg. pacemaker_remote)
            * command - specify the command should be applied on service
                (eg. enable or start)
    """
    report_items = []

    report_processor.process(reports.actions_on_nodes_started(
        actions.keys(),
        [node.label]
    ))

    action_results = _call_for_json(
        node_communicator,
        node,
        "remote/run_action",
        report_items,
        [("data_json", json.dumps(actions))]
    )

    #can raise
    report_processor.process_list(report_items)

    return node_communication_format.response_to_result(
        action_results,
        "actions",
        actions.keys(),
        node.label,
    )

def put_files_to_node(
    node_communicator, report_processor, node, file_definitions
):
    """
    NodeCommunicator node_communicator is an object for making the http request
    NodeAddresses node specifies the destination url
    dict file_definitions has key that identifies the file and value is a dict
        with a data that are specific per file type. Mandatory keys there are:
        * type - is type of file like "booth_autfile" or "pcmk_remote_authkey"
        * data - it contains content of file in file specific format (e.g.
            binary is encoded by base64)
        Common optional key is "rewrite_existing" (True/False) that specifies
        the behaviour when file already exists.
    """
    report_items = []
    file_results = _call_for_json(
        node_communicator,
        node,
        "remote/put_file",
        report_items,
        [("data_json", json.dumps(file_definitions))]
    )

    #can raise
    report_processor.process_list(report_items)

    return node_communication_format.response_to_result(
        file_results,
        "files",
        file_definitions.keys(),
        node.label,
    )

def distribute_files(
    node_communicator, report_processor, file_definitions, node_addresses_list,
    allow_incomplete_distribution=False
):
    """
    Put files specified in file_definitions to nodes specified in
    node_addresses_list.

    NodeCommunicator node_communicator is an object for making the http request
    NodeAddresses node specifies the destination url
    dict file_definitions has key that identifies the file and value is a dict
        with a data that are specific per file type. Mandatory keys there are:
        * type - is type of file like "booth_autfile" or "pcmk_remote_authkey"
        * data - it contains content of file in file specific format (e.g.
            binary is encoded by base64)
        Common optional key is "rewrite_existing" (True/False) that specifies
        the behaviour when file already exists.
    bool allow_incomplete_distribution keep success even if some node(s) are
        unavailable
    """
    response_map = {}
    def put_authkey_to_node(node_addresses):
        result = put_files_to_node(
            node_communicator,
            report_processor,
            node_addresses,
            file_definitions=file_definitions
        )
        response_map[node_addresses] = result

    report_processor.process(reports.files_distribution_started(
        file_definitions.keys(),
        [node.label for node in node_addresses_list]
    ))

    parallel_nodes_communication_helper(
        put_authkey_to_node,
        [([node_addresses], {}) for node_addresses in node_addresses_list],
        report_processor,
        allow_incomplete_distribution,
    )

    return response_map
