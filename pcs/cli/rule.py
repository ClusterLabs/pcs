from typing import List

from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.str_tools import (
    format_name_value_list,
    indent,
)
from pcs.common.types import (
    CibRuleExpiredStatus,
    CibRuleExpressionType,
)

_expired_label_map = {
    CibRuleExpiredStatus.NOT_YET_IN_EFFECT: "not yet in effect",
    CibRuleExpiredStatus.IN_EFFECT: None,
    CibRuleExpiredStatus.EXPIRED: "expired",
}


def rule_expression_dto_to_lines(
    rule_expr: CibRuleExpressionDto, with_ids: bool = False
) -> List[str]:
    if rule_expr.type == CibRuleExpressionType.RULE:
        return _rule_dto_to_lines(rule_expr, with_ids)
    if rule_expr.type == CibRuleExpressionType.DATE_EXPRESSION:
        return _date_dto_to_lines(rule_expr, with_ids)
    return _simple_expr_to_lines(rule_expr, with_ids)


def _rule_dto_to_lines(
    rule_expr: CibRuleExpressionDto, with_ids: bool = False
) -> List[str]:
    expired_label = _expired_label_map.get(rule_expr.expired, None)
    heading_parts = [
        "Rule{0}:".format(f" ({expired_label})" if expired_label else "")
    ]
    heading_parts.extend(
        format_name_value_list(sorted(rule_expr.options.items()))
    )
    if with_ids:
        heading_parts.append(f"(id:{rule_expr.id})")

    lines = []
    for child in rule_expr.expressions:
        lines.extend(rule_expression_dto_to_lines(child, with_ids))

    return [" ".join(heading_parts)] + indent(lines)


def _date_dto_to_lines(
    rule_expr: CibRuleExpressionDto, with_ids: bool = False
) -> List[str]:
    # pylint: disable=too-many-branches
    operation = rule_expr.options.get("operation", None)

    if operation == "date_spec":
        heading_parts = ["Expression:"]
        if with_ids:
            heading_parts.append(f"(id:{rule_expr.id})")
        line_parts = ["Date Spec:"]
        if rule_expr.date_spec:
            line_parts.extend(
                format_name_value_list(
                    sorted(rule_expr.date_spec.options.items())
                )
            )
            if with_ids:
                line_parts.append(f"(id:{rule_expr.date_spec.id})")
        return [" ".join(heading_parts)] + indent([" ".join(line_parts)])

    if operation == "in_range" and rule_expr.duration:
        heading_parts = ["Expression:", "date", "in_range"]
        if "start" in rule_expr.options:
            heading_parts.append(rule_expr.options["start"])
        heading_parts.extend(["to", "duration"])
        if with_ids:
            heading_parts.append(f"(id:{rule_expr.id})")
        lines = [" ".join(heading_parts)]

        line_parts = ["Duration:"]
        line_parts.extend(
            format_name_value_list(sorted(rule_expr.duration.options.items()))
        )
        if with_ids:
            line_parts.append(f"(id:{rule_expr.duration.id})")
        lines.extend(indent([" ".join(line_parts)]))

        return lines

    return _simple_expr_to_lines(rule_expr, with_ids=with_ids)


def _simple_expr_to_lines(
    rule_expr: CibRuleExpressionDto, with_ids: bool = False
) -> List[str]:
    parts = ["Expression:", rule_expr.as_string]
    if with_ids:
        parts.append(f"(id:{rule_expr.id})")
    return [" ".join(parts)]
