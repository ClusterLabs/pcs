from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.booth import config_parser
from pcs.lib.booth.config_structure import ConfigItem
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.pcs_unittest import TestCase


class BuildTest(TestCase):
    def test_build_file_content_from_parsed_structure(self):
        self.assertEqual(
            "\n".join([
                "authfile = /path/to/auth.file",
                "site = 1.1.1.1",
                "site = 2.2.2.2",
                "arbitrator = 3.3.3.3",
                'ticket = "TA"',
                'ticket = "TB"',
                "  timeout = 10",
                "", #newline at the end
            ]),
            config_parser.build([
                ConfigItem("authfile", "/path/to/auth.file"),
                ConfigItem("site", "1.1.1.1"),
                ConfigItem("site", "2.2.2.2"),
                ConfigItem("arbitrator", "3.3.3.3"),
                ConfigItem("ticket", "TA"),
                ConfigItem("ticket", "TB", [
                    ConfigItem("timeout", "10")
                ]),
            ])
        )


class OrganizeLinesTest(TestCase):
    def test_move_non_ticket_config_keys_above_tickets(self):
        self.assertEqual(
            [
                ConfigItem("site", "1.1.1.1"),
                ConfigItem('site', '2.2.2.2'),
                ConfigItem('arbitrator', '3.3.3.3'),
                ConfigItem("ticket", "TA"),
            ],
            config_parser.organize_lines([
                ("site", "1.1.1.1"),
                ("ticket", "TA"),
                ('site', '2.2.2.2'),
                ('arbitrator', '3.3.3.3'),
            ])
        )

    def test_use_ticket_key_as_ticket_detail(self):
        self.maxDiff = None
        self.assertEqual(
            [
                ConfigItem("site", "1.1.1.1"),
                ConfigItem('expire', '300'),
                ConfigItem('site', '2.2.2.2'),
                ConfigItem('arbitrator', '3.3.3.3'),
                ConfigItem("ticket", "TA", [
                    ConfigItem("timeout", "10"),
                    ConfigItem('--nonexistent', 'value'),
                    ConfigItem("expire", "300"),
                ]),
                ConfigItem("ticket", "TB", [
                    ConfigItem("timeout", "20"),
                    ConfigItem("renewal-freq", "40"),
                ]),
            ],
            config_parser.organize_lines([
                ("site", "1.1.1.1"),
                ("expire", "300"), # out of ticket content is kept global
                ("ticket", "TA"),
                ("site", "2.2.2.2"), # move to global
                ("timeout", "10"),
                ("--nonexistent", "value"), # no global is kept under ticket
                ("expire", "300"),
                ("ticket", "TB"),
                ('arbitrator', '3.3.3.3'),
                ("timeout", "20"),
                ("renewal-freq", "40"),
            ])
        )


class ParseRawLinesTest(TestCase):
    def test_parse_simple_correct_lines(self):
        self.assertEqual(
            [
                ("site", "1.1.1.1"),
                ('site', '2.2.2.2'),
                ('arbitrator', '3.3.3.3'),
                ('syntactically_correct', 'nonsense'),
                ('line-with', 'hash#literal'),
            ],
            config_parser.parse_to_raw_lines("\n".join([
                "site = 1.1.1.1",
                " site  =  2.2.2.2 ",
                "arbitrator=3.3.3.3",
                "syntactically_correct = nonsense",
                "line-with = hash#literal",
                "",
            ]))
        )

    def test_parse_lines_with_whole_line_comment(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            config_parser.parse_to_raw_lines("\n".join([
                " # some comment",
                "site = 1.1.1.1",
            ]))
       )

    def test_skip_empty_lines(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            config_parser.parse_to_raw_lines("\n".join([
                " ",
                "site = 1.1.1.1",
            ]))
       )

    def test_raises_when_unexpected_lines_appear(self):
        invalid_line_list = [
            "first invalid line",
            "second = 'invalid line' something else #comment",
            "third = 'invalid line 'something#'#",
        ]
        line_list = ["site = 1.1.1.1"] + invalid_line_list
        with self.assertRaises(config_parser.InvalidLines) as context_manager:
            config_parser.parse_to_raw_lines("\n".join(line_list))
        self.assertEqual(context_manager.exception.args[0], invalid_line_list)

    def test_parse_lines_finishing_with_comment(self):
        self.assertEqual(
            [("site", "1.1.1.1")],
            config_parser.parse_to_raw_lines("\n".join([
                "site = '1.1.1.1' #comment",
            ]))
       )

class ParseTest(TestCase):
    def test_raises_when_invalid_lines_appear(self):
        invalid_line_list = [
            "first invalid line",
            "second = 'invalid line' something else #comment"
        ]
        line_list = ["site = 1.1.1.1"] + invalid_line_list
        assert_raise_library_error(
            lambda:
                config_parser.parse("\n".join(line_list))
            ,
            (
                severities.ERROR,
                report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                {
                    "line_list": invalid_line_list,
                },
            ),
        )

    def test_do_not_raises_when_no_invalid_liens_there(self):
        config_parser.parse("site = 1.1.1.1")
