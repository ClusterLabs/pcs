from pcs import usage
from pcs.cli.common.routing import create_router
from pcs.cli.tag import command as tag

tag_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.tag(argv),
        "create": tag.tag_create,
        "config": tag.tag_config,
        "list": tag.tag_config,
    },
    ["tag"],
    default_cmd="config"
)
