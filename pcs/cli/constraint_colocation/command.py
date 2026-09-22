from typing import Any, cast

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv, InputModifiers
from pcs.cli.constraint import command
from pcs.cli.constraint.output import print_config
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
    constraint_dto = lib.constraint.get_config(evaluate_rules=False)
    constraint_ids_to_remove = [
        colocation_dto.attributes.constraint_id
        for colocation_dto in constraint_dto.colocation
        if (
            colocation_dto.resource_id == source_rsc_id
            and colocation_dto.with_resource_id == target_rsc_id
        )
    ]
    if not constraint_ids_to_remove:
        raise CmdLineInputError(
            f"Unable to find colocation constraint with source resource "
            f"'{source_rsc_id}' and target resource '{target_rsc_id}'"
        )
    lib.cib.remove_elements(constraint_ids_to_remove)
