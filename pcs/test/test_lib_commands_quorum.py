from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
)
from pcs.test.tools.pcs_unittest import mock

from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as severity,
)
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
                    "option_name": "invalid",
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


@mock.patch.object(LibraryEnvironment, "push_corosync_conf")
@mock.patch.object(LibraryEnvironment, "get_corosync_conf_data")
@mock.patch("pcs.lib.commands.quorum._add_device_model_net")
@mock.patch("pcs.lib.commands.quorum.qdevice_client.remote_client_enable")
@mock.patch("pcs.lib.commands.quorum.qdevice_client.remote_client_start")
class AddDeviceTest(TestCase, CmanMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_disabled_on_cman(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assert_disabled_on_cman(
            lambda: lib.add_device(lib_env, "net", {"host": "127.0.0.1"}, {})
        )
        mock_get_corosync.assert_not_called()
        mock_push_corosync.assert_not_called()
        mock_add_net.assert_not_called()
        mock_client_enable.assert_not_called()
        mock_client_start.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    def test_enabled_on_cman_if_not_live(
        self, mock_client_start, mock_client_enable, mock_add_net,
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
            lambda: lib.add_device(lib_env, "bad model", {}, {}),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "bad model",
                    "allowed_values": ("net", ),
                },
                report_codes.FORCE_QDEVICE_MODEL
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)
        mock_add_net.assert_not_called()
        mock_client_enable.assert_not_called()
        mock_client_start.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.add_device(
            lib_env,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {"timeout": "12345"}
        )

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "provider: corosync_votequorum\n",
                """provider: corosync_votequorum

    device {
        timeout: 12345
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }
"""
            )
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, len(mock_add_net.mock_calls))
        self.assertEqual(3, len(mock_client_enable.mock_calls))
        self.assertEqual(3, len(mock_client_start.mock_calls))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_success_file(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            corosync_conf_data=original_conf
        )

        lib.add_device(
            lib_env,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {"timeout": "12345"}
        )

        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "provider: corosync_votequorum\n",
                """provider: corosync_votequorum

    device {
        timeout: 12345
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }
"""
            )
        )
        self.assertEqual([], self.mock_reporter.report_item_list)
        mock_add_net.assert_not_called()
        mock_client_enable.assert_not_called()
        mock_client_start.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_options(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.add_device(
                lib_env,
                "net",
                {"host": "127.0.0.1", "algorithm": "ffsplit"},
                {"bad_option": "bad_value", }
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_name": "bad_option",
                    "option_type": "quorum device",
                    "allowed": ["sync_timeout", "timeout"],
                },
                report_codes.FORCE_OPTIONS
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)
        mock_add_net.assert_not_called()
        mock_client_enable.assert_not_called()
        mock_client_start.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_options_forced(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.add_device(
            lib_env,
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
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
                        "option_name": "bad_option",
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "provider: corosync_votequorum\n",
                """provider: corosync_votequorum

    device {
        bad_option: bad_value
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }
"""
            )
        )
        self.assertEqual(1, len(mock_add_net.mock_calls))
        self.assertEqual(3, len(mock_client_enable.mock_calls))
        self.assertEqual(3, len(mock_client_start.mock_calls))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_model(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        assert_raise_library_error(
            lambda: lib.add_device(lib_env, "bad model", {}, {}),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "bad model",
                    "allowed_values": ("net", ),
                },
                report_codes.FORCE_QDEVICE_MODEL
            )
        )

        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(0, mock_push_corosync.call_count)
        mock_add_net.assert_not_called()
        mock_client_enable.assert_not_called()
        mock_client_start.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    def test_invalid_model_forced(
        self, mock_client_start, mock_client_enable, mock_add_net,
        mock_get_corosync, mock_push_corosync
    ):
        original_conf = open(rc("corosync-3nodes.conf")).read()
        mock_get_corosync.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)

        lib.add_device(lib_env, "bad model", {}, {}, force_model=True)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "bad model",
                        "allowed_values": ("net", ),
                    },
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "corosync-qdevice",
                    }
                ),
            ]
        )
        self.assertEqual(1, mock_get_corosync.call_count)
        self.assertEqual(1, len(mock_push_corosync.mock_calls))
        ac(
            mock_push_corosync.mock_calls[0][1][0].config.export(),
            original_conf.replace(
                "provider: corosync_votequorum\n",
                """provider: corosync_votequorum

    device {
        model: bad model
    }
"""
            )
        )
        mock_add_net.assert_not_called() # invalid model - don't setup net model
        self.assertEqual(3, len(mock_client_enable.mock_calls))
        self.assertEqual(3, len(mock_client_start.mock_calls))


@mock.patch(
    "pcs.lib.commands.quorum.qdevice_net.remote_client_import_certificate_and_key"
)
@mock.patch("pcs.lib.commands.quorum.qdevice_net.client_cert_request_to_pk12")
@mock.patch(
    "pcs.lib.commands.quorum.qdevice_net.remote_sign_certificate_request"
)
@mock.patch(
    "pcs.lib.commands.quorum.qdevice_net.client_generate_certificate_request"
)
@mock.patch("pcs.lib.commands.quorum.qdevice_net.remote_client_setup")
@mock.patch(
    "pcs.lib.commands.quorum.qdevice_net.remote_qdevice_get_ca_certificate"
)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
@mock.patch.object(
    LibraryEnvironment,
    "node_communicator",
    lambda self: "mock_communicator"
)
class AddDeviceNetTest(TestCase):
    #pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.qnetd_host = "qnetd_host"
        self.cluster_name = "clusterName"
        self.nodes = NodeAddressesList([
            NodeAddresses("node1"),
            NodeAddresses("node2"),
        ])
        self.ca_cert = "CA certificate"
        self.cert_request = "client certificate request"
        self.signed_cert = "signed certificate"
        self.final_cert = "final client certificate"

    def test_success(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = False

        lib._add_device_model_net(
            self.lib_env,
            self.qnetd_host,
            self.cluster_name,
            self.nodes,
            skip_offline_nodes
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    {
                        "node": self.nodes[0].label
                    }
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    {
                        "node": self.nodes[1].label
                    }
                ),
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host,
            self.cert_request,
            self.cluster_name
        )
        mock_cert_to_pk12.assert_called_once_with(
            "mock_runner",
            self.signed_cert
        )
        client_import_calls = [
            mock.call("mock_communicator", self.nodes[0], self.final_cert),
            mock.call("mock_communicator", self.nodes[1], self.final_cert),
        ]
        self.assertEqual(
            len(client_import_calls),
            len(mock_import_cert.mock_calls)
        )
        mock_import_cert.assert_has_calls(client_import_calls, any_order=True)

    def test_error_get_ca_cert(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.side_effect = NodeCommunicationException(
            "host", "command", "reason"
        )
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = False

        assert_raise_library_error(
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
                self.nodes,
                skip_offline_nodes
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {}
            )
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                )
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        mock_client_setup.assert_not_called()
        mock_get_cert_request.assert_not_called()
        mock_sign_cert_request.assert_not_called()
        mock_cert_to_pk12.assert_not_called()
        mock_import_cert.assert_not_called()


    def test_error_client_setup(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        def raiser(communicator, node, cert):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_client_setup.side_effect = raiser
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = False

        assert_raise_library_error(
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
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
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.ERROR,
                    report_codes.NODE_COMMUNICATION_ERROR,
                    {},
                    report_codes.SKIP_OFFLINE_NODES
                ),
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)

    def test_error_client_setup_skip_offline(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        def raiser(communicator, node, cert):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_client_setup.side_effect = raiser
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = True

        lib._add_device_model_net(
            self.lib_env,
            self.qnetd_host,
            self.cluster_name,
            self.nodes,
            skip_offline_nodes
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    {
                        "node": self.nodes[0].label
                    }
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    {
                        "node": self.nodes[1].label
                    }
                ),
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)

    def test_generate_cert_request_error(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.side_effect = LibraryError()
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = False

        self.assertRaises(
            LibraryError,
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
                self.nodes,
                skip_offline_nodes
            )
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                )
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_not_called()
        mock_cert_to_pk12.assert_not_called()
        mock_import_cert.assert_not_called()

    def test_sign_certificate_error(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.side_effect = NodeCommunicationException(
            "host", "command", "reason"
        )
        mock_cert_to_pk12.return_value = self.final_cert
        skip_offline_nodes = False

        assert_raise_library_error(
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
                self.nodes,
                skip_offline_nodes
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {}
            )
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                )
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host,
            self.cert_request,
            self.cluster_name
        )
        mock_cert_to_pk12.assert_not_called()
        mock_import_cert.assert_not_called()

    def test_certificate_to_pk12_error(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.side_effect = LibraryError()
        skip_offline_nodes = False

        self.assertRaises(
            LibraryError,
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
                self.nodes,
                skip_offline_nodes
            )
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                )
            ]
        )
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host,
            self.cert_request,
            self.cluster_name
        )
        mock_cert_to_pk12.assert_called_once_with(
            "mock_runner",
            self.signed_cert
        )
        mock_import_cert.assert_not_called()

    def test_client_import_cert_error(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        def raiser(communicator, node, cert):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_import_cert.side_effect = raiser
        skip_offline_nodes = False

        assert_raise_library_error(
            lambda: lib._add_device_model_net(
                self.lib_env,
                self.qnetd_host,
                self.cluster_name,
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
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
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
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host,
            self.cert_request,
            self.cluster_name
        )
        mock_cert_to_pk12.assert_called_once_with(
            "mock_runner",
            self.signed_cert
        )
        client_import_calls = [
            mock.call("mock_communicator", self.nodes[0], self.final_cert),
            mock.call("mock_communicator", self.nodes[1], self.final_cert),
        ]
        self.assertEqual(
            len(client_import_calls),
            len(mock_import_cert.mock_calls)
        )
        mock_import_cert.assert_has_calls(client_import_calls, any_order=True)

    def test_client_import_cert_error_skip_offline(
        self, mock_get_ca, mock_client_setup, mock_get_cert_request,
        mock_sign_cert_request, mock_cert_to_pk12, mock_import_cert
    ):
        mock_get_ca.return_value = self.ca_cert
        mock_get_cert_request.return_value = self.cert_request
        mock_sign_cert_request.return_value = self.signed_cert
        mock_cert_to_pk12.return_value = self.final_cert
        def raiser(communicator, node, cert):
            if node == self.nodes[1]:
                raise NodeCommunicationException("host", "command", "reason")
        mock_import_cert.side_effect = raiser
        skip_offline_nodes = True

        lib._add_device_model_net(
            self.lib_env,
            self.qnetd_host,
            self.cluster_name,
            self.nodes,
            skip_offline_nodes
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
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
        mock_get_ca.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host
        )
        client_setup_calls = [
            mock.call("mock_communicator", self.nodes[0], self.ca_cert),
            mock.call("mock_communicator", self.nodes[1], self.ca_cert),
        ]
        self.assertEqual(
            len(client_setup_calls),
            len(mock_client_setup.mock_calls)
        )
        mock_client_setup.assert_has_calls(client_setup_calls, any_order=True)
        mock_get_cert_request.assert_called_once_with(
            "mock_runner",
            self.cluster_name
        )
        mock_sign_cert_request.assert_called_once_with(
            "mock_communicator",
            self.qnetd_host,
            self.cert_request,
            self.cluster_name
        )
        mock_cert_to_pk12.assert_called_once_with(
            "mock_runner",
            self.signed_cert
        )
        client_import_calls = [
            mock.call("mock_communicator", self.nodes[0], self.final_cert),
            mock.call("mock_communicator", self.nodes[1], self.final_cert),
        ]
        self.assertEqual(
            len(client_import_calls),
            len(mock_import_cert.mock_calls)
        )
        mock_import_cert.assert_has_calls(client_import_calls, any_order=True)


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
                    "option_name": "bad_option",
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
                        "option_name": "bad_option",
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
