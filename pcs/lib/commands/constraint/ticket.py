from functools import partial

import pcs.lib.commands.constraint.common
from pcs.lib.cib.constraint import (
    constraint,
    ticket,
)
from pcs.lib.cib.tools import (
    are_new_role_names_supported,
    get_constraints,
)

# configure common constraint command
config = partial(
    pcs.lib.commands.constraint.common.config,
    ticket.TAG_NAME,
    lambda element: element.attrib.has_key("rsc"),
)

# configure common constraint command
create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    ticket.TAG_NAME,
    ticket.prepare_options_with_set,
    duplicate_check=ticket.are_duplicate_with_resource_set,
)


def create(
    env,
    ticket_key,
    resource_id,
    options,
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
        env.report_processor,
        options,
        ticket_key,
        constraint.find_valid_resource_id(
            env.report_processor, cib, resource_in_clone_alowed, resource_id
        ),
    )

    constraint_section = get_constraints(cib)
    constraint_element = ticket.create_plain(constraint_section, options)

    constraint.check_is_without_duplication(
        env.report_processor,
        constraint_section,
        constraint_element,
        are_duplicate=ticket.get_duplicit_checker_callback(
            are_new_role_names_supported(constraint_section)
        ),
        export_element=constraint.export_plain,
        duplication_allowed=duplication_alowed,
    )

    env.push_cib()


def remove(env, ticket_key, resource_id):
    """
    remove all ticket constraint from resource
    If resource is in resource set with another resources then only resource
    ref is removed. If resource is alone in resource set whole constraint is
    removed.
    """
    constraint_section = get_constraints(env.get_cib())
    any_plain_removed = ticket.remove_plain(
        constraint_section, ticket_key, resource_id
    )
    any_with_resource_set_removed = ticket.remove_with_resource_set(
        constraint_section, ticket_key, resource_id
    )

    env.push_cib()

    return any_plain_removed or any_with_resource_set_removed
