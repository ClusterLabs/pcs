from typing import Any

import pcs.cli.constraint_colocation.command as colocation_command
from pcs import (
    constraint,
    usage,
)
from pcs.cli.common.errors import (
    CmdLineInputError,
    raise_command_removed,
    raise_command_replaced,
)
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.common.routing import create_router
from pcs.cli.constraint import command as constraint_command
from pcs.cli.constraint.location import command as location_command
from pcs.cli.constraint_ticket import command as ticket_command
from pcs.utils import exit_on_cmdline_input_error


def constraint_location_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    if not argv:
        sub_cmd = "config"
    else:
        sub_cmd = argv.pop(0)

    try:
        if sub_cmd == "add":
            constraint.location_add(lib, argv, modifiers)
        elif sub_cmd in ["remove", "delete"]:
            location_command.remove(lib, argv, modifiers)
        elif sub_cmd == "show":
            raise_command_replaced(
                ["pcs constraint location config"], pcs_version="0.12"
            )
        elif sub_cmd == "config":
            constraint.location_config_cmd(lib, argv, modifiers)
        elif len(argv) >= 2:
            if argv[0] == "rule":
                location_command.create_with_rule(
                    lib, [sub_cmd] + argv, modifiers
                )
            else:
                constraint.location_prefer(lib, [sub_cmd] + argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        exit_on_cmdline_input_error(e, "constraint", ["location", sub_cmd])


constraint_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.constraint(argv)),
        "location": constraint_location_cmd,
        "order": constraint.constraint_order_cmd,
        "ticket": create_router(
            {
                "set": ticket_command.create_with_set,
                "add": ticket_command.add,
                "delete": ticket_command.remove,
                "remove": ticket_command.remove,
                "show": lambda lib, argv, modifiers: raise_command_replaced(
                    ["pcs constraint ticket config"], pcs_version="0.12"
                ),
                "config": ticket_command.config_cmd,
            },
            ["constraint", "ticket"],
            default_cmd="config",
        ),
        "colocation": create_router(
            {
                "add": constraint.colocation_add,
                "remove": colocation_command.remove,
                "delete": colocation_command.remove,
                "set": colocation_command.create_with_set,
                "show": lambda lib, argv, modifiers: raise_command_replaced(
                    ["pcs constraint colocation config"], pcs_version="0.12"
                ),
                "config": colocation_command.config_cmd,
            },
            ["constraint", "colocation"],
            default_cmd="config",
        ),
        "remove": constraint_command.remove,
        "delete": constraint_command.remove,
        "show": lambda lib, argv, modifiers: raise_command_replaced(
            ["pcs constraint config"], pcs_version="0.12"
        ),
        "list": lambda lib, argv, modifiers: raise_command_replaced(
            ["pcs constraint config"], pcs_version="0.12"
        ),
        "config": constraint.config_cmd,
        "ref": constraint.ref,
        "rule": lambda lib, argv, modifiers: raise_command_removed(
            pcs_version="0.12"
        ),
    },
    ["constraint"],
    default_cmd="config",
)
