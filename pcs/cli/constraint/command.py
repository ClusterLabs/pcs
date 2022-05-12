from pcs.cli.constraint import parse_args
from pcs.common.reports.constraints import constraint_with_sets
from pcs.common.str_tools import indent


def create_with_set(create_with_set_library_call, argv, modifiers):
    """
    callable create_with_set_library_call create constraint with set
    list argv part of comandline args
        see usage for  "constraint (colocation|resource|ticket) set"
    dict like object modifiers can contain
        "force" allows resource in clone/master and constraint duplicity

    Commandline options:
      * --force - allow resource inside clone (or master), allow duplicate
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


def _config_constraints_with_set(constraint_list, show_detail, indent_step=2):
    """
    return list of console lines with info about constraints
    list of dict constraint_list see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options
    int indent_step is count of spaces for indenting

    Commandline options: no options
    """
    return ["Resource Sets:"] + indent(
        [
            constraint_with_sets(constraint, with_id=show_detail)
            for constraint in constraint_list
        ],
        indent_step=indent_step,
    )


def config_cmd(caption, load_constraints, format_options, modifiers):
    """
    load constraints and return console lines list with info about constraints
    string caption for example "Ticket Constraints:"
    callable load_constraints which returns desired constraints as dictionary
        like {"plain": [], "with_resource_sets": []}
    callable format_options takes dict of options and show_detail flag (bool)
        and returns string with constraint formatted for commandline
    modifiers dict like object with command modifiers

    Commandline options:
      * -f - CIB file
      * --full - print more details
    """
    show_detail = modifiers.get("--full")
    constraints = load_constraints()

    line_list = [caption]
    line_list.extend(
        [
            "  " + format_options(constraint_options_dict, show_detail)
            for constraint_options_dict in constraints["plain"]
        ]
    )

    if constraints["with_resource_sets"]:
        line_list.extend(
            indent(
                _config_constraints_with_set(
                    constraints["with_resource_sets"], show_detail
                )
            )
        )

    return line_list
