from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports


def remote_client_enable(reporter, node_communicator, node):
    response = node_communicator.call_node(
        node,
        "remote/qdevice_client_enable",
        ""
    )
    if response == "corosync is not enabled, skipping":
        reporter.process(
            reports.service_enable_skipped(
                "corosync-qdevice",
                "corosync is not enabled",
                node.label
            )
        )
    else:
        reporter.process(
            reports.service_enable_success("corosync-qdevice", node.label)
        )

def remote_client_disable(reporter, node_communicator, node):
    node_communicator.call_node(node, "remote/qdevice_client_disable", "")
    reporter.process(
        reports.service_disable_success("corosync-qdevice", node.label)
    )
