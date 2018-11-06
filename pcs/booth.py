from pcs import usage
from pcs import utils
from pcs.cli.booth import command
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.routing import create_router
from pcs.resource import resource_remove, resource_restart


def booth_cmd(lib, argv, modifiers):
    try:
        create_router(
            {
                "help": lambda _lib, _argv, _modifiers: usage.booth(_argv),
                "config": command.config_show,
                "setup": command.config_setup,
                "destroy": command.config_destroy,
                "ticket": create_router(
                    {
                        "help": lambda _lib, _argv, _modifiers: usage.booth(
                            ["ticket"]
                        ),
                        "add": command.config_ticket_add,
                        "delete": command.config_ticket_remove,
                        "remove": command.config_ticket_remove,
                        "grant": command.ticket_grant,
                        "revoke": command.ticket_revoke,
                    },
                    ["booth", "ticket"]
                ),
                "create": command.create_in_cluster,
                "delete": command.get_remove_from_cluster(resource_remove),
                "remove": command.get_remove_from_cluster(resource_remove),
                "restart": command.get_restart(resource_restart),
                "sync": command.sync,
                "pull": command.pull,
                "enable": command.enable,
                "disable": command.disable,
                "start": command.start,
                "stop": command.stop,
                "status": command.status,
            },
            ["booth"]
        )(lib, argv, modifiers)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "booth", "")
