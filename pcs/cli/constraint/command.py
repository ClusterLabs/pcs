from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.constraint import parse_args, console_report

def create_with_set(create_with_set, argv, modificators):
    """
    callable create_with_set create constraint with set
    list argv part of comandline args
    modificators dict like object with command modificators
    """
    resource_set_list, constraint_options = parse_args.prepare_set_args(argv)
    create_with_set(
        resource_set_list, constraint_options,
        can_repair_to_clone=modificators["autocorrect"],
        resource_in_clone_alowed=modificators["force"],
        duplication_alowed=modificators["force"],
    )

def show_constraints_with_set(constraint_with_set_list, show_detail):
    """
    return console lines list with info about constraints
    list constraint_with_set_list for example:
        [{"attrib": {"id": "id_constraint"}, "resource_sets": [{
            "ids": ["resource_id_1", "resource_id_2"],
            "attrib": {"id": "resource_set_id"}
        }]}]
    bool with_id have to show id with attributes
    """
    return ["  Resource Sets:"] + [
        "    "+console_report.constraint_with_sets(
            constraint,
            with_id=show_detail
        )
        for constraint in constraint_with_set_list
    ]

def show(caption, load_constraints, format_attrs, modificators):
    """
    load constraints and return console lines list with info about constraints
    string caption for example "Ticket Constraints:"
    callable load_constraints which returns desired constraints as dictionary
        like {"plain": [], "with_resource_sets": []}
    callable format_attrs takes dict of attributes and show_detail flag (bool)
        and returns string with constraint formated for commandline
    modificators dict like object with command modificators
    """
    show_detail = modificators["full"]
    constraints = load_constraints()

    line_list = [caption]
    line_list.extend([
        "  " + format_attrs(constraint_attribute_dict, show_detail)
        for constraint_attribute_dict in constraints["plain"]
    ])

    if constraints["with_resource_sets"]:
        line_list.extend(show_constraints_with_set(
            constraints["with_resource_sets"],
            show_detail
        ))

    return line_list
