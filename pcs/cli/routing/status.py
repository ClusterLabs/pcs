from pcs import (
    status,
    usage,
)
from pcs.cli.booth.command import status as booth_status_cmd
from pcs.cli.common.routing import create_router
from pcs.cli.status import command as status_command
from pcs.pcsd import pcsd_status_cmd
from pcs.qdevice import qdevice_status_cmd
from pcs.quorum import quorum_status_cmd
from pcs.resource import resource_status

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
        "wait": status_command.wait_for_pcmk_idle,
    },
    ["status"],
    default_cmd="status",
)
