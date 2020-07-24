from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint import command
from pcs.cli.constraint_ticket import parse_args
from pcs.cli.reports.output import error
from pcs.common.reports import constraints


def create_with_set(lib, argv, modifiers):
    """
    create ticket constraint with resource set
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
    command.create_with_set(
        lib.constraint_ticket.set, argv, modifiers,
    )


def add(lib, argv, modifiers):
    """
    create ticket constraint
    object lib exposes library
    list argv see usage for "constraint colocation add"
    dict like object modifiers can contain
        "force" allows resource in clone/main and constraint duplicity

    Options:
      * --force - allow resource inside clone (or main), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    ticket, resource_id, resource_role, options = parse_args.parse_add(argv)
    if "rsc-role" in options:
        raise CmdLineInputError(
            "Resource role must not be specified among options"
            + ", specify it before resource id"
        )

    if resource_role:
        options["rsc-role"] = resource_role

    lib.constraint_ticket.add(
        ticket,
        resource_id,
        options,
        resource_in_clone_alowed=modifiers.get("--force"),
        duplication_alowed=modifiers.get("--force"),
    )


def remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 2:
        raise CmdLineInputError()
    ticket, resource_id = argv
    if not lib.constraint_ticket.remove(ticket, resource_id):
        raise error("no matching ticket constraint found")


def show(lib, argv, modifiers):
    """
    show all ticket constraints
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
                "Ticket Constraints:",
                lib.constraint_ticket.show,
                constraints.ticket_plain,
                modifiers,
            )
        )
    )
