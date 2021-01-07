from functools import partial
import logging
from unittest import mock, TestCase

from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import (
    create_patcher,
    get_test_resource as rc,
)

from pcs.common import file_type_codes
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.env import LibraryEnvironment


patch_env = create_patcher("pcs.lib.env")
patch_env_object = partial(mock.patch.object, LibraryEnvironment)


class LibraryEnvironmentTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_logger(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(self.mock_logger, env.logger)

    def test_report_processor(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(self.mock_reporter, env.report_processor)

    def test_user_set(self):
        user = "testuser"
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, user_login=user
        )
        self.assertEqual(user, env.user_login)

    def test_user_not_set(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(None, env.user_login)

    def test_usergroups_set(self):
        groups = ["some", "group"]
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, user_groups=groups
        )
        self.assertEqual(groups, env.user_groups)

    def test_usergroups_not_set(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual([], env.user_groups)


class GhostFileCodes(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def _fixture_get_env(self, cib_data=None, corosync_conf_data=None):
        return LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            cib_data=cib_data,
            corosync_conf_data=corosync_conf_data,
        )

    def test_nothing(self):
        self.assertEqual(self._fixture_get_env().ghost_file_codes, [])

    def test_corosync(self):
        self.assertEqual(
            self._fixture_get_env(corosync_conf_data="x").ghost_file_codes,
            [file_type_codes.COROSYNC_CONF],
        )

    def test_cib(self):
        self.assertEqual(
            self._fixture_get_env(cib_data="x").ghost_file_codes,
            [file_type_codes.CIB],
        )

    def test_all(self):
        self.assertEqual(
            self._fixture_get_env(
                cib_data="x",
                corosync_conf_data="x",
            ).ghost_file_codes,
            sorted([file_type_codes.COROSYNC_CONF, file_type_codes.CIB]),
        )


@patch_env("CommandRunner")
class CmdRunner(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_no_options(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "LC_ALL": "C",
            },
        )

    def test_user(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        user = "testuser"
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, user_login=user
        )
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "CIB_user": user,
                "LC_ALL": "C",
            },
        )

    @patch_env("write_tmpfile")
    def test_dump_cib_file(self, mock_tmpfile, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        mock_instance = mock.MagicMock()
        mock_instance.name = rc("file.tmp")
        mock_tmpfile.return_value = mock_instance
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, cib_data="<cib />"
        )
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "LC_ALL": "C",
                "CIB_file": rc("file.tmp"),
            },
        )
        mock_tmpfile.assert_called_once_with("<cib />")


@patch_env_object("cmd_runner", lambda self: "runner")
class EnsureValidWait(TestCase):
    def setUp(self):
        self.create_env = partial(
            LibraryEnvironment,
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor(),
        )

    @property
    def env_live(self):
        return self.create_env()

    @property
    def env_fake(self):
        return self.create_env(cib_data="<cib/>")

    def test_not_raises_if_waiting_false_no_matter_if_env_is_live(self):
        self.env_live.ensure_wait_satisfiable(False)
        self.env_fake.ensure_wait_satisfiable(False)

    def test_raises_when_is_not_live(self):
        env = self.env_fake
        assert_raise_library_error(
            lambda: env.ensure_wait_satisfiable(10),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                {},
                None,
            ),
        )

    @patch_env("get_valid_timeout_seconds")
    def test_do_checks(self, get_valid_timeout):
        env = self.env_live
        env.ensure_wait_satisfiable(10)
        get_valid_timeout.assert_called_once_with(10)
