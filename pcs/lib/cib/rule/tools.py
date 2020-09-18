from .expression_part import (
    NODE_ATTR_TYPE_INTEGER,
    BoolExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)


def has_node_attr_expr_with_type_integer(rule_expr: RuleExprPart) -> bool:
    if (
        isinstance(rule_expr, NodeAttrExpr)
        and rule_expr.attr_type == NODE_ATTR_TYPE_INTEGER
    ):
        return True
    if isinstance(rule_expr, BoolExpr):
        return any(
            has_node_attr_expr_with_type_integer(child)
            for child in rule_expr.children
        )
    return False


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
