import re
from textwrap import dedent
from unittest import TestCase

from pcs.cli import rule
from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)


class RuleDtoToLinesMixin:
    @staticmethod
    def _export(dto, with_ids):
        return (
            "\n".join(rule.rule_expression_dto_to_lines(dto, with_ids=with_ids))
            + "\n"
        )

    def assert_lines(self, dto, lines):
        self.assertEqual(
            self._export(dto, True),
            lines,
        )
        self.assertEqual(
            self._export(dto, False),
            re.sub(r" +\(id:.*\)", "", lines),
        )


class ExpressionDtoToLines(RuleDtoToLinesMixin, TestCase):
    def test_defined(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-expr",
                    CibRuleExpressionType.EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"attribute": "pingd", "operation": "defined"},
                    None,
                    None,
                    [],
                    "defined pingd",
                ),
            ],
            "defined pingd",
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: defined pingd (id: my-id-expr)
            """
        )
        self.assert_lines(dto, output)

    def test_value_comparison(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-expr",
                    CibRuleExpressionType.EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {
                        "attribute": "my-attr",
                        "operation": "eq",
                        "value": "my value",
                    },
                    None,
                    None,
                    [],
                    "my-attr eq 'my value'",
                ),
            ],
            "my-attr eq 'my value'",
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: my-attr eq 'my value' (id: my-id-expr)
            """
        )
        self.assert_lines(dto, output)

    def test_value_comparison_with_type(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-expr",
                    CibRuleExpressionType.EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
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
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: foo gt version 1.2.3 (id: my-id-expr)
            """
        )
        self.assert_lines(dto, output)


class DateExpressionDtoToLines(RuleDtoToLinesMixin, TestCase):
    def test_simple(self):
        dto = CibRuleExpressionDto(
            "rule",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule-expr",
                    CibRuleExpressionType.DATE_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"operation": "gt", "start": "2014-06-26"},
                    None,
                    None,
                    [],
                    "date gt 2014-06-26",
                ),
            ],
            "date gt 2014-06-26",
        )
        output = dedent(
            """\
              Rule: (id: rule)
                Expression: date gt 2014-06-26 (id: rule-expr)
            """
        )
        self.assert_lines(dto, output)

    def test_datespec(self):
        dto = CibRuleExpressionDto(
            "rule",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule-expr",
                    CibRuleExpressionType.DATE_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"operation": "date_spec"},
                    CibRuleDateCommonDto(
                        "rule-expr-datespec",
                        {"hours": "1-14", "monthdays": "20-30", "months": "1"},
                    ),
                    None,
                    [],
                    "date-spec hours=1-14 monthdays=20-30 months=1",
                ),
            ],
            "date-spec hours=1-14 monthdays=20-30 months=1",
        )
        output = dedent(
            """\
              Rule: (id: rule)
                Expression: (id: rule-expr)
                  Date Spec: hours=1-14 monthdays=20-30 months=1 (id: rule-expr-datespec)
            """
        )
        self.assert_lines(dto, output)

    def test_inrange_start_end(self):
        dto = CibRuleExpressionDto(
            "rule",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule-expr",
                    CibRuleExpressionType.DATE_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
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
        )
        output = dedent(
            """\
              Rule: (id: rule)
                Expression: date in_range 2014-06-26 to 2014-07-26 (id: rule-expr)
            """
        )
        self.assert_lines(dto, output)

    def test_inrange_end(self):
        dto = CibRuleExpressionDto(
            "rule",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule-expr",
                    CibRuleExpressionType.DATE_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"operation": "in_range", "end": "2014-07-26"},
                    None,
                    None,
                    [],
                    "date in_range to 2014-07-26",
                ),
            ],
            "date in_range to 2014-07-26",
        )
        output = dedent(
            """\
              Rule: (id: rule)
                Expression: date in_range to 2014-07-26 (id: rule-expr)
            """
        )
        self.assert_lines(dto, output)

    def test_inrange_start_duration(self):
        dto = CibRuleExpressionDto(
            "rule",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "rule-expr",
                    CibRuleExpressionType.DATE_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {
                        "operation": "in_range",
                        "start": "2014-06-26",
                    },
                    None,
                    CibRuleDateCommonDto("rule-expr-duration", {"years": "1"}),
                    [],
                    "date in_range 2014-06-26 to duration years=1",
                ),
            ],
            "date in_range 2014-06-26 to duration years=1",
        )
        output = dedent(
            """\
              Rule: (id: rule)
                Expression: date in_range 2014-06-26 to duration (id: rule-expr)
                  Duration: years=1 (id: rule-expr-duration)
            """
        )
        self.assert_lines(dto, output)


class OpExpressionDtoToLines(RuleDtoToLinesMixin, TestCase):
    def test_minimal(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-op",
                    CibRuleExpressionType.OP_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"name": "start"},
                    None,
                    None,
                    [],
                    "op start",
                ),
            ],
            "op start",
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: op start (id: my-id-op)
            """
        )
        self.assert_lines(dto, output)

    def test_interval(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-op",
                    CibRuleExpressionType.OP_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"name": "start", "interval": "2min"},
                    None,
                    None,
                    [],
                    "op start interval=2min",
                ),
            ],
            "op start interval=2min",
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: op start interval=2min (id: my-id-op)
            """
        )
        self.assert_lines(dto, output)


class ResourceExpressionDtoToLines(RuleDtoToLinesMixin, TestCase):
    def test_success(self):
        dto = CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-expr",
                    CibRuleExpressionType.RSC_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"class": "ocf", "provider": "pacemaker", "type": "Dummy"},
                    None,
                    None,
                    [],
                    "resource ocf:pacemaker:Dummy",
                ),
            ],
            "resource ocf:pacemaker:Dummy",
        )
        output = dedent(
            """\
              Rule: (id: my-id)
                Expression: resource ocf:pacemaker:Dummy (id: my-id-expr)
            """
        )
        self.assert_lines(dto, output)


class InEffect(RuleDtoToLinesMixin, TestCase):
    @staticmethod
    def fixture_dto(expired):
        return CibRuleExpressionDto(
            "my-id",
            CibRuleExpressionType.RULE,
            expired,
            {},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "my-id-expr",
                    CibRuleExpressionType.EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"attribute": "pingd", "operation": "defined"},
                    None,
                    None,
                    [],
                    "defined pingd",
                ),
            ],
            "defined pingd",
        )

    def test_unknown(self):
        self.assert_lines(
            self.fixture_dto(CibRuleInEffectStatus.UNKNOWN),
            dedent(
                """\
                  Rule: (id: my-id)
                    Expression: defined pingd (id: my-id-expr)
                """
            ),
        )

    def test_expired(self):
        self.assert_lines(
            self.fixture_dto(CibRuleInEffectStatus.EXPIRED),
            dedent(
                """\
                  Rule (expired): (id: my-id)
                    Expression: defined pingd (id: my-id-expr)
                """
            ),
        )

    def test_not_yet_effective(self):
        self.assert_lines(
            self.fixture_dto(CibRuleInEffectStatus.NOT_YET_IN_EFFECT),
            dedent(
                """\
                  Rule (not yet in effect): (id: my-id)
                    Expression: defined pingd (id: my-id-expr)
                """
            ),
        )


class RuleDtoToLines(RuleDtoToLinesMixin, TestCase):
    def test_complex_rule(self):
        dto = CibRuleExpressionDto(
            "complex",
            CibRuleExpressionType.RULE,
            CibRuleInEffectStatus.UNKNOWN,
            {"boolean-op": "or", "score": "INFINITY"},
            None,
            None,
            [
                CibRuleExpressionDto(
                    "complex-rule-1",
                    CibRuleExpressionType.RULE,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "complex-rule-1-expr",
                            CibRuleExpressionType.DATE_EXPRESSION,
                            CibRuleInEffectStatus.UNKNOWN,
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
                            CibRuleInEffectStatus.UNKNOWN,
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
                    CibRuleInEffectStatus.UNKNOWN,
                    {"boolean-op": "and", "score": "0"},
                    None,
                    None,
                    [
                        CibRuleExpressionDto(
                            "complex-rule-expr-1",
                            CibRuleExpressionType.EXPRESSION,
                            CibRuleInEffectStatus.UNKNOWN,
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
                            CibRuleInEffectStatus.UNKNOWN,
                            {
                                "attribute": "#uname",
                                "operation": "eq",
                                "value": "node3 4",
                            },
                            None,
                            None,
                            [],
                            "#uname eq 'node3 4'",
                        ),
                        CibRuleExpressionDto(
                            "complex-rule-expr-2",
                            CibRuleExpressionType.EXPRESSION,
                            CibRuleInEffectStatus.UNKNOWN,
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
                    "foo gt version 1.2 and #uname eq 'node3 4' and #uname "
                    "eq nodeA",
                ),
            ],
            "(date-spec hours=12-23 weekdays=1-5 and date in_range "
            "2014-07-26 to duration months=1) or (foo gt version 1.2 and "
            "#uname eq 'node3 4' and #uname eq nodeA)",
        )
        output = dedent(
            """\
            Rule: boolean-op=or score=INFINITY (id: complex)
              Rule: boolean-op=and score=0 (id: complex-rule-1)
                Expression: (id: complex-rule-1-expr)
                  Date Spec: hours=12-23 weekdays=1-5 (id: complex-rule-1-expr-datespec)
                Expression: date in_range 2014-07-26 to duration (id: complex-rule-1-expr-1)
                  Duration: months=1 (id: complex-rule-1-expr-1-durat)
              Rule: boolean-op=and score=0 (id: complex-rule)
                Expression: foo gt version 1.2 (id: complex-rule-expr-1)
                Expression: #uname eq 'node3 4' (id: complex-rule-expr)
                Expression: #uname eq nodeA (id: complex-rule-expr-2)
            """
        )
        self.assert_lines(dto, output)
