from unittest import mock, TestCase

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import reports
from pcs.common.types import CibRuleExpressionType
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    DATE_OP_GT,
    NODE_ATTR_OP_EQ,
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
from pcs.lib.external import CommandRunner


class ComplexExpressions(TestCase):
    def test_propagate_errors_from_subexpressions(self):
        # pylint: disable=no-self-use
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = ("", "invalid", 1)
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
                            BOOL_AND, [DateUnaryExpr(DATE_OP_GT, "a date"),]
                        ),
                    ],
                ),
                mock_runner,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="a date",
                    allowed_values="ISO8601 date",
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
                        "mock runner",
                        allow_rsc_expr=rsc_allowed,
                        allow_op_expr=op_allowed,
                    ).get_reports(),
                    report_list,
                )

    def test_disallow_missing_op(self):
        assert_report_item_list_equal(
            Validator(
                self.rule_rsc,
                "mock runner",
                allow_rsc_expr=True,
                allow_op_expr=False,
            ).get_reports(),
            [],
        )

    def test_disallow_missing_rsc(self):
        assert_report_item_list_equal(
            Validator(
                self.rule_op,
                "mock runner",
                allow_rsc_expr=False,
                allow_op_expr=True,
            ).get_reports(),
            [],
        )


class DateUnaryExpression(TestCase):
    def setUp(self):
        self.expr = BoolExpr(BOOL_AND, [DateUnaryExpr(DATE_OP_GT, "a date")])
        self.runner = mock.MagicMock(spec_set=CommandRunner)

    def test_date_ok(self):
        self.runner.run.return_value = ("Date: 1234", "", 0)
        assert_report_item_list_equal(
            Validator(self.expr, self.runner).get_reports(), [],
        )

    def test_date_bad(self):
        self.runner.run.return_value = ("", "invalid", 1)
        assert_report_item_list_equal(
            Validator(self.expr, self.runner).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="a date",
                    allowed_values="ISO8601 date",
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

    def setUp(self):
        self.runner = mock.MagicMock(spec_set=CommandRunner)

    def test_date_date_ok(self):
        self.runner.run.side_effect = [
            ("Date: 1234", "", 0),
            ("Date: 2345", "", 0),
        ]
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr("date1", "date2", None)]),
                self.runner,
            ).get_reports(),
            [],
        )

    def test_date_ok(self):
        self.runner.run.return_value = ("Date: 1234", "", 0)
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr(None, "date2", None)]),
                self.runner,
            ).get_reports(),
            [],
        )

    def test_date_duration_ok(self):
        self.runner.run.return_value = ("Date: 1234", "", 0)
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [
                        DateInRangeExpr(
                            "date1",
                            None,
                            [(name, "3") for name in self.part_list],
                        )
                    ],
                ),
                self.runner,
            ).get_reports(),
            [],
        )

    def test_until_greater_than_since(self):
        self.runner.run.side_effect = [
            ("Date: 2345", "", 0),
            ("Date: 1234", "", 0),
        ]
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr("date1", "date2", None)]),
                self.runner,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_SINCE_GREATER_THAN_UNTIL,
                    since="date1",
                    until="date2",
                )
            ],
        )

    def test_dates_bad(self):
        self.runner.run.return_value = ("", "invalid", 1)
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DateInRangeExpr("date1", "date2", None)]),
                self.runner,
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="date1",
                    allowed_values="ISO8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="date",
                    option_value="date2",
                    allowed_values="ISO8601 date",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_duration_bad(self):
        self.runner.run.return_value = ("Date: 1234", "", 0)
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [
                        DateInRangeExpr(
                            "date1",
                            None,
                            [(name, "0") for name in self.part_list]
                            + [("hours", "foo"), ("bad", "something")],
                        )
                    ],
                ),
                self.runner,
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
            ],
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

    def test_ok(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "3") for name in self.part_list])],
                ),
                "mock runner",
            ).get_reports(),
            [],
        )

    def test_range_ok(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "3-5") for name in self.part_list])],
                ),
                "mock runner",
            ).get_reports(),
            [],
        )

    def test_bad_value(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(
                    BOOL_AND,
                    [DatespecExpr([(name, "5-3") for name in self.part_list])],
                ),
                "mock runner",
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
            ],
        )

    def test_bad_name(self):
        assert_report_item_list_equal(
            Validator(
                BoolExpr(BOOL_AND, [DatespecExpr([("name", "5-3")])]),
                "mock runner",
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
                "mock runner",
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
                self.fixture_expr(NODE_ATTR_TYPE_NUMBER, "16464"),
                "mock runner",
            ).get_reports(),
            [],
        )

    def test_integer_bad(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_NUMBER, "16464aa"),
                "mock runner",
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="attribute",
                    option_value="16464aa",
                    allowed_values="an integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_version_ok(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_VERSION, "0.10.11"),
                "mock runner",
            ).get_reports(),
            [],
        )

    def test_version_bad(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(NODE_ATTR_TYPE_VERSION, "0.10.11c"),
                "mock runner",
            ).get_reports(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="attribute",
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
                "mock runner",
            ).get_reports(),
            [],
        )

    def test_no_type(self):
        assert_report_item_list_equal(
            Validator(
                self.fixture_expr(None, "a string 461.78"), "mock runner",
            ).get_reports(),
            [],
        )
