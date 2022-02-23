from pcs import (
    resource,
    stonith,
    usage,
)
from pcs.cli.common.routing import create_router

stonith_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.stonith(argv)),
        "list": stonith.stonith_list_available,
        "describe": stonith.stonith_list_options,
        "create": stonith.stonith_create,
        "update": resource.resource_update,
        "update-scsi-devices": stonith.stonith_update_scsi_devices,
        "delete": resource.resource_remove_cmd,
        "remove": resource.resource_remove_cmd,
        # TODO remove, deprecated command
        # replaced with 'stonith status' and 'stonith config'
        "show": stonith.stonith_show_cmd,
        "status": stonith.stonith_status_cmd,
        "config": stonith.stonith_config_cmd,
        "level": create_router(
            {
                "add": stonith.stonith_level_add_cmd,
                "clear": stonith.stonith_level_clear_cmd,
                "config": stonith.stonith_level_config_cmd,
                "remove": stonith.stonith_level_remove_cmd,
                "delete": stonith.stonith_level_remove_cmd,
                "verify": stonith.stonith_level_verify_cmd,
            },
            ["stonith", "level"],
            default_cmd="config",
        ),
        "fence": stonith.stonith_fence,
        "cleanup": resource.resource_cleanup,
        "refresh": resource.resource_refresh,
        "confirm": stonith.stonith_confirm,
        "sbd": create_router(
            {
                "enable": stonith.sbd_enable,
                "disable": stonith.sbd_disable,
                "status": stonith.sbd_status,
                "config": stonith.sbd_config,
                "device": create_router(
                    {
                        "setup": stonith.sbd_setup_block_device,
                        "message": stonith.sbd_message,
                    },
                    ["stonith", "sbd", "device"],
                ),
                "watchdog": create_router(
                    {
                        "list": stonith.sbd_watchdog_list,
                        "test": stonith.sbd_watchdog_test,
                        # internal use only
                        "list_json": stonith.sbd_watchdog_list_json,
                    },
                    ["stonith", "sbd", "watchdog"],
                ),
                # internal use only
                "local_config_in_json": stonith.local_sbd_config,
            },
            ["stonith", "sbd"],
        ),
        "enable": resource.resource_enable_cmd,
        "disable": resource.resource_disable_cmd,
        "history": create_router(
            {
                "show": stonith.stonith_history_show_cmd,
                "cleanup": stonith.stonith_history_cleanup_cmd,
                "update": stonith.stonith_history_update_cmd,
            },
            ["stonith", "history"],
            default_cmd="show",
        ),
        # internal use only
        "get_fence_agent_info": stonith.get_fence_agent_info,
    },
    ["stonith"],
    default_cmd="status",
)
