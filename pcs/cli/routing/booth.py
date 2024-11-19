from pcs import (
    settings,
    usage,
)
from pcs.cli.booth import command
from pcs.cli.common.routing import create_router

mapping = {
    "help": lambda lib, argv, modifiers: print(usage.booth(argv)),
    "config": command.config_show,
    "setup": command.config_setup,
    "destroy": command.config_destroy,
    "ticket": create_router(
        {
            "help": lambda lib, argv, modifiers: print(usage.booth(["ticket"])),
            "add": command.config_ticket_add,
            "cleanup": command.ticket_cleanup,
            "delete": command.config_ticket_remove,
            "grant": command.ticket_grant,
            "remove": command.config_ticket_remove,
            "revoke": command.ticket_revoke,
        },
        ["booth", "ticket"],
    ),
    "create": command.create_in_cluster,
    "delete": command.remove_from_cluster,
    "remove": command.remove_from_cluster,
    "restart": command.restart,
    "sync": command.sync,
    "pull": command.pull,
    "enable": command.enable,
    "disable": command.disable,
    "start": command.start,
    "stop": command.stop,
    "status": command.status,
}

if settings.booth_enable_authfile_set_enabled:
    mapping["enable-authfile"] = command.enable_authfile

if settings.booth_enable_authfile_unset_enabled:
    mapping["clean-enable-authfile"] = command.enable_authfile_clean

booth_cmd = create_router(mapping, ["booth"])
