# pylint: disable=too-many-lines
import os
import shutil
from unittest import mock, TestCase

from pcs import stonith
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.common.tools import indent
from pcs_test.tier0.cib_resource.common import ResourceTest
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.misc import (
    get_test_resource as rc,
    is_minimum_pacemaker_version,
    skip_unless_pacemaker_version,
    skip_unless_crm_rule,
    outdent,
    ParametrizedTestMetaClass,
)
from pcs_test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

# pylint: disable=invalid-name
# pylint: disable=line-too-long
# pylint: disable=bad-whitespace

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)
ERRORS_HAVE_OCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
STONITH_TMP = rc("test_stonith")
if not os.path.exists(STONITH_TMP):
    os.makedirs(STONITH_TMP)

empty_cib = rc("cib-empty.xml")
temp_cib = os.path.join(STONITH_TMP, "temp-cib.xml")

# target-pattern attribute was added in pacemaker 1.1.13 with validate-with 2.3.
# However in pcs this was implemented much later together with target-attribute
# support. In that time pacemaker 1.1.12 was quite old. To keep tests simple we
# do not run fencing topology tests on pacemaker older that 1.1.13 even if it
# supports targeting by node names.
skip_unless_fencing_level_supported = skip_unless_pacemaker_version(
    (1, 1, 13),
    "fencing levels"
)
# target-attribute and target-value attributes were added in pacemaker 1.1.14
# with validate-with 2.4.
fencing_level_attribute_supported = is_minimum_pacemaker_version(1, 1, 14)
skip_unless_fencing_level_attribute_supported = skip_unless_pacemaker_version(
    (1, 1, 14),
    "fencing levels with attribute targets"
)


class StonithDescribeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def test_success(self):
        self.assert_pcs_success(
            "stonith describe fence_apc",
            stdout_start="""\
fence_apc - Fence agent for APC over telnet/ssh

fence_apc is an I/O Fencing agent which can be used with the APC network power switch. It logs into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections should be avoided while a GFS cluster  is  running  because  the  connection will block any necessary fencing actions.

Stonith options:
"""
        )

    def test_full(self):
        stdout, pcs_returncode = self.pcs_runner.run(
            "stonith describe fence_apc --full",
        )
        self.assertEqual(0, pcs_returncode)
        self.assertTrue("pcmk_list_retries" in stdout)

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "stonith describe fence_noexist",
            stdout_full=(
                "Error: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22)\n"
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n"
            )
        )

    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith describe",
            stdout_start="\nUsage: pcs stonith describe...\n"
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "stonith describe agent1 agent2",
            stdout_start="\nUsage: pcs stonith describe...\n"
        )


class StonithTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        shutil.copy(empty_cib, temp_cib)

    @skip_unless_crm_rule
    def testStonithCreation(self):
        self.assert_pcs_fail(
            "stonith create test1 fence_noexist",
            stdout_full=(
                "Error: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22)\n"
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error, use --force to override\n"
            )
        )

        self.assert_pcs_success(
            "stonith create test1 fence_noexist --force",
            stdout_full=(
                "Warning: Agent 'fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22)\n"
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n"
            )
        )

        self.assert_pcs_fail(
            "stonith create test2 fence_apc",
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                    "use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )

        self.assert_pcs_success(
            "stonith create test2 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_apc bad_argument=test",
            stdout_start="Error: invalid stonith option 'bad_argument',"
                " allowed options are:"
        )

        self.assert_pcs_fail(
            "stonith create test9 fence_apc pcmk_status_action=xxx",
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                    "use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )

        self.assert_pcs_success(
            "stonith create test9 fence_apc pcmk_status_action=xxx --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )

        self.assert_pcs_success("stonith config test9", outdent(
            """\
             Resource: test9 (class=stonith type=fence_apc)
              Attributes: pcmk_status_action=xxx
              Operations: monitor interval=60s (test9-monitor-interval-60s)
            """
        ))

        self.assert_pcs_success(
            "stonith delete test9",
            "Deleting Resource - test9\n"
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_ilo ip=test",
            (
                "Error: required stonith option 'username' is missing, use "
                    "--force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )

        self.assert_pcs_success(
            "stonith create test3 fence_ilo ip=test --force",
            "Warning: required stonith option 'username' is missing\n"
        )

        # Testing that pcmk_host_check, pcmk_host_list & pcmk_host_map are
        # allowed for stonith agents
        self.assert_pcs_success(
            'stonith create apc-fencing fence_apc ip=morph-apc username=apc password=apc switch=1 pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5 pcmk_host_check=static-list pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05',
        )

        self.assert_pcs_fail(
            "resource config apc-fencing",
            "Error: unable to find resource 'apc-fencing'\n"
        )

        self.assert_pcs_success("stonith config apc-fencing", outdent(
            """\
             Resource: apc-fencing (class=stonith type=fence_apc)
              Attributes: ip=morph-apc password=apc pcmk_host_check=static-list pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05 pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5 switch=1 username=apc
              Operations: monitor interval=60s (apc-fencing-monitor-interval-60s)
            """
        ))

        self.assert_pcs_success(
            "stonith remove apc-fencing",
            "Deleting Resource - apc-fencing\n"
        )

        self.assert_pcs_fail(
            "stonith update test3 bad_ipaddr=test username=login",
            stdout_regexp=(
                "^Error: invalid stonith option 'bad_ipaddr', allowed options"
                " are: [^\n]+, use --force to override\n$"
            )
        )

        self.assert_pcs_success("stonith update test3 username=testA")

        self.assert_pcs_success("stonith config test2", outdent(
            """\
             Resource: test2 (class=stonith type=fence_apc)
              Operations: monitor interval=60s (test2-monitor-interval-60s)
            """
        ))

        self.assert_pcs_success("stonith config", outdent(
            """\
             Resource: test1 (class=stonith type=fence_noexist)
              Operations: monitor interval=60s (test1-monitor-interval-60s)
             Resource: test2 (class=stonith type=fence_apc)
              Operations: monitor interval=60s (test2-monitor-interval-60s)
             Resource: test3 (class=stonith type=fence_ilo)
              Attributes: ip=test username=testA
              Operations: monitor interval=60s (test3-monitor-interval-60s)
            """
        ))

        self.assert_pcs_success(
            "stonith create test-fencing fence_apc 'pcmk_host_list=rhel7-node1 rhel7-node2' op monitor interval=61s --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )

        self.assert_pcs_success("config show", outdent(
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

            Quorum:
              Options:
            """
        ))

    def test_stonith_create_does_not_require_deprecated(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_fail(
            "stonith create test2 fence_apc",
            (
                "Error: required stonith options 'ip', 'username' are missing, "
                    "use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )

    def test_stonith_create_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            "stonith create S fence_apc ip=i login=l"
        )
        self.assert_pcs_success(
            "stonith config S",
            outdent(
            """\
             Resource: S (class=stonith type=fence_apc)
              Attributes: ip=i login=l
              Operations: monitor interval=60s (S-monitor-interval-60s)
            """
            )
        )

    def test_stonith_create_both_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            "stonith create S fence_apc ip=i1 login=l ipaddr=i2 username=u"
        )
        self.assert_pcs_success(
            "stonith config S",
            outdent(
            """\
             Resource: S (class=stonith type=fence_apc)
              Attributes: ip=i1 ipaddr=i2 login=l username=u
              Operations: monitor interval=60s (S-monitor-interval-60s)
            """
            )
        )

    def test_stonith_create_provides_unfencing(self):
        self.assert_pcs_success("stonith create f1 fence_scsi")

        self.assert_pcs_success(
            "stonith create f2 fence_scsi meta provides=unfencing"
        )

        self.assert_pcs_success(
            "stonith create f3 fence_scsi meta provides=something"
        )

        self.assert_pcs_success(
            "stonith create f4 fence_xvm meta provides=something"
        )

        self.assert_pcs_success("stonith config", outdent(
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
        ))

    def test_stonith_create_action(self):
        self.assert_pcs_fail(
            "stonith create test fence_apc ip=i username=u action=a",
            (
                "Error: stonith option 'action' is deprecated and should not be"
                    " used, use pcmk_off_action, pcmk_reboot_action instead,"
                    " use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )

        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u action=a --force",
            "Warning: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead\n"
        )

        self.assert_pcs_success(
            "stonith config",
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action=a ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            )
        )

    def test_stonith_create_action_empty(self):
        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u action="
        )

        self.assert_pcs_success(
            "stonith config",
            # TODO fix code and test - there should be no action in the attribs
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action= ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            )
        )

    def test_stonith_update_action(self):
        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u"
        )

        self.assert_pcs_success(
            "stonith config",
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            )
        )

        self.assert_pcs_fail(
            "stonith update test action=a",
            "Error: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead,"
                " use --force to override\n"
        )

        self.assert_pcs_success(
            "stonith update test action=a --force",
            "Warning: stonith option 'action' is deprecated and should not be"
                " used, use pcmk_off_action, pcmk_reboot_action instead\n"
        )

        self.assert_pcs_success(
            "stonith config",
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: action=a ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            )
        )

        self.assert_pcs_success(
            "stonith update test action="
        )

        self.assert_pcs_success(
            "stonith config",
            outdent(
                """\
                 Resource: test (class=stonith type=fence_apc)
                  Attributes: ip=i username=u
                  Operations: monitor interval=60s (test-monitor-interval-60s)
                """
            )
        )

    def testStonithFenceConfirm(self):
        self.pcs_runner.cib_file = None
        self.assert_pcs_fail(
            "stonith fence blah blah",
            "Error: must specify one (and only one) node to fence\n"
        )
        self.assert_pcs_fail(
            "stonith confirm blah blah",
            "Error: must specify one (and only one) node to confirm fenced\n"
        )

    def testPcmkHostList(self):
        self.assert_pcs_success(
            "stonith create F1 fence_apc 'pcmk_host_list=nodea nodeb' --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )

        self.assert_pcs_success("stonith config F1", outdent(
            """\
             Resource: F1 (class=stonith type=fence_apc)
              Attributes: pcmk_host_list="nodea nodeb"
              Operations: monitor interval=60s (F1-monitor-interval-60s)
            """
        ))

    def testStonithDeleteRemovesLevel(self):
        shutil.copy(rc("cib-empty-with3nodes.xml"), temp_cib)

        self.assert_pcs_success(
            "stonith create n1-ipmi fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n2-ipmi fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n1-apc1 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n1-apc2 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n2-apc1 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n2-apc2 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success(
            "stonith create n2-apc3 fence_apc --force",
            "Warning: required stonith options 'ip', 'username' are missing\n"
        )
        self.assert_pcs_success_all([
            "stonith level add 1 rh7-1 n1-ipmi",
            "stonith level add 2 rh7-1 n1-apc1,n1-apc2,n2-apc2",
            "stonith level add 1 rh7-2 n2-ipmi",
            "stonith level add 2 rh7-2 n2-apc1,n2-apc2,n2-apc3",
        ])

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
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
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
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
            ))

        self.assert_pcs_success(
            "stonith delete n2-apc2",
            "Deleting Resource - n2-apc2\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
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
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
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
            ))

        self.assert_pcs_success(
            "stonith remove n2-apc1",
            "Deleting Resource - n2-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
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
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
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
            ))

        self.assert_pcs_success(
            "stonith delete n2-apc3",
            "Deleting Resource - n2-apc3\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
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
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
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
            ))

        self.assert_pcs_success(
            "resource remove n1-apc1",
            "Deleting Resource - n1-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
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
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
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
            ))

        self.assert_pcs_success("resource delete n1-apc2", outdent(
            """\
            Deleting Resource - n1-apc2
            """
        ))

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success("stonith", outdent(
                """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
            ), despace=True)
        else:
            self.assert_pcs_success("stonith", outdent(
                """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
            ))

    def testNoStonithWarning(self):
        # pylint: disable=unused-variable
        corosync_conf = rc("corosync.conf")
        o,r = pcs(temp_cib, "status", corosync_conf_opt=corosync_conf)
        self.assertIn(
            "No stonith devices and stonith-enabled is not false",
            o
        )

        self.assert_pcs_success(
            "stonith create test_stonith fence_apc ip=i username=u pcmk_host_argument=node1"
        )

        o,r = pcs(temp_cib, "status", corosync_conf_opt=corosync_conf)
        self.assertNotIn(
            "No stonith devices and stonith-enabled is not false",
            o
        )

        self.assert_pcs_success(
            "stonith delete test_stonith",
            "Deleting Resource - test_stonith\n"
        )

        o,r = pcs(temp_cib, "status", corosync_conf_opt=corosync_conf)
        self.assertIn(
            "No stonith devices and stonith-enabled is not false",
            o
        )


class LevelTestsBase(TestCase, AssertPcsMixin):
    def setUp(self):
        if fencing_level_attribute_supported:
            shutil.copy(rc("cib-empty-2.5-withnodes.xml"), temp_cib)
        else:
            shutil.copy(rc("cib-empty-2.3-withnodes.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.config = ""
        self.config_lines = []

    def fixture_stonith_resource(self, name):
        self.assert_pcs_success(
            "stonith create {name} fence_apc 'pcmk_host_list=rh7-1 rh7-2' ip=i username=u"
            .format(name=name)
        )

    def fixture_full_configuration(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.fixture_stonith_resource("F3")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1")
        self.assert_pcs_success("stonith level add 2 rh7-1 F2")
        self.assert_pcs_success("stonith level add 2 rh7-2 F1")
        self.assert_pcs_success("stonith level add 1 rh7-2 F2")
        self.assert_pcs_success(r"stonith level add 4 regexp%rh7-\d F3")
        self.assert_pcs_success(r"stonith level add 3 regexp%rh7-\d F2 F1")

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
            "stonith level add 5 attrib%fencewith=levels1 F3 F2"
        )
        self.assert_pcs_success(
            "stonith level add 6 attrib%fencewith=levels2 F3 F1"
        )
        self.config += outdent(
            """\
            Target: fencewith=levels1
              Level 5 - F3,F2
            Target: fencewith=levels2
              Level 6 - F3,F1
            """)
        self.config_lines = self.config.splitlines()


@skip_unless_fencing_level_supported
class LevelBadCommand(LevelTestsBase):
    def test_success(self):
        self.assert_pcs_fail(
            "stonith level nonsense",
            stdout_start="\nUsage: pcs stonith level ...\n"
        )


@skip_unless_fencing_level_supported
class LevelAddTargetUpgradesCib(LevelTestsBase):
    def setUp(self):
        shutil.copy(rc("cib-empty-withnodes.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    @skip_unless_fencing_level_attribute_supported
    def test_attribute(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 attrib%fencewith=levels F1",
            "CIB has been upgraded to the latest schema version.\n"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            )
        )

    def test_regexp(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            r"stonith level add 1 regexp%node-\d+ F1",
            "CIB has been upgraded to the latest schema version.\n"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: node-\\d+
                  Level 1 - F1
                """
            )
        )


@skip_unless_fencing_level_supported
class LevelAdd(LevelTestsBase):
    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith level add",
            stdout_start="\nUsage: pcs stonith level add...\n"
        )

        self.assert_pcs_fail(
            "stonith level add 1",
            stdout_start="\nUsage: pcs stonith level add...\n"
        )

        self.assert_pcs_fail(
            "stonith level add 1 nodeA",
            stdout_start="\nUsage: pcs stonith level add...\n"
        )

    def test_add_wrong_target_type(self):
        self.assert_pcs_fail(
            "stonith level add 1 error%value F1",
            "Error: 'error' is not an allowed type for 'error%value', "
                "use attrib, node, regexp\n"
        )

    def test_add_bad_level(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add NaN rh7-1 F1",
            (
                "Error: 'NaN' is not a valid level value, use a positive "
                    "integer\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_fail(
            "stonith level add -10 rh7-1 F1",
            (
                "Error: '-10' is not a valid level value, use a positive "
                    "integer\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_fail(
            "stonith level add 10abc rh7-1 F1",
            (
                "Error: '10abc' is not a valid level value, use a positive "
                    "integer\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_fail(
            "stonith level add 0 rh7-1 F1",
            (
                "Error: '0' is not a valid level value, use a positive "
                    "integer\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_fail(
            "stonith level add 000 rh7-1 F1",
            (
                "Error: '000' is not a valid level value, use a positive "
                "integer\n"
                + ERRORS_HAVE_OCURRED
            )
        )

    def test_add_bad_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 dev@ce",
            (
                "Error: invalid device id 'dev@ce', '@' is not a valid "
                    "character for a device id\n"
                + ERRORS_HAVE_OCURRED
            )
        )

    def test_add_more_errors(self):
        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce",
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Error: Node 'rh7-X' does not appear to exist in configuration, use --force to override
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Error: Stonith resource(s) 'F0' do not exist, use --force to override
                """
            ) + ERRORS_HAVE_OCURRED
        )

        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce --force",
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Error: Errors have occurred, therefore pcs is unable to continue
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Warning: Stonith resource(s) 'F0' do not exist
                """
            )
        )

    def test_add_level_leading_zero(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 0002 rh7-1 F1")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 2 - F1
                """
            )
        )

    def test_add_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            )
        )

        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1",
            (
                "Error: Fencing level for 'rh7-1' at level '1' with device(s) "
                    "'F1' already exists\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            )
        )

    def test_add_node_pattern(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(r"stonith level add 1 regexp%rh7-\d F1")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-\\d
                  Level 1 - F1
                """
            )
        )

        self.assert_pcs_fail(
            r"stonith level add 1 regexp%rh7-\d F1",
            (
                r"Error: Fencing level for 'rh7-\d' at level '1' with device(s) "
                    "'F1' already exists\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-\\d
                  Level 1 - F1
                """
            )
        )

    @skip_unless_fencing_level_attribute_supported
    def test_add_node_attribute(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 attrib%fencewith=levels F1"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            )
        )

        self.assert_pcs_fail(
            "stonith level add 1 attrib%fencewith=levels F1",
            (
                "Error: Fencing level for 'fencewith=levels' at level '1' with "
                    "device(s) 'F1' already exists\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            )
        )

    def test_add_more_devices(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1 F2")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            )
        )

    def test_add_more_devices_old_syntax(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.fixture_stonith_resource("F3")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1,F2")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            )
        )

        self.assert_pcs_success("stonith level add 2 rh7-1 F1,F2 F3")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                """
            )
        )

        self.assert_pcs_success("stonith level add 3 rh7-1 F1 F2,F3")
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                  Level 3 - F1,F2,F3
                """
            )
        )

    def test_nonexistant_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-X F1",
            (
                "Error: Node 'rh7-X' does not appear to exist in configuration"
                    ", use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X F1 --force",
            "Warning: Node 'rh7-X' does not appear to exist in configuration\n"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-X
                  Level 1 - F1
                """
            )
        )

    def test_nonexistant_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1",
            (
                "Error: Stonith resource(s) 'F1' do not exist"
                    ", use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 --force",
            "Warning: Stonith resource(s) 'F1' do not exist\n"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            )
        )

    def test_nonexistant_devices(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1 F2 F3",
            (
                "Error: Stonith resource(s) 'F2', 'F3' do not exist"
                    ", use --force to override\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 F2 F3 --force",
            "Warning: Stonith resource(s) 'F2', 'F3' do not exist\n"
        )
        self.assert_pcs_success(
            "stonith level",
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2,F3
                """
            )
        )


@skip_unless_fencing_level_supported
@skip_unless_crm_rule
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

        Quorum:
          Options:
        """
    )

    def test_empty(self):
        self.assert_pcs_success("stonith level config", "")
        self.assert_pcs_success("stonith level", "")
        self.assert_pcs_success("stonith", "NO stonith devices configured\n")
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            "config",
            self.full_config.format(devices="", levels="")
        )

    def test_all_posibilities(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level config", self.config)
        self.assert_pcs_success("stonith level", self.config)
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
            "stonith",
            result + "\n".join(indent(self.config_lines, 1)) + "\n",
            despace=True
        )
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            "config",
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
                levels=("\n" + "\n".join(indent(self.config_lines, 2)))
            )
        )


@skip_unless_fencing_level_supported
class LevelClear(LevelTestsBase):
    def setUp(self):
        super(LevelClear, self).setUp()
        self.fixture_full_configuration()

    def test_clear_all(self):
        self.assert_pcs_success("stonith level clear")
        self.assert_pcs_success("stonith level config", "")

    def test_clear_nonexistant_node_or_device(self):
        self.assert_pcs_success("stonith level clear rh-X")
        self.assert_pcs_success("stonith level config", self.config)

    def test_clear_nonexistant_devices(self):
        self.assert_pcs_success("stonith level clear F1,F5")
        self.assert_pcs_success("stonith level config", self.config)

    def test_pattern_is_not_device(self):
        self.assert_pcs_success("stonith level clear regexp%F1")
        self.assert_pcs_success("stonith level config", self.config)

    def test_clear_node(self):
        self.assert_pcs_success("stonith level clear rh7-1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[3:]) + "\n"
        )

    def test_clear_pattern(self):
        self.assert_pcs_success(r"stonith level clear regexp%rh7-\d")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:6] + self.config_lines[9:]) + "\n"
        )

    @skip_unless_fencing_level_attribute_supported
    def test_clear_attribute(self):
        self.assert_pcs_success("stonith level clear attrib%fencewith=levels2")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:11]) + "\n"
        )

    def test_clear_device(self):
        self.assert_pcs_success("stonith level clear F1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(
                self.config_lines[0:1]
                +
                self.config_lines[2:5]
                +
                self.config_lines[6:]
            ) + "\n"
        )

    def test_clear_devices(self):
        self.assert_pcs_success("stonith level clear F2,F1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n"
        )


class LevelDeleteRemove(LevelTestsBase):
    command = None

    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def _test_usage(self):
        self.assert_pcs_fail(
            f"stonith level {self.command}",
            stdout_start=outdent(f"""
                Usage: pcs stonith level {self.command}...
                    level {self.command} <""")
        )

    def _test_nonexisting_level_node_device(self):
        self.assert_pcs_fail(
            f"stonith level {self.command} 1 rh7-1 F3",
            outdent(
                """\
                Error: Fencing level for 'rh7-1' at level '1' with device(s) 'F3' does not exist
                Error: Fencing level at level '1' with device(s) 'F3', 'rh7-1' does not exist
                """
            ) + ERRORS_HAVE_OCURRED
        )
        self.assert_pcs_success("stonith level config", self.config)

    def _test_nonexisting_level_pattern_device(self):
        self.assert_pcs_fail(
            f"stonith level {self.command} 1 regexp%rh7-\\d F3",
            (
                "Error: Fencing level for 'rh7-\\d' at level '1' with "
                    "device(s) 'F3' does not exist\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success("stonith level config", self.config)

        self.assert_pcs_fail(
            f"stonith level {self.command} 3 regexp%rh7-\\d F1,F2",
            (
                "Error: Fencing level for 'rh7-\\d' at level '3' with "
                    "device(s) 'F1', 'F2' does not exist\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success("stonith level config", self.config)

    def _test_nonexisting_level(self):
        self.assert_pcs_fail(
            f"stonith level {self.command} 9",
            (
                "Error: Fencing level at level '9' does not exist\n"
                + ERRORS_HAVE_OCURRED
            )
        )
        self.assert_pcs_success("stonith level config", self.config)

    def _test_remove_level(self):
        self.assert_pcs_success(f"stonith level {self.command} 1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(
                self.config_lines[0:1]
                +
                self.config_lines[2:4]
                +
                self.config_lines[5:]
            ) + "\n"
        )

    def _test_remove_level_node(self):
        self.assert_pcs_success(f"stonith level {self.command} 1 rh7-2")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n"
        )

    def _test_remove_level_pattern(self):
        self.assert_pcs_success(f"stonith level {self.command} 3 regexp%rh7-\\d")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n"
        )

    @skip_unless_fencing_level_attribute_supported
    def _test_remove_level_attrib(self):
        self.assert_pcs_success(
            f"stonith level {self.command} 6 attrib%fencewith=levels2"
        )
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:11]) + "\n"
        )

    def _test_remove_level_device(self):
        self.assert_pcs_success(f"stonith level {self.command} 1 F2")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n"
        )

    def _test_remove_level_devices(self):
        self.assert_pcs_success(f"stonith level {self.command} 3 F2 F1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n"
        )

    def _test_remove_level_devices_old_syntax(self):
        self.assert_pcs_success(f"stonith level {self.command} 3 F2,F1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n"
        )

    def _test_remove_level_node_device(self):
        self.assert_pcs_success(f"stonith level {self.command} 1 rh7-2 F2")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n"
        )

    def _test_remove_level_pattern_device(self):
        self.assert_pcs_success(f"stonith level {self.command} 3 regexp%rh7-\\d F2 F1")
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n"
        )

    @skip_unless_fencing_level_attribute_supported
    def _test_remove_level_attrib_device(self):
        self.assert_pcs_success(
            f"stonith level {self.command} 6 attrib%fencewith=levels2 F3 F1"
        )
        self.assert_pcs_success(
            "stonith level config",
            "\n".join(self.config_lines[:11]) + "\n"
        )


@skip_unless_fencing_level_supported
class LevelDelete(
    LevelDeleteRemove,
    metaclass=ParametrizedTestMetaClass

):
    command = "delete"


@skip_unless_fencing_level_supported
class LevelRemove(
    LevelDeleteRemove,
    metaclass=ParametrizedTestMetaClass

):
    command = "remove"


@skip_unless_fencing_level_supported
class LevelVerify(LevelTestsBase):
    def test_success(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level verify", "")

    def test_errors(self):
        self.fixture_stonith_resource("F1")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1")
        self.assert_pcs_success(
            "stonith level add 2 rh7-1 FX --force",
            "Warning: Stonith resource(s) 'FX' do not exist\n"
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X FX --force",
            outdent(
                """\
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FX' do not exist
                """
            )
        )
        self.assert_pcs_success(
            "stonith level add 2 rh7-Y FY --force",
            outdent(
                """\
                Warning: Node 'rh7-Y' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FY' do not exist
                """
            )
        )
        self.assert_pcs_success(
            r"stonith level add 4 regexp%rh7-\d FX --force",
            "Warning: Stonith resource(s) 'FX' do not exist\n"
        )
        self.assert_pcs_success(
            r"stonith level add 3 regexp%rh7-\d FY FZ --force",
            "Warning: Stonith resource(s) 'FY', 'FZ' do not exist\n"
        )

        self.assert_pcs_fail(
            "stonith level verify",
            (
                "Error: Stonith resource(s) 'FX', 'FY', 'FZ' do not exist\n"
                "Error: Node 'rh7-X' does not appear to exist in "
                    "configuration\n"
                "Error: Node 'rh7-Y' does not appear to exist in "
                    "configuration\n"
                + ERRORS_HAVE_OCURRED
            )
        )

def _dict_to_modifiers(options):
    def _convert_val(val):
        if val is True:
            return ""
        return val
    return InputModifiers(
        {
            f"--{opt}": _convert_val(val)
            for opt, val in options.items()
            if val is not False
        }
    )

class SbdEnable(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["sbd"])
        self.sbd = mock.Mock(spec_set=["enable_sbd"])
        self.lib.sbd = self.sbd

    def assert_called_with(
        self, default_watchdog, watchdog_dict, sbd_options, **kwargs
    ):
        default_kwargs = dict(
            default_device_list=None,
            node_device_dict=None,
            allow_unknown_opts=False,
            ignore_offline_nodes=False,
            no_watchdog_validation=False,
        )
        default_kwargs.update(kwargs)
        self.sbd.enable_sbd.assert_called_once_with(
            default_watchdog, watchdog_dict, sbd_options, **default_kwargs
        )

    def call_cmd(self, argv, modifiers=None):
        stonith.sbd_enable(self.lib, argv, _dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        self.call_cmd([])
        self.assert_called_with(None, dict(), dict())

    def test_watchdog(self):
        self.call_cmd(["watchdog=/dev/wd"])
        self.assert_called_with("/dev/wd", dict(), dict())

    def test_device(self):
        self.call_cmd(["device=/dev/sda"])
        self.assert_called_with(
            None, dict(), dict(), default_device_list=["/dev/sda"]
        )

    def test_options(self):
        self.call_cmd(["SBD_A=a", "SBD_B=b"])
        self.assert_called_with(
            None, dict(), dict(SBD_A="a", SBD_B="b")
        )

    def test_multiple_watchdogs_devices(self):
        self.call_cmd([
            "watchdog=/dev/wd",
            "watchdog=/dev/wda@node-a",
            "watchdog=/dev/wdb@node-b",
            "device=/dev/sda1",
            "device=/dev/sda2",
            "device=/dev/sdb1@node-b",
            "device=/dev/sdb2@node-b",
            "device=/dev/sdc1@node-c",
            "device=/dev/sdc2@node-c",
        ])
        self.assert_called_with(
            "/dev/wd",
            {"node-a": "/dev/wda", "node-b": "/dev/wdb"},
            dict(),
            default_device_list=["/dev/sda1", "/dev/sda2"],
            node_device_dict={
                "node-b": ["/dev/sdb1", "/dev/sdb2"],
                "node-c": ["/dev/sdc1", "/dev/sdc2"],
            }
        )

    def test_modifiers(self):
        self.call_cmd([], modifiers={
            "force": "",
            "skip-offline": "",
            "no-watchdog-validation": "",
        })
        self.assert_called_with(
            None, dict(), dict(),
            allow_unknown_opts=True,
            ignore_offline_nodes=True,
            no_watchdog_validation=True,
        )

class SbdDeviceSetup(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["sbd"])
        self.sbd = mock.Mock(spec_set=["initialize_block_devices"])
        self.lib.sbd = self.sbd

    def assert_called_with(self, device_list, option_dict):
        self.sbd.initialize_block_devices.assert_called_once_with(
            device_list, option_dict
        )

    def call_cmd(self, argv, modifiers=None):
        all_modifiers = dict(
            force=True, # otherwise it asks interactively for confirmation
        )
        all_modifiers.update(modifiers or {})
        stonith.sbd_setup_block_device(
            self.lib, argv, _dict_to_modifiers(all_modifiers)
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertEqual(cm.exception.message, "No device defined")

    def test_minimal(self):
        self.call_cmd(["device=/dev/sda"])
        self.assert_called_with(["/dev/sda"], dict())

    def test_devices_and_options(self):
        self.call_cmd(["device=/dev/sda", "a=A", "device=/dev/sdb", "b=B"])
        self.assert_called_with(["/dev/sda", "/dev/sdb"], {"a": "A", "b": "B"})

    def test_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["a=A"])
        self.assertEqual(cm.exception.message, "No device defined")


class StonithUpdate(ResourceTest):
    def setUp(self):
        # use our temp file instead of parent's one so parallel tests don't
        # overwrite it
        self.temp_cib = temp_cib
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.fixture_create_stonith()

    def fixture_create_stonith(self):
        self.assert_effect(
            "stonith create S fence_apc ip=i login=l ssh=0 debug=d",
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
            """
        )

    def test_set_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=D",
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
            """
        )

    def test_unset_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=",
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
            """
        )

    def test_unset_deprecated_required_param(self):
        self.assert_pcs_fail(
            "stonith update S login=",
            "Error: required stonith option 'username' is missing, use --force "
                "to override\n"
        )

    def test_set_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=1",
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
            """
        )

    def test_unset_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=",
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
            """
        )

    def test_unset_obsoleting_required_param(self):
        self.assert_pcs_fail(
            "stonith update S ip=",
            "Error: required stonith option 'ip' is missing, use --force "
                "to override\n"
        )

    def test_unset_deprecated_required_set_obsoleting(self):
        self.assert_effect(
            "stonith update S login= username=u",
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
            """
        )

    def test_unset_obsoleting_required_set_deprecated(self):
        self.assert_effect(
            "stonith update S ip= ipaddr=I",
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
            """
        )

    def test_set_both_deprecated_and_obsoleting(self):
        self.assert_effect(
            "stonith update S ip=I1 ipaddr=I2",
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
            """
        )
