from unittest import TestCase, mock

from pcs.cli.reports.output import process_library_reports
from pcs.common import reports


@mock.patch("pcs.cli.reports.output.print_to_stderr")
class ProcessLibraryReports(TestCase):
    report_message = reports.messages.NoActionNecessary()
    report_message_text = report_message.message

    def test_no_reports(self, mock_print_to_stderr):
        with self.assertRaises(SystemExit) as cm:
            process_library_reports([])
        self.assertEqual(cm.exception.code, 1)
        mock_print_to_stderr.assert_called_once_with(
            "Error: Errors have occurred, therefore pcs is unable to continue"
        )

    def test_all_report_severities_no_exit_on_error(self, mock_print_to_stderr):
        report_items = [
            reports.ReportItem.debug(self.report_message),
            reports.ReportItem.info(self.report_message),
            reports.ReportItem.warning(self.report_message),
            reports.ReportItem.deprecation(self.report_message),
            reports.ReportItem.error(self.report_message),
        ]

        process_library_reports(report_items, exit_on_error=False)

        mock_print_to_stderr.assert_has_calls(
            [
                mock.call(self.report_message_text),
                mock.call(self.report_message_text),
                mock.call(f"Warning: {self.report_message_text}"),
                mock.call(f"Deprecation Warning: {self.report_message_text}"),
                mock.call(f"Error: {self.report_message_text}"),
            ]
        )
        self.assertEqual(mock_print_to_stderr.call_count, 5)

    def test_exit_on_error(self, mock_print_to_stderr):
        with self.assertRaises(SystemExit) as cm:
            process_library_reports(
                [reports.ReportItem.error(self.report_message)],
                exit_on_error=True,
            )
        self.assertEqual(cm.exception.code, 1)
        mock_print_to_stderr.assert_called_once_with(
            f"Error: {self.report_message_text}"
        )

    def test_error_with_force_code(self, mock_print_to_stderr):
        with self.assertRaises(SystemExit) as cm:
            process_library_reports(
                [
                    reports.ReportItem.error(
                        self.report_message, force_code=reports.codes.FORCE
                    )
                ],
                exit_on_error=True,
            )
        self.assertEqual(cm.exception.code, 1)
        mock_print_to_stderr.assert_called_once_with(
            f"Error: {self.report_message_text}, use --force to override"
        )

    def test_context(self, mock_print_to_stderr):
        report_items = [
            reports.ReportItem.info(
                self.report_message, context=reports.ReportItemContext("node-A")
            ),
            reports.ReportItem.error(
                self.report_message, context=reports.ReportItemContext("node-B")
            ),
        ]

        process_library_reports(report_items, exit_on_error=False)

        mock_print_to_stderr.assert_has_calls(
            [
                mock.call(f"node-A: {self.report_message_text}"),
                mock.call(f"Error: node-B: {self.report_message_text}"),
            ]
        )
        self.assertEqual(mock_print_to_stderr.call_count, 2)

    def test_do_not_include_debug(self, mock_print_to_stderr):
        report_items = [
            reports.ReportItem.debug(self.report_message),
            reports.ReportItem.warning(self.report_message),
        ]

        process_library_reports(report_items, include_debug=False)

        mock_print_to_stderr.assert_called_once_with(
            f"Warning: {self.report_message_text}"
        )
