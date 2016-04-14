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


show = partial(
    pcs.lib.commands.constraint.common.show,
    ticket.TAG_NAME,
    lambda element: element.attrib.has_key('rsc')
)

create_with_set = partial(
    pcs.lib.commands.constraint.common.create_with_set,
    ticket.TAG_NAME,
    ticket.prepare_options_with_set,
    duplicity_check=ticket.are_duplicit_with_resource_set,
)

def create(
    env, ticket_key, resource_id, resource_role, options,
    autocorrection_allowed=False,
    resource_in_clone_alowed=False,
    duplication_alowed=False,
):
    cib = env.get_cib()

    options = ticket.prepare_options_plain(
        cib,
        options,
        ticket_key,
        constraint.find_valid_resource_id(
            cib, autocorrection_allowed, resource_in_clone_alowed, resource_id
        ),
        resource_role
    )

    constraint_section = get_constraints(cib)
    constraint_element = ticket.create_plain(constraint_section, options)

    if not duplication_alowed:
        constraint.check_is_without_duplication(
            constraint_section,
            constraint_element,
            are_duplicit=ticket.are_duplicit_plain,
            export_element=constraint.export_plain,
        )

    env.push_cib(cib)
