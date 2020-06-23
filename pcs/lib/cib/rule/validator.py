from typing import Set

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType

from .expression_part import (
    BoolExpr,
    OpExpr,
    RscExpr,
)


class Validator:
    # TODO For now we only check allowed expressions. Other checks and
    # validations can be added if needed.
    def __init__(
        self,
        parsed_rule: BoolExpr,
        allow_rsc_expr: bool = False,
        allow_op_expr: bool = False,
    ):
        """
        parsed_rule -- a rule to be validated
        allow_op_expr -- are op expressions allowed in the rule?
        allow_rsc_expr -- are resource expressions allowed in the rule?
        """
        self._rule = parsed_rule
        self._allow_op_expr = allow_op_expr
        self._allow_rsc_expr = allow_rsc_expr
        self._disallowed_expr_list: Set[CibRuleExpressionType] = set()

        self._method_map = {
            BoolExpr: self._validate_bool_expr,
            OpExpr: self._validate_op_expr,
            RscExpr: self._validate_rsc_expr,
        }

    def get_reports(self) -> reports.ReportItemList:
        self._method_map[type(self._rule)](self._rule)
        report_list = []
        for expr_type in self._disallowed_expr_list:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.RuleExpressionNotAllowed(expr_type)
                )
            )
        return report_list

    def _validate_bool_expr(self, expr: BoolExpr):
        for child in expr.children:
            if type(child) in self._method_map:
                self._method_map[type(child)](child)

    def _validate_op_expr(self, expr):
        del expr
        if not self._allow_op_expr:
            self._disallowed_expr_list.add(CibRuleExpressionType.OP_EXPRESSION)

    def _validate_rsc_expr(self, expr):
        del expr
        if not self._allow_rsc_expr:
            self._disallowed_expr_list.add(CibRuleExpressionType.RSC_EXPRESSION)
