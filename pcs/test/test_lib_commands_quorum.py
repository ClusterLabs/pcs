from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
from unittest import TestCase

from pcs.test.tools.pcs_mock import mock
from pcs.test.library_test_tools import LibraryAssertionMixin
from pcs.test.tools.resources import get_test_resource as rc

from pcs.lib.external import NodeAuthenticationException
from pcs.lib.env import LibraryEnvironment
from pcs.lib import error_codes
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade

from pcs.lib.commands import quorum as lib


@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock cmd runner"
)
@mock.patch.object(
    LibraryEnvironment,
    "node_communicator",
    lambda self: "mock node communicator"
)
class SetQuorumOptionsTest(TestCase, LibraryAssertionMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)

    def assert_set_remote_corosync_conf_call(self, a_call, node_ring0, config):
        self.assertEqual("set_remote_corosync_conf", a_call[0])
        self.assertEqual(3, len(a_call[1]))
        self.assertEqual("mock node communicator", a_call[1][0])
        self.assertEqual(node_ring0, a_call[1][1].ring0)
        self.assertEqual(config, a_call[1][2])
        self.assertEqual(0, len(a_call[2]))

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    @mock.patch("pcs.lib.commands.quorum.corosync_live.reload_config")
    @mock.patch("pcs.lib.commands.quorum.corosync_live.set_remote_corosync_conf")
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_disabled_on_cman(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        lib_env = LibraryEnvironment(self.mock_logger)
        self.assert_raise_library_error(
            lambda: lib.set_options(lib_env, {}),
            (
                severity.ERROR,
                error_codes.CMAN_UNSUPPORTED_COMMAND,
                {}
            )
        )
        mock_get_local.assert_not_called()
        mock_set_remote.assert_not_called()
        mock_reload.assert_not_called()

    def base_test_not_live_success(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        original_conf = open(rc("corosync.conf")).read()
        lib_env = LibraryEnvironment(
            self.mock_logger,
            corosync_conf_data=original_conf
        )

        self.assertEqual(
            {},
            CorosyncConfigFacade
                .from_string(lib_env.get_corosync_conf())
                .get_quorum_options()
        )
        options = {"wait_for_all": "1"}

        lib.set_options(lib_env, options)

        self.assertEqual(
            options,
            CorosyncConfigFacade
                .from_string(lib_env.get_corosync_conf())
                .get_quorum_options()
        )
        mock_get_local.assert_not_called()
        mock_set_remote.assert_not_called()
        mock_reload.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.commands.quorum.corosync_live.reload_config")
    @mock.patch("pcs.lib.commands.quorum.corosync_live.set_remote_corosync_conf")
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_not_live_success(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        self.base_test_not_live_success(
            mock_get_local, mock_set_remote, mock_reload
        )

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
    @mock.patch("pcs.lib.commands.quorum.corosync_live.reload_config")
    @mock.patch("pcs.lib.commands.quorum.corosync_live.set_remote_corosync_conf")
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_not_live_cman_success(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        self.base_test_not_live_success(
            mock_get_local, mock_set_remote, mock_reload
        )

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    @mock.patch("pcs.lib.commands.quorum.corosync_live")
    def test_live_success(self, mock_corosync_live, mock_get_local):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_local.return_value = original_conf
        mock_corosync_live.set_remote_corosync_conf = mock.MagicMock()
        mock_corosync_live.reload_config = mock.MagicMock()
        lib_env = LibraryEnvironment(self.mock_logger)

        conf_facade = CorosyncConfigFacade.from_string(original_conf)
        self.assertEqual(
            {},
            conf_facade.get_quorum_options()
        )
        nodes = conf_facade.get_nodes()
        self.assertEqual(2, len(nodes))

        new_options = {"wait_for_all": "1"}
        lib.set_options(lib_env, new_options)

        conf_facade.set_quorum_options(new_options)
        new_conf = conf_facade.config.export()
        corosync_live_calls = [
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[0], new_conf
            ),
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[1], new_conf
            ),
            mock.call.reload_config("mock cmd runner"),
        ]
        self.assertEqual(
            len(corosync_live_calls),
            len(mock_corosync_live.mock_calls)
        )
        self.assert_set_remote_corosync_conf_call(
            mock_corosync_live.mock_calls[0], "rh7-1", new_conf
        )
        self.assert_set_remote_corosync_conf_call(
            mock_corosync_live.mock_calls[1], "rh7-2", new_conf
        )
        self.assertEqual(
            corosync_live_calls[2],
            mock_corosync_live.mock_calls[2]
        )

        logger_calls = [
            mock.call("Sending updated corosync.conf to nodes..."),
            mock.call("rh7-1: Succeeded"),
            mock.call("rh7-2: Succeeded"),
            mock.call("Corosync configuration reloaded"),
        ]
        self.assertEqual(self.mock_logger.info.call_count, len(logger_calls))
        self.mock_logger.info.assert_has_calls(logger_calls)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    @mock.patch("pcs.lib.commands.quorum.corosync_live")
    def test_live_one_node_down(self, mock_corosync_live, mock_get_local):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_local.return_value = original_conf
        mock_corosync_live.set_remote_corosync_conf = mock.MagicMock()
        def raiser(comm, node, conf):
            if node.ring0 == "rh7-2":
                raise NodeAuthenticationException("rh7-2", "command", "401")
        mock_corosync_live.set_remote_corosync_conf.side_effect = raiser
        mock_corosync_live.reload_config = mock.MagicMock()
        lib_env = LibraryEnvironment(self.mock_logger)

        conf_facade = CorosyncConfigFacade.from_string(original_conf)
        self.assertEqual(
            {},
            conf_facade.get_quorum_options()
        )
        nodes = conf_facade.get_nodes()
        self.assertEqual(2, len(nodes))

        new_options = {"wait_for_all": "1"}
        self.assert_raise_library_error(
            lambda: lib.set_options(lib_env, new_options),
            (
                severity.ERROR,
                error_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                {
                    "node": "rh7-2",
                    "command": "command",
                    "reason" : "HTTP error: 401",
                }
            ),
            (
                severity.ERROR,
                error_codes.NODE_COROSYNC_CONF_SAVE_ERROR,
                {
                    "node": "rh7-2",
                }
            )
        )

        conf_facade.set_quorum_options(new_options)
        new_conf = conf_facade.config.export()
        corosync_live_calls = [
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[0], new_conf
            ),
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[1], new_conf
            ),
        ]
        self.assertEqual(
            len(corosync_live_calls),
            len(mock_corosync_live.mock_calls)
        )
        self.assert_set_remote_corosync_conf_call(
            mock_corosync_live.mock_calls[0], "rh7-1", new_conf
        )
        self.assert_set_remote_corosync_conf_call(
            mock_corosync_live.mock_calls[1], "rh7-2", new_conf
        )
        mock_corosync_live.reload_config.assert_not_called()

        logger_calls = [
            mock.call("Sending updated corosync.conf to nodes..."),
            mock.call("rh7-1: Succeeded"),
        ]
        self.assertEqual(self.mock_logger.info.call_count, len(logger_calls))
        self.mock_logger.info.assert_has_calls(logger_calls)

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.commands.quorum.corosync_live.reload_config")
    @mock.patch("pcs.lib.commands.quorum.corosync_live.set_remote_corosync_conf")
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_live_bad_options(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        original_conf = open(rc("corosync.conf")).read()
        mock_get_local.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger)

        new_options = {"invalid": "option"}
        self.assert_raise_library_error(
            lambda: lib.set_options(lib_env, new_options),
            (
                severity.ERROR,
                error_codes.INVALID_OPTION,
                {
                    "type": "quorum",
                    "option": "invalid",
                    "allowed_raw": (
                        "auto_tie_breaker",
                        "last_man_standing",
                        "last_man_standing_window",
                        "wait_for_all",
                    ),
                }
            )
        )

        mock_get_local.assert_called_once_with()
        mock_set_remote.assert_not_called()
        mock_reload.assert_not_called()

    @mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
    @mock.patch("pcs.lib.commands.quorum.corosync_live.reload_config")
    @mock.patch("pcs.lib.commands.quorum.corosync_live.set_remote_corosync_conf")
    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_live_bad_config(
        self, mock_get_local, mock_set_remote, mock_reload
    ):
        original_conf = "invalid {\nconfig: this is"
        mock_get_local.return_value = original_conf
        lib_env = LibraryEnvironment(self.mock_logger)

        new_options = {"wait_for_all": "1"}
        self.assert_raise_library_error(
            lambda: lib.set_options(lib_env, new_options),
            (
                severity.ERROR,
                error_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {
                }
            )
        )

        mock_get_local.assert_called_once_with()
        mock_set_remote.assert_not_called()
        mock_reload.assert_not_called()
