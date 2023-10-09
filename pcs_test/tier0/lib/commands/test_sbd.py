from unittest import (
    TestCase,
    mock,
)

import pcs.lib.commands.sbd as cmd_sbd
from pcs import settings
from pcs.common import reports
from pcs.common.node_communicator import RequestTarget
from pcs.common.reports import ReportItem
from pcs.common.reports import ReportItemSeverity as Severities
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import outdent


def _assert_equal_list_of_dictionaries_without_order(expected, actual):
    for item in actual:
        if item not in expected:
            raise AssertionError("Given but not expected: {0}".format(item))
    for item in expected:
        if item not in actual:
            raise AssertionError("Expected but not given: {0}".format(item))


class ValidateSbdOptionsTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.allowed_sbd_options = sorted(
            [
                "SBD_DELAY_START",
                "SBD_STARTMODE",
                "SBD_WATCHDOG_TIMEOUT",
                "SBD_TIMEOUT_ACTION",
            ]
        )
        self.timeout_action_allowed_values = sorted(
            [
                "flush",
                "noflush",
                "off",
                "reboot",
                "crashdump",
                "flush,off",
                "flush,reboot",
                "flush,crashdump",
                "noflush,off",
                "noflush,reboot",
                "noflush,crashdump",
                "off,flush",
                "off,noflush",
                "reboot,flush",
                "reboot,noflush",
                "crashdump,flush",
                "crashdump,noflush",
            ]
        )

    def test_all_ok(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_TIMEOUT_ACTION": "flush,reboot",
        }
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_invalid_value(self):
        config = {
            "SBD_TIMEOUT_ACTION": "flush,noflush",
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="SBD_TIMEOUT_ACTION",
                    option_value="flush,noflush",
                    allowed_values=self.timeout_action_allowed_values,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_invalid_value_forced(self):
        config = {
            "SBD_TIMEOUT_ACTION": "flush,noflush",
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(
                config, allow_invalid_option_values=True
            ),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="SBD_TIMEOUT_ACTION",
                    option_value="flush,noflush",
                    allowed_values=self.timeout_action_allowed_values,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_unknown_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value",
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_UNKNOWN", "another_unknown_option"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                    force_code=reports.codes.FORCE,
                ),
            ],
        )

    def test_unknown_options_forced(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value",
        }
        # just make sure there is no exception raised
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config, allow_unknown_opts=True),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_UNKNOWN", "another_unknown_option"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ],
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
                    reports.codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_DEVICE"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ],
        )

    def test_invalid_and_unsupported_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_UNKNOWN": "",
            "SBD_OPTS": "  ",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=sorted(["SBD_WATCHDOG_DEV", "SBD_OPTS"]),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["SBD_UNKNOWN"],
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                    force_code=reports.codes.FORCE,
                ),
            ],
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
                    reports.codes.INVALID_OPTIONS,
                    option_names=sorted(
                        ["SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER"]
                    ),
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["SBD_UNKNOWN"],
                    option_type=None,
                    allowed=self.allowed_sbd_options,
                    allowed_patterns=[],
                ),
            ],
        )

    def test_watchdog_timeout_is_not_present(self):
        config = {"SBD_DELAY_START": "yes", "SBD_STARTMODE": "clean"}
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_watchdog_timeout_is_nonnegative_int(self):
        # pylint: disable=no-self-use
        config = {
            "SBD_WATCHDOG_TIMEOUT": "-1",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="SBD_WATCHDOG_TIMEOUT",
                    option_value="-1",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_watchdog_timeout_is_not_int(self):
        # pylint: disable=no-self-use
        config = {
            "SBD_WATCHDOG_TIMEOUT": "not int",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="SBD_WATCHDOG_TIMEOUT",
                    option_value="not int",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_watchdog_timeout_is_none(self):
        # pylint: disable=no-self-use
        config = {
            "SBD_WATCHDOG_TIMEOUT": None,
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="SBD_WATCHDOG_TIMEOUT",
                    option_value=None,
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )


class ValidateWatchdogDictTest(TestCase):
    # pylint: disable=protected-access
    def test_all_ok(self):
        watchdog_dict = {
            "node1": "/dev/watchdog1",
            "node2": "/dev/watchdog2",
        }
        self.assertEqual([], cmd_sbd._validate_watchdog_dict(watchdog_dict))

    def test_some_not_ok(self):
        # pylint: disable=no-self-use
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
                    reports.codes.WATCHDOG_INVALID,
                    {"watchdog": watchdog},
                )
                for watchdog in ["", None]
            ],
        )


class GetFullTargetDictTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.target_list = [
            RequestTarget("node{0}".format(i)) for i in range(1, 4)
        ]

    def test_not_using_default(self):
        target_dict = {"node" + str(i): "val" + str(i) for i in range(4)}
        expected = {
            self.target_list[0].label: "val1",
            self.target_list[1].label: "val2",
            self.target_list[2].label: "val3",
        }
        self.assertEqual(
            expected,
            cmd_sbd._get_full_target_dict(self.target_list, target_dict, None),
        )

    def test_using_default(self):
        target_dict = {"node" + str(i): "val" + str(i) for i in range(3)}
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
            ),
        )


class GetLocalSbdConfigTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success(self):
        config_content = outdent(
            """\
            # This file has been generated by pcs.
            SBD_OPTS="-n node1"
            SBD_WATCHDOG_DEV=/dev/watchdog
            SBD_WATCHDOG_TIMEOUT=0
            """
        )
        self.config.fs.open(
            settings.sbd_config,
            mock.mock_open(read_data=config_content)(),
        )

        self.assertEqual(
            {
                "SBD_OPTS": '"-n node1"',
                "SBD_WATCHDOG_DEV": "/dev/watchdog",
                "SBD_WATCHDOG_TIMEOUT": "0",
            },
            cmd_sbd.get_local_sbd_config(self.env_assist.get_env()),
        )

    def test_file_error(self):
        node = "node"
        reason = "reason"
        self.config.fs.open(
            settings.sbd_config,
            side_effect=LibraryError(
                ReportItem.error(
                    reports.messages.UnableToGetSbdConfig(node, reason)
                )
            ),
        )
        assert_raise_library_error(
            lambda: cmd_sbd.get_local_sbd_config(self.env_assist.get_env()),
            (
                Severities.ERROR,
                reports.codes.UNABLE_TO_GET_SBD_CONFIG,
                {
                    "node": node,
                    "reason": reason,
                },
            ),
        )


class InitializeBlockDevicesTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    @staticmethod
    def fixture_invalid_value(option, value):
        return fixture.error(
            reports.codes.INVALID_OPTION_VALUE,
            option_name=option,
            option_value=value,
            allowed_values="a non-negative integer",
            cannot_be_empty=False,
            forbidden_characters=None,
        )

    def test_all_options(self):
        device_list = ["dev1", "dev2"]
        option_dict = {
            "watchdog-timeout": "1",
            "loop-timeout": "10",
            "allocate-timeout": "3",
            "msgwait-timeout": "2",
        }
        self.config.runner.sbd.initialize_devices(device_list, option_dict)
        cmd_sbd.initialize_block_devices(
            self.env_assist.get_env(), device_list, option_dict
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.INFO,
                    reports.codes.SBD_DEVICE_INITIALIZATION_STARTED,
                    {"device_list": device_list},
                ),
                (
                    Severities.INFO,
                    reports.codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
                    {"device_list": device_list},
                ),
            ]
        )

    def test_no_options(self):
        device_list = ["dev1", "dev2"]
        self.config.runner.sbd.initialize_devices(device_list, {})
        cmd_sbd.initialize_block_devices(
            self.env_assist.get_env(), device_list, {}
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.INFO,
                    reports.codes.SBD_DEVICE_INITIALIZATION_STARTED,
                    {"device_list": device_list},
                ),
                (
                    Severities.INFO,
                    reports.codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
                    {"device_list": device_list},
                ),
            ]
        )

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
            "watchdog-timeout",
            "loop-timeout",
            "allocate-timeout",
            "msgwait-timeout",
        ]
        self.env_assist.assert_raise_library_error(
            lambda: cmd_sbd.initialize_block_devices(
                self.env_assist.get_env(), [], option_dict
            )
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.ERROR,
                    reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {
                        "option_names": ["device"],
                        "option_type": None,
                    },
                ),
                (
                    Severities.ERROR,
                    reports.codes.INVALID_OPTIONS,
                    {
                        "option_names": ["another_one", "unknown_option"],
                        "option_type": None,
                        "allowed": sorted(allowed_options),
                        "allowed_patterns": [],
                    },
                ),
            ]
            + [
                self.fixture_invalid_value(opt, option_dict[opt])
                for opt in allowed_options
            ],
        )


class GetLocalDevicesInfoTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success(self):
        config_data = 'SBD_DEVICE="/dev1;/dev2"\n'
        self.config.services.is_enabled("sbd")
        self.config.fs.exists(settings.sbd_config, return_value=True)
        self.config.fs.open(
            settings.sbd_config, mock.mock_open(read_data=config_data)()
        )
        self.config.runner.sbd.get_device_info("/dev1", stdout="1")
        self.config.runner.sbd.get_device_info(
            "/dev2", stdout="2", name="list2"
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
            expected_output,
            cmd_sbd.get_local_devices_info(self.env_assist.get_env()),
        )

    def test_with_dump(self):
        config_data = 'SBD_DEVICE="/dev1;/dev2"\n'
        self.config.services.is_enabled("sbd")
        self.config.fs.exists(settings.sbd_config, return_value=True)
        self.config.fs.open(
            settings.sbd_config, mock.mock_open(read_data=config_data)()
        )
        self.config.runner.sbd.get_device_info("/dev1", stdout="1")
        self.config.runner.sbd.get_device_dump("/dev1", stdout="2")
        self.config.runner.sbd.get_device_info(
            "/dev2", stdout="3", name="list2"
        )
        self.config.runner.sbd.get_device_dump(
            "/dev2", stdout="4", name="dump2"
        )
        expected_output = [
            {
                "device": "/dev1",
                "list": "1",
                "dump": "2",
            },
            {
                "device": "/dev2",
                "list": "3",
                "dump": "4",
            },
        ]
        self.assertEqual(
            expected_output,
            cmd_sbd.get_local_devices_info(
                self.env_assist.get_env(), dump=True
            ),
        )

    def test_no_config(self):
        self.config.services.is_enabled("sbd")
        self.config.fs.exists(settings.sbd_config, return_value=False)
        self.assertEqual(
            [], cmd_sbd.get_local_devices_info(self.env_assist.get_env())
        )

    def test_sbd_disabled(self):
        self.config.services.is_enabled("sbd", return_value=False)
        self.assertEqual(
            [], cmd_sbd.get_local_devices_info(self.env_assist.get_env())
        )

    def test_with_failures(self):
        config_data = 'SBD_DEVICE="/dev1;/dev2;/dev3"\n'
        self.config.services.is_enabled("sbd")
        self.config.fs.exists(settings.sbd_config, return_value=True)
        self.config.fs.open(
            settings.sbd_config, mock.mock_open(read_data=config_data)()
        )
        self.config.runner.sbd.get_device_info(
            "/dev1", stdout="1", return_code=1
        )
        self.config.runner.sbd.get_device_info(
            "/dev2", stdout="2", name="list2"
        )
        self.config.runner.sbd.get_device_dump(
            "/dev2", stdout="4", return_code=1
        )
        self.config.runner.sbd.get_device_info(
            "/dev3", stdout="5", name="list3"
        )
        self.config.runner.sbd.get_device_dump(
            "/dev3", stdout="6", name="dump2"
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
            expected_output,
            cmd_sbd.get_local_devices_info(
                self.env_assist.get_env(), dump=True
            ),
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.WARNING,
                    reports.codes.SBD_DEVICE_LIST_ERROR,
                    {"device": "/dev1", "reason": "1"},
                ),
                (
                    Severities.WARNING,
                    reports.codes.SBD_DEVICE_DUMP_ERROR,
                    {"device": "/dev2", "reason": "4"},
                ),
            ]
        )


class SetMessageTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_empty_options(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_sbd.set_message(self.env_assist.get_env(), "", "", "")
        )
        self.env_assist.assert_reports(
            [
                (
                    Severities.ERROR,
                    reports.codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {
                        "option_names": ["device", "node"],
                        "option_type": None,
                    },
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="message",
                    option_value="",
                    allowed_values=settings.sbd_message_types,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_invalid_message_type(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_sbd.set_message(
                self.env_assist.get_env(), "device", "node1", "message"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="message",
                    option_value="message",
                    allowed_values=settings.sbd_message_types,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_success(self):
        self.config.runner.sbd.set_device_message("device", "node", "test")
        cmd_sbd.set_message(self.env_assist.get_env(), "device", "node", "test")

    def test_failure(self):
        self.config.runner.sbd.set_device_message(
            "device", "node", "test", stderr="error", return_code=1
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_sbd.set_message(
                self.env_assist.get_env(), "device", "node", "test"
            ),
            [
                (
                    Severities.ERROR,
                    reports.codes.SBD_DEVICE_MESSAGE_ERROR,
                    {
                        "device": "device",
                        "node": "node",
                        "sbd_message": "test",
                        "reason": "error",
                    },
                )
            ],
            expected_in_processor=False,
        )
