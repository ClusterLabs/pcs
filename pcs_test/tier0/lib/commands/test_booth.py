from collections import namedtuple
import os
from unittest import mock, TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.misc import create_patcher

from pcs import settings
from pcs.common import report_codes, env_file_role_codes as file_roles
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError, ReportItemSeverity as Severities
from pcs.lib.commands import booth as commands
from pcs.lib.external import (
    CommandRunner,
    EnableServiceError,
    DisableServiceError,
    StartServiceError,
    StopServiceError
)

# pylint: disable=no-self-use, unused-argument, protected-access

def _booth_env_fixture(name):
    booth_env = mock.MagicMock()
    booth_env.name = name
    return booth_env


def _env_fixture(booth_name):
    env = mock.MagicMock(spec_set=LibraryEnvironment)
    env.booth = _booth_env_fixture(booth_name)
    return env

patch_commands = create_patcher("pcs.lib.commands.booth")

@mock.patch("pcs.lib.tools.generate_binary_key", return_value=b"key value")
@mock.patch("pcs.lib.commands.booth.build", return_value="config content")
@mock.patch("pcs.lib.booth.config_validators.create")
class ConfigSetupTest(TestCase):
    def test_successfuly_build_and_write_to_std_path(
        self, mock_validate_create, mock_build, mock_generate_binary_key
    ):
        env = _env_fixture("booth_name")
        commands.config_setup(
            env,
            ["1.1.1.1", "2.2.2.2"],
            ["3.3.3.3"]
        )
        env.booth.create_config.assert_called_once_with(
            "config content",
            False
        )
        env.booth.create_key.assert_called_once_with(
            b"key value",
            False
        )
        mock_validate_create.assert_called_once_with(
            ["1.1.1.1", "2.2.2.2"], ["3.3.3.3"]
        )
        mock_generate_binary_key.assert_called_once_with(random_bytes_count=64)

    def test_sanitize_peers_before_validation(
        self, mock_validate_peers, mock_build, mock_generate_binary_key
    ):
        commands.config_setup(_env_fixture("booth_name"), [], [])
        mock_validate_peers.assert_called_once_with([], [])
        mock_generate_binary_key.assert_called_once_with(random_bytes_count=64)


class ConfigDestroyTest(TestCase):
    @patch_commands("external.is_systemctl", mock.Mock(return_value=True))
    @patch_commands("external.is_service_enabled", mock.Mock(return_value=True))
    @patch_commands("external.is_service_running", mock.Mock(return_value=True))
    @patch_commands("resource.find_for_config", mock.Mock(return_value=[True]))
    def test_raises_when_booth_config_in_use(self):
        env = _env_fixture("somename")

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
        env = _env_fixture("somename")
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
        env = _env_fixture("somename")
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


class ConfigSyncTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.name = "booth"
        self.config_path = os.path.join(
            settings.booth_config_dir, "{}.conf".format(self.name)
        )
        self.node_list = ["rh7-1", "rh7-2"]
        self.config.env.set_booth({"name": self.name})
        self.config.env.set_known_nodes(self.node_list)
        self.reason = "fail"

    def test_success(self):
        auth_file = "auth.file"
        auth_file_path = os.path.join(settings.booth_config_dir, auth_file)
        config_content = "authfile={}".format(auth_file_path)
        auth_file_content = b"auth"
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data=config_content)(),
                name="open.conf"
            )
            .fs.open(
                auth_file_path,
                mock.mock_open(read_data=auth_file_content)(),
                mode="rb",
                name="open.authfile",
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, config_content,
                authfile=auth_file,
                authfile_data=auth_file_content,
                node_labels=self.node_list,
            )
        )

        commands.config_sync(self.env_assist.get_env(), self.name)
        self.env_assist.assert_reports(
            [fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)]
            +
            [
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.name]
                ) for node in self.node_list
            ]
        )

    def test_some_node_names_missing(self):
        auth_file = "auth.file"
        auth_file_path = os.path.join(settings.booth_config_dir, auth_file)
        config_content = "authfile={}".format(auth_file_path)
        auth_file_content = b"auth"
        nodes = ["rh7-2"]
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data=config_content)(),
                name="open.conf"
            )
            .fs.open(
                auth_file_path,
                mock.mock_open(read_data=auth_file_content)(),
                mode="rb",
                name="open.authfile",
            )
            .corosync_conf.load(filename="corosync-some-node-names.conf")
            .http.booth.send_config(
                self.name, config_content,
                authfile=auth_file,
                authfile_data=auth_file_content,
                node_labels=nodes,
            )
        )

        commands.config_sync(self.env_assist.get_env(), self.name)
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
            ]
            +
            [
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.name]
                ) for node in nodes
            ]
        )

    def test_all_node_names_missing(self):
        auth_file = "auth.file"
        auth_file_path = os.path.join(settings.booth_config_dir, auth_file)
        config_content = "authfile={}".format(auth_file_path)
        auth_file_content = b"auth"
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data=config_content)(),
                name="open.conf"
            )
            .fs.open(
                auth_file_path,
                mock.mock_open(read_data=auth_file_content)(),
                mode="rb",
                name="open.authfile",
            )
            .corosync_conf.load(filename="corosync-no-node-names.conf")
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env(), self.name),
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_NO_NODES_DEFINED,
                ),
            ]
        )
        self.env_assist.assert_reports([
            fixture.warn(
                report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                fatal=False,
            ),
        ])

    def test_node_failure(self):
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data="")(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, "",
                communication_list=[
                    dict(
                        label=self.node_list[0],
                        response_code=400,
                        output=self.reason,
                    ),
                    dict(
                        label=self.node_list[1],
                    )
                ]
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=[self.name]
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                ),
            ]
        )

    def test_node_failure_skip_offline(self):
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data="")(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, "",
                communication_list=[
                    dict(
                        label=self.node_list[0],
                        response_code=400,
                        output=self.reason,
                    ),
                    dict(
                        label=self.node_list[1],
                    )
                ]
            )
        )

        commands.config_sync(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=[self.name]
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                ),
            ]
        )

    def test_node_offline(self):
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data="")(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, "",
                communication_list=[
                    dict(
                        label=self.node_list[0],
                        errno=1,
                        error_msg=self.reason,
                        was_connected=False,
                    ),
                    dict(
                        label=self.node_list[1],
                    )
                ],
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env()),
            []
        )
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=[self.name]
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                ),
            ]
        )

    def test_node_offline_skip_offline(self):
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data="")(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, "",
                communication_list=[
                    dict(
                        label=self.node_list[0],
                        errno=1,
                        error_msg=self.reason,
                        was_connected=False,
                    ),
                    dict(
                        label=self.node_list[1],
                    )
                ],
            )
        )

        commands.config_sync(self.env_assist.get_env(), skip_offline_nodes=True)
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=self.node_list[1],
                    name_list=[self.name]
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=self.node_list[0],
                    reason=self.reason,
                    command="remote/booth_set_config",
                ),
            ]
        )

    def test_config_not_accessible(self):
        self.config.fs.open(
            self.config_path,
            side_effect=EnvironmentError(0, self.reason, self.config_path),
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.config_sync(self.env_assist.get_env(), self.name),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, self.config_path),
                    file_role=file_roles.BOOTH_CONFIG,
                    file_path=self.config_path,
                    operation="read",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])

    def test_authfile_not_accessible(self):
        auth_file = "auth.file"
        auth_file_path = os.path.join(settings.booth_config_dir, auth_file)
        config_content = "authfile={}".format(auth_file_path)

        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data=config_content)(),
                name="open.conf"
            )
            .fs.open(
                auth_file_path,
                mode="rb",
                name="open.authfile",
                side_effect=EnvironmentError(0, self.reason, auth_file_path),
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, config_content, node_labels=self.node_list,
            )
        )

        commands.config_sync(self.env_assist.get_env(), self.name)
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, auth_file_path),
                    file_role=file_roles.BOOTH_KEY,
                    file_path=auth_file_path,
                    operation="read",
                ),
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)
            ]
            +
            [
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.name]
                ) for node in self.node_list
            ]
        )

    def test_no_authfile(self):
        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data="")(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, "", node_labels=self.node_list,
            )
        )

        commands.config_sync(self.env_assist.get_env(), self.name)
        self.env_assist.assert_reports(
            [fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)]
            +
            [
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.name]
                ) for node in self.node_list
            ]
        )

    def test_authfile_not_in_booth_dir(self):
        config_file_content = "authfile=/etc/my_booth.conf"

        (self.config
            .fs.open(
                self.config_path,
                mock.mock_open(read_data=config_file_content)(),
                name="open.conf"
            )
            .corosync_conf.load()
            .http.booth.send_config(
                self.name, config_file_content, node_labels=self.node_list,
            )
        )

        commands.config_sync(self.env_assist.get_env(), self.name)
        self.env_assist.assert_reports(
            [
                fixture.warn(report_codes.BOOTH_UNSUPPORTED_FILE_LOCATION),
                fixture.info(report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)
            ]
            +
            [
                fixture.info(
                    report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.name]
                ) for node in self.node_list
            ]
        )


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
@mock.patch("pcs.lib.external.enable_service")
class EnableBoothTest(TestCase):
    def setUp(self):
        self.name = "booth_name"
        self.mock_env = _env_fixture(self.name)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_enable, mock_is_systemctl):
        commands.enable_booth(self.mock_env)
        mock_enable.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_ENABLE_SUCCESS,
                {
                    "service": "booth",
                    "node": None,
                    "instance": self.name,
                }
            )]
        )

    def test_failed(self, mock_enable, mock_is_systemctl):
        mock_enable.side_effect = EnableServiceError("booth", "msg", self.name)
        assert_raise_library_error(
            lambda: commands.enable_booth(self.mock_env),
            (
                Severities.ERROR,
                report_codes.SERVICE_ENABLE_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": self.name,
                }
            )
        )
        mock_enable.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
@mock.patch("pcs.lib.external.disable_service")
class DisableBoothTest(TestCase):
    def setUp(self):
        self.name = "booth_name"
        self.mock_env = _env_fixture(self.name)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_disable, mock_is_systemctl):
        commands.disable_booth(self.mock_env)
        mock_disable.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_DISABLE_SUCCESS,
                {
                    "service": "booth",
                    "node": None,
                    "instance": self.name,
                }
            )]
        )

    def test_failed(self, mock_disable, mock_is_systemctl):
        mock_disable.side_effect = DisableServiceError(
            "booth", "msg", self.name
        )
        assert_raise_library_error(
            lambda: commands.disable_booth(self.mock_env),
            (
                Severities.ERROR,
                report_codes.SERVICE_DISABLE_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": self.name,
                }
            )
        )
        mock_disable.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
@mock.patch("pcs.lib.external.start_service")
class StartBoothTest(TestCase):
    def setUp(self):
        self.name = "booth_name"
        self.mock_env = _env_fixture(self.name)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_start, mock_is_systemctl):
        commands.start_booth(self.mock_env)
        mock_start.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_START_SUCCESS,
                {
                    "service": "booth",
                    "node": None,
                    "instance": self.name,
                }
            )]
        )

    def test_failed(self, mock_start, mock_is_systemctl):
        mock_start.side_effect = StartServiceError("booth", "msg", self.name)
        assert_raise_library_error(
            lambda: commands.start_booth(self.mock_env),
            (
                Severities.ERROR,
                report_codes.SERVICE_START_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": self.name,
                }
            )
        )
        mock_start.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()


@mock.patch("pcs.lib.commands.booth.external.ensure_is_systemd")
@mock.patch("pcs.lib.external.stop_service")
class StopBoothTest(TestCase):
    def setUp(self):
        self.name = "booth_name"
        self.mock_env = _env_fixture(self.name)
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_env.report_processor = self.mock_rep

    def test_success(self, mock_stop, mock_is_systemctl):
        commands.stop_booth(self.mock_env)
        mock_stop.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_STOP_SUCCESS,
                {
                    "service": "booth",
                    "node": None,
                    "instance": self.name,
                }
            )]
        )

    def test_failed(self, mock_stop, mock_is_systemctl):
        mock_stop.side_effect = StopServiceError("booth", "msg", self.name)
        assert_raise_library_error(
            lambda: commands.stop_booth(self.mock_env),
            (
                Severities.ERROR,
                report_codes.SERVICE_STOP_ERROR,
                {
                    "service": "booth",
                    "reason": "msg",
                    "node": None,
                    "instance": self.name,
                }
            )
        )
        mock_stop.assert_called_once_with(self.mock_run, "booth", self.name)
        mock_is_systemctl.assert_called_once_with()

def _get_booth_file_path(file):
    return os.path.join(settings.booth_config_dir, file)


class PullConfigBase(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.name = "booth"
        self.node_name = "node"
        self.config_data = "config"
        self.config_path = _get_booth_file_path("{}.conf".format(self.name))
        self.report_list = [
            fixture.info(
                report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
                node=self.node_name,
                config=self.name
            ),
            fixture.info(
                report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node=None,
                name_list=[self.name],
            )
        ]
        self.config.env.set_booth({"name": self.name})


class PullConfigSuccess(PullConfigBase):
    def setUp(self):
        super(PullConfigSuccess, self).setUp()
        self.booth_cfg_open_mock = mock.mock_open()()
        (self.config
            .http.booth.get_config(
                self.name, self.config_data, node_labels=[self.node_name]
            )
            .fs.exists(self.config_path, False)
            .fs.open(self.config_path, self.booth_cfg_open_mock, mode="w")
        )
        self.addCleanup(
            lambda: self.booth_cfg_open_mock.write.assert_called_once_with(
                self.config_data
            )
        )

    def test_success(self):
        commands.pull_config(self.env_assist.get_env(), self.node_name)

        self.env_assist.assert_reports(self.report_list)

    def test_success_config_exists(self):
        self.config.fs.exists(self.config_path, True, instead="fs.exists")

        commands.pull_config(self.env_assist.get_env(), self.node_name)

        self.env_assist.assert_reports(
            self.report_list
            +
            [
                fixture.warn(
                    report_codes.FILE_ALREADY_EXISTS,
                    node=None,
                    file_role=file_roles.BOOTH_CONFIG,
                    file_path=self.config_path,
                ),
            ]
        )


class PullConfigFailure(PullConfigBase):
    reason = "reason"
    def test_write_failure(self):
        (self.config
            .http.booth.get_config(
                self.name, self.config_data, node_labels=[self.node_name]
            )
            .fs.exists(self.config_path, False)
            .fs.open(
                self.config_path,
                mode="w",
                side_effect=EnvironmentError(0, self.reason, self.config_path),
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, self.config_path),
                    file_role=file_roles.BOOTH_CONFIG,
                    file_path=self.config_path,
                    operation="write",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.report_list[:1])

    def test_network_failure(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[dict(
                label=self.node_name,
                was_connected=False,
                errno=1,
                error_msg=self.reason,
            )]
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports([
            self.report_list[0],
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                force_code=None,
                node=self.node_name,
                command="remote/booth_get_config",
                reason=self.reason,
            ),
        ])

    def test_network_request_failure(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[dict(
                label=self.node_name,
                response_code=400,
                output=self.reason,
            )]
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports([
            self.report_list[0],
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=None,
                node=self.node_name,
                command="remote/booth_get_config",
                reason=self.reason,
            ),
        ])

    def test_request_response_not_json(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[dict(
                label=self.node_name,
                output="not json",
            )]
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports([
            self.report_list[0],
            fixture.error(
                report_codes.INVALID_RESPONSE_FORMAT,
                node=self.node_name,
            ),
        ])

    def test_request_response_missing_keys(self):
        self.config.http.booth.get_config(
            self.name,
            communication_list=[dict(
                label=self.node_name,
                output="{'config':{}}",
            )]
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [],
        )
        self.env_assist.assert_reports([
            self.report_list[0],
            fixture.error(
                report_codes.INVALID_RESPONSE_FORMAT,
                node=self.node_name,
            ),
        ])


class PullConfigWithAuthfile(PullConfigBase):
    def setUp(self):
        super(PullConfigWithAuthfile, self).setUp()
        self.booth_cfg_open_mock = mock.mock_open()()
        self.authfile = "authfile"
        self.authfile_path = _get_booth_file_path(self.authfile)
        self.authfile_data = b"auth"
        self.pcmk_uid = 2
        self.pcmk_gid = 3

        (self.config
            .http.booth.get_config(
                self.name,
                self.config_data,
                authfile=self.authfile,
                authfile_data=self.authfile_data,
                node_labels=[self.node_name],
            )
            .fs.exists(self.config_path, False)
            .fs.open(self.config_path, self.booth_cfg_open_mock, mode="w")
            .fs.exists(self.authfile_path, False, name="fs.exists.authfile")
        )

        self.addCleanup(
            lambda: self.booth_cfg_open_mock.write.assert_called_once_with(
                self.config_data
            )
        )

    def _set_pwd_mock(self, pwd_mock):
        pwd_mock.return_value = namedtuple("Pw", "pw_uid")(self.pcmk_uid)
        self.addCleanup(
            lambda: pwd_mock.assert_called_once_with(settings.pacemaker_uname)
        )

    def _set_grp_mock(self, grp_mock):
        grp_mock.return_value = namedtuple("Gr", "gr_gid")(self.pcmk_gid)
        self.addCleanup(
            lambda: grp_mock.assert_called_once_with(settings.pacemaker_gname)
        )


@mock.patch("grp.getgrnam")
@mock.patch("pwd.getpwnam")
class PullConfigWithAuthfileSuccess(PullConfigWithAuthfile):
    def setUp(self):
        super(PullConfigWithAuthfileSuccess, self).setUp()
        self.booth_authfile_open_mock = mock.mock_open()()

        (self.config
            .fs.open(
                self.authfile_path,
                self.booth_authfile_open_mock,
                mode="wb",
                name="fs.open.authfile.write"
            )
            .fs.chown(self.authfile_path, self.pcmk_uid, self.pcmk_gid)
            .fs.chmod(self.authfile_path, settings.booth_authkey_file_mode)
        )

        self.addCleanup(
            lambda: self.booth_authfile_open_mock.write.assert_called_once_with(
                self.authfile_data
            )
        )

    def test_success(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        self._set_grp_mock(grp_mock)

        commands.pull_config(self.env_assist.get_env(), self.node_name)

        self.env_assist.assert_reports(self.report_list)

    def test_success_authfile_exists(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        self._set_grp_mock(grp_mock)

        self.config.fs.exists(
            self.authfile_path, True,
            name="fs.exists.authfile",
            instead="fs.exists.authfile",
        )

        commands.pull_config(self.env_assist.get_env(), self.node_name)

        self.env_assist.assert_reports(
            self.report_list
            +
            [
                fixture.warn(
                    report_codes.FILE_ALREADY_EXISTS,
                    node=None,
                    file_role=file_roles.BOOTH_KEY,
                    file_path=self.authfile_path,
                )
            ]
        )

    def test_success_config_and_authfile_exists(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        self._set_grp_mock(grp_mock)

        (self.config
            .fs.exists(self.config_path, True, instead="fs.exists")
            .fs.exists(
                self.authfile_path, True,
                name="fs.exists.authfile",
                instead="fs.exists.authfile",
            )
        )

        commands.pull_config(self.env_assist.get_env(), self.node_name)

        self.env_assist.assert_reports(
            self.report_list
            +
            [
                fixture.warn(
                    report_codes.FILE_ALREADY_EXISTS,
                    node=None, file_role=role, file_path=path,
                ) for role, path in [
                    (file_roles.BOOTH_CONFIG, self.config_path),
                    (file_roles.BOOTH_KEY, self.authfile_path)
                ]
            ]
        )


@mock.patch("grp.getgrnam")
@mock.patch("pwd.getpwnam")
class PullConfigWithAuthfileFailure(PullConfigWithAuthfile):
    def setUp(self):
        super(PullConfigWithAuthfileFailure, self).setUp()
        self.reason = "reason"
        self.booth_authfile_open_mock = mock.mock_open()()

    def assert_authfile_written(self):
        self.booth_authfile_open_mock.write.assert_called_once_with(
            self.authfile_data
        )

    def test_authfile_write_failure(self, pwd_mock, grp_mock):
        self.config.fs.open(
            self.authfile_path,
            mode="wb",
            name="fs.open.authfile.write",
            side_effect=EnvironmentError(1, self.reason, self.authfile_path)
        )
        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, self.authfile_path),
                    file_role=file_roles.BOOTH_KEY,
                    file_path=self.authfile_path,
                    operation="write",
                )
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(self.report_list[:1])

    def test_unable_to_get_uid(self, pwd_mock, grp_mock):
        pwd_mock.side_effect = KeyError()
        self.config.fs.open(
            self.authfile_path,
            self.booth_authfile_open_mock,
            mode="wb",
            name="fs.open.authfile.write"
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.UNABLE_TO_DETERMINE_USER_UID,
                    user=settings.pacemaker_uname,
                )
            ],
            expected_in_processor=False,
        )
        self.assert_authfile_written()
        pwd_mock.assert_called_once_with(settings.pacemaker_uname)
        self.assertEqual(0, grp_mock.call_count)
        self.env_assist.assert_reports(self.report_list[:1])

    def test_unable_to_get_gid(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        grp_mock.side_effect = KeyError()
        self.config.fs.open(
            self.authfile_path,
            self.booth_authfile_open_mock,
            mode="wb",
            name="fs.open.authfile.write"
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.UNABLE_TO_DETERMINE_GROUP_GID,
                    group=settings.pacemaker_gname,
                )
            ],
            expected_in_processor=False,
        )
        self.assert_authfile_written()
        grp_mock.assert_called_once_with(settings.pacemaker_gname)
        self.env_assist.assert_reports(self.report_list[:1])

    def test_unable_to_set_authfile_uid_gid(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        self._set_grp_mock(grp_mock)
        (self.config
            .fs.open(
                self.authfile_path,
                self.booth_authfile_open_mock,
                mode="wb",
                name="fs.open.authfile.write"
            )
            .fs.chown(
                self.authfile_path, self.pcmk_uid, self.pcmk_gid,
                side_effect=EnvironmentError(1, self.reason, self.authfile_path)
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, self.authfile_path),
                    file_role=file_roles.BOOTH_KEY,
                    file_path=self.authfile_path,
                    operation="chown",
                )
            ],
            expected_in_processor=False,
        )
        self.assert_authfile_written()
        self.env_assist.assert_reports(self.report_list[:1])

    def test_unable_to_set_authfile_mode(self, pwd_mock, grp_mock):
        self._set_pwd_mock(pwd_mock)
        self._set_grp_mock(grp_mock)
        (self.config
            .fs.open(
                self.authfile_path,
                self.booth_authfile_open_mock,
                mode="wb",
                name="fs.open.authfile.write"
            )
            .fs.chown(
                self.authfile_path, self.pcmk_uid, self.pcmk_gid,
            )
            .fs.chmod(
                self.authfile_path, settings.booth_authkey_file_mode,
                side_effect=EnvironmentError(1, self.reason, self.authfile_path)
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: commands.pull_config(
                self.env_assist.get_env(), self.node_name
            ),
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    reason="{}: '{}'".format(self.reason, self.authfile_path),
                    file_role=file_roles.BOOTH_KEY,
                    file_path=self.authfile_path,
                    operation="chmod",
                )
            ],
            expected_in_processor=False,
        )
        self.assert_authfile_written()
        self.env_assist.assert_reports(self.report_list[:1])


class TicketOperationTest(TestCase):
    @mock.patch("pcs.lib.booth.resource.find_bound_ip")
    def test_raises_when_implicit_site_not_found_in_cib(
        self, mock_find_bound_ip
    ):
        mock_find_bound_ip.return_value = []
        assert_raise_library_error(
            lambda: commands._ticket_operation(
                "grant", _env_fixture("booth_name"), "ABC", site_ip=None
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
            lambda: commands._ticket_operation(
                "grant", mock_env, "ABC", site_ip="1.2.3.4"
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
                _env_fixture("somename"), ip="1.2.3.4"
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
        report_processor = MockLibraryReportProcessor()
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
