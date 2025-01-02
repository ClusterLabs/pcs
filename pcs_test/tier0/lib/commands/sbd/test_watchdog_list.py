from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands.sbd import get_local_available_watchdogs

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import outdent


def _watchdog_fixture(identity, driver, caution=None):
    return dict(
        identity=identity,
        driver="<unknown>" if driver is None else driver,
        caution=caution,
    )


class GetLocalAvailableWatchdogs(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_one_device(self):
        self.config.runner.sbd.list_watchdogs(
            outdent(
                """
        Discovered 1 watchdog devices:

        [1] /dev/watchdog
        Identity: i6300ESB timer
        Driver: <unknown>
        """
            )
        )
        self.assertEqual(
            {"/dev/watchdog": _watchdog_fixture("i6300ESB timer", None)},
            get_local_available_watchdogs(self.env_assist.get_env()),
        )

    def test_multiple_devices(self):
        self.config.runner.sbd.list_watchdogs(
            outdent(
                """
        Discovered 3 watchdog devices:

        [1] /dev/watchdog
        Identity: i6300ESB timer
        Driver: <unknown>

        [2] /dev/watchdog2
        Identity: iTCO_wdt
        Driver: iTCO_wdt

        [3] /dev/watchdog3
        Identity: iTCO_wdt
        Driver: iTCO_wdt
        """
            )
        )
        self.assertEqual(
            {
                "/dev/watchdog": _watchdog_fixture("i6300ESB timer", None),
                "/dev/watchdog2": _watchdog_fixture("iTCO_wdt", "iTCO_wdt"),
                "/dev/watchdog3": _watchdog_fixture("iTCO_wdt", "iTCO_wdt"),
            },
            get_local_available_watchdogs(self.env_assist.get_env()),
        )

    def test_with_caution(self):
        self.config.runner.sbd.list_watchdogs(
            outdent(
                """
        Discovered 4 watchdog devices:

        [1] /dev/watchdog
        Identity: i6300ESB timer
        Driver: <unknown>

        [2] /dev/watchdog0
        Identity: Software Watchdog
        Driver: softdog
        CAUTION: Not recommended for use with sbd.

        [3] /dev/watchdog1
        Identity: iTCO_wdt
        Driver: iTCO_wdt

        [4] /dev/watchdog2
        Identity: Software Watchdog
        Driver: softdog
        CAUTION: Not recommended for use with sbd.
        """
            )
        )
        self.assertEqual(
            {
                "/dev/watchdog": _watchdog_fixture("i6300ESB timer", None),
                "/dev/watchdog0": _watchdog_fixture(
                    "Software Watchdog",
                    "softdog",
                    "Not recommended for use with sbd.",
                ),
                "/dev/watchdog1": _watchdog_fixture("iTCO_wdt", "iTCO_wdt"),
                "/dev/watchdog2": _watchdog_fixture(
                    "Software Watchdog",
                    "softdog",
                    "Not recommended for use with sbd.",
                ),
            },
            get_local_available_watchdogs(self.env_assist.get_env()),
        )

    def test_failure(self):
        reason = "some error"
        self.config.runner.sbd.list_watchdogs("", stderr=reason, returncode=1)
        self.env_assist.assert_raise_library_error(
            lambda: get_local_available_watchdogs(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.SBD_LIST_WATCHDOG_ERROR,
                    reason=reason,
                )
            ],
            expected_in_processor=False,
        )
