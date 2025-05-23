# pylint: disable=too-many-lines
import os
from textwrap import dedent
from typing import Optional
from unittest import TestCase, mock

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.const import (
    PCMK_ROLE_STOPPED,
    PCMK_STATUS_ROLE_STOPPED,
    PcmkRoleType,
)
from pcs.common.reports import codes as report_codes
from pcs.common.status_dto import (
    BundleReplicaStatusDto,
    BundleStatusDto,
    CloneStatusDto,
    GroupStatusDto,
    PrimitiveStatusDto,
    ResourcesStatusDto,
)
from pcs.lib.booth import constants
from pcs.lib.commands import status
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture, fixture_crm_mon
from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_runner_pcmk import (
    RULE_EXPIRED_RETURNCODE,
    RULE_IN_EFFECT_RETURNCODE,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import read_test_resource as rc_read

EXITCODE_INVALID_CIB = 78


def _booth_config_path_fixture(instance_name="booth"):
    return os.path.join(settings.booth_config_dir, f"{instance_name}.conf")


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


class FullClusterStatusPlaintextBase(TestCase):
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
            """.format(name=name)

    @staticmethod
    def _fixture_crm_verify_success():
        return """
            <pacemaker-result api-version="2.38"
                request="crm_verify --live-check --output-as=xml"
            >
                <status code="0" message="OK"/>
            </pacemaker-result>
        """

    @staticmethod
    def _fixture_crm_verify_invalid_cib(error_list):
        errors = "\n".join(f"<error>{error}</error>" for error in error_list)
        return f"""
            <pacemaker-result api-version="2.38"
                request="crm_verify --live-check --output-as=xml"
            >
                <status code="{EXITCODE_INVALID_CIB}"
                    message="Invalid configuration"
                >
                    <errors>{errors}</errors>
                </status>
            </pacemaker-result>
        """

    def _fixture_config_crm_verify(
        self, stdout, stderr="", retval=0, cib_file=None
    ):
        self.config.runner.pcmk.verify_xml(
            cib_tempfile=cib_file,
            stdout=stdout,
            stderr=stderr,
            returncode=retval,
            env=({"CIB_file": cib_file} if cib_file else None),
        )
        self.config.fs.isfile(
            settings.pacemaker_api_result_schema,
            name="fs.exists.crm_verify_xml_schema",
        )

    def _fixture_config_live_minimal(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )

    def _fixture_config_live_remote_minimal(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=False)
        self.config.runner.cib.load(
            optional_in_conf=self._fixture_xml_clustername("test-cib"),
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )

    def _fixture_config_local_daemons(  # noqa: PLR0913
        self,
        *,
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
        self.config.services.is_enabled(
            "corosync",
            name="services.is_enabled.corosync",
            return_value=corosync_enabled,
        )
        self.config.services.is_running(
            "corosync",
            name="services.is_running.corosync",
            return_value=corosync_active,
        )
        self.config.services.is_enabled(
            "pacemaker",
            name="services.is_enabled.pacemaker",
            return_value=pacemaker_enabled,
        )
        self.config.services.is_running(
            "pacemaker",
            name="services.is_running.pacemaker",
            return_value=pacemaker_active,
        )
        self.config.services.is_enabled(
            "pacemaker_remote",
            name="services.is_enabled.pacemaker_remote",
            return_value=pacemaker_remote_enabled,
        )
        self.config.services.is_running(
            "pacemaker_remote",
            name="services.is_running.pacemaker_remote",
            return_value=pacemaker_remote_active,
        )
        self.config.services.is_enabled(
            "pcsd",
            name="services.is_enabled.pcsd",
            return_value=pcsd_enabled,
        )
        self.config.services.is_running(
            "pcsd",
            name="services.is_running.pcsd",
            return_value=pcsd_active,
        )
        self.config.services.is_enabled(
            "sbd",
            name="services.is_enabled.sbd_2",
            return_value=sbd_enabled,
        )
        self.config.services.is_running(
            "sbd",
            name="services.is_running.sbd_2",
            return_value=sbd_active,
        )


@mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
@mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class FullClusterStatusPlaintext(FullClusterStatusPlaintextBase):
    # pylint: disable=too-many-public-methods
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
        self.config.runner.pcmk.load_state_plaintext(
            stdout="some stdout", stderr="some stderr", returncode=1
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
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load_content("invalid corosync conf")

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
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load_content(
            "some stdout", stderr="cib load error", returncode=1
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
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.env.set_known_nodes(self.node_name_list)
        self.config.runner.pcmk.can_fence_history_status(stderr="not supported")
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True, stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load(node_name_list=self.node_name_list)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket status"
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.http.host.check_reachability(
            node_labels=self.node_name_list
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.runner.pcmk.can_fence_history_status(stderr="not supported")
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True, stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=False)
        self.config.runner.cib.load(
            optional_in_conf=self._fixture_xml_clustername("test-cib"),
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket status"
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons(
            corosync_enabled=False,
            corosync_active=False,
            pacemaker_enabled=False,
            pacemaker_active=False,
            pacemaker_remote_enabled=True,
            pacemaker_remote_active=True,
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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

    def test_success_mocked(self):
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
        self.config.env.set_cib_data("<cib/>", cib_tempfile=tmp_file)
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status", env=env
        )
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
            env=env,
        )
        self._fixture_config_crm_verify(
            self._fixture_crm_verify_success(), cib_file=tmp_file
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99
                crm_mon cluster status"""
            ),
        )

    def test_success_mocked_verbose(self):
        tmp_file = "/fake/tmp_file"
        env = dict(CIB_file=tmp_file)
        self.config.env.set_corosync_conf_data(rc_read("corosync.conf"))
        self.config.env.set_cib_data("<cib/>", cib_tempfile=tmp_file)
        self.config.runner.pcmk.can_fence_history_status(
            stderr="not supported", env=env
        )
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True, stdout="crm_mon cluster status", env=env
        )
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """,
            env=env,
        )
        self._fixture_config_crm_verify(
            self._fixture_crm_verify_success(), cib_file=tmp_file
        )
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket status", env=env
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
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
        self.config.env.set_known_nodes(self.node_name_list)
        self.config.runner.pcmk.can_fence_history_status()
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True,
            inactive=False,
            fence_history=True,
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load(node_name_list=self.node_name_list)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket status"
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.http.host.check_reachability(
            node_labels=self.node_name_list
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.env.set_known_nodes(self.node_name_list)
        self.config.runner.pcmk.can_fence_history_status(stderr="not supported")
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True, stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load(node_name_list=self.node_name_list)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket stdout", stderr=stderr, returncode=1
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.http.host.check_reachability(
            node_labels=self.node_name_list
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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

    def test_crm_verify_messages(self):
        errors = [
            "error: Resource chr:0 is of type systemd and therefore cannot be used as a promotable clone resource",
            "error: Ignoring &lt;clone&gt; resource 'chr-clone' because configuration is invalid",
            "error: CIB did not pass schema validation",
            "Configuration invalid (with errors)",
        ]
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(
            self._fixture_crm_verify_invalid_cib(errors),
            retval=EXITCODE_INVALID_CIB,
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                error: Resource chr:0 is of type systemd and therefore cannot be used as a promotable clone resource
                error: Ignoring <clone> resource 'chr-clone' because configuration is invalid
                error: CIB did not pass schema validation
                Configuration invalid (with errors)

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ),
        )

    def test_crm_verify_error(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self.config.runner.pcmk.verify_xml(
            stdout="not a xml", stderr="some message"
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.env_assist.assert_reports(
            [
                fixture.debug(
                    report_codes.BAD_PCMK_API_RESPONSE_FORMAT,
                    reason=(
                        "Start tag expected, '<' not found, line 1, column 1 "
                        "(<string>, line 1)"
                    ),
                    api_response="some message\nnot a xml",
                )
            ]
        )

    def test_stonith_warning_no_devices(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load()
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load()
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=True, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
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
                    <primitive id="S4" class="stonith" type="fence_sbd">
                        <instance_attributes>
                            <nvpair name="method" value="cycle" />
                        </instance_attributes>
                    </primitive>
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

        self.assertEqual(
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
        self.config.env.set_known_nodes(self.node_name_list[1:])
        self.config.runner.pcmk.can_fence_history_status(stderr="not supported")
        self.config.runner.pcmk.load_state_plaintext(
            verbose=True, stdout="crm_mon cluster status"
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load(node_name_list=self.node_name_list)
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="S" class="stonith" type="fence_dummy" />
                </resources>
            """
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.runner.pcmk.load_ticket_state_plaintext(
            stdout="ticket status"
        )
        self.config.services.is_running(
            "sbd", return_value=False, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons()
        self.config.http.host.check_reachability(
            communication_list=[
                # node1 has no record in known-hosts
                dict(
                    label="node2",
                    was_connected=False,
                    errno=7,
                    error_msg="node2 error",
                ),
                dict(label="node3", response_code=401, output="node3 output"),
                dict(label="node4", response_code=500, output="node4 output"),
                dict(label="node5"),
            ]
        )
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

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
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
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
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
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

    def test_move_constrains_warnings(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            constraints="""
            <constraints>
                <rsc_location id="cli-ban-P1-on-node1" rsc="P1"
                    role="Started" node="node1" score="-INFINITY"/>
                <rsc_location id="cli-prefer-P1" rsc="P1" role="Started"
                    node="node3" score="INFINITY"/>
                <rsc_location id="cli-prefer-P2" rsc="P2" role="Started"
                    node="node1" score="INFINITY"/>
                <rsc_location id="cli-ban-P2-on-node1" rsc="P2"
                    role="Started" node="node1" score="-INFINITY"/>
                <rsc_location id="location-P3-node3--INFINITY" rsc="P3"
                    node="node3" score="-INFINITY"/>
            </constraints>
            """,
            resources="""
            <resources>
                <primitive class="ocf" id="P1" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P2" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P3" provider="pacemaker"
                    type="Dummy"/>
            </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=True, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons(sbd_enabled=True, sbd_active=True)
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                Following resources have been moved and their move constraints are still in place: 'P1', 'P2'
                Run 'pcs constraint location' or 'pcs resource clear <resource id>' to view or remove the constraints, respectively

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled
                  sbd: active/enabled"""
            ),
        )

    def test_expired_move_constraints_warnings(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            constraints="""
            <constraints>
                <rsc_location id="cli-ban-P1-on-node1" rsc="P1"
                    role="Started" node="node1" score="-INFINITY"/>
                <rsc_location id="cli-prefer-P2" rsc="P2" role="Started"
                    node="node1" score="INFINITY">
                    <rule id="cli-prefer-rule-P2" score="INFINITY" boolean-op="and">
                        <expression id="cli-prefer-expr-P2" attribute="#uname"
                                    operation="eq" value="P2" type="string"/>
                        <date_expression id="cli-prefer-lifetime-end-P2"
                                    operation="lt" end="0000-01-1 01:00:00 +02:00"/>
                    </rule>
                </rsc_location>
            </constraints>
            """,
            resources="""
            <resources>
                <primitive class="ocf" id="P1" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P2" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P3" provider="pacemaker"
                    type="Dummy"/>
            </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=True, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons(sbd_enabled=True, sbd_active=True)
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.runner.pcmk.get_rule_in_effect_status(
            "cli-prefer-rule-P2", returncode=RULE_EXPIRED_RETURNCODE
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                Following resources have been moved and their move constraints are still in place: 'P1'
                Run 'pcs constraint location' or 'pcs resource clear <resource id>' to view or remove the constraints, respectively

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled
                  sbd: active/enabled"""
            ),
        )

    def test_expired_and_in_effect_move_constraints_warnings(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            constraints="""
            <constraints>
                <rsc_location id="cli-prefer-P1" rsc="P1" role="Started"
                    node="node1" score="INFINITY">
                    <rule id="cli-prefer-rule-P1" score="INFINITY" boolean-op="and">
                        <expression id="cli-prefer-expr-P1" attribute="#uname"
                                    operation="eq" value="P1" type="string"/>
                        <date_expression id="cli-prefer-lifetime-end-P1"
                                    operation="lt" end="0000-01-1 01:00:00 +02:00"/>
                    </rule>
                </rsc_location>
                <rsc_location id="cli-prefer-P2" rsc="P2" role="Started"
                    node="node2" score="INFINITY">
                    <rule id="cli-prefer-rule-P2" score="INFINITY" boolean-op="and">
                        <expression id="cli-prefer-expr-P2" attribute="#uname"
                                    operation="eq" value="P2" type="string"/>
                        <date_expression id="cli-prefer-lifetime-end-P2"
                                    operation="lt" end="0000-01-1 01:00:00 +02:00"/>
                    </rule>
                </rsc_location>
            </constraints>
            """,
            resources="""
            <resources>
                <primitive class="ocf" id="P1" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P2" provider="pacemaker"
                    type="Dummy"/>
                <primitive class="ocf" id="P3" provider="pacemaker"
                    type="Dummy"/>
            </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=True, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons(sbd_enabled=True, sbd_active=True)
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.runner.pcmk.get_rule_in_effect_status(
            "cli-prefer-rule-P1",
            returncode=RULE_EXPIRED_RETURNCODE,
            name="runner.pcmk.get_rule_in_effect_status-1",
        )
        self.config.runner.pcmk.get_rule_in_effect_status(
            "cli-prefer-rule-P2",
            returncode=RULE_IN_EFFECT_RETURNCODE,
            name="runner.pcmk.get_rule_in_effect_status-2",
        )

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                Following resources have been moved and their move constraints are still in place: 'P2'
                Run 'pcs constraint location' or 'pcs resource clear <resource id>' to view or remove the constraints, respectively

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled
                  sbd: active/enabled"""
            ),
        )

    def test_bundle_warnings(self):
        self.config.runner.pcmk.load_state_plaintext(
            stdout="crm_mon cluster status",
        )
        self.config.fs.exists(settings.corosync_conf_file, return_value=True)
        self.config.corosync_conf.load()
        self.config.runner.cib.load(
            resources="""
            <resources>
                <bundle id="bundle-bad">
                    <rkt image="pcs:test" />
                </bundle>
                <bundle id="bundle-good">
                    <docker image="pcs:test" />
                </bundle>
            </resources>
            """,
        )
        self._fixture_config_crm_verify(self._fixture_crm_verify_success())
        self.config.services.is_running(
            "sbd", return_value=True, name="services.is_running.sbd"
        )
        self._fixture_config_local_daemons(sbd_enabled=True, sbd_active=True)
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)

        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99

                WARNINGS:
                Bundle 'bundle-bad' uses unsupported container type. Supported container types are: 'docker', 'podman'

                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled
                  sbd: active/enabled"""
            ),
        )


class FullClusterStatusPlaintextBoothWarning(FullClusterStatusPlaintextBase):
    def setUp(self):
        super().setUp()
        self.settings_patcher = mock.patch(
            "pcs.settings.pacemaker_api_result_schema",
            rc("pcmk_api_rng/api-result.rng"),
        )
        self.settings_patcher.start()
        self._fixture_config_live_minimal()
        self._fixture_config_local_daemons()

    def tearDown(self):
        self.settings_patcher.stop()

    def _assert_status_output(self, warning=None):
        warning_str = ""
        if warning:
            warning_str = f"\n\nWARNINGS:\n{warning}\n"
        self.assertEqual(
            status.full_cluster_status_plaintext(self.env_assist.get_env()),
            dedent(
                """\
                Cluster name: test99{warning_str}
                crm_mon cluster status

                Daemon Status:
                  corosync: active/enabled
                  pacemaker: active/enabled
                  pcsd: active/enabled"""
            ).format(warning_str=warning_str),
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_booth_not_configured_set_enabled(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=False,
        )
        self._assert_status_output()

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_booth_authfile_not_configured_set_enabled(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=True,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            content=dedent(
                """
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self._assert_status_output()

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_booth_not_configured_unset_enabled(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=False,
        )
        self._assert_status_output()

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_missing_option(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=True,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            content=dedent(
                f"""
                authfile = {_booth_config_path_fixture()}
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self._assert_status_output(
            "Booth is configured to use an authfile, but authfile is not "
            "enabled. Run 'pcs booth enable-authfile --name booth' to enable "
            "usage of booth autfile."
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", True)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", False)
    def test_properly_configured(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=True,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            content=dedent(
                f"""
                authfile = {_booth_config_path_fixture()}
                {constants.AUTHFILE_FIX_OPTION} = yes
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self._assert_status_output()

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_unsupported_option(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=True,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            content=dedent(
                f"""
                authfile = {_booth_config_path_fixture()}
                {constants.AUTHFILE_FIX_OPTION} = yes
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self._assert_status_output(
            "Unsupported option 'enable-authfile' is set in booth "
            "configuration. Run 'pcs booth enable-booth-clean --name booth' to "
            "remove the option."
        )

    @mock.patch("pcs.settings.booth_enable_authfile_set_enabled", False)
    @mock.patch("pcs.settings.booth_enable_authfile_unset_enabled", True)
    def test_unsupported_option_not_present(self):
        self.config.fs.isfile(settings.crm_rule_exec, return_value=True)
        self.config.raw_file.exists(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            exists=True,
        )
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            _booth_config_path_fixture(),
            content=dedent(
                f"""
                authfile = {_booth_config_path_fixture()}
                site = 1.1.1.1
                """
            ).encode("utf-8"),
        )
        self._assert_status_output()


def _fixture_primitive_resource_dto(
    resource_id: str,
    resource_agent: str,
    target_role: Optional[PcmkRoleType] = None,
    managed: bool = True,
) -> PrimitiveStatusDto:
    return PrimitiveStatusDto(
        resource_id=resource_id,
        instance_id=None,
        resource_agent=resource_agent,
        role=PCMK_STATUS_ROLE_STOPPED,
        target_role=target_role,
        active=False,
        orphaned=False,
        blocked=False,
        maintenance=False,
        description=None,
        failed=False,
        managed=managed,
        failure_ignored=False,
        node_names=[],
        pending=None,
        locked_to=None,
    )


@mock.patch.object(
    settings,
    "pacemaker_api_result_schema",
    rc("pcmk_api_rng/api-result.rng"),
)
class ResourcesStatus(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_empty_resources(self):
        self.config.runner.pcmk.load_state()

        result = status.resources_status(self.env_assist.get_env())
        self.assertEqual(result, ResourcesStatusDto([]))

    def test_bad_xml_format(self):
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource />
                </resources>
            """,
        )

        self.env_assist.assert_raise_library_error(
            lambda: status.resources_status(
                self.env_assist.get_env(),
            ),
            [fixture.error(report_codes.BAD_CLUSTER_STATE_FORMAT)],
            False,
        )

    def test_bad_xml(self):
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <resource id="R7" resource_agent="ocf:pacemaker:Dummy"
                        role="NotPcmkRole" active="false" orphaned="false"
                        blocked="false" maintenance="false" managed="true"
                        failed="false" failure_ignored="false"
                        nodes_running_on="0"
                    />
                </resources>
            """,
        )

        self.env_assist.assert_raise_library_error(
            lambda: status.resources_status(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.BAD_CLUSTER_STATE_DATA,
                    reason="Resource 'R7' contains an unknown role 'NotPcmkRole'",
                )
            ],
            False,
        )

    def test_all_resources(self):
        self.config.runner.pcmk.load_state(
            filename=rc("crm_mon.all_resources.xml")
        )

        result = status.resources_status(self.env_assist.get_env())

        self.assertEqual(
            result,
            ResourcesStatusDto(
                [
                    BundleStatusDto(
                        resource_id="B1",
                        type="docker",
                        image="pcs:test",
                        unique=True,
                        maintenance=False,
                        description=None,
                        managed=False,
                        failed=False,
                        replicas=[
                            BundleReplicaStatusDto(
                                replica_id="0",
                                member=None,
                                remote=None,
                                container=_fixture_primitive_resource_dto(
                                    "B1-docker-0",
                                    "ocf:heartbeat:docker",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                                ip_address=_fixture_primitive_resource_dto(
                                    "B1-ip-192.168.100.200",
                                    "ocf:heartbeat:IPaddr2",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                            ),
                            BundleReplicaStatusDto(
                                replica_id="1",
                                member=None,
                                remote=None,
                                container=_fixture_primitive_resource_dto(
                                    "B1-docker-1",
                                    "ocf:heartbeat:docker",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                                ip_address=_fixture_primitive_resource_dto(
                                    "B1-ip-192.168.100.201",
                                    "ocf:heartbeat:IPaddr2",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                            ),
                            BundleReplicaStatusDto(
                                replica_id="2",
                                member=None,
                                remote=None,
                                container=_fixture_primitive_resource_dto(
                                    "B1-docker-2",
                                    "ocf:heartbeat:docker",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                                ip_address=_fixture_primitive_resource_dto(
                                    "B1-ip-192.168.100.202",
                                    "ocf:heartbeat:IPaddr2",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                            ),
                            BundleReplicaStatusDto(
                                replica_id="3",
                                member=None,
                                remote=None,
                                container=_fixture_primitive_resource_dto(
                                    "B1-docker-3",
                                    "ocf:heartbeat:docker",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                                ip_address=_fixture_primitive_resource_dto(
                                    "B1-ip-192.168.100.203",
                                    "ocf:heartbeat:IPaddr2",
                                    target_role=PCMK_ROLE_STOPPED,
                                    managed=False,
                                ),
                            ),
                        ],
                    ),
                    _fixture_primitive_resource_dto(
                        "R7", "ocf:pacemaker:Dummy"
                    ),
                    _fixture_primitive_resource_dto(
                        "S2", "stonith:fence_kdump"
                    ),
                    GroupStatusDto(
                        resource_id="G2",
                        instance_id=None,
                        maintenance=False,
                        description=None,
                        managed=True,
                        disabled=False,
                        members=[
                            _fixture_primitive_resource_dto(
                                "R5", "ocf:pacemaker:Dummy"
                            ),
                            _fixture_primitive_resource_dto(
                                "S1", "stonith:fence_kdump"
                            ),
                        ],
                    ),
                    CloneStatusDto(
                        resource_id="G1-clone",
                        multi_state=True,
                        unique=False,
                        maintenance=False,
                        description=None,
                        managed=True,
                        disabled=False,
                        failed=False,
                        failure_ignored=False,
                        target_role=None,
                        instances=[
                            GroupStatusDto(
                                resource_id="G1",
                                instance_id="0",
                                maintenance=False,
                                description=None,
                                managed=True,
                                disabled=False,
                                members=[
                                    _fixture_primitive_resource_dto(
                                        "R2", "ocf:pacemaker:Stateful"
                                    ),
                                    _fixture_primitive_resource_dto(
                                        "R3", "ocf:pacemaker:Stateful"
                                    ),
                                    _fixture_primitive_resource_dto(
                                        "R4", "ocf:pacemaker:Stateful"
                                    ),
                                ],
                            )
                        ],
                    ),
                    CloneStatusDto(
                        resource_id="R6-clone",
                        multi_state=False,
                        unique=False,
                        maintenance=False,
                        description=None,
                        managed=True,
                        disabled=False,
                        failed=False,
                        failure_ignored=False,
                        target_role=None,
                        instances=[
                            _fixture_primitive_resource_dto(
                                "R6", "ocf:pacemaker:Dummy"
                            )
                        ],
                    ),
                ]
            ),
        )

    def test_bundle_skip(self):
        self.config.runner.pcmk.load_state(
            resources="""
                <resources>
                    <bundle id="B1" type="docker" image="pcs:test" unique="true"
                        maintenance="false" managed="false" failed="false"
                    >
                        <replica id="0">
                            <resource id="B1-0"
                                resource_agent="ocf:heartbeat:Dummy"
                                role="Stopped" target_role="Stopped"
                                active="false" orphaned="false" blocked="false"
                                maintenance="false" managed="true" failed="false"
                                failure_ignored="false" nodes_running_on="0"
                            />
                            <resource id="B1-docker-0"
                                resource_agent="ocf:heartbeat:docker"
                                role="Stopped" target_role="Stopped"
                                active="false" orphaned="false" blocked="false"
                                maintenance="false" managed="false" failed="false"
                                failure_ignored="false" nodes_running_on="0"
                            />
                            <resource id="B1-0"
                                resource_agent="ocf:pacemaker:remote"
                                role="Stopped" target_role="Stopped"
                                active="false" orphaned="false" blocked="false"
                                maintenance="false" managed="false" failed="false"
                                failure_ignored="false" nodes_running_on="0"
                            />
                        </replica>
                    </bundle>
                </resources>
            """,
        )

        result = status.resources_status(self.env_assist.get_env())
        self.assertEqual(result, ResourcesStatusDto([]))
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CLUSTER_STATUS_BUNDLE_MEMBER_ID_AS_IMPLICIT,
                    bundle_id="B1",
                    bad_ids=["B1-0"],
                )
            ]
        )
