from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.file import toolbox
from pcs.lib.interface.config import ParserErrorException
from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class JsonParser(TestCase):
    file_type_code = "file type code"
    file_path = "file path"

    def test_success(self):
        self.assertEqual(
            toolbox.JsonParser.parse(dedent("""
                {
                    "simple": "value",
                    "list": ["item1", "item2"]
                }
                """
            )),
            {
                "simple": "value",
                "list": ["item1", "item2"],
            }
        )

    def _parse_error(self, force_code, is_forced):
        with self.assertRaises(ParserErrorException) as cm:
            toolbox.JsonParser.parse(dedent("""
                {
                    "simple": "value",
                    "list": ["item1" "item2"]
                }
                """
            ))
        return toolbox.JsonParser.exception_to_report_list(
            cm.exception, self.file_type_code, self.file_path, force_code,
            is_forced
        )

    def _parse_error_report_args(self):
        return dict(
            file_path=self.file_path,
            file_type_code=self.file_type_code,
            line_number=4,
            column_number=22,
            position=47,
            reason="Expecting ',' delimiter",
            full_msg="Expecting ',' delimiter: line 4 column 22 (char 47)",
        )

    def test_parse_error(self):
        assert_report_item_list_equal(
            self._parse_error(None, False),
            [
                fixture.error(
                    report_codes.PARSE_ERROR_JSON_FILE,
                    **self._parse_error_report_args()
                ),
            ]
        )

    def test_parse_error_forcible(self):
        assert_report_item_list_equal(
            self._parse_error("force code", False),
            [
                fixture.error(
                    report_codes.PARSE_ERROR_JSON_FILE,
                    force_code="force code",
                    **self._parse_error_report_args()
                ),
            ]
        )

    def test_parse_error_forced(self):
        assert_report_item_list_equal(
            self._parse_error("force code", True),
            [
                fixture.warn(
                    report_codes.PARSE_ERROR_JSON_FILE,
                    **self._parse_error_report_args()
                ),
            ]
        )


class JsonExporter(TestCase):
    def test_success(self):
        self.assertEqual(
            toolbox.JsonExporter.export(
                {
                    "simple": "value",
                    "list": ["item1", "item2"],
                }
            ),
            dedent("""\
                {
                    "list": [
                        "item1",
                        "item2"
                    ],
                    "simple": "value"
                }
            """.rstrip()).encode("utf-8")
        )
