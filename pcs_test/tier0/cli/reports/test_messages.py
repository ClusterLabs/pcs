from unittest import TestCase

from pcs.common.reports import (
    item,
    messages,
)
from pcs.cli.reports import messages as cli_messages


class CliReportMessageTestBase(TestCase):
    def assert_message(
        self, msg_obj: item.ReportItemMessage, expected_msg: str
    ) -> None:
        self.assertEqual(
            cli_messages.report_item_msg_from_dto(msg_obj.to_dto()).message,
            expected_msg,
        )


class ResourceManagedNoMonitorEnabled(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.ResourceManagedNoMonitorEnabled("resId"),
            (
                "Resource 'resId' has no enabled monitor operations. Re-run "
                "with '--monitor' to enable them."
            ),
        )


class ResourceUnmoveUnbanPcmkExpiredNotSupported(CliReportMessageTestBase):
    def test_message(self):
        self.assert_message(
            messages.ResourceUnmoveUnbanPcmkExpiredNotSupported(),
            "--expired not supported, please upgrade pacemaker",
        )


class CannotUnmoveUnbanResourceMasterResourceNotPromotable(
    CliReportMessageTestBase
):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable(
                "R", "P"
            ),
            (
                "when specifying --master you must use the promotable clone id "
                "(P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotUnmoveUnbanResourceMasterResourceNotPromotable("R"),
            "when specifying --master you must use the promotable clone id",
        )


class CannotBanResourceMasterResourceNotPromotable(CliReportMessageTestBase):
    def test_with_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R", "P"),
            (
                "when specifying --master you must use the promotable clone id "
                "(P)"
            ),
        )

    def test_without_promotable_id(self):
        self.assert_message(
            messages.CannotBanResourceMasterResourceNotPromotable("R"),
            "when specifying --master you must use the promotable clone id",
        )


class InvalidCibContent(CliReportMessageTestBase):
    def test_message_can_be_more_verbose(self):
        report = "no verbose\noutput\n"
        self.assert_message(
            messages.InvalidCibContent(report, True),
            "invalid cib:\n{0}\n\nUse --full for more details.".format(report),
        )

    def test_message_cannot_be_more_verbose(self):
        report = "some verbose\noutput"
        self.assert_message(
            messages.InvalidCibContent(report, False),
            "invalid cib:\n{0}".format(report),
        )


class NodeCommunicationErrorNotAuthorized(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.NodeCommunicationErrorNotAuthorized(
                "node1", "some-command", "some error"
            ),
            (
                "Unable to authenticate to node1 (some error), try running "
                "'pcs host auth node1'"
            ),
        )


class NodeCommunicationErrorTimedOut(CliReportMessageTestBase):
    def test_success(self):
        self.assert_message(
            messages.NodeCommunicationErrorTimedOut(
                "node-1",
                "/remote/command",
                "Connection timed out after 60049 milliseconds",
            ),
            (
                "node-1: Connection timeout, try setting higher timeout in "
                "--request-timeout option (Connection timed out after 60049 "
                "milliseconds)"
            ),
        )


# TODO: create test/check that all subclasses of
# pcs.cli.reports.messages.CliReportMessageCustom have their test class with
# the same name in this file
