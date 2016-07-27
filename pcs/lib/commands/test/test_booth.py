from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import base64

from unittest import TestCase

from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)

from pcs import settings
from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.node import NodeAddresses
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.commands import booth as commands
from pcs.lib.external import (
    NodeCommunicator,
    CommandRunner,
    EnableServiceError,
    DisableServiceError,
    StartServiceError,
    StopServiceError
)

def patch_commands(target, *args, **kwargs):
    return mock.patch(
        "pcs.lib.commands.booth.{0}".format(target), *args, **kwargs
    )

class ConfigSetupTest(TestCase):
    @mock.patch("pcs.lib.booth.configuration.generate_key")
    @mock.patch("pcs.lib.booth.configuration.build")
    @mock.patch("pcs.lib.booth.configuration.validate_participants")
    def test_successfuly_build_and_write_to_std_path(
        self, mock_validate_participants, mock_build, mock_generate_key
    ):
        mock_build.return_value = "config content"
        mock_generate_key.return_value = "key value"
        env = mock.MagicMock()
        commands.config_setup(
            env,
            booth_configuration={
                "sites": ["1.1.1.1"],
                "arbitrators": ["2.2.2.2"],
            },
        )
        env.booth.create_config.assert_called_once_with(
            "config content",
            False
        )
        env.booth.create_key.assert_called_once_with(
            "key value",
            False
        )
        mock_validate_participants.assert_called_once_with(
            ["1.1.1.1"], ["2.2.2.2"]
        )

class ConfigDestroyTest(TestCase):
    @patch_commands("get_config_file_name", return_value="/path/to/config")
    @patch_commands("external.is_systemctl", return_value=True)
    @patch_commands("external.is_service_enabled", return_value=True)
    @patch_commands("external.is_service_running", return_value=True)
    @patch_commands("resource.find_for_config", return_value=[True])
    def test_raises_when_booth_config_in_use(
        self, mock_find, mock_running, mock_enabled, mock_is_systemctl,
        mock_config_file_name
    ):
        assert_raise_library_error(
            lambda: commands.config_destroy(mock.MagicMock()),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "config_file_path": "/path/to/config",
                    "detail": "in cib",
                }
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "config_file_path": "/path/to/config",
                    "detail": "(enabled in systemd)",
                }
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "config_file_path": "/path/to/config",
                    "detail": "(running in systemd)",
                }
            )
        )


@mock.patch("pcs.lib.booth.configuration.parse")
@mock.patch("pcs.lib.booth.configuration.read_authfile")
@mock.patch("pcs.lib.booth.sync.send_config_to_all_nodes")
class ConfigSyncTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock()
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env.report_processor = self.mock_rep
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_env.node_communicator.return_value = self.mock_com
        self.node_list = ["node1", "node2", "node3"]
        corosync_conf = mock.MagicMock()
        corosync_conf.get_nodes.return_value = self.node_list
        self.mock_env.get_corosync_conf.return_value = corosync_conf
        self.mock_env.booth.get_config_content.return_value = "config"

    def test_skip_offline(self, mock_sync, mock_read_key, mock_parse):
        mock_parse.return_value = {"authfile": "/key/path.key"}
        mock_read_key.return_value = "key"
        commands.config_sync(self.mock_env, "name", True)
        self.mock_env.booth.get_config_content.assert_called_once_with()
        mock_read_key.assert_called_once_with(self.mock_rep, "/key/path.key")
        mock_parse.assert_called_once_with("config")
        mock_sync.assert_called_once_with(
            self.mock_com,
            self.mock_rep,
            self.node_list,
            "name",
            "config",
            authfile="/key/path.key",
            authfile_data="key",
            skip_offline=True
        )

    def test_do_not_skip_offline(self, mock_sync, mock_read_key, mock_parse):
        mock_parse.return_value = {"authfile": "/key/path.key"}
        mock_read_key.return_value = "key"
        commands.config_sync(self.mock_env, "name")
        self.mock_env.booth.get_config_content.assert_called_once_with()
        mock_read_key.assert_called_once_with(self.mock_rep, "/key/path.key")
        mock_parse.assert_called_once_with("config")
        mock_sync.assert_called_once_with(
            self.mock_com,
            self.mock_rep,
            self.node_list,
            "name",
            "config",
            authfile="/key/path.key",
            authfile_data="key",
            skip_offline=False
        )


class GetBoothInstanceNameTest(TestCase):
    def test_no_name(self):
        self.assertEqual("booth", commands._get_booth_instance_name())

    def test_name(self):
        self.assertEqual(
            "booth@name", commands._get_booth_instance_name("name")
        )


@mock.patch("pcs.lib.commands.booth.external.is_systemctl")
class EnsureIsSystemctlTest(TestCase):
    def test_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        commands._ensure_is_systemd()

    def test_not_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = False
        assert_raise_library_error(
            commands._ensure_is_systemd,
            (
                Severities.ERROR,
                report_codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS,
                {}
            )
        )


@mock.patch("pcs.lib.commands.booth._ensure_is_systemd")
@mock.patch("pcs.lib.external.enable_service")
class EnableBoothTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_enable, mock_is_systemctl):
        commands.enable_booth(self.mock_env, "name")
        mock_enable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_ENABLE_SUCCESS,
                {
                    "service": "booth@name",
                    "node": None,
                }
            )]
        )

    def test_failed(self, mock_enable, mock_is_systemctl):
        mock_enable.side_effect = EnableServiceError("booth@name", "msg")
        assert_raise_library_error(
            lambda: commands.enable_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_ENABLE_ERROR,
                {
                    "service": "booth@name",
                    "reason": "msg",
                    "node": None
                }
            )
        )
        mock_enable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth._ensure_is_systemd")
@mock.patch("pcs.lib.external.disable_service")
class DisableBoothTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_disable, mock_is_systemctl):
        commands.disable_booth(self.mock_env, "name")
        mock_disable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_DISABLE_SUCCESS,
                {
                    "service": "booth@name",
                    "node": None,
                }
            )]
        )

    def test_failed(self, mock_disable, mock_is_systemctl):
        mock_disable.side_effect = DisableServiceError("booth@name", "msg")
        assert_raise_library_error(
            lambda: commands.disable_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_DISABLE_ERROR,
                {
                    "service": "booth@name",
                    "reason": "msg",
                    "node": None
                }
            )
        )
        mock_disable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth._ensure_is_systemd")
@mock.patch("pcs.lib.external.start_service")
class StartBoothTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_start, mock_is_systemctl):
        commands.start_booth(self.mock_env, "name")
        mock_start.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_START_SUCCESS,
                {
                    "service": "booth@name",
                    "node": None,
                }
            )]
        )

    def test_failed(self, mock_start, mock_is_systemctl):
        mock_start.side_effect = StartServiceError("booth@name", "msg")
        assert_raise_library_error(
            lambda: commands.start_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_START_ERROR,
                {
                    "service": "booth@name",
                    "reason": "msg",
                    "node": None
                }
            )
        )
        mock_start.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth._ensure_is_systemd")
@mock.patch("pcs.lib.external.stop_service")
class StopBoothTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_stop, mock_is_systemctl):
        commands.stop_booth(self.mock_env, "name")
        mock_stop.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_STOP_SUCCESS,
                {
                    "service": "booth@name",
                    "node": None,
                }
            )]
        )

    def test_failed(self, mock_stop, mock_is_systemctl):
        mock_stop.side_effect = StopServiceError("booth@name", "msg")
        assert_raise_library_error(
            lambda: commands.stop_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_STOP_ERROR,
                {
                    "service": "booth@name",
                    "reason": "msg",
                    "node": None
                }
            )
        )
        mock_stop.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.booth.sync.pull_config_from_node")
class PullConfigTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_env.node_communicator.return_value = self.mock_com
        self.mock_env.report_processor = self.mock_rep

    def test_with_authfile(self, mock_pull):
        mock_pull.return_value = {
            "config": {
                "name": "name.conf",
                "data": "config"
            },
            "authfile": {
                "name": "name.key",
                "data": base64.b64encode("key".encode("utf-8")).decode("utf-8")
            }
        }
        commands.pull_config(self.mock_env, "node", "name")
        mock_pull.assert_called_once_with(
            self.mock_com, NodeAddresses("node"), "name"
        )
        self.mock_env.booth.create_config.called_once_with("config", True)
        self.mock_env.booth.set_key_path.called_once_with(os.path.join(
            settings.booth_config_dir, "name.key"
        ))
        self.mock_env.booth.create_key.called_once_with(
            "key".encode("utf-8"), True
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                    {
                        "node": "node",
                        "config": "name"
                    }
                ),
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                    {
                        "node": "node",
                        "name": "name",
                        "name_list": ["name"]
                    }
                )
            ]
        )

    def test_without_authfile(self, mock_pull):
        mock_pull.return_value = {
            "config": {
                "name": "name.conf",
                "data": "config"
            },
            "authfile": {
                "name": None,
                "data": None
            }
        }
        commands.pull_config(self.mock_env, "node", "name")
        mock_pull.assert_called_once_with(
            self.mock_com, NodeAddresses("node"), "name"
        )
        self.mock_env.booth.create_config.called_once_with("config", True)
        self.assertEqual(0, self.mock_env.booth.set_key_path.call_count)
        self.assertEqual(0, self.mock_env.booth.create_key.call_count)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                    {
                        "node": "node",
                        "config": "name"
                    }
                ),
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                    {
                        "node": "node",
                        "name": "name",
                        "name_list": ["name"]
                    }
                )
            ]
        )

    def test_invalid_input(self, mock_pull):
        mock_pull.return_value = {}
        assert_raise_library_error(
            lambda: commands.pull_config(self.mock_env, "node", "name"),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": "node"}
            )
        )
        mock_pull.assert_called_once_with(
            self.mock_com, NodeAddresses("node"), "name"
        )
        self.assertEqual(0, self.mock_env.booth.create_config.call_count)
        self.assertEqual(0, self.mock_env.booth.set_key_path.call_count)
        self.assertEqual(0, self.mock_env.booth.create_key.call_count)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                {
                    "node": "node",
                    "config": "name"
                }
            )]
        )

class TicketOperationTest(TestCase):
    @mock.patch("pcs.lib.booth.resource.find_binded_single_ip")
    def test_raises_when_implicit_site_not_found_in_cib(
        self, mock_find_binded_ip
    ):
        mock_find_binded_ip.return_value = None
        assert_raise_library_error(
            lambda: commands.ticket_operation(
                "grant", mock.Mock(), "booth", "ABC", site_ip=None
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CORRECT_CONFIG_NOT_FOUND_IN_CIB,
                {
                    "operation": "grant",
                }
            ),
        )

    def test_raises_when_command_fail(self):
        mock_run = mock.Mock(return_value=("some message", 1))
        mock_env = mock.MagicMock(
            cmd_runner=mock.Mock(return_value=mock.MagicMock(run=mock_run))
        )
        assert_raise_library_error(
            lambda: commands.ticket_operation(
                "grant", mock_env, "booth", "ABC", site_ip="1.2.3.4"
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_TICKET_OPERATION_FAILED,
                {
                    "operation": "grant",
                    "reason": "some message",
                    "site_ip": "1.2.3.4",
                    "ticket": "ABC",
                }
            ),
        )
