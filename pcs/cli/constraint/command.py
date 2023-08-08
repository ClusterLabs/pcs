from typing import (
    Any,
    Callable,
)

from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.constraint import parse_args


def create_with_set(
    create_with_set_library_call: Callable[..., Any],
    argv: Argv,
    modifiers: InputModifiers,
) -> None:
    """
    callable create_with_set_library_call create constraint with set
    argv -- part of comandline args
    modifiers -- can contain "force" allowing resources in clone/promotable and
        constraint duplicity

    Commandline options:
      * --force - allow a resource inside clone or promotable, allow duplicate
        element
      * -f - CIB file
    """
    resource_set_list, constraint_options = parse_args.prepare_set_args(argv)
    create_with_set_library_call(
        resource_set_list,
        constraint_options,
        resource_in_clone_alowed=modifiers.get("--force"),
        duplication_alowed=modifiers.get("--force"),
    )
