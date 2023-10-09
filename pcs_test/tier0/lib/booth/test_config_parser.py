from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.booth import config_parser
from pcs.lib.booth.config_parser import ConfigItem
from pcs.lib.interface.config import ParserErrorException

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class BuildTest(TestCase):
    def test_build_file_content_from_parsed_structure(self):
        self.assertEqual(
            "\n".join(
                [
                    "authfile = /path/to/auth.file",
                    "site = 1.1.1.1",
                    "site = 2.2.2.2",
                    "arbitrator = 3.3.3.3",
                    'ticket = "TA"',
                    'ticket = "TB"',
                    "  timeout = 10",
                    "",  # newline at the end
                ]
            ).encode("utf-8"),
            config_parser.Exporter.export(
                [
                    ConfigItem("authfile", "/path/to/auth.file"),
                    ConfigItem("site", "1.1.1.1"),
                    ConfigItem("site", "2.2.2.2"),
                    ConfigItem("arbitrator", "3.3.3.3"),
                    ConfigItem("ticket", "TA"),
                    ConfigItem("ticket", "TB", [ConfigItem("timeout", "10")]),
                ]
            ),
        )


class OrganizeLinesTest(TestCase):
    def test_move_non_ticket_config_keys_above_tickets(self):
        self.assertEqual(
            [
                ConfigItem("site", "1.1.1.1"),
                ConfigItem("site", "2.2.2.2"),
                ConfigItem("arbitrator", "3.3.3.3"),
                ConfigItem("ticket", "TA"),
            ],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._organize_lines(
                [
                    ("site", "1.1.1.1"),
                    ("ticket", "TA"),
                    ("site", "2.2.2.2"),
                    ("arbitrator", "3.3.3.3"),
                ]
            ),
        )

    def test_use_ticket_key_as_ticket_detail(self):
        self.maxDiff = None
        self.assertEqual(
            [
                ConfigItem("site", "1.1.1.1"),
                ConfigItem("expire", "300"),
                ConfigItem("site", "2.2.2.2"),
                ConfigItem("arbitrator", "3.3.3.3"),
                ConfigItem(
                    "ticket",
                    "TA",
                    [
                        ConfigItem("timeout", "10"),
                        ConfigItem("--nonexistent", "value"),
                        ConfigItem("expire", "300"),
                    ],
                ),
                ConfigItem(
                    "ticket",
                    "TB",
                    [
                        ConfigItem("timeout", "20"),
                        ConfigItem("renewal-freq", "40"),
                    ],
                ),
            ],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._organize_lines(
                [
                    ("site", "1.1.1.1"),
                    ("expire", "300"),  # out of ticket content is kept global
                    ("ticket", "TA"),
                    ("site", "2.2.2.2"),  # move to global
                    ("timeout", "10"),
                    (
                        "--nonexistent",
                        "value",
                    ),  # no global is kept under ticket
                    ("expire", "300"),
                    ("ticket", "TB"),
                    ("arbitrator", "3.3.3.3"),
                    ("timeout", "20"),
                    ("renewal-freq", "40"),
                ]
            ),
        )


class ParseRawLinesTest(TestCase):
    def test_parse_simple_correct_lines(self):
        self.assertEqual(
            [
                ("site", "1.1.1.1"),
                ("site", "2.2.2.2"),
                ("arbitrator", "3.3.3.3"),
                ("syntactically_correct", "nonsense"),
                ("line-with", "hash#literal"),
            ],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._parse_to_raw_lines(
                "\n".join(
                    [
                        "site = 1.1.1.1",
                        " site  =  2.2.2.2 ",
                        "arbitrator=3.3.3.3",
                        "syntactically_correct = nonsense",
                        "line-with = hash#literal",
                        "",
                    ]
                )
            ),
        )

    def test_parse_lines_with_whole_line_comment(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._parse_to_raw_lines(
                "\n".join(
                    [
                        " # some comment",
                        "site = 1.1.1.1",
                    ]
                )
            ),
        )

    def test_skip_empty_lines(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._parse_to_raw_lines(
                "\n".join(
                    [
                        " ",
                        "site = 1.1.1.1",
                    ]
                )
            ),
        )

    def test_raises_when_unexpected_lines_appear(self):
        invalid_line_list = [
            "first invalid line",
            "second = 'invalid line' something else #comment",
            "third = 'invalid line 'something#'#",
        ]
        line_list = ["site = 1.1.1.1"] + invalid_line_list
        with self.assertRaises(config_parser.InvalidLines) as context_manager:
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._parse_to_raw_lines("\n".join(line_list))
        self.assertEqual(context_manager.exception.args[0], invalid_line_list)

    def test_parse_lines_finishing_with_comment(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            # testing a function which should not be used outside of the module
            # pylint: disable=protected-access
            config_parser._parse_to_raw_lines(
                "\n".join(
                    [
                        "site = '1.1.1.1' #comment",
                    ]
                )
            ),
        )


class ParseTest(TestCase):
    def test_raises_when_invalid_lines_appear(self):
        invalid_line_list = [
            "first invalid line",
            "second = 'invalid line' something else #comment",
        ]
        line_list = ["site = 1.1.1.1"] + invalid_line_list

        with self.assertRaises(ParserErrorException) as cm:
            config_parser.Parser.parse("\n".join(line_list).encode("utf-8"))

        assert_report_item_list_equal(
            config_parser.Parser.exception_to_report_list(
                cm.exception, "does not matter", "path", None, False
            ),
            [
                fixture.error(
                    report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=invalid_line_list,
                    file_path="path",
                ),
            ],
        )
        assert_report_item_list_equal(
            config_parser.Parser.exception_to_report_list(
                cm.exception,
                "does not matter",
                "path",
                report_codes.FORCE,
                False,
            ),
            [
                fixture.error(
                    report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    force_code=report_codes.FORCE,
                    line_list=invalid_line_list,
                    file_path="path",
                ),
            ],
        )
        assert_report_item_list_equal(
            config_parser.Parser.exception_to_report_list(
                cm.exception,
                "does not matter",
                "path",
                report_codes.FORCE,
                True,
            ),
            [
                fixture.warn(
                    report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=invalid_line_list,
                    file_path="path",
                ),
            ],
        )

    def test_do_not_raises_when_no_invalid_liens_there(self):
        parsed = config_parser.Parser.parse("site = 1.1.1.1".encode("utf-8"))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].key, "site")
        self.assertEqual(parsed[0].value, "1.1.1.1")
        self.assertEqual(parsed[0].details, [])
