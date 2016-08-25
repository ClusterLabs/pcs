from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import assert_raise_library_error

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.external import CommandRunner

import pcs.lib.corosync.qdevice_client as lib


class GetStatusTextTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.qdevice_tool = "/usr/sbin/corosync-qdevice-tool"

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.get_status_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([
            self.qdevice_tool, "-s"
        ])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.get_status_text(self.mock_runner, True)
        )
        self.mock_runner.run.assert_called_once_with([
            self.qdevice_tool, "-s", "-v"
        ])

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 1)
        assert_raise_library_error(
            lambda: lib.get_status_text(self.mock_runner),
            (
                severity.ERROR,
                report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                {
                    "reason": "status error\nsome info",
                }
            )
        )
        self.mock_runner.run.assert_called_once_with([
            self.qdevice_tool, "-s"
        ])

