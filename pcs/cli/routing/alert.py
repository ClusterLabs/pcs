from pcs import (
    alert,
    usage,
)
from pcs.cli.alert import command as alert_command
from pcs.cli.common.routing import create_router

alert_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.alert(argv)),
        "create": alert.alert_add,
        "update": alert.alert_update,
        "delete": alert.alert_remove,
        "remove": alert.alert_remove,
        "config": alert_command.alert_config,
        # TODO remove, deprecated command
        # replaced with 'config'
        "show": alert.print_alert_show,
        "recipient": create_router(
            {
                "help": lambda lib, argv, modifiers: print(
                    usage.alert(["recipient"])
                ),
                "add": alert.recipient_add,
                "update": alert.recipient_update,
                "delete": alert.recipient_remove,
                "remove": alert.recipient_remove,
            },
            ["alert", "recipient"],
        ),
        "get_all_alerts": alert.print_alerts_in_json,
    },
    ["alert"],
    default_cmd="config",
)
