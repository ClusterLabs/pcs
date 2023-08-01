import os
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.booth.status as lib
from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.reports import ReportItemSeverity as Severities
from pcs.common.reports import codes as report_codes
from pcs.lib.booth import constants
from pcs.lib.external import CommandRunner

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.command_env import get_env_tools


class GetDaemonStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_daemon_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "status"]
        )

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_daemon_status(self.mock_run, "name"))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "status", "-c", "name"]
        )

    def test_daemon_not_running(self):
        self.mock_run.run.return_value = ("", "error", 7)
        self.assertEqual("", lib.get_daemon_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "status"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_daemon_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_DAEMON_STATUS_ERROR,
                {"reason": "error\nout"},
            ),
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "status"]
        )


class GetTicketsStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_tickets_status(self.mock_run))
        self.mock_run.run.assert_called_once_with([settings.booth_exec, "list"])

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual(
            "output", lib.get_tickets_status(self.mock_run, "name")
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "list", "-c", "name"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_tickets_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_TICKET_STATUS_ERROR,
                {"reason": "error\nout"},
            ),
        )
        self.mock_run.run.assert_called_once_with([settings.booth_exec, "list"])


class GetPeersStatusTest(TestCase):
    def setUp(self):
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)

    def test_no_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_peers_status(self.mock_run))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "peers"]
        )

    def test_with_name(self):
        self.mock_run.run.return_value = ("output", "", 0)
        self.assertEqual("output", lib.get_peers_status(self.mock_run, "name"))
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "peers", "-c", "name"]
        )

    def test_failure(self):
        self.mock_run.run.return_value = ("out", "error", 1)
        assert_raise_library_error(
            lambda: lib.get_peers_status(self.mock_run),
            (
                Severities.ERROR,
                report_codes.BOOTH_PEERS_STATUS_ERROR,
                {"reason": "error\nout"},
            ),
        )
        self.mock_run.run.assert_called_once_with(
            [settings.booth_exec, "peers"]
        )


class CheckAuthfileMisconfiguration(TestCase):
    def setUp(self):
        self.instance_name = "instance_name"
        self.config_path = os.path.join(
            settings.booth_config_dir, f"{self.instance_name}.conf"
        )
        self.env_assist, self.config = get_env_tools(self)

    def _run(self):
        env = self.env_assist.get_env()
        return lib.check_authfile_misconfiguration(
            env.get_booth_env(self.instance_name), env.report_processor
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_nothing_enabled(self):
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_file_doesnt_exist_set_enabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            exists=False,
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_file_doesnt_exist_unset_enabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            exists=False,
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_file_doesnt_exist_both_enabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            exists=False,
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_set_enabled_no_authfile(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                """
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_set_enabled_authfile_enable_missing(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                """
                site = 1.1.1.1
                authfile = /path/to/authfile
                """
            ).encode("utf-8"),
        )
        self.assertEqual(
            self._run(),
            reports.messages.BoothAuthfileNotUsed(self.instance_name),
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_set_enabled_authfile_disabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                f"""
                site = 1.1.1.1
                authfile = /path/to/authfile
                {constants.AUTHFILE_FIX_OPTION} = no
                """
            ).encode("utf-8"),
        )
        self.assertEqual(
            self._run(),
            reports.messages.BoothAuthfileNotUsed(self.instance_name),
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_set_enabled_authfile_enabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                f"""
                site = 1.1.1.1
                authfile = /path/to/authfile
                {constants.AUTHFILE_FIX_OPTION} = on
                """
            ).encode("utf-8"),
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_set_and_unset_enabled(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                f"""
                site = 1.1.1.1
                authfile = /path/to/authfile
                {constants.AUTHFILE_FIX_OPTION} = yes
                """
            ).encode("utf-8"),
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_unset_enabled_option_missing(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                """
                site = 1.1.1.1
                authfile = /path/to/authfile
                """
            ).encode("utf-8"),
        )
        self.assertIsNone(self._run())

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_unset_enabled_authfile_enable_present(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                f"""
                site = 1.1.1.1
                authfile = /path/to/authfile
                {constants.AUTHFILE_FIX_OPTION} = 0
                """
            ).encode("utf-8"),
        )
        self.assertEqual(
            self._run(),
            reports.messages.BoothUnsupportedOptionEnableAuthfile(
                self.instance_name
            ),
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_config_read_failure(self):
        read_failure_reason = "read failed"
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            exception_msg=read_failure_reason,
        )
        self.assertIsNone(self._run())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    operation="read",
                    reason=read_failure_reason,
                    file_path=self.config_path,
                )
            ]
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_config_parsing_failed(self):
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            content=dedent(
                """
                site = 1.1.1.1
                invalid ' option
                """
            ).encode("utf-8"),
        )
        self.assertIsNone(self._run())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.BOOTH_CONFIG_UNEXPECTED_LINES,
                    line_list=["invalid ' option"],
                    file_path=self.config_path,
                )
            ]
        )
