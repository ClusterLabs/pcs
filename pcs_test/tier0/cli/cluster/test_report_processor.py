from unittest import TestCase, mock

from pcs.cli.cluster.report_processor import NodeRemoveRemoteReportProcessor
from pcs.common import reports


@mock.patch("pcs.cli.cluster.report_processor.print_report")
class NodeRemoveRemote(TestCase):
    REPORT = reports.ReportItem.info(reports.messages.NoActionNecessary())
    DEBUG_REPORT = reports.ReportItem.debug(
        reports.messages.NoActionNecessary()
    )
    FIRST_SERVICE_COMMAND_REPORT = reports.ReportItem.info(
        reports.messages.ServiceCommandsOnNodesStarted()
    )

    def setUp(self):
        self.report_processor = NodeRemoveRemoteReportProcessor()

    def test_saves_reports_in_memory(self, mock_print_report):
        self.report_processor.report(self.REPORT)
        self.assertEqual(self.report_processor.reports, [self.REPORT])
        self.assertFalse(self.report_processor.already_reported_to_console)
        mock_print_report.assert_not_called()

        self.report_processor.report(self.REPORT)
        self.assertEqual(
            self.report_processor.reports, [self.REPORT, self.REPORT]
        )
        self.assertFalse(self.report_processor.already_reported_to_console)
        mock_print_report.assert_not_called()

    def test_switches_to_printing(self, mock_print_report):
        self.report_processor.report_list([self.REPORT, self.REPORT])
        self.assertEqual(
            self.report_processor.reports, [self.REPORT, self.REPORT]
        )
        self.assertFalse(self.report_processor.already_reported_to_console)
        mock_print_report.assert_not_called()

        self.report_processor.report(self.FIRST_SERVICE_COMMAND_REPORT)
        self.assertEqual(self.report_processor.reports, [])
        self.assertTrue(self.report_processor.already_reported_to_console)
        self.assertEqual(mock_print_report.call_count, 3)
        mock_print_report.assert_has_calls(
            [
                mock.call(self.REPORT.to_dto()),
                mock.call(self.REPORT.to_dto()),
                mock.call(self.FIRST_SERVICE_COMMAND_REPORT.to_dto()),
            ]
        )

        self.report_processor.report(self.REPORT)
        self.assertEqual(self.report_processor.reports, [])
        self.assertEqual(mock_print_report.call_count, 4)
        mock_print_report.assert_has_calls(
            [
                mock.call(self.REPORT.to_dto()),
                mock.call(self.REPORT.to_dto()),
                mock.call(self.FIRST_SERVICE_COMMAND_REPORT.to_dto()),
                mock.call(self.REPORT.to_dto()),
            ]
        )

    def test_filter_debug(self, mock_print_report):
        self.report_processor.report_list([self.REPORT, self.DEBUG_REPORT])
        self.assertEqual(self.report_processor.reports, [self.REPORT])
        mock_print_report.assert_not_called()

    def test_keep_debug(self, mock_print_report):
        self.report_processor = NodeRemoveRemoteReportProcessor(True)

        self.report_processor.report_list([self.REPORT, self.DEBUG_REPORT])
        self.assertEqual(
            self.report_processor.reports, [self.REPORT, self.DEBUG_REPORT]
        )
        mock_print_report.assert_not_called()
