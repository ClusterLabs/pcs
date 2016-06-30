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
from pcs.lib.external import NodeCommunicator

def get_local_corosync_conf():
    """
    Read corosync.conf file from local machine
    """
    path = settings.corosync_conf_file
    try:
        return open(path).read()
    except IOError as e:
        raise LibraryError(reports.corosync_config_read_error(path, e.strerror))

def set_remote_corosync_conf(node_communicator, node_addr, config_text):
    """
    Send corosync.conf to a node
    node_addr instance of NodeAddresses
    config_text corosync.conf text
    """
    dummy_response = node_communicator.call_node(
        node_addr,
        "remote/set_corosync_conf",
        NodeCommunicator.format_data_dict({'corosync_conf': config_text})
    )

def reload_config(runner):
    """
    Ask corosync to reload its configuration
    """
    output, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync-cfgtool"),
        "-R"
    ])
    if retval != 0 or "invalid option" in output:
        raise LibraryError(
            reports.corosync_config_reload_error(output.rstrip())
        )

def get_quorum_status_text(runner):
    """
    Get runtime quorum status from the local node
    """
    output, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync-quorumtool"),
        "-p"
    ])
    # retval is 0 on success if node is not in partition with quorum
    # retval is 1 on error OR on success if node has quorum
    if retval not in [0, 1]:
        raise LibraryError(
            reports.corosync_quorum_get_status_error(output)
        )
    return output

def set_expected_votes(runner, votes):
    """
    set expected votes in live cluster to specified value
    """
    output, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync-quorumtool"),
        # format votes to handle the case where they are int
        "-e", "{0}".format(votes)
    ])
    if retval != 0:
        raise LibraryError(
            reports.corosync_quorum_set_expected_votes_error(output)
        )
    return output
