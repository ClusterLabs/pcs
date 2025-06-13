from functools import partial
from typing import Mapping

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.cib.constraint import ticket
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_constraints,
    get_element_by_id,
    get_pacemaker_version_by_which_cib_was_validated,
)
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
    id_provider = IdProvider(cib)
    constraint_section = get_constraints(cib)

    # validation
    constrained_el = None
    try:
        constrained_el = get_element_by_id(cib, resource_id)
    except ElementNotFound:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(resource_id, [])
            )
        )

    options_pairs = validate.values_to_pairs(
        options,
        validate.option_value_normalization(
            {
                "loss-policy": lambda value: value.lower(),
                "rsc-role": lambda value: value.capitalize(),
            }
        ),
    )

    env.report_processor.report_list(
        ticket.validate_create_plain(
            id_provider,
            ticket_key,
            constrained_el,
            options_pairs,
            in_multiinstance_allowed=resource_in_clone_alowed,
        )
    )

    if env.report_processor.has_errors:
        raise LibraryError()

    # modify CIB
    new_constraint = ticket.create_plain(
        constraint_section,
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        ticket_key,
        resource_id,
        validate.pairs_to_values(options_pairs),
    )

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
