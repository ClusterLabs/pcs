from typing import Any

from pcs import (
    status,
    usage,
)
from pcs.cli.booth.command import status as booth_status_cmd
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.common.routing import create_router
from pcs.cli.query import resource
from pcs.cli.status import command as status_command
from pcs.pcsd import pcsd_status_cmd
from pcs.qdevice import qdevice_status_cmd
from pcs.quorum import quorum_status_cmd
from pcs.resource import resource_status


def _query_resource_router(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    if not argv:
        raise CmdLineInputError()

    if len(argv) < 2:
        # show correct usage when resource_id is missing in the command
        argv.insert(0, "")

    # swap resource_id with next keyword in the command to be able to use router
    argv[0], argv[1] = argv[1], argv[0]

    create_router(
        {
            "exists": resource.exists,
            "is-in-bundle": resource.is_in_bundle,
            "is-in-clone": resource.is_in_clone,
            "is-in-group": resource.is_in_group,
            "is-state": resource.is_state,
            "is-stonith": resource.is_stonith,
            "is-type": resource.is_type,
            "get-type": resource.get_type,
            "get-members": resource.get_members,
            "get-nodes": resource.get_nodes,
            "get-index-in-group": resource.get_index_in_group,
        },
        ["status", "query", "resource", "<resource-id>"],
    )(lib, argv, modifiers)


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
        "query": create_router(
            {"resource": _query_resource_router}, ["status", "query"]
        ),
        "wait": status_command.wait_for_pcmk_idle,
    },
    ["status"],
    default_cmd="status",
)
