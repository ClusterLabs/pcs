from pcs import (
    acl,
    usage,
)
from pcs.cli.common.routing import create_router


acl_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.acl(argv),
        "show": acl.show_acl_config,
        "enable": acl.acl_enable,
        "disable": acl.acl_disable,
        "role": create_router(
            {
                "create": acl.role_create,
                "delete": acl.role_delete,
                "remove": acl.role_delete,
                "assign": acl.role_assign,
                "unassign": acl.role_unassign,
            },
            ["acl", "role"],
        ),
        "user": create_router(
            {
                "create": acl.user_create,
                "delete": acl.user_delete,
                "remove": acl.user_delete,
            },
            ["acl", "user"],
        ),
        "group": create_router(
            {
                "create": acl.group_create,
                "delete": acl.group_delete,
                "remove": acl.group_delete,
            },
            ["acl", "group"],
        ),
        "permission": create_router(
            {
                "add": acl.permission_add,
                "delete": acl.run_permission_delete,
                "remove": acl.run_permission_delete,
            },
            ["acl", "permission"],
        ),
    },
    ["acl"],
    default_cmd="show",
)
