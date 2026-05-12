import stat
from textwrap import dedent
from unittest import TestCase, mock

from pcs.common.reports import codes as report_codes
from pcs.common.sbd_dto import (
    SbdCheckResultDto,
    SbdDeviceStatusDto,
    SbdWatchdogStatusDto,
)
from pcs.common.services_dto import ServiceStatusDto
from pcs.lib.commands.sbd import check_sbd

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

WATCHDOG_LIST_OUTPUT = dedent(
    """
    Discovered 2 watchdog devices:

    [1] /dev/watchdog
    Identity: i6300ESB timer
    Driver: <unknown>

    [2] /dev/watchdog1
    Identity: iTCO_wdt
    Driver: iTCO_wdt
    """
)


class TestCheckSbdServiceOnly(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_all_true(self):
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.services.is_running("sbd", return_value=True)
        result = check_sbd(self.env_assist.get_env())
        self.assertEqual(
            result,
            SbdCheckResultDto(
                sbd_service=ServiceStatusDto(
                    service="sbd",
                    installed=True,
                    enabled=True,
                    running=True,
                ),
            ),
        )

    def test_not_installed(self):
        self.config.services.is_installed("sbd", return_value=False)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.services.is_running("sbd", return_value=False)
        result = check_sbd(self.env_assist.get_env())
        self.assertEqual(
            result,
            SbdCheckResultDto(
                sbd_service=ServiceStatusDto(
                    service="sbd",
                    installed=False,
                    enabled=False,
                    running=False,
                ),
            ),
        )

    def test_installed_not_enabled_not_running(self):
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.services.is_running("sbd", return_value=False)
        result = check_sbd(self.env_assist.get_env())
        self.assertEqual(
            result,
            SbdCheckResultDto(
                sbd_service=ServiceStatusDto(
                    service="sbd",
                    installed=True,
                    enabled=False,
                    running=False,
                ),
            ),
        )


class TestCheckSbdWatchdog(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.services.is_running("sbd", return_value=True)

    def test_watchdog_exists(self):
        self.config.runner.sbd.list_watchdogs(WATCHDOG_LIST_OUTPUT)
        result = check_sbd(self.env_assist.get_env(), watchdog="/dev/watchdog")
        self.assertEqual(
            result.watchdog,
            SbdWatchdogStatusDto(
                path="/dev/watchdog",
                exists=True,
                is_supported=True,
            ),
        )

    def test_watchdog_not_exists(self):
        self.config.runner.sbd.list_watchdogs(WATCHDOG_LIST_OUTPUT)
        result = check_sbd(
            self.env_assist.get_env(), watchdog="/dev/nonexistent"
        )
        self.assertEqual(
            result.watchdog,
            SbdWatchdogStatusDto(
                path="/dev/nonexistent",
                exists=False,
                is_supported=False,
            ),
        )

    def test_empty_watchdog_skips_check(self):
        result = check_sbd(self.env_assist.get_env(), watchdog="")
        self.assertIsNone(result.watchdog)

    def test_watchdog_query_failure(self):
        reason = "some error"
        self.config.runner.sbd.list_watchdogs("", stderr=reason, returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: check_sbd(
                self.env_assist.get_env(), watchdog="/dev/watchdog"
            ),
            [
                fixture.error(
                    report_codes.SBD_LIST_WATCHDOG_ERROR,
                    reason=reason,
                ),
            ],
            expected_in_processor=False,
        )


class TestCheckSbdDeviceList(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.services.is_running("sbd", return_value=True)

    @mock.patch("pcs.lib.sbd.os.stat")
    def test_multiple_devices(self, mock_stat):
        mock_stat.side_effect = [
            mock.Mock(st_mode=stat.S_IFBLK | 0o660),
            OSError(),
            mock.Mock(st_mode=stat.S_IFREG | 0o644),
        ]
        result = check_sbd(
            self.env_assist.get_env(),
            device_list=["/dev/sdb", "/dev/sdc", "/dev/sdd"],
        )
        self.assertEqual(
            result.device_list,
            [
                SbdDeviceStatusDto(
                    path="/dev/sdb", exists=True, is_block_device=True
                ),
                SbdDeviceStatusDto(
                    path="/dev/sdc", exists=False, is_block_device=False
                ),
                SbdDeviceStatusDto(
                    path="/dev/sdd", exists=True, is_block_device=False
                ),
            ],
        )

    def test_empty_device_list(self):
        result = check_sbd(self.env_assist.get_env(), device_list=[])
        self.assertIsNone(result.device_list)
