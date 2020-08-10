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
)
from pcs.lib.cib.tools import IdProvider


class Base(TestCase):
    @staticmethod
    def assert_cib(tree, expected_xml):
        xml = etree.fromstring('<root id="X"/>')
        rule.rule_to_cib(xml, IdProvider(xml), tree)
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
                            <rsc_expression id="X-rule-rsc-systemd-pcsd"
                                class="systemd" type="pcsd"
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
                <rule id="X-rule" boolean-op="and" score="INFINITY">
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
