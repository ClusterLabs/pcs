from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.commands.sbd import disable_sbd
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools


class DisableSbd(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.corosync_conf_name = "corosync-3nodes.conf"
        self.node_list = ["rh7-1", "rh7-2", "rh7-3"]
        self.config.env.set_known_nodes(self.node_list)

    def test_success(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            node_labels=self.node_list[:1]
        )
        self.config.http.sbd.disable_sbd(node_labels=self.node_list)
        disable_sbd(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [fixture.info(report_codes.SBD_DISABLING_STARTED)]
            +
            [
                fixture.info(
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    service="sbd",
                    node=node,
                    instance=None
                ) for node in self.node_list
            ]
            +
            [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_node_offline(self):
        err_msg = "Failed connect to rh7-3:2224; No route to host"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(
            communication_list=[
                {"label": "rh7-1"},
                {"label": "rh7-2"},
                {
                    "label": "rh7-3",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": err_msg,
                }
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
            expected_in_processor=False
        )
        self.env_assist.assert_reports([
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                node="rh7-3",
                reason=err_msg,
                command="remote/check_auth"
            )
        ])

    def test_success_node_offline_skip_offline(self):
        err_msg = "Failed connect to rh7-3:2224; No route to host"
        online_nodes_list = ["rh7-2", "rh7-3"]
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(
            communication_list=[
                {
                    "label": "rh7-1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": err_msg,
                },
                {"label": "rh7-2"},
                {"label": "rh7-3"}
            ]
        )
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            node_labels=online_nodes_list[:1]
        )
        self.config.http.sbd.disable_sbd(node_labels=online_nodes_list)
        disable_sbd(self.env_assist.get_env(), ignore_offline_nodes=True)
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.OMITTING_NODE, node="rh7-1")]
            +
            [fixture.info(report_codes.SBD_DISABLING_STARTED)]
            +
            [
                fixture.info(
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    service="sbd",
                    node=node,
                    instance=None
                ) for node in online_nodes_list
            ]
            +
            [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_set_stonith_watchdog_timeout_fails_on_some_nodes(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[
                [{
                    "label": "rh7-1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": err_msg,
                }],
                [{
                    "label": "rh7-2",
                    "response_code": 400,
                    "output": "FAILED",
                }],
                [{"label": "rh7-3"}]
            ]
        )
        self.config.http.sbd.disable_sbd(node_labels=self.node_list)
        disable_sbd(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="rh7-1",
                    reason=err_msg,
                    command="remote/set_stonith_watchdog_timeout_to_zero"
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="rh7-2",
                    reason="FAILED",
                    command="remote/set_stonith_watchdog_timeout_to_zero"
                )
            ]
            +
            [fixture.info(report_codes.SBD_DISABLING_STARTED)]
            +
            [
                fixture.info(
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    service="sbd",
                    node=node,
                    instance=None
                ) for node in self.node_list
            ]
            +
            [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_set_stonith_watchdog_timeout_fails_on_all_nodes(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[
                [dict(label=node, response_code=400, output=err_msg)]
                for node in self.node_list
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    reason=err_msg,
                    command="remote/set_stonith_watchdog_timeout_to_zero"
                ) for node in self.node_list
            ]
            +
            [
                fixture.error(
                    report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                )
            ]
        )

    def test_disable_failed(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            node_labels=self.node_list[:1]
        )
        self.config.http.sbd.disable_sbd(
            communication_list=[
                {"label": "rh7-1"},
                {"label": "rh7-2"},
                {
                    "label": "rh7-3",
                    "response_code": 400,
                    "output": err_msg
                }
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [fixture.info(report_codes.SBD_DISABLING_STARTED)]
            +
            [
                fixture.info(
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    service="sbd",
                    node=node,
                    instance=None
                ) for node in self.node_list[:2]
            ]
            +
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="rh7-3",
                    reason=err_msg,
                    command="remote/sbd_disable"
                )
            ]
        )
