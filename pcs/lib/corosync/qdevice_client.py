from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs import settings
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
    output, retval = runner.run(cmd)
    if retval != 0:
        raise LibraryError(
            reports.corosync_quorum_get_status_error(output)
        )
    return output

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
