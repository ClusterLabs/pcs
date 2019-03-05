from functools import partial

from pcs import (
    node,
    usage,
)
from pcs.cli.common.routing import create_router


node_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.node(argv),
        "maintenance": partial(node.node_maintenance_cmd, enable=True),
        "unmaintenance": partial(node.node_maintenance_cmd, enable=False),
        "standby": partial(node.node_standby_cmd, enable=True),
        "unstandby": partial(node.node_standby_cmd, enable=False),
        "attribute": node.node_attribute_cmd,
        "utilization": node.node_utilization_cmd,
        # pcs-to-pcsd use only
        "pacemaker-status": node.node_pacemaker_status,
    },
    ["node"]
)
