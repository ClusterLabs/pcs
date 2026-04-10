from unittest import TestCase

from pcs.common import file_type_codes, reports
from pcs.lib.commands import services as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class PacemakerRemoteServiceMixin:
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.service_name = "pacemaker_remote"

    def get_lib_command(self):
        raise NotImplementedError()

    def test_not_live_cib(self):
        self.config.env.set_cib_data("<cib/>")

        self.env_assist.assert_raise_library_error(
            lambda: self.get_lib_command()(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.CIB],
                ),
            ]
        )

    def test_not_live_corosync_conf(self):
        self.config.env.set_corosync_conf_data("totem {\n}\n")

        self.env_assist.assert_raise_library_error(
            lambda: self.get_lib_command()(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ]
        )

    def test_not_live_both(self):
        self.config.env.set_cib_data("<cib/>")
        self.config.env.set_corosync_conf_data("totem {\n}\n")

        self.env_assist.assert_raise_library_error(
            lambda: self.get_lib_command()(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[
                        file_type_codes.CIB,
                        file_type_codes.COROSYNC_CONF,
                    ],
                ),
            ]
        )


class PacemakerRemoteOnLocal(PacemakerRemoteServiceMixin, TestCase):
    def get_lib_command(self):
        return lib.pacemaker_remote_on_local

    def test_success(self):
        self.config.services.enable(self.service_name)
        self.config.services.start(self.service_name)

        lib.pacemaker_remote_on_local(self.env_assist.get_env())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_START,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
            ]
        )

    def test_enable_failure(self):
        self.config.services.enable(
            self.service_name, failure_msg="enable failed: permission denied"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.pacemaker_remote_on_local(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.SERVICE_ACTION_FAILED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service=self.service_name,
                    reason="enable failed: permission denied",
                    node="",
                    instance="",
                ),
            ]
        )

    def test_start_failure(self):
        self.config.services.enable(self.service_name)
        self.config.services.start(
            self.service_name, failure_msg="start failed: service timeout"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.pacemaker_remote_on_local(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
                fixture.error(
                    reports.codes.SERVICE_ACTION_FAILED,
                    action=reports.const.SERVICE_ACTION_START,
                    service=self.service_name,
                    reason="start failed: service timeout",
                    node="",
                    instance="",
                ),
            ]
        )


class PacemakerRemoteOffLocal(PacemakerRemoteServiceMixin, TestCase):
    def get_lib_command(self):
        return lib.pacemaker_remote_off_local

    def test_success(self):
        self.config.services.stop(self.service_name)
        self.config.services.disable(self.service_name)

        lib.pacemaker_remote_off_local(self.env_assist.get_env())

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
            ]
        )

    def test_stop_failure(self):
        self.config.services.stop(
            self.service_name, failure_msg="stop failed: permission denied"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.pacemaker_remote_off_local(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.SERVICE_ACTION_FAILED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service=self.service_name,
                    reason="stop failed: permission denied",
                    node="",
                    instance="",
                ),
            ]
        )

    def test_disable_failure(self):
        self.config.services.stop(self.service_name)
        self.config.services.disable(
            self.service_name, failure_msg="disable failed: service timeout"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.pacemaker_remote_off_local(self.env_assist.get_env())
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service=self.service_name,
                    node="",
                    instance="",
                ),
                fixture.error(
                    reports.codes.SERVICE_ACTION_FAILED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service=self.service_name,
                    reason="disable failed: service timeout",
                    node="",
                    instance="",
                ),
            ]
        )
