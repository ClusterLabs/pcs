from unittest import mock, TestCase

from lxml import etree

from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.types import (
    CibRuleExpiredStatus,
    CibRuleExpressionType,
)
from pcs.lib.cib.rule import (
    fill_expired_flag_in_dto,
    rule_element_to_dto,
)


class ExpressionToDto(TestCase):
    def test_defined(self):
        xml = etree.fromstring(
            """
            <rule id="my-id">
                <expression id="my-id-expr"
                    attribute="pingd" operation="defined"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "my-id",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-expr",
                        CibRuleExpressionType.EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"attribute": "pingd", "operation": "defined"},
                        None,
                        None,
                        [],
                        "defined pingd",
                    ),
                ],
                "defined pingd",
            ),
        )

    def test_value_comparison(self):
        xml = etree.fromstring(
            """
            <rule id="my-id">
                <expression id="my-id-expr"
                    attribute="my-attr" operation="eq" value="my value"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "my-id",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-expr",
                        CibRuleExpressionType.EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {
                            "attribute": "my-attr",
                            "operation": "eq",
                            "value": "my value",
                        },
                        None,
                        None,
                        [],
                        'my-attr eq "my value"',
                    ),
                ],
                'my-attr eq "my value"',
            ),
        )

    def test_value_comparison_with_type(self):
        xml = etree.fromstring(
            """
            <rule id="my-id">
                <expression id="my-id-expr"
                    attribute="foo" operation="gt" type="version" value="1.2.3"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "my-id",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-expr",
                        CibRuleExpressionType.EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {
                            "attribute": "foo",
                            "operation": "gt",
                            "type": "version",
                            "value": "1.2.3",
                        },
                        None,
                        None,
                        [],
                        "foo gt version 1.2.3",
                    ),
                ],
                "foo gt version 1.2.3",
            ),
        )


class DateExpressionToDto(TestCase):
    def test_gt(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr"
                    operation="gt" start="2014-06-26"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"operation": "gt", "start": "2014-06-26"},
                        None,
                        None,
                        [],
                        "date gt 2014-06-26",
                    ),
                ],
                "date gt 2014-06-26",
            ),
        )

    def test_lt(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr"
                    operation="lt" end="2014-06-26"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"operation": "lt", "end": "2014-06-26"},
                        None,
                        None,
                        [],
                        "date lt 2014-06-26",
                    ),
                ],
                "date lt 2014-06-26",
            ),
        )

    def test_datespec(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr" operation="date_spec">
                    <date_spec id="rule-expr-datespec"
                        hours="1-14" monthdays="20-30" months="1"
                    />
                </date_expression>
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"operation": "date_spec"},
                        CibRuleDateCommonDto(
                            "rule-expr-datespec",
                            {
                                "hours": "1-14",
                                "monthdays": "20-30",
                                "months": "1",
                            },
                        ),
                        None,
                        [],
                        "date-spec hours=1-14 monthdays=20-30 months=1",
                    ),
                ],
                "date-spec hours=1-14 monthdays=20-30 months=1",
            ),
        )

    def test_inrange_start_end(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr"
                    operation="in_range" start="2014-06-26" end="2014-07-26"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {
                            "operation": "in_range",
                            "start": "2014-06-26",
                            "end": "2014-07-26",
                        },
                        None,
                        None,
                        [],
                        "date in_range 2014-06-26 to 2014-07-26",
                    ),
                ],
                "date in_range 2014-06-26 to 2014-07-26",
            ),
        )

    def test_inrange_end(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr"
                    operation="in_range" end="2014-07-26"
                />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"operation": "in_range", "end": "2014-07-26"},
                        None,
                        None,
                        [],
                        "date in_range to 2014-07-26",
                    ),
                ],
                "date in_range to 2014-07-26",
            ),
        )

    def test_inrange_start_duration(self):
        xml = etree.fromstring(
            """
            <rule id="rule">
                <date_expression id="rule-expr"
                    operation="in_range" start="2014-06-26"
                >
                    <duration id="rule-expr-duration" years="1"/>
                </date_expression>
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "rule",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "rule-expr",
                        CibRuleExpressionType.DATE_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"operation": "in_range", "start": "2014-06-26",},
                        None,
                        CibRuleDateCommonDto(
                            "rule-expr-duration", {"years": "1"},
                        ),
                        [],
                        "date in_range 2014-06-26 to duration years=1",
                    ),
                ],
                "date in_range 2014-06-26 to duration years=1",
            ),
        )


class OpExpressionToDto(TestCase):
    def test_minimal(self):
        xml = etree.fromstring(
            """
            <rule id="my-id">
                <op_expression id="my-id-op" name="start" />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "my-id",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-op",
                        CibRuleExpressionType.OP_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"name": "start"},
                        None,
                        None,
                        [],
                        "op start",
                    ),
                ],
                "op start",
            ),
        )

    def test_interval(self):
        xml = etree.fromstring(
            """
            <rule id="my-id">
                <op_expression id="my-id-op" name="start" interval="2min" />
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "my-id",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-op",
                        CibRuleExpressionType.OP_EXPRESSION,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"name": "start", "interval": "2min"},
                        None,
                        None,
                        [],
                        "op start interval=2min",
                    ),
                ],
                "op start interval=2min",
            ),
        )


class ResourceExpressionToDto(TestCase):
    def test_success(self):
        test_data = [
            # ((class, provider, type), output)
            ((None, None, None), "::"),
            (("ocf", None, None), "ocf::"),
            ((None, "pacemaker", None), ":pacemaker:"),
            ((None, None, "Dummy"), "::Dummy"),
            (("ocf", "pacemaker", None), "ocf:pacemaker:"),
            (("ocf", None, "Dummy"), "ocf::Dummy"),
            ((None, "pacemaker", "Dummy"), ":pacemaker:Dummy"),
            (("ocf", "pacemaker", "Dummy"), "ocf:pacemaker:Dummy"),
        ]
        for in_data, out_data in test_data:
            with self.subTest(in_data=in_data):
                attrs = {}
                if in_data[0] is not None:
                    attrs["class"] = in_data[0]
                if in_data[1] is not None:
                    attrs["provider"] = in_data[1]
                if in_data[2] is not None:
                    attrs["type"] = in_data[2]
                attrs_str = " ".join(
                    [f"{name}='{value}'" for name, value in attrs.items()]
                )
                xml = etree.fromstring(
                    f"""
                    <rule id="my-id">
                        <rsc_expression id="my-id-expr" {attrs_str}/>
                    </rule>
                """
                )
                self.assertEqual(
                    rule_element_to_dto(xml),
                    CibRuleExpressionDto(
                        "my-id",
                        CibRuleExpressionType.RULE,
                        CibRuleExpiredStatus.UNKNOWN,
                        {},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                "my-id-expr",
                                CibRuleExpressionType.RSC_EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                attrs,
                                None,
                                None,
                                [],
                                f"resource {out_data}",
                            ),
                        ],
                        f"resource {out_data}",
                    ),
                )


class RuleToDto(TestCase):
    def test_complex_rule(self):
        xml = etree.fromstring(
            """
            <rule id="complex" boolean-op="or" score="INFINITY">
                <rule id="complex-rule-1" boolean-op="and" score="0">
                    <date_expression id="complex-rule-1-expr"
                        operation="date_spec"
                    >
                        <date_spec id="complex-rule-1-expr-datespec"
                            weekdays="1-5" hours="12-23"
                        />
                    </date_expression>
                    <date_expression id="complex-rule-1-expr-1"
                        operation="in_range" start="2014-07-26"
                    >
                        <duration id="complex-rule-1-expr-1-durat" months="1"/>
                    </date_expression>
                </rule>
                <rule id="complex-rule" boolean-op="and" score="0">
                    <expression id="complex-rule-expr-1"
                        attribute="foo" operation="gt" type="version" value="1.2"
                    />
                    <expression id="complex-rule-expr"
                        attribute="#uname" operation="eq" value="node3 4"
                    />
                    <expression id="complex-rule-expr-2"
                        attribute="#uname" operation="eq" value="nodeA"
                    />
                </rule>
            </rule>
        """
        )
        self.assertEqual(
            rule_element_to_dto(xml),
            CibRuleExpressionDto(
                "complex",
                CibRuleExpressionType.RULE,
                CibRuleExpiredStatus.UNKNOWN,
                {"boolean-op": "or", "score": "INFINITY"},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "complex-rule-1",
                        CibRuleExpressionType.RULE,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"boolean-op": "and", "score": "0"},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                "complex-rule-1-expr",
                                CibRuleExpressionType.DATE_EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                {"operation": "date_spec"},
                                CibRuleDateCommonDto(
                                    "complex-rule-1-expr-datespec",
                                    {"hours": "12-23", "weekdays": "1-5"},
                                ),
                                None,
                                [],
                                "date-spec hours=12-23 weekdays=1-5",
                            ),
                            CibRuleExpressionDto(
                                "complex-rule-1-expr-1",
                                CibRuleExpressionType.DATE_EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                {
                                    "operation": "in_range",
                                    "start": "2014-07-26",
                                },
                                None,
                                CibRuleDateCommonDto(
                                    "complex-rule-1-expr-1-durat",
                                    {"months": "1"},
                                ),
                                [],
                                "date in_range 2014-07-26 to duration months=1",
                            ),
                        ],
                        "date-spec hours=12-23 weekdays=1-5 and date in_range "
                        "2014-07-26 to duration months=1",
                    ),
                    CibRuleExpressionDto(
                        "complex-rule",
                        CibRuleExpressionType.RULE,
                        CibRuleExpiredStatus.UNKNOWN,
                        {"boolean-op": "and", "score": "0"},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                "complex-rule-expr-1",
                                CibRuleExpressionType.EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                {
                                    "attribute": "foo",
                                    "operation": "gt",
                                    "type": "version",
                                    "value": "1.2",
                                },
                                None,
                                None,
                                [],
                                "foo gt version 1.2",
                            ),
                            CibRuleExpressionDto(
                                "complex-rule-expr",
                                CibRuleExpressionType.EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                {
                                    "attribute": "#uname",
                                    "operation": "eq",
                                    "value": "node3 4",
                                },
                                None,
                                None,
                                [],
                                '#uname eq "node3 4"',
                            ),
                            CibRuleExpressionDto(
                                "complex-rule-expr-2",
                                CibRuleExpressionType.EXPRESSION,
                                CibRuleExpiredStatus.UNKNOWN,
                                {
                                    "attribute": "#uname",
                                    "operation": "eq",
                                    "value": "nodeA",
                                },
                                None,
                                None,
                                [],
                                "#uname eq nodeA",
                            ),
                        ],
                        'foo gt version 1.2 and #uname eq "node3 4" and #uname '
                        "eq nodeA",
                    ),
                ],
                "(date-spec hours=12-23 weekdays=1-5 and date in_range "
                "2014-07-26 to duration months=1) or (foo gt version 1.2 and "
                '#uname eq "node3 4" and #uname eq nodeA)',
            ),
        )


@mock.patch("pcs.lib.cib.rule.cib_to_dto.get_rules_expired_status")
class FillExpiredFlagInDto(TestCase):
    def test_success(self, mock_rules_status):
        dto_in = CibRuleExpressionDto(
            "rule1",
            CibRuleExpressionType.RULE,
            CibRuleExpiredStatus.UNKNOWN,
            {"boolean-op": "or", "score": "INFINITY"},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule2",
                    CibRuleExpressionType.RULE,
                    CibRuleExpiredStatus.UNKNOWN,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "rule3",
                            CibRuleExpressionType.RULE,
                            CibRuleExpiredStatus.UNKNOWN,
                            {"boolean-op": "or", "score": "0"},
                            None,
                            None,
                            [
                                CibRuleExpressionDto(
                                    "id1",
                                    CibRuleExpressionType.OP_EXPRESSION,
                                    CibRuleExpiredStatus.UNKNOWN,
                                    {"name": "start"},
                                    None,
                                    None,
                                    [],
                                    "",
                                ),
                            ],
                            "",
                        ),
                        CibRuleExpressionDto(
                            "id2",
                            CibRuleExpressionType.RSC_EXPRESSION,
                            CibRuleExpiredStatus.UNKNOWN,
                            {"type": "Dummy"},
                            None,
                            None,
                            [],
                            "",
                        ),
                    ],
                    "",
                ),
                CibRuleExpressionDto(
                    "rule4",
                    CibRuleExpressionType.RULE,
                    CibRuleExpiredStatus.UNKNOWN,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "id3",
                            CibRuleExpressionType.RSC_EXPRESSION,
                            CibRuleExpiredStatus.UNKNOWN,
                            {"type": "Stateful"},
                            None,
                            None,
                            [],
                            "",
                        ),
                    ],
                    "",
                ),
            ],
            "",
        )

        dto_expected = CibRuleExpressionDto(
            "rule1",
            CibRuleExpressionType.RULE,
            CibRuleExpiredStatus.UNKNOWN,
            {"boolean-op": "or", "score": "INFINITY"},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule2",
                    CibRuleExpressionType.RULE,
                    CibRuleExpiredStatus.EXPIRED,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "rule3",
                            CibRuleExpressionType.RULE,
                            CibRuleExpiredStatus.IN_EFFECT,
                            {"boolean-op": "or", "score": "0"},
                            None,
                            None,
                            [
                                CibRuleExpressionDto(
                                    "id1",
                                    CibRuleExpressionType.OP_EXPRESSION,
                                    CibRuleExpiredStatus.UNKNOWN,
                                    {"name": "start"},
                                    None,
                                    None,
                                    [],
                                    "",
                                ),
                            ],
                            "",
                        ),
                        CibRuleExpressionDto(
                            "id2",
                            CibRuleExpressionType.RSC_EXPRESSION,
                            CibRuleExpiredStatus.UNKNOWN,
                            {"type": "Dummy"},
                            None,
                            None,
                            [],
                            "",
                        ),
                    ],
                    "",
                ),
                CibRuleExpressionDto(
                    "rule4",
                    CibRuleExpressionType.RULE,
                    CibRuleExpiredStatus.NOT_YET_IN_EFFECT,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "id3",
                            CibRuleExpressionType.RSC_EXPRESSION,
                            CibRuleExpiredStatus.UNKNOWN,
                            {"type": "Stateful"},
                            None,
                            None,
                            [],
                            "",
                        ),
                    ],
                    "",
                ),
            ],
            "",
        )

        rules_status = {
            "rule1": CibRuleExpiredStatus.UNKNOWN,
            "rule2": CibRuleExpiredStatus.EXPIRED,
            "rule3": CibRuleExpiredStatus.IN_EFFECT,
            "rule4": CibRuleExpiredStatus.NOT_YET_IN_EFFECT,
        }
        mock_rules_status.return_value = rules_status
        dto_out = fill_expired_flag_in_dto(
            "mock runner", etree.fromstring("<cib />"), dto_in
        )
        mock_rules_status.assert_called_once_with(
            "mock runner", "<cib/>", set(rules_status.keys())
        )
        self.assertEqual(dto_out, dto_expected)
