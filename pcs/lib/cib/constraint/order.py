from functools import partial

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.const import PcmkAction
from pcs.common.pacemaker.constraint import (
    CibConstraintOrderAttributesDto,
    CibConstraintOrderDto,
    CibConstraintOrderSetDto,
)
from pcs.common.pacemaker.types import CibResourceSetOrderType
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.constraint.resource_set import (
    constraint_element_to_resource_set_dto_list,
    is_set_constraint,
)
from pcs.lib.cib.tools import check_new_id_applicable
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    BOOLEAN_VALUES,
    is_true,
)
from pcs.lib.tools import get_optional_value

TAG_NAME = "rsc_order"
DESCRIPTION = "constraint id"
ATTRIB = {
    "symmetrical": BOOLEAN_VALUES,
    "kind": ("Optional", "Mandatory", "Serialize"),
}


def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        tuple(ATTRIB.keys()),
        options,
        create_id_fn=partial(
            constraint.create_id, cib, "order", resource_set_list
        ),
        validate_id=partial(check_new_id_applicable, cib, DESCRIPTION),
    )

    report_items = []
    if "kind" in options:
        kind = options["kind"].lower().capitalize()
        if kind not in ATTRIB["kind"]:
            report_items.append(
                ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "kind", options["kind"], ATTRIB["kind"]
                    )
                )
            )
        options["kind"] = kind

    if "symmetrical" in options:
        symmetrical = options["symmetrical"].lower()
        if symmetrical not in ATTRIB["symmetrical"]:
            report_items.append(
                ReportItem.error(
                    reports.messages.InvalidOptionValue(
                        "symmetrical",
                        options["symmetrical"],
                        ATTRIB["symmetrical"],
                    )
                )
            )
        options["symmetrical"] = symmetrical

    if report_items:
        raise LibraryError(*report_items)

    return options


def _element_to_attributes_dto(
    element: _Element,
) -> CibConstraintOrderAttributesDto:
    return CibConstraintOrderAttributesDto(
        constraint_id=str(element.attrib["id"]),
        symmetrical=get_optional_value(is_true, element.get("symmetrical")),
        require_all=get_optional_value(is_true, element.get("require-all")),
        score=element.get("score"),
        kind=get_optional_value(CibResourceSetOrderType, element.get("kind")),
    )


def _constraint_el_to_dto(element: _Element) -> CibConstraintOrderDto:
    return CibConstraintOrderDto(
        first_resource_id=str(element.attrib["first"]),
        then_resource_id=str(element.attrib["then"]),
        first_action=get_optional_value(
            PcmkAction, element.get("first-action")
        ),
        then_action=get_optional_value(PcmkAction, element.get("then-action")),
        first_resource_instance=get_optional_value(
            int, element.get("first-instance")
        ),
        then_resource_instance=get_optional_value(
            int, element.get("then-instance")
        ),
        attributes=_element_to_attributes_dto(element),
    )


def _set_constraint_el_to_dto(element: _Element) -> CibConstraintOrderSetDto:
    return CibConstraintOrderSetDto(
        resource_sets=constraint_element_to_resource_set_dto_list(element),
        attributes=_element_to_attributes_dto(element),
    )


def get_all_as_dtos(
    constraints_el: _Element,
) -> tuple[list[CibConstraintOrderDto], list[CibConstraintOrderSetDto]]:
    plain_list: list[CibConstraintOrderDto] = []
    set_list: list[CibConstraintOrderSetDto] = []
    for constraint_el in constraints_el.findall(f"./{TAG_NAME}"):
        if is_set_constraint(constraint_el):
            set_list.append(_set_constraint_el_to_dto(constraint_el))
        else:
            plain_list.append(_constraint_el_to_dto(constraint_el))
    return plain_list, set_list
