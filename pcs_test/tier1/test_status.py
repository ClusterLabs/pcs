# pylint: disable=line-too-long
from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    is_minimum_pacemaker_version,
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
            "Warning: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
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
    command = None
    no_resources_msg = None
    all_resources_output = None
    cib_file = rc("cib-tags.xml")

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

    def test_resource_id(self):
        self.assert_pcs_success(
            self.command + ["x1"],
            stdout_full="  * x1	(ocf::pacemaker:Dummy):	 Stopped\n",
        )

    def test_stonith_id(self):
        self.assert_pcs_success(
            self.command + ["fence-rh-1"],
            stdout_full="  * fence-rh-1	(stonith:fence_xvm):	 Stopped\n",
        )

    def test_tag_id(self):
        self.assert_pcs_success(
            self.command + ["tag-mixed-stonith-devices-and-resources"],
            stdout_full=outdent(
                """\
                  * fence-rh-1	(stonith:fence_xvm):	 Stopped
                  * fence-rh-2	(stonith:fence_xvm):	 Stopped
                  * x3	(ocf::pacemaker:Dummy):	 Stopped
                  * y1	(ocf::pacemaker:Dummy):	 Stopped
                """
            ),
        )

    def test_resource_status_without_id(self):
        self.assert_pcs_success(
            self.command, stdout_full=self.all_resources_output
        )

    def test_resource_status_without_id_default_command(self):
        self.assert_pcs_success(
            self.command[:-1], stdout_full=self.all_resources_output
        )

    def test_status_no_resources(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(self.command, stdout_full=self.no_resources_msg)

    def test_status_no_resources_default_command(self):
        write_file_to_tmpfile(rc("cib-empty.xml"), self.temp_cib)
        self.assert_pcs_success(
            self.command[:-1], stdout_full=self.no_resources_msg
        )


class StonithStatus(ResourceStonithStatusBase, TestCase):
    command = ["stonith", "status"]
    no_resources_msg = "NO stonith devices configured\n"
    all_resources_output = outdent(
        """\
          * fence-rh-1	(stonith:fence_xvm):	 Stopped
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


FIXTURE_RESOURCES_STATUS_OUTPUT = outdent(
    """\
      * not-in-tags	(ocf::pacemaker:Dummy):	 Stopped
      * x1	(ocf::pacemaker:Dummy):	 Stopped
      * x2	(ocf::pacemaker:Dummy):	 Stopped
      * x3	(ocf::pacemaker:Dummy):	 Stopped
      * y1	(ocf::pacemaker:Dummy):	 Stopped
      * Clone Set: y2-clone [y2]:
        * Stopped: [ rh-1 rh-2 ]
    """
)


class ResourceStatus(ResourceStonithStatusBase, TestCase):
    command = ["resource", "status"]
    no_resources_msg = "NO resources configured\n"
    all_resources_output = FIXTURE_RESOURCES_STATUS_OUTPUT


class StatusResources(ResourceStonithStatusBase, TestCase):
    command = ["status", "resources"]
    no_resources_msg = "NO resources configured\n"
    all_resources_output = FIXTURE_RESOURCES_STATUS_OUTPUT

    def test_resource_status_without_id_default_command(self):
        pass

    def test_status_no_resources_default_command(self):
        pass
