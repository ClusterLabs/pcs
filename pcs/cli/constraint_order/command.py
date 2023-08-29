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
from pcs.common.pacemaker.constraint import CibConstraintsDto


def create_with_set(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    create order constraint with resource set
    object lib exposes library
    list argv see usage for "constraint colocation set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Options:
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    command.create_with_set(
        lib.constraint_order.create_with_set, argv, modifiers
    )


def show(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint order config' instead."
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
            order=constraints_dto.order,
            order_set=constraints_dto.order_set,
        ),
        modifiers,
    )
