from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint import command
from pcs.common.reports import constraints


def create_with_set(lib, argv, modifiers):
    """
    create order constraint with resource set
    object lib exposes library
    list argv see usage for "constraint colocation set"
    dict like object modifiers can contain
        "force" allows resource in clone/main and constraint duplicity

    Options:
      * --force - allow resource inside clone (or main), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    command.create_with_set(lib.constraint_order.set, argv, modifiers)


def show(lib, argv, modifiers):
    """
    show all order constraints
    object lib exposes library
    list argv see usage for "constraint colocation show"
    dict like object modifiers can contain "full"

    Options:
      * --full - print more details
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--full")
    if argv:
        raise CmdLineInputError()
    print(
        "\n".join(
            command.show(
                "Ordering Constraints:",
                lib.constraint_order.show,
                constraints.order_plain,
                modifiers,
            )
        )
    )
