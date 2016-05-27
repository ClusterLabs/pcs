from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.assertions import assert_raise_library_error

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.external import CommandRunner

import pcs.lib.corosync.qdevice_net as lib


_qnetd_cert_dir = "/etc/corosync/qdevice/net/qnetd/nssdb"
_qnetd_tool = "/usr/sbin/corosync-qnetd-certutil"

@mock.patch("pcs.lib.corosync.qdevice_net.external.is_dir_nonempty")
class QdeviceSetupTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = False
        self.mock_runner.run.return_value = ("initialized", 0)

        lib.qdevice_setup(self.mock_runner)

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-i"])

    def test_cert_db_exists(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = True

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_ALREADY_INITIALIZED,
                {"model": "net"}
            )
        )

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.assert_not_called()

    def test_init_tool_fail(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = False
        self.mock_runner.run.return_value = ("test error", 1)

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "test error",
                }
            )
        )

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-i"])


@mock.patch("pcs.lib.corosync.qdevice_net.shutil.rmtree")
class QdeviceDestroyTest(TestCase):
    def test_success(self, mock_rmtree):
        lib.qdevice_destroy()
        mock_rmtree.assert_called_once_with(_qnetd_cert_dir)

    def test_cert_dir_rm_error(self, mock_rmtree):
        mock_rmtree.side_effect = EnvironmentError("test errno", "test message")
        assert_raise_library_error(
            lib.qdevice_destroy,
            (
                severity.ERROR,
                report_codes.QDEVICE_DESTROY_ERROR,
                {
                    "model": "net",
                    "reason": "test message",
                }
            )
        )
        mock_rmtree.assert_called_once_with(_qnetd_cert_dir)
