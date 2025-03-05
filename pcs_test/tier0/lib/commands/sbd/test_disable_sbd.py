from unittest import TestCase

from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.lib.commands.sbd import disable_sbd

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class DisableSbd(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.corosync_conf_name = "corosync-3nodes.conf"
        self.node_list = ["rh7-1", "rh7-2", "rh7-3"]
        self.config.env.set_known_nodes(self.node_list)
        self.cib_resources = """
            <resources>
                <primitive id="S-any" class="stonith" type="fence_any" />
            </resources>
        """

    def test_success(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[[dict(label=node)] for node in self.node_list],
        )
        self.config.http.sbd.disable_sbd(node_labels=self.node_list)
        disable_sbd(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.node_list
            ]
            + [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_no_stonith_left(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load()

        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                    force_code=reports.codes.FORCE,
                )
            ]
        )

    def test_no_stonith_left_forced(self):
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load()
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[[dict(label=node)] for node in self.node_list],
        )
        self.config.http.sbd.disable_sbd(node_labels=self.node_list)

        disable_sbd(
            self.env_assist.get_env(), force_flags={reports.codes.FORCE}
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NO_STONITH_MEANS_WOULD_BE_LEFT,
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.node_list
            ]
            + [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_some_node_names_missing(self):
        self.corosync_conf_name = "corosync-some-node-names.conf"
        self.node_list = ["rh7-2"]

        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[[dict(label=node)] for node in self.node_list],
        )
        self.config.http.sbd.disable_sbd(node_labels=self.node_list)

        disable_sbd(self.env_assist.get_env())

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.node_list
            ]
            + [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_all_node_names_missing(self):
        self.config.corosync_conf.load(filename="corosync-no-node-names.conf")
        self.config.runner.cib.load(resources=self.cib_resources)
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
                fixture.error(
                    report_codes.COROSYNC_CONFIG_NO_NODES_DEFINED,
                ),
            ]
        )

    def test_node_offline(self):
        err_msg = "Failed connect to rh7-3:2224; No route to host"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(
            communication_list=[
                {"label": "rh7-1"},
                {"label": "rh7-2"},
                {
                    "label": "rh7-3",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": err_msg,
                },
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    node="rh7-3",
                    reason=err_msg,
                    command="remote/check_auth",
                )
            ]
        )

    def test_success_node_offline_skip_offline(self):
        err_msg = "Failed connect to rh7-3:2224; No route to host"
        online_nodes_list = ["rh7-2", "rh7-3"]
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(
            communication_list=[
                {
                    "label": "rh7-1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": err_msg,
                },
                {"label": "rh7-2"},
                {"label": "rh7-3"},
            ]
        )
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[
                [dict(label=node)] for node in self.node_list[1:]
            ],
        )
        self.config.http.sbd.disable_sbd(node_labels=online_nodes_list)
        disable_sbd(self.env_assist.get_env(), ignore_offline_nodes=True)
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.OMITTING_NODE, node="rh7-1")]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in online_nodes_list
            ]
            + [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_set_stonith_watchdog_timeout_fails_on_some_nodes(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[
                [
                    {
                        "label": "rh7-1",
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": err_msg,
                    }
                ],
                [
                    {
                        "label": "rh7-2",
                        "response_code": 400,
                        "output": "FAILED",
                    }
                ],
                [{"label": "rh7-3"}],
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
                    command="remote/set_stonith_watchdog_timeout_to_zero",
                ),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="rh7-2",
                    reason="FAILED",
                    command="remote/set_stonith_watchdog_timeout_to_zero",
                ),
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.node_list
            ]
            + [
                fixture.warn(
                    report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES
                )
            ]
        )

    def test_set_stonith_watchdog_timeout_fails_on_all_nodes(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
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
                    command="remote/set_stonith_watchdog_timeout_to_zero",
                )
                for node in self.node_list
            ]
            + [
                fixture.error(
                    report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                )
            ]
        )

    def test_disable_failed(self):
        err_msg = "Error"
        self.config.corosync_conf.load(filename=self.corosync_conf_name)
        self.config.runner.cib.load(resources=self.cib_resources)
        self.config.http.host.check_auth(node_labels=self.node_list)
        self.config.http.pcmk.set_stonith_watchdog_timeout_to_zero(
            communication_list=[[dict(label=node)] for node in self.node_list],
        )
        self.config.http.sbd.disable_sbd(
            communication_list=[
                {"label": "rh7-1"},
                {"label": "rh7-2"},
                {"label": "rh7-3", "response_code": 400, "output": err_msg},
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: disable_sbd(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.node_list[:2]
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="rh7-3",
                    reason=err_msg,
                    command="remote/sbd_disable",
                )
            ]
        )
