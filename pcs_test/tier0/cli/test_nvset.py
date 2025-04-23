import re
from textwrap import dedent
from unittest import TestCase

from pcs.cli import nvset
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)


def fixture_dto(in_effect):
    return CibNvsetDto(
        f"id-{in_effect}",
        {"score": "150"},
        CibRuleExpressionDto(
            f"id-{in_effect}-rule",
            CibRuleExpressionType.RULE,
            in_effect,
            {"boolean-op": "or"},
            None,
            None,
            [
                CibRuleExpressionDto(
                    f"id-{in_effect}-rule-op",
                    CibRuleExpressionType.OP_EXPRESSION,
                    CibRuleInEffectStatus.UNKNOWN,
                    {"name": "monitor"},
                    None,
                    None,
                    [],
                    "op monitor",
                ),
            ],
            "op monitor",
        ),
        [CibNvpairDto(f"id-{in_effect}-pair1", "name1", "value1")],
    )


def fixture_dto_list():
    return [fixture_dto(in_effect.value) for in_effect in CibRuleInEffectStatus]


class FilterOutExpiredNvset(TestCase):
    def test_filter(self):
        self.maxDiff = None
        list_with_expired_nvsets = [
            CibNvsetDto(id="nvset-no-rule", options={}, rule=None, nvpairs=[]),
            CibNvsetDto(
                id="nvset-2",
                options={},
                rule=CibRuleExpressionDto(
                    id="rule-another-expired",
                    type=CibRuleExpressionType.DATE_EXPRESSION,
                    in_effect=CibRuleInEffectStatus.EXPIRED,
                    options={},
                    date_spec=None,
                    duration=None,
                    expressions=[],
                    as_string="",
                ),
                nvpairs=[],
            ),
        ] + fixture_dto_list()
        expected_list = [
            item
            for idx, item in enumerate(list_with_expired_nvsets[:])
            if idx not in [1, 4]
        ]
        self.assertEqual(
            nvset.filter_out_expired_nvset(list_with_expired_nvsets),
            expected_list,
        )

    def test_empty_list(self):
        self.assertEqual(nvset.filter_out_expired_nvset([]), [])


class FilterNvpairsByNames(TestCase):
    test_nvsets = [
        CibNvsetDto(
            id="1",
            options={},
            rule=None,
            nvpairs=[
                CibNvpairDto(id="1a", name="a", value="1"),
                CibNvpairDto(id="1b", name="b", value="2"),
                CibNvpairDto(id="1c", name="c", value="3"),
            ],
        ),
        CibNvsetDto(
            id="2",
            options={},
            rule=None,
            nvpairs=[
                CibNvpairDto(id="2a", name="a", value="1"),
                CibNvpairDto(id="2b", name="b", value="2"),
            ],
        ),
    ]

    def test_filter_no_match(self):
        self.assertEqual(
            nvset.filter_nvpairs_by_names(self.test_nvsets, ["x"]),
            [
                CibNvsetDto(id="1", options={}, rule=None, nvpairs=[]),
                CibNvsetDto(id="2", options={}, rule=None, nvpairs=[]),
            ],
        )

    def test_filter_match_in_one_set(self):
        self.assertEqual(
            nvset.filter_nvpairs_by_names(self.test_nvsets, ["c"]),
            [
                CibNvsetDto(
                    id="1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="1c", name="c", value="3"),
                    ],
                ),
                CibNvsetDto(id="2", options={}, rule=None, nvpairs=[]),
            ],
        )

    def test_filter_match_in_more_set(self):
        self.assertEqual(
            nvset.filter_nvpairs_by_names(self.test_nvsets, ["a"]),
            [
                CibNvsetDto(
                    id="1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="1a", name="a", value="1"),
                    ],
                ),
                CibNvsetDto(
                    id="2",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="2a", name="a", value="1"),
                    ],
                ),
            ],
        )

    def test_filter_multiple_filter(self):
        self.assertEqual(
            nvset.filter_nvpairs_by_names(self.test_nvsets, ["a", "c", "x"]),
            [
                CibNvsetDto(
                    id="1",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="1a", name="a", value="1"),
                        CibNvpairDto(id="1c", name="c", value="3"),
                    ],
                ),
                CibNvsetDto(
                    id="2",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(id="2a", name="a", value="1"),
                    ],
                ),
            ],
        )


class NvsetDtoToLines(TestCase):
    def setUp(self):
        self.label = "Meta Attributes"

    def _export(self, dto, with_ids):
        return (
            "\n".join(
                nvset.nvset_dto_to_lines(
                    dto, nvset_label=self.label, with_ids=with_ids
                )
            )
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

    def test_minimal(self):
        dto = CibNvsetDto("my-id", {}, None, [])
        output = dedent(
            f"""\
              {self.label}: my-id
            """
        )
        self.assert_lines(dto, output)

    def test_full(self):
        dto = CibNvsetDto(
            "my-id",
            {"score": "150"},
            CibRuleExpressionDto(
                "my-id-rule",
                CibRuleExpressionType.RULE,
                CibRuleInEffectStatus.UNKNOWN,
                {"boolean-op": "or"},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-rule-op",
                        CibRuleExpressionType.OP_EXPRESSION,
                        CibRuleInEffectStatus.UNKNOWN,
                        {"name": "monitor"},
                        None,
                        None,
                        [],
                        "op monitor",
                    ),
                ],
                "op monitor",
            ),
            [
                CibNvpairDto("my-id-pair1", "name1", "value1"),
                CibNvpairDto("my-id-pair2", "name 2", "value 2"),
                CibNvpairDto("my-id-pair3", "name=3", "value=3"),
            ],
        )
        output = dedent(
            f"""\
            {self.label}: my-id score=150
              "name 2"="value 2" (id: my-id-pair2)
              name1=value1 (id: my-id-pair1)
              "name=3"="value=3" (id: my-id-pair3)
              Rule: boolean-op=or (id: my-id-rule)
                Expression: op monitor (id: my-id-rule-op)
            """
        )
        self.assert_lines(dto, output)


class NvsetDtoListToLines(TestCase):
    def setUp(self):
        self.label = "Meta Attributes"

    def _export(self, dto, with_ids):
        return (
            "\n".join(
                nvset.nvset_dto_list_to_lines(
                    dto,
                    nvset_label=self.label,
                    with_ids=with_ids,
                )
            )
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

    def test_lines(self):
        self.maxDiff = None
        output = dedent(
            f"""\
            {self.label} (not yet in effect): id-NOT_YET_IN_EFFECT score=150
              name1=value1 (id: id-NOT_YET_IN_EFFECT-pair1)
              Rule (not yet in effect): boolean-op=or (id: id-NOT_YET_IN_EFFECT-rule)
                Expression: op monitor (id: id-NOT_YET_IN_EFFECT-rule-op)
            {self.label}: id-IN_EFFECT score=150
              name1=value1 (id: id-IN_EFFECT-pair1)
              Rule: boolean-op=or (id: id-IN_EFFECT-rule)
                Expression: op monitor (id: id-IN_EFFECT-rule-op)
            {self.label} (expired): id-EXPIRED score=150
              name1=value1 (id: id-EXPIRED-pair1)
              Rule (expired): boolean-op=or (id: id-EXPIRED-rule)
                Expression: op monitor (id: id-EXPIRED-rule-op)
            {self.label}: id-UNKNOWN score=150
              name1=value1 (id: id-UNKNOWN-pair1)
              Rule: boolean-op=or (id: id-UNKNOWN-rule)
                Expression: op monitor (id: id-UNKNOWN-rule-op)
        """
        )
        self.assert_lines(fixture_dto_list(), output)
