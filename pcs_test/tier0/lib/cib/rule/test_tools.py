from unittest import TestCase

from pcs.lib.cib.rule import tools
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    NODE_ATTR_OP_EQ,
    NODE_ATTR_TYPE_INTEGER,
    NODE_ATTR_TYPE_NUMBER,
    BoolExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
)


class HasNodeAttrExprWithTypeInteger(TestCase):
    @staticmethod
    def fixture_rule(attr_type):
        return BoolExpr(
            BOOL_OR,
            [
                BoolExpr(
                    BOOL_AND,
                    [
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "A", None),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "B", attr_type),
                    ],
                ),
                BoolExpr(
                    BOOL_AND,
                    [
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "aa", None),
                        RscExpr("ocf", "pacemaker", "Dummy"),
                    ],
                ),
                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "1", None),
                OpExpr("stop", None),
            ],
        )

    def test_node_attr_no_type(self):
        self.assertFalse(
            tools.has_node_attr_expr_with_type_integer(self.fixture_rule(None))
        )

    def test_node_attr_no_integer(self):
        self.assertFalse(
            tools.has_node_attr_expr_with_type_integer(
                self.fixture_rule(NODE_ATTR_TYPE_NUMBER)
            )
        )

    def test_node_attr_integer(self):
        self.assertTrue(
            tools.has_node_attr_expr_with_type_integer(
                self.fixture_rule(NODE_ATTR_TYPE_INTEGER)
            )
        )

    def test_no_node_attr(self):
        self.assertFalse(
            tools.has_node_attr_expr_with_type_integer(
                BoolExpr(
                    BOOL_OR,
                    [
                        RscExpr("ocf", "pacemaker", "Dummy"),
                        OpExpr("stop", None),
                    ],
                )
            )
        )


class HasRscOrOpExpression(TestCase):
    def test_no_rsc_op(self):
        self.assertFalse(
            tools.has_rsc_or_op_expression(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "A", None),
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "B", None),
                            ],
                        ),
                        BoolExpr(
                            BOOL_AND,
                            [
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "aa", None),
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "bb", None),
                            ],
                        ),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "1", None),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "2", None),
                    ],
                )
            )
        )

    def test_rsc_on_top(self):
        self.assertTrue(
            tools.has_rsc_or_op_expression(RscExpr("ocf", "pacemaker", "Dummy"))
        )

    def test_op_on_top(self):
        self.assertTrue(tools.has_rsc_or_op_expression(OpExpr("stop", None)))

    def test_rsc_present(self):
        self.assertTrue(
            tools.has_rsc_or_op_expression(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "A", None),
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "B", None),
                            ],
                        ),
                        BoolExpr(
                            BOOL_AND,
                            [
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "aa", None),
                                RscExpr("ocf", "pacemaker", "Dummy"),
                            ],
                        ),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "1", None),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "2", None),
                    ],
                )
            )
        )

    def test_op_present(self):
        self.assertTrue(
            tools.has_rsc_or_op_expression(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "A", None),
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "B", None),
                            ],
                        ),
                        BoolExpr(
                            BOOL_AND,
                            [
                                OpExpr("stop", None),
                                NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "bb", None),
                            ],
                        ),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "a", "1", None),
                        NodeAttrExpr(NODE_ATTR_OP_EQ, "b", "2", None),
                    ],
                )
            )
        )
