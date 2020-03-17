from pcs_test.tier0.cli.common.test_console_report import NameBuildTest

from pcs.lib.booth import reports



class BoothTicketOperationFailedTest(NameBuildTest):

    def test_success(self):
        self.assert_message_from_report(
            (
                "unable to operation booth ticket 'ticket_name'"
                " for site 'site_ip', reason: reason"
            ),
            reports.booth_ticket_operation_failed(
                "operation", "reason", "site_ip", "ticket_name"
            )
        )
