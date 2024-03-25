from unittest import TestCase

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    DATE_OP_GT,
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
from pcs.lib.cib.rule.validator import Validator

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ComplexExpressions(TestCase):
    def test_propagate_errors_from_subexpressions(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_OR,
                    [
                        BoolExpr(
                            BOOL_AND,
                            [
                                RscExpr(None, None, "Dummy"),
                                OpExpr("stop", None),
                            ],
                        ),
                        BoolExpr(
                            BOOL_AND,
                            [
                                DateUnaryExpr(DATE_OP_GT, "a date"),
                                NodeAttrExpr(
                                    NODE_ATTR_OP_EQ,
                                    "attr",
                                    "10",
                                    NODE_ATTR_TYPE_INTEGER,
                                ),
                            ],
                        ),
                    ],
                ),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="a date",
                    allowed_values="ISO 8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                    expression_type=CibRuleExpressionType.OP_EXPRESSION,
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                    expression_type=CibRuleExpressionType.RSC_EXPRESSION,
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                    expression_type=CibRuleExpressionType.EXPRESSION,
                ),
            ],
        )


class DisallowedRscOpExpressions(TestCase):
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
                self.rule_rsc,
                allow_rsc_expr=True,
                allow_op_expr=False,
            ).get_reports(),
            [],
        )

    def test_disallow_missing_rsc(self):
        assert_report_item_list_equal(
            Validator(
                self.rule_op,
                allow_rsc_expr=False,
                allow_op_expr=True,
            ).get_reports(),
            [],
        )


class DisallowedNodeAttrExpressions(TestCase):
    @staticmethod
    def fixture_expr_binary(operator):
        return BoolExpr(
            BOOL_AND,
            [
                RscExpr(None, None, "Dummy"),
                NodeAttrExpr(operator, "name", "10", NODE_ATTR_TYPE_INTEGER),
                OpExpr("stop", None),
            ],
        )

    @staticmethod
    def fixture_expr_unary(operator):
        return BoolExpr(
            BOOL_AND,
            [
                RscExpr(None, None, "Dummy"),
                NodeAttrExpr(operator, "name", None, None),
                OpExpr("stop", None),
            ],
        )

    @staticmethod
    def get_validator(rule):
        return Validator(
            rule,
            allow_rsc_expr=True,
            allow_op_expr=True,
            allow_node_attr_expr=False,
        )

    def test_binary_expr(self):
        operator_list = [
            NODE_ATTR_OP_EQ,
            NODE_ATTR_OP_NE,
            NODE_ATTR_OP_GTE,
            NODE_ATTR_OP_GT,
            NODE_ATTR_OP_LTE,
            NODE_ATTR_OP_LT,
        ]
        for operator in operator_list:
            with self.subTest(operator=operator):
                assert_report_item_list_equal(
                    self.get_validator(
                        self.fixture_expr_binary(operator)
                    ).get_reports(),
                    [
                        fixture.error(
                            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                            expression_type=CibRuleExpressionType.EXPRESSION,
                        ),
                    ],
                )

    def test_unary_expr(self):
        operator_list = [
            NODE_ATTR_OP_DEFINED,
            NODE_ATTR_OP_NOT_DEFINED,
        ]
        for operator in operator_list:
            with self.subTest(operator=operator):
                assert_report_item_list_equal(
                    self.get_validator(
                        self.fixture_expr_unary(operator)
                    ).get_reports(),
                    [
                        fixture.error(
                            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                            expression_type=CibRuleExpressionType.EXPRESSION,
                        ),
                    ],
                )


class DateUnaryExpression(TestCase):
    def test_date_ok(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateUnaryExpr(DATE_OP_GT, "2020-02-03")])
            ).get_reports(),
            [],
        )

    def test_date_bad(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateUnaryExpr(DATE_OP_GT, "a date")])
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="a date",
                    allowed_values="ISO 8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )


class DateInrangeExpression(TestCase):
    part_list = {
        "hours",
        "monthdays",
        "weekdays",
        "yearsdays",
        "months",
        "weeks",
        "years",
        "weekyears",
        "moon",
    }
    deprecation_reports = [
        fixture.deprecation(
            reports.codes.DEPRECATED_OPTION,
            option_name=option,
            replaced_by=[],
            option_type="duration",
        )
        for option in (
            "monthdays",
            "weekdays",
            "weekyears",
            "moon",
            "yearsdays",
        )
    ]

    def test_date_date_ok(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DateInRangeExpr("2020-01-01", "2020-02-01", None)],
                ),
            ).get_reports(),
            [],
        )

    def test_date_ok(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr(None, "2020-02-01", None)]),
            ).get_reports(),
            [],
        )

    def test_date_duration_ok(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [
                        DateInRangeExpr(
                            "2020-01-01T01:01:01+01:00",
                            None,
                            [(name, "3") for name in self.part_list],
                        )
                    ],
                ),
            ).get_reports(),
            [] + self.deprecation_reports,
        )

    def test_until_greater_than_since(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DateInRangeExpr("2020-02-01", "2020-01-01", None)],
                ),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_SINCE_GREATER_THAN_UNTIL,
                    since="2020-02-01",
                    until="2020-01-01",
                )
            ],
        )

    def test_dates_bad(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr("date1", "date2", None)]),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="date1",
                    allowed_values="ISO 8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="date2",
                    allowed_values="ISO 8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_duration_bad(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [
                        DateInRangeExpr(
                            "2020-01-01",
                            None,
                            [(name, "0") for name in self.part_list]
                            + [("hours", "foo"), ("bad", "something")],
                        )
                    ],
                ),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="hours",
                    option_value="foo",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="monthdays",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="months",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="moon",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weekdays",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weeks",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weekyears",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="years",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="yearsdays",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad"],
                    allowed=sorted(self.part_list),
                    option_type="duration",
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_OPTIONS_DUPLICATION,
                    duplicate_option_list=["hours"],
                ),
            ]
            + self.deprecation_reports,
        )


class DatespecExpression(TestCase):
    part_list = {
        "hours",
        "monthdays",
        "weekdays",
        "yearsdays",
        "months",
        "weeks",
        "years",
        "weekyears",
        "moon",
    }
    deprecation_reports = [
        fixture.deprecation(
            reports.codes.DEPRECATED_OPTION,
            option_name="yearsdays",
            replaced_by=[],
            option_type="datespec",
        ),
        fixture.deprecation(
            reports.codes.DEPRECATED_OPTION,
            option_name="moon",
            replaced_by=[],
            option_type="datespec",
        ),
    ]

    def test_ok(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "3") for name in self.part_list])],
                ),
            ).get_reports(),
            [] + self.deprecation_reports,
        )

    def test_range_ok(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "3-5") for name in self.part_list])],
                ),
            ).get_reports(),
            [] + self.deprecation_reports,
        )

    def test_bad_value(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "5-3") for name in self.part_list])],
                ),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="hours",
                    option_value="5-3",
                    allowed_values="0..23 or 0..22-1..23",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="monthdays",
                    option_value="5-3",
                    allowed_values="1..31 or 1..30-2..31",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="months",
                    option_value="5-3",
                    allowed_values="1..12 or 1..11-2..12",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="moon",
                    option_value="5-3",
                    allowed_values="0..7 or 0..6-1..7",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weekdays",
                    option_value="5-3",
                    allowed_values="1..7 or 1..6-2..7",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weeks",
                    option_value="5-3",
                    allowed_values="1..53 or 1..52-2..53",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="weekyears",
                    option_value="5-3",
                    allowed_values="an integer or integer-integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="years",
                    option_value="5-3",
                    allowed_values="an integer or integer-integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="yearsdays",
                    option_value="5-3",
                    allowed_values="1..366 or 1..365-2..366",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
            + self.deprecation_reports,
        )

    def test_bad_name(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DatespecExpr([("name", "5-3")])]),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["name"],
                    allowed=sorted(self.part_list),
                    option_type="datespec",
                    allowed_patterns=[],
                ),
            ],
        )

    def test_duplicate_names(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [
                        DatespecExpr(
                            [
                                ("hours", "10-12"),
                                ("weekdays", "6-7"),
                                ("hours", "13-14"),
                            ]
                        )
                    ],
                ),
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_OPTIONS_DUPLICATION,
                    duplicate_option_list=["hours"],
                ),
            ],
        )


class NodeAttrExpression(TestCase):
    @staticmethod
    def fixture_expr(type_, value):
        return BoolExpr(
            BOOL_AND, [NodeAttrExpr(NODE_ATTR_OP_EQ, "name", value, type_)]
        )

    def test_integer_ok(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_INTEGER, "16464"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [],
        )

    def test_integer_bad(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_INTEGER, "16464aa"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="integer attribute",
                    option_value="16464aa",
                    allowed_values="an integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_number_ok(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_NUMBER, "164.64"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [],
        )

    def test_number_bad(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_NUMBER, "164.64aa"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="number attribute",
                    option_value="164.64aa",
                    allowed_values="a floating-point number",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_version_ok(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_VERSION, "0.10.11"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [],
        )

    def test_version_bad(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_VERSION, "0.10.11c"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="version attribute",
                    option_value="0.10.11c",
                    allowed_values="a version number (e.g. 1, 1.2, 1.23.45, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_string(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_STRING, "a string 461.78"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [],
        )

    def test_no_type(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(None, "a string 461.78"),
                allow_node_attr_expr=True,
            ).get_reports(),
            [],
        )
