from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path

from pcs import settings
from pcs.lib import error_codes
from pcs.lib.errors import ReportItem, LibraryError
from pcs.lib.external import NodeCommunicator

def get_local_corosync_conf():
    """
    Read corosync.conf file from local machine
    """
    path = settings.corosync_conf_file
    try:
        return open(path).read()
    except IOError as e:
        raise LibraryError(ReportItem.error(
            error_codes.UNABLE_TO_READ_COROSYNC_CONFIG,
            "Unable to read {path}: {reason}",
            info={
                "path": path,
                "reason": e.strerror
            }
        ))

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
        raise LibraryError(ReportItem.error(
            error_codes.COROSYNC_CONFIG_RELOAD_ERROR,
            "Unable to reload corosync configuration: {reason}",
            info={"reason": output.rstrip()}
        ))

