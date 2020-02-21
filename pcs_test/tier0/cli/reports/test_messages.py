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


# TODO: create test/check that all subclasses of
# pcs.cli.reports.messages.CliReportMessageCustom have their test class with
# the same name in this file
