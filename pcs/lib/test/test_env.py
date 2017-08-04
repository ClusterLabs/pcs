from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase
import logging
from functools import partial
from lxml import etree

from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import get_test_resource as rc, create_patcher
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.xml import etree_to_str

from pcs.lib.env import LibraryEnvironment
from pcs.common import report_codes
from pcs.lib.node import NodeAddresses, NodeAddressesList
from pcs.lib.cluster_conf_facade import ClusterConfFacade
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.errors import ReportItemSeverity as severity


patch_env = create_patcher("pcs.lib.env")
patch_env_object = partial(mock.patch.object, LibraryEnvironment)

class LibraryEnvironmentTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_logger(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(self.mock_logger, env.logger)

    def test_report_processor(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(self.mock_reporter, env.report_processor)

    def test_user_set(self):
        user = "testuser"
        env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            user_login=user
        )
        self.assertEqual(user, env.user_login)

    def test_user_not_set(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual(None, env.user_login)

    def test_usergroups_set(self):
        groups = ["some", "group"]
        env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            user_groups=groups
        )
        self.assertEqual(groups, env.user_groups)

    def test_usergroups_not_set(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertEqual([], env.user_groups)

    @patch_env("is_cman_cluster")
    def test_is_cman_cluster(self, mock_is_cman):
        mock_is_cman.return_value = True
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertTrue(env.is_cman_cluster)
        self.assertTrue(env.is_cman_cluster)
        self.assertEqual(1, mock_is_cman.call_count)


    @patch_env("NodeCommunicator")
    def test_node_communicator_no_options(self, mock_comm):
        expected_comm = mock.MagicMock()
        mock_comm.return_value = expected_comm
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        comm = env.node_communicator()
        self.assertEqual(expected_comm, comm)
        mock_comm.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {},
            None,
            [],
            None
        )

    @patch_env("NodeCommunicator")
    def test_node_communicator_all_options(self, mock_comm):
        expected_comm = mock.MagicMock()
        mock_comm.return_value = expected_comm
        user = "testuser"
        groups = ["some", "group"]
        tokens = {"node": "token"}
        timeout = 10
        env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            user_login=user,
            user_groups=groups,
            auth_tokens_getter=lambda:tokens,
            request_timeout=timeout
        )
        comm = env.node_communicator()
        self.assertEqual(expected_comm, comm)
        mock_comm.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            tokens,
            user,
            groups,
            timeout
        )

    @patch_env("get_local_cluster_conf")
    def test_get_cluster_conf_live(self, mock_get_local_cluster_conf):
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, cluster_conf_data=None
        )
        mock_get_local_cluster_conf.return_value = "cluster.conf data"
        self.assertEqual("cluster.conf data", env.get_cluster_conf_data())
        mock_get_local_cluster_conf.assert_called_once_with()

    @patch_env("get_local_cluster_conf")
    def test_get_cluster_conf_not_live(self, mock_get_local_cluster_conf):
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, cluster_conf_data="data"
        )
        self.assertEqual("data", env.get_cluster_conf_data())
        self.assertEqual(0, mock_get_local_cluster_conf.call_count)

    @mock.patch.object(
        LibraryEnvironment,
        "get_cluster_conf_data",
        lambda self: "<cluster/>"
    )
    def test_get_cluster_conf(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        facade_obj = env.get_cluster_conf()
        self.assertTrue(isinstance(facade_obj, ClusterConfFacade))
        assert_xml_equal(
            '<cluster/>', etree.tostring(facade_obj._config).decode()
        )

    def test_is_cluster_conf_live_live(self):
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.assertTrue(env.is_cluster_conf_live)

    def test_is_cluster_conf_live_not_live(self):
        env = LibraryEnvironment(
            self.mock_logger, self.mock_reporter, cluster_conf_data="data"
        )
        self.assertFalse(env.is_cluster_conf_live)

@patch_env("CommandRunner")
class CmdRunner(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def test_no_options(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "LC_ALL": "C",
            }
        )

    def test_user(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        user = "testuser"
        env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            user_login=user
        )
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "CIB_user": user,
                "LC_ALL": "C",
            }
        )

    @patch_env("write_tmpfile")
    def test_dump_cib_file(self, mock_tmpfile, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        mock_instance = mock.MagicMock()
        mock_instance.name = rc("file.tmp")
        mock_tmpfile.return_value = mock_instance
        env = LibraryEnvironment(
            self.mock_logger,
            self.mock_reporter,
            cib_data="<cib />"
        )
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            self.mock_reporter,
            {
                "LC_ALL": "C",
                "CIB_file": rc("file.tmp"),
            }
        )
        mock_tmpfile.assert_called_once_with("<cib />")


@patch_env_object("cmd_runner", lambda self: "runner")
class EnsureValidWait(TestCase):
    def setUp(self):
        self.create_env = partial(
            LibraryEnvironment,
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )

    @property
    def env_live(self):
        return self.create_env()

    @property
    def env_fake(self):
        return self.create_env(cib_data="<cib/>")

    def test_not_raises_if_waiting_false_no_matter_if_env_is_live(self):
        self.env_live.ensure_wait_satisfiable(False)
        self.env_fake.ensure_wait_satisfiable(False)

    def test_raises_when_is_not_live(self):
        env = self.env_fake
        assert_raise_library_error(
            lambda: env.ensure_wait_satisfiable(10),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                {},
                None
            )
        )

    @patch_env("get_valid_timeout_seconds")
    @patch_env("ensure_wait_for_idle_support")
    def test_do_checks(self, ensure_wait_for_idle_support, get_valid_timeout):
        env = self.env_live
        env.ensure_wait_satisfiable(10)
        ensure_wait_for_idle_support.assert_called_once_with(env.cmd_runner())
        get_valid_timeout.assert_called_once_with(10)


class PushCorosyncConfLiveBase(TestCase):
    def setUp(self):
        self.env_assistant, self.config = get_env_tools(self)
        self.corosync_conf_facade = mock.MagicMock(CorosyncConfigFacade)
        self.corosync_conf_text = "corosync conf"
        self.corosync_conf_facade.config.export.return_value = (
            self.corosync_conf_text
        )
        self.corosync_conf_facade.get_nodes.return_value = NodeAddressesList([
            NodeAddresses("node-1"),
            NodeAddresses("node-2"),
        ])
        self.corosync_conf_facade.need_stopped_cluster = False
        self.corosync_conf_facade.need_qdevice_reload = False
        self.node_label_list = [
            dict(label="node-1"),
            dict(label="node-2"),
        ]


@mock.patch("pcs.lib.external.is_systemctl")
class PushCorosyncConfLiveNoQdeviceTest(PushCorosyncConfLiveBase):
    def test_dont_need_stopped_cluster(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        (self.config
            .http.add_communication(
                "distribute_corosync_conf",
                self.node_label_list,
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
                response_code=200,
                output="Succeeded",
            )
            .runner.systemctl.is_active("corosync")
            .runner.corosync.reload()
        )
        self.env_assistant.get_env().push_corosync_conf(
            self.corosync_conf_facade
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-2",
            ),
            fixture.info(report_codes.COROSYNC_CONFIG_RELOADED)
        ])

    def test_need_stopped_cluster(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_stopped_cluster = True
        (self.config
            .http.add_communication(
                "status",
                self.node_label_list,
                action="remote/status",
                response_code=200,
                output="""
{"uptime":"0 days, 05:07:39","corosync":false,"pacemaker":false,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":[],\
"corosync_offline":["node-1","node-2"],"pacemaker_online":[],\
"pacemaker_offline":[],"pacemaker_standby":[],"cluster_name":"cluster_name",\
"resources":[],"groups":[],"constraints":{},"cluster_settings":{"error":\
"Unable to get configuration settings"},"node_id":"","node_attr":{},\
"fence_levels":{},"need_ring1_address":false,"is_cman_with_udpu_transport":\
false,"acls":{},"username":"hacluster"}
                """,
            )
            .http.add_communication(
                "set_corosync_conf",
                self.node_label_list,
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
                response_code=200,
                output="Succeeded",
            )
            .runner.systemctl.is_active("corosync", is_active=False)
        )
        self.env_assistant.get_env().push_corosync_conf(
            self.corosync_conf_facade
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                node="node-2",
            ),
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-2",
            ),
        ])

    def test_need_stopped_cluster_not_stopped(self, mock_is_systemctl):
        self.corosync_conf_facade.need_stopped_cluster = True
        mock_is_systemctl.return_value = True
        (self.config
            .http.add_communication(
                "status",
                self.node_label_list,
                action="remote/status",
                response_code=200,
                output="""
{"uptime":"0 days, 06:29:36","corosync":true,"pacemaker":true,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":\
["node-1","node-2"],"corosync_offline":[],"pacemaker_online":["node-1",\
"node-2"],"pacemaker_offline":[],"pacemaker_standby":[],"cluster_name":\
"cluster_name","resources":[],"groups":[],"constraints":{},"cluster_settings":\
{"have-watchdog":"false","dc-version":"1.1.16-11.el7-94ff4df",\
"cluster-infrastructure":"corosync","cluster-name":"cluster_name"},\
"node_id":"1","node_attr":{},"fence_levels":{},"need_ring1_address":false,\
"is_cman_with_udpu_transport":false,"acls":{"role":{},"group":{},"user":{},\
"target":{}},"username":"hacluster"}
                """,
            )
        )
        env = self.env_assistant.get_env()
        self.env_assistant.assert_raise_library_error(
            lambda: env.push_corosync_conf(self.corosync_conf_facade),
            []
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            fixture.error(
                report_codes.COROSYNC_RUNNING_ON_NODE,
                node="node-1",
            ),
            fixture.error(
                report_codes.COROSYNC_RUNNING_ON_NODE,
                node="node-2",
            ),
        ])

    def test_need_stopped_cluster_not_stopped_skip_offline(
        self, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_stopped_cluster = True
        (self.config
            .http.add_communication(
                "status",
                [
                    dict(
                        label="node-1",
                        output="""\
{"uptime":"0 days, 06:36:00","corosync":true,"pacemaker":true,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":\
["node-1"],"corosync_offline":["node-2"],"pacemaker_online":["node-1"],\
"pacemaker_offline":["node-2"],"pacemaker_standby":[],"cluster_name":\
"cluster_name","resources":[],"groups":[],"constraints":{},"cluster_settings":\
{"have-watchdog":"false","dc-version":"1.1.16-11.el7-94ff4df",\
"cluster-infrastructure":"corosync","cluster-name":"cluster_name"},\
"node_id":"1","node_attr":{},"fence_levels":{},"need_ring1_address":false,\
"is_cman_with_udpu_transport":false,"acls":{"role":{},"group":{},"user":{},\
"target":{}},"username":"hacluster"}
                        """,
                    ),
                    dict(
                        label="node-2",
                        output="""\
{"uptime":"0 days, 06:35:58","corosync":false,"pacemaker":false,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":[],\
"corosync_offline":["node-1","node-2"],"pacemaker_online":[],\
"pacemaker_offline":[],"pacemaker_standby":[],"cluster_name":"cluster_name",\
"resources":[],"groups":[],"constraints":{},"cluster_settings":\
{"error":"Unable to get configuration settings"},"node_id":"","node_attr":{},\
"fence_levels":{},"need_ring1_address":false,"is_cman_with_udpu_transport":\
false,"acls":{},"username":"hacluster"}
                        """,
                    ),
                ],
                action="remote/status",
                response_code=200,
            )
        )
        env = self.env_assistant.get_env()
        self.env_assistant.assert_raise_library_error(
            lambda: env.push_corosync_conf(
                self.corosync_conf_facade, skip_offline_nodes=True
            ),
            []
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            fixture.error(
                report_codes.COROSYNC_RUNNING_ON_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                node="node-2",
            )
        ])

    def test_need_stopped_cluster_comunnication_failure(
        self, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_stopped_cluster = True
        (self.config
            .http.add_communication(
                "status",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="""\
{"uptime":"0 days, 00:11:52","corosync":false,"pacemaker":false,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":[],\
"corosync_offline":["node-1","node-2"],"pacemaker_online":[],\
"pacemaker_offline":[],"pacemaker_standby":[],"cluster_name":"cluster_name",\
"resources":[],"groups":[],"constraints":{},"cluster_settings":\
{"error":"Unable to get configuration settings"},"node_id":"","node_attr":{},\
"fence_levels":{},"need_ring1_address":false,"is_cman_with_udpu_transport":\
false,"acls":{},"username":"hacluster"}
                        """,
                    ),
                    dict(
                        label="node-2",
                        response_code=401,
                        output="""{"notauthorized":"true"}"""
                    ),
                ],
                action="remote/status",
            )
        )
        env = self.env_assistant.get_env()
        self.env_assistant.assert_raise_library_error(
            lambda: env.push_corosync_conf(self.corosync_conf_facade),
            []
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                node="node-1",
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node="node-2",
            ),
            fixture.error(
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node="node-2",
            ),
        ])

    def test_need_stopped_cluster_comunnication_failure_skip_offline(
        self, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_stopped_cluster = True
        (self.config
            .http.add_communication(
                "status",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="""\
{"uptime":"0 days, 00:11:52","corosync":false,"pacemaker":false,"cman":false,\
"corosync_enabled":false,"pacemaker_enabled":false,"pacemaker_remote":false,\
"pacemaker_remote_enabled":false,"pcsd_enabled":true,"corosync_online":[],\
"corosync_offline":["node-1","node-2"],"pacemaker_online":[],\
"pacemaker_offline":[],"pacemaker_standby":[],"cluster_name":"cluster_name",\
"resources":[],"groups":[],"constraints":{},"cluster_settings":\
{"error":"Unable to get configuration settings"},"node_id":"","node_attr":{},\
"fence_levels":{},"need_ring1_address":false,"is_cman_with_udpu_transport":\
false,"acls":{},"username":"hacluster"}
                        """,
                    ),
                    dict(
                        label="node-2",
                        response_code=401,
                        output="""{"notauthorized":"true"}"""
                    ),
                ],
                action="remote/status",
            )
            .http.add_communication(
                "set_corosync_conf",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="Succeeded",
                    ),
                    dict(
                        label="node-2",
                        response_code=401,
                        output="""{"notauthorized":"true"}""",
                    )
                ],
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
            )
            .runner.systemctl.is_active("corosync", is_active=False)
        )
        self.env_assistant.get_env().push_corosync_conf(
            self.corosync_conf_facade, skip_offline_nodes=True
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                node="node-1",
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                node="node-2",
                reason="HTTP error: 401",
                command="remote/status",
            ),
            fixture.warn(
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                node="node-2",
            ),
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                node="node-2",
                reason="HTTP error: 401",
                command="remote/set_corosync_conf",
            ),
            fixture.warn(
                report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                node="node-2",
            ),
        ])


@mock.patch("pcs.lib.external.is_systemctl")
class PushCorosyncConfLiveWithQdeviceTest(PushCorosyncConfLiveBase):
    def test_qdevice_reload(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_qdevice_reload = True
        (self.config
            .http.add_communication(
                "set_corosync_conf",
                self.node_label_list,
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
                response_code=200,
                output="Succeeded",
            )
            .runner.systemctl.is_active("corosync", is_active=False)
            .http.add_communication(
                "qdevice_client_stop",
                self.node_label_list,
                action="remote/qdevice_client_stop",
                response_code=200,
                output="corosync-qdevice stopped",
            )
            .http.add_communication(
                "qdevice_client_start",
                self.node_label_list,
                action="remote/qdevice_client_start",
                response_code=200,
                output="corosync-qdevice started",
            )
        )
        self.env_assistant.get_env().push_corosync_conf(
            self.corosync_conf_facade
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-2",
            ),
            fixture.info(report_codes.QDEVICE_CLIENT_RELOAD_STARTED),
            fixture.info(
                report_codes.SERVICE_STOP_SUCCESS,
                node="node-1",
                service="corosync-qdevice",
                instance=None,
            ),
            fixture.info(
                report_codes.SERVICE_STOP_SUCCESS,
                node="node-2",
                service="corosync-qdevice",
                instance=None,
            ),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node="node-1",
                service="corosync-qdevice",
                instance=None,
            ),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node="node-2",
                service="corosync-qdevice",
                instance=None,
            ),
        ])

    def test_qdevice_reload_failures(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_qdevice_reload = True
        (self.config
            .http.add_communication(
                "set_corosync_conf",
                self.node_label_list,
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
                response_code=200,
                output="Succeeded",
            )
            .runner.systemctl.is_active("corosync", is_active=False)
            .http.add_communication(
                "qdevice_client_stop",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="corosync-qdevice stopped",
                    ),
                    dict(
                        label="node-2",
                        response_code=400,
                        output="error",
                    ),
                ],
                action="remote/qdevice_client_stop",
            )
            .http.add_communication(
                "qdevice_client_start",
                [
                    dict(
                        label="node-1",
                        errno=8,
                        error_msg="failure",
                        was_connected=False,
                    ),
                    dict(
                        label="node-2",
                        response_code=200,
                        output="corosync-qdevice started",
                    ),
                ],
                action="remote/qdevice_client_start",
            )
        )
        env = self.env_assistant.get_env()
        self.env_assistant.assert_raise_library_error(
            lambda: env.push_corosync_conf(self.corosync_conf_facade),
            []
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-2",
            ),
            fixture.info(report_codes.QDEVICE_CLIENT_RELOAD_STARTED),
            fixture.info(
                report_codes.SERVICE_STOP_SUCCESS,
                node="node-1",
                service="corosync-qdevice",
                instance=None,
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node="node-2",
                reason="error",
                command="remote/qdevice_client_stop",
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node="node-1",
                reason="failure",
                command="remote/qdevice_client_start",
            ),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node="node-2",
                service="corosync-qdevice",
                instance=None,
            ),
        ])

    def test_qdevice_reload_failures_skip_offline(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.corosync_conf_facade.need_qdevice_reload = True
        (self.config
            .http.add_communication(
                "set_corosync_conf",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="Succeeded",
                    ),
                    dict(
                        label="node-2",
                        errno=8,
                        error_msg="failure",
                        was_connected=False,
                    ),
                ],
                action="remote/set_corosync_conf",
                param_list=[("corosync_conf", self.corosync_conf_text)],
            )
            .runner.systemctl.is_active("corosync", is_active=False)
            .http.add_communication(
                "qdevice_client_stop",
                [
                    dict(
                        label="node-1",
                        response_code=200,
                        output="corosync-qdevice stopped",
                    ),
                    dict(
                        label="node-2",
                        response_code=400,
                        output="error",
                    ),
                ],
                action="remote/qdevice_client_stop",
            )
            .http.add_communication(
                "qdevice_client_start",
                [
                    dict(
                        label="node-1",
                        errno=8,
                        error_msg="failure",
                        was_connected=False,
                    ),
                    dict(
                        label="node-2",
                        response_code=200,
                        output="corosync-qdevice started",
                    ),
                ],
                action="remote/qdevice_client_start",
            )
        )
        env = self.env_assistant.get_env()
        env.push_corosync_conf(
            self.corosync_conf_facade, skip_offline_nodes=True
        )
        self.env_assistant.assert_reports([
            fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            fixture.info(
                report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                node="node-1",
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node="node-2",
                reason="failure",
                command="remote/set_corosync_conf",
            ),
            fixture.warn(
                report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                node="node-2",
            ),
            fixture.info(report_codes.QDEVICE_CLIENT_RELOAD_STARTED),
            fixture.info(
                report_codes.SERVICE_STOP_SUCCESS,
                node="node-1",
                service="corosync-qdevice",
                instance=None,
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                node="node-2",
                reason="error",
                command="remote/qdevice_client_stop",
            ),
            fixture.warn(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node="node-1",
                reason="failure",
                command="remote/qdevice_client_start",
            ),
            fixture.info(
                report_codes.SERVICE_START_SUCCESS,
                node="node-2",
                service="corosync-qdevice",
                instance=None,
            ),
        ])


class PushCorosyncConfFile(TestCase):
    def setUp(self):
        self.env_assistant, self.config = get_env_tools(
            self, corosync_conf_data="totem {\n    version: 2\n}\n",
        )

    def test_success(self):
        env = self.env_assistant.get_env()
        new_corosync_conf_data = "totem {\n    version: 3\n}\n"
        env.push_corosync_conf(
            CorosyncConfigFacade.from_string(new_corosync_conf_data)
        )
        self.assertEqual(new_corosync_conf_data, env.get_corosync_conf_data())


class GetCorosyncConfFile(TestCase):
    def setUp(self):
        self.corosync_conf_data = "totem {\n    version: 2\n}\n"
        self.env_assistant, self.config = get_env_tools(
            self, corosync_conf_data=self.corosync_conf_data,
        )

    def test_success(self):
        env = self.env_assistant.get_env()
        self.assertFalse(env.is_corosync_conf_live)
        self.assertEqual(self.corosync_conf_data, env.get_corosync_conf_data())
        self.assertEqual(
            self.corosync_conf_data, env.get_corosync_conf().config.export()
        )


class GetCorosyncConfLive(TestCase):
    def setUp(self):
        self.env_assistant, self.config = get_env_tools(self)

    def test_success(self):
        corosync_conf_data = "totem {\n    version: 2\n}\n"
        self.config.corosync_conf.load_content(corosync_conf_data)
        env = self.env_assistant.get_env()
        self.assertTrue(env.is_corosync_conf_live)
        self.assertEqual(
            corosync_conf_data, env.get_corosync_conf().config.export()
        )


@patch_env_object("push_cib_diff")
@patch_env_object("push_cib_full")
class CibPushProxy(TestCase):
    def setUp(self):
        self.env = LibraryEnvironment(
            mock.MagicMock(logging.Logger),
            MockLibraryReportProcessor()
        )

    def test_push_loaded(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib()
        mock_push_full.assert_called_once_with(None, False)
        mock_push_diff.assert_not_called()

    def test_push_loaded_wait(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(wait=10)
        mock_push_full.assert_called_once_with(None, 10)
        mock_push_diff.assert_not_called()

    def test_push_custom(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(custom_cib="<cib />")
        mock_push_full.assert_called_once_with("<cib />", False)
        mock_push_diff.assert_not_called()

    def test_push_custom_wait(self, mock_push_full, mock_push_diff):
        self.env.get_cib()
        self.env.push_cib(custom_cib="<cib />", wait=10)
        mock_push_full.assert_called_once_with("<cib />", 10)
        mock_push_diff.assert_not_called()


class CibBase(object):
    def place_load_calls(self, name="load_cib"):
        return NotImplementedError

    def assertion_error(self, callable_obj, message):
        try:
            callable_obj()
        except AssertionError as e:
            self.assertEqual(str(e), message)

    def assert_already_loaded(self, callable_obj):
        self.assertion_error(callable_obj, "CIB has already been loaded")

    def assert_not_loaded(self, callable_obj):
        self.assertion_error(callable_obj, "CIB has not been loaded")

    def assert_cannot_push_custom(self, callable_obj):
        self.assertion_error(
            callable_obj,
            "CIB has been loaded, cannot push custom CIB"
        )

    def test_get_and_property(self):
        self.place_load_calls()
        env = self.env_assist.get_env()
        self.assertEqual(env.get_cib(), env.cib)

    def test_property_without_get(self):
        env = self.env_assist.get_env()
        # need to use lambda because env.cib is a property
        self.assert_not_loaded(lambda: env.cib)

    def test_double_get(self):
        self.place_load_calls()
        env = self.env_assist.get_env()
        env.get_cib()
        self.assert_already_loaded(env.get_cib)

    def test_push_without_get(self):
        env = self.env_assist.get_env()
        self.assert_not_loaded(self.push_function(env))

    def test_can_get_after_push(self):
        self.place_load_calls()
        self.place_push_calls()
        self.place_load_calls(name="load_cib_2")

        env = self.env_assist.get_env()
        env.get_cib()
        self.push_function(env)()
        # need to use lambda because env.cib is a property
        self.assert_not_loaded(lambda: env.cib)
        env.get_cib()


class CibLive(CibBase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def push_function(self, env):
        return NotImplementedError

    def place_push_calls(self):
        return NotImplementedError

    def place_load_calls(self, name="load_cib"):
        self.config.runner.cib.load(name=name)

    def test_is_live(self):
        env = self.env_assist.get_env()
        self.assertTrue(env.is_cib_live)

    def test_get_and_push(self):
        self.config.runner.cib.load()
        self.place_push_calls()

        env = self.env_assist.get_env()
        env.get_cib()
        self.assertFalse(env.cib_upgraded)
        self.push_function(env)()
        self.assertFalse(env.cib_upgraded)

    def test_get_and_push_cib_version_upgrade_needed(self):
        (self.config
            .runner.cib.load(filename="cib-empty-2.6.xml", name="load_cib_old")
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-2.8.xml")
        )
        self.place_push_calls()
        env = self.env_assist.get_env()

        env.get_cib((2, 8, 0))
        self.assertTrue(env.cib_upgraded)
        self.push_function(env)()
        self.assertFalse(env.cib_upgraded)

        self.env_assist.assert_reports([
            (
                severity.INFO,
                report_codes.CIB_UPGRADE_SUCCESSFUL,
                {
                },
                None
            ),
        ])

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        self.config.runner.cib.load(filename="cib-empty-2.6.xml")
        self.place_push_calls()
        env = self.env_assist.get_env()

        env.get_cib((2, 5, 0))
        self.assertFalse(env.cib_upgraded)
        self.push_function(env)()
        self.assertFalse(env.cib_upgraded)

    def test_push_wait(self):
        wait_timeout = 10
        (self.config
            .runner.cib.load()
            .runner.pcmk.can_wait()
        )
        self.place_push_calls()
        self.config.runner.pcmk.wait(timeout=wait_timeout)

        env = self.env_assist.get_env()
        env.get_cib()
        self.push_function(env)(wait=wait_timeout)

    def test_push_wait_invalid_timeout(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.can_wait()
        )
        env = self.env_assist.get_env()
        env.get_cib()
        assert_raise_library_error(
            lambda: self.push_function(env)(wait="abc"),
            (
                severity.ERROR,
                report_codes.INVALID_TIMEOUT_VALUE,
                {
                    "timeout": "abc",
                },
                None
            )
        )

    def test_push_wait_not_supported(self):
        (self.config
            .runner.cib.load()
            .runner.pcmk.can_wait(stdout="cannot wait")
        )
        env = self.env_assist.get_env()
        env.get_cib()
        assert_raise_library_error(
            lambda: self.push_function(env)(wait=10),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED,
                {
                },
                None
            )
        )


class CibLivePushFull(CibLive, TestCase):
    def push_function(self, env):
        return env.push_cib_full

    def place_push_calls(self):
        self.config.runner.cib.push()

    def test_push_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.push(stderr="invalid cib")
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.assertFalse(env.cib_upgraded)
        self.env_assist.assert_raise_library_error(
            env.push_cib_full,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_PUSH_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )

    def test_push_custom_without_get(self):
        custom_cib = "<custom_cib />"
        self.config.runner.cib.push_independent(custom_cib)
        env = self.env_assist.get_env()
        env.push_cib_full(etree.XML(custom_cib))

    def test_push_custom_after_get(self):
        self.config.runner.cib.load()
        env = self.env_assist.get_env()
        env.get_cib()
        self.assert_cannot_push_custom(lambda: env.push_cib_full("custom cib"))


class CibLivePushDiff(CibLive, TestCase):
    def setUp(self):
        tmpfile_patcher = mock.patch(
            "pcs.lib.pacemaker.live.write_tmpfile"
        )
        self.addCleanup(tmpfile_patcher.stop)
        self.mock_write_tmpfile = tmpfile_patcher.start()
        self.tmpfile_old = self.mock_tmpfile("old.cib")
        self.tmpfile_new = self.mock_tmpfile("new.cib")
        self.mock_write_tmpfile.side_effect = [
            self.tmpfile_old, self.tmpfile_new
        ]

        self.env_assist, self.config = get_env_tools(test_case=self)

    def mock_tmpfile(self, filename):
        mock_file = mock.MagicMock()
        mock_file.name = rc(filename)
        return mock_file

    def push_function(self, env):
        return env.push_cib_diff

    def place_push_calls(self):
        (self.config
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff()
        )

    def test_tmpfile_fails(self):
        self.config.runner.cib.load()
        self.mock_write_tmpfile.side_effect = EnvironmentError("test error")
        env = self.env_assist.get_env()
        env.get_cib()
        self.assertFalse(env.cib_upgraded)
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_SAVE_TMP_ERROR,
                    {
                        "reason": "test error",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )

    def test_diff_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.diff(
                self.tmpfile_old.name, self.tmpfile_new.name,
                stderr="invalid cib", returncode=1
             )
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.assertFalse(env.cib_upgraded)
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_DIFF_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )

    def test_push_fails(self):
        (self.config
            .runner.cib.load()
            .runner.cib.diff(self.tmpfile_old.name, self.tmpfile_new.name)
            .runner.cib.push_diff(stderr="invalid cib", returncode=1)
        )
        env = self.env_assist.get_env()
        env.get_cib()
        self.assertFalse(env.cib_upgraded)
        self.env_assist.assert_raise_library_error(
            env.push_cib_diff,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_PUSH_ERROR,
                    {
                        "reason": "invalid cib",
                    },
                    None
                )
            ],
            expected_in_processor=False
        )


class CibFile(CibBase):
    def setUp(self):
        self.cib_data = open(rc("cib-empty-2.6.xml")).read()
        self.env_assist, self.config = get_env_tools(
            test_case=self,
            cib_data=self.cib_data
        )

    def push_function(self, env):
        return NotImplementedError

    def place_load_calls(self, name="load_cib"):
        pass # no calls when the CIB is not live

    def place_push_calls(self):
        pass # no calls when the CIB is not live

    def test_is_live(self):
        env = self.env_assist.get_env()
        self.assertFalse(env.is_cib_live)

    def test_get_and_push(self):
        env = self.env_assist.get_env()
        assert_xml_equal(
            self.cib_data,
            etree_to_str(env.get_cib())
        )
        self.assertFalse(env.cib_upgraded)
        self.push_function(env)()
        assert_xml_equal(
            self.cib_data,
            env._get_cib_xml()
        )
        self.assertFalse(env.cib_upgraded)

    def test_get_and_push_cib_version_upgrade_needed(self):
        (self.config
            .runner.cib.upgrade()
            .runner.cib.load(filename="cib-empty-2.8.xml")
        )
        env = self.env_assist.get_env()

        env.get_cib((2, 8, 0))
        self.assertTrue(env.cib_upgraded)
        self.push_function(env)()
        self.assertTrue(env.cib_upgraded)

    def test_get_and_push_cib_version_upgrade_not_needed(self):
        env = self.env_assist.get_env()

        env.get_cib((2, 5, 0))
        self.assertFalse(env.cib_upgraded)
        self.push_function(env)()
        self.assertFalse(env.cib_upgraded)

    def test_push_wait(self):
        env = self.env_assist.get_env()
        env.get_cib()
        assert_raise_library_error(
            lambda: self.push_function(env)(wait=10),
            (
                severity.ERROR,
                report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
                {},
                None
            )
        )


class CibFilePushFull(CibFile, TestCase):
    def push_function(self, env):
        return env.push_cib_full

    def test_push_custom_without_get(self):
        custom_cib = "<custom_cib />"
        env = self.env_assist.get_env()
        env.push_cib_full(etree.XML(custom_cib))
        assert_xml_equal(
            custom_cib,
            env._get_cib_xml()
        )

    def test_push_custom_after_get(self):
        env = self.env_assist.get_env()
        env.get_cib()
        self.assert_cannot_push_custom(lambda: env.push_cib_full("custom cib"))


class CibFilePushDiff(CibFile, TestCase):
    def push_function(self, env):
        return env.push_cib_diff
