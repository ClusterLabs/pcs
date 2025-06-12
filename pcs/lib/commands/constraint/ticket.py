from functools import partial
from typing import Mapping

from pcs.common import reports
from pcs.lib.cib.constraint import constraint, ticket
from pcs.lib.cib.tools import get_constraints
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

from . import common

# configure common constraint command
create_with_set = partial(
    common.create_with_set,
    ticket.TAG,
    ticket.prepare_options_with_set,
    duplicate_check=ticket.are_duplicate_with_resource_set,
)


def create(
    env: LibraryEnvironment,
    ticket_key: str,
    resource_id: str,
    options: Mapping[str, str],
    resource_in_clone_alowed: bool = False,
    duplication_alowed: bool = False,
):
    """
    create a ticket constraint

    ticket_key -- ticket for constraining a resource
    resource_id -- resource to be constrained
    options -- desired constraint attributes
    resource_in_clone_alowed -- allow to constrain a resource in a clone
    duplication_alowed -- allow to create a duplicate constraint
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
    new_constraint = ticket.create_plain(constraint_section, options)

    # Check whether the created constraint is a duplicate of an existing one
    env.report_processor.report_list(
        ticket.DuplicatesCheckerTicketPlain().check(
            constraint_section,
            new_constraint,
            {reports.codes.FORCE} if duplication_alowed else set(),
        )
    )
    if env.report_processor.has_errors:
        raise LibraryError()

    # push CIB
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
