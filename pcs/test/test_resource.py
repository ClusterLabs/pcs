from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree
import re
from random import shuffle
import shutil
from textwrap import dedent

from pcs.test.tools import pcs_unittest as unittest
from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.pcs_unittest import mock, TestCase
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)
from pcs.test.bin_mock import get_mock_settings

from pcs import utils
from pcs import resource

empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")
large_cib = rc("cib-large.xml")
temp_large_cib  = rc("temp-cib-large.xml")

LOCATION_NODE_VALIDATION_SKIP_WARNING = (
    "Warning: Validation for node existence in the cluster will be skipped\n"
)

class ResourceDescribeTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def fixture_description(self, advanced=False):
        advanced_params = (
            """\
              trace_ra: Set to 1 to turn on resource agent tracing (expect large output) The
                        trace output will be saved to trace_file, if set, or by default to
                        $HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp> e.g.
                        $HA_VARRUN/ra_trace/oracle/db.start.2012-11-27.08:37:08
              trace_file: Path to a file to store resource agent tracing log
            """
        )
        return outdent(
            """\
            ocf:pacemaker:HealthCPU - System health CPU usage

            Systhem health agent that measures the CPU idling and updates the #health-cpu attribute.

            Resource options:
              state (unique): Location to store the resource state in.
              yellow_limit (unique): Lower (!) limit of idle percentage to switch the health
                                     attribute to yellow. I.e. the #health-cpu will go
                                     yellow if the %idle of the CPU falls below 50%.
              red_limit: Lower (!) limit of idle percentage to switch the health attribute
                         to red. I.e. the #health-cpu will go red if the %idle of the CPU
                         falls below 10%.
{0}
            Default operations:
              start: interval=0s timeout=10
              stop: interval=0s timeout=10
              monitor: interval=10 start-delay=0 timeout=10
            """.format(advanced_params if advanced else "")
        )

    def test_success(self):
        self.assert_pcs_success(
            "resource describe ocf:pacemaker:HealthCPU",
            self.fixture_description()
        )

    def test_full(self):
        self.assert_pcs_success(
            "resource describe ocf:pacemaker:HealthCPU --full",
            self.fixture_description(True)
        )

    def test_success_guess_name(self):
        self.assert_pcs_success(
            "resource describe healthcpu",
            "Assumed agent name 'ocf:pacemaker:HealthCPU' (deduced from"
                + " 'healthcpu')\n"
                + self.fixture_description()
        )

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "resource describe ocf:heartbeat:NoExisting",
            stdout_full=(
                "Error: Agent 'ocf:heartbeat:NoExisting' is not installed or "
                "does not provide valid metadata: Metadata query for "
                "ocf:heartbeat:NoExisting failed: Input/output error\n"
            )
        )

    def test_nonextisting_agent_guess_name(self):
        self.assert_pcs_fail(
            "resource describe nonexistent",
            (
                "Error: Unable to find agent 'nonexistent', try specifying"
                " its full name\n"
            )
        )

    def test_more_agents_guess_name(self):
        self.assert_pcs_fail(
            "resource describe dummy",
            (
                "Error: Multiple agents match 'dummy', please specify full"
                " name: ocf:heartbeat:Dummy, ocf:pacemaker:Dummy\n"
            )
        )

    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "resource describe",
            stdout_start="\nUsage: pcs resource describe...\n"
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "resource describe agent1 agent2",
            stdout_start="\nUsage: pcs resource describe...\n"
        )


class ResourceTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        shutil.copy(large_cib, temp_large_cib)
        self.mock_settings = get_mock_settings("crm_resource_binary")
        self.pcs_runner = PcsRunner(temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setupClusterA(self,temp_cib):
        self.pcs_runner.mock_settings = self.mock_settings
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP2 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.92 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP3 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.93 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP4 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.94 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.95 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP6 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.96 op monitor interval=30s"
        )
        self.assert_pcs_success("resource group add TestGroup1 ClusterIP")
        self.assert_pcs_success(
            "resource group add TestGroup2 ClusterIP2 ClusterIP3"
        )
        self.assert_pcs_success("resource clone ClusterIP4")
        self.assert_pcs_success("resource master Master ClusterIP5")

    def testCaseInsensitive(self):
        self.pcs_runner.mock_settings = self.mock_settings
        self.assert_pcs_fail(
            "resource create --no-default-ops D0 dummy",
            stdout_full=(
                "Error: Multiple agents match 'dummy', please specify full "
                "name: ocf:heartbeat:Dummy, ocf:pacemaker:Dummy\n"
            )
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D1 systemhealth",
            "Assumed agent name 'ocf:pacemaker:SystemHealth'"
                " (deduced from 'systemhealth')\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 SYSTEMHEALTH",
            "Assumed agent name 'ocf:pacemaker:SystemHealth'"
                " (deduced from 'SYSTEMHEALTH')\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D3 ipaddr2 ip=1.1.1.1",
            "Assumed agent name 'ocf:heartbeat:IPaddr2'"
                " (deduced from 'ipaddr2')\n"
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops D4 ipaddr3",
            stdout_full=(
                "Error: Unable to find agent 'ipaddr3', try specifying its "
                "full name\n"
            )
        )

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "resource")
        assert returnVal == 0, 'Unable to list resources'
        assert output == "NO resources configured\n", "Bad output"

    def testAddResourcesLargeCib(self):
        self.pcs_runner = PcsRunner(
            temp_large_cib, mock_settings=self.mock_settings
        )
        self.assert_pcs_success(
            "resource create dummy0 ocf:heartbeat:Dummy"
        )

        self.assert_pcs_success(
            "resource show dummy0",
            stdout_full=outdent(
                """\
                 Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)
                  Operations: migrate_from interval=0s timeout=20s (dummy0-migrate_from-interval-0s)
                              migrate_to interval=0s timeout=20s (dummy0-migrate_to-interval-0s)
                              monitor interval=10s timeout=20s (dummy0-monitor-interval-10s)
                              reload interval=0s timeout=20s (dummy0-reload-interval-0s)
                              start interval=0s timeout=20s (dummy0-start-interval-0s)
                              stop interval=0s timeout=20s (dummy0-stop-interval-0s)
                """
            )
        )

    def testDeleteResources(self):
        self.pcs_runner.mock_settings = self.mock_settings
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
            " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_fail(
            'resource delete',
            stdout_start="\nUsage: pcs resource",
        )

        self.assert_pcs_success(
            "resource delete ClusterIP",
            "Deleting Resource - ClusterIP\n"
        )

        self.assert_pcs_fail(
            "resource show ClusterIP",
            "Error: unable to find resource 'ClusterIP'\n",
        )

        self.assert_pcs_success(
            "resource show",
            'NO resources configured\n',
        )

        self.assert_pcs_fail(
            "resource delete ClusterIP",
            "Error: Resource 'ClusterIP' does not exist.\n"
        )

    def testResourceShow(self):
        self.pcs_runner.mock_settings = self.mock_settings
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success("resource show ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
            """
        ))

    def testAddOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

        o,r = pcs(temp_cib, "resource add_operation")
        assert r == 1
        assert o == "Error: add_operation has been deprecated, please use 'op add'\n",[o]

        o,r = pcs(temp_cib, "resource remove_operation")
        assert r == 1
        assert o == "Error: remove_operation has been deprecated, please use 'op remove'\n"

        line = 'resource op add'
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource op remove'
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line)
        ac(output, """\
Error: operation monitor already specified for ClusterIP, use --force to override:
monitor interval=30s (ClusterIP-monitor-interval-30s)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource op add ClusterIP monitor interval=31s --force"
        )
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line)
        ac(output, """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""")
        assert returnVal == 1

        line = 'resource op add ClusterIP monitor interval=31'
        output, returnVal = pcs(temp_cib, line)
        ac(output, """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""")
        assert returnVal == 1

        output, returnVal = pcs(
            temp_cib,
            "resource op add ClusterIP moni=tor interval=60"
        )
        ac(output, """\
Error: moni=tor does not appear to be a valid operation action
""")
        assert returnVal == 1

        self.assert_pcs_success("resource show ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
                          monitor interval=31s (ClusterIP-monitor-interval-31s)
            """
        ))

        o, r = pcs(temp_cib, "resource create --no-default-ops OPTest ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest")
        ac(o," Resource: OPTest (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-25s)\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource create --no-default-ops OPTest2 ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=2 op start timeout=30s")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource op add OPTest2 start timeout=1800s")
        ac(o, """\
Error: operation start with interval 0s already specified for OPTest2:
start interval=0s timeout=30s (OPTest2-start-interval-0s)
""")
        assert r == 1

        output, retVal = pcs(
            temp_cib, "resource op add OPTest2 start interval=100"
        )
        ac(output, """\
Error: operation start already specified for OPTest2, use --force to override:
start interval=0s timeout=30s (OPTest2-start-interval-0s)
""")
        self.assertEqual(1, retVal)

        o, r = pcs(temp_cib, "resource op add OPTest2 monitor timeout=1800s")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest2")
        ac(o," Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=2 (OPTest2-monitor-interval-25s)\n              start interval=0s timeout=30s (OPTest2-start-interval-0s)\n              monitor interval=60s timeout=1800s (OPTest2-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest3 ocf:heartbeat:Dummy op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest3")
        ac(o," Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest3-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest4 ocf:heartbeat:Dummy op monitor interval=30s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest4")
        ac(o," Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest4-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest5 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest5")
        ac(o," Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest5-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest6 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show OPTest6", stdout_regexp=re.compile(outdent(
                """\
                 Resource: OPTest6 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(OPTest6-monitor-interval-10s?\\)
                              monitor interval=30s OCF_CHECK_LEVEL=1 \\(OPTest6-monitor-interval-30s\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest7 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest7 op monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1")
        ac(o, """\
Error: operation monitor already specified for OPTest7, use --force to override:
monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)
""")
        self.assertEqual(1, r)

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1 --force")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest7")
        ac(o," Resource: OPTest7 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)\n              monitor interval=61s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-61s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o, """\
Error: operation monitor with interval 60s already specified for OPTest7:
monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)
""")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops OCFTest1 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        self.assert_pcs_fail(
            "resource op add OCFTest1 monitor interval=31s",
            stdout_regexp=re.compile(outdent(
                """\
                Error: operation monitor already specified for OCFTest1, use --force to override:
                monitor interval=10s? timeout=20s? \\(OCFTest1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource op add OCFTest1 monitor interval=31s --force")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OCFTest1 monitor interval=30s OCF_CHECK_LEVEL=15")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show OCFTest1", stdout_regexp=re.compile(outdent(
                """\
                 Resource: OCFTest1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(OCFTest1-monitor-interval-10s?\\)
                              monitor interval=31s \\(OCFTest1-monitor-interval-31s\\)
                              monitor interval=30s OCF_CHECK_LEVEL=15 \\(OCFTest1-monitor-interval-30s\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor interval=61s OCF_CHECK_LEVEL=5")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=61s OCF_CHECK_LEVEL=5 (OCFTest1-monitor-interval-61s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-60s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4 interval=35s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=35s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-35s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        self.assert_pcs_success(
            "resource create --no-default-ops state ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10 to 11 to"
                " make the operation unique\n"
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10",
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10 role=Master timeout=20 (state-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10 role=Started",
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10 role=Master timeout=20 (state-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_success(
            "resource op add state monitor interval=15 role=Master --force"
        )

        self.assert_pcs_success("resource show state", outdent(
            """\
             Resource: state (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10 role=Master timeout=20 (state-monitor-interval-10)
                          monitor interval=11 role=Slave timeout=20 (state-monitor-interval-11)
                          monitor interval=15 role=Master (state-monitor-interval-15)
            """
        ))

    def testUpdateOperation(self):
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success("resource show ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
            """
        ))

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=32s"
        )
        self.assert_pcs_success("resource show ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=32s (ClusterIP-monitor-interval-32s)
            """
        ))

        show_clusterip = outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=33s (ClusterIP-monitor-interval-33s)
                          start interval=30s timeout=180s (ClusterIP-start-interval-30s)
            """
        )
        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s"
        )
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s"
        )
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        self.assert_pcs_success("resource update ClusterIP op")
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        self.assert_pcs_success("resource update ClusterIP op monitor")
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        # test invalid id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ab#cd",
            "Error: invalid operation id 'ab#cd', '#' is not a valid character"
                " for a operation id\n"
        )
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        # test existing id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ClusterIP",
            "Error: id 'ClusterIP' is already in use, please specify another"
                " one\n"
        )
        self.assert_pcs_success("resource show ClusterIP", show_clusterip)

        # test id change
        # there is a bug:
        # - first an existing operation is removed
        # - then a new operation is created at the same place
        # - therefore options not specified for in the command are removed
        #    instead of them being kept from the old operation
        # This needs to be fixed. However it's not my task currently.
        # Moreover it is documented behavior.
        self.assert_pcs_success("resource update ClusterIP op monitor id=abcd")
        self.assert_pcs_success("resource show ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=60s (abcd)
                          start interval=30s timeout=180s (ClusterIP-start-interval-30s)
            """
        ))


        # test two monitor operations:
        # - the first one is updated
        # - operation duplicity detection test
        self.assert_pcs_success(
            "resource create A ocf:heartbeat:Dummy op monitor interval=10 op monitor interval=20"
        )
        self.assert_pcs_success(
            "resource show A",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Resource: A \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: migrate_from interval=0s timeout=20s? \\(A-migrate_from-interval-0s\\)
                              migrate_to interval=0s timeout=20s? \\(A-migrate_to-interval-0s\\)
                              monitor interval=10 \\(A-monitor-interval-10\\)
                              monitor interval=20 \\(A-monitor-interval-20\\)
                              reload interval=0s timeout=20s? \\(A-reload-interval-0s\\)
                              start interval=0s timeout=20s? \\(A-start-interval-0s\\)
                              stop interval=0s timeout=20s? \\(A-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(
            temp_cib,
            "resource update A op monitor interval=20"
        )
        ac(output, """\
Error: operation monitor with interval 20s already specified for A:
monitor interval=20 (A-monitor-interval-20)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update A op monitor interval=11"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show A",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Resource: A \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: migrate_from interval=0s timeout=20s? \\(A-migrate_from-interval-0s\\)
                              migrate_to interval=0s timeout=20s? \\(A-migrate_to-interval-0s\\)
                              monitor interval=11 \\(A-monitor-interval-11\\)
                              monitor interval=20 \\(A-monitor-interval-20\\)
                              reload interval=0s timeout=20s? \\(A-reload-interval-0s\\)
                              start interval=0s timeout=20s? \\(A-start-interval-0s\\)
                              stop interval=0s timeout=20s? \\(A-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create B ocf:heartbeat:Dummy --no-default-ops"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, return_val = self.pcs_runner.run("resource show B")
        self.assertEqual(0, return_val)
        op_id = "B-monitor-interval-10"
        if "{}s".format(op_id) in output:
            op_id = "{}s".format(op_id)
        self.assert_pcs_success("resource op remove {}".format(op_id))

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=60s"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=60s (B-monitor-interval-60s)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=30"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=10"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
              start interval=0 timeout=10 (B-start-interval-0)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=20"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
              start interval=0 timeout=20 (B-start-interval-0)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=33"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=20 (B-start-interval-0)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=100 role=Master"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=20 (B-start-interval-0)
              monitor interval=100 role=Master (B-monitor-interval-100)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=22"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=22 (B-start-interval-0)
              monitor interval=100 role=Master (B-monitor-interval-100)
""")
        self.assertEqual(0, returnVal)

    def testGroupDeleteTest(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A3 ocf:heartbeat:Dummy --group AGroup")
        assert r == 0

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"""\
 Resource Group: AGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
     A3\t(ocf::heartbeat:Dummy):\tStopped
""")

        self.assert_pcs_success("resource delete AGroup", outdent(
            """\
            Removing group: AGroup (and all resources within group)
            Stopping all resources in group: AGroup...
            Deleting Resource - A1
            Deleting Resource - A2
            Deleting Resource (and group) - A3
            """
        ))

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"NO resources configured\n")

    def testGroupRemoveTest(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP3 prefers rh7-1")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        self.assert_pcs_success(
            "resource delete ClusterIP2",
            "Deleting Resource - ClusterIP2\n"
        )

        self.assert_pcs_success("resource delete ClusterIP3", outdent(
            """\
            Removing Constraint - location-ClusterIP3-rh7-1-INFINITY
            Deleting Resource (and group) - ClusterIP3
            """
        ))

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A4 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A5 ocf:heartbeat:Dummy"
        )
        assert r == 0

        o,r = pcs(temp_cib, "resource group add AGroup A1 A2 A3 A4 A5")
        assert r == 0

        self.assert_pcs_success(
            "resource show AGroup", stdout_regexp=re.compile(outdent(
                """\
                 Group: AGroup
                  Resource: A1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A1-monitor-interval-10s?\\)
                  Resource: A2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A2-monitor-interval-10s?\\)
                  Resource: A3 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A3-monitor-interval-10s?\\)
                  Resource: A4 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A4-monitor-interval-10s?\\)
                  Resource: A5 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A5-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource ungroup Noexist")
        assert r == 1
        ac(o,"Error: Group 'Noexist' does not exist\n")

        o,r = pcs(temp_cib, "resource ungroup AGroup A1 A3")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o, """\
 ClusterIP6\t(ocf::heartbeat:IPaddr2):\tStopped
 Resource Group: TestGroup1
     ClusterIP\t(ocf::heartbeat:IPaddr2):\tStopped
 Clone Set: ClusterIP4-clone [ClusterIP4]
 Master/Slave Set: Master [ClusterIP5]
 Resource Group: AGroup
     A2\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
 A1\t(ocf::heartbeat:Dummy):\tStopped
 A3\t(ocf::heartbeat:Dummy):\tStopped
""")

        o,r = pcs(temp_cib, "constraint location AGroup prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AGroup A2")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "constraint")
        assert r == 0
        ac(o, """\
Location Constraints:
  Resource: AGroup
    Enabled on: rh7-1 (score:INFINITY)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        o,r = pcs(temp_cib, "resource ungroup AGroup")
        assert r == 0
        ac(o, 'Removing Constraint - location-AGroup-rh7-1-INFINITY\n')

        o,r = pcs(temp_cib, "resource show AGroup")
        assert r == 1
        ac(o,"Error: unable to find resource 'AGroup'\n")

        self.assert_pcs_success(
            "resource show A1 A2 A3 A4 A5", stdout_regexp=re.compile(outdent(
                """\
                 Resource: A1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A1-monitor-interval-10s?\\)
                 Resource: A2 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A2-monitor-interval-10s?\\)
                 Resource: A3 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A3-monitor-interval-10s?\\)
                 Resource: A4 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A4-monitor-interval-10s?\\)
                 Resource: A5 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A5-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testGroupAdd(self):
        # see also BundleGroup
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A4 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A5 ocf:heartbeat:Dummy"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A6 ocf:heartbeat:Dummy --group"
        )
        assert r == 1
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A6 ocf:heartbeat:Dummy --group Dgroup"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A7 ocf:heartbeat:Dummy --group Dgroup"
        )
        assert r == 0

        o,r = pcs(temp_cib, "resource group add MyGroup A1 B1")
        assert r == 1
        ac(o,'Error: Unable to find resource: B1\n')

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"""\
 A1\t(ocf::heartbeat:Dummy):\tStopped
 A2\t(ocf::heartbeat:Dummy):\tStopped
 A3\t(ocf::heartbeat:Dummy):\tStopped
 A4\t(ocf::heartbeat:Dummy):\tStopped
 A5\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: Dgroup
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
""")

        o,r = pcs(temp_cib, "resource delete A6")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A7")
        assert r == 0

        o,r = pcs(temp_cib, "resource group add MyGroup A1 A2 A3")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource group add MyGroup A1 A2 A3")
        assert r == 1
        ac(o,'Error: A1 already exists in MyGroup\n')

        o,r = pcs(temp_cib, "resource group add MyGroup2 A3 A4 A5")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"""\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")

        o, r = pcs(
            temp_cib,
            "resource create --no-default-ops A6 ocf:heartbeat:Dummy"
        )
        self.assertEqual(0, r)

        o, r = pcs(
            temp_cib,
            "resource create --no-default-ops A7 ocf:heartbeat:Dummy"
        )
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --after A1")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A7 --before A1")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A7\t(ocf::heartbeat:Dummy):\tStopped
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A6 --before A5")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A7 --after A5")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 A7 --before A2")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A6 A7 --after A4")
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --before A0")
        ac(o, "Error: there is no resource 'A0' in the group 'MyGroup'\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --after A0")
        ac(o, "Error: there is no resource 'A0' in the group 'MyGroup'\n")
        self.assertEqual(1, r)

        o, r = pcs(
            temp_cib,
            "resource group add MyGroup A6 --after A1 --before A2"
        )
        ac(o, "Error: you cannot specify both --before and --after\n")
        self.assertEqual(1, r)

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A8 ocf:heartbeat:Dummy --group MyGroup --before A1"
        )
        ac(o, "")
        self.assertEqual(0, r)

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A9 ocf:heartbeat:Dummy --group MyGroup --after A1"
        )
        ac(o, "")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A8\t(ocf::heartbeat:Dummy):\tStopped
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A9\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A1 --before A8")
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --after A6")
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A8\t(ocf::heartbeat:Dummy):\tStopped
     A9\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: MyGroup2
     A4\t(ocf::heartbeat:Dummy):\tStopped
     A6\t(ocf::heartbeat:Dummy):\tStopped
     A3\t(ocf::heartbeat:Dummy):\tStopped
     A7\t(ocf::heartbeat:Dummy):\tStopped
     A5\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --after A3")
        self.assertEqual(1, r)
        ac(o, "Error: cannot put resource after itself\n")

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --before A3")
        self.assertEqual(1, r)
        ac(o, "Error: cannot put resource before itself\n")

        o, r = pcs(temp_cib, "resource group add A7 A6")
        ac(o, "Error: 'A7' is already a resource\n")
        self.assertEqual(1, r)

        o, r = pcs(
            temp_cib,
            "resource create --no-default-ops A0 ocf:heartbeat:Dummy --clone"
        )
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add A0-clone A6")
        ac(o, "Error: 'A0-clone' is already a clone resource\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "resource unclone A0-clone")
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource master A0")
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add A0-master A6")
        ac(o, "Error: 'A0-master' is already a master/slave resource\n")
        self.assertEqual(1, r)

        output, returnVal = pcs(temp_large_cib, "resource group add dummyGroup dummy1")
        assert returnVal == 0
        ac(output, '')

        output, returnVal = pcs(temp_cib, "resource group add group:dummy dummy1")
        assert returnVal == 1
        ac(output, "Error: invalid group name 'group:dummy', ':' is not a valid character for a group name\n")

    def testGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group) - dummylarge
            """
        ))
        assert returnVal == 0

    def testGroupOrder(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops A ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops B ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops C ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops E ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops F ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops G ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops H ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops I ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops J ocf:heartbeat:Dummy"
        )
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops K ocf:heartbeat:Dummy"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource group add RGA A B C E D K J I"
        )
        assert returnVal == 0
        assert output == "",output

        output, returnVal = pcs(temp_cib, "resource")
        assert returnVal == 0
        ac(output, """\
 F\t(ocf::heartbeat:Dummy):\tStopped
 G\t(ocf::heartbeat:Dummy):\tStopped
 H\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: RGA
     A\t(ocf::heartbeat:Dummy):\tStopped
     B\t(ocf::heartbeat:Dummy):\tStopped
     C\t(ocf::heartbeat:Dummy):\tStopped
     E\t(ocf::heartbeat:Dummy):\tStopped
     D\t(ocf::heartbeat:Dummy):\tStopped
     K\t(ocf::heartbeat:Dummy):\tStopped
     J\t(ocf::heartbeat:Dummy):\tStopped
     I\t(ocf::heartbeat:Dummy):\tStopped
""")

        output, returnVal = pcs(temp_cib, "resource group list")
        ac(output, "RGA: A B C E D K J I\n")
        assert returnVal == 0

    def testRemoveLastResourceFromGroup(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d1 ocf:heartbeat:Dummy --group gr1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d2 ocf:heartbeat:Dummy --group gr2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: gr1
     d1\t(ocf::heartbeat:Dummy):\tStopped
 Resource Group: gr2
     d2\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr1 d2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: gr1
     d1\t(ocf::heartbeat:Dummy):\tStopped
     d2\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, returnVal)

    def testRemoveLastResourceFromClonedGroup(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d1 ocf:heartbeat:Dummy --group gr1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d2 ocf:heartbeat:Dummy --group gr2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone gr2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: gr1
     d1\t(ocf::heartbeat:Dummy):\tStopped
 Clone Set: gr2-clone [gr2]
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr1 d2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: gr1
     d1\t(ocf::heartbeat:Dummy):\tStopped
     d2\t(ocf::heartbeat:Dummy):\tStopped
""")
        self.assertEqual(0, returnVal)

    def testRemoveLastResourceFromMasteredGroup(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d1 ocf:heartbeat:Dummy --group gr1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops d2 ocf:heartbeat:Dummy --group gr2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master gr2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, outdent("""\
             Resource Group: gr1
                 d1\t(ocf::heartbeat:Dummy):\tStopped
             Master/Slave Set: gr2-master [gr2]
            """
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr1 d2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show")
        ac(output, outdent("""\
             Resource Group: gr1
                 d1\t(ocf::heartbeat:Dummy):\tStopped
                 d2\t(ocf::heartbeat:Dummy):\tStopped
            """
        ))
        self.assertEqual(0, returnVal)

    def testClusterConfig(self):
        self.setupClusterA(temp_cib)

        self.assert_pcs_success("config",outdent("""\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
             Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.96
              Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)
             Group: TestGroup1
              Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
             Group: TestGroup2
              Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.92
               Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)
              Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.93
               Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)
             Clone: ClusterIP4-clone
              Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.94
               Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)
             Master: Master
              Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.95
               Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)

            Stonith Devices:
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

    def testCloneRemove(self):
        o,r = pcs(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --clone"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location D1-clone prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o,r = pcs("constraint location D1 prefers rh7-1 --force")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Clone: D1-clone
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )
        # self.assert_pcs_success("resource --full", outdent(
        #     """\
        #      Clone: D1-clone
        #       Resource: D1 (class=ocf provider=heartbeat type=Dummy)
        #        Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
        #     """
        # ))

        self.assert_pcs_success("resource delete D1-clone", outdent(
            """\
            Removing Constraint - location-D1-clone-rh7-1-INFINITY
            Removing Constraint - location-D1-rh7-1-INFINITY
            Deleting Resource - D1
            """
        ))

        o,r = pcs("resource --full")
        assert r == 0
        ac(o,"")

        o, r = pcs(
            "resource create d99 ocf:heartbeat:Dummy clone globally-unique=true"
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource delete d99",
            "Deleting Resource - d99\n"
        )

        output, returnVal = pcs(temp_large_cib, "resource clone dummylarge")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummylarge")
        ac(output, 'Deleting Resource - dummylarge\n')
        assert returnVal == 0

    def testCloneGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource clone dummies")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group and clone) - dummylarge
            """
        ))
        assert returnVal == 0

    def testMasterSlaveRemove(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1 --force")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location Master prefers rh7-2")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        self.assert_pcs_success("resource delete Master", outdent(
            """\
            Removing Constraint - location-Master-rh7-2-INFINITY
            Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
            Deleting Resource - ClusterIP5
            """
        ))

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        self.assert_pcs_success("resource delete ClusterIP5", outdent(
            """\
            Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
            Removing Constraint - location-ClusterIP5-rh7-2-INFINITY
            Deleting Resource - ClusterIP5
            """
        ))

        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.95 op monitor interval=30s"
        )

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        assert returnVal == 0

        self.assert_pcs_success("config", outdent(
            """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
             Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.96
              Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)
             Group: TestGroup1
              Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
             Group: TestGroup2
              Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.92
               Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)
              Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.93
               Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)
             Clone: ClusterIP4-clone
              Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.94
               Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)
             Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.95
              Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)

            Stonith Devices:
            Fencing Levels:

            Location Constraints:
              Resource: ClusterIP5
                Enabled on: rh7-1 (score:INFINITY) (id:location-ClusterIP5-rh7-1-INFINITY)
                Enabled on: rh7-2 (score:INFINITY) (id:location-ClusterIP5-rh7-2-INFINITY)
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

        output, returnVal = pcs(temp_large_cib, "resource master dummylarge")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummylarge")
        ac(output, 'Deleting Resource - dummylarge\n')
        assert returnVal == 0

    def testMasterSlaveGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource master dummies")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group and M/S) - dummylarge
            """
        ))
        assert returnVal == 0

    def testMSGroup(self):
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource group add Group D0 D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource master GroupMaster Group")
        assert returnVal == 0
        assert output == "", [output]

        self.assert_pcs_success(
            "resource --full", stdout_regexp=re.compile(outdent(
                """\
                 Master: GroupMaster
                  Group: Group
                   Resource: D0 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(D0-monitor-interval-10s?\\)
                   Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success(
            "resource delete D0",
            "Deleting Resource - D0\n"
        )

        self.assert_pcs_success(
            "resource delete D1",
            "Deleting Resource (and group and M/S) - D1\n"
        )

    def testUncloneWithConstraints(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:pacemaker:Dummy"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint location D0-clone prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o,r = pcs(temp_cib, "constraint")
        ac(o,"Location Constraints:\n  Resource: D0-clone\n    Enabled on: rh7-1 (score:INFINITY)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource unclone D0-clone")
        ac(o,"")
        assert r == 0

    def testUnclone(self):
        # see also BundleCloneMaster
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy1 ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy2 ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # try to unclone a non-cloned resource
        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "Error: 'dummy1' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "Error: 'gr' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        # unclone with a cloned primitive specified
        output, returnVal = pcs(temp_cib, "resource clone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Group: gr
                  Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                 Clone: dummy2-clone
                  Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Group: gr
                  Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                 Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        # unclone with a clone itself specified
        output, returnVal = pcs(temp_cib, "resource group add gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: gr-clone
                  Group: gr
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(temp_cib, "resource unclone gr-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Group: gr
                  Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                  Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        # unclone with a cloned group specified
        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: gr-clone
                  Group: gr
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Group: gr
                  Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                  Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: gr-clone
                  Group: gr
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: gr-clone
                  Group: gr
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                 Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)$
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)$
                 Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testUncloneMaster(self):
        # see also BundleCloneMaster
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10 to 11 to make the operation unique\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10 to 11 to make the operation unique\n"
        )

        # try to unclone a non-cloned resource
        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "Error: 'dummy1' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "Error: 'gr' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        # unclone with a cloned primitive specified
        output, returnVal = pcs(temp_cib, "resource master dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
             Master: dummy2-master
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                          monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a clone itself specified
        output, returnVal = pcs(temp_cib, "resource group add gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Master: gr-master
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr-master")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a cloned group specified
        output, returnVal = pcs(temp_cib, "resource master gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Master: gr-master
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(temp_cib, "resource ungroup gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                          monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
             Master: gr-master
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                          monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
             Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                          monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource group add gr dummy1 dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Master: gr-master
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "Error: Groups that have more than one resource and are master/slave resources cannot be removed.  The group may be deleted with 'pcs resource delete gr'.\n")
        self.assertEqual(1, returnVal)

        self.assert_pcs_success("resource --full", outdent(
            """\
             Master: gr-master
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy1-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10 role=Master timeout=20 (dummy2-monitor-interval-10)
                            monitor interval=11 role=Slave timeout=20 (dummy2-monitor-interval-11)
            """
        ))

    def testCloneGroupMember(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy --group AG"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group AG"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o,"""\
 Resource Group: AG
     D1\t(ocf::heartbeat:Dummy):\tStopped
 Clone Set: D0-clone [D0]
""")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Clone Set: D0-clone [D0]\n Clone Set: D1-clone [D1]\n")
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group AG2"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy --group AG2"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource master D2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o,"""\
 Clone Set: D0-clone [D0]
 Clone Set: D1-clone [D1]
 Resource Group: AG2
     D3\t(ocf::heartbeat:Dummy):\tStopped
 Master/Slave Set: D2-master [D2]
""")
        assert r == 0

        o,r = pcs(temp_cib, "resource master D3")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Clone Set: D0-clone [D0]\n Clone Set: D1-clone [D1]\n Master/Slave Set: D2-master [D2]\n Master/Slave Set: D3-master [D3]\n")
        assert r == 0

    def testCloneMaster(self):
        # see also BundleCloneMaster
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource clone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource unclone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource clone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource master D1-master-custom D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource master D2")
        assert returnVal == 0
        assert output == "", [output]

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Clone: D0-clone
                  Resource: D0 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D0-monitor-interval-10s?\\)
                 Master: D1-master-custom
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                 Master: D2-master
                  Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success(
            "resource delete D0",
            "Deleting Resource - D0\n"
        )

        self.assert_pcs_success(
            "resource delete D2",
            "Deleting Resource - D2\n"
        )

        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
        )
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy"
        )

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Master: D1-master-custom
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                 Resource: D0 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D0-monitor-interval-10s?\\)
                 Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testLSBResource(self):
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.assert_pcs_fail(
            "resource create --no-default-ops D2 lsb:network foo=bar",
            "Error: invalid resource option 'foo', there are no options"
                " allowed, use --force to override\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 lsb:network foo=bar --force",
            "Warning: invalid resource option 'foo', there are no options"
                " allowed\n"
        )

        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: D2 (class=lsb type=network)
                  Attributes: foo=bar
                  Operations: monitor interval=15 timeout=15 (D2-monitor-interval-15)
                """
            )
        )

        self.assert_pcs_fail(
            "resource update D2 bar=baz",
            "Error: invalid resource option 'bar', there are no options"
                " allowed, use --force to override\n"
        )

        self.assert_pcs_success(
            "resource update D2 bar=baz --force",
            "Warning: invalid resource option 'bar', there are no options"
                " allowed\n"
        )

        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: D2 (class=lsb type=network)
                  Attributes: bar=baz foo=bar
                  Operations: monitor interval=15 timeout=15 (D2-monitor-interval-15)
                """
            )
        )

    def testResourceMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib

        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_fail_regardless_of_force(
            "resource move",
            "Error: must specify a resource to move\n"
        )
        self.assert_pcs_fail_regardless_of_force(
            "resource ban",
            "Error: must specify a resource to ban\n"
        )
        self.assert_pcs_fail_regardless_of_force(
            "resource clear",
            "Error: must specify a resource to clear\n"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy")
        ac(output, """\
Error: You must specify a node when moving/banning a stopped resource
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy rh7-1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy
    Enabled on: rh7-1 (score:INFINITY) (role: Started) (id:cli-prefer-dummy)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        output, returnVal = pcs(temp_cib, "resource ban dummy rh7-1")
        ac(output, """\
Warning: Creating location constraint cli-ban-dummy-on-rh7-1 with a score of -INFINITY for resource dummy on node rh7-1.
This will prevent dummy from running on rh7-1 until the constraint is removed. This will be the case even if rh7-1 is the last node in the cluster.
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy
    Disabled on: rh7-1 (score:-INFINITY) (role: Started) (id:cli-ban-dummy-on-rh7-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        output, returnVal = pcs(
            temp_cib, "resource move dummy rh7-1 lifetime=1H"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ", "{datetime}", output)
        ac(output, """\
Location Constraints:
  Resource: dummy
    Constraint: cli-prefer-dummy
      Rule: boolean-op=and score=INFINITY  (id:cli-prefer-rule-dummy)
        Expression: #uname eq string rh7-1  (id:cli-prefer-expr-dummy)
        Expression: date lt {datetime}  (id:cli-prefer-lifetime-end-dummy)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        output, returnVal = pcs(
            temp_cib, "resource ban dummy rh7-1 lifetime=P1H"
        )
        ac(output, """\
Warning: Creating location constraint cli-ban-dummy-on-rh7-1 with a score of -INFINITY for resource dummy on node rh7-1.
This will prevent dummy from running on rh7-1 until the constraint is removed. This will be the case even if rh7-1 is the last node in the cluster.
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ", "{datetime}", output)
        ac(output, """\
Location Constraints:
  Resource: dummy
    Constraint: cli-ban-dummy-on-rh7-1
      Rule: boolean-op=and score=-INFINITY  (id:cli-ban-dummy-on-rh7-1-rule)
        Expression: #uname eq string rh7-1  (id:cli-ban-dummy-on-rh7-1-expr)
        Expression: date lt {datetime}  (id:cli-ban-dummy-on-rh7-1-lifetime)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban dummy rh7-1 rh7-1")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource ban dummy rh7-1 lifetime=1H lifetime=1H"
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy rh7-1 --master")
        ac(output, """\
Error: when specifying --master you must use the master id
""")
        self.assertEqual(1, returnVal)

    def testCloneMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib
        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --clone"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone rh7-1")
        ac(output, """\
Warning: Creating location constraint cli-ban-DG-clone-on-rh7-1 with a score of -INFINITY for resource DG-clone on node rh7-1.
This will prevent DG-clone from running on rh7-1 until the constraint is removed. This will be the case even if rh7-1 is the last node in the cluster.
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: DG-clone
    Disabled on: rh7-1 (score:-INFINITY) (role: Started) (id:cli-ban-DG-clone-on-rh7-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

    def testNoMoveMSClone(self):
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --clone"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --master"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource move D1")
        assert returnVal == 1
        assert output == "Error: cannot move cloned resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D1-clone")
        assert returnVal == 1
        assert output == "Error: cannot move cloned resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2")
        assert returnVal == 1
        assert output == "Error: to move Master/Slave resources you must use --master and the master id (D2-master)\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2 --master")
        ac(output,"Error: when specifying --master you must use the master id (D2-master)\n")
        assert returnVal == 1

        self.assert_pcs_fail(
            "resource move D2-master --master",
            # pacemaker 1.1.18 changes --host to --node
            stdout_regexp=re.compile("^"
                "Error: error moving/banning/clearing resource\n"
                "Resource 'D2-master' not moved: active in 0 locations "
                    "\(promoted in 0\).\n"
                "You can prevent 'D2-master' from running on a specific "
                    "location with: --ban --(host|node) <name>\n"
                "You can prevent 'D2-master' from being promoted at a specific "
                    "location with: --ban --master --(host|node) <name>\n"
                "Error performing operation: Invalid argument\n\n"
                "$", re.MULTILINE
            )
        )

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: D0 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D0-monitor-interval-10s?\\)
                 Clone: D1-clone
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                 Master: D2-master
                  Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testMasterOfGroupMove(self):
        o,r = pcs(
            "resource create stateful ocf:pacemaker:Stateful --group group1"
        )
        ac(o, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        assert r == 0

        o,r = pcs("resource master group1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_fail(
            "resource move group1-master --master",
            # pacemaker 1.1.18 changes --host to --node
            stdout_regexp=re.compile("^"
                "Error: error moving/banning/clearing resource\n"
                "Resource 'group1-master' not moved: active in 0 locations "
                    "\(promoted in 0\).\n"
                "You can prevent 'group1-master' from running on a specific "
                    "location with: --ban --(host|node) <name>\n"
                "You can prevent 'group1-master' from being promoted at a "
                    "specific location with: --ban --master --(host|node) "
                    "<name>\n"
                "Error performing operation: Invalid argument\n\n"
                "$", re.MULTILINE
            )
        )

    def testDebugStartCloneGroup(self):
        o,r = pcs("resource create D0 ocf:heartbeat:Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D1 ocf:heartbeat:Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D2 ocf:heartbeat:Dummy --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D3 ocf:heartbeat:Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource debug-start DGroup")
        ac(o,"Error: unable to debug-start a group, try one of the group's resource(s) (D0,D1)\n")
        assert r == 1

        o,r = pcs("resource debug-start D2-clone")
        ac(o,"Error: unable to debug-start a clone, try the clone's resource: D2\n")
        assert r == 1

        o,r = pcs("resource debug-start D3-master")
        ac(o,"Error: unable to debug-start a master, try the master's resource: D3\n")
        assert r == 1

    def testGroupCloneCreation(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup"
        )
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource clone DGroup1")
        ac(o,"Error: unable to find group or resource: DGroup1\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource clone DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Clone Set: DGroup-clone [DGroup]\n")

        o,r = pcs(temp_cib, "resource clone DGroup")
        ac(o,"Error: cannot clone a group that has already been cloned\n")
        assert r == 1

    def testGroupRemoveWithConstraints1(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib

        o,r = utils.run(["cibadmin","-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(o,"")
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup"
        )
        assert r == 0
        ac(o,"")

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DGroup"
        )
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"""\
 Resource Group: DGroup
     D1\t(ocf::heartbeat:Dummy):\tStopped
     D2\t(ocf::heartbeat:Dummy):\tStopped
""")

        o,r = pcs(temp_cib, "resource move DGroup rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint")
        assert r == 0
        ac(o,"Location Constraints:\n  Resource: DGroup\n    Enabled on: rh7-1 (score:INFINITY) (role: Started)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")

        self.assert_pcs_success(
            "resource delete D1",
            "Deleting Resource - D1\n"
        )

        self.assert_pcs_success("resource delete D2", outdent(
            """\
            Removing Constraint - cli-prefer-DGroup
            Deleting Resource (and group) - D2
            """
        ))

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"NO resources configured\n")

    def testResourceCloneCreation(self):
        #resource "dummy1" is already in "temp_large_cib
        output, returnVal = pcs(temp_large_cib, "resource clone dummy1")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource unclone dummy1")
        ac(output, '')
        assert returnVal == 0

    def testResourceCloneId(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy-clone ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: dummy-clone \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy-clone-monitor-interval-10s?\\)
                 Clone: dummy-clone-1
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success(
            "resource delete dummy",
            "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy --clone"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: dummy-clone \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy-clone-monitor-interval-10s?\\)
                 Clone: dummy-clone-1
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testResourceMasterId(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy-master ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: dummy-master \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy-master-monitor-interval-10s?\\)
                 Master: dummy-master-1
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        output, returnVal = pcs(temp_cib, "resource unclone dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource master dummy-master dummy")
        ac(output, "Error: dummy-master already exists in the cib\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource master dummy-master0 dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: dummy-master \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy-master-monitor-interval-10s?\\)
                 Master: dummy-master0
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success(
            "resource delete dummy",
            "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy --master"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: dummy-master \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(dummy-master-monitor-interval-10s?\\)
                 Master: dummy-master-1
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testResourceCloneUpdate(self):
        o, r  = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --clone"
        )
        assert r == 0
        ac(o, "")

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: D1-clone
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o, r = pcs(temp_cib, 'resource update D1-clone foo=bar')
        ac(o, "")
        self.assertEqual(0, r)

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: D1-clone
                  Meta Attrs: foo=bar
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success("resource update D1-clone bar=baz")

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: D1-clone
                  Meta Attrs: bar=baz foo=bar
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o, r = pcs(temp_cib, 'resource update D1-clone foo=')
        assert r == 0
        ac(o, "")

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: D1-clone
                  Meta Attrs: bar=baz
                  Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testGroupRemoveWithConstraints2(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG"
        )
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG"
        )
        assert r == 0

        o,r = pcs(temp_cib, "constraint location AG prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"Removing Constraint - location-AG-rh7-1-INFINITY\n")
        assert r == 0

        self.assert_pcs_success(
            "resource --full", stdout_regexp=re.compile(outdent(
                """\
                 Resource: A \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(A-monitor-interval-10s?\\)
                 Resource: B \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(B-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AA"
        )
        assert r == 0
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AA"
        )
        assert r == 0
        o,r = pcs(temp_cib, "resource master AA")
        assert r == 0
        o,r = pcs(temp_cib, "constraint location AA-master prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        self.assert_pcs_success(
            "resource delete A1",
            "Deleting Resource - A1\n"
        )

        self.assert_pcs_success("resource delete A2", outdent(
            """\
            Removing Constraint - location-AA-master-rh7-1-INFINITY
            Deleting Resource (and group and M/S) - A2
            """
        ))

    def testMasteredGroup(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG"
        )
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG"
        )
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops C ocf:heartbeat:Dummy --group AG"
        )
        assert r == 0

        o,r = pcs(temp_cib, "resource master AGMaster AG")
        assert r == 0

        self.assert_pcs_fail(
            "resource create --no-default-ops A ocf:heartbeat:Dummy",
            "Error: 'A' already exists\n"
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops AG ocf:heartbeat:Dummy",
            "Error: 'AG' already exists\n"
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops AGMaster ocf:heartbeat:Dummy",
            "Error: 'AGMaster' already exists\n"
        )

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"Error: Groups that have more than one resource and are master/slave resources cannot be removed.  The group may be deleted with 'pcs resource delete AG'.\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource delete B")
        assert r == 0
        o,r = pcs(temp_cib, "resource delete C")
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Master: AGMaster
                  Resource: A \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(A-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testClonedGroup(self):
        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Clone: DG-clone
                  Group: DG
                   Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                   Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )
        # self.assert_pcs_success("resource show --full", outdent(
        #     """\
        #      Clone: DG-clone
        #       Group: DG
        #        Resource: D1 (class=ocf provider=heartbeat type=Dummy)
        #         Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
        #        Resource: D2 (class=ocf provider=heartbeat type=Dummy)
        #         Operations: monitor interval=10 timeout=20 (D2-monitor-interval-10)
        #     """
        # ))

        self.assert_pcs_fail(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy",
            "Error: 'D1' already exists\n"
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG ocf:heartbeat:Dummy",
            "Error: 'DG' already exists\n"
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG-clone ocf:heartbeat:Dummy",
            "Error: 'DG-clone' already exists\n"
        )

        output, returnVal = pcs(temp_cib, "resource ungroup DG")
        ac(output, """\
Error: Cannot remove more than one resource from cloned group
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ungroup DG D1 D2")
        ac(output, """\
Error: Cannot remove more than one resource from cloned group
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ungroup DG D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Clone: DG-clone
                  Group: DG
                   Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                 Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )
        # self.assert_pcs_success("resource show --full", outdent(

        output, returnVal = pcs(temp_cib, "resource ungroup DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource show --full", stdout_regexp=re.compile(outdent(
                """\
                 Clone: DG-clone
                  Resource: D2 \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(D2-monitor-interval-10s?\\)
                 Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testResourceEnable(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.

        # see also BundleMiscCommands
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0

        # primitive resource
        o,r = pcs(temp_cib, "resource disable D1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show D1",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show D1",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: D1 \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(D1-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )
        # self.assert_pcs_success("resource show D1", outdent(
        #     """\
        #      Resource: D1 (class=ocf provider=heartbeat type=Dummy)
        #       Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
        #     """
        # ))

        # bad resource name
        o,r = pcs(temp_cib, "resource enable NoExist")
        ac(o,"Error: bundle/clone/group/master/resource 'NoExist' does not exist\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource disable NoExist")
        ac(o,"Error: bundle/clone/group/master/resource 'NoExist' does not exist\n")
        assert r == 1

        # cloned group
        output, retVal = pcs(
            temp_cib,
            "resource create dummy0 ocf:heartbeat:Dummy --group group0"
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource clone group0")
        ac(output, "")
        assert retVal == 0
        self.assert_pcs_success(
            "resource show group0-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: group0-clone
                  Group: group0
                   Resource: dummy0 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: migrate_from interval=0s timeout=20s? \\(dummy0-migrate_from-interval-0s\\)
                                migrate_to interval=0s timeout=20s? \\(dummy0-migrate_to-interval-0s\\)
                                monitor interval=10s? timeout=20s? \\(dummy0-monitor-interval-10s?\\)
                                reload interval=0s timeout=20s? \\(dummy0-reload-interval-0s\\)
                                start interval=0s timeout=20s? \\(dummy0-start-interval-0s\\)
                                stop interval=0s timeout=20s? \\(dummy0-stop-interval-0s\\)
                """), re.MULTILINE
            )
        )
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource disable group0")
        ac(output, "")
        assert retVal == 0

    def testResourceEnableUnmanaged(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.

        # see also BundleMiscCommands
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0

        # unmanaged resource - by meta attribute
        o,r = pcs(temp_cib, "resource unmanage D2")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D2")
        ac(o,"Warning: 'D2' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D2")
        ac(o,"Warning: 'D2' is unmanaged\n")
        assert r == 0

        # unmanaged resource - by cluster property
        o,r = pcs(temp_cib, "property set is-managed-default=false")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "property set is-managed-default=")
        ac(o,"")
        assert r == 0

        # resource in an unmanaged group
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0
        o,r = pcs("resource group add DG D3")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource unmanage DG")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D3")
        ac(o,"Warning: 'D3' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D3")
        ac(o,"Warning: 'D3' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource manage DG")
        ac(o,"")
        assert r == 0

        # unmanaged resource in a group
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D4 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0
        o,r = pcs("resource group add DG D4")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource unmanage D4")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource manage D4")
        ac(o,"")
        assert r == 0

    def testResourceEnableClone(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.
        output, retVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy --clone"
        )
        ac(output, "")
        self.assertEqual(retVal, 0)

        # disable primitive, enable clone
        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        # disable clone, enable primitive
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        # disable both primitive and clone, enable clone
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        # disable both primitive and clone, enable primitive
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        # disable via 'resource disable', enable via 'resource meta'
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Meta Attrs: target-role=Stopped
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        output, retVal = pcs(temp_cib, "resource meta dummy-clone target-role=")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        # disable via 'resource meta', enable via 'resource enable'
        output, retVal = pcs(
            temp_cib, "resource meta dummy-clone target-role=Stopped"
        )
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Meta Attrs: target-role=Stopped
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        output, retVal = pcs(temp_cib, "resource enable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

    def testResourceEnableMaster(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:pacemaker:Stateful --master",
            "Warning: changing a monitor operation interval from 10 to 11 to make the operation unique\n"
        )

        # disable primitive, enable master
        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable master, enable primitive
        output, retVal = pcs(temp_cib, "resource disable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable both primitive and master, enable master
        output, retVal = pcs(temp_cib, "resource disable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable both primitive and master, enable primitive
        output, retVal = pcs(temp_cib, "resource disable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable via 'resource disable', enable via 'resource meta'
        output, retVal = pcs(temp_cib, "resource disable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Meta Attrs: target-role=Stopped
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        output, retVal = pcs(temp_cib, "resource meta dummy-master target-role=")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable via 'resource meta', enable via 'resource enable'
        output, retVal = pcs(
            temp_cib, "resource meta dummy-master target-role=Stopped"
        )
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Meta Attrs: target-role=Stopped
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        output, retVal = pcs(temp_cib, "resource enable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource show dummy-master", outdent(
            """\
             Master: dummy-master
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

    def test_resource_enable_more_resources(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pacemaker:Dummy"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pacemaker:Dummy"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy3 ocf:pacemaker:Dummy"
        )
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_success("resource disable dummy1 dummy2")
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_success("resource disable dummy2 dummy3")
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_success("resource enable dummy1 dummy2")
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_fail_regardless_of_force(
            "resource enable dummy3 dummyX",
            "Error: bundle/clone/group/master/resource 'dummyX' does not exist\n"
        )
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

        self.assert_pcs_fail_regardless_of_force(
            "resource disable dummy1 dummyX",
            "Error: bundle/clone/group/master/resource 'dummyX' does not exist\n"
        )
        self.assert_pcs_success(
            "resource show --full",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy1-monitor-interval-10)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10 timeout=20 (dummy2-monitor-interval-10)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10 timeout=20 (dummy3-monitor-interval-10)
                """
            )
        )

    def testOPOption(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops B ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update B ocf:heartbeat:Dummy op monitor interval=30s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops C ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add C monitor interval=30s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        output, returnVal = pcs(
            temp_cib,
            "resource op add C monitor interval=60 role=role"
        )
        ac(output, """\
Error: role must be: Stopped, Started, Slave or Master (use --force to override)
""")
        assert returnVal == 1

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: B \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(B-monitor-interval-10s?\\)
                 Resource: C \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(C-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource update B op monitor interval=30s monitor interval=31s role=master")
        ac(o,"Error: role must be: Stopped, Started, Slave or Master (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource update B op monitor interval=30s monitor interval=31s role=Master")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource show --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: B \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=30s \\(B-monitor-interval-30s\\)
                              monitor interval=31s role=Master \\(B-monitor-interval-31s\\)
                 Resource: C \\(class=ocf provider=heartbeat type=Dummy\\)
                  Operations: monitor interval=10s? timeout=20s? \\(C-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        o,r = pcs(temp_cib, "resource update B op interval=5s")
        ac(o,"Error: interval=5s does not appear to be a valid operation action\n")
        assert r == 1

    def testCloneMasterBadResources(self):
        self.setupClusterA(temp_cib)
        o,r = pcs("resource clone ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs("resource clone ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a master/slave resource\n")
        assert r == 1

        o,r = pcs("resource master ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs("resource master ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a master/slave resource\n")
        assert r == 1

    def groupMSAndClone(self):
        o,r = pcs(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --clone"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --master"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs("resource group add DG D1")
        ac(o,"Error: cannot group clone resources\n")
        assert r == 1

        o,r = pcs("resource group add DG D2")
        ac(o,"Error: cannot group master/slave resources\n")
        assert r == 1

        o,r = pcs("resource create --no-default-ops D3 ocf:heartbeat:Dummy --master --group xxx --clone")
        ac(o,"Warning: --group ignored when creating a clone\nWarning: --master ignored when creating a clone\n")
        assert r == 0

        o,r = pcs("resource create --no-default-ops D4 ocf:heartbeat:Dummy --master --group xxx")
        ac(o,"Warning: --group ignored when creating a master\n")
        assert r == 0

    def testResourceCloneGroup(self):
        o,r = pcs(
            "resource create --no-default-ops dummy0 ocf:heartbeat:Dummy --group group"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs("resource clone group")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource delete dummy0",
            "Deleting Resource (and group and clone) - dummy0\n"
        )

    def testResourceMissingValues(self):
        self.assert_pcs_success(
            "resource create --no-default-ops myip IPaddr2 --force",
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from 'IPaddr2')
                Warning: required resource option 'ip' is missing
                """
            )
        )
        self.assert_pcs_success(
            "resource create --no-default-ops myip2 IPaddr2 ip=3.3.3.3",
            "Assumed agent name 'ocf:heartbeat:IPaddr2'"
                " (deduced from 'IPaddr2')\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops myfs Filesystem --force",
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')
                Warning: required resource options 'device', 'directory', 'fstype' are missing
                """
            )
        )

        self.assert_pcs_success(
            "resource create --no-default-ops myfs2 Filesystem device=x"
                " directory=y --force"
            ,
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')
                Warning: required resource option 'fstype' is missing
                """
            )
        )

        self.assert_pcs_success(
            "resource create --no-default-ops myfs3 Filesystem device=x"
                " directory=y fstype=z"
            ,
            "Assumed agent name 'ocf:heartbeat:Filesystem'"
                " (deduced from 'Filesystem')\n"
        )

        self.assert_pcs_success(
            "resource --full",
            stdout_regexp=re.compile(outdent(
                """\
                 Resource: myip \\(class=ocf provider=heartbeat type=IPaddr2\\)
                  Operations: monitor interval=10s timeout=20s \\(myip-monitor-interval-10s\\)
                 Resource: myip2 \\(class=ocf provider=heartbeat type=IPaddr2\\)
                  Attributes: ip=3.3.3.3
                  Operations: monitor interval=10s timeout=20s \\(myip2-monitor-interval-10s\\)
                 Resource: myfs \\(class=ocf provider=heartbeat type=Filesystem\\)
                  Operations: monitor interval=20s? timeout=40s? \\(myfs-monitor-interval-20s?\\)
                 Resource: myfs2 \\(class=ocf provider=heartbeat type=Filesystem\\)
                  Attributes: device=x directory=y
                  Operations: monitor interval=20s? timeout=40s? \\(myfs2-monitor-interval-20s?\\)
                 Resource: myfs3 \\(class=ocf provider=heartbeat type=Filesystem\\)
                  Attributes: device=x directory=y fstype=z
                  Operations: monitor interval=20s? timeout=40s? \\(myfs3-monitor-interval-20s?\\)
                """), re.MULTILINE
            )
        )

    def testClonedMasteredGroup(self):
        output, retVal = pcs(
            temp_cib,
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            temp_cib,
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            temp_cib,
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource clone dummies")
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource show dummies-clone", stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummies-clone
                  Group: dummies
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                   Resource: dummy3 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy3-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        output, retVal = pcs(temp_cib, "resource unclone dummies-clone")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: dummies
     dummy1\t(ocf::heartbeat:Dummy):\tStopped
     dummy2\t(ocf::heartbeat:Dummy):\tStopped
     dummy3\t(ocf::heartbeat:Dummy):\tStopped
""")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource clone dummies")
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource show dummies-clone", stdout_regexp=re.compile(outdent(
                """\
                 Clone: dummies-clone
                  Group: dummies
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                   Resource: dummy3 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy3-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success("resource delete dummies-clone", outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and clone) - dummy3
            """
        ))
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, "NO resources configured\n")
        assert retVal == 0

        output, retVal = pcs(
            temp_cib,
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            temp_cib,
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            temp_cib,
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies"
        )
        ac(output, "")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource master dummies")
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource show dummies-master", stdout_regexp=re.compile(outdent(
                """\
                 Master: dummies-master
                  Group: dummies
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                   Resource: dummy3 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy3-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        output, retVal = pcs(temp_cib, "resource unclone dummies-master")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, """\
 Resource Group: dummies
     dummy1\t(ocf::heartbeat:Dummy):\tStopped
     dummy2\t(ocf::heartbeat:Dummy):\tStopped
     dummy3\t(ocf::heartbeat:Dummy):\tStopped
""")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource master dummies")
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource show dummies-master", stdout_regexp=re.compile(outdent(
                """\
                 Master: dummies-master
                  Group: dummies
                   Resource: dummy1 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy1-monitor-interval-10s?\\)
                   Resource: dummy2 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy2-monitor-interval-10s?\\)
                   Resource: dummy3 \\(class=ocf provider=heartbeat type=Dummy\\)
                    Operations: monitor interval=10s? timeout=20s? \\(dummy3-monitor-interval-10s?\\)
                """), re.MULTILINE
            )
        )

        self.assert_pcs_success("resource delete dummies-master", outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and M/S) - dummy3
            """
        ))
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, "NO resources configured\n")
        assert retVal == 0

    def test_relocate_stickiness(self):
        output, retVal = pcs(
            temp_cib, "resource create D1 ocf:pacemaker:Dummy --no-default-ops"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(
            temp_cib,
            "resource create DG1 ocf:pacemaker:Dummy --no-default-ops --group GR"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(
            temp_cib,
            "resource create DG2 ocf:pacemaker:Dummy --no-default-ops --group GR"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(
            temp_cib,
            "resource create DC ocf:pacemaker:Dummy --no-default-ops --clone"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(
            temp_cib,
            "resource create DGC1 ocf:pacemaker:Dummy --no-default-ops --group GRC"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(
            temp_cib,
            "resource create DGC2 ocf:pacemaker:Dummy --no-default-ops --group GRC"
        )
        self.assertEqual(0, retVal)
        ac(output, "")
        output, retVal = pcs(temp_cib, "resource clone GRC")
        self.assertEqual(0, retVal)
        ac(output, "")

        status = outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DG1-monitor-interval-10)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DG2-monitor-interval-10)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DC-monitor-interval-10)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10 timeout=20 (DGC1-monitor-interval-10)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10 timeout=20 (DGC2-monitor-interval-10)
            """
        )

        cib_original, retVal = pcs(temp_cib, "cluster cib")
        self.assertEqual(0, retVal)

        resources = set([
            "D1", "DG1", "DG2", "GR", "DC", "DC-clone", "DGC1", "DGC2", "GRC",
            "GRC-clone"
        ])
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())

        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attrs: resource-stickiness=0
              Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
             Group: GR
              Meta Attrs: resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DG1-monitor-interval-10)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DG2-monitor-interval-10)
             Clone: DC-clone
              Meta Attrs: resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DC-monitor-interval-10)
             Clone: GRC-clone
              Meta Attrs: resource-stickiness=0
              Group: GRC
               Meta Attrs: resource-stickiness=0
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10 timeout=20 (DGC1-monitor-interval-10)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10 timeout=20 (DGC2-monitor-interval-10)
            """
        ))

        resources = set(["D1", "DG1", "DC", "DGC1"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, resources
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attrs: resource-stickiness=0
              Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DG1-monitor-interval-10)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DG2-monitor-interval-10)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DC-monitor-interval-10)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10 timeout=20 (DGC1-monitor-interval-10)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10 timeout=20 (DGC2-monitor-interval-10)
            """
        ))

        resources = set(["GRC-clone", "GRC", "DGC1", "DGC2"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GRC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DG1-monitor-interval-10)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DG2-monitor-interval-10)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10 timeout=20 (DC-monitor-interval-10)
             Clone: GRC-clone
              Meta Attrs: resource-stickiness=0
              Group: GRC
               Meta Attrs: resource-stickiness=0
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10 timeout=20 (DGC1-monitor-interval-10)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10 timeout=20 (DGC2-monitor-interval-10)
            """
        ))

        resources = set(["GR", "DG1", "DG2", "DC-clone", "DC"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GR", "DC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource --full")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource --full", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10 timeout=20 (D1-monitor-interval-10)
             Group: GR
              Meta Attrs: resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DG1-monitor-interval-10)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DG2-monitor-interval-10)
             Clone: DC-clone
              Meta Attrs: resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10 timeout=20 (DC-monitor-interval-10)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10 timeout=20 (DGC1-monitor-interval-10)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10 timeout=20 (DGC2-monitor-interval-10)
            """
        ))


class OperationRemove(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    # see also BundleMiscCommands

    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = temp_cib
        shutil.copy(self.empty_cib, self.temp_cib)
        shutil.copy(large_cib, temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    fixture_xml_1_monitor = """
        <resources>
            <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                <operations>
                    <op id="R-monitor-interval-10" interval="10"
                        name="monitor" timeout="20"
                    />
                </operations>
            </primitive>
        </resources>
    """

    fixture_xml_empty_operations = """
        <resources>
            <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                <operations>
                </operations>
            </primitive>
        </resources>
    """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy",
            self.fixture_xml_1_monitor
        )

    def fixture_monitor_20(self):
        self.assert_effect(
            "resource op add R monitor interval=20 timeout=20 --force",
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                            <op id="R-monitor-interval-20" interval="20"
                                name="monitor" timeout="20"
                            />
                        </operations>
                    </primitive>
                </resources>
            """
        )

    def fixture_start(self):
        self.assert_effect(
            "resource op add R start timeout=20",
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10" interval="10"
                                name="monitor" timeout="20"
                            />
                            <op id="R-monitor-interval-20" interval="20"
                                name="monitor" timeout="20"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                        </operations>
                    </primitive>
                </resources>
            """
        )

    def test_remove_missing_op(self):
        self.fixture_resource()
        self.assert_pcs_fail(
            "resource op remove R-monitor-interval-30",
            "Error: unable to find operation id: R-monitor-interval-30\n"
        )

    def test_keep_empty_operations(self):
        self.fixture_resource()
        self.assert_effect(
            "resource op remove R-monitor-interval-10",
            self.fixture_xml_empty_operations
        )

    def test_remove_by_id_success(self):
        self.fixture_resource()
        self.fixture_monitor_20()
        self.assert_effect(
            "resource op remove R-monitor-interval-20",
            self.fixture_xml_1_monitor
        )

    def test_remove_all_monitors(self):
        self.fixture_resource()
        self.fixture_monitor_20()
        self.fixture_start()
        self.assert_effect(
            "resource op remove R monitor",
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                        </operations>
                    </primitive>
                </resources>
            """
        )


class Utilization(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = temp_cib
        shutil.copy(self.empty_cib, self.temp_cib)
        shutil.copy(large_cib, temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    @staticmethod
    def fixture_xml_resource_no_utilization():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_empty_utilization():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                    <utilization id="R-utilization" />
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_with_utilization():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                    <utilization id="R-utilization">
                        <nvpair id="R-utilization-test" name="test"
                            value="100"
                        />
                    </utilization>
                </primitive>
            </resources>
            """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy",
            self.fixture_xml_resource_no_utilization()
        )

    def fixture_resource_utilization(self):
        self.fixture_resource()
        self.assert_effect(
            "resource utilization R test=100",
            self.fixture_xml_resource_with_utilization()
        )

    def testResourceUtilizationSet(self):
        # see also BundleMiscCommands
        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy test1=10"
        )
        ac("", output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_large_cib, "resource utilization dummy1")
        expected_out = """\
Resource Utilization:
 dummy1: \n"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_large_cib, "resource utilization dummy")
        expected_out = """\
Resource Utilization:
 dummy: test1=10
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy test1=-10 test4=1234"
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(temp_large_cib, "resource utilization dummy")
        expected_out = """\
Resource Utilization:
 dummy: test1=-10 test4=1234
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy1 test2=321 empty="
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(temp_large_cib, "resource utilization dummy1")
        expected_out = """\
Resource Utilization:
 dummy1: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_large_cib, "resource utilization")
        expected_out = """\
Resource Utilization:
 dummy: test1=-10 test4=1234
 dummy1: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

    def test_resource_utilization_set_invalid(self):
        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy test"
        )
        expected_out = """\
Error: missing value of 'test' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy =10"
        )
        expected_out = """\
Error: missing key in '=10' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_large_cib, "resource utilization dummy0")
        expected_out = """\
Error: Unable to find a resource: dummy0
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy0 test=10"
        )
        expected_out = """\
Error: Unable to find a resource: dummy0
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_large_cib, "resource utilization dummy1 test1=10 test=int"
        )
        expected_out = """\
Error: Value of utilization attribute must be integer: 'test=int'
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

    def test_keep_empty_nvset(self):
        self.fixture_resource_utilization()
        self.assert_effect(
            "resource utilization R test=",
            self.fixture_xml_resource_empty_utilization()
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource utilization R test=",
            self.fixture_xml_resource_no_utilization()
        )


class MetaAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = temp_cib
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    @staticmethod
    def fixture_xml_resource_no_meta():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_empty_meta():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <meta_attributes id="R-meta_attributes" />
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_with_meta():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-a" name="a" value="b"/>
                    </meta_attributes>
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy",
            self.fixture_xml_resource_no_meta()
        )

    def fixture_resource_meta(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy meta a=b",
            self.fixture_xml_resource_with_meta()
        )

    def testMetaAttrs(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
             "resource create --no-default-ops --force D0 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30 meta"
                " test5=test5a test6=test6a"
            ,
            "Warning: invalid resource options: 'test', 'test2', allowed"
                " options are: fake, state, trace_file, trace_ra\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops --force D1 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30"
            ,
            "Warning: invalid resource options: 'test', 'test2', allowed"
                " options are: fake, state, trace_file, trace_ra\n"
        )

        self.assert_pcs_success(
            "resource update --force D0 test=testC test2=test2a op monitor "
                "interval=35 meta test7=test7a test6=",
            "Warning: invalid resource options: 'test', 'test2', allowed"
                " options are: fake, state, trace_file, trace_ra\n"
        )

        output, returnVal = pcs(temp_cib, "resource meta D1 d1meta=superd1meta")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource group add TestRG D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            temp_cib,
            "resource meta TestRG testrgmeta=mymeta testrgmeta2=mymeta2"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource show --full")
        ac(output, """\
 Resource: D0 (class=ocf provider=heartbeat type=Dummy)
  Attributes: test=testC test2=test2a
  Meta Attrs: test5=test5a test7=test7a
  Operations: monitor interval=35 (D0-monitor-interval-35)
 Group: TestRG
  Meta Attrs: testrgmeta=mymeta testrgmeta2=mymeta2
  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
   Attributes: test=testA test2=test2a
   Meta Attrs: d1meta=superd1meta
   Operations: monitor interval=30 (D1-monitor-interval-30)
""")
        assert returnVal == 0

    def test_resource_meta_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource meta R a=",
            self.fixture_xml_resource_empty_meta()
        )

    def test_resource_update_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource update R meta a=",
            self.fixture_xml_resource_empty_meta()
        )

    def test_resource_meta_dont_create_meta_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource meta R a=",
            self.fixture_xml_resource_no_meta()
        )

    def test_resource_update_dont_create_meta_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R meta a=",
            self.fixture_xml_resource_no_meta()
        )


class UpdateInstanceAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    # The idempotency with remote-node is tested in
    # pcs/test/test_cluster_pcmk_remote.py in
    #NodeAddGuest.test_success_when_guest_node_matches_with_existing_guest

    # see also BundleMiscCommands

    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = temp_cib
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    @staticmethod
    def fixture_xml_resource_no_attrs():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_empty_attrs():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <instance_attributes id="R-instance_attributes" />
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    @staticmethod
    def fixture_xml_resource_with_attrs():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-fake" name="fake"
                            value="F"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="R-monitor-interval-10" interval="10"
                            name="monitor" timeout="20"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy",
            self.fixture_xml_resource_no_attrs()
        )

    def fixture_resource_attrs(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy fake=F",
            self.fixture_xml_resource_with_attrs()
        )

    def test_usage(self):
        self.assert_pcs_fail(
            "resource update",
            stdout_start="\nUsage: pcs resource update...\n"
        )

    def testBadInstanceVariables(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ,
            "Error: invalid resource options: 'test', 'test2', 'test4',"
                " allowed options are: fake, state, trace_file, trace_ra, "
                "use --force to override\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops --force D0 ocf:heartbeat:Dummy"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ,
            "Warning: invalid resource options: 'test', 'test2', 'test4',"
                " allowed options are: fake, state, trace_file, trace_ra\n"
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA test2=testB test3=testD",
            "Error: invalid resource options: 'test', 'test2', 'test3', allowed"
                " options are: fake, state, trace_file, trace_ra, use --force"
                " to override\n"
        )

        self.assert_pcs_success(
            "resource update D0 test=testB test2=testC test3=testD --force",
            "Warning: invalid resource options: 'test', 'test2', 'test3',"
                " allowed options are: fake, state, trace_file, trace_ra\n"
        )

        self.assert_pcs_success("resource show D0", outdent(
            """\
             Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Attributes: test=testB test2=testC test3=testD test4=test4A
              Meta Attrs: test6= test7=test7a
              Operations: monitor interval=35 (D0-monitor-interval-35)
            """
        ))

    def test_update_existing(self):
        xml = """
            <resources>
                <primitive class="ocf" id="ClusterIP" provider="heartbeat"
                    type="IPaddr2"
                >
                    <instance_attributes id="ClusterIP-instance_attributes">
                        <nvpair id="ClusterIP-instance_attributes-cidr_netmask"
                            name="cidr_netmask" value="32"
                        />
                        <nvpair id="ClusterIP-instance_attributes-ip" name="ip"
                            value="{ip}"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="ClusterIP-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
        """
        self.assert_effect(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ,
            xml.format(ip="192.168.0.99")
        )

        self.assert_effect(
            "resource update ClusterIP ip=192.168.0.100",
            xml.format(ip="192.168.0.100")
        )

    def test_keep_empty_nvset(self):
        self.fixture_resource_attrs()
        self.assert_effect(
            "resource update R fake=",
            self.fixture_xml_resource_empty_attrs()
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R fake=",
            self.fixture_xml_resource_no_attrs()
        )


class ResourcesReferencedFromAclTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_remove_referenced_primitive_resource(self):
        self.assert_pcs_success('resource create dummy ocf:heartbeat:Dummy')
        self.assert_pcs_success('acl role create read-dummy read id dummy')
        self.assert_pcs_success('resource delete dummy', [
            'Deleting Resource - dummy'
        ])

    def test_remove_group_with_referenced_primitive_resource(self):
        self.assert_pcs_success('resource create dummy1 ocf:heartbeat:Dummy')
        self.assert_pcs_success('resource create dummy2 ocf:heartbeat:Dummy')
        self.assert_pcs_success('resource group add dummy-group dummy1 dummy2')
        self.assert_pcs_success('acl role create read-dummy read id dummy2')
        self.assert_pcs_success('resource delete dummy-group', [
            'Removing group: dummy-group (and all resources within group)',
            'Stopping all resources in group: dummy-group...',
            'Deleting Resource - dummy1',
            'Deleting Resource (and group) - dummy2',
        ])

    def test_remove_referenced_group(self):
        self.assert_pcs_success('resource create dummy1 ocf:heartbeat:Dummy')
        self.assert_pcs_success('resource create dummy2 ocf:heartbeat:Dummy')
        self.assert_pcs_success('resource group add dummy-group dummy1 dummy2')
        self.assert_pcs_success('acl role create acl-role-a read id dummy-group')
        self.assert_pcs_success('resource delete dummy-group', [
            'Removing group: dummy-group (and all resources within group)',
            'Stopping all resources in group: dummy-group...',
            'Deleting Resource - dummy1',
            'Deleting Resource (and group) - dummy2',
        ])

class CloneMasterUpdate(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_no_op_allowed_in_clone_update(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy --clone"
        )
        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: migrate_from interval=0s timeout=20s? \\(dummy-migrate_from-interval-0s\\)
                               migrate_to interval=0s timeout=20s? \\(dummy-migrate_to-interval-0s\\)
                               monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                               reload interval=0s timeout=20s? \\(dummy-reload-interval-0s\\)
                               start interval=0s timeout=20s? \\(dummy-start-interval-0s\\)
                               stop interval=0s timeout=20s? \\(dummy-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )
        self.assert_pcs_fail(
            "resource update dummy-clone op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_fail(
            "resource update dummy-clone foo=bar op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_success(
            "resource show dummy-clone",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Clone: dummy-clone
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: migrate_from interval=0s timeout=20s? \\(dummy-migrate_from-interval-0s\\)
                               migrate_to interval=0s timeout=20s? \\(dummy-migrate_to-interval-0s\\)
                               monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                               reload interval=0s timeout=20s? \\(dummy-reload-interval-0s\\)
                               start interval=0s timeout=20s? \\(dummy-start-interval-0s\\)
                               stop interval=0s timeout=20s? \\(dummy-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )

    def test_no_op_allowed_in_master_update(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy --master"
        )
        self.assert_pcs_success(
            "resource show dummy-master",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Master: dummy-master
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: migrate_from interval=0s timeout=20s? \\(dummy-migrate_from-interval-0s\\)
                               migrate_to interval=0s timeout=20s? \\(dummy-migrate_to-interval-0s\\)
                               monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                               reload interval=0s timeout=20s? \\(dummy-reload-interval-0s\\)
                               start interval=0s timeout=20s? \\(dummy-start-interval-0s\\)
                               stop interval=0s timeout=20s? \\(dummy-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )
        self.assert_pcs_fail(
            "resource update dummy-master op stop timeout=300",
            "Error: op settings must be changed on base resource, not the master\n"
        )
        self.assert_pcs_fail(
            "resource update dummy-master foo=bar op stop timeout=300",
            "Error: op settings must be changed on base resource, not the master\n"
        )
        self.assert_pcs_success(
            "resource show dummy-master",
            stdout_regexp=re.compile(outdent(
                """\
                ^ Master: dummy-master
                  Resource: dummy \\(class=ocf provider=heartbeat type=Dummy\\)
                   Operations: migrate_from interval=0s timeout=20s? \\(dummy-migrate_from-interval-0s\\)
                               migrate_to interval=0s timeout=20s? \\(dummy-migrate_to-interval-0s\\)
                               monitor interval=10s? timeout=20s? \\(dummy-monitor-interval-10s?\\)
                               reload interval=0s timeout=20s? \\(dummy-reload-interval-0s\\)
                               start interval=0s timeout=20s? \\(dummy-start-interval-0s\\)
                               stop interval=0s timeout=20s? \\(dummy-stop-interval-0s\\)$
                """), re.MULTILINE
            )
        )

class ResourceRemoveWithTicketTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_remove_ticket(self):
        self.assert_pcs_success('resource create A ocf:heartbeat:Dummy')
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence'
        )
        self.assert_pcs_success(
            'constraint ticket show',
            [
                "Ticket Constraints:",
                "  Master A loss-policy=fence ticket=T",
            ]
        )
        self.assert_pcs_success(
            "resource delete A",
            [
                "Removing Constraint - ticket-T-A-Master",
                "Deleting Resource - A",
            ]
        )


class BundleCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    )
):
    temp_cib = rc("temp-cib.xml")
    empty_cib = rc("cib-empty-2.8.xml")

    def setUp(self):
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

    def fixture_primitive(self, name, bundle):
        self.assert_pcs_success(
            "resource create {0} ocf:heartbeat:Dummy bundle {1}".format(
                name, bundle
            )
        )

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            (
                "resource bundle create {0} container docker image=pcs:test "
                "network control-port=1234"
            ).format(name)
        )


@skip_unless_pacemaker_supports_bundle
class BundleDeleteTest(BundleCommon):
    def test_without_primitive(self):
        self.fixture_bundle("B")
        self.assert_effect(
            "resource delete B",
            "<resources/>",
            "Deleting bundle 'B'\n"
        )

    def test_with_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "resource delete B",
            "<resources/>",
            dedent("""\
                Deleting bundle 'B' and its inner resource 'R'
                Deleting Resource - R
            """),
        )

    def test_remove_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "resource delete R",
            """
                <resources>
                    <bundle id="B">
                        <docker image="pcs:test" />
                        <network control-port="1234" />
                    </bundle>
                </resources>
            """,
            "Deleting Resource - R\n",
        )


@skip_unless_pacemaker_supports_bundle
class BundleGroup(BundleCommon):
    def test_group_add_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource group add bundles B",
            "Error: Unable to find resource: B\n"
        )

    def test_group_add_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource group add group R",
            "Error: cannot group bundle resources\n"
        )

    def test_group_remove_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource group remove B R",
            "Error: Group 'B' does not exist\n"
        )

    def test_ungroup_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource ungroup B",
            "Error: Group 'B' does not exist\n"
        )


@skip_unless_pacemaker_supports_bundle
class BundleCloneMaster(BundleCommon):
    def test_clone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource clone B",
            "Error: unable to find group or resource: B\n"
        )

    def test_master_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource master B",
            "Error: Unable to find resource or group with id B\n"
        )

    def test_clone_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource clone R",
            "Error: cannot clone bundle resource\n"
        )

    def test_master_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource master R",
            "Error: cannot make a master/slave resource from a bundle resource\n"
        )

    def test_unclone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource unclone B",
            "Error: could not find resource: B\n"
        )


@skip_unless_pacemaker_supports_bundle
class BundleMiscCommands(BundleCommon):
    def test_resource_enable_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource enable B"
        )

    def test_resource_disable_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource disable B"
        )

    def test_resource_manage_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource manage B"
        )

    def test_resource_unmanage_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success(
            "resource unmanage B"
        )

    def test_op_add(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource op add B monitor interval=30",
            "Error: Unable to find resource: B\n"
        )

    def test_op_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource op remove B monitor interval=30",
            "Error: Unable to find resource: B\n"
        )

    def test_update(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource update B meta aaa=bbb",
            "Error: Unable to find resource: B\n"
        )

    def test_meta(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource meta B aaa=bbb",
            "Error: unable to find a resource/clone/master/group: B\n"
        )

    def test_utilization(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource utilization B aaa=10",
            "Error: Unable to find a resource: B\n"
        )

    def test_debug_start_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B",
            "Error: unable to debug-start a bundle\n"
        )

    def test_debug_start_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B",
            "Error: unable to debug-start a bundle, try the bundle's resource: R\n"
        )

    def test_debug_stop_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B",
            "Error: unable to debug-stop a bundle\n"
        )

    def test_debug_stop_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B",
            "Error: unable to debug-stop a bundle, try the bundle's resource: R\n"
        )

    def test_debug_monitor_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B",
            "Error: unable to debug-monitor a bundle\n"
        )

    def test_debug_monitor_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B",
            "Error: unable to debug-monitor a bundle, try the bundle's resource: R\n"
        )

    def test_debug_promote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B",
            "Error: unable to debug-promote a bundle\n"
        )

    def test_debug_promote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B",
            "Error: unable to debug-promote a bundle, try the bundle's resource: R\n"
        )

    def test_debug_demote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B",
            "Error: unable to debug-demote a bundle\n"
        )

    def test_debug_demote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B",
            "Error: unable to debug-demote a bundle, try the bundle's resource: R\n"
        )


class ResourceUpdateRemoteAndGuestChecks(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_update_fail_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy",
        )
        self.assert_pcs_fail(
            "resource update R meta remote-node=HOST",
            "Error: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest', use --force to override\n"
        )
    def test_update_warn_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy",
        )
        self.assert_pcs_success(
            "resource update R meta remote-node=HOST --force",
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
    def test_update_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
        self.assert_pcs_fail(
            "resource update R meta remote-node=",
            "Error: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest', use --force to override\n"
        )

    def test_update_warn_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
        self.assert_pcs_success(
            "resource update R meta remote-node= --force",
            "Warning: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest'\n"
        )

    def test_meta_fail_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy",
        )
        self.assert_pcs_fail(
            "resource meta R remote-node=HOST",
            "Error: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest', use --force to override\n"
        )

    def test_meta_warn_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy",
        )
        self.assert_pcs_success(
            "resource meta R remote-node=HOST --force",
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )

    def test_meta_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
        self.assert_pcs_fail(
            "resource meta R remote-node=",
            "Error: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest', use --force to override\n"
        )

    def test_meta_warn_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ,
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n"
        )
        self.assert_pcs_success(
            "resource meta R remote-node= --force",
            "Warning: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest'\n"
        )

class ResourceUpdateUniqueAttrChecks(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def test_unique_err(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1"
        )
        self.assert_pcs_success("resource create R2 ocf:pacemaker:Dummy")
        self.assert_pcs_fail(
            "resource update R2 state=1",
            "Error: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1', "
            "use --force to override\n"
        )

    def test_unique_setting_same_value(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1 --no-default-ops"
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:Dummy --no-default-ops"
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force",
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n"
        )
        res_config = outdent(
            """\
             Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R1-monitor-interval-10)
             Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R2-monitor-interval-10)
            """
        )
        self.assert_pcs_success("resource show --full", res_config)
        # make sure that it doesn't check against resource itself
        self.assert_pcs_success(
            "resource update R2 state=1 --force",
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n"
        )
        self.assert_pcs_success("resource show --full", res_config)
        res_config = outdent(
            """\
             Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R1-monitor-interval-10)
             Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=2
              Operations: monitor interval=10 timeout=20 (R2-monitor-interval-10)
            """
        )
        self.assert_pcs_success("resource update R2 state=2")
        self.assert_pcs_success("resource show --full", res_config)
        self.assert_pcs_success("resource update R2 state=2")
        self.assert_pcs_success("resource show --full", res_config)

    def test_unique_warn(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1 --no-default-ops"
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:Dummy --no-default-ops"
        )
        self.assert_pcs_success(
            "resource create R3 ocf:pacemaker:Dummy --no-default-ops"
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force",
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n"
        )
        self.assert_pcs_success(
            "resource show --full",
            outdent(
            """\
             Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R1-monitor-interval-10)
             Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R2-monitor-interval-10)
             Resource: R3 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10 timeout=20 (R3-monitor-interval-10)
            """
            )
        )
        self.assert_pcs_success(
            "resource update R3 state=1 --force",
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1', "
            "'R2'\n"
        )
        self.assert_pcs_success(
            "resource show --full",
            outdent(
            """\
             Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R1-monitor-interval-10)
             Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R2-monitor-interval-10)
             Resource: R3 (class=ocf provider=pacemaker type=Dummy)
              Attributes: state=1
              Operations: monitor interval=10 timeout=20 (R3-monitor-interval-10)
            """
            )
        )

class FailcountShow(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource"])
        self.resource = mock.Mock(spec_set=["get_failcounts"])
        self.get_failcounts = mock.Mock()
        self.lib.resource = self.resource
        self.lib.resource.get_failcounts = self.get_failcounts

    def assert_failcount_output(
        self, lib_failures, expected_output, resource_id=None, node=None,
        operation=None, interval=None, full=False
    ):
        self.get_failcounts.return_value = lib_failures
        ac(
            resource.resource_failcount_show(
                self.lib, resource_id, node, operation, interval, full
            ),
            expected_output
        )

    def fixture_failures_no_op(self):
        failures = [
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "0",
                "operation": None,
                "interval": None,
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "1",
                "operation": None,
                "interval": None,
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "0",
                "operation": None,
                "interval": None,
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "1",
                "operation": None,
                "interval": None,
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": None,
                "interval": None,
                "fail_count": 100,
                "last_failure": 1528871966,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": None,
                "interval": None,
                "fail_count": "INFINITY",
                "last_failure": 1528871966,
            },
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": None,
                "interval": None,
                "fail_count": 10,
                "last_failure": 1528871946,
            },
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": None,
                "interval": None,
                "fail_count": 150,
                "last_failure": 1528871956,
            },
        ]
        shuffle(failures)
        return failures

    def fixture_failures_monitor(self):
        failures = [
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "500",
                "fail_count": 10,
                "last_failure": 1528871946,
            },
            {
                "node": "node2",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "1500",
                "fail_count": 150,
                "last_failure": 1528871956,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "monitor",
                "interval": "1500",
                "fail_count": 25,
                "last_failure": 1528871966,
            },
        ]
        shuffle(failures)
        return failures

    def fixture_failures(self):
        failures = self.fixture_failures_monitor() + [
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "0",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "clone",
                "clone_id": "1",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "0",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node2",
                "resource": "clone",
                "clone_id": "1",
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871936,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "start",
                "interval": "0",
                "fail_count": 100,
                "last_failure": 1528871966,
            },
            {
                "node": "node1",
                "resource": "resource",
                "clone_id": None,
                "operation": "start",
                "interval": "0",
                "fail_count": "INFINITY",
                "last_failure": 1528871966,
            },
        ]
        shuffle(failures)
        return failures

    def test_no_failcounts(self):
        self.assert_failcount_output(
            [],
            "No failcounts"
        )

    def test_no_failcounts_resource(self):
        self.assert_failcount_output(
            [],
            "No failcounts for resource 'res'",
            resource_id="res"
        )

    def test_no_failcounts_node(self):
        self.assert_failcount_output(
            [],
            "No failcounts on node 'nod'",
            node="nod"
        )

    def test_no_failcounts_operation(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope'",
            operation="ope"
        )

    def test_no_failcounts_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10'",
            operation="ope",
            interval="10"
        )

    def test_no_failcounts_resource_node(self):
        self.assert_failcount_output(
            [],
            "No failcounts for resource 'res' on node 'nod'",
            resource_id="res",
            node="nod"
        )

    def test_no_failcounts_resource_operation(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' of resource 'res'",
            resource_id="res",
            operation="ope",
        )

    def test_no_failcounts_resource_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' of resource "
                "'res'",
            resource_id="res",
            operation="ope",
            interval="10"
        )

    def test_no_failcounts_resource_node_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' of resource "
                "'res' on node 'nod'",
            resource_id="res",
            node="nod",
            operation="ope",
            interval="10"
        )

    def test_no_failcounts_node_operation(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' on node 'nod'",
            node="nod",
            operation="ope",
        )

    def test_no_failcounts_node_operation_interval(self):
        self.assert_failcount_output(
            [],
            "No failcounts for operation 'ope' with interval '10' on node 'nod'",
            node="nod",
            operation="ope",
            interval="10"
        )

    def test_failcounts_short(self):
        self.assert_failcount_output(
            self.fixture_failures(),
            dedent("""\
                Failcounts for resource 'clone'
                  node1: INFINITY
                  node2: INFINITY
                Failcounts for resource 'resource'
                  node1: INFINITY
                  node2: 160"""
            ),
            full=False
        )

    def test_failcounts_full(self):
        self.assert_failcount_output(
            self.fixture_failures(),
            dedent("""\
                Failcounts for resource 'clone'
                  node1:
                    start 0ms: INFINITY
                  node2:
                    start 0ms: INFINITY
                Failcounts for resource 'resource'
                  node1:
                    monitor 1500ms: 25
                    start 0ms: INFINITY
                  node2:
                    monitor 1500ms: 150
                    monitor 500ms: 10"""
            ),
            full=True
        )

    def test_failcounts_short_filter(self):
        self.assert_failcount_output(
            self.fixture_failures_monitor(),
            dedent("""\
                Failcounts for operation 'monitor' of resource 'resource'
                  node1: 25
                  node2: 160"""
            ),
            operation="monitor",
            full=False
        )

    def test_failcounts_full_filter(self):
        self.assert_failcount_output(
            self.fixture_failures_monitor(),
            dedent("""\
                Failcounts for operation 'monitor' of resource 'resource'
                  node1:
                    monitor 1500ms: 25
                  node2:
                    monitor 1500ms: 150
                    monitor 500ms: 10"""
            ),
            operation="monitor",
            full=True
        )

    def test_failcounts_no_op_short(self):
        self.assert_failcount_output(
            self.fixture_failures_no_op(),
            dedent("""\
                Failcounts for resource 'clone'
                  node1: INFINITY
                  node2: INFINITY
                Failcounts for resource 'resource'
                  node1: INFINITY
                  node2: 160"""
            ),
            full=False
        )

    def test_failcounts_no_op_full(self):
        self.assert_failcount_output(
            self.fixture_failures_no_op(),
            dedent("""\
                Failcounts for resource 'clone'
                  node1: INFINITY
                  node2: INFINITY
                Failcounts for resource 'resource'
                  node1: INFINITY
                  node2: 160"""
            ),
            full=True
        )
