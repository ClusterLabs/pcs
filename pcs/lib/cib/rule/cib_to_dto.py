from typing import (
    cast,
    Set,
)

import dataclasses
from lxml.etree import _Element

from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.str_tools import (
    format_name_value_list,
    quote,
)
from pcs.common.types import (
    CibRuleExpiredStatus,
    CibRuleExpressionType,
)
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.live import get_rules_expired_status
from pcs.lib.xml_tools import (
    etree_to_str,
    export_attributes,
)


def rule_element_to_dto(rule_el: _Element) -> CibRuleExpressionDto:
    """
    Export a rule xml element including its children to their DTOs
    """
    return _tag_to_export[str(rule_el.tag)](rule_el)


def fill_expired_flag_in_dto(
    runner: CommandRunner, cib: _Element, rule_dto: CibRuleExpressionDto
) -> CibRuleExpressionDto:
    """
    Fill 'expired' flag in rule DTOs and return the new updated DTOs

    runner -- a class for running external processes
    cib -- cib containing the rule expressions
    rule_dto -- the rule DTO to be filled
    """
    id_to_expired_map = get_rules_expired_status(
        runner, etree_to_str(cib), _extract_rule_ids_from_dto(rule_dto)
    )

    def setter(rule_dto: CibRuleExpressionDto) -> CibRuleExpressionDto:
        if rule_dto.type != CibRuleExpressionType.RULE:
            return rule_dto
        new_children = [setter(child) for child in rule_dto.expressions]
        new_expired = id_to_expired_map.get(
            rule_dto.id, CibRuleExpiredStatus.UNKNOWN
        )
        return dataclasses.replace(
            rule_dto, expired=new_expired, expressions=new_children
        )

    return setter(rule_dto)


def _extract_rule_ids_from_dto(rule_dto: CibRuleExpressionDto) -> Set[str]:
    id_set = set()
    if rule_dto.type == CibRuleExpressionType.RULE:
        id_set.add(rule_dto.id)
        for child in rule_dto.expressions:
            id_set = id_set.union(_extract_rule_ids_from_dto(child))
    return id_set


def _attrs_to_str(el: _Element) -> str:
    return " ".join(
        format_name_value_list(
            sorted(export_attributes(el, with_id=False).items())
        )
    )


def _rule_to_dto(rule_el: _Element) -> CibRuleExpressionDto:
    children_dto_list = [
        _tag_to_export[str(child.tag)](child)
        # The xpath method has a complicated return value, but we know our xpath
        # expression only returns elements.
        for child in cast(_Element, rule_el.xpath(_xpath_for_export))
    ]
    # "and" is a documented pacemaker default
    # https://clusterlabs.org/pacemaker/doc/en-US/Pacemaker/2.0/html-single/Pacemaker_Explained/index.html#_rule_properties
    boolean_op = str(rule_el.get("boolean-op", "and"))
    string_parts = []
    for child_dto in children_dto_list:
        if child_dto.type == CibRuleExpressionType.RULE:
            string_parts.append(f"({child_dto.as_string})")
        else:
            string_parts.append(child_dto.as_string)
    return CibRuleExpressionDto(
        str(rule_el.get("id", "")),
        _tag_to_type[str(rule_el.tag)],
        CibRuleExpiredStatus.UNKNOWN,
        export_attributes(rule_el, with_id=False),
        None,
        None,
        children_dto_list,
        f" {boolean_op} ".join(string_parts),
    )


def _common_expr_to_dto(
    expr_el: _Element, as_string: str
) -> CibRuleExpressionDto:
    return CibRuleExpressionDto(
        str(expr_el.get("id", "")),
        _tag_to_type[str(expr_el.tag)],
        CibRuleExpiredStatus.UNKNOWN,
        export_attributes(expr_el, with_id=False),
        None,
        None,
        [],
        as_string,
    )


def _simple_expr_to_dto(expr_el: _Element) -> CibRuleExpressionDto:
    string_parts = []
    if "value" in expr_el.attrib:
        # "attribute" and "operation" are defined as mandatory in CIB schema
        string_parts.extend(
            [
                str(expr_el.get("attribute", "")),
                str(expr_el.get("operation", "")),
            ]
        )
        if "type" in expr_el.attrib:
            # CIB schema defines "number", pacemaker code treats its values as
            # integers, Pacemaker Explained uses "integer" instead of "number"
            # and that's how it has been implemented in pcs rule parser.
            # Therefore we must export it the same way so that the string is
            # parsable by pcs.
            # There is an ongoing discussion to resolve this inconsistency. For
            # now, we stick with what pcs has been doing so far: use the
            # keyword "integer", validate values to be integers, save them to
            # attribute "number".
            type_ = str(expr_el.get("type", ""))
            if type_ == "number":
                type_ = "integer"
            string_parts.append(type_)
        string_parts.append(quote(str(expr_el.get("value", "")), " "))
    else:
        # "attribute" and "operation" are defined as mandatory in CIB schema
        string_parts.extend(
            [
                str(expr_el.get("operation", "")),
                str(expr_el.get("attribute", "")),
            ]
        )
    return _common_expr_to_dto(expr_el, " ".join(string_parts))


def _date_common_to_dto(expr_el: _Element) -> CibRuleDateCommonDto:
    return CibRuleDateCommonDto(
        str(expr_el.get("id", "")), export_attributes(expr_el, with_id=False),
    )


def _date_expr_to_dto(expr_el: _Element) -> CibRuleExpressionDto:
    date_spec = expr_el.find("./date_spec")
    duration = expr_el.find("./duration")

    string_parts = []
    # "operation" is defined as mandatory in CIB schema
    operation = expr_el.get("operation", "")
    if operation == "date_spec":
        string_parts.append("date-spec")
        if date_spec is not None:
            string_parts.append(_attrs_to_str(date_spec))
    elif operation == "in_range":
        string_parts.extend(["date", "in_range"])
        # CIB schema allows "start" + "duration" or optional "start" + "end"
        if "start" in expr_el.attrib:
            string_parts.append(str(expr_el.get("start", "")))
        string_parts.append("to")
        if "end" in expr_el.attrib:
            string_parts.append(str(expr_el.get("end", "")))
        if duration is not None:
            string_parts.append("duration")
            string_parts.append(_attrs_to_str(duration))
    else:
        # CIB schema allows operation=="gt" + "start" or operation=="lt" + "end"
        string_parts.extend(["date", str(expr_el.get("operation", ""))])
        if "start" in expr_el.attrib:
            string_parts.append(str(expr_el.get("start", "")))
        if "end" in expr_el.attrib:
            string_parts.append(str(expr_el.get("end", "")))

    return CibRuleExpressionDto(
        str(expr_el.get("id", "")),
        _tag_to_type[str(expr_el.tag)],
        CibRuleExpiredStatus.UNKNOWN,
        export_attributes(expr_el, with_id=False),
        None if date_spec is None else _date_common_to_dto(date_spec),
        None if duration is None else _date_common_to_dto(duration),
        [],
        " ".join(string_parts),
    )


def _op_expr_to_dto(expr_el: _Element) -> CibRuleExpressionDto:
    string_parts = ["op"]
    string_parts.append(str(expr_el.get("name", "")))
    if "interval" in expr_el.attrib:
        string_parts.append(
            "interval={interval}".format(interval=expr_el.get("interval", ""))
        )
    return _common_expr_to_dto(expr_el, " ".join(string_parts))


def _rsc_expr_to_dto(expr_el: _Element) -> CibRuleExpressionDto:
    return _common_expr_to_dto(
        expr_el,
        (
            "resource "
            + ":".join(
                [
                    str(expr_el.get(attr, ""))
                    for attr in ["class", "provider", "type"]
                ]
            )
        ),
    )


_tag_to_type = {
    "rule": CibRuleExpressionType.RULE,
    "expression": CibRuleExpressionType.EXPRESSION,
    "date_expression": CibRuleExpressionType.DATE_EXPRESSION,
    "op_expression": CibRuleExpressionType.OP_EXPRESSION,
    "rsc_expression": CibRuleExpressionType.RSC_EXPRESSION,
}

_tag_to_export = {
    "rule": _rule_to_dto,
    "expression": _simple_expr_to_dto,
    "date_expression": _date_expr_to_dto,
    "op_expression": _op_expr_to_dto,
    "rsc_expression": _rsc_expr_to_dto,
}
_xpath_for_export = "./*[{export_tags}]".format(
    export_tags=" or ".join(f"self::{tag}" for tag in _tag_to_export)
)
