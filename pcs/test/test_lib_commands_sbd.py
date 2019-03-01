import logging
from unittest import mock, TestCase

from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.integration_lib import Runner
from pcs.test.tools.command_env.mock_runner import Call

from pcs import settings
from pcs.common import report_codes
from pcs.common.node_communicator import RequestTarget
from pcs.lib.errors import (
    ReportItemSeverity as Severities,
    LibraryError,
    ReportItem,
)
from pcs.lib.env import LibraryEnvironment
import pcs.lib.commands.sbd as cmd_sbd

# pylint: disable=protected-access, no-self-use


runner = Runner()


def _assert_equal_list_of_dictionaries_without_order(expected, actual):
    for item in actual:
        if item not in expected:
            raise AssertionError("Given but not expected: {0}".format(item))
    for item in expected:
        if item not in actual:
            raise AssertionError("Expected but not given: {0}".format(item))


class ValidateSbdOptionsTest(TestCase):
    def setUp(self):
        self.allowed_sbd_options = sorted([
            "SBD_DELAY_START", "SBD_STARTMODE", "SBD_WATCHDOG_TIMEOUT"
        ])

    def test_all_ok(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean"
        }
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_unknown_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value"
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_UNKNOWN", "another_unknown_option"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                    force_code=report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_unknown_options_forced(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value"
        }
        # just make sure there is no exception raised
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config, allow_unknown_opts=True),
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_UNKNOWN", "another_unknown_option"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ]
        )


    def test_unsupported_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_OPTS": "  ",
            "SBD_DEVICE": "/dev/vda",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_DEVICE"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_invalid_and_unsupported_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_UNKNOWN": "",
            "SBD_OPTS": "  "
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=sorted(["SBD_WATCHDOG_DEV", "SBD_OPTS"]),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["SBD_UNKNOWN"],
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                    force_code=report_codes.FORCE_OPTIONS,
                ),
            ]
        )

    def test_invalid_and_unsupported_options_forced(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_UNKNOWN": "",
            "SBD_OPTS": "  ",
            "SBD_PACEMAKER": "false",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config, allow_unknown_opts=True),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["SBD_UNKNOWN"],
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_watchdog_timeout_is_not_present(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_STARTMODE": "clean"
        }
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_watchdog_timeout_is_nonnegative_int(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": "-1",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": "-1",
                        "allowed_values": "a non-negative integer",
                    },
                    None
                )
            ]
        )

    def test_watchdog_timeout_is_not_int(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": "not int",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": "not int",
                        "allowed_values": "a non-negative integer",
                    },
                    None
                )
            ]
        )

    def test_watchdog_timeout_is_none(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": None,
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": None,
                        "allowed_values": "a non-negative integer",
                    },
                    None
                )
            ]
        )


class ValidateWatchdogDictTest(TestCase):
    def test_all_ok(self):
        watchdog_dict = {
            "node1": "/dev/watchdog1",
            "node2": "/dev/watchdog2",
        }
        self.assertEqual([], cmd_sbd._validate_watchdog_dict(watchdog_dict))

    def test_some_not_ok(self):
        watchdog_dict = {
            "node1": "",
            "node2": None,
            "node3": "/dev/watchdog",
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_watchdog_dict(watchdog_dict),
            [
                (
                    Severities.ERROR,
                    report_codes.WATCHDOG_INVALID,
                    {"watchdog": watchdog}
                ) for watchdog in ["", None]
            ]
        )


class GetFullTargetDictTest(TestCase):
    def setUp(self):
        self.target_list = [
            RequestTarget("node{0}".format(i)) for i in range(1, 4)
        ]

    def test_not_using_default(self):
        target_dict = {
            "node" + str(i): "val" + str(i) for i in range(4)
        }
        expected = {
            self.target_list[0].label: "val1",
            self.target_list[1].label: "val2",
            self.target_list[2].label: "val3",
        }
        self.assertEqual(
            expected,
            cmd_sbd._get_full_target_dict(self.target_list, target_dict, None)
        )

    def test_using_default(self):
        target_dict = {
            "node" + str(i): "val" + str(i) for i in range(3)
        }
        default = "default"
        expected = {
            self.target_list[0].label: "val1",
            self.target_list[1].label: "val2",
            self.target_list[2].label: default,
        }
        self.assertEqual(
            expected,
            cmd_sbd._get_full_target_dict(
                self.target_list, target_dict, default
            )
        )


@mock.patch("pcs.lib.sbd.get_local_sbd_config")
class GetLocalSbdConfigTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)

    def test_success(self, mock_config):
        mock_config.return_value = """
# This file has been generated by pcs.
SBD_OPTS="-n node1"
SBD_WATCHDOG_DEV=/dev/watchdog
SBD_WATCHDOG_TIMEOUT=0
"""

        self.assertEqual(
            {
                "SBD_OPTS": '"-n node1"',
                "SBD_WATCHDOG_DEV": "/dev/watchdog",
                "SBD_WATCHDOG_TIMEOUT": "0"
            },
            cmd_sbd.get_local_sbd_config(self.mock_env)
        )
        self.assertEqual(1, mock_config.call_count)

    def test_file_error(self, mock_config):
        mock_config.side_effect = LibraryError(ReportItem.error(
            report_codes.UNABLE_TO_GET_SBD_CONFIG,
        ))
        assert_raise_library_error(
            lambda: cmd_sbd.get_local_sbd_config(self.mock_env),
            (
                Severities.ERROR,
                report_codes.UNABLE_TO_GET_SBD_CONFIG,
                {}
            )
        )


class CommonTest(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patcher = mock.patch.object(
            LibraryEnvironment,
            "cmd_runner",
            lambda self: runner
        )
        cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.patcher.stop()

    def setUp(self):
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )


class InitializeBlockDevicesTest(CommonTest):
    def fixture_sbd_init(
        self, device_list, options, stdout="", stderr="", return_code=0
    ):
        cmd = ["sbd"]
        for device in device_list:
            cmd += ["-d", device]

        for opt, val in options:
            cmd += [opt, val]

        cmd.append("create")
        return [Call(" ".join(cmd), stdout, stderr, return_code)]

    def fixture_invalid_value(self, option, value):
        return (
            Severities.ERROR,
            report_codes.INVALID_OPTION_VALUE,
            {
                "option_name": option,
                "option_value": value,
                "allowed_values": "a non-negative integer",
            }
        )

    def test_all_options(self):
        device_list = ["dev1", "dev2"]
        option_dict = {
            "watchdog-timeout": "1",
            "loop-timeout": "10",
            "allocate-timeout": "3",
            "msgwait-timeout": "2",

        }
        runner.set_runs(self.fixture_sbd_init(
            device_list,
            [
                ("-2", "3"),
                ("-3", "10"),
                ("-4", "2"),
                ("-1", "1"),
            ]
        ))
        cmd_sbd.initialize_block_devices(self.env, device_list, option_dict)
        runner.assert_everything_launched()
        self.env.report_processor.assert_reports([
            (
                Severities.INFO,
                report_codes.SBD_DEVICE_INITIALIZATION_STARTED,
                {"device_list": device_list}
            ),
            (
                Severities.INFO,
                report_codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
                {"device_list": device_list}
            ),
        ])

    def test_no_options(self):
        device_list = ["dev1", "dev2"]
        runner.set_runs(self.fixture_sbd_init(device_list, {}))
        cmd_sbd.initialize_block_devices(self.env, device_list, {})
        runner.assert_everything_launched()
        self.env.report_processor.assert_reports([
            (
                Severities.INFO,
                report_codes.SBD_DEVICE_INITIALIZATION_STARTED,
                {"device_list": device_list}
            ),
            (
                Severities.INFO,
                report_codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
                {"device_list": device_list}
            ),
        ])

    def test_validation_failed(self):
        option_dict = {
            "unknown_option": "val",
            "watchdog-timeout": "-1",
            "another_one": "-1",
            "loop-timeout": "-3",
            "allocate-timeout": "-3",
            "msgwait-timeout": "-2",
        }
        allowed_options = [
            "watchdog-timeout", "loop-timeout", "allocate-timeout",
            "msgwait-timeout",
        ]
        assert_raise_library_error(
            lambda: cmd_sbd.initialize_block_devices(self.env, [], option_dict),
            (
                Severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {
                    "option_names": ["device"],
                    "option_type": None,
                }
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": sorted(["another_one", "unknown_option"]),
                    "option_type": "option",
                    "allowed": sorted(allowed_options),
                    "allowed_patterns": [],
                }
            ),
            *[
                self.fixture_invalid_value(opt, option_dict[opt])
                for opt in allowed_options
            ]
        )


@mock.patch("os.path.exists")
@mock.patch("pcs.lib.sbd.get_local_sbd_config")
@mock.patch("pcs.lib.external.is_systemctl", lambda: True)
class GetLocalDevicesInfoTest(CommonTest):
    def fixture_sbd_enabled(self, enabled):
        cmd = [settings.systemctl_binary, "is-enabled", "sbd.service"]
        return [Call(" ".join(cmd), returncode=0 if enabled else 1)]

    def fixture_sbd_info(self, device, stdout="", return_code=0):
        cmd = ["sbd", "-d", device, "list"]
        return [Call(" ".join(cmd), stdout, returncode=return_code)]

    def fixture_sbd_dump(self, device, stdout="", return_code=0):
        cmd = ["sbd", "-d", device, "dump"]
        return [Call(" ".join(cmd), stdout, returncode=return_code)]

    def test_success(self, mock_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_config.return_value = """
SBD_DEVICE="/dev1;/dev2"
        """
        runner.set_runs(
            self.fixture_sbd_enabled(True) +
            self.fixture_sbd_info("/dev1", "1") +
            self.fixture_sbd_info("/dev2", "2")
        )
        expected_output = [
            {
                "device": "/dev1",
                "list": "1",
                "dump": None,
            },
            {
                "device": "/dev2",
                "list": "2",
                "dump": None,
            },
        ]
        self.assertEqual(
            expected_output, cmd_sbd.get_local_devices_info(self.env)
        )
        runner.assert_everything_launched()
        mock_config.assert_called_once_with()
        mock_config_exists.assert_called_once_with(settings.sbd_config)

    def test_with_dump(self, mock_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_config.return_value = """
SBD_DEVICE="/dev1;/dev2"
        """
        runner.set_runs(
            self.fixture_sbd_enabled(True) +
            self.fixture_sbd_info("/dev1", "1") +
            self.fixture_sbd_dump("/dev1", "3") +
            self.fixture_sbd_info("/dev2", "2") +
            self.fixture_sbd_dump("/dev2", "4")
        )
        expected_output = [
            {
                "device": "/dev1",
                "list": "1",
                "dump": "3",
            },
            {
                "device": "/dev2",
                "list": "2",
                "dump": "4",
            },
        ]
        self.assertEqual(
            expected_output, cmd_sbd.get_local_devices_info(self.env, dump=True)
        )
        runner.assert_everything_launched()
        mock_config.assert_called_once_with()
        mock_config_exists.assert_called_once_with(settings.sbd_config)

    def test_no_config(self, mock_config, mock_config_exists):
        mock_config_exists.return_value = False
        runner.set_runs(self.fixture_sbd_enabled(True))
        self.assertEqual([], cmd_sbd.get_local_devices_info(self.env))
        runner.assert_everything_launched()
        self.assertEqual(0, mock_config.call_count)
        mock_config_exists.assert_called_once_with(settings.sbd_config)

    def test_sbd_disabled(self, mock_config, mock_config_exists):
        mock_config_exists.return_value = True
        runner.set_runs(self.fixture_sbd_enabled(False))
        self.assertEqual([], cmd_sbd.get_local_devices_info(self.env))
        runner.assert_everything_launched()
        self.assertEqual(0, mock_config.call_count)
        self.assertEqual(0, mock_config_exists.call_count)

    def test_with_failures(self, mock_config, mock_config_exists):
        mock_config_exists.return_value = True
        mock_config.return_value = """
SBD_DEVICE="/dev1;/dev2;/dev3"
        """
        runner.set_runs(
            self.fixture_sbd_enabled(True) +
            self.fixture_sbd_info("/dev1", "1", 1) +
            self.fixture_sbd_info("/dev2", "2") +
            self.fixture_sbd_dump("/dev2", "4", 1) +
            self.fixture_sbd_info("/dev3", "5") +
            self.fixture_sbd_dump("/dev3", "6")
        )
        expected_output = [
            {
                "device": "/dev1",
                "list": None,
                "dump": None,
            },
            {
                "device": "/dev2",
                "list": "2",
                "dump": None,
            },
            {
                "device": "/dev3",
                "list": "5",
                "dump": "6",
            },
        ]
        self.assertEqual(
            expected_output, cmd_sbd.get_local_devices_info(self.env, dump=True)
        )
        self.env.report_processor.assert_reports([
            (
                Severities.WARNING,
                report_codes.SBD_DEVICE_LIST_ERROR,
                {
                    "device": "/dev1",
                    "reason": "1"
                }
            ),
            (
                Severities.WARNING,
                report_codes.SBD_DEVICE_DUMP_ERROR,
                {
                    "device": "/dev2",
                    "reason": "4"
                }
            ),
        ])
        runner.assert_everything_launched()
        mock_config.assert_called_once_with()
        mock_config_exists.assert_called_once_with(settings.sbd_config)


class SetMessageTest(CommonTest):
    def fixture_call_sbd_message(
        self, device, node, message, stderr="", return_code=0
    ):
        return [Call(
            "sbd -d {0} message {1} {2}".format(device, node, message),
            stderr=stderr,
            returncode=return_code
        )]

    def test_empty_options(self):
        assert_raise_library_error(
            lambda: cmd_sbd.set_message(self.env, "", "", ""),
            (
                Severities.ERROR,
                report_codes.REQUIRED_OPTION_IS_MISSING,
                {
                    "option_names": ["device", "node"],
                    "option_type": None,
                }
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "message",
                    "option_value": "",
                    "allowed_values": settings.sbd_message_types,
                }
            )
        )

    def test_invalid_message_type(self):
        assert_raise_library_error(
            lambda: cmd_sbd.set_message(self.env, "device", "node1", "message"),
            (
                Severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "message",
                    "option_value": "message",
                    "allowed_values": settings.sbd_message_types,
                }
            )
        )

    def test_success(self):
        runner.set_runs(self.fixture_call_sbd_message("device", "node", "test"))
        cmd_sbd.set_message(self.env, "device", "node", "test")
        runner.assert_everything_launched()

    def test_failuer(self):
        runner.set_runs(
            self.fixture_call_sbd_message("device", "node", "test", "error", 1)
        )
        assert_raise_library_error(
            lambda: cmd_sbd.set_message(self.env, "device", "node", "test"),
            (
                Severities.ERROR,
                report_codes.SBD_DEVICE_MESSAGE_ERROR,
                {
                    "device": "device",
                    "node": "node",
                    "message": "test",
                    "reason": "error",
                }
            )
        )
        runner.assert_everything_launched()
