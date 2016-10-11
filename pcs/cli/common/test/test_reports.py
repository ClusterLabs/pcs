from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from collections import namedtuple

from pcs.cli.common.reports import build_message_from_report

ReportItem = namedtuple("ReportItem", "code info")

class BuildMessageFromReportTest(TestCase):
    def test_returns_default_message_when_code_not_in_map(self):
        info = {"first": "FIRST"}
        self.assertEqual(
            "Unknown report: SOME info: {0}force text".format(str(info)) ,
            build_message_from_report(
                {},
                ReportItem("SOME", info),
                "force text"
            )
        )

    def test_complete_force_text(self):
        self.assertEqual(
            "Message force text is inside",
            build_message_from_report(
                {
                    "SOME": "Message {force} is inside",
                },
                ReportItem("SOME", {}),
                "force text"
            )
        )

    def test_deal_with_callable(self):
        self.assertEqual(
            "Info: MESSAGE",
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message}".format(**info),
                },
                ReportItem("SOME", {"message": "MESSAGE"}),
            )
        )

    def test_append_force_when_needed_and_not_specified(self):
        self.assertEqual(
            "message force at the end",
            build_message_from_report(
                {"SOME": "message"},
                ReportItem("SOME", {}),
                " force at the end",
            )
        )

    def test_returns_default_message_when_conflict_key_appear(self):
        info = {"message": "MESSAGE"}
        self.assertEqual(
            "Unknown report: SOME info: {0}".format(str(info)),
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message} {extra}".format(
                        message="ANY", **info
                    ),
                },
                ReportItem("SOME", info),
            )
        )

    def test_returns_default_message_when_key_disappear(self):
        self.assertEqual(
            "Unknown report: SOME info: {}"
            ,
            build_message_from_report(
                {
                    "SOME": lambda info: "Info: {message}".format(**info),
                },
                ReportItem("SOME", {}),
            )
        )
