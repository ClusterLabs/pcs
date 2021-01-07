from unittest import TestCase

from dataclasses import (
    dataclass,
    field,
)
from typing import (
    Any,
    List,
    Mapping,
    Optional,
    Union,
)

from pcs.common.reports import (
    types,
    dto,
    item,
)

REPORT_CODE = types.MessageCode("REPORT_CODE")
OUTER_REPORT_CODE = types.MessageCode("OUTER_REPORT_CODE")


@dataclass(frozen=True)
class ReportMessage(item.ReportItemMessage):
    string: str
    union_str_or_list_of_str: Union[str, List[str]]
    list_of_str: List[str] = field(default_factory=list)
    optional_list_of_int: Optional[List[int]] = None
    optional_mapping_str_to_any: Optional[Mapping[str, Any]] = None
    _code = REPORT_CODE

    @property
    def message(self):
        return "a message"


@dataclass(frozen=True)
class OuterReportMessage(item.ReportItemMessage):
    optional_inner_msg: Optional[ReportMessage]
    optional_string: Optional[str] = None
    _code = OUTER_REPORT_CODE

    @property
    def message(self):
        return "an outer message"


class ReportItemMessageToDtoTest(TestCase):
    def test_all_specified(self):
        self.assertEqual(
            ReportMessage(
                "a string",
                "another string",
                ["str1", "str0"],
                [0, 1, 0],
                {"str1": 1, "key": "val", "another": False},
            ).to_dto(),
            dto.ReportItemMessageDto(
                REPORT_CODE,
                "a message",
                dict(
                    string="a string",
                    union_str_or_list_of_str="another string",
                    list_of_str=["str1", "str0"],
                    optional_list_of_int=[0, 1, 0],
                    optional_mapping_str_to_any=dict(
                        str1=1,
                        key="val",
                        another=False,
                    ),
                ),
            ),
        )

    def test_minimal(self):
        self.assertEqual(
            ReportMessage("a string", ["str1", "str0"]).to_dto(),
            dto.ReportItemMessageDto(
                REPORT_CODE,
                "a message",
                dict(
                    string="a string",
                    union_str_or_list_of_str=["str1", "str0"],
                    list_of_str=[],
                    optional_list_of_int=None,
                    optional_mapping_str_to_any=None,
                ),
            ),
        )

    def test_alternatives(self):
        self.assertEqual(
            ReportMessage(
                "a string",
                ["str1", "str0"],
                ["str1", "str0", "str3"],
                optional_list_of_int=None,
                optional_mapping_str_to_any={},
            ).to_dto(),
            dto.ReportItemMessageDto(
                REPORT_CODE,
                "a message",
                dict(
                    string="a string",
                    union_str_or_list_of_str=["str1", "str0"],
                    list_of_str=["str1", "str0", "str3"],
                    optional_list_of_int=None,
                    optional_mapping_str_to_any={},
                ),
            ),
        )

    def test_with_inner_msg(self):
        self.assertEqual(
            OuterReportMessage(
                ReportMessage("a string", ["str1", "str0"]), "a str"
            ).to_dto(),
            dto.ReportItemMessageDto(
                OUTER_REPORT_CODE,
                "an outer message",
                dict(
                    optional_inner_msg=dto.ReportItemMessageDto(
                        REPORT_CODE,
                        "a message",
                        dict(
                            string="a string",
                            union_str_or_list_of_str=["str1", "str0"],
                            list_of_str=[],
                            optional_list_of_int=None,
                            optional_mapping_str_to_any=None,
                        ),
                    ),
                    optional_string="a str",
                ),
            ),
        )
