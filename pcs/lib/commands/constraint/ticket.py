from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.lib.cib.constraint import constraint, ticket
from pcs.lib.cib.tools import get_constraints
import pcs.lib.commands.constraint.common


#configure common constraint command
show = partial(
    pcs.lib.commands.constraint.common.show,
    ticket.TAG_NAME,
    lambda element: element.attrib.has_key('rsc')
)

#configure common constraint command
create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    ticket.TAG_NAME,
    ticket.prepare_options_with_set,
    duplicate_check=ticket.are_duplicate_with_resource_set,
)

def create(
    env, ticket_key, resource_id, options,
    autocorrection_allowed=False,
    resource_in_clone_alowed=False,
    duplication_alowed=False,
):
    """
    create ticket constraint
    string ticket_key ticket for constraining resource
    dict options desired constraint attributes
    bool resource_in_clone_alowed flag for allowing to reference id which is
        in tag clone or master
    bool duplication_alowed flag for allowing create duplicate element
    callable duplicate_check takes two elements and decide if they are
        duplicates
    """
    cib = env.get_cib()

    options = ticket.prepare_options_plain(
        cib,
        options,
        ticket_key,
        constraint.find_valid_resource_id(
            env.report_processor, cib,
            autocorrection_allowed, resource_in_clone_alowed, resource_id
        ),
    )

    constraint_section = get_constraints(cib)
    constraint_element = ticket.create_plain(constraint_section, options)

    constraint.check_is_without_duplication(
        env.report_processor,
        constraint_section,
        constraint_element,
        are_duplicate=ticket.are_duplicate_plain,
        export_element=constraint.export_plain,
        duplication_alowed=duplication_alowed,
    )

    env.push_cib(cib)

def remove(env, ticket_key, resource_id):
    """
    remove all ticket constraint from resource
    If resource is in resource set with another resources then only resource ref
    is removed. If resource is alone in resource set whole constraint is removed.
    """
    cib = env.get_cib()
    constraint_section = get_constraints(cib)
    any_plain_removed = ticket.remove_plain(
        constraint_section,
        ticket_key,
        resource_id
    )
    any_with_resource_set_removed = ticket.remove_with_resource_set(
        constraint_section,
        ticket_key,
        resource_id
    )

    env.push_cib(cib)

    return any_plain_removed or any_with_resource_set_removed
