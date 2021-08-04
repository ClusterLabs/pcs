from textwrap import dedent
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import status
from pcs.lib.errors import LibraryError
from pcs_test.tools import fixture, fixture_crm_mon
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import read_test_resource as rc_read


class PacemakerStatusXml(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success(self):
        self.config.runner.pcmk.load_state(filename="crm_mon.minimal.xml")
        assert_xml_equal(
            status.pacemaker_status_xml(self.env_assist.get_env()),
            rc_read("crm_mon.minimal.xml"),
        )

    def test_not_xml(self):
        # Loading pacemaker state succeeded, we expect to get an xml and we
        # just return it. If it is not a valid xml, it is a bug in pacemaker.
        self.config.runner.pcmk.load_state(stdout="not an xml")
        self.assertEqual(
            status.pacemaker_status_xml(self.env_assist.get_env()), "not an xml"
        )

    def test_error(self):
        error_xml = fixture_crm_mon.error_xml(
            1, "an error", ["This is an error message", "And one more"]
        )
        self.config.runner.pcmk.load_state(stdout=error_xml, returncode=1)
        with self.assertRaises(LibraryError) as cm:
            status.pacemaker_status_xml(self.env_assist.get_env())
        assert_xml_equal(cm.exception.output, error_xml)

    def test_error_not_xml(self):
        # Loading pacemaker state failed, but we expect to get an xml anyway
        # and we return it. If it is not a valid xml, it is a bug or a critical
        # error in pacemaker we can do nothing about.
        self.config.runner.pcmk.load_state(stdout="an error", returncode=1)
        with self.assertRaises(LibraryError) as cm:
            status.pacemaker_status_xml(self.env_assist.get_env())
        self.assertEqual(cm.exception.output, "an error")


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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            self.config.services.is_enabled(
                "corosync",
                name="services.is_enabled.corosync",
                return_value=corosync_enabled,
            )
            .services.is_running(
                "corosync",
                name="services.is_running.corosync",
                return_value=corosync_active,
            )
            .services.is_enabled(
                "pacemaker",
                name="services.is_enabled.pacemaker",
                return_value=pacemaker_enabled,
            )
            .services.is_running(
                "pacemaker",
                name="services.is_running.pacemaker",
                return_value=pacemaker_active,
            )
            .services.is_enabled(
                "pacemaker_remote",
                name="services.is_enabled.pacemaker_remote",
                return_value=pacemaker_remote_enabled,
            )
            .services.is_running(
                "pacemaker_remote",
                name="services.is_running.pacemaker_remote",
                return_value=pacemaker_remote_active,
            )
            .services.is_enabled(
                "pcsd",
                name="services.is_enabled.pcsd",
                return_value=pcsd_enabled,
            )
            .services.is_running(
                "pcsd",
                name="services.is_running.pcsd",
                return_value=pcsd_active,
            )
            .services.is_enabled(
                "sbd",
                name="services.is_enabled.sbd_2",
                return_value=sbd_enabled,
            )
            .services.is_running(
                "sbd",
                name="services.is_running.sbd_2",
                return_value=sbd_active,
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        (
            self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
            .env.set_cib_data("<cib/>", cib_tempfile=tmp_file)
            .runner.pcmk.load_state_plaintext(
                stdout="crm_mon cluster status",
                env=env,
            )
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
                env=env,
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
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        (
            self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
            .env.set_cib_data("<cib/>", cib_tempfile=tmp_file)
            .runner.pcmk.can_fence_history_status(
                stderr="not supported",
                env=env,
            )
            .runner.pcmk.load_state_plaintext(
                verbose=True,
                stdout="crm_mon cluster status",
                env=env,
            )
            .runner.cib.load(
                resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
                env=env,
            )
            .runner.pcmk.load_ticket_state_plaintext(
                stdout="ticket status", env=env
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=True, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
            .services.is_running(
                "sbd", return_value=False, name="services.is_running.sbd"
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
