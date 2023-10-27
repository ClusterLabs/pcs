from typing import (
    Any,
    Callable,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    ensure_unique_args,
)
from pcs.cli.constraint import parse_args
from pcs.common.pacemaker.constraint import (
    get_all_constraints_ids,
    get_all_location_rules_ids,
)
from pcs.common.str_tools import format_list


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


def remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    ensure_unique_args(argv)
    constraints_dto = lib.constraint.get_config(evaluate_rules=False)
    missing_ids = set(argv) - (
        get_all_constraints_ids(constraints_dto)
        | get_all_location_rules_ids(constraints_dto)
    )
    if missing_ids:
        raise CmdLineInputError(
            f"Unable to find constraint or rule ids: {format_list(missing_ids)}"
        )
    lib.cib.remove_elements(argv)
