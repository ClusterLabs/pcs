from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs import settings
from pcs.common.tools import join_multilines
from pcs.lib import reports
from pcs.lib.errors import LibraryError


def get_status_text(runner, verbose=False):
    """
    Get quorum device client runtime status in plain text
    bool verbose get more detailed output
    """
    cmd = [
        os.path.join(settings.corosync_binaries, "corosync-qdevice-tool"),
        "-s"
    ]
    if verbose:
        cmd.append("-v")
    stdout, stderr, retval = runner.run(cmd)
    if retval != 0:
        raise LibraryError(
            reports.corosync_quorum_get_status_error(
                join_multilines([stderr, stdout])
            )
        )
    return stdout

def remote_client_enable(reporter, node_communicator, node):
    """
    enable qdevice client service (corosync-qdevice) on a remote node
    """
    response = node_communicator.call_node(
        node,
        "remote/qdevice_client_enable",
        None
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
    """
    disable qdevice client service (corosync-qdevice) on a remote node
    """
    node_communicator.call_node(node, "remote/qdevice_client_disable", None)
    reporter.process(
        reports.service_disable_success("corosync-qdevice", node.label)
    )

def remote_client_start(reporter, node_communicator, node):
    """
    start qdevice client service (corosync-qdevice) on a remote node
    """
    response = node_communicator.call_node(
        node,
        "remote/qdevice_client_start",
        None
    )
    if response == "corosync is not running, skipping":
        reporter.process(
            reports.service_start_skipped(
                "corosync-qdevice",
                "corosync is not running",
                node.label
            )
        )
    else:
        reporter.process(
            reports.service_start_success("corosync-qdevice", node.label)
        )

def remote_client_stop(reporter, node_communicator, node):
    """
    stop qdevice client service (corosync-qdevice) on a remote node
    """
    node_communicator.call_node(node, "remote/qdevice_client_stop", None)
    reporter.process(
        reports.service_stop_success("corosync-qdevice", node.label)
    )
