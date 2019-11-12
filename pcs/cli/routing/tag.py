from pcs.cli.common.routing import create_router
from pcs.cli.tag import command as tag
from pcs import usage

tag_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.tag(argv),
        "create": tag.tag_create,
    },
    ["tag"],
    default_cmd="list"
)
