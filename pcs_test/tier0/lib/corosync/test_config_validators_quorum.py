# pylint: disable=too-many-lines
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.corosync import config_validators

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

fixture_report_exec_names = fixture.error(
    report_codes.INVALID_USERDEFINED_OPTIONS,
    option_names=[
        "exec_ls bad",
        "exec_ls#bad",
        "exec_ls.bad",
        "exec_ls:bad",
        "exec_ls{bad",
        "exec_ls}bad",
        "exec_lsčbad",
    ],
    option_type="heuristics",
    allowed_characters="a-z A-Z 0-9 /_-",
)
forbidden_characters_kwargs = dict(
    allowed_values=None,
    cannot_be_empty=False,
    forbidden_characters=r"{}\n\r",
)


class BaseQuorumOptions:
    # pylint: disable=no-member
    def test_no_options(self):
        has_qdevice = False
        assert_report_item_list_equal(self.validator({}, has_qdevice), [])

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
                has_qdevice,
            ),
            [],
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
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="auto_tie_breaker",
                    option_value="atb",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="last_man_standing",
                    option_value="lms",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="last_man_standing_window",
                    option_value="lmsw",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="wait_for_all",
                    option_value="wfa",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
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
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense1", "nonsense2"],
                    option_type="quorum",
                    allowed=[
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all",
                    ],
                    allowed_patterns=[],
                ),
            ],
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
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE,
                    options=[
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                    ],
                ),
            ],
        )

    def test_qdevice_compatible_options(self):
        has_qdevice = True
        assert_report_item_list_equal(
            self.validator(
                {
                    "wait_for_all": "1",
                },
                has_qdevice,
            ),
            [],
        )

    def test_last_man_standing_required(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum",
                )
            ],
        )

    def test_last_man_standing_required_enabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing": "0",
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum",
                )
            ],
        )

    def test_forbidden_characters(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "0}",
                    "last_man_standing": "1{",
                    "last_man_standing_window": "1000\n",
                    "wait_for_all": "0\r",
                    "op:.tion": "va}l{ue",
                },
                has_qdevice,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="quorum",
                    allowed=[
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="quorum",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0}",
                    option_name="auto_tie_breaker",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1{",
                    option_name="last_man_standing",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1000\n",
                    option_name="last_man_standing_window",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0\r",
                    option_name="wait_for_all",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0}",
                    option_name="auto_tie_breaker",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1{",
                    option_name="last_man_standing",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1000\n",
                    option_name="last_man_standing_window",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0\r",
                    option_name="wait_for_all",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )


class CreateQuorumOptions(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = config_validators.create_quorum_options


class QuorumOptionsUpdate(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = lambda options, has_qdevice: (
            config_validators.update_quorum_options(options, has_qdevice, {})
        )

    def test_last_man_standing_required_currently_disabled(self):
        # pylint: disable=no-self-use
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "0",
                },
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum",
                )
            ],
        )

    def test_last_man_standing_required_currently_enabled(self):
        # pylint: disable=no-self-use
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "1",
                },
            ),
            [],
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
                    "tls": "on",
                    "keep_active_partition_tie_breaker": "on",
                },
                {"timeout": "23456", "sync_timeout": "34567"},
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids,
            ),
            [],
        )

    def test_bad_model(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid", {}, {}, {}, self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="model",
                    option_value="invalid",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_bad_model_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid", {}, {}, {}, self.node_ids, force_model=True
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="model",
                    option_value="invalid",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_missing_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net", {}, {}, {}, self.node_ids
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["algorithm", "host"],
                    option_type="quorum device model",
                ),
            ],
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
                force_options=True,
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["algorithm", "host"],
                    option_type="quorum device model",
                ),
            ],
        )

    def test_empty_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net", {"host": "", "algorithm": ""}, {}, {}, self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ],
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
                force_options=True,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ],
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
                    "tls": "",
                    "keep_active_partition_tie_breaker": "",
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
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="connect_timeout",
                    option_value="",
                    allowed_values="1000..120000",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="force_ip_version",
                    option_value="",
                    allowed_values=("0", "4", "6"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="port",
                    option_value="",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="tie_breaker",
                    option_value="",
                    allowed_values=["lowest", "highest"] + self.node_ids,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="tls",
                    option_value="",
                    allowed_values=("on", "off", "required"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="keep_active_partition_tie_breaker",
                    option_value="",
                    allowed_values=("on", "off"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="timeout",
                    option_value="",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="mode",
                    option_value="",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="interval",
                    option_value="",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="timeout",
                    option_value="",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ],
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
                    "tls": "bad",
                    "keep_active_partition_tie_breaker": "30",
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
                    "exec_lsčbad": "test -f /tmp/test",
                },
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="algorithm",
                    option_value="bad algorithm",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE,
                    option_names=["bad_model_option"],
                    option_type="quorum device model",
                    allowed=[
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "keep_active_partition_tie_breaker",
                        "port",
                        "tie_breaker",
                        "tls",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="connect_timeout",
                    option_value="-1",
                    allowed_values="1000..120000",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="force_ip_version",
                    option_value="3",
                    allowed_values=("0", "4", "6"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="port",
                    option_value="65537",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="tie_breaker",
                    option_value="125",
                    allowed_values=["lowest", "highest"] + self.node_ids,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="tls",
                    option_value="bad",
                    allowed_values=("on", "off", "required"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="keep_active_partition_tie_breaker",
                    option_value="30",
                    allowed_values=("on", "off"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE,
                    option_names=["bad_generic_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["model"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="timeout",
                    option_value="-2",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture_report_exec_names,
            ],
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
                    "tls": "bad",
                    "keep_active_partition_tie_breaker": "30",
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
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="bad algorithm",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["bad_model_option"],
                    option_type="quorum device model",
                    allowed=[
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "keep_active_partition_tie_breaker",
                        "port",
                        "tie_breaker",
                        "tls",
                    ],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="connect_timeout",
                    option_value="-1",
                    allowed_values="1000..120000",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="force_ip_version",
                    option_value="3",
                    allowed_values=("0", "4", "6"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="port",
                    option_value="65537",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="tie_breaker",
                    option_value="125",
                    allowed_values=["lowest", "highest"] + self.node_ids,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="tls",
                    option_value="bad",
                    allowed_values=("on", "off", "required"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="keep_active_partition_tie_breaker",
                    option_value="30",
                    allowed_values=("on", "off"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["bad_generic_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-2",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_cannot_force_forbidden_characters(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net{",
                {
                    "algorithm": "bad\nalgorithm\r",
                    "any_}model{_option": "bad}model{value",
                },
                {
                    "sync_timeout": "}-3",
                    "any\rgeneric\noption": "bad\r\ngeneric{}value",
                },
                {
                    "mode": "{bad mode}",
                    "any_:heuristics._option": "bad{}heuristics\n\rvalue",
                    "exec_ls": "test -f /tmp/test {abc}\nsomething\r",
                },
                self.node_ids,
                force_model=True,
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="model",
                    option_value="net{",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="model",
                    option_value="net{",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any_}model{_option"],
                    option_type="quorum device model",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="bad\nalgorithm\r",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any_}model{_option",
                    option_value="bad}model{value",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["any\rgeneric\noption"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any\rgeneric\noption"],
                    option_type="quorum device",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="}-3",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any\rgeneric\noption",
                    option_value="bad\r\ngeneric{}value",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="}-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any_:heuristics._option"],
                    option_type="heuristics",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="{bad mode}",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any_:heuristics._option",
                    option_value="bad{}heuristics\n\rvalue",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ls",
                    option_value="test -f /tmp/test {abc}\nsomething\r",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["any_:heuristics._option"],
                    option_type="heuristics",
                    allowed=["interval", "mode", "sync_timeout", "timeout"],
                    allowed_patterns=["exec_NAME"],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="{bad mode}",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
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
                    "exec_lsčbad": "test -f /tmp/test",
                },
                self.node_ids,
                force_options=True,
            ),
            [
                fixture_report_exec_names,
            ],
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
                    "tls": "required",
                    "keep_active_partition_tie_breaker": "on",
                },
                {"timeout": "23456", "sync_timeout": "34567"},
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids,
            ),
            [],
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
                    "tls": "",
                    "keep_active_partition_tie_breaker": "",
                },
                {"timeout": "", "sync_timeout": ""},
                {
                    "mode": "",
                    "timeout": "",
                    "sync_timeout": "",
                    "interval": "",
                    "exec_ping": "",
                    "exec_ls": "",
                },
                self.node_ids,
            ),
            [],
        )

    def test_net_doesnt_require_host_and_algorithm(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "12345",
                },
                {},
                {},
                self.node_ids,
            ),
            [],
        )

    def test_net_host_and_algorithm_cannot_be_removed(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                {},
                {},
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_net_host_and_algorithm_cannot_be_removed_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                {},
                {},
                self.node_ids,
                force_options=True,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ],
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
                    "tls": "bad",
                    "keep_active_partition_tie_breaker": "30",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="algorithm",
                    option_value="bad algorithm",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    report_codes.FORCE,
                    option_names=["bad_model_option"],
                    option_type="quorum device model",
                    allowed=[
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "keep_active_partition_tie_breaker",
                        "port",
                        "tie_breaker",
                        "tls",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="connect_timeout",
                    option_value="-1",
                    allowed_values="1000..120000",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="force_ip_version",
                    option_value="3",
                    allowed_values=("0", "4", "6"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="port",
                    option_value="65537",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="tie_breaker",
                    option_value="125",
                    allowed_values=["lowest", "highest"] + self.node_ids,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="tls",
                    option_value="bad",
                    allowed_values=("on", "off", "required"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="keep_active_partition_tie_breaker",
                    option_value="30",
                    allowed_values=("on", "off"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
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
                    "tls": "bad",
                    "keep_active_partition_tie_breaker": "30",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids,
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="bad algorithm",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["bad_model_option"],
                    option_type="quorum device model",
                    allowed=[
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "keep_active_partition_tie_breaker",
                        "port",
                        "tie_breaker",
                        "tls",
                    ],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="connect_timeout",
                    option_value="-1",
                    allowed_values="1000..120000",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="force_ip_version",
                    option_value="3",
                    allowed_values=("0", "4", "6"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="port",
                    option_value="65537",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="tie_breaker",
                    option_value="125",
                    allowed_values=["lowest", "highest"] + self.node_ids,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="tls",
                    option_value="bad",
                    allowed_values=("on", "off", "required"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="keep_active_partition_tie_breaker",
                    option_value="30",
                    allowed_values=("on", "off"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
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
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=report_codes.FORCE,
                    option_names=["bad_generic_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["model"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    report_codes.FORCE,
                    option_name="timeout",
                    option_value="-2",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_bad_generic_options_cannot_force_model(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {
                    "model": "some model",
                },
                {},
                self.node_ids,
                force_options=True,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["model"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                )
            ],
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
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["bad_generic_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-2",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
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
                    "exec_lsčbad": "test -f /tmp/test",
                },
                self.node_ids,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture_report_exec_names,
            ],
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
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_cannot_force_forbidden_characters(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "algorithm": "bad\nalgorithm\r",
                    "any_}model{_option": "bad}model{value",
                },
                {
                    "sync_timeout": "}-3",
                    "any\rgeneric\noption": "bad\r\ngeneric{}value",
                },
                {
                    "mode": "{bad mode}",
                    "any_:heuristics._option": "bad{}heuristics\n\rvalue",
                    "exec_ls": "test -f /tmp/test {abc}\nsomething\r",
                },
                self.node_ids,
                force_options=True,
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["any_}model{_option"],
                    option_type="quorum device model",
                    allowed=[
                        "algorithm",
                        "connect_timeout",
                        "force_ip_version",
                        "host",
                        "keep_active_partition_tie_breaker",
                        "port",
                        "tie_breaker",
                        "tls",
                    ],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="bad\nalgorithm\r",
                    allowed_values=("ffsplit", "lms"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any_}model{_option"],
                    option_type="quorum device model",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="bad\nalgorithm\r",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any_}model{_option",
                    option_value="bad}model{value",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["any\rgeneric\noption"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any\rgeneric\noption"],
                    option_type="quorum device",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="}-3",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any\rgeneric\noption",
                    option_value="bad\r\ngeneric{}value",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="}-3",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["any_:heuristics._option"],
                    option_type="heuristics",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="{bad mode}",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="any_:heuristics._option",
                    option_value="bad{}heuristics\n\rvalue",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ls",
                    option_value="test -f /tmp/test {abc}\nsomething\r",
                    **forbidden_characters_kwargs,
                ),
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["any_:heuristics._option"],
                    option_type="heuristics",
                    allowed=["interval", "mode", "sync_timeout", "timeout"],
                    allowed_patterns=["exec_NAME"],
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="{bad mode}",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_cannot_force_bad_heuristics_exec_name(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {},
                {
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                    "exec_lsčbad": "test -f /tmp/test",
                },
                self.node_ids,
                force_options=True,
            ),
            [
                fixture_report_exec_names,
            ],
        )
