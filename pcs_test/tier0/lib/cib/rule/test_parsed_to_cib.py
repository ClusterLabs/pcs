from unittest import TestCase

from lxml import etree

from pcs.common.tools import Version
from pcs.lib.cib import rule
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    DATE_OP_GT,
    DATE_OP_LT,
    NODE_ATTR_OP_DEFINED,
    NODE_ATTR_OP_EQ,
    NODE_ATTR_OP_GT,
    NODE_ATTR_OP_GTE,
    NODE_ATTR_OP_LT,
    NODE_ATTR_OP_LTE,
    NODE_ATTR_OP_NE,
    NODE_ATTR_OP_NOT_DEFINED,
    NODE_ATTR_TYPE_INTEGER,
    NODE_ATTR_TYPE_NUMBER,
    NODE_ATTR_TYPE_STRING,
    NODE_ATTR_TYPE_VERSION,
    BoolExpr,
    DateInRangeExpr,
    DatespecExpr,
    DateUnaryExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
)
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.xml import etree_to_str


class Base(TestCase):
    @staticmethod
    def assert_cib(tree, expected_xml, schema_version=None):
        if schema_version is None:
            schema_version = Version(3, 5, 0)
        xml = etree.fromstring('<root id="X"/>')
        rule.rule_to_cib(xml, IdProvider(xml), schema_version, tree)
        assert_xml_equal(
            '<root id="X">' + expected_xml + "</root>", etree_to_str(xml)
        )


class SimpleBool(Base):
    def test_no_children(self):
        self.assert_cib(
            BoolExpr(BOOL_AND, []),
            """
                <rule id="X-rule" boolean-op="and" />
            """,
        )

    def test_one_child(self):
        self.assert_cib(
            BoolExpr(BOOL_AND, [OpExpr("start", None)]),
            """
                <rule id="X-rule" boolean-op="and">
                    <op_expression id="X-rule-op-start" name="start" />
                </rule>
            """,
        )

    def test_two_children(self):
        operators = [
            (BOOL_OR, "or"),
            (BOOL_AND, "and"),
        ]
        for op_in, op_out in operators:
            with self.subTest(op_in=op_in, op_out=op_out):
                self.assert_cib(
                    BoolExpr(
                        op_in,
                        [
                            OpExpr("start", None),
                            RscExpr("systemd", None, "pcsd"),
                        ],
                    ),
                    f"""
                        <rule id="X-rule" boolean-op="{op_out}">
                            <op_expression id="X-rule-op-start" name="start" />
                            <rsc_expression id="X-rule-rsc-systemd-pcsd"
                                class="systemd" type="pcsd"
                            />
                        </rule>
                    """,
                )


class SimpleNodeAttr(Base):
    def test_defined(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_DEFINED, "pingd", None, None),
            """
                <expression attribute="pingd" id="X-expr" operation="defined" />
            """,
        )

    def test_not_defined(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_NOT_DEFINED, "pingd", None, None),
            """
                <expression attribute="pingd" id="X-expr" operation="not_defined" />
            """,
        )

    def test_eq(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_EQ, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    value="node1"
                />
            """,
        )

    def test_ne(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_NE, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="ne"
                    value="node1"
                />
            """,
        )

    def test_gt(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_GT, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="gt"
                    value="node1"
                />
            """,
        )

    def test_gte(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_GTE, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="gte"
                    value="node1"
                />
            """,
        )

    def test_lt(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_LT, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="lt"
                    value="node1"
                />
            """,
        )

    def test_lte(self):
        self.assert_cib(
            NodeAttrExpr(NODE_ATTR_OP_LTE, "#uname", "node1", None),
            """
                <expression attribute="#uname" id="X-expr" operation="lte"
                    value="node1"
                />
            """,
        )

    def test_type_integer(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "12345", NODE_ATTR_TYPE_INTEGER
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="integer" value="12345"
                />
            """,
        )

    def test_type_integer_old_schema(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "12345", NODE_ATTR_TYPE_INTEGER
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="number" value="12345"
                />
            """,
            Version(3, 4, 0),
        )

    def test_type_number(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "12345", NODE_ATTR_TYPE_NUMBER
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="number" value="12345"
                />
            """,
        )

    def test_type_number_old_schema(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "12345", NODE_ATTR_TYPE_NUMBER
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="number" value="12345"
                />
            """,
            Version(3, 4, 0),
        )

    def test_type_string(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "node1", NODE_ATTR_TYPE_STRING
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="string" value="node1"
                />
            """,
        )

    def test_type_version(self):
        self.assert_cib(
            NodeAttrExpr(
                NODE_ATTR_OP_EQ, "#uname", "1.2.3", NODE_ATTR_TYPE_VERSION
            ),
            """
                <expression attribute="#uname" id="X-expr" operation="eq"
                    type="version" value="1.2.3"
                />
            """,
        )


class SimpleDatespec(Base):
    def test_1(self):
        self.assert_cib(
            DatespecExpr([("hours", "1")]),
            """
                <date_expression id="X-expr" operation="date_spec">
                    <date_spec id="X-expr-datespec" hours="1" />
                </date_expression>
            """,
        )

    def test_2(self):
        self.assert_cib(
            DatespecExpr(
                [("hours", "1-14"), ("monthdays", "20-30"), ("months", "1")]
            ),
            """
                <date_expression id="X-expr" operation="date_spec">
                    <date_spec id="X-expr-datespec"
                        hours="1-14" monthdays="20-30" months="1"
                    />
                </date_expression>
            """,
        )


class SimpleDate(Base):
    def test_gt(self):
        self.assert_cib(
            DateUnaryExpr(DATE_OP_GT, "2014-06-26"),
            """
                <date_expression id="X-expr" operation="gt" start="2014-06-26" />
            """,
        )

    def test_lt(self):
        self.assert_cib(
            DateUnaryExpr(DATE_OP_LT, "2014-06-26"),
            """
                <date_expression id="X-expr" operation="lt" end="2014-06-26" />
            """,
        )

    def test_inrange_start_end(self):
        self.assert_cib(
            DateInRangeExpr("2014-06-26", "2014-07-26", None),
            """
                <date_expression id="X-expr"
                    operation="in_range" start="2014-06-26" end="2014-07-26"
                />
            """,
        )

    def test_inrange_end(self):
        self.assert_cib(
            DateInRangeExpr(None, "2014-07-26", None),
            """
                <date_expression id="X-expr"
                    operation="in_range" end="2014-07-26"
                />
            """,
        )

    def test_inrange_start_duration(self):
        self.assert_cib(
            DateInRangeExpr("2014-06-26", None, [("years", "1")]),
            """
                <date_expression id="X-expr" operation="in_range" start="2014-06-26">
                    <duration id="X-expr-duration" years="1"/>
                </date_expression>
            """,
        )


class SimpleOp(Base):
    def test_minimal(self):
        self.assert_cib(
            OpExpr("start", None),
            """
                <op_expression id="X-op-start" name="start" />
            """,
        )

    def test_interval(self):
        self.assert_cib(
            OpExpr("monitor", "2min"),
            """
                <op_expression id="X-op-monitor" name="monitor"
                    interval="2min"
                />
            """,
        )


class SimpleRsc(Base):
    def test_class(self):
        self.assert_cib(
            RscExpr("ocf", None, None),
            """
                <rsc_expression id="X-rsc-ocf" class="ocf" />
            """,
        )

    def test_provider(self):
        self.assert_cib(
            RscExpr(None, "pacemaker", None),
            """
                <rsc_expression id="X-rsc-pacemaker" provider="pacemaker" />
            """,
        )

    def type(self):
        self.assert_cib(
            RscExpr(None, None, "Dummy"),
            """
                <rsc_expression id="X-rsc-Dummy" type="Dummy" />
            """,
        )

    def test_provider_type(self):
        self.assert_cib(
            RscExpr(None, "pacemaker", "Dummy"),
            """
                <rsc_expression id="X-rsc-pacemaker-Dummy"
                    provider="pacemaker" type="Dummy"
                />
            """,
        )

    def test_class_provider(self):
        self.assert_cib(
            RscExpr("ocf", "pacemaker", None),
            """
                <rsc_expression id="X-rsc-ocf-pacemaker"
                    class="ocf" provider="pacemaker"
                />
            """,
        )

    def test_class_type(self):
        self.assert_cib(
            RscExpr("systemd", None, "pcsd"),
            """
                <rsc_expression id="X-rsc-systemd-pcsd"
                    class="systemd" type="pcsd"
                />
            """,
        )

    def test_class_provider_type(self):
        self.assert_cib(
            RscExpr("ocf", "pacemaker", "Dummy"),
            """
                <rsc_expression id="X-rsc-ocf-pacemaker-Dummy"
                    class="ocf" provider="pacemaker" type="Dummy"
                />
            """,
        )


class Complex(Base):
    def test_expr_1(self):
        self.assert_cib(
            BoolExpr(
                BOOL_AND,
                [
                    BoolExpr(
                        BOOL_OR,
                        [
                            RscExpr("ocf", "pacemaker", "Dummy"),
                            OpExpr("start", None),
                            RscExpr("systemd", None, "pcsd"),
                            RscExpr("ocf", "heartbeat", "Dummy"),
                        ],
                    ),
                    BoolExpr(
                        BOOL_OR,
                        [
                            OpExpr("monitor", "30s"),
                            RscExpr("ocf", "pacemaker", "Dummy"),
                            OpExpr("start", None),
                            OpExpr("monitor", "2min"),
                        ],
                    ),
                ],
            ),
            """
                <rule id="X-rule" boolean-op="and">
                  <rule id="X-rule-rule" boolean-op="or" score="0">
                    <rsc_expression id="X-rule-rule-rsc-ocf-pacemaker-Dummy"
                        class="ocf" provider="pacemaker" type="Dummy"
                    />
                    <op_expression id="X-rule-rule-op-start" name="start" />
                    <rsc_expression id="X-rule-rule-rsc-systemd-pcsd"
                        class="systemd" type="pcsd"
                    />
                    <rsc_expression id="X-rule-rule-rsc-ocf-heartbeat-Dummy"
                        class="ocf" provider="heartbeat" type="Dummy"
                    />
                  </rule>
                  <rule id="X-rule-rule-1" boolean-op="or" score="0">
                    <op_expression id="X-rule-rule-1-op-monitor"
                        name="monitor" interval="30s"
                    />
                    <rsc_expression id="X-rule-rule-1-rsc-ocf-pacemaker-Dummy"
                        class="ocf" provider="pacemaker" type="Dummy"
                    />
                    <op_expression id="X-rule-rule-1-op-start" name="start" />
                    <op_expression id="X-rule-rule-1-op-monitor-1"
                        name="monitor" interval="2min"
                    />
                  </rule>
                </rule>
            """,
        )
