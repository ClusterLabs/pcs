from typing import (
    Any,
    List,
)

from pcs import resource
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.common.routing import (
    CliCmdInterface,
    create_router,
)


def resource_defaults_cmd(parent_cmd: List[str]) -> CliCmdInterface:
    def _get_router(
        lib: Any, argv: List[str], modifiers: InputModifiers
    ) -> None:
        """
        Options:
          * -f - CIB file
          * --force - allow unknown options
        """
        if argv and "=" in argv[0]:
            # DEPRECATED legacy command
            return resource.resource_defaults_legacy_cmd(
                lib, argv, modifiers, deprecated_syntax_used=True
            )

        router = create_router(
            {
                "config": resource.resource_defaults_config_cmd,
                "set": create_router(
                    {
                        "create": resource.resource_defaults_set_create_cmd,
                        "delete": resource.resource_defaults_set_remove_cmd,
                        "remove": resource.resource_defaults_set_remove_cmd,
                        "update": resource.resource_defaults_set_update_cmd,
                    },
                    parent_cmd + ["set"],
                ),
                "update": resource.resource_defaults_legacy_cmd,
            },
            parent_cmd,
            default_cmd="config",
        )
        return router(lib, argv, modifiers)

    return _get_router


def resource_op_defaults_cmd(parent_cmd: List[str]) -> CliCmdInterface:
    def _get_router(
        lib: Any, argv: List[str], modifiers: InputModifiers
    ) -> None:
        """
        Options:
          * -f - CIB file
          * --force - allow unknown options
        """
        if argv and "=" in argv[0]:
            # DEPRECATED legacy command
            return resource.resource_op_defaults_legacy_cmd(
                lib, argv, modifiers, deprecated_syntax_used=True
            )

        router = create_router(
            {
                "config": resource.resource_op_defaults_config_cmd,
                "set": create_router(
                    {
                        "create": resource.resource_op_defaults_set_create_cmd,
                        "delete": resource.resource_op_defaults_set_remove_cmd,
                        "remove": resource.resource_op_defaults_set_remove_cmd,
                        "update": resource.resource_op_defaults_set_update_cmd,
                    },
                    parent_cmd + ["set"],
                ),
                "update": resource.resource_op_defaults_legacy_cmd,
            },
            parent_cmd,
            default_cmd="config",
        )
        return router(lib, argv, modifiers)

    return _get_router
