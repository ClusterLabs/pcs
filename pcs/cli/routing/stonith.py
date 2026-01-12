import pcs.cli.stonith.command as stonith_cli
import pcs.cli.stonith.levels.command as levels_cli
from pcs import (
    resource,
    stonith,
    usage,
)
from pcs.cli.cib.element import command as cib_element_cmd
from pcs.cli.common.routing import create_router

from .resource_stonith_common import (
    resource_defaults_cmd,
    resource_op_defaults_cmd,
)

stonith_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.stonith(argv)),
        "list": stonith.stonith_list_available,
        "describe": stonith.stonith_list_options,
        "description": cib_element_cmd.description,
        "config": stonith_cli.config,
        "create": stonith.stonith_create,
        "update": stonith.update_cmd,
        "update-scsi-devices": stonith.stonith_update_scsi_devices,
        "delete": stonith.delete_cmd,
        "remove": stonith.delete_cmd,
        "status": stonith.stonith_status_cmd,
        "meta": stonith_cli.meta,
        "op": create_router(
            {
                "defaults": resource_op_defaults_cmd(
                    ["resource", "op", "defaults"]
                ),
                "add": stonith.op_add_cmd,
                "remove": stonith.op_delete_cmd,
                "delete": stonith.op_delete_cmd,
            },
            ["stonith", "op"],
        ),
        "defaults": resource_defaults_cmd(["resource", "defaults"]),
        "level": create_router(
            {
                "add": stonith.stonith_level_add_cmd,
                "clear": stonith.stonith_level_clear_cmd,
                "config": levels_cli.config,
                "remove": stonith.stonith_level_remove_cmd,
                "delete": stonith.stonith_level_remove_cmd,
                "verify": stonith.stonith_level_verify_cmd,
            },
            ["stonith", "level"],
            default_cmd="config",
        ),
        "failcount": create_router(
            {
                "show": resource.resource_failcount_show,
            },
            ["stonith", "failcount"],
            default_cmd="show",
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
        "enable": stonith.enable_cmd,
        "disable": stonith.disable_cmd,
        "history": create_router(
            {
                "show": stonith.stonith_history_show_cmd,
                "cleanup": stonith.stonith_history_cleanup_cmd,
                "update": stonith.stonith_history_update_cmd,
            },
            ["stonith", "history"],
            default_cmd="show",
        ),
    },
    ["stonith"],
    default_cmd="status",
)
