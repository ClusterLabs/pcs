# pylint: disable=line-too-long
import re
from textwrap import dedent
from unittest import TestCase

from pcs import settings

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    is_minimum_pacemaker_version,
    is_pacemaker_21_without_20_compatibility,
    outdent,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)


class StonithWarningTest(TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")
    corosync_conf = rc("corosync.conf")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier0_statust_stonith_warning")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_stonith_action(self):
        self.assert_pcs_success(
            (
                "stonith create Sa fence_apc ip=i username=u action=reboot "
                "--force"
            ).split(),
            "Warning: stonith option 'action' is deprecated and should not be "
            "used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
        )

    def fixture_stonith_cycle(self):
        self.assert_pcs_success(
            "stonith create Sc fence_ipmilan method=cycle".split()
        )

    def fixture_resource(self):
        self.assert_pcs_success(
            (
                "resource create dummy ocf:pacemaker:Dummy action=reboot "
                "method=cycle --force"
            ).split(),
            "Warning: invalid resource options: 'action', 'method', allowed "
            "options are: 'envfile', 'fail_start_on', 'fake', 'op_sleep', "
            "'passwd', 'state', 'trace_file', 'trace_ra'\n",
        )

    def test_warning_stonith_action(self):
        self.fixture_stonith_action()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'

                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'

                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )

    def test_warning_stonith_method_cycle(self):
        self.fixture_stonith_cycle()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )

    def test_stonith_warnings(self):
        self.fixture_stonith_action()
        self.fixture_stonith_cycle()
        self.fixture_resource()
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    Following stonith devices have the 'action' option set, it is recommended to set 'pcmk_off_action', 'pcmk_reboot_action' instead: 'Sa'
                    Following stonith devices have the 'method' option set to 'cycle' which is potentially dangerous, please consider using 'onoff': 'Sc'

                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )

    def test_warn_when_no_stonith(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    No stonith devices and stonith-enabled is not false

                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    WARNINGS:
                    No stonith devices and stonith-enabled is not false

                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )

    def test_no_stonith_warning_when_stonith_in_group(self):
        self.assert_pcs_success(
            "stonith create S fence_xvm --group G".split(),
            (
                "Deprecation Warning: Option to group stonith resource is "
                "deprecated and will be removed in a future release.\n"
            ),
        )
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99
                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99

                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )

    def test_disabled_stonith_does_not_care_about_missing_devices(self):
        self.assert_pcs_success("property set stonith-enabled=false".split())
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99
                    Cluster Summary:
                """
                ),
            )
        else:
            self.assert_pcs_success(
                ["status"],
                stdout_start=dedent(
                    """\
                    Cluster name: test99
                    Stack: unknown
                    Current DC: NONE
                """
                ),
            )


class ResourceStonithStatusBase(AssertPcsMixin):
    # pylint: disable=too-many-public-methods
    command = None
    no_resources_msg = None
    all_resources_output = None
    active_resources_output = None
    active_resources_output_node = None
    node_output = None
    cib_file = rc("cib-tags.xml")
    corosync_conf = rc("corosync.conf")
    no_active_resources_msg = "No active resources\n"

    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_status_resource_stonith_status")
        write_file_to_tmpfile(self.cib_file, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()

    def test_not_resource_or_tag_id(self):
        self.assert_pcs_fail(
            self.command + ["cx1"],
            stdout_full="Error: resource or tag id 'cx1' not found\n",
        )

    def test_nonexistent_id(self):
        self.assert_pcs_fail(
            self.command + ["nonexistent"],
            stdout_full="Error: resource or tag id 'nonexistent' not found\n",
        )

    def test_missing_node_value(self):
        self.assert_pcs_fail(
            self.command + ["node="],
            stdout_full="Error: missing value of 'node' option\n",
        )

    def test_missing_node_key(self):
        self.assert_pcs_fail(
            self.command + ["=node"],
            stdout_full="Error: missing key in '=node' option\n",
        )

    def test_more_node_options(self):
        self.assert_pcs_fail(
            self.command + ["node=rh-1", "node=rh-2"],
            stdout_full=(
                "Error: duplicate option 'node' with different values 'rh-1' "
                "and 'rh-2'\n"
            ),
        )

    def test_more_no_node_option(self):
        self.assert_pcs_fail(
            self.command + ["r1", "r2"],
            stdout_full="Error: missing value of 'r2' option\n",
        )

    def test_resource_id(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = "  * x1	(ocf:pacemaker:Dummy):	 Started rh-1\n"
        else:
            stdout_full = "  * x1	(ocf::pacemaker:Dummy):	 Started rh-1\n"
        self.assert_pcs_success(
            self.command + ["x1"],
            stdout_full=stdout_full,
        )

    def test_resource_id_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["x2", "--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_resource_id_with_node_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["x2", "node=rh-1", "--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_resource_id_with_node_started(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = "  * x1	(ocf:pacemaker:Dummy):	 Started rh-1\n"
        else:
            stdout_full = "  * x1	(ocf::pacemaker:Dummy):	 Started rh-1\n"
        self.assert_pcs_success(
            self.command + ["x1", "node=rh-1"],
            stdout_full=stdout_full,
        )

    def test_resource_id_with_node_stopped(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = "  * x2	(ocf:pacemaker:Dummy):	 Stopped\n"
        else:
            stdout_full = "  * x2	(ocf::pacemaker:Dummy):	 Stopped\n"
        self.assert_pcs_success(
            self.command + ["x2", "node=rh-1"],
            stdout_full=stdout_full,
        )

    def test_resource_id_with_node_without_status(self):
        self.assert_pcs_success(
            self.command + ["x1", "node=rh-2"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_resource_id_with_node_changed_arg_order(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = "  * x1	(ocf:pacemaker:Dummy):	 Started rh-1\n"
        else:
            stdout_full = "  * x1	(ocf::pacemaker:Dummy):	 Started rh-1\n"
        self.assert_pcs_success(
            self.command + ["node=rh-1", "x1"],
            stdout_full=stdout_full,
        )

    def test_stonith_id(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-1"],
            stdout_full="  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1\n",
        )

    def test_stonith_id_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-2", "--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_stonith_id_with_node_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-2", "node=rh-2", "--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_stonith_id_with_node_started(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-1", "node=rh-1"],
            stdout_full="  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1\n",
        )

    def test_stonith_id_with_node_stopped(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-2", "node=rh-2"],
            stdout_full="  * fence-rh-2	(stonith:fence_xvm):	 Stopped\n",
        )

    def test_stonith_id_with_node_without_status(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-1", "node=rh-2"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_tag_id(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = outdent(
                """\
                  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
                  * fence-rh-2	(stonith:fence_xvm):	 Stopped
                  * x3	(ocf:pacemaker:Dummy):	 Stopped
                  * y1	(ocf:pacemaker:Dummy):	 Stopped
                """
            )
        else:
            stdout_full = outdent(
                """\
                  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
                  * fence-rh-2	(stonith:fence_xvm):	 Stopped
                  * x3	(ocf::pacemaker:Dummy):	 Stopped
                  * y1	(ocf::pacemaker:Dummy):	 Stopped
                """
            )
        self.assert_pcs_success(
            self.command + ["tag-mixed-stonith-devices-and-resources"],
            stdout_full=stdout_full,
        )

    def test_tag_id_hide_inactive(self):
        self.assert_pcs_success(
            self.command
            + ["tag-mixed-stonith-devices-and-resources", "--hide-inactive"],
            stdout_full=outdent(
                """\
                  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
                """
            ),
        )

    def test_tag_id_with_node(self):
        if is_pacemaker_21_without_20_compatibility():
            stdout_full = outdent(
                """\
                  * fence-rh-2	(stonith:fence_xvm):	 Stopped
                  * x3	(ocf:pacemaker:Dummy):	 Stopped
                  * y1	(ocf:pacemaker:Dummy):	 Stopped
                """
            )
        else:
            stdout_full = outdent(
                """\
                  * fence-rh-2	(stonith:fence_xvm):	 Stopped
                  * x3	(ocf::pacemaker:Dummy):	 Stopped
                  * y1	(ocf::pacemaker:Dummy):	 Stopped
                """
            )
        self.assert_pcs_success(
            self.command
            + ["tag-mixed-stonith-devices-and-resources", "node=rh-2"],
            stdout_full=stdout_full,
        )

    def test_tag_id_with_node_hide_inactive(self):
        self.assert_pcs_success(
            self.command
            + [
                "tag-mixed-stonith-devices-and-resources",
                "node=rh-1",
                "--hide-inactive",
            ],
            stdout_full=outdent(
                """\
                  * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
                """
            ),
        )

    def test_resource_status_without_id(self):
        self.assert_pcs_success(
            self.command, stdout_full=self.all_resources_output
        )

    def test_resource_status_without_id_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["--hide-inactive"],
            stdout_full=self.active_resources_output,
        )

    def test_resource_status_without_id_with_node(self):
        self.assert_pcs_success(
            self.command + ["node=rh-1"], stdout_full=self.node_output
        )

    def test_resource_status_without_id_with_node_hide_inactive(self):
        self.assert_pcs_success(
            self.command + ["node=rh-1", "--hide-inactive"],
            stdout_full=self.active_resources_output_node,
        )

    def test_resource_status_without_id_default_command(self):
        self.assert_pcs_success(
            self.command[:-1], stdout_full=self.all_resources_output
        )

    def test_resource_status_without_id_default_command_hide_inactive(self):
        self.assert_pcs_success(
            self.command[:-1] + ["--hide-inactive"],
            stdout_full=self.active_resources_output,
        )

    def test_status_no_resources(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(self.command, stdout_full=self.no_resources_msg)

    def test_status_no_resources_hide_inactive(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command + ["--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_status_no_resources_with_node(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command + ["node=rh-1"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_status_no_resources_with_node_hide_inactive(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command + ["node=rh-1", "--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )

    def test_status_no_resources_default_command(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command[:-1], stdout_full=self.no_resources_msg
        )

    def test_status_no_resources_default_command_hide_inactive(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command[:-1] + ["--hide-inactive"],
            stdout_full=self.no_active_resources_msg,
        )


class StonithStatus(ResourceStonithStatusBase, TestCase):
    command = ["stonith", "status"]
    no_resources_msg = "NO stonith devices configured\n"
    all_resources_output = outdent(
        """\
          * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
          * fence-rh-2	(stonith:fence_xvm):	 Stopped
          * fence-kdump	(stonith:fence_kdump):	 Stopped
         Target: rh-1
           Level 1 - fence-kdump
           Level 2 - fence-rh-1
         Target: rh-2
           Level 1 - fence-kdump
           Level 2 - fence-rh-2
        """
    )
    active_resources_output = outdent(
        """\
          * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
         Target: rh-1
           Level 1 - fence-kdump
           Level 2 - fence-rh-1
         Target: rh-2
           Level 1 - fence-kdump
           Level 2 - fence-rh-2
        """
    )
    active_resources_output_node = outdent(
        """\
          * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
        """
    )
    node_output = outdent(
        """\
          * fence-rh-1	(stonith:fence_xvm):	 Started rh-1
          * fence-rh-2	(stonith:fence_xvm):	 Stopped
          * fence-kdump	(stonith:fence_kdump):	 Stopped
        """
    )


def fixture_resources_status_output(nodes="rh-1 rh-2", inactive=True):
    if not inactive:
        if is_pacemaker_21_without_20_compatibility():
            return outdent(
                """\
                  * x1	(ocf:pacemaker:Dummy):	 Started rh-1
                """
            )
        return outdent(
            """\
              * x1	(ocf::pacemaker:Dummy):	 Started rh-1
            """
        )

    if is_pacemaker_21_without_20_compatibility():
        return outdent(
            f"""\
              * not-in-tags	(ocf:pacemaker:Dummy):	 Stopped
              * x1	(ocf:pacemaker:Dummy):	 Started rh-1
              * x2	(ocf:pacemaker:Dummy):	 Stopped
              * x3	(ocf:pacemaker:Dummy):	 Stopped
              * y1	(ocf:pacemaker:Dummy):	 Stopped
              * Clone Set: y2-clone [y2]:
                * Stopped: [ {nodes} ]
            """
        )
    return outdent(
        f"""\
          * not-in-tags	(ocf::pacemaker:Dummy):	 Stopped
          * x1	(ocf::pacemaker:Dummy):	 Started rh-1
          * x2	(ocf::pacemaker:Dummy):	 Stopped
          * x3	(ocf::pacemaker:Dummy):	 Stopped
          * y1	(ocf::pacemaker:Dummy):	 Stopped
          * Clone Set: y2-clone [y2]:
            * Stopped: [ {nodes} ]
        """
    )


class ResourceStatus(ResourceStonithStatusBase, TestCase):
    command = ["resource", "status"]
    no_resources_msg = "NO resources configured\n"
    all_resources_output = fixture_resources_status_output()
    active_resources_output = fixture_resources_status_output(inactive=False)
    active_resources_output_node = active_resources_output
    node_output = fixture_resources_status_output(nodes="rh-1")


class StatusResources(ResourceStonithStatusBase, TestCase):
    command = ["status", "resources"]
    no_resources_msg = "NO resources configured\n"
    all_resources_output = fixture_resources_status_output()
    active_resources_output = fixture_resources_status_output(inactive=False)
    active_resources_output_node = active_resources_output
    node_output = fixture_resources_status_output(nodes="rh-1")
    no_resources_status = outdent(
        """\
        Cluster name: test99

        WARNINGS:
        No stonith devices and stonith-enabled is not false

        Cluster Summary:
          * Stack: unknown
          * Current DC: NONE
        """
    )
    resources_status = outdent(
        """\
        Cluster name: test99
        Cluster Summary:
          * Stack: unknown
          * Current DC: rh-2 (version unknown) - partition WITHOUT quorum
        """
    )

    def test_resource_status_without_id_default_command(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_success(["status"], stdout_start=self.resources_status)

    def test_status_no_resources_default_command(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            ["status"], stdout_start=self.no_resources_status
        )

    def test_resource_status_without_id_default_command_hide_inactive(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        self.assert_pcs_success(
            ["status", "--hide-inactive"], stdout_start=self.resources_status
        )

    def test_status_no_resources_default_command_hide_inactive(self):
        self.pcs_runner.corosync_conf_opt = self.corosync_conf
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            ["status", "--hide-inactive"], stdout_start=self.no_resources_status
        )


class XmlStatus(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_status_xml_status")
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_success(self):
        xml = r"""
            <pacemaker-result api-version="[^"]*" request="{crm_mon} --one-shot --inactive --output-as xml">
              <summary>
                <stack type="unknown"/>
                <current_dc present="false"/>
                <last_update time="[^"]*"/>
                <last_change time="Thu Aug 23 16:49:17 2012" user="" client="crmd" origin="rh7-3"/>
                <nodes_configured number="0"/>
                <resources_configured number="0" disabled="0" blocked="0"/>
                <cluster_options[^/>]*/>
              </summary>
              <nodes/>
              <status code="0" message="OK"/>
            </pacemaker-result>
        """.format(
            crm_mon=settings.crm_mon
        )
        self.assert_pcs_success(
            ["status", "xml"],
            stdout_regexp=re.compile(dedent(xml).strip(), re.MULTILINE),
        )
