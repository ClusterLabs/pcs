from functools import partial

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.pacemaker.constraint import (
    CibConstraintColocationAttributesDto,
    CibConstraintColocationDto,
    CibConstraintColocationSetDto,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.constraint.resource_set import (
    constraint_element_to_resource_set_dto_list,
    is_set_constraint,
)
from pcs.lib.cib.rule import RuleInEffectEval
from pcs.lib.cib.rule.cib_to_dto import rule_element_to_dto
from pcs.lib.cib.tools import (
    check_new_id_applicable,
    role_constructor,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    SCORE_INFINITY,
    is_score,
)
from pcs.lib.tools import get_optional_value

TAG_NAME = "rsc_colocation"
DESCRIPTION = "constraint id"


def is_colocation_constraint(element: _Element) -> bool:
    return element.tag == TAG_NAME


def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        ("score",),
        options,
        partial(constraint.create_id, cib, "colocation", resource_set_list),
        partial(check_new_id_applicable, cib, DESCRIPTION),
    )

    if "score" in options:
        if not is_score(options["score"]):
            raise LibraryError(
                ReportItem.error(
                    reports.messages.InvalidScore(options["score"])
                )
            )
    else:
        options["score"] = SCORE_INFINITY

    return options


def _element_to_attributes_dto(
    element: _Element, rule_in_effect_eval: RuleInEffectEval
) -> CibConstraintColocationAttributesDto:
    return CibConstraintColocationAttributesDto(
        constraint_id=str(element.attrib["id"]),
        score=element.get("score"),
        influence=element.get("influence"),
        lifetime=[
            rule_element_to_dto(rule_in_effect_eval, rule_el)
            for rule_el in element.findall("./lifetime/rule")
        ],
    )


def _constraint_el_to_dto(
    element: _Element, rule_in_effect_eval: RuleInEffectEval
) -> CibConstraintColocationDto:
    return CibConstraintColocationDto(
        resource_id=str(element.attrib["rsc"]),
        with_resource_id=str(element.attrib["with-rsc"]),
        node_attribute=element.get("node-attribute"),
        resource_role=get_optional_value(
            role_constructor, element.get("rsc-role")
        ),
        with_resource_role=get_optional_value(
            role_constructor, element.get("with-rsc-role")
        ),
        resource_instance=get_optional_value(int, element.get("rsc-instance")),
        with_resource_instance=get_optional_value(
            int, element.get("with-rsc-instance")
        ),
        attributes=_element_to_attributes_dto(element, rule_in_effect_eval),
    )


def _set_constraint_el_to_dto(
    element: _Element, rule_in_effect_eval: RuleInEffectEval
) -> CibConstraintColocationSetDto:
    return CibConstraintColocationSetDto(
        resource_sets=constraint_element_to_resource_set_dto_list(element),
        attributes=_element_to_attributes_dto(element, rule_in_effect_eval),
    )


def get_all_as_dtos(
    constraints_el: _Element, rule_in_effect_eval: RuleInEffectEval
) -> tuple[
    list[CibConstraintColocationDto], list[CibConstraintColocationSetDto]
]:
    plain_list: list[CibConstraintColocationDto] = []
    set_list: list[CibConstraintColocationSetDto] = []
    for constraint_el in constraints_el.findall(f"./{TAG_NAME}"):
        if is_set_constraint(constraint_el):
            set_list.append(
                _set_constraint_el_to_dto(constraint_el, rule_in_effect_eval)
            )
        else:
            plain_list.append(
                _constraint_el_to_dto(constraint_el, rule_in_effect_eval)
            )
    return plain_list, set_list
