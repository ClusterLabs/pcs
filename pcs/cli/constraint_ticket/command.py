from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint import command
from pcs.cli.constraint_ticket import parse_args, console_report
from pcs.cli.common.console_report import error

def create_with_set(lib, argv, modifiers):
    """
    create ticket constraint with resource set
    object lib exposes library
    list argv see usage for "constraint colocation set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity
        "autocorrect" allows correct resource to its clone/master parent

    Options:
      * --autocorrect - can repair to clone
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--autocorrect", "--force", "-f")
    command.create_with_set(
        lib.constraint_ticket.set,
        argv,
        modifiers,
    )

def add(lib, argv, modifiers):
    """
    create ticket constraint
    object lib exposes library
    list argv see usage for "constraint colocation add"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity
        "autocorrect" allows correct resource to its clone/master parent

    Options:
      * --autocorrect - allow autocorrection
      * --force - allow resource inside clone (or master), allow duplicate
        element
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--autocorrect", "--force", "-f")
    ticket, resource_id, resource_role, options = parse_args.parse_add(argv)
    if "rsc-role" in options:
        raise CmdLineInputError(
            "Resource role must not be specified among options"
            +", specify it before resource id"
        )

    if resource_role:
        options["rsc-role"] = resource_role

    lib.constraint_ticket.add(
        ticket,
        resource_id,
        options,
        autocorrection_allowed=modifiers.get("--autocorrect"),
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
    print("\n".join(command.show(
        "Ticket Constraints:",
        lib.constraint_ticket.show,
        console_report.constraint_plain,
        modifiers,
    )))
