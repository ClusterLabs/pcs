from unittest import TestCase, mock

from pcs.cli.reports.processor import (
    ReportProcessorToConsole,
    report_and_exit_on_error,
)
from pcs.common import reports


# error, warning and deprecation reports are printed via
# pcs.cli.reports.output.print_to_stderr, while info and debug reports are
# printed via pcs.cli.reports.processor.print_to_stderr.
@mock.patch("pcs.cli.reports.processor.print_to_stderr")
@mock.patch("pcs.cli.reports.output.print_to_stderr")
class ReportAndExitOnError(TestCase):
    report_message = reports.messages.NoActionNecessary()
    report_message_text = report_message.message

    def setUp(self):
        self.report_processor = ReportProcessorToConsole()

    def test_no_reports(self, mock_out_stderr, mock_proc_stderr):
        with self.assertRaises(SystemExit) as cm:
            report_and_exit_on_error(self.report_processor, [])
        self.assertEqual(cm.exception.code, 1)
        mock_out_stderr.assert_called_once_with(
            "Error: Errors have occurred, therefore pcs is unable to continue"
        )
        mock_proc_stderr.assert_not_called()

    def test_exit_on_error(self, mock_out_stderr, mock_proc_stderr):
        with self.assertRaises(SystemExit) as cm:
            report_and_exit_on_error(
                self.report_processor,
                [reports.ReportItem.error(self.report_message)],
            )
        self.assertEqual(cm.exception.code, 1)
        mock_out_stderr.assert_called_once_with(
            f"Error: {self.report_message_text}"
        )
        mock_proc_stderr.assert_not_called()
        self.assertTrue(self.report_processor.has_errors)

    def test_no_exit_without_errors(self, mock_out_stderr, mock_proc_stderr):
        # Reports which are not errors are printed, but do not cause the program
        # to exit.
        report_and_exit_on_error(
            self.report_processor,
            [
                reports.ReportItem.info(self.report_message),
                reports.ReportItem.warning(self.report_message),
                reports.ReportItem.deprecation(self.report_message),
            ],
        )
        self.assertFalse(self.report_processor.has_errors)
        mock_proc_stderr.assert_called_once_with(self.report_message_text)
        mock_out_stderr_calls = [
            mock.call(f"Warning: {self.report_message_text}"),
            mock.call(f"Deprecation Warning: {self.report_message_text}"),
        ]
        mock_out_stderr.assert_has_calls(mock_out_stderr_calls)
        self.assertEqual(mock_out_stderr.call_count, len(mock_out_stderr_calls))

    def test_exit_when_processor_already_has_errors(
        self, mock_out_stderr, mock_proc_stderr
    ):
        # has_errors is cumulative: once the report processor has seen an error,
        # report_and_exit_on_error exits even when the passed report list itself
        # contains no error.
        self.report_processor.report(
            reports.ReportItem.error(self.report_message)
        )
        self.assertTrue(self.report_processor.has_errors)

        with self.assertRaises(SystemExit) as cm:
            report_and_exit_on_error(
                self.report_processor,
                [reports.ReportItem.warning(self.report_message)],
            )
        self.assertEqual(cm.exception.code, 1)
        mock_out_stderr.assert_has_calls(
            [mock.call(f"Warning: {self.report_message_text}")]
        )
        mock_proc_stderr.assert_not_called()
