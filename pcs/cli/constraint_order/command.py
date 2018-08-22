from pcs.cli.constraint import command
from pcs.cli.constraint_order import console_report


def create_with_set(lib, argv, modifiers):
    """
    create order constraint with resource set
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
        lib.constraint_order.set,
        argv,
        modifiers
    )

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
    print("\n".join(command.show(
        "Ordering Constraints:",
        lib.constraint_order.show,
        console_report.constraint_plain,
        modifiers,
    )))
