from pcs import (
    config,
    usage,
)
from pcs.cli.common.routing import create_router


config_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.config(argv)),
        "show": config.config_show,
        "backup": config.config_backup,
        "restore": config.config_restore,
        "checkpoint": create_router(
            {
                "list": config.config_checkpoint_list,
                "view": config.config_checkpoint_view,
                "restore": config.config_checkpoint_restore,
                "diff": config.config_checkpoint_diff,
            },
            ["config", "checkpoint"],
            default_cmd="list",
        ),
    },
    ["config"],
    default_cmd="show",
)
