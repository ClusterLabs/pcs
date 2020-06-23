from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    BoolExpr,
    OpExpr,
    RscExpr,
)
from pcs.lib.cib.rule.validator import Validator


class ValidatorTest(TestCase):
    def setUp(self):
        self.report_op = fixture.error(
            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
            expression_type=CibRuleExpressionType.OP_EXPRESSION,
        )
        self.report_rsc = fixture.error(
            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
            expression_type=CibRuleExpressionType.RSC_EXPRESSION,
        )
        self.rule_rsc = BoolExpr(
            BOOL_OR, [RscExpr(None, None, "a"), RscExpr(None, None, "b")]
        )
        self.rule_op = BoolExpr(
            BOOL_OR, [OpExpr("start", None), OpExpr("stop", None)]
        )
        self.rule = BoolExpr(BOOL_AND, [self.rule_rsc, self.rule_op])

    def test_complex_rule(self):
        test_data = (
            (True, True, []),
            (True, False, [self.report_rsc]),
            (False, True, [self.report_op]),
            (False, False, [self.report_rsc, self.report_op]),
        )
        for op_allowed, rsc_allowed, report_list in test_data:
            with self.subTest(op_allowed=op_allowed, rsc_allowed=rsc_allowed):
                assert_report_item_list_equal(
                    Validator(
                        self.rule,
                        allow_rsc_expr=rsc_allowed,
                        allow_op_expr=op_allowed,
                    ).get_reports(),
                    report_list,
                )

    def test_disallow_missing_op(self):
        assert_report_item_list_equal(
            Validator(
                self.rule_rsc, allow_rsc_expr=True, allow_op_expr=False
            ).get_reports(),
            [],
        )

    def test_disallow_missing_rsc(self):
        assert_report_item_list_equal(
            Validator(
                self.rule_op, allow_rsc_expr=False, allow_op_expr=True
            ).get_reports(),
            [],
        )
