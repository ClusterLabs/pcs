from textwrap import dedent
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import status
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import read_test_resource as rc_read


class FullClusterStatusPlaintext(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_name_list = ["node1", "node2", "node3"]
        self.maxDiff = None

    @staticmethod
    def _fixture_xml_clustername(name):
        return """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair
                        id="cib-bootstrap-options-cluster-name"
                        name="cluster-name" value="{name}"
                    />
                </cluster_property_set>
            </crm_config>
            """.format(
            name=name
        )

    def _fixture_config_live_minimal(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load()
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )

    def _fixture_config_live_remote_minimal(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=False)
            .runner.cib.load(
                optional_in_conf=self._fixture_xml_clustername("test-cib"),
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
            )
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )

    def _fixture_config_local_daemons(
        self,
        corosync_enabled=True,
        corosync_active=True,
        pacemaker_enabled=True,
        pacemaker_active=True,
        pacemaker_remote_enabled=False,
        pacemaker_remote_active=False,
        pcsd_enabled=True,
        pcsd_active=True,
        sbd_enabled=False,
        sbd_active=False,
    ):
        # pylint: disable=too-many-arguments
        (
            self.config.runner.systemctl.is_enabled(
                "corosync",
                name="runner.systemctl.is_enabled.corosync",
                is_enabled=corosync_enabled,
            )
            .runner.systemctl.is_active(
                "corosync",
                name="runner.systemctl.is_active.corosync",
                is_active=corosync_active,
            )
            .runner.systemctl.is_enabled(
                "pacemaker",
                name="runner.systemctl.is_enabled.pacemaker",
                is_enabled=pacemaker_enabled,
            )
            .runner.systemctl.is_active(
                "pacemaker",
                name="runner.systemctl.is_active.pacemaker",
                is_active=pacemaker_active,
            )
            .runner.systemctl.is_enabled(
                "pacemaker_remote",
                name="runner.systemctl.is_enabled.pacemaker_remote",
                is_enabled=pacemaker_remote_enabled,
            )
            .runner.systemctl.is_active(
                "pacemaker_remote",
                name="runner.systemctl.is_active.pacemaker_remote",
                is_active=pacemaker_remote_active,
            )
            .runner.systemctl.is_enabled(
                "pcsd",
                name="runner.systemctl.is_enabled.pcsd",
                is_enabled=pcsd_enabled,
            )
            .runner.systemctl.is_active(
                "pcsd",
                name="runner.systemctl.is_active.pcsd",
                is_active=pcsd_active,
            )
            .runner.systemctl.is_enabled(
                "sbd",
                name="runner.systemctl.is_enabled.sbd_2",
                is_enabled=sbd_enabled,
            )
            .runner.systemctl.is_active(
                "sbd",
                name="runner.systemctl.is_active.sbd_2",
                is_active=sbd_active,
            )
        )

    def test_life_cib_mocked_corosync(self):
        self.config.env.set_corosync_conf_data("corosync conf data")
        self.env_assist.assert_raise_library_error(
            lambda: status.full_cluster_status_plaintext(
                self.env_assist.get_env()
            ),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                    mocked_files=[file_type_codes.COROSYNC_CONF],
                    required_files=[file_type_codes.CIB],
                ),
            ],
            expected_in_processor=False,
        )

    def test_mocked_cib_life_corosync(self):
        self.config.env.set_cib_data("<cib/>")
        self.env_assist.assert_raise_library_error(
            lambda: status.full_cluster_status_plaintext(
                self.env_assist.get_env()
            ),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
                    mocked_files=[file_type_codes.CIB],
                    required_files=[file_type_codes.COROSYNC_CONF],
                ),
            ],
            expected_in_processor=False,
        )

    def test_fail_getting_cluster_status(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="some stdout",
                stderr="some stderr",
                returncode=1,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: status.full_cluster_status_plaintext(
                self.env_assist.get_env()
            ),
            [
                fixture.error(
                    report_codes.CRM_MON_ERROR,
                    reason="some stderr\nsome stdout",
                ),
            ],
            expected_in_processor=False,
        )

    def test_fail_getting_corosync_conf(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load_content("invalid corosync conf")
        )
        self.env_assist.assert_raise_library_error(
            lambda: status.full_cluster_status_plaintext(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE,
                ),
            ]
        )

    def test_fail_getting_cib(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load()
            .runner.cib.load_content(
                "some stdout", stderr="cib load error", returncode=1
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: status.full_cluster_status_plaintext(
                self.env_assist.get_env()
            ),
            [
                fixture.error(
                    report_codes.CIB_LOAD_ERROR,
                    reason="cib load error",
                ),
            ],
            expected_in_processor=False,
        )

    def test_success_live(self):
        self._fixture_config_live_minimal()
        self._fixture_config_local_daemons()
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_success_live_verbose(self):
        (
            self.config.env.set_known_nodes(self.node_name_list)
            .runner.pcmk.can_fence_history_status(stderr="not supported")
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load(node_name_list=self.node_name_list)
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.pcmk.load_ticket_state_plaintext(stdout="ticket status")
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()
        (
            self.config.http.host.check_reachability(
                node_labels=self.node_name_list
            )
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(), verbose=True
            ),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Tickets:
                  ticket status

                PCSD Status:
                  node1: Online
                  node2: Online
                  node3: Online

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_success_live_remote_node(self):
        self._fixture_config_live_remote_minimal()
        self._fixture_config_local_daemons(
            corosync_enabled=False,
            corosync_active=False,
            pacemaker_enabled=False,
            pacemaker_active=False,
            pacemaker_remote_enabled=True,
            pacemaker_remote_active=True,
        )
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test-cib
                crm_mon cluster status

                Daemon Status:
                  corosync: inactive/disabled
                  pacemaker: inactive/disabled
                  pacemaker_remote: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_success_live_remote_node_verbose(self):
        (
            self.config.runner.pcmk.can_fence_history_status(
                stderr="not supported"
            )
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=False)
            .runner.cib.load(
                optional_in_conf=self._fixture_xml_clustername("test-cib"),
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
            )
            .runner.pcmk.load_ticket_state_plaintext(stdout="ticket status")
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons(
            corosync_enabled=False,
            corosync_active=False,
            pacemaker_enabled=False,
            pacemaker_active=False,
            pacemaker_remote_enabled=True,
            pacemaker_remote_active=True,
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(), verbose=True
            ),
            dedent(
                """\
                Cluster name: test-cib
                crm_mon cluster status

                Tickets:
                  ticket status

                Daemon Status:
                  corosync: inactive/disabled
                  pacemaker: inactive/disabled
                  pacemaker_remote: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_succes_mocked(self):
        (
            self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
            .env.set_cib_data("<cib/>")
            .runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
        )
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status"""
            ),
        )

    def test_succes_mocked_verbose(self):
        (
            self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
            .env.set_cib_data("<cib/>")
            .runner.pcmk.can_fence_history_status(stderr="not supported")
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
            )
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.pcmk.load_ticket_state_plaintext(stdout="ticket status")
        )
        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(), verbose=True
            ),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Tickets:
                  ticket status"""
            ),
        )

    def test_success_verbose_inactive_and_fence_history(self):
        (
            self.config.env.set_known_nodes(self.node_name_list)
            .runner.pcmk.can_fence_history_status()
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                inactive=False,
                fence_history=True,
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load(node_name_list=self.node_name_list)
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.pcmk.load_ticket_state_plaintext(stdout="ticket status")
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()
        (
            self.config.http.host.check_reachability(
                node_labels=self.node_name_list
            )
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(),
                verbose=True,
                hide_inactive_resources=True,
            ),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Tickets:
                  ticket status

                PCSD Status:
                  node1: Online
                  node2: Online
                  node3: Online

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def _assert_success_with_ticket_status_failure(self, stderr="", msg=""):
        (
            self.config.env.set_known_nodes(self.node_name_list)
            .runner.pcmk.can_fence_history_status(stderr="not supported")
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load(node_name_list=self.node_name_list)
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.pcmk.load_ticket_state_plaintext(
                stdout="ticket stdout", stderr=stderr, returncode=1
            )
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()
        (
            self.config.http.host.check_reachability(
                node_labels=self.node_name_list
            )
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(), verbose=True
            ),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Tickets:
                  WARNING: Unable to get information about tickets{msg}

                PCSD Status:
                  node1: Online
                  node2: Online
                  node3: Online

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ).format(msg=msg),
        )

    def test_success_with_ticket_status_failure(self):
        self._assert_success_with_ticket_status_failure()

    def test_success_with_ticket_status_failure_with_message(self):
        self._assert_success_with_ticket_status_failure(
            stderr="ticket status error\nmultiline\n",
            msg="\n    ticket status error\n    multiline",
        )

    def test_stonith_warning_no_devices(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load()
            .runner.cib.load()
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                No stonith devices and stonith-enabled is not false

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_stonith_warning_no_devices_sbd_enabled(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load()
            .runner.cib.load()
            .runner.systemctl.is_active(
                "sbd", is_active=True, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_stonith_warnings_regarding_devices_configuration(self):
        (
            self.config.runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load()
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S1" class="stonith" type="fence_dummy">
                        <instance_attributes>
                            <nvpair name="method" value="cycle" />
                        </instance_attributes>
                    </primitive>
                    <primitive id="S2" class="stonith" type="fence_dummy">
                        <instance_attributes>
                            <nvpair name="action" value="value" />
                            <nvpair name="method" value="not-cycle" />
                        </instance_attributes>
                    </primitive>
                    <primitive id="S3" class="stonith" type="fence_dummy">
                        <instance_attributes>
                            <nvpair name="method" value="cycle" />
                            <nvpair name="action" value="value" />
                        </instance_attributes>
                    </primitive>
                </resources>
            """
            )
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()

        self.assertEqual(
            # pylint: disable=line-too-long
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'S2', 'S3'
                Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'S1', 'S3'

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_pcsd_status_issues(self):
        self.node_name_list = ["node1", "node2", "node3", "node4", "node5"]

        (
            self.config.env.set_known_nodes(self.node_name_list[1:])
            .runner.pcmk.can_fence_history_status(stderr="not supported")
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
            )
            .fs.exists(settings.corosync_conf_file, return_value=True)
            .corosync_conf.load(node_name_list=self.node_name_list)
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
            )
            .runner.pcmk.load_ticket_state_plaintext(stdout="ticket status")
            .runner.systemctl.is_active(
                "sbd", is_active=False, name="runner.systemctl.is_active.sbd"
            )
        )
        self._fixture_config_local_daemons()
        (
            self.config.http.host.check_reachability(
                communication_list=[
                    # node1 has no record in known-hosts
                    dict(
                        label="node2",
                        was_connected=False,
                        errno=7,
                        error_msg="node2 error",
                    ),
                    dict(
                        label="node3",
                        response_code=401,
                        output="node3 output",
                    ),
                    dict(
                        label="node4",
                        response_code=500,
                        output="node4 output",
                    ),
                    dict(
                        label="node5",
                    ),
                ]
            )
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(
                self.env_assist.get_env(), verbose=True
            ),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Tickets:
                  ticket status

                PCSD Status:
                  node1: Unable to authenticate
                  node2: Offline
                  node3: Unable to authenticate
                  node4: Online
                  node5: Online

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_daemon_status_all_on(self):
        self._fixture_config_live_minimal()
        self._fixture_config_local_daemons(
            corosync_enabled=True,
            corosync_active=True,
            pacemaker_enabled=True,
            pacemaker_active=True,
            pacemaker_remote_enabled=True,
            pacemaker_remote_active=True,
            pcsd_enabled=True,
            pcsd_active=True,
            sbd_enabled=True,
            sbd_active=True,
        )
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pacemaker_remote: active/enabled
                  pcsd: active/enabled
                  sbd: active/enabled"""
            ),
        )

    def test_daemon_status_all_off(self):
        self._fixture_config_live_minimal()
        self._fixture_config_local_daemons(
            corosync_enabled=False,
            corosync_active=False,
            pacemaker_enabled=False,
            pacemaker_active=False,
            pacemaker_remote_enabled=False,
            pacemaker_remote_active=False,
            pcsd_enabled=False,
            pcsd_active=False,
            sbd_enabled=False,
            sbd_active=False,
        )
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status

                Daemon Status:
                  corosync: inactive/disabled
                  pacemaker: inactive/disabled
                  pcsd: inactive/disabled"""
            ),
        )
