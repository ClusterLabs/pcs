import logging
from unittest import TestCase, mock

from pcs.common import reports


class ReportProcessorToLog(TestCase):
    _REPORT_MESSAGE = reports.messages.ParseErrorCorosyncConf()
    _EXPECTED_MESSAGE = "Unable to parse corosync config"

    def setUp(self):
        self.mock_logger = mock.MagicMock(spec_set=logging.Logger)
        self.report_processor = reports.processor.ReportProcessorToLog(
            self.mock_logger
        )

    def test_log_error(self):
        self.report_processor.report(
            reports.ReportItem.error(self._REPORT_MESSAGE)
        )
        self.mock_logger.error.assert_called_once_with(self._EXPECTED_MESSAGE)
        self.mock_logger.warning.assert_not_called()
        self.mock_logger.info.assert_not_called()
        self.mock_logger.debug.assert_not_called()

    def test_log_warning(self):
        self.report_processor.report(
            reports.ReportItem.warning(self._REPORT_MESSAGE)
        )
        self.mock_logger.warning.assert_called_once_with(self._EXPECTED_MESSAGE)
        self.mock_logger.error.assert_not_called()
        self.mock_logger.info.assert_not_called()
        self.mock_logger.debug.assert_not_called()

    def test_log_deprecation(self):
        self.report_processor.report(
            reports.ReportItem.deprecation(self._REPORT_MESSAGE)
        )
        self.mock_logger.warning.assert_called_once_with(self._EXPECTED_MESSAGE)
        self.mock_logger.error.assert_not_called()
        self.mock_logger.info.assert_not_called()
        self.mock_logger.debug.assert_not_called()

    def test_log_info(self):
        self.report_processor.report(
            reports.ReportItem.info(self._REPORT_MESSAGE)
        )
        self.mock_logger.info.assert_called_once_with(self._EXPECTED_MESSAGE)
        self.mock_logger.error.assert_not_called()
        self.mock_logger.warning.assert_not_called()
        self.mock_logger.debug.assert_not_called()

    def test_log_debug(self):
        self.report_processor.report(
            reports.ReportItem.debug(self._REPORT_MESSAGE)
        )
        self.mock_logger.debug.assert_called_once_with(self._EXPECTED_MESSAGE)
        self.mock_logger.error.assert_not_called()
        self.mock_logger.warning.assert_not_called()
        self.mock_logger.info.assert_not_called()

    def test_log_with_context(self):
        self.report_processor.report(
            reports.ReportItem.error(
                self._REPORT_MESSAGE, context=reports.ReportItemContext("node")
            )
        )
        self.mock_logger.error.assert_called_once_with(
            f"node: {self._EXPECTED_MESSAGE}"
        )
