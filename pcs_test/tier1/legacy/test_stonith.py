# pylint: disable=too-many-lines
import shutil
from textwrap import dedent
from unittest import TestCase

from pcs.common.str_tools import indent
from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    is_minimum_pacemaker_version,
    skip_unless_pacemaker_version,
    skip_unless_crm_rule,
    outdent,
    ParametrizedTestMetaClass,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

# pylint: disable=invalid-name
# pylint: disable=line-too-long

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)
ERRORS_HAVE_OCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)

empty_cib = rc("cib-empty.xml")

# target-pattern attribute was added in pacemaker 1.1.13 with validate-with 2.3.
# However in pcs this was implemented much later together with target-attribute
# support. In that time pacemaker 1.1.12 was quite old. To keep tests simple we
# do not run fencing topology tests on pacemaker older that 1.1.13 even if it
# supports targeting by node names.
skip_unless_fencing_level_supported = skip_unless_pacemaker_version(
    (1, 1, 13), "fencing levels"
)
# target-attribute and target-value attributes were added in pacemaker 1.1.14
# with validate-with 2.4.
fencing_level_attribute_supported = is_minimum_pacemaker_version(1, 1, 14)
skip_unless_fencing_level_attribute_supported = skip_unless_pacemaker_version(
    (1, 1, 14), "fencing levels with attribute targets"
)


class StonithDescribeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def test_success(self):
        self.assert_pcs_success(
            "stonith describe fence_apc".split(),
            stdout_start=dedent(
                """\
                fence_apc - Fence agent for APC over telnet/ssh

                fence_apc is an I/O Fencing agent which can be used with the APC network power switch. It logs into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections should be avoided while a GFS cluster  is  running  because  the  connection will block any necessary fencing actions.

                Stonith options:
                """
            ),
        )

    def test_full(self):
        stdout, pcs_returncode = self.pcs_runner.run(
            "stonith describe fence_apc --full".split(),
        )
        self.assertEqual(0, pcs_returncode)
        self.assertTrue("pcmk_list_retries" in stdout)

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "stonith describe fence_noexist".split(),
            stdout_full=(
                "Error: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n"
            ),
        )

    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith describe".split(),
            stdout_start="\nUsage: pcs stonith describe...\n",
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "stonith describe agent1 agent2".split(),
            stdout_start="\nUsage: pcs stonith describe...\n",
        )


class StonithTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_stonith")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )

    def tearDown(self):
        self.temp_cib.close()

    @skip_unless_crm_rule()
    def testStonithCreation(self):
        self.assert_pcs_fail(
            "stonith create test1 fence_noexist".split(),
            stdout_full=(
                "Error: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error, use --force to override\n"
            ),
        )

        self.assert_pcs_success(
            "stonith create test1 fence_noexist --force".split(),
            stdout_full=(
                "Warning: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n"
            ),
        )

        self.assert_pcs_fail(
            "stonith create test2 fence_apc".split(),
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                "use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test2 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_apc bad_argument=test".split(),
            stdout_start="Error: invalid stonith option 'bad_argument',"
            " allowed options are:",
        )

        self.assert_pcs_fail(
            "stonith create test9 fence_apc pcmk_status_action=xxx".split(),
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                "use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test9 fence_apc pcmk_status_action=xxx --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )

        self.assert_pcs_success(
            "stonith config test9".split(),
            outdent(
                """\
             Resource: test9 (class=stonith type=fence_apc)
              Attributes: pcmk_status_action=xxx
              Operations: monitor interval=60s (test9-monitor-interval-60s)
            """
            ),
        )

        self.assert_pcs_success(
            "stonith delete test9".split(), "Deleting Resource - test9\n"
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_ilo ip=test".split(),
            (
                "Error: required stonith option 'username' is missing, use "
                "--force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test3 fence_ilo ip=test --force".split(),
            "Warning: required stonith option 'username' is missing\n",
        )

        # Testing that pcmk_host_check, pcmk_host_list & pcmk_host_map are
        # allowed for stonith agents
        self.assert_pcs_success(
            "stonith create apc-fencing fence_apc ip=morph-apc username=apc password=apc switch=1 pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5 pcmk_host_check=static-list pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05".split(),
        )

        self.assert_pcs_fail(
            "resource config apc-fencing".split(),
            "Error: unable to find resource 'apc-fencing'\n",
        )

        self.assert_pcs_success(
            "stonith config apc-fencing".split(),
            outdent(
                """\
             Resource: apc-fencing (class=stonith type=fence_apc)
              Attributes: ip=morph-apc password=apc pcmk_host_check=static-list pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05 pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5 switch=1 username=apc
              Operations: monitor interval=60s (apc-fencing-monitor-interval-60s)
            """
            ),
        )

        self.assert_pcs_success(
            "stonith remove apc-fencing".split(),
            "Deleting Resource - apc-fencing\n",
        )

        self.assert_pcs_fail(
            "stonith update test3 bad_ipaddr=test username=login".split(),
            stdout_regexp=(
                "^Error: invalid stonith option 'bad_ipaddr', allowed options"
                " are: [^\n]+, use --force to override\n$"
            ),
        )

        self.assert_pcs_success("stonith update test3 username=testA".split())

        self.assert_pcs_success(
            "stonith config test2".split(),
            outdent(
                """\
             Resource: test2 (class=stonith type=fence_apc)
              Operations: monitor interval=60s (test2-monitor-interval-60s)
            """
            ),
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
             Resource: test1 (class=stonith type=fence_noexist)
              Operations: monitor interval=60s (test1-monitor-interval-60s)
             Resource: test2 (class=stonith type=fence_apc)
              Operations: monitor interval=60s (test2-monitor-interval-60s)
             Resource: test3 (class=stonith type=fence_ilo)
              Attributes: ip=test username=testA
              Operations: monitor interval=60s (test3-monitor-interval-60s)
            """
            ),
        )

        self.assert_pcs_success(
            [
                "stonith",
                "create",
                "test-fencing",
                "fence_apc",
                "pcmk_host_list=rhel7-node1 rhel7-node2",
                "op",
                "monitor",
                "interval=61s",
                "--force",
            ],
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )

        self.assert_pcs_success(
            "config show".split(),
            outdent(
                """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:

            Stonith Devices:
             Resource: test1 (class=stonith type=fence_noexist)
              Operations: monitor interval=60s (test1-monitor-interval-60s)
             Resource: test2 (class=stonith type=fence_apc)
              Operations: monitor interval=60s (test2-monitor-interval-60s)
             Resource: test3 (class=stonith type=fence_ilo)
              Attributes: ip=test username=testA
              Operations: monitor interval=60s (test3-monitor-interval-60s)
             Resource: test-fencing (class=stonith type=fence_apc)
              Attributes: pcmk_host_list="rhel7-node1 rhel7-node2"
              Operations: monitor interval=61s (test-fencing-monitor-interval-61s)
            Fencing Levels:

            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:

            Alerts:
             No alerts defined

            Resources Defaults:
              No defaults set
            Operations Defaults:
              No defaults set

            Cluster Properties:

            Tags:
             No tags defined

            Quorum:
              Options:
            """
            ),
        )

    def test_stonith_create_does_not_require_deprecated(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_fail(
            "stonith create test2 fence_apc".split(),
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                "use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )

    def test_stonith_create_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            "stonith create S fence_apc ip=i login=l".split()
        )
        self.assert_pcs_success(
            "stonith config S".split(),
            outdent(
                """\
             Resource: S (class=stonith type=fence_apc)
              Attributes: ip=i login=l
              Operations: monitor interval=60s (S-monitor-interval-60s)
            """
            ),
        )

    def test_stonith_create_both_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            "stonith create S fence_apc ip=i1 login=l ipaddr=i2 username=u".split()
        )
        self.assert_pcs_success(
            "stonith config S".split(),
            outdent(
                """\
             Resource: S (class=stonith type=fence_apc)
              Attributes: ip=i1 ipaddr=i2 login=l username=u
              Operations: monitor interval=60s (S-monitor-interval-60s)
            """
            ),
        )

    def test_stonith_create_provides_unfencing(self):
        self.assert_pcs_success("stonith create f1 fence_scsi".split())
        self.assert_pcs_success(
            "stonith create f2 fence_scsi meta provides=unfencing".split()
        )
        self.assert_pcs_success(
            "stonith create f3 fence_scsi meta provides=something".split()
        )
        self.assert_pcs_success(
            "stonith create f4 fence_xvm meta provides=something".split()
        )
        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
             Resource: f1 (class=stonith type=fence_scsi)
              Meta Attrs: provides=unfencing
              Operations: monitor interval=60s (f1-monitor-interval-60s)
             Resource: f2 (class=stonith type=fence_scsi)
              Meta Attrs: provides=unfencing
              Operations: monitor interval=60s (f2-monitor-interval-60s)
             Resource: f3 (class=stonith type=fence_scsi)
              Meta Attrs: provides=unfencing
              Operations: monitor interval=60s (f3-monitor-interval-60s)
             Resource: f4 (class=stonith type=fence_xvm)
              Meta Attrs: provides=something
              Operations: monitor interval=60s (f4-monitor-interval-60s)
            """
            ),
        )

    def test_stonith_create_action(self):
        self.assert_pcs_fail(
            "stonith create test fence_apc ip=i username=u action=a".split(),
            (
                "Error: stonith option 'action' is deprecated and should not be"
                " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead,"
                " use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u action=a --force".split(),
            "Warning: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action=a ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            ),
        )

    def test_stonith_create_action_empty(self):
        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u action=".split()
        )

        self.assert_pcs_success(
            "stonith config".split(),
            # TODO fix code and test - there should be no action in the attribs
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action= ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            ),
        )

    def test_stonith_update_action(self):
        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u".split()
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith update test action=a".split(),
            "Error: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead,"
            " use --force to override\n",
        )

        self.assert_pcs_success(
            "stonith update test action=a --force".split(),
            "Warning: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action=a ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            ),
        )

        self.assert_pcs_success("stonith update test action=".split())

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            ),
        )

    def testStonithFenceConfirm(self):
        self.pcs_runner.cib_file = None
        self.assert_pcs_fail(
            "stonith fence blah blah".split(),
            "Error: must specify one (and only one) node to fence\n",
        )
        self.assert_pcs_fail(
            "stonith confirm blah blah".split(),
            "Error: must specify one (and only one) node to confirm fenced\n",
        )

    def testPcmkHostList(self):
        self.assert_pcs_success(
            [
                "stonith",
                "create",
                "F1",
                "fence_apc",
                "pcmk_host_list=nodea nodeb",
                "--force",
            ],
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )

        self.assert_pcs_success(
            "stonith config F1".split(),
            outdent(
                """\
             Resource: F1 (class=stonith type=fence_apc)
              Attributes: pcmk_host_list="nodea nodeb"
              Operations: monitor interval=60s (F1-monitor-interval-60s)
            """
            ),
        )

    def testStonithDeleteRemovesLevel(self):
        shutil.copyfile(rc("cib-empty-with3nodes.xml"), self.temp_cib.name)

        self.assert_pcs_success(
            "stonith create n1-ipmi fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n2-ipmi fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n1-apc1 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n1-apc2 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n2-apc1 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n2-apc2 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success(
            "stonith create n2-apc3 fence_apc --force".split(),
            "Warning: required stonith options 'ip', 'username' are missing\n",
        )
        self.assert_pcs_success_all(
            [
                "stonith level add 1 rh7-1 n1-ipmi".split(),
                "stonith level add 2 rh7-1 n1-apc1,n1-apc2,n2-apc2".split(),
                "stonith level add 1 rh7-2 n2-ipmi".split(),
                "stonith level add 2 rh7-2 n2-apc1,n2-apc2,n2-apc3".split(),
            ]
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc1\t(stonith:fence_apc):\tStopped
                  * n2-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2,n2-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc2,n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc1\t(stonith:fence_apc):\tStopped
                 n2-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2,n2-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc2,n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith delete n2-apc2".split(), "Deleting Resource - n2-apc2\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc1\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc1\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith remove n2-apc1".split(), "Deleting Resource - n2-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith delete n2-apc3".split(), "Deleting Resource - n2-apc3\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

        self.assert_pcs_success(
            "resource remove n1-apc1".split(), "Deleting Resource - n1-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

        self.assert_pcs_success(
            "resource delete n1-apc2".split(),
            outdent(
                """\
            Deleting Resource - n1-apc2
            """
            ),
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

    def testNoStonithWarning(self):
        # pylint: disable=unused-variable
        corosync_conf = rc("corosync.conf")
        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertIn("No stonith devices and stonith-enabled is not false", o)

        self.assert_pcs_success(
            "stonith create test_stonith fence_apc ip=i username=u pcmk_host_argument=node1".split()
        )

        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertNotIn(
            "No stonith devices and stonith-enabled is not false", o
        )

        self.assert_pcs_success(
            "stonith delete test_stonith".split(),
            "Deleting Resource - test_stonith\n",
        )

        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertIn("No stonith devices and stonith-enabled is not false", o)


class LevelTestsBase(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_stonith_level")
        if fencing_level_attribute_supported:
            write_file_to_tmpfile(
                rc("cib-empty-2.5-withnodes.xml"), self.temp_cib
            )
        else:
            write_file_to_tmpfile(
                rc("cib-empty-2.3-withnodes.xml"), self.temp_cib
            )
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.config = ""
        self.config_lines = []

    def tearDown(self):
        self.temp_cib.close()

    def fixture_stonith_resource(self, name):
        self.assert_pcs_success(
            [
                "stonith",
                "create",
                name,
                "fence_apc",
                "pcmk_host_list=rh7-1 rh7-2",
                "ip=i",
                "username=u",
            ]
        )

    def fixture_full_configuration(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.fixture_stonith_resource("F3")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success("stonith level add 2 rh7-1 F2".split())
        self.assert_pcs_success("stonith level add 2 rh7-2 F1".split())
        self.assert_pcs_success("stonith level add 1 rh7-2 F2".split())
        self.assert_pcs_success("stonith level add 4 regexp%rh7-\\d F3".split())
        self.assert_pcs_success(
            "stonith level add 3 regexp%rh7-\\d F2 F1".split()
        )

        self.config = outdent(
            """\
            Target: rh7-1
              Level 1 - F1
              Level 2 - F2
            Target: rh7-2
              Level 1 - F2
              Level 2 - F1
            Target: rh7-\\d
              Level 3 - F2,F1
              Level 4 - F3
            """
        )
        self.config_lines = self.config.splitlines()

        if not fencing_level_attribute_supported:
            return
        self.assert_pcs_success(
            "stonith level add 5 attrib%fencewith=levels1 F3 F2".split()
        )
        self.assert_pcs_success(
            "stonith level add 6 attrib%fencewith=levels2 F3 F1".split()
        )
        self.config += outdent(
            """\
            Target: fencewith=levels1
              Level 5 - F3,F2
            Target: fencewith=levels2
              Level 6 - F3,F1
            """
        )
        self.config_lines = self.config.splitlines()


@skip_unless_fencing_level_supported
class LevelBadCommand(LevelTestsBase):
    def test_success(self):
        self.assert_pcs_fail(
            "stonith level nonsense".split(),
            stdout_start="\nUsage: pcs stonith level ...\n",
        )


@skip_unless_fencing_level_supported
class LevelAddTargetUpgradesCib(LevelTestsBase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_stonith_level")
        write_file_to_tmpfile(rc("cib-empty-withnodes.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    @skip_unless_fencing_level_attribute_supported
    def test_attribute(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 attrib%fencewith=levels F1".split(),
            "CIB has been upgraded to the latest schema version.\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            ),
        )

    def test_regexp(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 regexp%node-\\d+ F1".split(),
            "CIB has been upgraded to the latest schema version.\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: node-\\d+
                  Level 1 - F1
                """
            ),
        )


@skip_unless_fencing_level_supported
class LevelAdd(LevelTestsBase):
    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith level add".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

        self.assert_pcs_fail(
            "stonith level add 1".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

        self.assert_pcs_fail(
            "stonith level add 1 nodeA".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

    def test_add_wrong_target_type(self):
        self.assert_pcs_fail(
            "stonith level add 1 error%value F1".split(),
            "Error: 'error' is not an allowed type for 'error%value', "
            "use attrib, node, regexp\n",
        )

    def test_add_bad_level(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add NaN rh7-1 F1".split(),
            (
                "Error: 'NaN' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_fail(
            "-- stonith level add -10 rh7-1 F1".split(),
            (
                "Error: '-10' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 10abc rh7-1 F1".split(),
            (
                "Error: '10abc' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 0 rh7-1 F1".split(),
            (
                "Error: '0' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 000 rh7-1 F1".split(),
            (
                "Error: '000' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCURRED
            ),
        )

    def test_add_bad_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 dev@ce".split(),
            (
                "Error: invalid device id 'dev@ce', '@' is not a valid "
                "character for a device id\n" + ERRORS_HAVE_OCURRED
            ),
        )

    def test_add_more_errors(self):
        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce".split(),
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Error: Node 'rh7-X' does not appear to exist in configuration, use --force to override
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Error: Stonith resource(s) 'F0' do not exist, use --force to override
                """
            )
            + ERRORS_HAVE_OCURRED,
        )

        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce --force".split(),
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Error: Errors have occurred, therefore pcs is unable to continue
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Warning: Stonith resource(s) 'F0' do not exist
                """
            ),
        )

    def test_add_level_leading_zero(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 0002 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 2 - F1
                """
            ),
        )

    def test_add_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1".split(),
            (
                "Error: Fencing level for 'rh7-1' at level '1' with device(s) "
                "'F1' already exists\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

    def test_add_node_pattern(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 1 regexp%rh7-\\d F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-\\d
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 regexp%rh7-\\d F1".split(),
            (
                r"Error: Fencing level for 'rh7-\d' at level '1' with device(s) "
                "'F1' already exists\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-\\d
                  Level 1 - F1
                """
            ),
        )

    @skip_unless_fencing_level_attribute_supported
    def test_add_node_attribute(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 attrib%fencewith=levels F1".split()
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 attrib%fencewith=levels F1".split(),
            (
                "Error: Fencing level for 'fencewith=levels' at level '1' with "
                "device(s) 'F1' already exists\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            ),
        )

    def test_add_more_devices(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1 F2".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            ),
        )

    def test_add_more_devices_old_syntax(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.fixture_stonith_resource("F3")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1,F2".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            ),
        )

        self.assert_pcs_success("stonith level add 2 rh7-1 F1,F2 F3".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                """
            ),
        )

        self.assert_pcs_success("stonith level add 3 rh7-1 F1 F2,F3".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                  Level 3 - F1,F2,F3
                """
            ),
        )

    def test_nonexistant_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-X F1".split(),
            (
                "Error: Node 'rh7-X' does not appear to exist in configuration"
                ", use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X F1 --force".split(),
            "Warning: Node 'rh7-X' does not appear to exist in configuration\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-X
                  Level 1 - F1
                """
            ),
        )

    def test_nonexistant_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1".split(),
            (
                "Error: Stonith resource(s) 'F1' do not exist"
                ", use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 --force".split(),
            "Warning: Stonith resource(s) 'F1' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

    def test_nonexistant_devices(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1 F2 F3".split(),
            (
                "Error: Stonith resource(s) 'F2', 'F3' do not exist"
                ", use --force to override\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 F2 F3 --force".split(),
            "Warning: Stonith resource(s) 'F2', 'F3' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2,F3
                """
            ),
        )


@skip_unless_fencing_level_supported
@skip_unless_crm_rule()
class LevelConfig(LevelTestsBase):
    full_config = outdent(
        """\
        Cluster Name: test99
        Corosync Nodes:
         rh7-1 rh7-2
        Pacemaker Nodes:
         rh7-1 rh7-2

        Resources:

        Stonith Devices:{devices}
        Fencing Levels:{levels}

        Location Constraints:
        Ordering Constraints:
        Colocation Constraints:
        Ticket Constraints:

        Alerts:
         No alerts defined

        Resources Defaults:
          No defaults set
        Operations Defaults:
          No defaults set

        Cluster Properties:

        Tags:
         No tags defined

        Quorum:
          Options:
        """
    )

    def test_empty(self):
        self.assert_pcs_success("stonith level config".split(), "")
        self.assert_pcs_success("stonith level".split(), "")
        self.assert_pcs_success(["stonith"], "NO stonith devices configured\n")
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            ["config"], self.full_config.format(devices="", levels="")
        )

    def test_all_posibilities(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level config".split(), self.config)
        self.assert_pcs_success("stonith level".split(), self.config)
        if PCMK_2_0_3_PLUS:
            result = outdent(
                """\
                  * F1\t(stonith:fence_apc):\tStopped
                  * F2\t(stonith:fence_apc):\tStopped
                  * F3\t(stonith:fence_apc):\tStopped
                """
            )
        else:
            result = outdent(
                """\
                 F1\t(stonith:fence_apc):\tStopped
                 F2\t(stonith:fence_apc):\tStopped
                 F3\t(stonith:fence_apc):\tStopped
                """
            )
        self.assert_pcs_success(
            ["stonith"],
            result + "\n".join(indent(self.config_lines, 1)) + "\n",
            despace=True,
        )
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            ["config"],
            self.full_config.format(
                devices="""
 Resource: F1 (class=stonith type=fence_apc)
  Attributes: ip=i pcmk_host_list="rh7-1 rh7-2" username=u
  Operations: monitor interval=60s (F1-monitor-interval-60s)
 Resource: F2 (class=stonith type=fence_apc)
  Attributes: ip=i pcmk_host_list="rh7-1 rh7-2" username=u
  Operations: monitor interval=60s (F2-monitor-interval-60s)
 Resource: F3 (class=stonith type=fence_apc)
  Attributes: ip=i pcmk_host_list="rh7-1 rh7-2" username=u
  Operations: monitor interval=60s (F3-monitor-interval-60s)\
""",
                levels=("\n" + "\n".join(indent(self.config_lines, 2))),
            ),
        )


@skip_unless_fencing_level_supported
class LevelClear(LevelTestsBase):
    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def test_clear_all(self):
        self.assert_pcs_success("stonith level clear".split())
        self.assert_pcs_success("stonith level config".split(), "")

    def test_clear_nonexistant_node_or_device(self):
        self.assert_pcs_success("stonith level clear rh-X".split())
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_nonexistant_devices(self):
        self.assert_pcs_success("stonith level clear F1,F5".split())
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_pattern_is_not_device(self):
        self.assert_pcs_success("stonith level clear regexp%F1".split())
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_node(self):
        self.assert_pcs_success("stonith level clear rh7-1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[3:]) + "\n",
        )

    def test_clear_pattern(self):
        self.assert_pcs_success("stonith level clear regexp%rh7-\\d".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:6] + self.config_lines[9:]) + "\n",
        )

    @skip_unless_fencing_level_attribute_supported
    def test_clear_attribute(self):
        self.assert_pcs_success(
            "stonith level clear attrib%fencewith=levels2".split()
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def test_clear_device(self):
        self.assert_pcs_success("stonith level clear F1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:5]
                + self.config_lines[6:]
            )
            + "\n",
        )

    def test_clear_devices(self):
        self.assert_pcs_success("stonith level clear F2,F1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )


class LevelDeleteRemove(LevelTestsBase):
    command = None

    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def _test_usage(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command],
            stdout_start=outdent(
                f"""
                Usage: pcs stonith level {self.command}...
                    level {self.command} <"""
            ),
        )

    def _test_nonexisting_level_node_device(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "rh7-1", "F3"],
            outdent(
                """\
                Error: Fencing level for 'rh7-1' at level '1' with device(s) 'F3' does not exist
                Error: Fencing level at level '1' with device(s) 'F3', 'rh7-1' does not exist
                """
            )
            + ERRORS_HAVE_OCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level_pattern_device(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", r"regexp%rh7-\d", "F3"],
            (
                "Error: Fencing level for 'rh7-\\d' at level '1' with "
                "device(s) 'F3' does not exist\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

        self.assert_pcs_fail(
            ["stonith", "level", self.command, "3", r"regexp%rh7-\d", "F1,F2"],
            (
                "Error: Fencing level for 'rh7-\\d' at level '3' with "
                "device(s) 'F1', 'F2' does not exist\n" + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "9"],
            (
                "Error: Fencing level at level '9' does not exist\n"
                + ERRORS_HAVE_OCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_remove_level(self):
        self.assert_pcs_success(["stonith", "level", self.command, "1"])
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:4]
                + self.config_lines[5:]
            )
            + "\n",
        )

    def _test_remove_level_node(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "rh7-2"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", r"regexp%rh7-\d"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    @skip_unless_fencing_level_attribute_supported
    def _test_remove_level_attrib(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "6", "attrib%fencewith=levels2"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def _test_remove_level_device(self):
        self.assert_pcs_success(["stonith", "level", self.command, "1", "F2"])
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_devices(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "F2", "F1"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_devices_old_syntax(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "F2,F1"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_node_device(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "rh7-2", "F2"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "3",
                r"regexp%rh7-\d",
                "F2",
                "F1",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    @skip_unless_fencing_level_attribute_supported
    def _test_remove_level_attrib_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "6",
                "attrib%fencewith=levels2",
                "F3",
                "F1",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )


@skip_unless_fencing_level_supported
class LevelDelete(LevelDeleteRemove, metaclass=ParametrizedTestMetaClass):
    command = "delete"


@skip_unless_fencing_level_supported
class LevelRemove(LevelDeleteRemove, metaclass=ParametrizedTestMetaClass):
    command = "remove"


@skip_unless_fencing_level_supported
class LevelVerify(LevelTestsBase):
    def test_success(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level verify".split(), "")

    def test_errors(self):
        self.fixture_stonith_resource("F1")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level add 2 rh7-1 FX --force".split(),
            "Warning: Stonith resource(s) 'FX' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X FX --force".split(),
            outdent(
                """\
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FX' do not exist
                """
            ),
        )
        self.assert_pcs_success(
            "stonith level add 2 rh7-Y FY --force".split(),
            outdent(
                """\
                Warning: Node 'rh7-Y' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FY' do not exist
                """
            ),
        )
        self.assert_pcs_success(
            "stonith level add 4 regexp%rh7-\\d FX --force".split(),
            "Warning: Stonith resource(s) 'FX' do not exist\n",
        )
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                "add",
                "3",
                r"regexp%rh7-\d",
                "FY",
                "FZ",
                "--force",
            ],
            "Warning: Stonith resource(s) 'FY', 'FZ' do not exist\n",
        )

        self.assert_pcs_fail(
            "stonith level verify".split(),
            (
                "Error: Stonith resource(s) 'FX', 'FY', 'FZ' do not exist\n"
                "Error: Node 'rh7-X' does not appear to exist in "
                "configuration\n"
                "Error: Node 'rh7-Y' does not appear to exist in "
                "configuration\n" + ERRORS_HAVE_OCURRED
            ),
        )


class StonithUpdate(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.fixture_create_stonith()

    def fixture_create_stonith(self):
        self.assert_effect(
            "stonith create S fence_apc ip=i login=l ssh=0 debug=d".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_set_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=D".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="D"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_deprecated_required_param(self):
        self.assert_pcs_fail(
            "stonith update S login=".split(),
            "Error: required stonith option 'username' is missing, use --force "
            "to override\n",
        )

    def test_set_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=1".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="1"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_obsoleting_required_param(self):
        self.assert_pcs_fail(
            "stonith update S ip=".split(),
            "Error: required stonith option 'ip' is missing, use --force "
            "to override\n",
        )

    def test_unset_deprecated_required_set_obsoleting(self):
        self.assert_effect(
            "stonith update S login= username=u".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-username"
                            name="username" value="u"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_obsoleting_required_set_deprecated(self):
        self.assert_effect(
            "stonith update S ip= ipaddr=I".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-ipaddr" name="ipaddr"
                            value="I"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_set_both_deprecated_and_obsoleting(self):
        self.assert_effect(
            "stonith update S ip=I1 ipaddr=I2".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="I1"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-ipaddr" name="ipaddr"
                            value="I2"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )
