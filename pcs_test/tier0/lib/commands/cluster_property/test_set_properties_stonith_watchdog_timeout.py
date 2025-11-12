from unittest import TestCase, mock

from pcs import settings
from pcs.common import reports
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import get_test_resource as rc

from .crm_attribute_mixins import CrmAttributeLoadMetadataMixin
from .fixtures import fixture_crm_config_properties


class StonithWatchdogTimeoutMixin:
    sbd_enabled = None

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "10"})]
            )
        )
        self.load_fake_agent_metadata()
        self.config.services.is_enabled("sbd", return_value=self.sbd_enabled)

    def _set_success(self, options_dict):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", options_dict)]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(), options_dict, []
        )
        self.env_assist.assert_reports([])

    def _set_invalid_value(self, forced=False):
        self.config.remove("services.is_enabled")
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "15x"},
                [] if not forced else [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="stonith-watchdog-timeout",
                    option_value="15x",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_set_invalid_value(self):
        self._set_invalid_value(forced=False)

    def test_set_invalid_value_forced(self):
        self._set_invalid_value(forced=True)


class SetStonithWatchdogTimeoutSBDIsDisabledMixin(StonithWatchdogTimeoutMixin):
    sbd_enabled = False

    def test_set_empty(self):
        self._set_success({"stonith-watchdog-timeout": ""})

    def test_set_zero(self):
        self._set_success({"stonith-watchdog-timeout": "0"})

    def test_set_zero_time_suffix(self):
        self._set_success({"stonith-watchdog-timeout": "0s"})

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                ),
            ]
        )

    def test_set_not_zero_or_empty_forced(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_not_set_up",
                ),
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
class TestSetStonithWatchdogTimeoutSBDIsDisabledCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsDisabledMixin,
    TestCase,
):
    pass


class SetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixin(
    StonithWatchdogTimeoutMixin
):
    sbd_enabled = True

    def test_set_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(), {"stonith-watchdog-timeout": ""}, []
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_empty_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": ""},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_zero(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "0"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_set_zero_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "0s"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "0s"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_UNSET,
                    reason="sbd_set_up_without_devices",
                )
            ]
        )

    def test_equal_to_timeout(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "10"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="10",
                )
            ]
        )

    def test_too_small(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "9s"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    force_code=reports.codes.FORCE,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9s",
                )
            ]
        )

    def test_too_small_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "9s"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "9s"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_TOO_SMALL,
                    cluster_sbd_watchdog_timeout=10,
                    entered_watchdog_timeout="9s",
                )
            ]
        )

    def test_more_than_timeout(self):
        self._set_success({"stonith-watchdog-timeout": "11s"})


@mock.patch("pcs.lib.sbd._get_local_sbd_watchdog_timeout", lambda: 10)
@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", list)
class TestSetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixinCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsEnabledWatchdogOnlyMixin,
    TestCase,
):
    pass


class SetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesMixin(
    StonithWatchdogTimeoutMixin
):
    sbd_enabled = True

    def test_set_empty(self):
        self._set_success({"stonith-watchdog-timeout": ""})

    def test_set_to_zero(self):
        self._set_success({"stonith-watchdog-timeout": "0"})

    def test_set_to_zero_time_suffix(self):
        self._set_success({"stonith-watchdog-timeout": "0min"})

    def test_set_not_zero_or_empty(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.set_properties(
                self.env_assist.get_env(),
                {"stonith-watchdog-timeout": "20"},
                [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    force_code=reports.codes.FORCE,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )

    def test_set_not_zero_or_empty_forced(self):
        self.config.env.push_cib(
            crm_config=fixture_crm_config_properties(
                [("cib-bootstrap-options", {"stonith-watchdog-timeout": "20"})]
            )
        )
        cluster_property.set_properties(
            self.env_assist.get_env(),
            {"stonith-watchdog-timeout": "20"},
            [reports.codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.STONITH_WATCHDOG_TIMEOUT_CANNOT_BE_SET,
                    reason="sbd_set_up_with_devices",
                )
            ]
        )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_rng/api/api-result.rng"),
)
@mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["dev1", "dev2"])
class TestSetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesCrmAttributeMetadata(
    CrmAttributeLoadMetadataMixin,
    SetStonithWatchdogTimeoutSBDIsEnabledSharedDevicesMixin,
    TestCase,
):
    pass
