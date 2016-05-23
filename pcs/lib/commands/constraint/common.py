"""
Common functions used from specific constraint commands.
Functions of this module are not intended to be used for direct call from
client.
"""
from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.lib.cib.constraint import constraint, resource_set
from pcs.lib.cib.tools import get_constraints


def create_with_set(
    tag_name, prepare_options, env, resource_set_list, constraint_options,
    can_repair_to_clone=False,
    resource_in_clone_alowed=False,
    duplication_alowed=False,
    duplicate_check=None,
):
    """
    string tag_name is constraint tag name
    callable prepare_options takes
        cib(Element), options(dict), resource_set_list and return corrected
        options or if options not usable raises error
    env is library environment
    list resource_set_list is description of resource set, for example:
        {"ids": ["A", "B"], "options": {"sequential": "true"}},
    dict constraint_options is base for building attributes of constraint tag
    bool resource_in_clone_alowed flag for allowing to reference id which is
        in tag clone or master
    bool duplication_alowed flag for allowing create duplicate element
    callable duplicate_check takes two elements and decide if they are
        duplicates
    """
    cib = env.get_cib()

    find_valid_resource_id = partial(
        constraint.find_valid_resource_id,
        env.report_processor, cib, can_repair_to_clone, resource_in_clone_alowed
    )

    constraint_section = get_constraints(cib)
    constraint_element = constraint.create_with_set(
        constraint_section,
        tag_name,
        options=prepare_options(cib, constraint_options, resource_set_list),
        resource_set_list=[
             resource_set.prepare_set(find_valid_resource_id, resource_set_item)
             for resource_set_item in resource_set_list
        ]
    )

    if not duplicate_check:
        duplicate_check = constraint.have_duplicate_resource_sets

    constraint.check_is_without_duplication(
        env.report_processor,
        constraint_section,
        constraint_element,
        are_duplicate=duplicate_check,
        export_element=constraint.export_with_set,
        duplication_alowed=duplication_alowed,
    )

    env.push_cib(cib)

def show(tag_name, is_plain, env):
    """
    string tag_name is constraint tag name
    callable is_plain takes constraint element and returns if is plain (i.e.
        without resource set)
    env is library environment
    """
    constraints_info = {"plain": [], "with_resource_sets": []}
    for element in get_constraints(env.get_cib()).findall(".//"+tag_name):
        if is_plain(element):
            constraints_info["plain"].append(constraint.export_plain(element))
        else:
            constraints_info["with_resource_sets"].append(
                constraint.export_with_set(element)
            )
    return constraints_info
