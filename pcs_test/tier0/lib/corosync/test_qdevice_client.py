from unittest import (
    TestCase,
    mock,
)

import pcs.lib.corosync.qdevice_client as lib
from pcs import settings
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.external import CommandRunner

from pcs_test.tools.assertions import assert_raise_library_error


class GetStatusTextTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.qdevice_tool = settings.corosync_qdevice_tool_exec

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual("status info", lib.get_status_text(self.mock_runner))
        self.mock_runner.run.assert_called_once_with([self.qdevice_tool, "-s"])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info", lib.get_status_text(self.mock_runner, True)
        )
        self.mock_runner.run.assert_called_once_with(
            [self.qdevice_tool, "-s", "-v"]
        )

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 1)
        assert_raise_library_error(
            lambda: lib.get_status_text(self.mock_runner),
            (
                severity.ERROR,
                report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                {
                    "reason": "status error\nsome info",
                    "node": "",
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with([self.qdevice_tool, "-s"])
