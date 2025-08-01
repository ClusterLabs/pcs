from typing import (
    Any,
    cast,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.constraint import command
from pcs.cli.constraint.output import print_config
from pcs.cli.reports.output import deprecation_warning
from pcs.cli.reports.preprocessor import (
    get_duplicate_constraint_exists_preprocessor,
)
from pcs.common.pacemaker.constraint import CibConstraintsDto


def create_with_set(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    create colocation constraint with resource set
    object lib exposes library
    list argv see usage for "constraint colocation set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Options:
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--force")
    lib.env.report_processor.set_report_item_preprocessor(
        get_duplicate_constraint_exists_preprocessor(lib)
    )
    command.create_with_set(
        lib.constraint_colocation.create_with_set,
        argv,
        modifiers,
    )


def show(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint colocation config' instead."
    )
    return config_cmd(lib, argv, modifiers)


def config_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    modifiers.ensure_only_supported("-f", "--output-format", "--full")
    if argv:
        raise CmdLineInputError()

    constraints_dto = cast(
        CibConstraintsDto,
        lib.constraint.get_config(evaluate_rules=True),
    )

    print_config(
        CibConstraintsDto(
            colocation=constraints_dto.colocation,
            colocation_set=constraints_dto.colocation_set,
        ),
        modifiers,
    )


def remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 2:
        raise CmdLineInputError()
    source_rsc_id, target_rsc_id = argv
    constraint_ids_to_remove: list[str] = []
    constraint_dto = lib.constraint.get_config(evaluate_rules=False)
    for colocation_dto in constraint_dto.colocation:
        if (
            colocation_dto.resource_id == source_rsc_id
            and colocation_dto.with_resource_id == target_rsc_id
        ):
            constraint_ids_to_remove.append(
                colocation_dto.attributes.constraint_id
            )
        elif (
            colocation_dto.resource_id == target_rsc_id
            and colocation_dto.with_resource_id == source_rsc_id
        ):
            # deprecated since pcs-0.11.7
            deprecation_warning(
                "Removing colocation constraint with interchanged source "
                "resource id and target resource id. This behavior is "
                "deprecated and will be removed."
            )
            constraint_ids_to_remove.append(
                colocation_dto.attributes.constraint_id
            )
    if not constraint_ids_to_remove:
        raise CmdLineInputError(
            f"Unable to find colocation constraint with source resource "
            f"'{source_rsc_id}' and target resource '{target_rsc_id}'"
        )
    lib.cib.remove_elements(constraint_ids_to_remove)
