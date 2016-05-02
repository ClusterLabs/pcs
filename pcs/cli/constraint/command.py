from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.constraint import parse_args, console_report
from pcs.cli.common.console_report import indent

def create_with_set(create_with_set_library_call, argv, modificators):
    """
    callable create_with_set_library_call create constraint with set
    list argv part of comandline args
        see usage for  "constraint (colocation|resource|ticket) set"
    dict like object modificators can contain
        "force" allows resource in clone/master and constraint duplicity
        "autocorrect" allows correct resource to its clone/master parent
    """
    resource_set_list, constraint_options = parse_args.prepare_set_args(argv)
    create_with_set_library_call(
        resource_set_list, constraint_options,
        can_repair_to_clone=modificators["autocorrect"],
        resource_in_clone_alowed=modificators["force"],
        duplication_alowed=modificators["force"],
    )

def show_constraints_with_set(constraint_list, show_detail, indent_step=2):
    """
    return list of console lines with info about constraints
    list of dict constraint_list see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options
    int indent_step is count of spaces for indenting
    """
    return ["Resource Sets:"] + indent(
        [
            console_report.constraint_with_sets(constraint, with_id=show_detail)
            for constraint in constraint_list
        ],
        indent_step=indent_step
    )

def show(caption, load_constraints, format_options, modificators):
    """
    load constraints and return console lines list with info about constraints
    string caption for example "Ticket Constraints:"
    callable load_constraints which returns desired constraints as dictionary
        like {"plain": [], "with_resource_sets": []}
    callable format_options takes dict of options and show_detail flag (bool)
        and returns string with constraint formated for commandline
    modificators dict like object with command modificators
    """
    show_detail = modificators["full"]
    constraints = load_constraints()

    line_list = [caption]
    line_list.extend([
        "  " + format_options(constraint_options_dict, show_detail)
        for constraint_options_dict in constraints["plain"]
    ])

    if constraints["with_resource_sets"]:
        line_list.extend(
            indent(show_constraints_with_set(
                constraints["with_resource_sets"],
                show_detail
            ))
        )

    return line_list
