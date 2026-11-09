from unittest import TestCase, mock

from pcs.cli.reports.processor import (
    ReportProcessorToConsole,
    report_and_exit_on_error,
)
from pcs.common import reports
from pcs.common.reports import codes as reports_codes

REPORT_MESSAGE = reports.messages.NoActionNecessary()
MESSAGE_TEXT = REPORT_MESSAGE.message


# Error, warning and deprecation reports are printed via
# pcs.cli.reports.output.print_to_stderr, while info and debug reports are
# printed via pcs.cli.reports.processor.print_to_stderr. Both are patched so the
# tests can tell the two output paths apart.
@mock.patch("pcs.cli.reports.processor.print_to_stderr")
@mock.patch("pcs.cli.reports.output.print_to_stderr")
class ReportProcessorToConsoleTest(TestCase):
    def setUp(self):
        self.report_processor = ReportProcessorToConsole()

    # Test reporting severities

    def test_error(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(reports.ReportItem.error(REPORT_MESSAGE))
        mock_out_stderr.assert_called_once_with(f"Error: {MESSAGE_TEXT}")
        mock_proc_stderr.assert_not_called()
        self.assertTrue(self.report_processor.has_errors)

    def test_warning(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(reports.ReportItem.warning(REPORT_MESSAGE))
        mock_out_stderr.assert_called_once_with(f"Warning: {MESSAGE_TEXT}")
        mock_proc_stderr.assert_not_called()
        self.assertFalse(self.report_processor.has_errors)

    def test_deprecation(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(
            reports.ReportItem.deprecation(REPORT_MESSAGE)
        )
        mock_out_stderr.assert_called_once_with(
            f"Deprecation Warning: {MESSAGE_TEXT}"
        )
        mock_proc_stderr.assert_not_called()
        self.assertFalse(self.report_processor.has_errors)

    def test_info(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(reports.ReportItem.info(REPORT_MESSAGE))
        mock_proc_stderr.assert_called_once_with(MESSAGE_TEXT)
        mock_out_stderr.assert_not_called()
        self.assertFalse(self.report_processor.has_errors)

    def test_debug_suppressed_by_default(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self.report_processor.report(reports.ReportItem.debug(REPORT_MESSAGE))
        mock_out_stderr.assert_not_called()
        mock_proc_stderr.assert_not_called()

    def test_debug_printed_in_debug_mode(
        self, mock_out_stderr, mock_proc_stderr
    ):
        report_processor = ReportProcessorToConsole(debug=True)
        report_processor.report(reports.ReportItem.debug(REPORT_MESSAGE))
        mock_proc_stderr.assert_called_once_with(MESSAGE_TEXT)
        mock_out_stderr.assert_not_called()

    def test_report_list(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report_list(
            [
                reports.ReportItem.info(REPORT_MESSAGE),
                reports.ReportItem.warning(REPORT_MESSAGE),
                reports.ReportItem.error(REPORT_MESSAGE),
            ]
        )
        mock_proc_stderr.assert_called_once_with(MESSAGE_TEXT)
        mock_out_stderr_calls = [
            mock.call(f"Warning: {MESSAGE_TEXT}"),
            mock.call(f"Error: {MESSAGE_TEXT}"),
        ]
        mock_out_stderr.assert_has_calls(mock_out_stderr_calls)
        self.assertEqual(mock_out_stderr.call_count, len(mock_out_stderr_calls))
        self.assertTrue(self.report_processor.has_errors)

    @mock.patch("pcs.cli.reports.processor.report_item_msg_from_dto")
    def test_empty_message_not_printed(
        self, mock_msg_from_dto, mock_out_stderr, mock_proc_stderr
    ):
        mock_msg_from_dto.return_value = mock.Mock(message="")
        self.report_processor.report(reports.ReportItem.info(REPORT_MESSAGE))
        mock_out_stderr.assert_not_called()
        mock_proc_stderr.assert_not_called()

    # Test adding --force, --skip-offline and context

    def test_error_with_force_code(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(
            reports.ReportItem.error(
                REPORT_MESSAGE, force_code=reports_codes.FORCE
            )
        )
        mock_out_stderr.assert_called_once_with(
            f"Error: {MESSAGE_TEXT}, use --force to override"
        )
        mock_proc_stderr.assert_not_called()

    def test_error_with_skip_offline_force_code(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self.report_processor.report(
            reports.ReportItem.error(
                REPORT_MESSAGE,
                force_code=reports_codes.SKIP_OFFLINE_NODES,
            )
        )
        mock_out_stderr.assert_called_once_with(
            f"Error: {MESSAGE_TEXT}, use --skip-offline to override"
        )
        mock_proc_stderr.assert_not_called()

    def test_context_added_to_error(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(
            reports.ReportItem.error(
                REPORT_MESSAGE,
                context=reports.ReportItemContext(node="node1"),
            )
        )
        mock_out_stderr.assert_called_once_with(f"Error: node1: {MESSAGE_TEXT}")
        mock_proc_stderr.assert_not_called()

    def test_context_added_to_info(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.report(
            reports.ReportItem.info(
                REPORT_MESSAGE,
                context=reports.ReportItemContext(node="node1"),
            )
        )
        mock_proc_stderr.assert_called_once_with(f"node1: {MESSAGE_TEXT}")
        mock_out_stderr.assert_not_called()

    # Test suppressing severities

    def test_suppress_warning(self, mock_out_stderr, mock_proc_stderr):
        self.report_processor.suppress_reports_of_severity(
            [reports.ReportItemSeverity.WARNING]
        )
        self.report_processor.report_list(
            [
                reports.ReportItem.error(REPORT_MESSAGE),
                reports.ReportItem.warning(REPORT_MESSAGE),
                reports.ReportItem.info(REPORT_MESSAGE),
            ]
        )
        # The warning is suppressed, others are still printed.
        mock_out_stderr.assert_called_once_with(f"Error: {MESSAGE_TEXT}")
        mock_proc_stderr.assert_called_once_with(MESSAGE_TEXT)

    def test_debug_stays_suppressed_in_non_debug_mode(
        self, mock_out_stderr, mock_proc_stderr
    ):
        # Suppressing another severity must not re-enable debug reports.
        self.report_processor.suppress_reports_of_severity(
            [reports.ReportItemSeverity.INFO]
        )
        self.report_processor.report(reports.ReportItem.debug(REPORT_MESSAGE))
        mock_out_stderr.assert_not_called()
        mock_proc_stderr.assert_not_called()

    def test_debug_cannot_be_suppressed_in_debug_mode(
        self, mock_out_stderr, mock_proc_stderr
    ):
        # In debug mode, debug reports are printed even if explicitly suppressed.
        report_processor = ReportProcessorToConsole(debug=True)
        report_processor.suppress_reports_of_severity(
            [reports.ReportItemSeverity.DEBUG]
        )
        report_processor.report(reports.ReportItem.debug(REPORT_MESSAGE))
        mock_proc_stderr.assert_called_once_with(MESSAGE_TEXT)
        mock_out_stderr.assert_not_called()

    # Test preprocessor

    def test_preprocessor_filters_out_report(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self.report_processor.set_report_item_preprocessor(lambda item: None)
        self.report_processor.report(reports.ReportItem.info(REPORT_MESSAGE))
        mock_out_stderr.assert_not_called()
        mock_proc_stderr.assert_not_called()

    def test_preprocessor_transforms_report(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self.report_processor.set_report_item_preprocessor(
            lambda item: reports.ReportItem.warning(item.message)
        )
        self.report_processor.report(reports.ReportItem.info(REPORT_MESSAGE))
        # The info report is turned into a warning before being printed.
        mock_out_stderr.assert_called_once_with(f"Warning: {MESSAGE_TEXT}")
        mock_proc_stderr.assert_not_called()

    # Test has_waiting_timeout_error

    def test_has_waiting_timeout_error_default_is_false(
        self, mock_out_stderr, mock_proc_stderr
    ):
        del mock_out_stderr, mock_proc_stderr
        self.assertFalse(self.report_processor.has_waiting_timeout_error)

    def test_has_waiting_timeout_error_false_for_other_reports(
        self, mock_out_stderr, mock_proc_stderr
    ):
        del mock_out_stderr, mock_proc_stderr
        self.report_processor.report(reports.ReportItem.error(REPORT_MESSAGE))
        self.assertFalse(self.report_processor.has_waiting_timeout_error)

    def test_has_waiting_timeout_error_false_for_other_severities(
        self, mock_out_stderr, mock_proc_stderr
    ):
        del mock_out_stderr, mock_proc_stderr
        self.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.WaitForIdleTimedOut("timeout")
            )
        )
        self.assertFalse(self.report_processor.has_waiting_timeout_error)

    def test_has_waiting_timeout_error_true_after_wait_timeout_report(
        self, mock_out_stderr, mock_proc_stderr
    ):
        del mock_out_stderr, mock_proc_stderr
        self.report_processor.report(
            reports.ReportItem.error(
                reports.messages.WaitForIdleTimedOut("timeout")
            )
        )
        self.assertTrue(self.report_processor.has_waiting_timeout_error)

    def test_has_waiting_timeout_error_false_when_preprocessor_filters_out_report(
        self, mock_out_stderr, mock_proc_stderr
    ):
        del mock_out_stderr, mock_proc_stderr
        # The preprocessor runs before the code is inspected, so a filtered-out
        # report does not set the flag.
        self.report_processor.set_report_item_preprocessor(lambda item: None)
        self.report_processor.report(
            reports.ReportItem.error(
                reports.messages.WaitForIdleTimedOut("timeout")
            )
        )
        self.assertFalse(self.report_processor.has_waiting_timeout_error)


# error, warning and deprecation reports are printed via
# pcs.cli.reports.output.print_to_stderr, while info and debug reports are
# printed via pcs.cli.reports.processor.print_to_stderr.
@mock.patch("pcs.cli.reports.processor.print_to_stderr")
@mock.patch("pcs.cli.reports.output.print_to_stderr")
class ReportAndExitOnError(TestCase):
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

    def _assert_exit_on_error(
        self, mock_out_stderr, mock_proc_stderr, REPORT_MESSAGE, exit_code
    ):
        with self.assertRaises(SystemExit) as cm:
            report_and_exit_on_error(
                self.report_processor,
                [reports.ReportItem.error(REPORT_MESSAGE)],
            )
        self.assertEqual(cm.exception.code, exit_code)
        mock_out_stderr.assert_called_once_with(
            f"Error: {REPORT_MESSAGE.message}"
        )
        mock_proc_stderr.assert_not_called()
        self.assertTrue(self.report_processor.has_errors)

    def test_exit_on_error(self, mock_out_stderr, mock_proc_stderr):
        self._assert_exit_on_error(
            mock_out_stderr, mock_proc_stderr, REPORT_MESSAGE, 1
        )

    def test_exit_on_wait_error(self, mock_out_stderr, mock_proc_stderr):
        self._assert_exit_on_error(
            mock_out_stderr,
            mock_proc_stderr,
            reports.messages.WaitForIdleTimedOut("timeout"),
            2,
        )

    def test_no_exit_without_errors(self, mock_out_stderr, mock_proc_stderr):
        # Reports which are not errors are printed, but do not cause the program
        # to exit.
        report_and_exit_on_error(
            self.report_processor,
            [
                reports.ReportItem.info(REPORT_MESSAGE),
                reports.ReportItem.warning(REPORT_MESSAGE),
                reports.ReportItem.deprecation(REPORT_MESSAGE),
            ],
        )
        self.assertFalse(self.report_processor.has_errors)
        mock_proc_stderr.assert_called_once_with(REPORT_MESSAGE.message)
        mock_out_stderr_calls = [
            mock.call(f"Warning: {REPORT_MESSAGE.message}"),
            mock.call(f"Deprecation Warning: {REPORT_MESSAGE.message}"),
        ]
        mock_out_stderr.assert_has_calls(mock_out_stderr_calls)
        self.assertEqual(mock_out_stderr.call_count, len(mock_out_stderr_calls))

    def _assert_exit_when_processor_already_has_errors(
        self, mock_out_stderr, mock_proc_stderr, report_message, exit_code
    ):
        # has_errors is cumulative: once the report processor has seen an error,
        # report_and_exit_on_error exits even when the passed report list itself
        # contains no error.
        self.report_processor.report(reports.ReportItem.error(report_message))
        self.assertTrue(self.report_processor.has_errors)

        with self.assertRaises(SystemExit) as cm:
            report_and_exit_on_error(
                self.report_processor,
                [reports.ReportItem.warning(REPORT_MESSAGE)],
            )
        self.assertEqual(cm.exception.code, exit_code)
        mock_out_stderr.assert_has_calls(
            [mock.call(f"Warning: {REPORT_MESSAGE.message}")]
        )
        mock_proc_stderr.assert_not_called()

    def test_exit_when_processor_already_has_errors(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self._assert_exit_when_processor_already_has_errors(
            mock_out_stderr, mock_proc_stderr, REPORT_MESSAGE, 1
        )

    def test_exit_when_processor_already_has_waiting_errors(
        self, mock_out_stderr, mock_proc_stderr
    ):
        self._assert_exit_when_processor_already_has_errors(
            mock_out_stderr,
            mock_proc_stderr,
            reports.messages.WaitForIdleTimedOut("timeout"),
            2,
        )
