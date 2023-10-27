import pcs.cli.constraint_colocation.command as colocation_command
from pcs import (
    constraint,
    usage,
)
from pcs.cli.common.routing import create_router
from pcs.cli.constraint import command as constraint_command
from pcs.cli.constraint.rule import command as rule_command
from pcs.cli.constraint_ticket import command as ticket_command

constraint_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.constraint(argv)),
        "location": constraint.constraint_location_cmd,
        "order": constraint.constraint_order_cmd,
        "ticket": create_router(
            {
                "set": ticket_command.create_with_set,
                "add": ticket_command.add,
                "delete": ticket_command.remove,
                "remove": ticket_command.remove,
                # TODO remove, deprecated command
                # replaced with 'config'
                "show": ticket_command.show,
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
                # TODO remove, deprecated command
                # replaced with 'config'
                "show": colocation_command.show,
                "config": colocation_command.config_cmd,
            },
            ["constraint", "colocation"],
            default_cmd="config",
        ),
        "remove": constraint_command.remove,
        "delete": constraint_command.remove,
        # TODO remove, deprecated command
        # replaced with 'config'
        "show": constraint.constraint_show,
        # TODO remove, deprecated command
        # replaced with 'config'
        "list": constraint.constraint_show,
        "config": constraint.config_cmd,
        "ref": constraint.ref,
        "rule": create_router(
            {
                "add": constraint.constraint_rule_add,
                "remove": rule_command.remove,
                "delete": rule_command.remove,
            },
            ["constraint", "rule"],
        ),
    },
    ["constraint"],
    default_cmd="config",
)
