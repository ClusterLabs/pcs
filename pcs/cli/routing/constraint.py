from pcs import (
    constraint,
    usage,
)
from pcs.cli.common.routing import create_router
import pcs.cli.constraint_colocation.command as colocation_command
from pcs.cli.constraint_ticket import command as ticket_command


constraint_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.constraint(argv),
        "location": constraint.constraint_location_cmd,
        "order": constraint.constraint_order_cmd,
        "ticket": create_router(
            {
                "set": ticket_command.create_with_set,
                "add": ticket_command.add,
                "delete": ticket_command.remove,
                "remove": ticket_command.remove,
                "show": ticket_command.show,
            },
            ["constraint", "ticket"],
            default_cmd="show"
        ),
        "colocation": create_router(
            {
                "add": constraint.colocation_add,
                "remove": constraint.colocation_rm,
                "delete": constraint.colocation_rm,
                "set": colocation_command.create_with_set,
                "show": colocation_command.show,
            },
            ["constraint", "colocation"],
            default_cmd="show"
        ),
        "remove": constraint.constraint_rm,
        "delete": constraint.constraint_rm,
        "show": constraint.constraint_show,
        "list": constraint.constraint_show,
        "ref": constraint.constraint_ref,
        "rule": constraint.constraint_rule,
    },
    ["constraint"],
    default_cmd="list"
)
