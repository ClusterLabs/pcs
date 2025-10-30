from unittest import TestCase

from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)
from pcs.lib.cib.rule import tools
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    NODE_ATTR_OP_EQ,
    BoolExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
)


class IsRscExpressionsOnly(TestCase):
    def test_rsc_expr(self):
        self.assertTrue(
            tools.is_rsc_expressions_only(RscExpr("ocf", None, None))
        )

    def test_rsc_expr_in_tree(self):
        self.assertTrue(
            tools.is_rsc_expressions_only(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                RscExpr("ocf", None, None),
                                RscExpr(None, None, "Dummy"),
                            ],
                        ),
                        RscExpr(None, "pacemaker", None),
                    ],
                )
            )
        )

    def test_no_rsc_expr(self):
        self.assertFalse(tools.is_rsc_expressions_only(OpExpr("monitor", None)))

    def test_no_rsc_expr_in_tree(self):
        self.assertFalse(
            tools.is_rsc_expressions_only(
                BoolExpr(
                    BOOL_AND,
                    [
                        OpExpr("monitor", None),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "foo", "bar", None),
                    ],
                ),
            )
        )

    def test_mixed(self):
        self.assertFalse(
            tools.is_rsc_expressions_only(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                RscExpr("ocf", None, None),
                                NodeAttrExpr(
                                    NODE_ATTR_OP_EQ, "foo", "bar", None
                                ),
                            ],
                        ),
                        RscExpr(None, "pacemaker", None),
                    ],
                )
            )
        )


class IsRscExpressionsOnlyDto(TestCase):
    dto_id = 0

    def fixture_dto(self, dto_type, children):
        self.dto_id += 1
        # dto is not complete and valid, it only contains parts which matter
        # for the tested functionality
        return CibRuleExpressionDto(
            f"id{self.dto_id}",
            dto_type,
            CibRuleInEffectStatus.UNKNOWN,
            dict(),
            None,
            None,
            children,
            "",
        )

    def test_rsc_expr(self):
        self.assertTrue(
            tools.is_rsc_expressions_only_dto(
                self.fixture_dto(CibRuleExpressionType.RSC_EXPRESSION, [])
            )
        )

    def test_rsc_expr_in_tree(self):
        self.assertTrue(
            tools.is_rsc_expressions_only_dto(
                self.fixture_dto(
                    CibRuleExpressionType.RULE,
                    [
                        self.fixture_dto(
                            CibRuleExpressionType.RULE,
                            [
                                self.fixture_dto(
                                    CibRuleExpressionType.RSC_EXPRESSION, []
                                ),
                                self.fixture_dto(
                                    CibRuleExpressionType.RSC_EXPRESSION, []
                                ),
                            ],
                        ),
                        self.fixture_dto(
                            CibRuleExpressionType.RSC_EXPRESSION, []
                        ),
                    ],
                )
            )
        )

    def test_no_rsc_expr(self):
        self.assertFalse(
            tools.is_rsc_expressions_only_dto(
                self.fixture_dto(CibRuleExpressionType.OP_EXPRESSION, [])
            )
        )

    def test_no_rsc_expr_in_tree(self):
        self.assertFalse(
            tools.is_rsc_expressions_only_dto(
                self.fixture_dto(
                    CibRuleExpressionType.RULE,
                    [
                        self.fixture_dto(
                            CibRuleExpressionType.OP_EXPRESSION, []
                        ),
                        self.fixture_dto(CibRuleExpressionType.EXPRESSION, []),
                    ],
                )
            )
        )

    def test_mixed(self):
        self.assertFalse(
            tools.is_rsc_expressions_only_dto(
                self.fixture_dto(
                    CibRuleExpressionType.RULE,
                    [
                        self.fixture_dto(
                            CibRuleExpressionType.RULE,
                            [
                                self.fixture_dto(
                                    CibRuleExpressionType.RSC_EXPRESSION, []
                                ),
                                self.fixture_dto(
                                    CibRuleExpressionType.EXPRESSION, []
                                ),
                            ],
                        ),
                        self.fixture_dto(
                            CibRuleExpressionType.RSC_EXPRESSION, []
                        ),
                    ],
                )
            )
        )
