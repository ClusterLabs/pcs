from functools import partial
from typing import Any

from pcs import (
    node,
    usage,
)
from pcs.cli.common.parse_args import Argv, InputModifiers
from pcs.cli.common.routing import create_router
from pcs.cli.node import command as node_command


def _node_attribute_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    if len(argv) > 1:
        # set command
        node.node_attribute_cmd(lib, argv, modifiers)
    else:
        # config command
        node_command.node_attribute_output_cmd(lib, argv, modifiers)


def _node_utilization_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    if len(argv) > 1:
        # set command
        node.node_utilization_cmd(lib, argv, modifiers)
    else:
        # config command
        node_command.node_utilization_output_cmd(lib, argv, modifiers)


node_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.node(argv)),
        "maintenance": partial(node.node_maintenance_cmd, enable=True),
        "unmaintenance": partial(node.node_maintenance_cmd, enable=False),
        "standby": partial(node.node_standby_cmd, enable=True),
        "unstandby": partial(node.node_standby_cmd, enable=False),
        "attribute": _node_attribute_cmd,
        "utilization": _node_utilization_cmd,
        # pcs-to-pcsd use only
        "pacemaker-status": node.node_pacemaker_status,
    },
    ["node"],
)
