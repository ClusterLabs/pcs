from pcs import usage
from pcs.cli.common.routing import create_router
from pcs.cli.tag import command as tag

tag_cmd = create_router(
    {
        "config": tag.tag_config,
        "create": tag.tag_create,
        "delete": tag.tag_remove,
        "help": lambda lib, argv, modifiers: usage.tag(argv),
        "list": tag.tag_config,
        "remove": tag.tag_remove,
    },
    ["tag"],
    default_cmd="config",
)
