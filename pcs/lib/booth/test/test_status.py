from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

try:
    # python 2
    #pylint: disable=unused-import
    from urlparse import parse_qs as url_decode
except ImportError:
    # python 3
    from urllib.parse import parse_qs as url_decode

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import assert_raise_library_error

from pcs import settings
from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.external import CommandRunner
import pcs.lib.booth.status as lib


class GetDaemonStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_daemon_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "status"]
        )

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_daemon_status(self.mock_run, "name"))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "status", "-c", "name"]
        )

    def test_daemon_not_running(self):
        self.mock_run.run.return_value = ("", "error", 7)
        self.assertEqual("", lib.get_daemon_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "status"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_daemon_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_DAEMON_STATUS_ERROR,
                {"reason": "error\nout"}
            )
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "status"]
        )


class GetTicketsStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_tickets_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "list"]
        )

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual(
            "output", lib.get_tickets_status(self.mock_run, "name")
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "list", "-c", "name"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_tickets_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_TICKET_STATUS_ERROR,
                {
                    "reason": "error\nout"
                }
            )
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "list"]
        )


class GetPeersStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_peers_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "peers"]
        )

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_peers_status(self.mock_run, "name"))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "peers", "-c", "name"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_peers_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_PEERS_STATUS_ERROR,
                {
                    "reason": "error\nout"
                }
            )
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_binary, "peers"]
        )
