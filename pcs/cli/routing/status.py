from pcs import (
    status,
    usage,
)
from pcs.cli.common.errors import raise_command_replaced
from pcs.cli.common.routing import create_router

from pcs.pcsd import pcsd_status_cmd
from pcs.qdevice import qdevice_status_cmd
from pcs.quorum import quorum_status_cmd
from pcs.resource import resource_status
from pcs.cli.booth.command import status as booth_status_cmd

status_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.status(argv)),
        "booth": booth_status_cmd,
        "corosync": status.corosync_status,
        "cluster": status.cluster_status,
        "nodes": status.nodes_status,
        "pcsd": pcsd_status_cmd,
        "qdevice": qdevice_status_cmd,
        "quorum": quorum_status_cmd,
        "resources": resource_status,
        "xml": status.xml_status,
        "status": status.full_status,
        # removed commands
        # These print error messages which point users to the changes section in
        # pcs manpage.
        # To be removed in the next significant version.
        "groups": lambda lib, argv, modifiers: raise_command_replaced(
            "pcs resource group list"
        ),
    },
    ["status"],
    default_cmd="status",
)
