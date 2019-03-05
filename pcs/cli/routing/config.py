from pcs import (
    config,
    usage,
)
from pcs.cli.common.routing import create_router


config_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.config(argv),
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
            default_cmd="list"
        ),
        "import-cman": config.config_import_cman,
        "export": create_router(
            {
                "pcs-commands": config.config_export_pcs_commands,
                "pcs-commands-verbose": lambda lib, argv, modifiers:
                    config.config_export_pcs_commands(
                        lib, argv, modifiers, verbose=True
                    )
            },
            ["config", "export"]
        )
    },
    ["config"],
    default_cmd="show",
)
