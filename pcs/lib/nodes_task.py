from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.external import (
    NodeCommunicationException,
    node_communicator_exception_to_report_item,
)
from pcs.lib.corosync import live as corosync_live


def distribute_corosync_conf(
    node_communicator, reporter, node_addr_list, config_text
):
    """
    Send corosync.conf to several cluster nodes and reload corosync config
    node_addr_list nodes to send config to (NodeAddressesList instance)
    config_text text of corosync.conf
    """
    reporter.process(reports.corosync_config_distribution_started())
    report_items = []
    # TODO use parallel communication
    for node in node_addr_list:
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
                node_communicator_exception_to_report_item(e)
            )
            report_items.append(
                reports.corosync_config_distribution_node_error(node.label)
            )
    if report_items:
        raise LibraryError(*report_items)

def check_corosync_offline_on_nodes(
    node_communicator, reporter, node_addr_list
):
    reporter.process(reports.corosync_not_running_check_started())
    report_items = []
    # TODO use parallel communication
    for node in node_addr_list:
        try:
            status = node_communicator.call_node(node, "remote/status", "")
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
                node_communicator_exception_to_report_item(e)
            )
            report_items.append(
                reports.corosync_not_running_check_node_error(node.label)
            )
        except (ValueError, LookupError):
            report_items.append(
                reports.corosync_not_running_check_node_error(node.label)
            )
    if report_items:
        raise LibraryError(*report_items)
