from unittest import TestCase

from lxml import etree

from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.xml import etree_to_str

from pcs.lib.cib import rule
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    BoolExpr,
    OpExpr,
    RscExpr,
    RuleExprPart,
)
from pcs.lib.cib.tools import IdProvider


class Base(TestCase):
    @staticmethod
    def assert_cib(tree, expected_xml):
        xml = etree.fromstring('<root id="X"/>')
        rule.build_cib(xml, tree, IdProvider(xml))
        assert_xml_equal(
            '<root id="X">' + expected_xml + "</root>", etree_to_str(xml)
        )


class SimpleBool(Base):
    def test_no_children(self):
        self.assert_cib(
            BoolExpr(BOOL_AND, []),
            """
                <rule id="X-rule" boolean-op="and" score="INFINITY" />
            """,
        )

    def test_one_child(self):
        self.assert_cib(
            BoolExpr(BOOL_AND, [OpExpr("start", None)]),
            """
                <rule id="X-rule" boolean-op="and" score="INFINITY">
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
                        <rule id="X-rule" boolean-op="{op_out}" score="INFINITY">
                            <op_expression id="X-rule-op-start" name="start" />
                            <rsc_expression id="X-rule-rsc-pcsd" class="systemd"
                                type="pcsd"
                            />
                        </rule>
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
    def test_2_part(self):
        self.assert_cib(
            RscExpr("systemd", None, "pcsd"),
            """
                <rsc_expression id="X-rsc-pcsd" class="systemd" type="pcsd" />
            """,
        )

    def test_3_part(self):
        self.assert_cib(
            RscExpr("ocf", "pacemaker", "Dummy"),
            """
                <rsc_expression id="X-rsc-Dummy" class="ocf"
                    provider="pacemaker" type="Dummy"
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
                <rule id="X-rule" boolean-op="and" score="INFINITY">
                  <rule id="X-rule-rule" boolean-op="or">
                    <rsc_expression id="X-rule-rule-rsc-Dummy"
                        class="ocf" provider="pacemaker" type="Dummy"
                    />
                    <op_expression id="X-rule-rule-op-start" name="start" />
                    <rsc_expression id="X-rule-rule-rsc-pcsd"
                        class="systemd" type="pcsd"
                    />
                    <rsc_expression id="X-rule-rule-rsc-Dummy-1"
                        class="ocf" provider="heartbeat" type="Dummy"
                    />
                  </rule>
                  <rule id="X-rule-rule-1" boolean-op="or">
                    <op_expression id="X-rule-rule-1-op-monitor"
                        name="monitor" interval="30s"
                    />
                    <rsc_expression id="X-rule-rule-1-rsc-Dummy"
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
