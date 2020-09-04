from typing import cast

from lxml.etree import _Element

from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.types import (
    CibRuleInEffectStatus,
    CibRuleExpressionType,
)
from pcs.lib.xml_tools import export_attributes

from .in_effect import RuleInEffectEval
from .cib_to_str import RuleToStr


def rule_element_to_dto(
    in_effect_eval: RuleInEffectEval, rule_el: _Element
) -> CibRuleExpressionDto:
    """
    Export a rule xml element including its children to their DTOs

    in_effect_eval -- a class for evaluating if a rule is in effect
    rule_el -- the rule to be converted to DTO
    """
    return _Exporter(in_effect_eval, RuleToStr()).export(rule_el)


class _Exporter:
    _tag_to_type = {
        "rule": CibRuleExpressionType.RULE,
        "expression": CibRuleExpressionType.EXPRESSION,
        "date_expression": CibRuleExpressionType.DATE_EXPRESSION,
        "op_expression": CibRuleExpressionType.OP_EXPRESSION,
        "rsc_expression": CibRuleExpressionType.RSC_EXPRESSION,
    }

    def __init__(self, in_effect_eval: RuleInEffectEval, str_eval: RuleToStr):
        self._in_effect_eval = in_effect_eval
        self._str_eval = str_eval

    def export(self, rule_el: _Element) -> CibRuleExpressionDto:
        return self._tag_to_export[str(rule_el.tag)](self, rule_el)

    def _rule_to_dto(self, rule_el: _Element) -> CibRuleExpressionDto:
        children_dto_list = [
            self._tag_to_export[str(child.tag)](self, child)
            # The xpath method has a complicated return value, but we know our
            # xpath expression only returns elements.
            for child in cast(_Element, rule_el.xpath(self._xpath_for_export))
        ]
        rule_id = str(rule_el.get("id", ""))
        return CibRuleExpressionDto(
            rule_id,
            self._tag_to_type[str(rule_el.tag)],
            self._in_effect_eval.get_rule_status(rule_id),
            export_attributes(rule_el, with_id=False),
            None,
            None,
            children_dto_list,
            self._str_eval.get_str(rule_el),
        )

    def _common_expr_to_dto(self, expr_el: _Element) -> CibRuleExpressionDto:
        return CibRuleExpressionDto(
            str(expr_el.get("id", "")),
            self._tag_to_type[str(expr_el.tag)],
            CibRuleInEffectStatus.UNKNOWN,
            export_attributes(expr_el, with_id=False),
            None,
            None,
            [],
            self._str_eval.get_str(expr_el),
        )

    @staticmethod
    def _date_common_to_dto(expr_el: _Element) -> CibRuleDateCommonDto:
        return CibRuleDateCommonDto(
            str(expr_el.get("id", "")),
            export_attributes(expr_el, with_id=False),
        )

    def _date_expr_to_dto(self, expr_el: _Element) -> CibRuleExpressionDto:
        date_spec = expr_el.find("./date_spec")
        duration = expr_el.find("./duration")
        return CibRuleExpressionDto(
            str(expr_el.get("id", "")),
            self._tag_to_type[str(expr_el.tag)],
            CibRuleInEffectStatus.UNKNOWN,
            export_attributes(expr_el, with_id=False),
            None if date_spec is None else self._date_common_to_dto(date_spec),
            None if duration is None else self._date_common_to_dto(duration),
            [],
            self._str_eval.get_str(expr_el),
        )

    _tag_to_export = {
        "rule": _rule_to_dto,
        "expression": _common_expr_to_dto,
        "date_expression": _date_expr_to_dto,
        "op_expression": _common_expr_to_dto,
        "rsc_expression": _common_expr_to_dto,
    }

    _xpath_for_export = "./*[{export_tags}]".format(
        export_tags=" or ".join(f"self::{tag}" for tag in _tag_to_export)
    )
