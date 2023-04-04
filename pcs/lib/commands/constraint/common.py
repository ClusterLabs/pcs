"""
Common functions used from specific constraint commands.
Functions of this module are not intended to be used for direct call from
client.
"""
from functools import partial

from pcs.common import reports
from pcs.common.pacemaker.constraint import CibConstraintsDto
from pcs.lib.cib.constraint import (
    colocation,
    constraint,
    location,
    order,
    resource_set,
    ticket,
)
from pcs.lib.cib.constraint.all import is_constraint
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import (
    get_constraints,
    get_elements_by_ids,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def create_with_set(
    tag_name,
    prepare_options,
    env,
    resource_set_list,
    constraint_options,
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
        env.report_processor,
        cib,
        resource_in_clone_alowed,
    )

    constraint_section = get_constraints(cib)
    constraint_element = constraint.create_with_set(
        constraint_section,
        tag_name,
        options=prepare_options(cib, constraint_options, resource_set_list),
        resource_set_list=[
            resource_set.prepare_set(
                find_valid_resource_id, resource_set_item, env.report_processor
            )
            for resource_set_item in resource_set_list
        ],
    )

    if not duplicate_check:
        duplicate_check = constraint.have_duplicate_resource_sets

    constraint.check_is_without_duplication(
        env.report_processor,
        constraint_section,
        constraint_element,
        are_duplicate=duplicate_check,
        export_element=constraint.export_with_set,
        duplication_allowed=duplication_alowed,
    )

    env.push_cib()


def get_config(
    env: LibraryEnvironment,
    evaluate_rules: bool = False,
) -> CibConstraintsDto:
    cib = env.get_cib()
    constraints_el = get_constraints(cib)
    rule_evaluator = get_rule_evaluator(
        cib, env.cmd_runner(), env.report_processor, evaluate_rules
    )
    location_constraints, location_set_constraints = location.get_all_as_dtos(
        constraints_el, rule_evaluator
    )
    (
        colocation_constraints,
        colocation_set_constraints,
    ) = colocation.get_all_as_dtos(constraints_el, rule_evaluator)
    order_constraints, order_set_constraints = order.get_all_as_dtos(
        constraints_el
    )
    ticket_constraints, ticket_set_constraints = ticket.get_all_as_dtos(
        constraints_el
    )
    return CibConstraintsDto(
        location=location_constraints,
        location_set=location_set_constraints,
        colocation=colocation_constraints,
        colocation_set=colocation_set_constraints,
        order=order_constraints,
        order_set=order_set_constraints,
        ticket=ticket_constraints,
        ticket_set=ticket_set_constraints,
    )


def remove(env: LibraryEnvironment, ids: list[str]) -> None:
    cib = env.get_cib()
    report_processor = env.report_processor
    elements, not_found_ids = get_elements_by_ids(cib, ids)

    for non_existing_id in not_found_ids:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.IdNotFound(non_existing_id, ["constraint"])
            )
        )

    constraints_elements = []
    for element in elements:
        if is_constraint(element):
            constraints_elements.append(element)
        else:
            report_processor.report(
                reports.ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        str(element.get("id")), ["constraint"], element.tag
                    )
                )
            )

    if report_processor.has_errors:
        raise LibraryError()

    for constraint_el in constraints_elements:
        parent_el = constraint_el.getparent()
        if parent_el is None:
            # This should never happen as all constraitns are inside element
            # with tag 'constraints'
            constraint_id = constraint_el.get("id")
            raise AssertionError(
                f"Invalid CIB, constraint '{constraint_id}' has no parrent element"
            )
        parent_el.remove(constraint_el)

    env.push_cib()
