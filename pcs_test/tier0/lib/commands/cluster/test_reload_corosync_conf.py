from unittest import TestCase

from pcs.common import file_type_codes, reports
from pcs.lib.commands.cluster import config

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import corosync_conf_fixture


class TestReloadCorosyncConf(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _setup_corosync_reload(self, stdout="", stderr="", returncode=0):
        self.config.services.is_running("corosync")
        self.config.runner.corosync.reload(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
        )

    def test_not_live_corosync_conf(self):
        self.config.env.set_corosync_conf_data(corosync_conf_fixture())
        self.env_assist.assert_raise_library_error(
            lambda: config.reload_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ]
        )

    def test_corosync_not_running(self):
        self.config.services.is_running("corosync", return_value=False)
        self.env_assist.assert_raise_library_error(
            lambda: config.reload_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node="",
                ),
            ]
        )

    def test_success(self):
        self._setup_corosync_reload()
        config.reload_corosync_conf(self.env_assist.get_env())

    def test_failure(self):
        stdout = "some error output"
        self._setup_corosync_reload(
            stdout=stdout,
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.reload_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    reason=stdout,
                    node="",
                ),
            ]
        )

    def test_failure_with_header_line(self):
        self._setup_corosync_reload(
            stdout="Reloading corosync.conf...\nactual error message",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.reload_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    reason="Reloading corosync.conf...\nactual error message",
                    node="",
                ),
            ]
        )

    def test_failure_with_stderr(self):
        self._setup_corosync_reload(
            stdout="Reloading corosync.conf...\n",
            stderr="stderr error",
            returncode=1,
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.reload_corosync_conf(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    reason="stderr error\nReloading corosync.conf...",
                    node="",
                ),
            ]
        )
