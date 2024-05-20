from typing import (
    Any,
    List,
)

from pcs import resource
from pcs.cli.common.errors import (
    command_replaced,
    raise_command_replaced,
)
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.common.routing import (
    CliCmdInterface,
    create_router,
)


def resource_show(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool = False
) -> None:
    """
    Options:
      * -f - CIB file
      * --full - print all configured options
      * --groups - print resource groups
      * --hide-inactive - print only active resources
    """
    del lib
    modifiers.ensure_only_supported(
        "-f", "--full", "--groups", "--hide-inactive"
    )
    if modifiers.get("--groups"):
        raise_command_replaced(["pcs resource group list"], pcs_version="0.11")

    keyword = "stonith" if stonith else "resource"
    if modifiers.get("--full") or argv:
        raise_command_replaced([f"pcs {keyword} config"], pcs_version="0.11")

    raise_command_replaced([f"pcs {keyword} status"], pcs_version="0.11")


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
            raise command_replaced(
                ["pcs resource defaults update"], pcs_version="0.12"
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
                "update": resource.resource_defaults_update_cmd,
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
            raise command_replaced(
                ["pcs resource op defaults update"], pcs_version="0.12"
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
                "update": resource.resource_op_defaults_update_cmd,
            },
            parent_cmd,
            default_cmd="config",
        )
        return router(lib, argv, modifiers)

    return _get_router
