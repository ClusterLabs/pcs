from functools import partial

import pcs.cli.resource.command as resource_cli
from pcs import (
    resource,
    usage,
)
from pcs.cli.common.routing import create_router
from pcs.cli.resource.relations import show_resource_relations_cmd

from .resource_stonith_common import (
    resource_defaults_cmd,
    resource_op_defaults_cmd,
)

resource_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.resource(argv)),
        "list": resource.resource_list_available,
        "describe": resource.resource_list_options,
        "create": resource.resource_create,
        "move": resource.resource_move,
        "move-with-constraint": resource.resource_move_with_constraint,
        "ban": resource.resource_ban,
        "clear": resource.resource_unmove_unban,
        "standards": resource.resource_standards,
        "providers": resource.resource_providers,
        "agents": resource.resource_agents,
        "update": resource.update_cmd,
        "meta": resource_cli.meta,
        "delete": resource.resource_remove_cmd,
        "remove": resource.resource_remove_cmd,
        # TODO remove, deprecated command
        # replaced with 'resource status' and 'resource config'
        "show": resource.resource_show,
        "status": resource.resource_status,
        "config": resource_cli.config,
        "group": create_router(
            {
                "add": resource.resource_group_add_cmd,
                "list": resource.resource_group_list,
                "remove": resource.resource_group_rm_cmd,
                "delete": resource.resource_group_rm_cmd,
            },
            ["resource", "group"],
        ),
        "ungroup": resource.resource_group_rm_cmd,
        "clone": resource.resource_clone,
        "promotable": partial(resource.resource_clone, promotable=True),
        "unclone": resource.resource_clone_master_remove,
        "enable": resource.resource_enable_cmd,
        "disable": resource.resource_disable_cmd,
        "safe-disable": resource.resource_safe_disable_cmd,
        "restart": resource.resource_restart_cmd,
        "debug-start": partial(
            resource.resource_force_action, action="debug-start"
        ),
        "debug-stop": partial(
            resource.resource_force_action, action="debug-stop"
        ),
        "debug-promote": partial(
            resource.resource_force_action, action="debug-promote"
        ),
        "debug-demote": partial(
            resource.resource_force_action, action="debug-demote"
        ),
        "debug-monitor": partial(
            resource.resource_force_action, action="debug-monitor"
        ),
        "manage": resource.resource_manage_cmd,
        "unmanage": resource.resource_unmanage_cmd,
        "failcount": create_router(
            {
                "show": resource.resource_failcount_show,
            },
            ["resource", "failcount"],
            default_cmd="show",
        ),
        "op": create_router(
            {
                "defaults": resource_op_defaults_cmd(
                    ["resource", "op", "defaults"]
                ),
                "add": resource.op_add_cmd,
                "remove": resource.op_delete_cmd,
                "delete": resource.op_delete_cmd,
            },
            ["resource", "op"],
        ),
        "defaults": resource_defaults_cmd(["resource", "defaults"]),
        "cleanup": resource.resource_cleanup,
        "refresh": resource.resource_refresh,
        "relocate": create_router(
            {
                "show": resource.resource_relocate_show_cmd,
                "dry-run": resource.resource_relocate_dry_run_cmd,
                "run": resource.resource_relocate_run_cmd,
                "clear": resource.resource_relocate_clear_cmd,
            },
            ["resource", "relocate"],
        ),
        "utilization": resource.resource_utilization_cmd,
        "bundle": create_router(
            {
                "create": resource.resource_bundle_create_cmd,
                "reset": resource.resource_bundle_reset_cmd,
                "update": resource.resource_bundle_update_cmd,
            },
            ["resource", "bundle"],
        ),
        # internal use only
        "get_resource_agent_info": resource.get_resource_agent_info,
        "relations": show_resource_relations_cmd,
    },
    ["resource"],
    default_cmd="status",
)
