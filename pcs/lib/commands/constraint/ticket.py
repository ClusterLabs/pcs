from typing import Mapping

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.cib.constraint import common, ticket
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_constraints,
    get_element_by_id,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

from .common import _load_resource_set_list, _primitive_resource_set_list


def create(
    env: LibraryEnvironment,
    ticket_key: str,
    resource_id: str,
    options: Mapping[str, str],
    resource_in_clone_alowed: bool = False,
    duplication_alowed: bool = False,
) -> None:
    """
    create a plain ticket constraint

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


def create_with_set(
    env: LibraryEnvironment,
    resource_set_list: common.CmdInputResourceSetList,
    constraint_options: Mapping[str, str],
    resource_in_clone_alowed: bool = False,
    duplication_alowed: bool = False,
) -> None:
    """
    create a set ticket constraint

    resource_set_list -- description of resource sets, for example:
        {"ids": ["A", "B"], "options": {"sequential": "true"}},
    constraint_options -- desired constraint attributes
    resource_in_clone_alowed -- allow to constrain resources in a clone
    duplication_alowed -- allow to create a duplicate constraint
    """
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    constraint_section = get_constraints(cib)

    # find all specified constrained resources and transform set options to
    # value pairs for normalization and validation
    resource_set_loaded_list = _load_resource_set_list(
        cib,
        env.report_processor,
        resource_set_list,
        validate.option_value_normalization(
            {
                "role": lambda value: value.capitalize(),
            }
        ),
    )
    # Unlike in plain constraints, validation cannot continue if even a single
    # resource could not be found. If such resources were omitted in their sets
    # for purposes of validation, similarly to plain constraint commands, then
    # those sets could become invalid, and thus validating such sets would
    # provide false results.
    if env.report_processor.has_errors:
        raise LibraryError()

    # transform constraint options to value pairs for normalization and
    # validation
    constraint_options_pairs = validate.values_to_pairs(
        constraint_options,
        validate.option_value_normalization(
            {
                "loss-policy": lambda value: value.lower(),
            }
        ),
    )

    # validation
    env.report_processor.report_list(
        ticket.validate_create_with_set(
            id_provider,
            resource_set_loaded_list,
            constraint_options_pairs,
            in_multiinstance_allowed=resource_in_clone_alowed,
        )
    )
    if env.report_processor.has_errors:
        raise LibraryError()

    # modify CIB
    new_constraint = ticket.create_with_set(
        constraint_section,
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        _primitive_resource_set_list(resource_set_loaded_list),
        validate.pairs_to_values(constraint_options_pairs),
    )

    # Check whether the created constraint is a duplicate of an existing one
    env.report_processor.report_list(
        ticket.DuplicatesCheckerTicketWithSet().check(
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
