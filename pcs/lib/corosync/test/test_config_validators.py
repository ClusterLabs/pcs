from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.corosync import config_validators
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.test.tools import fixture
from pcs.test.tools.assertions import assert_report_item_list_equal


class BaseQuorumOptions():
    def test_no_options(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                },
                has_qdevice
            ),
            []
        )

    def test_all_valid(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "0",
                    "last_man_standing": "1",
                    "last_man_standing_window": "1000",
                    "wait_for_all": "0",
                },
                has_qdevice
            ),
            []
        )

    def test_invalid_all_values(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "atb",
                    "last_man_standing": "lms",
                    "last_man_standing_window": "lmsw",
                    "wait_for_all": "wfa",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "auto_tie_breaker",
                        "option_value": "atb",
                        "allowed_values": ("0", "1"),
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "last_man_standing",
                        "option_value": "lms",
                        "allowed_values": ("0", "1"),
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "last_man_standing_window",
                        "option_value": "lmsw",
                        "allowed_values": "a positive integer",
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "wait_for_all",
                        "option_value": "wfa",
                        "allowed_values": ("0", "1"),
                    }
                ),
            ]
        )

    def test_invalid_option(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "1",
                    "nonsense1": "0",
                    "nonsense2": "doesnt matter",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["nonsense1", "nonsense2"],
                        "option_type": "quorum",
                        "allowed": [
                            "auto_tie_breaker",
                            "last_man_standing",
                            "last_man_standing_window",
                            "wait_for_all"
                        ],
                        "allowed_patterns": [],
                    }
                ),
            ]
        )

    def test_qdevice_incompatible_options(self):
        has_qdevice = True
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "1",
                    "last_man_standing": "1",
                    "last_man_standing_window": "250",
                    "wait_for_all": "1",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE,
                    {
                        "options_names": [
                            "auto_tie_breaker",
                            "last_man_standing",
                            "last_man_standing_window",
                        ],
                    }
                ),
            ]
        )

    def test_qdevice_compatible_options(self):
        has_qdevice = True
        assert_report_item_list_equal(
            self.validator(
                {
                    "wait_for_all": "1",
                },
                has_qdevice
            ),
            []
        )

    def test_last_man_standing_required(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )

    def test_last_man_standing_required_enabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing": "0",
                    "last_man_standing_window": "1000",
                },
                has_qdevice
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )


class CreateQuorumOptions(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = config_validators.create_quorum_options


class QuorumOptionsUpdate(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = (
            lambda options, has_qdevice:
            config_validators.update_quorum_options(options, has_qdevice, {})
        )

    def test_last_man_standing_required_currently_disabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "0",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )

    def test_last_man_standing_required_currently_enabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "1",
                }
            ),
            [
            ]
        )


class AddQuorumDevice(TestCase):
    def setUp(self):
        self.node_ids = ["1", "2", "3"]

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "4433",
                    "algorithm": "ffsplit",
                    "connect_timeout": "12345",
                    "force_ip_version": "4",
                    "tie_breaker": "2",
                },
                {
                    "timeout": "23456",
                    "sync_timeout": "34567"
                },
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_bad_model(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid",
                {},
                {},
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "invalid",
                        "allowed_values": ["net", ],
                    },
                    report_codes.FORCE_QDEVICE_MODEL
                )
            ]
        )

    def test_bad_model_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid",
                {},
                {},
                {},
                self.node_ids,
                force_model=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "invalid",
                        "allowed_values": ["net", ],
                    },
                )
            ]
        )

    def test_missing_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {},
                {},
                {},
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["algorithm"],
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["host"],
                )
            ]
        )

    def test_missing_required_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {},
                {},
                {},
                self.node_ids,
                force_model=True,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["algorithm"],
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["host"],
                )
            ]
        )

    def test_empty_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {"host": "", "algorithm": ""},
                {},
                {},
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_empty_required_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {"host": "", "algorithm": ""},
                {},
                {},
                self.node_ids,
                force_model=True,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_empty_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "",
                    "port": "",
                    "algorithm": "",
                    "connect_timeout": "",
                    "force_ip_version": "",
                    "tie_breaker": "",
                },
                {
                    "timeout": "",
                    "sync_timeout": "",
                },
                {
                    "mode": "",
                    "timeout": "",
                    "sync_timeout": "",
                    "interval": "",
                    "exec_ping": "",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run"
                ),
            ]
        )

    def test_bad_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "",
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                },
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ping": "",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run"
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )

    def test_bad_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                },
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                },
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    }
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )

    def test_cannot_force_bad_heuristics_exec_name(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "qnetd-host",
                    "algorithm": "ffsplit",
                },
                {},
                {
                    "mode": "on",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )


class UpdateQuorumDevice(TestCase):
    def setUp(self):
        self.node_ids = ["1", "2", "3"]

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "4433",
                    "algorithm": "ffsplit",
                    "connect_timeout": "12345",
                    "force_ip_version": "4",
                    "tie_breaker": "2",
                },
                {
                    "timeout": "23456",
                    "sync_timeout": "34567"
                },
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_all_valid_empty(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "",
                    "connect_timeout": "",
                    "force_ip_version": "",
                    "tie_breaker": "",
                },
                {
                    "timeout": "",
                    "sync_timeout": ""
                },
                {
                    "mode": "",
                    "timeout": "",
                    "sync_timeout": "",
                    "interval": "",
                    "exec_ping": "",
                    "exec_ls": "",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_net_doesnt_require_host_and_algorithm(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "12345",
                },
                { },
                { },
                self.node_ids
            ),
            [
            ]
        )

    def test_net_host_and_algorithm_cannot_be_removed(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                {
                },
                {
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_net_host_and_algorithm_cannot_be_removed_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                { },
                { },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_bad_net_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_bad_net_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                ),
            ]
        )

    def test_bad_generic_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                },
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                )
            ]
        )

    def test_bad_generic_options_cannot_force_model(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {"model": "some model", },
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                )
            ]
        )

    def test_bad_generic_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                },
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                )
            ]
        )

    def test_heuristics_bad_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {},
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )

    def test_heuristics_bad_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {},
                {
                    "interval": "-30",
                    "mode": "bad mode",
                    "sync_timeout": "-15",
                    "timeout": "-5",
                },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )
