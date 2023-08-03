# pylint: disable=too-many-lines
import base64
import logging
import os.path
import re
from textwrap import dedent
from typing import NamedTuple
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.lib.commands import quorum as lib
from pcs.lib.corosync.config_facade import ConfigFacade
from pcs.lib.env import LibraryEnvironment

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    ac,
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_http_corosync import (
    corosync_running_check_response,
)
from pcs_test.tools.custom_mock import (
    MockLibraryReportProcessor,
    TmpFileCall,
    TmpFileMock,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import outdent


def _read_file_rc(name):
    with open(rc(name)) as a_file:
        return a_file.read()


# pylint: disable=protected-access


@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
class GetQuorumConfigTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_enabled_if_not_live(self, mock_get_corosync):
        original_conf = _read_file_rc("corosync.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf,
        )

        self.assertEqual(
            {
                "options": {},
                "device": None,
            },
            lib.get_config(lib_env),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_no_options(self, mock_get_corosync):
        original_conf = _read_file_rc("corosync.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        self.assertEqual(
            {
                "options": {},
                "device": None,
            },
            lib.get_config(lib_env),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_options(self, mock_get_corosync):
        original_conf = "quorum {\nwait_for_all: 1\n}\n"
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        self.assertEqual(
            {
                "options": {
                    "wait_for_all": "1",
                },
                "device": None,
            },
            lib.get_config(lib_env),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_device(self, mock_get_corosync):
        original_conf = """\
            quorum {
                provider: corosync_votequorum
                wait_for_all: 1
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                        port: 4433
                    }
                }
            }
        """
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        self.assertEqual(
            {
                "options": {
                    "wait_for_all": "1",
                },
                "device": {
                    "model": "net",
                    "model_options": {
                        "host": "127.0.0.1",
                        "port": "4433",
                    },
                    "generic_options": {
                        "option": "value",
                    },
                    "heuristics_options": {},
                },
            },
            lib.get_config(lib_env),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_device_with_heuristics(self, mock_get_corosync):
        original_conf = """\
            quorum {
                provider: corosync_votequorum
                wait_for_all: 1
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                        port: 4433
                    }
                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
                }
            }
        """
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        self.assertEqual(
            {
                "options": {
                    "wait_for_all": "1",
                },
                "device": {
                    "model": "net",
                    "model_options": {
                        "host": "127.0.0.1",
                        "port": "4433",
                    },
                    "generic_options": {
                        "option": "value",
                    },
                    "heuristics_options": {
                        "exec_ls": "test -f /tmp/test",
                        "mode": "on",
                    },
                },
            },
            lib.get_config(lib_env),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)


@mock.patch("pcs.lib.sbd.is_auto_tie_breaker_needed")
class CheckIfAtbCanBeDisabledTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.mock_runner = "cmd_runner"
        self.mock_corosync_conf = mock.MagicMock(spec_set=ConfigFacade)

    def test_atb_no_need_was_disabled_atb_disabled(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, False
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_disabled_atb_enabled(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, False
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enable_atb_disabled(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enabled_atb_enabled(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_disabled(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, False
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_enabled(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, False
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_enable_atb_disabled(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        report_item = fixture.error(
            reports.codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD,
            force_code=reports.codes.FORCE,
        )
        assert_raise_library_error(
            lambda: lib._check_if_atb_can_be_disabled(
                self.mock_runner,
                self.mock_reporter,
                self.mock_corosync_conf,
                was_enabled=True,
            )
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list, [report_item]
        )

    def test_atb_needed_was_enabled_atb_enabled(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_disabled_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            False,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_disabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            False,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enable_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            True,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            True,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            False,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            False,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_enable_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            True,
            force=True,
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    reports.ReportItemSeverity.WARNING,
                    reports.codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD,
                    {},
                    None,
                )
            ],
        )

    def test_atb_needed_was_enabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner,
            self.mock_reporter,
            self.mock_corosync_conf,
            True,
            force=True,
        )
        self.assertEqual([], self.mock_reporter.report_item_list)


class SetQuorumOptionsTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_labels = ["rh7-1", "rh7-2"]
        self.config.env.set_known_nodes(self.node_labels)
        self.original_corosync_conf = _read_file_rc("corosync.conf")
        self.success_reports = (
            [
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
                ),
            ]
            + [
                fixture.info(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=node,
                )
                for node in self.node_labels
            ]
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node=node
                )
                for node in self.node_labels
            ]
        )

    def fixture_config_unable_to_connect(self):
        self.config.corosync_conf.load()
        self.config.http.corosync.get_corosync_online_targets(
            communication_list=[
                dict(
                    label=self.node_labels[0],
                    output=corosync_running_check_response(False),
                ),
                dict(
                    label=self.node_labels[1],
                    was_connected=False,
                    errno=7,
                    error_msg="an error",
                ),
            ]
        )

    def test_success(self):
        expected_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    wait_for_all: 1"
        )
        self.config.corosync_conf.load()
        self.config.http.corosync.check_corosync_offline(
            node_labels=self.node_labels
        )
        self.config.http.corosync.set_corosync_conf(
            expected_conf, node_labels=self.node_labels
        )

        new_options = {"wait_for_all": "1"}
        lib.set_options(self.env_assist.get_env(), new_options)
        self.env_assist.assert_reports(self.success_reports)

    def test_bad_options(self):
        self.config.corosync_conf.load()

        new_options = {"invalid": "option"}
        assert_raise_library_error(
            lambda: lib.set_options(self.env_assist.get_env(), new_options)
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["invalid"],
                    allowed=[
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all",
                    ],
                    option_type="quorum",
                    allowed_patterns=[],
                )
            ]
        )

    def test_bad_config(self):
        self.config.corosync_conf.load_content("invalid {\nconfig: this is")
        new_options = {"wait_for_all": "1"}
        assert_raise_library_error(
            lambda: lib.set_options(self.env_assist.get_env(), new_options)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE
                )
            ]
        )

    def test_corosync_not_offline(self):
        self.config.corosync_conf.load()
        self.config.http.corosync.get_corosync_online_targets(self.node_labels)

        new_options = {"wait_for_all": "1"}
        assert_raise_library_error(
            lambda: lib.set_options(self.env_assist.get_env(), new_options)
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node=self.node_labels[0],
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node=self.node_labels[1],
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_FINISHED_RUNNING,
                    node_list=self.node_labels,
                ),
            ]
        )

    def test_disable_atb_sbd_disabled(self):
        expected_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    auto_tie_breaker: 0"
        )
        self.config.corosync_conf.load(auto_tie_breaker=True)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.http.corosync.check_corosync_offline(
            node_labels=self.node_labels
        )
        self.config.http.corosync.set_corosync_conf(
            expected_conf, node_labels=self.node_labels
        )

        new_options = {"auto_tie_breaker": "0"}
        lib.set_options(self.env_assist.get_env(), new_options)
        self.env_assist.assert_reports(self.success_reports)

    def test_disable_atb_sbd_enabled(self):
        self.config.corosync_conf.load(auto_tie_breaker=True)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)

        new_options = {"auto_tie_breaker": "0"}
        assert_raise_library_error(
            lambda: lib.set_options(self.env_assist.get_env(), new_options)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_force_disable_atb_sbd_enabled(self):
        expected_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    auto_tie_breaker: 0"
        )
        self.config.corosync_conf.load(auto_tie_breaker=True)
        self.config.services.is_installed("sbd", return_value=True)
        self.config.services.is_enabled("sbd", return_value=True)
        self.config.http.corosync.check_corosync_offline(
            node_labels=self.node_labels
        )
        self.config.http.corosync.set_corosync_conf(
            expected_conf, node_labels=self.node_labels
        )

        new_options = {"auto_tie_breaker": "0"}
        lib.set_options(self.env_assist.get_env(), new_options, force=True)
        self.env_assist.assert_reports(
            self.success_reports
            + [
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD
                )
            ]
        )

    def test_not_live(self):
        original_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    auto_tie_breaker: 1"
        )
        expected_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    auto_tie_breaker: 0"
        )
        self.config.env.set_corosync_conf_data(original_conf)
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_conf, need_stopped_cluster=True
        )

        new_options = {"auto_tie_breaker": "0"}
        lib.set_options(self.env_assist.get_env(), new_options)

    def test_unable_to_connect(self):
        self.fixture_config_unable_to_connect()
        new_options = {"wait_for_all": "1"}
        assert_raise_library_error(
            lambda: lib.set_options(self.env_assist.get_env(), new_options)
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.info(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.node_labels[0],
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=self.node_labels[1],
                    command="remote/status",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.node_labels[1],
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                ),
            ]
        )

    def test_unable_to_connect_skip_offline_nodes(self):
        expected_conf = self.original_corosync_conf.replace(
            "   two_node: 1", "   two_node: 1\n    wait_for_all: 1"
        )
        self.fixture_config_unable_to_connect()
        self.config.http.corosync.set_corosync_conf(
            expected_conf,
            communication_list=[
                dict(label=self.node_labels[0]),
                dict(
                    label=self.node_labels[1],
                    response_code=400,
                    output="an error",
                ),
            ],
        )

        new_options = {"wait_for_all": "1"}
        lib.set_options(
            self.env_assist.get_env(), new_options, skip_offline_nodes=True
        )
        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.info(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.node_labels[0],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.node_labels[1],
                    command="remote/status",
                    reason="an error",
                ),
                fixture.warn(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.node_labels[1],
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_labels[0],
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_labels[1],
                    command="remote/set_corosync_conf",
                    reason="an error",
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=self.node_labels[1],
                ),
            ]
        )


@mock.patch("pcs.lib.commands.quorum.corosync_live.get_quorum_status_text")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class StatusTextTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

    def test_success(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(lib.status_text(self.lib_env), "status text")
        mock_status.assert_called_once_with("mock_runner")

    # TODO: add test for failure


@mock.patch("pcs.lib.commands.quorum.qdevice_client.get_status_text")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class StatusDeviceTextTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

    def test_success(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(lib.status_device_text(self.lib_env), "status text")
        mock_status.assert_called_once_with("mock_runner", False)

    def test_success_verbose(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(
            lib.status_device_text(self.lib_env, True), "status text"
        )
        mock_status.assert_called_once_with("mock_runner", True)


class DeviceNetCertsMixin:
    __client_initialized_counter = 0
    ca_file_path = os.path.join(
        settings.corosync_qdevice_net_client_certs_dir,
        settings.corosync_qdevice_net_client_ca_file_name,
    )

    def fixture_certificates(self):
        class Cert(NamedTuple):
            data: bytes
            b64data: bytes

            @classmethod
            def new(cls, data):
                bytes_data = data.encode()
                return cls(bytes_data, base64.b64encode(bytes_data))

        class CertGroup(NamedTuple):
            ca_cert: Cert
            cert_request: Cert
            signed_request: Cert
            pk12_cert: Cert

        self.certs = CertGroup(
            Cert.new("qnetd CA certificate"),
            Cert.new("qdevice certificate request"),
            Cert.new("qdevice certificate request signed by qnetd"),
            Cert.new("final qdevice certificate in pk12 format to be imported"),
        )

    def fixture_config_fs_client_initialized(self, result=True):
        nssdb_files = [
            "cert9.db",
            "key4.db",
            "pkcs11.txt",
            "cert8.db",
            "key3.db",
            "secmod.db",
        ]
        test_files = nssdb_files[:1] if result else nssdb_files
        for a_file in test_files:
            self.config.fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, a_file
                ),
                return_value=result,
                name=f"fs.exists.nssdb-file.{self.__client_initialized_counter}",
            )
            self.__client_initialized_counter += 1

    def fixture_config_http_get_ca_cert(self, output=None, fail=False):
        self.config.http.corosync.qdevice_net_get_ca_cert(
            communication_list=[
                {
                    "label": self.qnetd_host,
                    "output": (
                        "Unable to read certificate: error description"
                        if fail
                        else (output or self.certs.ca_cert.b64data)
                    ),
                    "response_code": 400 if fail else 200,
                },
            ]
        )

    def fixture_config_http_sign_cert_request(self, output=None, fail=False):
        self.config.http.corosync.qdevice_net_sign_certificate(
            self.cluster_name,
            self.certs.cert_request.data,
            communication_list=[
                {
                    "label": self.qnetd_host,
                    "output": (
                        "an error"
                        if fail
                        else (output or self.certs.signed_request.b64data)
                    ),
                    "response_code": 400 if fail else 200,
                },
            ],
        )


class AddDeviceNetTest(DeviceNetCertsMixin, TestCase):
    # pylint: disable=too-many-public-methods
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

        self.qnetd_host = "qnetd-host"
        self.corosync_conf_name = "corosync-3nodes.conf"
        # the cluster name is defined in the corosync-3nodes.conf file
        self.cluster_name = "test99"
        # nodes are defined in the corosync-3nodes.conf file
        self.cluster_nodes = ["rh7-1", "rh7-2", "rh7-3"]
        self.signed_cert_tmp_file_name = "signed_cert.tmp"
        self.config.env.set_known_nodes(self.cluster_nodes + [self.qnetd_host])

        self.tmp_file_patcher = mock.patch(
            "pcs.lib.corosync.qdevice_net.get_tmp_file"
        )
        self.addCleanup(self.tmp_file_patcher.stop)
        self.tmp_file_mock_obj = TmpFileMock()
        self.addCleanup(self.tmp_file_mock_obj.assert_all_done)
        self.tmp_file_mock = self.tmp_file_patcher.start()
        self.tmp_file_mock.side_effect = (
            self.tmp_file_mock_obj.get_mock_side_effect()
        )

        self.fixture_certificates()

    def fixture_config_success(self, expected_corosync_conf=""):
        mock_open_cert_request_file = mock.mock_open(
            read_data=self.certs.cert_request.data
        )()
        mock_open_pk12_cert_file = mock.mock_open(
            read_data=self.certs.pk12_cert.data
        )()
        tmp_file_mock_calls = []

        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.config.http.corosync.qdevice_net_client_setup(
            self.certs.ca_cert.data, self.cluster_nodes
        )
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_generate_cert(
            self.cluster_name,
            self.config.runner.corosync.qdevice_generated_cert_path,
        )
        self.config.fs.open(
            self.config.runner.corosync.qdevice_generated_cert_path,
            mock_open_cert_request_file,
            mode="rb",
            name="fs.open.cert_request",
        )
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_fs_client_initialized()
        tmp_file_mock_calls.append(
            TmpFileCall(
                self.signed_cert_tmp_file_name,
                is_binary=True,
                orig_content=self.certs.signed_request.data,
            )
        )
        self.config.runner.corosync.qdevice_get_pk12(
            self.signed_cert_tmp_file_name,
            self.config.runner.corosync.qdevice_pk12_cert_path,
        )
        self.config.fs.open(
            self.config.runner.corosync.qdevice_pk12_cert_path,
            mock_open_pk12_cert_file,
            mode="rb",
            name="fs.open.pk12_cert",
        )
        self.config.http.corosync.qdevice_net_client_import_cert_and_key(
            self.certs.pk12_cert.data, self.cluster_nodes
        )
        self.config.http.corosync.qdevice_client_enable(
            node_labels=self.cluster_nodes
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.config.http.corosync.qdevice_client_start(
            node_labels=self.cluster_nodes
        )

        return tmp_file_mock_calls

    def fixture_reports_success(self):
        report_builder = fixture.ReportSequenceBuilder()
        report_builder.info(
            reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
        )
        for node in self.cluster_nodes:
            report_builder.info(
                reports.codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=node,
                _name=f"cert_accepted_by_{node}",
            )
        report_builder.info(
            reports.codes.SERVICE_ACTION_STARTED,
            action=reports.const.SERVICE_ACTION_ENABLE,
            service="corosync-qdevice",
            instance="",
            _name="enable_qdevice_started",
        )
        for node in self.cluster_nodes:
            report_builder.info(
                reports.codes.SERVICE_ACTION_SUCCEEDED,
                action=reports.const.SERVICE_ACTION_ENABLE,
                service="corosync-qdevice",
                node=node,
                instance="",
                _name=f"enable_qdevice_done_on_{node}",
            )
        report_builder.info(
            reports.codes.SERVICE_ACTION_STARTED,
            action=reports.const.SERVICE_ACTION_START,
            service="corosync-qdevice",
            instance="",
            _name="start_qdevice_started",
        )
        for node in self.cluster_nodes:
            report_builder.info(
                reports.codes.SERVICE_ACTION_SUCCEEDED,
                action=reports.const.SERVICE_ACTION_START,
                service="corosync-qdevice",
                node=node,
                instance="",
                _name=f"start_qdevice_done_on_{node}",
            )
        return report_builder.fixtures

    def test_not_live_success_minimal(self):
        original_config = _read_file_rc(self.corosync_conf_name)
        expected_config = original_config.replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            ),
        )

        self.config.env.set_corosync_conf_data(original_config)
        self.config.env.push_corosync_conf(corosync_conf_text=expected_config)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {},
            {},
        )

    def test_not_live_success_full(self):
        original_config = _read_file_rc(self.corosync_conf_name)
        expected_config = original_config.replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        sync_timeout: 34567
                        timeout: 23456
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            connect_timeout: 12345
                            force_ip_version: 4
                            host: qnetd-host
                            port: 4433
                            tie_breaker: lowest
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            exec_ping: ping -q -c 1 "127.0.0.1"
                            interval: 30
                            mode: on
                            sync_timeout: 15
                            timeout: 5
                        }
                    }
                """
            ),
        )

        self.config.env.set_corosync_conf_data(original_config)
        self.config.env.push_corosync_conf(corosync_conf_text=expected_config)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {
                "host": self.qnetd_host,
                "port": "4433",
                "algorithm": "ffsplit",
                "connect_timeout": "12345",
                "force_ip_version": "4",
                "tie_breaker": "lowest",
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
        )

    def test_not_live_error(self):
        self.config.env.set_corosync_conf_data(
            _read_file_rc(self.corosync_conf_name)
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(), "bad model", {}, {}, {}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="model",
                    option_value="bad model",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_not_live_doesnt_care_about_node_names(self):
        # it's not live, it doesn't distribute config to nodes, therefore it
        # doesn't care about node names missing
        self.config.env.set_corosync_conf_data(
            _read_file_rc("corosync-no-node-names.conf")
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(), "bad model", {}, {}, {}
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="model",
                    option_value="bad model",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_fail_if_device_already_set(self):
        corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            ),
        )

        self.config.corosync_conf.load_content(corosync_conf)

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(), "net", {"host": "qnetd-host"}, {}, {}
            ),
            [
                fixture.error(reports.codes.QDEVICE_ALREADY_DEFINED),
            ],
            expected_in_processor=False,
        )

    def test_success_minimal(self):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {},
            {},
        )

        self.env_assist.assert_reports(self.fixture_reports_success())

    def test_some_node_names_missing(self):
        self.config.corosync_conf.load(filename="corosync-some-node-names.conf")

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": self.qnetd_host, "algorithm": "ffsplit"},
                {},
                {},
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_all_node_names_missing(self):
        self.config.corosync_conf.load(filename="corosync-no-node-names.conf")

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": self.qnetd_host, "algorithm": "ffsplit"},
                {},
                {},
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_success_corosync_not_running_not_enabled(self):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        self.config.calls.trim_before(
            "http.corosync.qdevice_client_enable_requests"
        )
        self.config.http.corosync.qdevice_client_enable(
            communication_list=[
                {
                    "label": label,
                    "output": "corosync is not enabled, skipping",
                }
                for label in self.cluster_nodes
            ]
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.config.http.corosync.qdevice_client_start(
            communication_list=[
                {
                    "label": label,
                    "output": "corosync is not running, skipping",
                }
                for label in self.cluster_nodes
            ]
        )

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {},
            {},
        )

        report_list_success = self.fixture_reports_success()
        expected_reports = fixture.ReportSequenceBuilder(
            report_list_success[
                :f"enable_qdevice_done_on_{self.cluster_nodes[0]}"
            ]
        )
        for node in self.cluster_nodes:
            expected_reports.info(
                reports.codes.SERVICE_ACTION_SKIPPED,
                action=reports.const.SERVICE_ACTION_ENABLE,
                service="corosync-qdevice",
                reason="corosync is not enabled",
                node=node,
                instance="",
            )
        expected_reports.fixtures.append(
            report_list_success["start_qdevice_started"]
        )
        for node in self.cluster_nodes:
            expected_reports.info(
                reports.codes.SERVICE_ACTION_SKIPPED,
                action=reports.const.SERVICE_ACTION_START,
                service="corosync-qdevice",
                reason="corosync is not running",
                node=node,
                instance="",
            )
        self.env_assist.assert_reports(expected_reports)

    def assert_success_heuristics_no_exec(self, mode, warn):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }

                        heuristics {
                            mode: %mode%
                        }
                    }
                """.replace(
                    "%mode%", mode
                )
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {},
            {"mode": mode},
        )

        expected_reports = self.fixture_reports_success()
        if warn:
            expected_reports.prepend(
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
                )
            )
        self.env_assist.assert_reports(expected_reports)

    def test_success_heuristics_on_no_exec(self):
        self.assert_success_heuristics_no_exec("on", True)

    def test_success_heuristics_sync_no_exec(self):
        self.assert_success_heuristics_no_exec("sync", True)

    def test_success_heuristics_off_no_exec(self):
        self.assert_success_heuristics_no_exec("off", False)

    def test_success_full(self):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        sync_timeout: 34567
                        timeout: 23456
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            connect_timeout: 12345
                            force_ip_version: 4
                            host: qnetd-host
                            port: 4433
                            tie_breaker: lowest
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            exec_ping: ping -q -c 1 "127.0.0.1"
                            interval: 30
                            mode: on
                            sync_timeout: 15
                            timeout: 5
                        }
                    }
                """
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {
                "host": self.qnetd_host,
                "port": "4433",
                "algorithm": "ffsplit",
                "connect_timeout": "12345",
                "force_ip_version": "4",
                "tie_breaker": "lowest",
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
        )

        self.env_assist.assert_reports(self.fixture_reports_success())

    def test_success_one_node_offline(self):
        node_2_offline_msg = (
            f"Failed connect to {self.cluster_nodes[1]}:2224; No route to host"
        )
        node_2_offline_responses = [
            {"label": self.cluster_nodes[0]},
            {
                "label": self.cluster_nodes[1],
                "was_connected": False,
                "errno": 7,
                "error_msg": node_2_offline_msg,
            },
            {"label": self.cluster_nodes[2]},
        ]

        def node_2_offline_warning(command):
            return fixture.warn(
                reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=self.cluster_nodes[1],
                reason=node_2_offline_msg,
                command=command,
            )

        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        self.config.remove("http.corosync.qdevice_net_client_setup_requests")
        self.config.remove("http.corosync.qdevice_net_client_setup_responses")
        self.config.http.corosync.qdevice_net_client_setup(
            self.certs.ca_cert.data,
            communication_list=node_2_offline_responses,
            before="fs.exists.nssdb-file.0",
        )
        self.config.trim_before(
            "http.corosync.qdevice_net_client_import_cert_and_key_requests"
        )
        self.config.http.corosync.qdevice_net_client_import_cert_and_key(
            self.certs.pk12_cert.data,
            communication_list=node_2_offline_responses,
        )
        self.config.http.corosync.qdevice_client_enable(
            communication_list=node_2_offline_responses
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf,
            skip_offline_targets=True,
        )
        self.config.http.corosync.qdevice_client_start(
            communication_list=node_2_offline_responses
        )

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {},
            {},
            skip_offline_nodes=True,
        )

        expected_reports = self.fixture_reports_success()
        expected_reports.insert(
            f"cert_accepted_by_{self.cluster_nodes[0]}",
            node_2_offline_warning(
                "remote/qdevice_net_client_init_certificate_storage"
            ),
        )
        expected_reports.replace(
            f"cert_accepted_by_{self.cluster_nodes[1]}",
            node_2_offline_warning(
                "remote/qdevice_net_client_import_certificate"
            ),
        )
        expected_reports.replace(
            f"enable_qdevice_done_on_{self.cluster_nodes[1]}",
            node_2_offline_warning("remote/qdevice_client_enable"),
        )
        expected_reports.replace(
            f"start_qdevice_done_on_{self.cluster_nodes[1]}",
            node_2_offline_warning("remote/qdevice_client_start"),
        )
        self.env_assist.assert_reports(expected_reports)

    def test_invalid_options(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"bad_option": "bad_value"},
                {"mode": "bad-mode", "bad_heur": "abc", "exec_bad.name": ""},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["bad_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="mode",
                    option_value="bad-mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["bad_heur"],
                    option_type="heuristics",
                    allowed=["interval", "mode", "sync_timeout", "timeout"],
                    allowed_patterns=["exec_NAME"],
                ),
                fixture.error(
                    reports.codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["exec_bad.name"],
                    option_type="heuristics",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="exec_bad.name",
                    option_value="",
                    allowed_values="a command to be run",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_invalid_options_forced(self):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        bad_option: bad_value
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }

                        heuristics {
                            bad_heur: abc
                            mode: bad-mode
                        }
                    }
                """
            ),
        )

        tmp_file_mock_calls = self.fixture_config_success(
            expected_corosync_conf
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": "qnetd-host", "algorithm": "ffsplit"},
            {"bad_option": "bad_value"},
            {
                "mode": "bad-mode",
                "bad_heur": "abc",
            },
            force_options=True,
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"],
                    allowed_patterns=[],
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad-mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["bad_heur"],
                    option_type="heuristics",
                    allowed=["interval", "mode", "sync_timeout", "timeout"],
                    allowed_patterns=["exec_NAME"],
                ),
            ]
            + self.fixture_reports_success().values
        )

    def test_invalid_model(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(), "bad_model", {}, {}, {}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="model",
                    option_value="bad_model",
                    allowed_values=["net"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_invalid_model_forced(self):
        expected_corosync_conf = _read_file_rc(self.corosync_conf_name).replace(
            "    provider: corosync_votequorum\n",
            outdent(
                """\
                    provider: corosync_votequorum

                    device {
                        model: bad_model
                    }
                """
            ),
        )

        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        # model is not "net" - do not set up certificates
        self.config.http.corosync.qdevice_client_enable(
            node_labels=self.cluster_nodes
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.config.http.corosync.qdevice_client_start(
            node_labels=self.cluster_nodes
        )

        lib.add_device(
            self.env_assist.get_env(), "bad_model", {}, {}, {}, force_model=True
        )

        # model is not "net" - do not report certificates setup
        expected_reports = self.fixture_reports_success()[
            "enable_qdevice_started":
        ]
        expected_reports.prepend(
            fixture.warn(
                reports.codes.INVALID_OPTION_VALUE,
                option_name="model",
                option_value="bad_model",
                allowed_values=["net"],
                cannot_be_empty=False,
                forbidden_characters=None,
            )
        )
        self.env_assist.assert_reports(expected_reports)

    def test_get_ca_cert_error_communication(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_get_ca_cert_requests"
        )
        self.config.http.corosync.qdevice_net_get_ca_cert(
            communication_list=[
                {
                    "label": self.qnetd_host,
                    "response_code": 400,
                    "output": "Unable to read certificate: error description",
                },
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
                skip_offline_nodes=True,  # test that this does not matter
            ),
            [],  # an empty LibraryError is raised
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(
                self.fixture_reports_success()[
                    :f"cert_accepted_by_{self.cluster_nodes[0]}"
                ]
            ).error(
                reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=None,
                node=self.qnetd_host,
                command="remote/qdevice_net_get_ca_certificate",
                reason="Unable to read certificate: error description",
            )
        )

    def test_get_ca_cert_error_decode_certificate(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_get_ca_cert_requests"
        )
        self.fixture_config_http_get_ca_cert(
            output="invalid base64 encoded certificate data"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": self.qnetd_host, "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
                skip_offline_nodes=True,  # test that this does not matter
            )
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(
                self.fixture_reports_success()[
                    :f"cert_accepted_by_{self.cluster_nodes[0]}"
                ]
            ).error(
                reports.codes.INVALID_RESPONSE_FORMAT,
                force_code=None,
                node=self.qnetd_host,
            )
        )

    def test_error_client_setup(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_client_setup_requests"
        )
        self.config.http.corosync.qdevice_net_client_setup(
            self.certs.ca_cert.data,
            communication_list=[
                {"label": self.cluster_nodes[0]},
                {
                    "label": self.cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": self.cluster_nodes[2]},
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            )
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(
                self.fixture_reports_success()[
                    :f"cert_accepted_by_{self.cluster_nodes[0]}"
                ]
            ).error(
                reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=reports.codes.SKIP_OFFLINE_NODES,
                node=self.cluster_nodes[1],
                command=("remote/qdevice_net_client_init_certificate_storage"),
                reason="some error occurred",
            )
        )

    def test_generate_cert_request_error(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_generate_cert")
        self.config.runner.corosync.qdevice_generate_cert(
            self.cluster_name,
            stdout="",
            stderr="some error occurred",
            returncode=1,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason="some error occurred",
                ),
            ],
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            self.fixture_reports_success()[
                :f"cert_accepted_by_{self.cluster_nodes[0]}"
            ]
        )

    def test_sign_certificate_error_communication(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_sign_certificate_requests"
        )
        self.config.http.corosync.qdevice_net_sign_certificate(
            self.cluster_name,
            self.certs.cert_request.data,
            communication_list=[
                {
                    "label": self.qnetd_host,
                    "response_code": 400,
                    "output": "some error occurred",
                },
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            )
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(
                self.fixture_reports_success()[
                    :f"cert_accepted_by_{self.cluster_nodes[0]}"
                ]
            ).error(
                reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=None,
                node=self.qnetd_host,
                command="remote/qdevice_net_sign_node_certificate",
                reason="some error occurred",
            )
        )

    def test_sign_certificate_error_decode_certificate(self):
        dummy_tmp_file_mock_calls = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_sign_certificate_requests"
        )
        self.fixture_config_http_sign_cert_request(
            output="invalid base64 encoded certificate data"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            )
        )

        self.env_assist.assert_reports(
            fixture.ReportSequenceBuilder(
                self.fixture_reports_success()[
                    :f"cert_accepted_by_{self.cluster_nodes[0]}"
                ]
            ).error(
                reports.codes.INVALID_RESPONSE_FORMAT,
                force_code=None,
                node=self.qnetd_host,
            )
        )

    def test_certificate_to_pk12_error(self):
        tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)
        self.config.trim_before("runner.corosync.qdevice_get_pk12")
        self.config.runner.corosync.qdevice_get_pk12(
            self.signed_cert_tmp_file_name,
            output_path=None,
            stdout="",
            stderr="some error occurred",
            returncode=1,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="some error occurred",
                ),
            ],
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            self.fixture_reports_success()[
                :f"cert_accepted_by_{self.cluster_nodes[0]}"
            ]
        )

    def test_client_import_cert_error(self):
        tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)
        self.config.trim_before(
            "http.corosync.qdevice_net_client_import_cert_and_key_requests"
        )
        self.config.http.corosync.qdevice_net_client_import_cert_and_key(
            self.certs.pk12_cert.data,
            communication_list=[
                {"label": self.cluster_nodes[0]},
                {
                    "label": self.cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": self.cluster_nodes[2]},
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                {},
            )
        )

        success_reports = self.fixture_reports_success()
        expected_reports = success_reports[
            :f"cert_accepted_by_{self.cluster_nodes[1]}"
        ]
        expected_reports.append(
            fixture.error(
                reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=reports.codes.SKIP_OFFLINE_NODES,
                node=self.cluster_nodes[1],
                command="remote/qdevice_net_client_import_certificate",
                reason="some error occurred",
            )
        )
        expected_reports.append(
            success_reports[f"cert_accepted_by_{self.cluster_nodes[2]}"]
        )
        self.env_assist.assert_reports(expected_reports)


class DeviceNetCertificateSetupLocal(DeviceNetCertsMixin, TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.qnetd_host = "qnetd-host"
        self.cluster_name = "my-cluster"
        self.signed_cert_tmp_file_name = "signed_cert.tmp"
        self.pk12_cert_tmp_file_name = "pk12_cert.tmp"

        self.tmp_file_patcher = mock.patch(
            "pcs.lib.corosync.qdevice_net.get_tmp_file"
        )
        self.addCleanup(self.tmp_file_patcher.stop)
        self.tmp_file_mock_obj = TmpFileMock()
        self.addCleanup(self.tmp_file_mock_obj.assert_all_done)
        self.tmp_file_mock = self.tmp_file_patcher.start()
        self.tmp_file_mock.side_effect = (
            self.tmp_file_mock_obj.get_mock_side_effect()
        )

        self.fixture_certificates()

    def fixture_config_success(self, initialized=True):
        mock_open_ca_file = mock.mock_open()()
        mock_open_cert_request_file = mock.mock_open(
            read_data=self.certs.cert_request.data
        )()
        mock_open_pk12_cert_file = mock.mock_open(
            read_data=self.certs.pk12_cert.data
        )()
        tmp_file_mock_calls = []

        self.fixture_config_http_get_ca_cert()
        self.fixture_config_fs_client_initialized(initialized)
        if initialized:
            self.config.fs.rmtree(
                settings.corosync_qdevice_net_client_certs_dir
            )
        self.config.fs.exists(
            settings.corosync_qdevice_net_client_certs_dir,
            return_value=initialized,
            name="fs.exists.certs-dir",
        )
        if not initialized:
            self.config.fs.makedirs(
                settings.corosync_qdevice_net_client_certs_dir, 0o700
            )
        self.config.fs.open(
            self.ca_file_path, mock_open_ca_file, mode="wb", name="fs.open.ca"
        )
        self.config.runner.corosync.qdevice_init_cert_storage(self.ca_file_path)
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_generate_cert(
            self.cluster_name,
            self.config.runner.corosync.qdevice_generated_cert_path,
        )
        self.config.fs.open(
            self.config.runner.corosync.qdevice_generated_cert_path,
            mock_open_cert_request_file,
            mode="rb",
            name="fs.open.cert_request",
        )
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_fs_client_initialized()
        tmp_file_mock_calls.append(
            TmpFileCall(
                self.signed_cert_tmp_file_name,
                is_binary=True,
                orig_content=self.certs.signed_request.data,
            )
        )
        self.config.runner.corosync.qdevice_get_pk12(
            self.signed_cert_tmp_file_name,
            self.config.runner.corosync.qdevice_pk12_cert_path,
        )
        self.config.fs.open(
            self.config.runner.corosync.qdevice_pk12_cert_path,
            mock_open_pk12_cert_file,
            mode="rb",
            name="fs.open.pk12_cert",
        )
        self.fixture_config_fs_client_initialized()
        tmp_file_mock_calls.append(
            TmpFileCall(
                self.pk12_cert_tmp_file_name,
                is_binary=True,
                orig_content=self.certs.pk12_cert.data,
            )
        )
        self.config.runner.corosync.qdevice_import_pk12(
            self.pk12_cert_tmp_file_name
        )

        return mock_open_ca_file, tmp_file_mock_calls

    def test_not_live(self):
        self.config.env.set_corosync_conf_data("corosync config")
        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                )
            ]
        )

    def test_success_client_not_initialized(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success(
            False
        )
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.device_net_certificate_setup_local(
            self.env_assist.get_env(), self.qnetd_host, self.cluster_name
        )

        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_success_client_initialized(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)

        lib.device_net_certificate_setup_local(
            self.env_assist.get_env(), self.qnetd_host, self.cluster_name
        )

        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_http_get_ca_cert(self):
        self.fixture_config_http_get_ca_cert(fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=None,
                    node=self.qnetd_host,
                    command="remote/qdevice_net_get_ca_certificate",
                    reason="Unable to read certificate: error description",
                ),
            ]
        )

    def test_fail_write_ca_cert_to_file(self):
        (
            dummy_mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.config.trim_before("fs.open.ca")
        self.config.fs.open(
            self.ca_file_path,
            side_effect=OSError(1, "an error", self.ca_file_path),
            mode="wb",
            name="fs.open.ca",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )

    def test_fail_init_cert_storage(self):
        (
            mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_init_cert_storage")
        self.config.runner.corosync.qdevice_init_cert_storage(
            self.ca_file_path, stderr="an error", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_generate_cert_request(self):
        (
            mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_generate_cert")
        self.config.runner.corosync.qdevice_generate_cert(
            self.cluster_name, stdout="stdout", stderr="an error", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason="an error\nstdout",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_read_cert_request(self):
        (
            mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.config.trim_before("fs.open.cert_request")
        self.config.fs.open(
            self.config.runner.corosync.qdevice_generated_cert_path,
            side_effect=OSError(
                1,
                "an error",
                self.config.runner.corosync.qdevice_generated_cert_path,
            ),
            mode="rb",
            name="fs.open.cert_request",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason=f"{self.config.runner.corosync.qdevice_generated_cert_path}: an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_http_sign_cert(self):
        (
            mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_sign_certificate_requests"
        )
        self.fixture_config_http_sign_cert_request(fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=None,
                    node=self.qnetd_host,
                    command="remote/qdevice_net_sign_node_certificate",
                    reason="an error",
                ),
            ]
        )

    def test_fail_write_signed_cert_to_tmpfile(self):
        (
            mock_open_ca_file,
            dummy_tmp_file_mock_calls,
        ) = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(
            [
                TmpFileCall(
                    self.signed_cert_tmp_file_name,
                    is_binary=True,
                    orig_content=OSError(
                        1, "an error", self.signed_cert_tmp_file_name
                    ),
                )
            ]
        )
        self.config.trim_before("runner.corosync.qdevice_get_pk12")

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_convert_signed_cert_to_pk12(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls[:1])
        self.config.trim_before("runner.corosync.qdevice_get_pk12")
        self.config.runner.corosync.qdevice_get_pk12(
            self.signed_cert_tmp_file_name,
            stdout="",
            stderr="an error",
            returncode=1,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_read_pk12_certificate(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls[:1])
        self.config.trim_before("fs.open.pk12_cert")
        self.config.fs.open(
            self.config.runner.corosync.qdevice_pk12_cert_path,
            side_effect=OSError(
                1,
                "an error",
                self.config.runner.corosync.qdevice_pk12_cert_path,
            ),
            mode="rb",
            name="fs.open.pk12_cert",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason=f"{self.config.runner.corosync.qdevice_pk12_cert_path}: an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_write_pk12_to_tmpfile(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(
            tmp_file_mock_calls[:1]
            + [
                TmpFileCall(
                    self.signed_cert_tmp_file_name,
                    is_binary=True,
                    orig_content=OSError(
                        1, "an error", self.pk12_cert_tmp_file_name
                    ),
                )
            ]
        )
        self.config.trim_before("runner.corosync.qdevice_import_pk12")

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)

    def test_fail_import_pk12(self):
        mock_open_ca_file, tmp_file_mock_calls = self.fixture_config_success()
        self.tmp_file_mock_obj.set_calls(tmp_file_mock_calls)
        self.config.trim_before("runner.corosync.qdevice_import_pk12")
        self.config.runner.corosync.qdevice_import_pk12(
            self.pk12_cert_tmp_file_name, stderr="an error", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            ),
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="an error",
                ),
            ],
            expected_in_processor=False,
        )
        mock_open_ca_file.write.assert_called_once_with(self.certs.ca_cert.data)


class DeviceNetCertificateCheckLocal(DeviceNetCertsMixin, TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.qnetd_host = "qnetd-host"
        self.cluster_name = "my-cluster"
        self.fixture_certificates()

    @staticmethod
    def fixture_cert_data(subject, data):
        return dedent(
            f"""\
            some cert plaintext data
              Subject: "CN={subject}"
            some cert plaintext data
            -----BEGIN CERTIFICATE-----
            {data.decode()}
            -----END CERTIFICATE-----
            """
        )

    def fixture_show_cluster_cert(self, cluster_name, fail=False):
        self.config.runner.corosync.qdevice_show_cert(
            "Cluster Cert",
            "" if fail else self.fixture_cert_data(cluster_name, b"whatever"),
            stderr="stderr message" if fail else "",
            returncode=1 if fail else 0,
            name="runner.corosync.qdevice_show_cert.cluster",
        )

    def fixture_show_ca_cert(self, data, fail=False):
        self.config.runner.corosync.qdevice_show_cert(
            "QNet CA",
            data,
            ascii_only=True,
            stderr="stderr message" if fail else "",
            returncode=1 if fail else 0,
            name="runner.corosync.qdevice_show_cert.ca",
        )

    def fixture_config_success(self):
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_list_certs()
        self.fixture_show_cluster_cert(self.cluster_name)
        self.fixture_config_http_get_ca_cert(
            base64.b64encode(
                self.fixture_cert_data(
                    "whatever", self.certs.ca_cert.b64data
                ).encode()
            ),
        )
        self.fixture_show_ca_cert(
            self.fixture_cert_data("whatever", self.certs.ca_cert.b64data),
        )

    def test_not_live(self):
        self.config.env.set_corosync_conf_data("corosync config")
        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_setup_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                )
            ]
        )

    def test_success_certificate_matches(self):
        self.fixture_config_success()

        self.assertTrue(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_success_client_not_initialized(self):
        self.fixture_config_fs_client_initialized(False)

        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_success_cluster_cert_missing(self):
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_list_certs("QNet CA  x,x,x")

        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_success_ca_cert_missing(self):
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_list_certs("Cluster Cert   x,x,x")

        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_success_cluster_cert_wrong_cluster_name(self):
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_list_certs()
        self.fixture_show_cluster_cert(self.cluster_name + "X")

        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_success_qa_cert_not_matching(self):
        self.fixture_config_fs_client_initialized()
        self.config.runner.corosync.qdevice_list_certs()
        self.fixture_show_cluster_cert(self.cluster_name)
        self.fixture_config_http_get_ca_cert(
            base64.b64encode(
                self.fixture_cert_data(
                    "whatever", self.certs.ca_cert.b64data
                ).encode()
            ),
        )
        self.fixture_show_ca_cert(
            self.fixture_cert_data(
                "whatever",
                base64.b64encode(self.certs.ca_cert.data + b"X"),
            ),
        )

        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_fail_local_ca_cert_format(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_show_cert.ca")
        self.fixture_show_ca_cert("unexpected data format")

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_BAD_FORMAT,
                    force_code=None,
                ),
            ]
        )

    def test_fail_local_ca_cert_read(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_show_cert.ca")
        self.fixture_show_ca_cert("stdout", fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_READ_ERROR,
                    force_code=None,
                    reason="stderr message\nstdout",
                ),
            ]
        )

    def test_fail_remote_ca_cert_format(self):
        self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_get_ca_cert_requests"
        )
        self.fixture_config_http_get_ca_cert(
            base64.b64encode(b"unexpected data format")
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_BAD_FORMAT,
                    force_code=None,
                ),
            ]
        )

    def test_fail_remote_ca_cert_fetch(self):
        self.fixture_config_success()
        self.config.trim_before(
            "http.corosync.qdevice_net_get_ca_cert_requests"
        )
        self.fixture_config_http_get_ca_cert(fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=None,
                    node=self.qnetd_host,
                    command="remote/qdevice_net_get_ca_certificate",
                    reason="Unable to read certificate: error description",
                ),
            ]
        )

    def test_fail_cluster_cert_format(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_show_cert.cluster")
        self.fixture_show_cluster_cert("unexpected data format")

        # We don't do full parsing, we just look for a specific string. So no
        # there is no exception raised.
        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_fail_cluster_cert_read(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_show_cert.cluster")
        self.fixture_show_cluster_cert("stdout", fail=True)

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_READ_ERROR,
                    force_code=None,
                    reason="stderr message",
                ),
            ]
        )

    def test_fail_cert_list_format(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_list_certs")
        self.config.runner.corosync.qdevice_list_certs("unexpected data format")

        # We don't do full parsing, we just look for a specific string. So no
        # there is no exception raised.
        self.assertFalse(
            lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )

    def test_fail_cert_list_read(self):
        self.fixture_config_success()
        self.config.trim_before("runner.corosync.qdevice_list_certs")
        self.config.runner.corosync.qdevice_list_certs(
            stdout="some stdout", stderr="Error message", returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.device_net_certificate_check_local(
                self.env_assist.get_env(), self.qnetd_host, self.cluster_name
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_READ_ERROR,
                    force_code=None,
                    reason="Error message\nsome stdout",
                ),
            ]
        )


class RemoveDeviceHeuristics(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_enabled_if_not_live(self):
        (
            self.config.env.set_corosync_conf_data(
                _read_file_rc("corosync-3nodes.conf")
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device_heuristics(self.env_assist.get_env()),
            [
                fixture.error(reports.codes.QDEVICE_NOT_DEFINED),
            ],
            expected_in_processor=False,
        )

    def test_success(self):
        config_no_heuristics = _read_file_rc("corosync-3nodes-qdevice.conf")
        config_heuristics = config_no_heuristics.replace(
            outdent(
                """\
                    net {
                        host: 127.0.0.1
                    }
            """
            ),
            outdent(
                """\
                    net {
                        host: 127.0.0.1
                    }

                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
            """
            ),
        )

        self.config.corosync_conf.load_content(config_heuristics)
        self.config.env.push_corosync_conf(
            corosync_conf_text=config_no_heuristics
        )

        lib.remove_device_heuristics(self.env_assist.get_env())

    def test_fail_if_device_not_set(self):
        self.config.corosync_conf.load_content(
            _read_file_rc("corosync-3nodes.conf")
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device_heuristics(self.env_assist.get_env()),
            [
                fixture.error(reports.codes.QDEVICE_NOT_DEFINED),
            ],
            expected_in_processor=False,
        )


class RemoveDeviceNetTest(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["rh7-1", "rh7-2", "rh7-3"])

    @staticmethod
    def conf_2nodes(quorum_line):
        cluster_nodes = ["rh7-1", "rh7-2"]
        original_conf = _read_file_rc("corosync-qdevice.conf")
        expected_conf = original_conf.replace(
            outdent(
                """\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }
                    }
                }
                """
            ),
            # cluster consists of two nodes, two_node must be set
            outdent(
                """\
                quorum {
                    provider: corosync_votequorum
                    """
                + quorum_line
                + """
                }
                """
            ),
        )
        return cluster_nodes, original_conf, expected_conf

    @staticmethod
    def conf_3nodes():
        cluster_nodes = ["rh7-1", "rh7-2", "rh7-3"]
        original_conf = _read_file_rc("corosync-3nodes-qdevice.conf")
        expected_conf = original_conf.replace(
            outdent(
                """\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }
                    }
                }
                """
            ),
            outdent(
                """\
                quorum {
                    provider: corosync_votequorum
                }
                """
            ),
        )
        return cluster_nodes, original_conf, expected_conf

    def fixture_config_http_qdevice_net_destroy(self, nodes, responses=None):
        responses = responses or [{"label": node} for node in nodes]
        self.config.http.add_communication(
            "http.qdevice_net_destroy",
            responses,
            action="remote/qdevice_net_client_destroy",
            response_code=200,
        )

    def fixture_config_success(
        self,
        cluster_nodes,
        original_corosync_conf,
        expected_corosync_conf,
        need_stopped_cluster=False,
    ):
        self.config.corosync_conf.load_content(original_corosync_conf)
        self.config.http.corosync.qdevice_client_disable(
            node_labels=cluster_nodes
        )
        self.config.http.corosync.qdevice_client_stop(node_labels=cluster_nodes)
        self.fixture_config_http_qdevice_net_destroy(cluster_nodes)
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf,
            need_stopped_cluster=need_stopped_cluster,
        )

    def fixture_config_success_sbd_part(self, sbd_installed, sbd_enabled):
        self.config.services.is_installed(
            "sbd",
            return_value=sbd_installed,
            before="http.corosync.qdevice_client_disable_requests",
        )
        if sbd_installed:
            self.config.services.is_enabled(
                "sbd",
                return_value=sbd_enabled,
                before="http.corosync.qdevice_client_disable_requests",
            )

    @staticmethod
    def fixture_reports_success(cluster_nodes, atb_enabled=False):
        report_list = []
        if atb_enabled:
            report_list.append(
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
                )
            )
        report_list += (
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=node,
                    instance="",
                )
                for node in cluster_nodes
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=node,
                    instance="",
                )
                for node in cluster_nodes
            ]
            + [
                fixture.info(reports.codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED),
            ]
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    node=node,
                )
                for node in cluster_nodes
            ]
        )
        return report_list

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_not_live_success(self):
        dummy_cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            # cluster consists of two nodes, two_node must be set
            "two_node: 1"
        )
        (
            self.config.env.set_corosync_conf_data(
                original_conf
            ).env.push_corosync_conf(corosync_conf_text=expected_conf)
        )

        lib.remove_device(self.env_assist.get_env())

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_not_live_error(self):
        (
            self.config.env.set_corosync_conf_data(
                _read_file_rc("corosync-3nodes.conf")
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(self.env_assist.get_env()),
            [
                fixture.error(reports.codes.QDEVICE_NOT_DEFINED),
            ],
            expected_in_processor=False,
        )

    def test_not_live_doesnt_care_about_node_names(self):
        # it's not live, it doesn't distribute config to nodes, therefore it
        # doesn't care about node names missing
        dummy_cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            # cluster consists of two nodes, two_node must be set
            "two_node: 1"
        )
        original_conf = re.sub(r"\s+name: .*\n", "\n", original_conf)
        expected_conf = re.sub(r"\s+name: .*\n", "\n", expected_conf)
        (
            self.config.env.set_corosync_conf_data(
                original_conf
            ).env.push_corosync_conf(corosync_conf_text=expected_conf)
        )

        lib.remove_device(self.env_assist.get_env())

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_fail_if_device_not_set(self):
        self.config.corosync_conf.load_content(
            _read_file_rc("corosync-3nodes.conf")
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(self.env_assist.get_env()),
            [
                fixture.error(reports.codes.QDEVICE_NOT_DEFINED),
            ],
            expected_in_processor=False,
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_2nodes_no_sbd(self):
        # cluster consists of two nodes, two_node must be set
        cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            "two_node: 1"
        )
        self.fixture_config_success(cluster_nodes, original_conf, expected_conf)
        self.fixture_config_success_sbd_part(False, False)
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports(
            self.fixture_reports_success(cluster_nodes)
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_2nodes_sbd_installed_disabled(self):
        # cluster consists of two nodes, two_node must be set
        cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            "two_node: 1"
        )
        self.fixture_config_success(cluster_nodes, original_conf, expected_conf)
        self.fixture_config_success_sbd_part(True, False)
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports(
            self.fixture_reports_success(cluster_nodes, atb_enabled=False)
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_2nodes_sbd_enabled(self):
        # cluster consists of two nodes and SBD is in use, so teo_nodes must be
        # disabled and auto_tie_breaker must be enabled
        cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            "auto_tie_breaker: 1"
        )
        self.fixture_config_success(
            cluster_nodes,
            original_conf,
            expected_conf,
            need_stopped_cluster=True,
        )
        self.fixture_config_success_sbd_part(True, True)
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports(
            self.fixture_reports_success(cluster_nodes, atb_enabled=True)
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["/dev/sdb"])
    def test_success_2nodes_sbd_enabled_with_devices(self):
        # cluster consists of two nodes, but SBD with shared storage is in use
        # auto tie breaker doesn't need to be enabled
        cluster_nodes, original_conf, expected_conf = self.conf_2nodes(
            "two_node: 1"
        )
        self.fixture_config_success(cluster_nodes, original_conf, expected_conf)
        self.fixture_config_success_sbd_part(True, True)
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports(
            self.fixture_reports_success(cluster_nodes, atb_enabled=False)
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_3nodes(self):
        # with odd number of nodes it doesn't matter if sbd is used
        cluster_nodes, original_conf, expected_conf = self.conf_3nodes()
        self.fixture_config_success(cluster_nodes, original_conf, expected_conf)
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports(
            self.fixture_reports_success(cluster_nodes)
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_3nodes_file(self):
        # with odd number of nodes it doesn't matter if sbd is used
        dummy_cluster_nodes, original_conf, expected_conf = self.conf_3nodes()
        (
            self.config.env.set_corosync_conf_data(
                original_conf
            ).env.push_corosync_conf(corosync_conf_text=expected_conf)
        )
        lib.remove_device(self.env_assist.get_env())
        self.env_assist.assert_reports([])

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_3nodes_one_node_offline(self):
        # with odd number of nodes it doesn't matter if sbd is used
        cluster_nodes, original_conf, expected_conf = self.conf_3nodes()
        node_2_offline_msg = (
            "Failed connect to {0}:2224; No route to host"
        ).format(cluster_nodes[1])
        node_2_offline_responses = [
            {"label": cluster_nodes[0]},
            {
                "label": cluster_nodes[1],
                "was_connected": False,
                "errno": 7,
                "error_msg": node_2_offline_msg,
            },
            {"label": cluster_nodes[2]},
        ]

        def node_2_offline_warning(command):
            return fixture.warn(
                reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=cluster_nodes[1],
                reason=node_2_offline_msg,
                command=command,
            )

        self.config.corosync_conf.load_content(original_conf)
        self.config.http.corosync.qdevice_client_disable(
            communication_list=node_2_offline_responses
        )
        self.config.http.corosync.qdevice_client_stop(
            communication_list=node_2_offline_responses
        )
        self.fixture_config_http_qdevice_net_destroy(
            cluster_nodes, node_2_offline_responses
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_conf,
            skip_offline_targets=True,
        )

        lib.remove_device(self.env_assist.get_env(), skip_offline_nodes=True)

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=cluster_nodes[0],
                    instance="",
                ),
                node_2_offline_warning("remote/qdevice_client_disable"),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=cluster_nodes[2],
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=cluster_nodes[0],
                    instance="",
                ),
                node_2_offline_warning("remote/qdevice_client_stop"),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=cluster_nodes[2],
                    instance="",
                ),
                fixture.info(reports.codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED),
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    node=cluster_nodes[0],
                ),
                node_2_offline_warning("remote/qdevice_net_client_destroy"),
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    node=cluster_nodes[2],
                ),
            ]
        )

    def test_some_node_names_missing(self):
        dummy_nodes, original_conf, dummy_expected_conf = self.conf_2nodes(
            # cluster consists of two nodes, two_node must be set
            "two_node: 1"
        )
        original_conf = re.sub(r"\s+name: rh7-1\n", "\n", original_conf)

        self.config.corosync_conf.load_content(original_conf)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_all_node_names_missing(self):
        dummy_nodes, original_conf, dummy_expected_conf = self.conf_2nodes(
            # cluster consists of two nodes, two_node must be set
            "two_node: 1"
        )
        original_conf = re.sub(r"\s+name: .*\n", "\n", original_conf)

        self.config.corosync_conf.load_content(original_conf)

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(self.env_assist.get_env()), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_error_disable_qdevice(self):
        cluster_nodes, original_conf, dummy_expected_conf = self.conf_3nodes()

        self.config.corosync_conf.load_content(original_conf)
        self.config.http.corosync.qdevice_client_disable(
            communication_list=[
                {"label": cluster_nodes[0]},
                {
                    "label": cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": cluster_nodes[2]},
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(
                self.env_assist.get_env(), skip_offline_nodes=False
            ),
            [],  # an empty LibraryError is raised
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=cluster_nodes[0],
                    instance="",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=cluster_nodes[1],
                    command="remote/qdevice_client_disable",
                    reason="some error occurred",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=cluster_nodes[2],
                    instance="",
                ),
            ]
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_error_stop_qdevice(self):
        cluster_nodes, original_conf, dummy_expected_conf = self.conf_3nodes()

        self.config.corosync_conf.load_content(original_conf)
        self.config.http.corosync.qdevice_client_disable(
            node_labels=cluster_nodes
        )
        self.config.http.corosync.qdevice_client_stop(
            communication_list=[
                {"label": cluster_nodes[0]},
                {
                    "label": cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": cluster_nodes[2]},
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(
                self.env_assist.get_env(), skip_offline_nodes=False
            ),
            [],  # an empty LibraryError is raised
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=node,
                    instance="",
                )
                for node in cluster_nodes
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    instance="",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=cluster_nodes[0],
                    instance="",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=cluster_nodes[1],
                    command="remote/qdevice_client_stop",
                    reason="some error occurred",
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=cluster_nodes[2],
                    instance="",
                ),
            ]
        )

    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_error_destroy_qdevice_net(self):
        cluster_nodes, original_conf, dummy_expected_conf = self.conf_3nodes()

        self.config.corosync_conf.load_content(original_conf)
        self.config.http.corosync.qdevice_client_disable(
            node_labels=cluster_nodes
        )
        self.config.http.corosync.qdevice_client_stop(node_labels=cluster_nodes)
        self.fixture_config_http_qdevice_net_destroy(
            cluster_nodes,
            [
                {"label": cluster_nodes[0]},
                {
                    "label": cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": cluster_nodes[2]},
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_device(
                self.env_assist.get_env(), skip_offline_nodes=False
            ),
            [],  # an empty LibraryError is raised
            expected_in_processor=False,
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="corosync-qdevice",
                    node=node,
                    instance="",
                )
                for node in cluster_nodes
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_STOP,
                    service="corosync-qdevice",
                    node=node,
                    instance="",
                )
                for node in cluster_nodes
            ]
            + [
                fixture.info(reports.codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED),
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    node=cluster_nodes[0],
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node=cluster_nodes[1],
                    command="remote/qdevice_net_client_destroy",
                    reason="some error occurred",
                ),
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    node=cluster_nodes[2],
                ),
            ]
        )


@mock.patch.object(LibraryEnvironment, "push_corosync_conf")
@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
class UpdateDeviceTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def assert_success_heuristics_add_no_exec(
        self, mock_get_corosync, mock_push_corosync, mode, warn
    ):
        original_conf = _read_file_rc("corosync-3nodes-qdevice.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(lib_env, {}, {}, {"mode": mode})

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "            host: 127.0.0.1\n",
                outdent(
                    """\
                                host: 127.0.0.1
                            }

                            heuristics {
                                mode: %mode%
                    """.replace(
                        "%mode%", mode
                    )
                ),
            ),
        )
        expected_reports = []
        if warn:
            expected_reports += [
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
                )
            ]
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list, expected_reports
        )

    def assert_success_heuristics_update_no_exec(
        self, mock_get_corosync, mock_push_corosync, mode, warn
    ):
        original_conf = _read_file_rc("corosync-3nodes-qdevice-heuristics.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(lib_env, {}, {}, {"mode": mode, "exec_ls": ""})

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        expected_config = re.sub(
            re.compile(r"heuristics {[^}]*}\n", re.MULTILINE | re.DOTALL),
            outdent(
                """\
                heuristics {
                            mode: %mode%
                        }
                """
            ).replace("%mode%", mode),
            original_conf,
        )
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            expected_config,
        )
        expected_reports = []
        if warn:
            expected_reports += [
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
                )
            ]
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list, expected_reports
        )

    def test_no_device(self, mock_get_corosync, mock_push_corosync):
        original_conf = _read_file_rc("corosync-3nodes.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.update_device(lib_env, {"host": "127.0.0.1"}, {}, {}),
            (
                reports.ReportItemSeverity.ERROR,
                reports.codes.QDEVICE_NOT_DEFINED,
                {},
            ),
        )

        mock_push_corosync.assert_not_called()

    def test_success(self, mock_get_corosync, mock_push_corosync):
        original_conf = _read_file_rc("corosync-3nodes-qdevice.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(
            lib_env,
            {"host": "127.0.0.2"},
            {"timeout": "12345"},
            {"mode": "on", "exec_ls": "test -f /tmp/test"},
        )

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "            host: 127.0.0.1\n",
                outdent(
                    """\
                                host: 127.0.0.2
                            }

                            heuristics {
                                exec_ls: test -f /tmp/test
                                mode: on
                    """
                ),
            ).replace("model: net", "model: net\n        timeout: 12345"),
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_success_heuristics_add_no_exec_on(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_add_no_exec(
            mock_get_corosync, mock_push_corosync, "on", True
        )

    def test_success_heuristics_add_no_exec_sync(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_add_no_exec(
            mock_get_corosync, mock_push_corosync, "sync", True
        )

    def test_success_heuristics_add_no_exec_off(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_add_no_exec(
            mock_get_corosync, mock_push_corosync, "off", False
        )

    def test_success_heuristics_update_no_exec_on(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_update_no_exec(
            mock_get_corosync, mock_push_corosync, "on", True
        )

    def test_success_heuristics_update_no_exec_sync(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_update_no_exec(
            mock_get_corosync, mock_push_corosync, "sync", True
        )

    def test_success_heuristics_update_no_exec_off(
        self, mock_get_corosync, mock_push_corosync
    ):
        self.assert_success_heuristics_update_no_exec(
            mock_get_corosync, mock_push_corosync, "off", False
        )

    def test_success_heuristics_update_no_exec_present(
        self, mock_get_corosync, mock_push_corosync
    ):
        original_conf = _read_file_rc("corosync-3nodes-qdevice-heuristics.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(
            lib_env, {}, {}, {"exec_ls": "", "exec_ping": "ping example.com"}
        )

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "exec_ls: /usr/bin/test -f /tmp/test",
                "exec_ping: ping example.com",
            ),
        )
        assert_report_item_list_equal(self.mock_reporter.report_item_list, [])

    def test_success_heuristics_update_no_exec_kept(
        self, mock_get_corosync, mock_push_corosync
    ):
        original_conf = _read_file_rc("corosync-3nodes-qdevice-heuristics.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(lib_env, {}, {}, {"mode": "sync"})

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "mode: on",
                "mode: sync",
            ),
        )
        assert_report_item_list_equal(self.mock_reporter.report_item_list, [])

    def test_invalid_options(self, mock_get_corosync, mock_push_corosync):
        original_conf = _read_file_rc("corosync-3nodes-qdevice.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.update_device(
                lib_env,
                {},
                {
                    "bad_option": "bad_value",
                },
                {"mode": "bad mode", "exec_bad.name": ""},
            )
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    reports.ReportItemSeverity.ERROR,
                    reports.codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                    reports.codes.FORCE,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["exec_bad.name"],
                    option_type="heuristics",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
            ],
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)

    def test_invalid_options_forced(
        self, mock_get_corosync, mock_push_corosync
    ):
        original_conf = _read_file_rc("corosync-3nodes-qdevice.conf")
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(
            lib_env,
            {},
            {
                "bad_option": "bad_value",
            },
            {"mode": "bad mode"},
            force_options=True,
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    reports.ReportItemSeverity.WARNING,
                    reports.codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                ),
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )
        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                outdent(
                    """\

                        net {
                            host: 127.0.0.1
                        }
                """
                ),
                outdent(
                    """\
                        bad_option: bad_value

                        net {
                            host: 127.0.0.1
                        }

                        heuristics {
                            mode: bad mode
                        }
                """
                ),
            ),
        )


@mock.patch("pcs.lib.commands.quorum.corosync_live.set_expected_votes")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class SetExpectedVotesLiveTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_success(self, mock_set_votes):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        lib.set_expected_votes_live(lib_env, "5")
        mock_set_votes.assert_called_once_with("mock_runner", 5)

    def test_invalid_votes(self, mock_set_votes):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        assert_raise_library_error(
            lambda: lib.set_expected_votes_live(lib_env, "-5"),
            (
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="expected votes",
                    option_value="-5",
                    allowed_values="positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ),
        )
        mock_set_votes.assert_not_called()
