from pcs import (
    settings,
    usage,
)
from pcs.cli.booth import command
from pcs.cli.common.routing import create_router
from pcs.resource import resource_remove

mapping = {
    "help": lambda lib, argv, modifiers: print(usage.booth(argv)),
    "config": command.config_show,
    "setup": command.config_setup,
    "destroy": command.config_destroy,
    "ticket": create_router(
        {
            "help": lambda lib, argv, modifiers: print(usage.booth(["ticket"])),
            "add": command.config_ticket_add,
            "delete": command.config_ticket_remove,
            "remove": command.config_ticket_remove,
            "grant": command.ticket_grant,
            "revoke": command.ticket_revoke,
        },
        ["booth", "ticket"],
    ),
    "create": command.create_in_cluster,
    # ignoring mypy errors, these functions need to be fixed, they are passing
    # a function to pcs.lib
    "delete": command.get_remove_from_cluster(resource_remove),  # type:ignore
    "remove": command.get_remove_from_cluster(resource_remove),  # type:ignore
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
