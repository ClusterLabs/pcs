from pcs import usage
from pcs.cli.common.routing import create_router
from pcs.cli.tag import command as tag

tag_cmd = create_router(
    {
        "config": tag.tag_config,
        "create": tag.tag_create,
        "delete": tag.tag_remove,
        "help": lambda lib, argv, modifiers: usage.tag(argv),
        # TODO remove, deprecated command
        # replaced with 'config'
        "list": tag.tag_list_cmd,
        "remove": tag.tag_remove,
        "update": tag.tag_update,
    },
    ["tag"],
    default_cmd="config",
)
