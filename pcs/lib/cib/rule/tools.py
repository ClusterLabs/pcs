from .expression_part import (
    BoolExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)


def has_rsc_or_op_expression(rule_expr: RuleExprPart) -> bool:
    if isinstance(rule_expr, OpExpr):
        return True
    if isinstance(rule_expr, RscExpr):
        return True
    if isinstance(rule_expr, BoolExpr):
        return any(
            has_rsc_or_op_expression(child) for child in rule_expr.children
        )
    return False
