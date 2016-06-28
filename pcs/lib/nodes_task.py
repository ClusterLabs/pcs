from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json

from pcs.common import report_codes
from pcs.common.tools import run_parallel as tools_run_parallel
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity
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
