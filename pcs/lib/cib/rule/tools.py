from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import CibRuleExpressionType

from .expression_part import BoolExpr, RscExpr, RuleExprPart


def is_rsc_expressions_only(rule_expr: RuleExprPart) -> bool:
    if isinstance(rule_expr, RscExpr):
        return True
    if isinstance(rule_expr, BoolExpr):
        return all(
            is_rsc_expressions_only(child) for child in rule_expr.children
        )
    return False


def is_rsc_expressions_only_dto(rule_dto: CibRuleExpressionDto) -> bool:
    if rule_dto.type == CibRuleExpressionType.RSC_EXPRESSION:
        return True
    if rule_dto.type == CibRuleExpressionType.RULE:
        return all(
            is_rsc_expressions_only_dto(child) for child in rule_dto.expressions
        )
    return False
