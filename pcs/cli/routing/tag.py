from pcs import usage
from pcs.cli.common.errors import raise_command_replaced
from pcs.cli.common.routing import create_router
from pcs.cli.tag import command as tag

tag_cmd = create_router(
    {
        "config": tag.tag_config,
        "create": tag.tag_create,
        "delete": tag.tag_remove,
        "help": lambda lib, argv, modifiers: print(usage.tag(argv)),
        "list": lambda lib, argv, modifiers: raise_command_replaced(
            ["pcs tag config"], pcs_version="0.12"
        ),
        "remove": tag.tag_remove,
        "update": tag.tag_update,
    },
    ["tag"],
    default_cmd="config",
)
