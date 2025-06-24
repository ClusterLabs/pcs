from functools import partial

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.constraint import CibConstraintsDto
from pcs.lib import validate
from pcs.lib.cib.constraint import (
    colocation,
    common,
    constraint,
    location,
    order,
    resource_set,
    ticket,
)
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import (
    ElementNotFound,
    get_constraints,
    get_element_by_id,
)
from pcs.lib.env import LibraryEnvironment


# This is an extracted part of lib commands for creating set constraints for
# the purposes of code deduplication. It is not meant to be part of API.
# DEPRECATED
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


# This is an extracted part of lib commands for creating set constraints for
# the purposes of code deduplication. It is not meant to be part of API.
def _load_resource_set_list(
    cib: _Element,
    report_processor: reports.ReportProcessor,
    rsc_set_list: common.CmdInputResourceSetList,
    option_value_normalization: validate.TypeNormalizeFunc,
) -> common.CmdInputResourceSetLoadedList:
    """
    Prepare resource sets definition for further processing in commands

    cib -- loaded CIB
    rsc_set_list -- resources set definition passed as a command input
    option_value_normalization -- function for normalizing set options values
    """
    resource_set_el_list: common.CmdInputResourceSetLoadedList = []
    for input_set_def in rsc_set_list:
        el_list = []
        for resource_id in input_set_def["ids"]:
            try:
                el_list.append(get_element_by_id(cib, resource_id))
            except ElementNotFound:
                report_processor.report(
                    reports.ReportItem.error(
                        reports.messages.IdNotFound(resource_id, [])
                    )
                )
        resource_set_el_list.append(
            dict(
                constrained_elements=el_list,
                options=validate.values_to_pairs(
                    input_set_def["options"], option_value_normalization
                ),
            )
        )
    return resource_set_el_list


# This is an extracted part of lib commands for creating set constraints for
# the purposes of code deduplication. It is not meant to be part of API.
def _primitive_resource_set_list(
    rsc_set_list: common.CmdInputResourceSetLoadedList,
) -> common.CmdInputResourceSetList:
    """
    Inverse transformation to _load_resource_set_list
    """
    return [
        dict(
            ids=[
                str(el.attrib["id"]) for el in rsc_set["constrained_elements"]
            ],
            options=validate.pairs_to_values(rsc_set["options"]),
        )
        for rsc_set in rsc_set_list
    ]
