from __future__ import (
    absolute_import,
    division,
    print_function,
)

import base64
import logging

from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    ac,
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
)
from pcs.test.tools.pcs_unittest import mock, skip, TestCase

from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.corosync.config_facade import ConfigFacade
from pcs.lib.external import NodeCommunicationException
from pcs.lib.node import NodeAddresses, NodeAddressesList

from pcs.lib.commands import quorum as lib


class CmanMixin(object):
    def assert_disabled_on_cman(self, func):
        assert_raise_library_error(
            func,
            (
                severity.ERROR,
                report_codes.CMAN_UNSUPPORTED_COMMAND,
                {}
            )
        )


@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
class GetQuorumConfigTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(self, mock_get_corosync):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(lambda: lib.get_config(lib_env))
        mock_get_corosync.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_enabled_on_cman_if_not_live(self, mock_get_corosync):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )

        self.assertEqual(
            {
                "options": {},
                "device": None,
            },
            lib.get_config(lib_env)
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_no_options(self, mock_get_corosync):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        self.assertEqual(
            {
                "options": {},
                "device": None,
            },
            lib.get_config(lib_env)
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
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
            lib.get_config(lib_env)
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
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
                },
            },
            lib.get_config(lib_env)
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
        report_item = (
            severity.ERROR,
            report_codes.COROSYNC_QUORUM_CANNOT_DISABLE_ATB_DUE_TO_SBD,
            {},
            report_codes.FORCE_OPTIONS
        )
        assert_raise_library_error(
            lambda: lib._check_if_atb_can_be_disabled(
                self.mock_runner,
                self.mock_reporter,
                self.mock_corosync_conf,
                True
            ),
            report_item
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


    def test_atb_no_need_was_disabled_atb_disabled_force(
        self, mock_atb_needed
    ):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf,
            False, force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_disabled_atb_enabled_force(
        self, mock_atb_needed
    ):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf,
            False, force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enable_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True,
            force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_no_need_was_enabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = False
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True,
            force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_disabled_force(
        self, mock_atb_needed
    ):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf,
            False, force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_disabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf,
            False, force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    def test_atb_needed_was_enable_atb_disabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = False
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True,
            force=True
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                severity.WARNING,
                report_codes.COROSYNC_QUORUM_CANNOT_DISABLE_ATB_DUE_TO_SBD,
                {},
                None
            )]
        )

    def test_atb_needed_was_enabled_atb_enabled_force(self, mock_atb_needed):
        mock_atb_needed.return_value = True
        self.mock_corosync_conf.is_enabled_auto_tie_breaker.return_value = True
        lib._check_if_atb_can_be_disabled(
            self.mock_runner, self.mock_reporter, self.mock_corosync_conf, True,
            force=True
        )
        self.assertEqual([], self.mock_reporter.report_item_list)


@mock.patch("pcs.lib.commands.quorum._check_if_atb_can_be_disabled")
@mock.patch.object(LibraryEnvironment, "push_corosync_conf")
@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
@mock.patch.object(LibraryEnvironment, "cmd_runner")
class SetQuorumOptionsTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(
        self, mock_runner, mock_get_corosync, mock_push_corosync, mock_check
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(lambda: lib.set_options(lib_env, {}))
        mock_get_corosync.assert_not_called()
        mock_push_corosync.assert_not_called()
        mock_check.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_enabled_on_cman_if_not_live(
        self, mock_runner, mock_get_corosync, mock_push_corosync, mock_check
    ):
        original_conf = "invalid {\nconfig: stop after cman test"
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )
        options = {"wait_for_all": "1"}
        assert_raise_library_error(
            lambda: lib.set_options(lib_env, options),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {}
            )
        )

        mock_push_corosync.assert_not_called()
        mock_check.assert_not_called()
        mock_runner.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(
        self, mock_runner, mock_get_corosync, mock_push_corosync, mock_check
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        mock_runner.return_value = "cmd_runner"
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        new_options = {"wait_for_all": "1"}
        lib.set_options(lib_env, new_options)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "provider: corosync_votequorum\n",
                "provider: corosync_votequorum\n    wait_for_all: 1\n"
            )
        )
        self.assertEqual([], self.mock_reporter.report_item_list)
        self.assertEqual(1, mock_check.call_count)
        self.assertEqual("cmd_runner", mock_check.call_args[0][0])
        self.assertEqual(self.mock_reporter, mock_check.call_args[0][1])
        self.assertFalse(mock_check.call_args[0][3])
        self.assertFalse(mock_check.call_args[0][4])

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_bad_options(
        self, mock_runner, mock_get_corosync, mock_push_corosync, mock_check
    ):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        new_options = {"invalid": "option"}
        assert_raise_library_error(
            lambda: lib.set_options(lib_env, new_options),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["invalid"],
                    "option_type": "quorum",
                    "allowed": [
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all",
                    ],
                }
            )
        )

        mock_push_corosync.assert_not_called()
        mock_check.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_bad_config(
        self, mock_runner, mock_get_corosync, mock_push_corosync, mock_check
    ):
        original_conf = "invalid {\nconfig: this is"
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        new_options = {"wait_for_all": "1"}
        assert_raise_library_error(
            lambda: lib.set_options(lib_env, new_options),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {}
            )
        )

        mock_push_corosync.assert_not_called()
        mock_check.assert_not_called()


@mock.patch("pcs.lib.commands.quorum.corosync_live.get_quorum_status_text")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class StatusTextTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(self, mock_status):
        self.assert_disabled_on_cman(
            lambda: lib.status_text(self.lib_env)
        )
        mock_status.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(
            lib.status_text(self.lib_env),
            "status text"
        )
        mock_status.assert_called_once_with("mock_runner")


@mock.patch("pcs.lib.commands.quorum.qdevice_client.get_status_text")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class StatusDeviceTextTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(self, mock_status):
        self.assert_disabled_on_cman(
            lambda: lib.status_device_text(self.lib_env)
        )
        mock_status.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(
            lib.status_device_text(self.lib_env),
            "status text"
        )
        mock_status.assert_called_once_with("mock_runner", False)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success_verbose(self, mock_status):
        mock_status.return_value = "status text"
        self.assertEqual(
            lib.status_device_text(self.lib_env, True),
            "status text"
        )
        mock_status.assert_called_once_with("mock_runner", True)


class AddDeviceNetTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

        self.qnetd_host = "qnetd-host"
        self.corosync_conf_name = "corosync-3nodes.conf"
        # the cluster name is defined in the corosync-3nodes.conf file
        self.cluster_name = "test99"
        # nodes are defined in the corosync-3nodes.conf file
        self.cluster_nodes = ["rh7-1", "rh7-2", "rh7-3"]
        self.certs = {
            "cacert": {
                "path": rc("qdevice-certs/qnetd-cacert.crt"),
            },
            "cert_request": {
                "path": rc("qdevice-certs/qdevice-cert-request.crq"),
            },
            "signed_request": {
                "path": rc("qdevice-certs/signed-certificate.crt"),
            },
            "final_cert": {
                "path": rc("qdevice-certs/final-certificate.pk12"),
            },
        }
        for cert_info in self.certs.values():
            # b64encode accepts bytes in python3, so we must read the file as
            # binary to get bytes instead of a string. In python2, it doesn't
            # matter.
            plain = open(cert_info["path"], "rb").read()
            cert_info["data"] = plain
            # Convert bytes to string in python3, because the communicator does
            # it the same way - it accepts bytes, converts them to string and
            # passes that to further processing.
            cert_info["b64data"] = base64.b64encode(plain).decode("utf-8")

    def fixture_config_http_get_ca_cert(self):
        self.config.http.add_communication(
            "http.get_ca_certificate",
            [
                {"label": self.qnetd_host, },
            ],
            action="remote/qdevice_net_get_ca_certificate",
            response_code=200,
            output=self.certs["cacert"]["b64data"]
        )

    def fixture_config_http_client_init(self):
        self.config.http.add_communication(
            "http.client_init",
            [{"label": node} for node in self.cluster_nodes],
            action="remote/qdevice_net_client_init_certificate_storage",
            param_list=[
                ("ca_certificate", self.certs["cacert"]["b64data"]),
            ],
            response_code=200,
        )

    def fixture_config_runner_get_cert_request(self):
        self.config.runner.place(
            "corosync-qdevice-net-certutil -r -n {cluster_name}".format(
                cluster_name=self.cluster_name
            ),
            name="runner.corosync.qdevice.cert-request",
            stdout="Certificate request stored in {path}".format(
                path=self.certs["cert_request"]["path"]
            )
        )

    def fixture_config_http_sign_cert_request(self):
        self.config.http.add_communication(
            "http.sign_certificate_request",
            [
                {"label": self.qnetd_host, },
            ],
            action="remote/qdevice_net_sign_node_certificate",
            param_list=[
                (
                    "certificate_request",
                    self.certs["cert_request"]["b64data"]
                ),
                ("cluster_name", self.cluster_name),
            ],
            response_code=200,
            output=self.certs["signed_request"]["b64data"]
        )

    def fixture_config_runner_cert_to_pk12(self, cert_file_path):
        self.config.runner.place(
            "corosync-qdevice-net-certutil -M -c {file_path}".format(
                file_path=cert_file_path
            ),
            name="runner.corosync.qdevice.cert-to-pk12",
            stdout="Certificate request stored in {path}".format(
                path=self.certs["final_cert"]["path"]
            )
        )

    def fixture_config_http_import_final_cert(self):
        self.config.http.add_communication(
            "http.client_import_certificate",
            [{"label": node} for node in self.cluster_nodes],
            action="remote/qdevice_net_client_import_certificate",
            param_list=[
                ("certificate", self.certs["final_cert"]["b64data"]),
            ],
            response_code=200,
        )

    def fixture_config_http_qdevice_enable(self):
        self.config.http.add_communication(
            "http.qdevice_enable",
            [{"label": node} for node in self.cluster_nodes],
            action="remote/qdevice_client_enable",
            response_code=200,
            output="corosync-qdevice enabled"
        )

    def fixture_config_http_qdevice_start(self):
        self.config.http.add_communication(
            "http.qdevice_start",
            [{"label": node} for node in self.cluster_nodes],
            action="remote/qdevice_client_start",
            response_code=200,
            output="corosync-qdevice started"
        )

    def test_disabled_on_cman(self):
        self.config.runner.corosync.version(version="1.4.7")
        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host"},
                {}
            ),
            [
                fixture.error(report_codes.CMAN_UNSUPPORTED_COMMAND),
            ],
            expected_in_processor=False
        )

    def test_does_not_check_cman_if_not_live(self):
        (self.config
            .env.set_corosync_conf_data(open(rc("corosync-3nodes.conf")).read())
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "bad model",
                {},
                {}
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_QDEVICE_MODEL,
                    option_name="model",
                    option_value="bad model",
                    allowed_values=("net", )
                ),
            ]
        )

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    @mock.patch("pcs.lib.corosync.qdevice_net.write_tmpfile")
    def test_success(self, mock_write_tmpfile):
        tmpfile_instance = mock.MagicMock()
        tmpfile_instance.name = rc("file.tmp")
        mock_write_tmpfile.return_value = tmpfile_instance

        expected_corosync_conf = open(
                rc(self.corosync_conf_name)
            ).read().replace(
            "    provider: corosync_votequorum\n",
            outdent("""\
                    provider: corosync_votequorum

                    device {
                        timeout: 20
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            )
        )

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.fixture_config_runner_get_cert_request()
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_runner_cert_to_pk12(tmpfile_instance.name)
        self.fixture_config_http_import_final_cert()
        self.fixture_config_http_qdevice_enable()
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.fixture_config_http_qdevice_start()

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {"timeout": "20"}
        )

        mock_write_tmpfile.assert_called_once_with(
            self.certs["signed_request"]["data"],
            binary=True
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
        ] + [
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=node
            )
            for node in self.cluster_nodes
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ] + [
            fixture.info(
                report_codes.SERVICE_START_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ])

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    @mock.patch("pcs.lib.corosync.qdevice_net.write_tmpfile")
    def test_success_one_node_offline(self, mock_write_tmpfile):
        node_2_offline_msg = (
            "Failed connect to {0}:2224; No route to host".format(
                self.cluster_nodes[1]
            )
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
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=self.cluster_nodes[1],
                reason=node_2_offline_msg,
                command=command
            )

        tmpfile_instance = mock.MagicMock()
        tmpfile_instance.name = rc("file.tmp")
        mock_write_tmpfile.return_value = tmpfile_instance

        expected_corosync_conf = open(
                rc(self.corosync_conf_name)
            ).read().replace(
            "    provider: corosync_votequorum\n",
            outdent("""\
                    provider: corosync_votequorum

                    device {
                        timeout: 20
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            )
        )

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.config.http.add_communication(
            "http.client_init",
            node_2_offline_responses,
            action="remote/qdevice_net_client_init_certificate_storage",
            param_list=[
                ("ca_certificate", self.certs["cacert"]["b64data"]),
            ],
            response_code=200,
        )
        self.fixture_config_runner_get_cert_request()
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_runner_cert_to_pk12(tmpfile_instance.name)
        self.config.http.add_communication(
            "http.client_import_certificate",
            node_2_offline_responses,
            action="remote/qdevice_net_client_import_certificate",
            param_list=[
                ("certificate", self.certs["final_cert"]["b64data"]),
            ],
            response_code=200,
        )
        self.config.http.add_communication(
            "http.qdevice_enable",
            node_2_offline_responses,
            action="remote/qdevice_client_enable",
            response_code=200,
            output="corosync-qdevice enabled"
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.config.http.add_communication(
            "http.qdevice_start",
            node_2_offline_responses,
            action="remote/qdevice_client_start",
            response_code=200,
            output="corosync-qdevice started"
        )

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {"timeout": "20"},
            skip_offline_nodes=True
        )

        mock_write_tmpfile.assert_called_once_with(
            self.certs["signed_request"]["data"],
            binary=True
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
            node_2_offline_warning(
                "remote/qdevice_net_client_init_certificate_storage"
            ),
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=self.cluster_nodes[0]
            ),
            node_2_offline_warning(
                "remote/qdevice_net_client_import_certificate"
            ),
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=self.cluster_nodes[2]
            ),
            fixture.info(
                report_codes.SERVICE_ENABLE_STARTED,
                service="corosync-qdevice"
            ),
            fixture.info(
                report_codes.SERVICE_ENABLE_SUCCESS,
                node=self.cluster_nodes[0],
                service="corosync-qdevice"
            ),
            node_2_offline_warning("remote/qdevice_client_enable"),
            fixture.info(
                report_codes.SERVICE_ENABLE_SUCCESS,
                node=self.cluster_nodes[2],
                service="corosync-qdevice"
            ),
            fixture.info(
                report_codes.SERVICE_START_STARTED,
                service="corosync-qdevice"
            ),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node=self.cluster_nodes[0],
                service="corosync-qdevice"
            ),
            node_2_offline_warning("remote/qdevice_client_start"),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node=self.cluster_nodes[2],
                service="corosync-qdevice"
            ),
        ])

    def test_success_file(self):
        expected_corosync_conf = open(
                rc(self.corosync_conf_name)
            ).read().replace(
            "    provider: corosync_votequorum\n",
            outdent("""\
                    provider: corosync_votequorum

                    device {
                        timeout: 20
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            )
        )

        (self.config
            .env.set_corosync_conf_data(
                open(rc(self.corosync_conf_name)).read()
            )
            .env.push_corosync_conf(
                corosync_conf_text=expected_corosync_conf
            )
        )

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": "qnetd-host", "algorithm": "ffsplit"},
            {"timeout": "20"}
        )

    def test_invalid_options(self):
        (self.config
            .runner.corosync.version()
            .corosync_conf.load(filename=self.corosync_conf_name)
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"bad_option": "bad_value"}
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_names=["bad_option"],
                    option_type="quorum device",
                    allowed=["sync_timeout", "timeout"]
                ),
            ]
        )

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    @mock.patch("pcs.lib.corosync.qdevice_net.write_tmpfile")
    def test_invalid_options_forced(self, mock_write_tmpfile):
        tmpfile_instance = mock.MagicMock()
        tmpfile_instance.name = rc("file.tmp")
        mock_write_tmpfile.return_value = tmpfile_instance

        expected_corosync_conf = open(
                rc(self.corosync_conf_name)
            ).read().replace(
            "    provider: corosync_votequorum\n",
            outdent("""\
                    provider: corosync_votequorum

                    device {
                        bad_option: bad_value
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: qnetd-host
                        }
                    }
                """
            )
        )

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.fixture_config_runner_get_cert_request()
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_runner_cert_to_pk12(tmpfile_instance.name)
        self.fixture_config_http_import_final_cert()
        self.fixture_config_http_qdevice_enable()
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.fixture_config_http_qdevice_start()

        lib.add_device(
            self.env_assist.get_env(),
            "net",
            {"host": self.qnetd_host, "algorithm": "ffsplit"},
            {"bad_option": "bad_value", },
            force_options=True
        )

        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.INVALID_OPTION,
                option_names=["bad_option"],
                option_type="quorum device",
                allowed=["sync_timeout", "timeout"],
            ),
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
        ] + [
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=node
            )
            for node in self.cluster_nodes
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ] + [
            fixture.info(
                report_codes.SERVICE_START_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ])

    def test_invalid_model(self):
        (self.config
            .runner.corosync.version()
            .corosync_conf.load(filename=self.corosync_conf_name)
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "bad_model",
                {},
                {}
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_QDEVICE_MODEL,
                    option_name="model",
                    option_value="bad_model",
                    allowed_values=("net", ),
                ),
            ]
        )

    def test_invalid_model_forced(self):
        expected_corosync_conf = open(
                rc(self.corosync_conf_name)
            ).read().replace(
            "    provider: corosync_votequorum\n",
            outdent("""\
                    provider: corosync_votequorum

                    device {
                        model: bad_model
                    }
                """
            )
        )

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        # model is not "net" - do not set up certificates
        self.fixture_config_http_qdevice_enable()
        self.config.env.push_corosync_conf(
            corosync_conf_text=expected_corosync_conf
        )
        self.fixture_config_http_qdevice_start()

        lib.add_device(
            self.env_assist.get_env(),
            "bad_model",
            {},
            {},
            force_model=True
        )

        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.INVALID_OPTION_VALUE,
                option_name="model",
                option_value="bad_model",
                allowed_values=("net", ),
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_ENABLE_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ] + [
            fixture.info(
                report_codes.SERVICE_START_STARTED,
                service="corosync-qdevice"
            ),
        ] + [
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node=node,
                service="corosync-qdevice"
            )
            for node in self.cluster_nodes
        ])

    def test_error_get_ca_cert(self):
        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.add_communication(
            "http.get_ca_certificate",
            [
                {"label": self.qnetd_host, },
            ],
            action="remote/qdevice_net_get_ca_certificate",
            response_code=400,
            output="Unable to read certificate: error description"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"},
                skip_offline_nodes=True # test that this does not matter
            ),
            [], # an empty LibraryError is raised
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=None,
                node=self.qnetd_host,
                command="remote/qdevice_net_get_ca_certificate",
                reason="Unable to read certificate: error description",
            )
        ])

    def test_error_client_setup(self):
        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.config.http.add_communication(
            "http.client_init",
            [
                {"label": self.cluster_nodes[0]},
                {
                    "label": self.cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": self.cluster_nodes[2]},
            ],
            action="remote/qdevice_net_client_init_certificate_storage",
            param_list=[
                ("ca_certificate", self.certs["cacert"]["b64data"]),
            ],
            response_code=200,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"}
            ),
            [], # an empty LibraryError is raised
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node=self.cluster_nodes[1],
                command="remote/qdevice_net_client_init_certificate_storage",
                reason="some error occurred",
            )
        ])

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_generate_cert_request_error(self):
        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.config.runner.place(
            "corosync-qdevice-net-certutil -r -n {cluster_name}".format(
                cluster_name=self.cluster_name
            ),
            name="runner.corosync.qdevice.cert-request",
            stderr="some error occurred",
            returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"}
            ),
            [
                fixture.error(
                    report_codes.QDEVICE_INITIALIZATION_ERROR,
                    force_code=None,
                    model="net",
                    reason="some error occurred",
                ),
            ],
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
        ])

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_sign_certificate_error(self):
        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.fixture_config_runner_get_cert_request()
        self.config.http.add_communication(
            "http.sign_certificate_request",
            [
                {"label": self.qnetd_host, },
            ],
            action="remote/qdevice_net_sign_node_certificate",
            param_list=[
                (
                    "certificate_request",
                    self.certs["cert_request"]["b64data"]
                ),
                ("cluster_name", self.cluster_name),
            ],
            response_code=400,
            output="some error occurred"
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"}
            ),
            [], # an empty LibraryError is raised
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=None,
                node=self.qnetd_host,
                command="remote/qdevice_net_sign_node_certificate",
                reason="some error occurred",
            )
        ])

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    @mock.patch("pcs.lib.corosync.qdevice_net.write_tmpfile")
    def test_certificate_to_pk12_error(self, mock_write_tmpfile):
        tmpfile_instance = mock.MagicMock()
        tmpfile_instance.name = rc("file.tmp")
        mock_write_tmpfile.return_value = tmpfile_instance

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.fixture_config_runner_get_cert_request()
        self.fixture_config_http_sign_cert_request()
        self.config.runner.place(
            "corosync-qdevice-net-certutil -M -c {file_path}".format(
                file_path=tmpfile_instance.name
            ),
            name="runner.corosync.qdevice.cert-to-pk12",
            stderr="some error occurred",
            returncode=1
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"}
            ),
            [
                fixture.error(
                    report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    force_code=None,
                    reason="some error occurred",
                ),
            ],
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
        ])

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    @mock.patch("pcs.lib.corosync.qdevice_net.write_tmpfile")
    def test_client_import_cert_error(self, mock_write_tmpfile):
        tmpfile_instance = mock.MagicMock()
        tmpfile_instance.name = rc("file.tmp")
        mock_write_tmpfile.return_value = tmpfile_instance

        self.config.runner.corosync.version()
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.fixture_config_http_get_ca_cert()
        self.fixture_config_http_client_init()
        self.fixture_config_runner_get_cert_request()
        self.fixture_config_http_sign_cert_request()
        self.fixture_config_runner_cert_to_pk12(tmpfile_instance.name)
        self.config.http.add_communication(
            "http.client_import_certificate",
            [
                {"label": self.cluster_nodes[0]},
                {
                    "label": self.cluster_nodes[1],
                    "response_code": 400,
                    "output": "some error occurred",
                },
                {"label": self.cluster_nodes[2]},
            ],
            action="remote/qdevice_net_client_import_certificate",
            param_list=[
                ("certificate", self.certs["final_cert"]["b64data"]),
            ],
            response_code=200,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.add_device(
                self.env_assist.get_env(),
                "net",
                {"host": "qnetd-host", "algorithm": "ffsplit"},
                {"timeout": "20"}
            ),
            [], # an empty LibraryError is raised
            expected_in_processor=False
        )

        self.env_assist.assert_reports([
            fixture.info(report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=self.cluster_nodes[0],
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node=self.cluster_nodes[1],
                command="remote/qdevice_net_client_import_certificate",
                reason="some error occurred",
            ),
            fixture.info(
                report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                node=self.cluster_nodes[2],
            ),
        ])


@skip("TODO: rewrite using new testing fremework")
@mock.patch.object(LibraryEnvironment, "push_corosync_conf")
@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
@mock.patch("pcs.lib.commands.quorum._remove_device_model_net")
@mock.patch("pcs.lib.commands.quorum.qdevice_client.remote_client_disable")
@mock.patch("pcs.lib.commands.quorum.qdevice_client.remote_client_stop")
class RemoveDeviceTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(lambda: lib.remove_device(lib_env))
        mock_get_corosync.assert_not_called()
        mock_push_corosync.assert_not_called()
        mock_remove_net.assert_not_called()
        mock_remote_disable.assert_not_called()
        mock_remote_stop.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_enabled_on_cman_if_not_live(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )

        assert_raise_library_error(
            lambda: lib.remove_device(lib_env),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)
        mock_remove_net.assert_not_called()
        mock_remote_disable.assert_not_called()
        mock_remote_stop.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_no_device(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.remove_device(lib_env),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)
        mock_remove_net.assert_not_called()
        mock_remote_disable.assert_not_called()
        mock_remote_stop.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.sbd.is_sbd_installed", lambda self: True)
    @mock.patch("pcs.lib.sbd.is_sbd_enabled", lambda self: True)
    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_3nodes_sbd(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        # nothing special needs to be done in regards of SBD if a cluster
        # consists of odd number of nodes
        original_conf = open(rc("corosync-3nodes-qdevice.conf")).read()
        no_device_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.remove_device(lib_env)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            no_device_conf
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, len(mock_remove_net.mock_calls))
        self.assertEqual(3, len(mock_remote_disable.mock_calls))
        self.assertEqual(3, len(mock_remote_stop.mock_calls))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.sbd.is_sbd_installed", lambda self: False)
    @mock.patch("pcs.lib.sbd.is_sbd_enabled", lambda self: False)
    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_2nodes_no_sbd(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        # cluster consists of two nodes, two_node must be set
        original_conf = open(rc("corosync-qdevice.conf")).read()
        no_device_conf = open(rc("corosync.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.remove_device(lib_env)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            no_device_conf
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, len(mock_remove_net.mock_calls))
        self.assertEqual(2, len(mock_remote_disable.mock_calls))
        self.assertEqual(2, len(mock_remote_stop.mock_calls))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.sbd.is_sbd_installed", lambda self: True)
    @mock.patch("pcs.lib.sbd.is_sbd_enabled", lambda self: True)
    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: [])
    def test_success_2nodes_sbd(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        # cluster consists of two nodes, but SBD is in use
        # auto tie breaker must be enabled
        original_conf = open(rc("corosync-qdevice.conf")).read()
        no_device_conf = open(rc("corosync.conf")).read().replace(
            "two_node: 1",
            "auto_tie_breaker: 1"
        )
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.remove_device(lib_env)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            no_device_conf
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.SBD_REQUIRES_ATB,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, len(mock_remove_net.mock_calls))
        self.assertEqual(2, len(mock_remote_disable.mock_calls))
        self.assertEqual(2, len(mock_remote_stop.mock_calls))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.sbd.is_sbd_installed", lambda self: True)
    @mock.patch("pcs.lib.sbd.is_sbd_enabled", lambda self: True)
    @mock.patch("pcs.lib.sbd.get_local_sbd_device_list", lambda: ["/dev"])
    def test_success_2nodes_sbd_with_device(
        self, mock_remote_stop, mock_remote_disable, mock_remove_net,
        mock_get_corosync, mock_push_corosync
    ):
        # cluster consists of two nodes, but SBD with shared storage is in use
        # auto tie breaker doesn't need to be enabled
        original_conf = open(rc("corosync-qdevice.conf")).read()
        no_device_conf = open(rc("corosync.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.remove_device(lib_env)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            no_device_conf
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, len(mock_remove_net.mock_calls))
        self.assertEqual(2, len(mock_remote_disable.mock_calls))
        self.assertEqual(2, len(mock_remote_stop.mock_calls))

    @mock.patch("pcs.lib.sbd.atb_has_to_be_enabled")
    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success_file(
        self, mock_atb_check, mock_remote_stop, mock_remote_disable,
        mock_remove_net, mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes-qdevice.conf")).read()
        no_device_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )

        lib.remove_device(lib_env)

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            no_device_conf
        )
        self.assertEqual([], self.mock_reporter.report_item_list)
        mock_remove_net.assert_not_called()
        mock_remote_disable.assert_not_called()
        mock_remote_stop.assert_not_called()
        mock_atb_check.assert_not_called()


@skip("TODO: rewrite using new testing fremework")
@mock.patch("pcs.lib.commands.quorum.qdevice_net.remote_client_destroy")
@mock.patch.object(
    LibraryEnvironment,
    "node_communicator",
    lambda self: "mock_communicator"
)
class RemoveDeviceNetTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.nodes = NodeAddressesList([
            NodeAddresses("node1"),
            NodeAddresses("node2"),
        ])

    def test_success(self, mock_client_destroy):
        skip_offline_nodes = False

        lib._remove_device_model_net(
            self.lib_env,
            self.nodes,
            skip_offline_nodes
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    {
                        "node": self.nodes[0].label
                    }
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    {
                        "node": self.nodes[1].label
                    }
                ),
            ]
        )
        client_destroy_calls = [
            mock.call("mock_communicator", self.nodes[0]),
            mock.call("mock_communicator", self.nodes[1]),
        ]
        self.assertEqual(
            len(client_destroy_calls),
            len(mock_client_destroy.mock_calls)
        )
        mock_client_destroy.assert_has_calls(
            client_destroy_calls,
            any_order=True
        )

    def test_error_client_destroy(self, mock_client_destroy):
        def raiser(communicator, node):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_client_destroy.side_effect = raiser
        skip_offline_nodes = False

        assert_raise_library_error(
            lambda: lib._remove_device_model_net(
                self.lib_env,
                self.nodes,
                skip_offline_nodes
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {},
                report_codes.SKIP_OFFLINE_NODES
            )
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    {
                        "node": self.nodes[0].label
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.NODE_COMMUNICATION_ERROR,
                    {},
                    report_codes.SKIP_OFFLINE_NODES
                ),
            ]
        )
        client_destroy_calls = [
            mock.call("mock_communicator", self.nodes[0]),
            mock.call("mock_communicator", self.nodes[1]),
        ]
        self.assertEqual(
            len(client_destroy_calls),
            len(mock_client_destroy.mock_calls)
        )
        mock_client_destroy.assert_has_calls(
            client_destroy_calls,
            any_order=True
        )

    def test_error_client_destroy_skip_offline(self, mock_client_destroy):
        def raiser(communicator, node):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_client_destroy.side_effect = raiser
        skip_offline_nodes = True

        lib._remove_device_model_net(
            self.lib_env,
            self.nodes,
            skip_offline_nodes
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
                    {
                        "node": self.nodes[0].label
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR,
                    {}
                ),
            ]
        )
        client_destroy_calls = [
            mock.call("mock_communicator", self.nodes[0]),
            mock.call("mock_communicator", self.nodes[1]),
        ]
        self.assertEqual(
            len(client_destroy_calls),
            len(mock_client_destroy.mock_calls)
        )
        mock_client_destroy.assert_has_calls(
            client_destroy_calls,
            any_order=True
        )


@mock.patch.object(LibraryEnvironment, "push_corosync_conf")
@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
class UpdateDeviceTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(self, mock_get_corosync, mock_push_corosync):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(
            lambda: lib.update_device(lib_env, {"host": "127.0.0.1"}, {})
        )
        mock_get_corosync.assert_not_called()
        mock_push_corosync.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_enabled_on_cman_if_not_live(
        self, mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )

        assert_raise_library_error(
            lambda: lib.update_device(lib_env, {"host": "127.0.0.1"}, {}),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_no_device(self, mock_get_corosync, mock_push_corosync):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.update_device(lib_env, {"host": "127.0.0.1"}, {}),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )

        mock_push_corosync.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(self, mock_get_corosync, mock_push_corosync):
        original_conf = open(rc("corosync-3nodes-qdevice.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(
            lib_env,
            {"host": "127.0.0.2"},
            {"timeout": "12345"}
        )

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf
                .replace("host: 127.0.0.1", "host: 127.0.0.2")
                .replace(
                    "model: net",
                    "model: net\n        timeout: 12345"
                )
        )
        self.assertEqual([], self.mock_reporter.report_item_list)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_options(self, mock_get_corosync, mock_push_corosync):
        original_conf = open(rc("corosync-3nodes-qdevice.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.update_device(
                lib_env,
                {},
                {"bad_option": "bad_value", }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["bad_option"],
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                },
                report_codes.FORCE_OPTIONS
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_options_forced(self, mock_get_corosync, mock_push_corosync):
        original_conf = open(rc("corosync-3nodes-qdevice.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.update_device(
            lib_env,
            {},
            {"bad_option": "bad_value", },
            force_options=True
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["bad_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                    }
                )
            ]
        )
        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "model: net",
                "model: net\n        bad_option: bad_value"
            )
        )


@mock.patch("pcs.lib.commands.quorum.corosync_live.set_expected_votes")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class SetExpectedVotesLiveTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(self, mock_set_votes):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(
            lambda: lib.set_expected_votes_live(lib_env, "5")
        )
        mock_set_votes.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(self, mock_set_votes):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        lib.set_expected_votes_live(lib_env, "5")
        mock_set_votes.assert_called_once_with("mock_runner", 5)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_votes(self, mock_set_votes):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        assert_raise_library_error(
            lambda: lib.set_expected_votes_live(lib_env, "-5"),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "expected votes",
                    "option_value": "-5",
                    "allowed_values": "positive integer",
                }
            )
        )
        mock_set_votes.assert_not_called()
