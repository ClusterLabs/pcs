from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import base64

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.misc import create_patcher

from pcs import settings
from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.node import NodeAddresses
from pcs.lib.errors import LibraryError, ReportItemSeverity as Severities
from pcs.lib.commands import booth as commands
from pcs.lib.external import (
    NodeCommunicator,
    CommandRunner,
    EnableServiceError,
    DisableServiceError,
    StartServiceError,
    StopServiceError
)

patch_commands = create_patcher("pcs.lib.commands.booth")

@mock.patch("pcs.lib.booth.config_files.generate_key", return_value="key value")
@mock.patch("pcs.lib.commands.booth.build", return_value="config content")
@mock.patch("pcs.lib.booth.config_structure.validate_peers")
class ConfigSetupTest(TestCase):
    def test_successfuly_build_and_write_to_std_path(
        self, mock_validate_peers, mock_build, mock_generate_key
    ):
        env = mock.MagicMock()
        commands.config_setup(
            env,
            booth_configuration=[
                {"key": "site", "value": "1.1.1.1", "details": []},
                {"key": "arbitrator", "value": "2.2.2.2", "details": []},
            ],
        )
        env.booth.create_config.assert_called_once_with(
            "config content",
            False
        )
        env.booth.create_key.assert_called_once_with(
            "key value",
            False
        )
        mock_validate_peers.assert_called_once_with(
            ["1.1.1.1"], ["2.2.2.2"]
        )

    def test_sanitize_peers_before_validation(
        self, mock_validate_peers, mock_build, mock_generate_key
    ):
        commands.config_setup(env=mock.MagicMock(), booth_configuration={})
        mock_validate_peers.assert_called_once_with([], [])


class ConfigDestroyTest(TestCase):
    @patch_commands("external.is_systemctl", mock.Mock(return_value=True))
    @patch_commands("external.is_service_enabled", mock.Mock(return_value=True))
    @patch_commands("external.is_service_running", mock.Mock(return_value=True))
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[True]))
    def test_raises_when_booth_config_in_use(self):
        env = mock.MagicMock()
        env.booth.name = "somename"

        assert_raise_library_error(
            lambda: commands.config_destroy(env),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "name": "somename",
                    "detail": "in cluster resource",
                }
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "name": "somename",
                    "detail": "(enabled in systemd)",
                }
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_IS_USED,
                {
                    "name": "somename",
                    "detail": "(running in systemd)",
                }
            )
        )

    @patch_commands("external.is_systemctl", mock.Mock(return_value=False))
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[]))
    @patch_commands("parse", mock.Mock(side_effect=LibraryError()))
    def test_raises_when_cannot_get_content_of_config(self):
        env = mock.MagicMock()
        assert_raise_library_error(
            lambda: commands.config_destroy(env),
            (
                Severities.ERROR,
                report_codes.BOOTH_CANNOT_IDENTIFY_KEYFILE,
                {},
                report_codes.FORCE_BOOTH_DESTROY
            )
        )

    @patch_commands("external.is_systemctl", mock.Mock(return_value=False))
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[]))
    @patch_commands("parse", mock.Mock(side_effect=LibraryError()))
    def test_remove_config_even_if_cannot_get_its_content_when_forced(self):
        env = mock.MagicMock()
        env.report_processor = MockLibraryReportProcessor()
        commands.config_destroy(env, ignore_config_load_problems=True)
        env.booth.remove_config.assert_called_once_with()
        assert_report_item_list_equal(env.report_processor.report_item_list, [
            (
                Severities.WARNING,
                report_codes.BOOTH_CANNOT_IDENTIFY_KEYFILE,
                {}
            )
        ])

@mock.patch("pcs.lib.commands.booth.config_structure.get_authfile")
@mock.patch("pcs.lib.commands.booth.parse")
@mock.patch("pcs.lib.booth.config_files.read_authfile")
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

    def test_skip_offline(
        self, mock_sync, mock_read_key, mock_parse, mock_get_authfile
    ):
        mock_get_authfile.return_value = "/key/path.key"
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

    def test_do_not_skip_offline(
        self, mock_sync, mock_read_key, mock_parse, mock_get_authfile
    ):
        mock_get_authfile.return_value = "/key/path.key"
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


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
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
                    "service": "booth",
                    "node": None,
                    "instance": "name",
                }
            )]
        )

    def test_failed(self, mock_enable, mock_is_systemctl):
        mock_enable.side_effect = EnableServiceError("booth", "msg", "name")
        assert_raise_library_error(
            lambda: commands.enable_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_ENABLE_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": "name",
                }
            )
        )
        mock_enable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
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
                    "service": "booth",
                    "node": None,
                    "instance": "name",
                }
            )]
        )

    def test_failed(self, mock_disable, mock_is_systemctl):
        mock_disable.side_effect = DisableServiceError("booth", "msg", "name")
        assert_raise_library_error(
            lambda: commands.disable_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_DISABLE_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": "name",
                }
            )
        )
        mock_disable.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
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
                    "service": "booth",
                    "node": None,
                    "instance": "name",
                }
            )]
        )

    def test_failed(self, mock_start, mock_is_systemctl):
        mock_start.side_effect = StartServiceError("booth", "msg", "name")
        assert_raise_library_error(
            lambda: commands.start_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_START_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": "name",
                }
            )
        )
        mock_start.assert_called_once_with(self.mock_run, "booth", "name")
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
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
                    "service": "booth",
                    "node": None,
                    "instance": "name",
                }
            )]
        )

    def test_failed(self, mock_stop, mock_is_systemctl):
        mock_stop.side_effect = StopServiceError("booth", "msg", "name")
        assert_raise_library_error(
            lambda: commands.stop_booth(self.mock_env, "name"),
            (
                Severities.ERROR,
                report_codes.SERVICE_STOP_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": "name",
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
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    {
                        "node": None,
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
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    {
                        "node": None,
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
    @mock.patch("pcs.lib.booth.resource.find_bound_ip")
    def test_raises_when_implicit_site_not_found_in_cib(
        self, mock_find_bound_ip
    ):
        mock_find_bound_ip.return_value = []
        assert_raise_library_error(
            lambda: commands.ticket_operation(
                "grant", mock.Mock(), "booth", "ABC", site_ip=None
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP,
                {}
            ),
        )

    def test_raises_when_command_fail(self):
        mock_run = mock.Mock(return_value=("some message", "error", 1))
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
                    "reason": "error\nsome message",
                    "site_ip": "1.2.3.4",
                    "ticket_name": "ABC",
                }
            ),
        )

class CreateInClusterTest(TestCase):
    @patch_commands("get_resources", mock.MagicMock())
    def test_raises_when_is_created_already(self):
        assert_raise_library_error(
            lambda: commands.create_in_cluster(
                mock.MagicMock(), "somename", ip="1.2.3.4",
                resource_create=None, resource_remove=None,
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_ALREADY_IN_CIB,
                {
                    "name": "somename",
                }
            ),
        )

class FindResourceElementsForOperationTest(TestCase):
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[]))
    def test_raises_when_no_booth_resource_found(self):
        assert_raise_library_error(
            lambda: commands._find_resource_elements_for_operation(
                mock.MagicMock(),
                "somename",
                allow_multiple=False
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_NOT_EXISTS_IN_CIB,
                {
                    'name': 'somename',
                }
            ),
        )

    @patch_commands(
        "resource.find_for_config", mock.Mock(return_value=["b_el1", "b_el2"])
    )
    def test_raises_when_multiple_booth_resource_found(self):
        assert_raise_library_error(
            lambda: commands._find_resource_elements_for_operation(
                mock.MagicMock(),
                "somename",
                allow_multiple=False
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
                {
                    'name': 'somename',
                },
                report_codes.FORCE_BOOTH_REMOVE_FROM_CIB,
            ),
        )

    @patch_commands("get_resources", mock.Mock(return_value="resources"))
    @patch_commands("resource.get_remover", mock.MagicMock())
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[1, 2]))
    def test_warn_when_multiple_booth_resources_removed(self):
        report_processor=MockLibraryReportProcessor()
        commands._find_resource_elements_for_operation(
            mock.MagicMock(report_processor=report_processor),
            "somename",
            allow_multiple=True,
        )
        assert_report_item_list_equal(report_processor.report_item_list, [(
            Severities.WARNING,
            report_codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
            {
                'name': 'somename',
            },
        )])
