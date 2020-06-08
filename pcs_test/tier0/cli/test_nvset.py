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
    CibNvsetType,
    CibRuleExpressionType,
)


class NvsetDtoToLines(TestCase):
    type_to_label = (
        (CibNvsetType.META, "Meta Attrs"),
        (CibNvsetType.INSTANCE, "Attributes"),
    )

    @staticmethod
    def _export(dto, with_ids):
        return (
            "\n".join(nvset.nvset_dto_to_lines(dto, with_ids=with_ids)) + "\n"
        )

    def assert_lines(self, dto, lines):
        self.assertEqual(
            self._export(dto, True), lines,
        )
        self.assertEqual(
            self._export(dto, False), re.sub(r" +\(id:.*\)", "", lines),
        )

    def test_minimal(self):
        for nvtype, label in self.type_to_label:
            with self.subTest(nvset_type=nvtype, lanel=label):
                dto = CibNvsetDto("my-id", nvtype, {}, None, [])
                output = dedent(
                    f"""\
                      {label}: my-id
                    """
                )
                self.assert_lines(dto, output)

    def test_full(self):
        for nvtype, label in self.type_to_label:
            with self.subTest(nvset_type=nvtype, lanel=label):
                dto = CibNvsetDto(
                    "my-id",
                    nvtype,
                    {"score": "150"},
                    CibRuleExpressionDto(
                        "my-id-rule",
                        CibRuleExpressionType.RULE,
                        False,
                        {"boolean-op": "or"},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                "my-id-rule-op",
                                CibRuleExpressionType.OP_EXPRESSION,
                                False,
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
                    {label}: my-id score=150
                      "name 2"="value 2"
                      name1=value1
                      "name=3"="value=3"
                      Rule: boolean-op=or (id:my-id-rule)
                        Expression: op monitor (id:my-id-rule-op)
                    """
                )
                self.assert_lines(dto, output)
