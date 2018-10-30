from lxml import etree
import os
import re
from random import shuffle
import shutil
from textwrap import dedent
from unittest import mock, skip, TestCase

from pcs.test.cib_resource.common import ResourceTest
from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.cib import get_assert_pcs_effect_mixin
from pcs.test.tools.fixture_cib import (
    fixture_master_xml,
    fixture_to_cib,
    wrap_element_by_master,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
    skip_unless_lsb_network_available,
    skip_unless_pacemaker_supports_bundle,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

from pcs import utils
from pcs import resource
from pcs.constraint import LOCATION_NODE_VALIDATION_SKIP_MSG

LOCATION_NODE_VALIDATION_SKIP_WARNING = f"Warning: {LOCATION_NODE_VALIDATION_SKIP_MSG}\n"

RESOURCES_TMP = rc("test_resource")
if not os.path.exists(RESOURCES_TMP):
    os.makedirs(RESOURCES_TMP)

empty_cib = rc("cib-empty.xml")
temp_cib = os.path.join(RESOURCES_TMP, "temp-cib.xml")
large_cib = rc("cib-large.xml")
temp_large_cib  = os.path.join(RESOURCES_TMP, "temp-cib-large.xml")


class ResourceDescribe(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)

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
              state: Location to store the resource state in.
              yellow_limit: Lower (!) limit of idle percentage to switch the health
                            attribute to yellow. I.e. the #health-cpu will go yellow if the
                            %idle of the CPU falls below 50%.
              red_limit: Lower (!) limit of idle percentage to switch the health attribute
                         to red. I.e. the #health-cpu will go red if the %idle of the CPU
                         falls below 10%.
{0}
            Default operations:
              start: interval=0s timeout=10s
              stop: interval=0s timeout=10s
              monitor: interval=10s start-delay=0s timeout=10s
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
            "resource describe ocf:pacemaker:nonexistent",
            # pacemaker 1.1.18 changes -5 to Input/output error
            stdout_regexp=re.compile("^"
                "Error: Agent 'ocf:pacemaker:nonexistent' is not installed or "
                "does not provide valid metadata: Metadata query for "
                "ocf:pacemaker:nonexistent failed: (-5|Input/output error)\n"
                "$", re.MULTILINE
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


class Resource(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        shutil.copy(large_cib, temp_large_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setupClusterA(self,temp_cib):
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP2 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP3 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP4 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP6 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success("resource group add TestGroup1 ClusterIP")
        self.assert_pcs_success(
            "resource group add TestGroup2 ClusterIP2 ClusterIP3"
        )
        self.assert_pcs_success("resource clone ClusterIP4")
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "ClusterIP5", master_id="Master")

    def testCaseInsensitive(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops D0 dummy")
        ac(o, "Error: Multiple agents match 'dummy', please specify full name: ocf:heartbeat:Dummy, ocf:pacemaker:Dummy\n")
        assert r == 1

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

        o,r = pcs(temp_cib, "resource create --no-default-ops D4 ipaddr3")
        ac(o,"Error: Unable to find agent 'ipaddr3', try specifying its full name\n")
        assert r == 1

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "resource")
        assert returnVal == 0, 'Unable to list resources'
        assert output == "NO resources configured\n", "Bad output"

    def testAddResourcesLargeCib(self):
        output, returnVal = pcs(
            temp_large_cib,
            "resource create dummy0 ocf:heartbeat:Dummy --no-default-ops"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource config dummy0")
        assert returnVal == 0
        ac(output, outdent(
            """\
             Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy0-monitor-interval-10s)
            """
        ))

    def _test_delete_remove_resources(self, command):
        assert command in {"delete", "remove"}

        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

        self.assert_pcs_success(
            f"resource {command} ClusterIP",
            "Deleting Resource - ClusterIP\n"
        )

        self.assert_pcs_fail(
            "resource config ClusterIP",
            "Error: unable to find resource 'ClusterIP'\n"
        )

        self.assert_pcs_success(
            "resource status",
            "NO resources configured\n"
        )

        self.assert_pcs_fail(
            f"resource {command} ClusterIP",
            "Error: Resource 'ClusterIP' does not exist.\n"
        )

    def testDeleteResources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource delete",
            stdout_start="\nUsage: pcs resource delete..."
        )

        self._test_delete_remove_resources("delete")

    def testRemoveResources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource remove",
            stdout_start="\nUsage: pcs resource remove..."
        )

        self._test_delete_remove_resources("remove")

    def testResourceShow(self):
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success("resource config ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
            """
        ))

    def testResourceUpdate(self):
        # The idempotency with remote-node is tested in
        # pcs/test/test_cluster_pcmk_remote.py in
        #NodeAddGuest.test_success_when_guest_node_matches_with_existing_guest

        # see also BundleMiscCommands
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

        line = 'resource update'
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        output, returnVal = pcs(temp_cib, "resource update ClusterIP ip=192.168.0.100")
        assert returnVal == 0
        assert output == ""

    def testAddOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

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

        self.assert_pcs_success("resource config ClusterIP", outdent(
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

        o, r = pcs(temp_cib, "resource config OPTest")
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

        o, r = pcs(temp_cib, "resource config OPTest2")
        ac(o," Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=2 (OPTest2-monitor-interval-25s)\n              start interval=0s timeout=30s (OPTest2-start-interval-0s)\n              monitor interval=60s timeout=1800s (OPTest2-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest3 ocf:heartbeat:Dummy op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource config OPTest3")
        ac(o," Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest3-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest4 ocf:heartbeat:Dummy op monitor interval=30s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource config OPTest4")
        ac(o," Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest4-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest5 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource config OPTest5")
        ac(o," Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest5-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest6 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success("resource config OPTest6", outdent(
            """\
             Resource: OPTest6 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (OPTest6-monitor-interval-10s)
                          monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest6-monitor-interval-30s)
            """
        ))

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

        o, r = pcs(temp_cib, "resource config OPTest7")
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
            outdent(
                """\
                Error: operation monitor already specified for OCFTest1, use --force to override:
                monitor interval=10s timeout=20s (OCFTest1-monitor-interval-10s)
                """
            )
        )

        o,r = pcs(temp_cib, "resource op add OCFTest1 monitor interval=31s --force")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OCFTest1 monitor interval=30s OCF_CHECK_LEVEL=15")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success(
            "resource config OCFTest1",
            outdent(
                """\
                 Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations: monitor interval=10s timeout=20s (OCFTest1-monitor-interval-10s)
                              monitor interval=31s (OCFTest1-monitor-interval-31s)
                              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)
                """
            )
        )

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor interval=61s OCF_CHECK_LEVEL=5")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource config OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=61s OCF_CHECK_LEVEL=5 (OCFTest1-monitor-interval-61s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource config OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-60s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4 interval=35s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource config OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=35s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-35s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        self.assert_pcs_success(
            "resource create --no-default-ops state ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10s to 11 to"
                " make the operation unique\n"
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10",
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10 role=Started",
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_success(
            "resource op add state monitor interval=15 role=Master --force"
        )

        self.assert_pcs_success("resource config state", outdent(
            """\
             Resource: state (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (state-monitor-interval-11)
                          monitor interval=15 role=Master (state-monitor-interval-15)
            """
        ))

    def _test_delete_remove_operation(self, command):
        assert command in {"delete", "remove"}

        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

        self.assert_pcs_success(
            'resource op add ClusterIP monitor interval=31s --force'
        )

        self.assert_pcs_success(
            'resource op add ClusterIP monitor interval=32s --force'
        )

        self.assert_pcs_fail(
            f'resource op {command} ClusterIP-monitor-interval-32s-xxxxx',
            "Error: unable to find operation id: "
                "ClusterIP-monitor-interval-32s-xxxxx\n"
        )

        self.assert_pcs_success(
            f'resource op {command} ClusterIP-monitor-interval-32s'
        )

        self.assert_pcs_success(
            f'resource op {command} ClusterIP monitor interval=30s'
        )

        self.assert_pcs_fail(
            f'resource op {command} ClusterIP monitor interval=30s',
            "Error: Unable to find operation matching: monitor interval=30s\n"
        )

        self.assert_pcs_success("resource config ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=31s (ClusterIP-monitor-interval-31s)
            """
        ))

        self.assert_pcs_success(
            f'resource op {command} ClusterIP monitor interval=31s'
        )

        self.assert_pcs_success("resource config ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
            """
        ))

        self.assert_pcs_success(
            'resource op add ClusterIP monitor interval=31s'
        )

        self.assert_pcs_success(
            'resource op add ClusterIP monitor interval=32s --force'
        )

        self.assert_pcs_success(
            'resource op add ClusterIP stop timeout=34s'
        )

        self.assert_pcs_success(
            'resource op add ClusterIP start timeout=33s'
        )

        self.assert_pcs_success(
            f'resource op {command} ClusterIP monitor'
        )

        self.assert_pcs_success("resource config ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: stop interval=0s timeout=34s (ClusterIP-stop-interval-0s)
                          start interval=0s timeout=33s (ClusterIP-start-interval-0s)
            """
        ))

    def testDeleteOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op delete",
            stdout_start="\nUsage: pcs resource op delete..."
        )

        self._test_delete_remove_operation("delete")

    def testRemoveOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op remove",
            stdout_start="\nUsage: pcs resource op remove..."
        )

        self._test_delete_remove_operation("remove")

    def testUpdateOperation(self):
        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )
        self.assert_pcs_success("resource config ClusterIP", outdent(
            """\
             Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
            """
        ))

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=32s"
        )
        self.assert_pcs_success("resource config ClusterIP", outdent(
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
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s"
        )
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        self.assert_pcs_success("resource update ClusterIP op")
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        self.assert_pcs_success("resource update ClusterIP op monitor")
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        # test invalid id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ab#cd",
            "Error: invalid operation id 'ab#cd', '#' is not a valid character"
                " for a operation id\n"
        )
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        # test existing id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ClusterIP",
            "Error: id 'ClusterIP' is already in use, please specify another"
                " one\n"
        )
        self.assert_pcs_success("resource config ClusterIP", show_clusterip)

        # test id change
        # there is a bug:
        # - first an existing operation is removed
        # - then a new operation is created at the same place
        # - therefore options not specified for in the command are removed
        #    instead of them being kept from the old operation
        # This needs to be fixed. However it's not my task currently.
        # Moreover it is documented behavior.
        self.assert_pcs_success("resource update ClusterIP op monitor id=abcd")
        self.assert_pcs_success("resource config ClusterIP", outdent(
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
        self.assert_pcs_success("resource config A", outdent(
            """\
             Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations: migrate_from interval=0s timeout=20s (A-migrate_from-interval-0s)
                          migrate_to interval=0s timeout=20s (A-migrate_to-interval-0s)
                          monitor interval=10 (A-monitor-interval-10)
                          monitor interval=20 (A-monitor-interval-20)
                          reload interval=0s timeout=20s (A-reload-interval-0s)
                          start interval=0s timeout=20s (A-start-interval-0s)
                          stop interval=0s timeout=20s (A-stop-interval-0s)
            """
        ))

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

        self.assert_pcs_success("resource config A", outdent(
            """\
             Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations: migrate_from interval=0s timeout=20s (A-migrate_from-interval-0s)
                          migrate_to interval=0s timeout=20s (A-migrate_to-interval-0s)
                          monitor interval=11 (A-monitor-interval-11)
                          monitor interval=20 (A-monitor-interval-20)
                          reload interval=0s timeout=20s (A-reload-interval-0s)
                          start interval=0s timeout=20s (A-start-interval-0s)
                          stop interval=0s timeout=20s (A-stop-interval-0s)
            """
        ))



        output, returnVal = pcs(
            temp_cib,
            "resource create B ocf:heartbeat:Dummy --no-default-ops"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource op remove B-monitor-interval-10s")

        output, returnVal = pcs(temp_cib, "resource config B")
        ac(output, outdent(
            """\
             Resource: B (class=ocf provider=heartbeat type=Dummy)
            """
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=60s"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        output, returnVal = pcs(temp_cib, "resource config B")
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

        o,r = pcs(temp_cib, "resource status")
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

        o,r = pcs(temp_cib, "resource status")
        assert r == 0
        ac(o,"NO resources configured\n")

    def testGroupUngroup(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP3 prefers rh7-1")
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

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

        self.assert_pcs_success("resource config AGroup", outdent(
            """\
             Group: AGroup
              Resource: A1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A1-monitor-interval-10s)
              Resource: A2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A2-monitor-interval-10s)
              Resource: A3 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A3-monitor-interval-10s)
              Resource: A4 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A4-monitor-interval-10s)
              Resource: A5 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A5-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "resource ungroup Noexist")
        assert r == 1
        ac(o,"Error: Group 'Noexist' does not exist\n")

        o,r = pcs(temp_cib, "resource ungroup AGroup A1 A3")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource config")
        assert r == 0
        ac(o, outdent(
            """\
             Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)
             Group: TestGroup1
              Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
             Clone: ClusterIP4-clone
              Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)
             Clone: Master
              Meta Attrs: promotable=true
              Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)
             Group: AGroup
              Resource: A2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A2-monitor-interval-10s)
              Resource: A4 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A4-monitor-interval-10s)
              Resource: A5 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A5-monitor-interval-10s)
             Resource: A1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A1-monitor-interval-10s)
             Resource: A3 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A3-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "constraint location AGroup prefers rh7-1")
        assert r == 0
        ac(o,'Warning: Validation for node existence in the cluster will be skipped\n')

        o,r = pcs(temp_cib, "resource ungroup AGroup A2")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "constraint")
        assert r == 0
        ac(o, outdent(
            """\
            Location Constraints:
              Resource: AGroup
                Enabled on: rh7-1 (score:INFINITY)
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
        ))

        o,r = pcs(temp_cib, "resource ungroup AGroup")
        assert r == 0
        ac(o, 'Removing Constraint - location-AGroup-rh7-1-INFINITY\n')

        o,r = pcs(temp_cib, "resource config AGroup")
        assert r == 1
        ac(o,"Error: unable to find resource 'AGroup'\n")

        self.assert_pcs_success("resource config A1 A2 A3 A4 A5", outdent(
            """\
             Resource: A1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A1-monitor-interval-10s)
             Resource: A2 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A2-monitor-interval-10s)
             Resource: A3 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A3-monitor-interval-10s)
             Resource: A4 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A4-monitor-interval-10s)
             Resource: A5 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A5-monitor-interval-10s)
            """
        ))

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

        o,r = pcs(temp_cib, "resource status")
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

        o,r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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

        o, r = pcs(temp_cib, "resource status")
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
            "resource create --no-default-ops A0 ocf:heartbeat:Dummy clone"
        )
        self.assertEqual(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add A0-clone A6")
        ac(o, "Error: 'A0-clone' is already a clone resource\n")
        self.assertEqual(1, r)

        o, r = pcs(temp_cib, "resource unclone A0-clone")
        self.assertEqual(0, r)
        ac(o, "")

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "A0")

        o, r = pcs(temp_cib, "resource group add A0-master A6")
        ac(o, "Error: 'A0-master' is already a clone resource\n")
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

        output, returnVal = pcs(temp_cib, "resource status")
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

        output, returnVal = pcs(temp_cib, "resource status")
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

        output, returnVal = pcs(temp_cib, "resource status")
        ac(output, """\
 Resource Group: gr1
     d1\t(ocf::heartbeat:Dummy):\tStopped
 Clone Set: gr2-clone [gr2]
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr1 d2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource status")
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

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "gr2")

        output, returnVal = pcs(temp_cib, "resource config")
        ac(output, outdent("""\
             Group: gr1
              Resource: d1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (d1-monitor-interval-10s)
             Clone: gr2-master
              Meta Attrs: promotable=true
              Group: gr2
               Resource: d2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (d2-monitor-interval-10s)
            """
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource group add gr1 d2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource config")
        ac(output, outdent("""\
             Group: gr1
              Resource: d1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (d1-monitor-interval-10s)
              Resource: d2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (d2-monitor-interval-10s)
            """
        ))
        self.assertEqual(0, returnVal)

    def testClusterConfig(self):
        self.setupClusterA(temp_cib)

        self.pcs_runner.corosync_conf_file = rc("corosync.conf")
        self.assert_pcs_success("config",outdent("""\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
             Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)
             Group: TestGroup1
              Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
             Group: TestGroup2
              Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)
              Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)
             Clone: ClusterIP4-clone
              Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)
             Clone: Master
              Meta Attrs: promotable=true
              Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
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
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint location D1-clone prefers rh7-1")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o,r = pcs(temp_cib, "constraint location D1 prefers rh7-1 --force")
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D1-clone
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success("resource delete D1-clone", outdent(
            """\
            Removing Constraint - location-D1-clone-rh7-1-INFINITY
            Removing Constraint - location-D1-rh7-1-INFINITY
            Deleting Resource - D1
            """
        ))

        o,r = pcs(temp_cib, "resource config")
        assert r == 0
        ac(o,"")

        o, r = pcs(
            temp_cib,
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
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(temp_cib, "constraint location Master prefers rh7-2")
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

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
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        self.assert_pcs_success("resource delete ClusterIP5", outdent(
            """\
            Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
            Removing Constraint - location-ClusterIP5-rh7-2-INFINITY
            Deleting Resource - ClusterIP5
            """
        ))

        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
        )

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        self.pcs_runner.corosync_conf_file = rc("corosync.conf")
        self.assert_pcs_success("config", outdent(
            """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
             Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
              Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)
             Group: TestGroup1
              Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)
             Group: TestGroup2
              Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)
              Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)
             Clone: ClusterIP4-clone
              Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
               Attributes: cidr_netmask=32 ip=192.168.0.99
               Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)
             Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: cidr_netmask=32 ip=192.168.0.99
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
        self.pcs_runner.corosync_conf_file = None

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_large_cib, "dummylarge")

        output, returnVal = pcs(temp_large_cib, "resource delete dummylarge")
        ac(output, 'Deleting Resource - dummylarge\n')
        assert returnVal == 0

    def testMasterSlaveGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_large_cib, "dummies")

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group and M/S) - dummylarge
            """
        ))
        assert returnVal == 0

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
            "Error: invalid resource option 'test3', allowed options"
                " are: fake, state, trace_file, trace_ra, use --force to"
                " override\n"
        )

        self.assert_pcs_success(
            "resource update D0 test=testB test2=testC test3=testD --force",
            "Warning: invalid resource option 'test3',"
                " allowed options are: fake, state, trace_file, trace_ra\n"
        )

        self.assert_pcs_success("resource config D0", outdent(
            """\
             Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Attributes: test=testB test2=testC test4=test4A test3=testD
              Meta Attrs: test6= test7=test7a
              Operations: monitor interval=35 (D0-monitor-interval-35)
            """
        ))

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
                "interval=35 meta test7=test7a test6="
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

        output, returnVal = pcs(temp_cib, "resource config")
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

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "Group", master_id="GroupMaster")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: GroupMaster
              Meta Attrs: promotable=true
              Group: Group
               Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (D0-monitor-interval-10s)
               Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

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
        # see also BundleClone
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

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
             Clone: dummy2-clone
              Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
             Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        # unclone with a clone itself specified
        output, returnVal = pcs(temp_cib, "resource group add gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-clone
              Group: gr
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
              Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        # unclone with a cloned group specified
        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-clone
              Group: gr
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
              Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(temp_cib, "resource clone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-clone
              Group: gr
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-clone
              Group: gr
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
             Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
             Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
            """
        ))

    def testUncloneMaster(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10s to 11 to make the operation unique\n"
        )

        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pacemaker:Stateful",
            "Warning: changing a monitor operation interval from 10s to 11 to make the operation unique\n"
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
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "dummy2")

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
             Clone: dummy2-master
              Meta Attrs: promotable=true
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a clone itself specified
        output, returnVal = pcs(temp_cib, "resource group add gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "gr")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-master
              Meta Attrs: promotable=true
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr-master")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a cloned group specified
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "gr")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-master
              Meta Attrs: promotable=true
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone gr")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                           monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(temp_cib, "resource ungroup gr dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "gr")

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
             Clone: gr-master
              Meta Attrs: promotable=true
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
             Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource group add gr dummy1 dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "gr")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-master
              Meta Attrs: promotable=true
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
               Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource unclone dummy2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: gr-master
              Meta Attrs: promotable=true
              Group: gr
               Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations: monitor interval=10s role=Master timeout=20s (dummy1-monitor-interval-10s)
                            monitor interval=11 role=Slave timeout=20s (dummy1-monitor-interval-11)
             Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations: monitor interval=10s role=Master timeout=20s (dummy2-monitor-interval-10s)
                          monitor interval=11 role=Slave timeout=20s (dummy2-monitor-interval-11)
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

    def testPromotableGroupMember(self):
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

        o,r = pcs(temp_cib, "resource promotable D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource config")
        ac(o,"""\
 Group: AG
  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
   Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
 Clone: D0-clone
  Meta Attrs: promotable=true
  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
   Operations: monitor interval=10s timeout=20s (D0-monitor-interval-10s)
""")
        assert r == 0

        o,r = pcs(temp_cib, "resource promotable D1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource config")
        ac(o,"""\
 Clone: D0-clone
  Meta Attrs: promotable=true
  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
   Operations: monitor interval=10s timeout=20s (D0-monitor-interval-10s)
 Clone: D1-clone
  Meta Attrs: promotable=true
  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
   Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
""")
        assert r == 0

    def testCloneMaster(self):
        # see also BundleClone
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
        output, returnVal  = pcs(
            temp_cib,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource clone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            temp_cib,
            "resource promotable D3 promotable=false"
        )
        assert returnVal == 1
        assert output == "Error: you cannot specify both promotable option and promotable keyword\n", [output]

        output, returnVal = pcs(temp_cib, "resource promotable D3")
        assert returnVal == 0
        assert output == "", [output]

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "D1", master_id="D1-master-custom")

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "D2")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D0-clone
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D0-monitor-interval-10s)
             Clone: D3-clone
              Meta Attrs: promotable=true
              Resource: D3 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D3-monitor-interval-10s)
             Clone: D1-master-custom
              Meta Attrs: promotable=true
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Clone: D2-master
              Meta Attrs: promotable=true
              Resource: D2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D3-clone
              Meta Attrs: promotable=true
              Resource: D3 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D3-monitor-interval-10s)
             Clone: D1-master-custom
              Meta Attrs: promotable=true
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D0-monitor-interval-10s)
             Resource: D2 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

    @skip_unless_lsb_network_available()
    def testLSBResource(self):
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
            "resource config",
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
            "resource config",
            outdent(
                """\
                 Resource: D2 (class=lsb type=network)
                  Attributes: foo=bar bar=baz
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

        self.assert_pcs_fail(
            "resource move",
            "Error: must specify a resource to move\n"
        )
        self.assert_pcs_fail(
            "resource ban",
            "Error: must specify a resource to ban\n"
        )
        self.assert_pcs_fail(
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
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(Z|( (\+|-)\d\d:\d\d))", "{datetime}", output)
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
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(Z|( (\+|-)\d\d:\d\d))", "{datetime}", output)
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
Error: when specifying --master you must use the promotable clone id
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
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone"
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

        # move
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

        # move --master
        output, returnVal = pcs(temp_cib, "resource move D1 --master")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone --master")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2 --master")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG --master")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone --master")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEqual(1, returnVal)

        # ban
        output, returnVal = pcs(temp_cib, "resource ban D1")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # ban --master
        output, returnVal = pcs(temp_cib, "resource ban D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        # clear
        output, returnVal = pcs(temp_cib, "resource clear D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # clear --master
        output, returnVal = pcs(temp_cib, "resource clear D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id\n")
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

    def testPromotableCloneMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib
        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy promotable"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource promotable DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # move
        output, returnVal = pcs(temp_cib, "resource move D1")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        # move --master
        output, returnVal = pcs(temp_cib, "resource move D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # ban
        output, returnVal = pcs(temp_cib, "resource ban D1")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # ban --master
        output, returnVal = pcs(temp_cib, "resource ban D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # clear
        output, returnVal = pcs(temp_cib, "resource clear D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # clear --master
        output, returnVal = pcs(temp_cib, "resource clear D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone --master")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone --master")
        ac(output, "")
        self.assertEqual(0, returnVal)


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

    def testMasterMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib
        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "D1", master_id="D1-clone")

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "DG", master_id="DG-clone")

        # move
        output, returnVal = pcs(temp_cib, "resource move D1")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone")
        ac(output, "Error: to move promotable clone resources you must use --master and the clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        # move --master
        output, returnVal = pcs(temp_cib, "resource move D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # ban
        output, returnVal = pcs(temp_cib, "resource ban D1")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # ban --master
        output, returnVal = pcs(temp_cib, "resource ban D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D1-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone --master")
        ac(output, "Error: You must specify a node when moving/banning a stopped resource\n")
        self.assertEqual(1, returnVal)

        # clear
        output, returnVal = pcs(temp_cib, "resource clear D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone")
        ac(output, "")
        self.assertEqual(0, returnVal)

        # clear --master
        output, returnVal = pcs(temp_cib, "resource clear D1 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (D1-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D1-clone --master")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear D2 --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG --master")
        ac(output, "Error: when specifying --master you must use the promotable clone id (DG-clone)\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone --master")
        ac(output, "")
        self.assertEqual(0, returnVal)


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

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def testDebugStartCloneGroup(self):
        o,r = pcs(temp_cib, "resource create D0 ocf:heartbeat:Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D1 ocf:heartbeat:Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D2 ocf:heartbeat:Dummy clone")
        ac(o,"")
        assert r == 0

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(temp_cib, fixture_master_xml("D3"))

        o,r = pcs(temp_cib, "resource debug-start DGroup")
        ac(o,"Error: unable to debug-start a group, try one of the group's resource(s) (D0,D1)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource debug-start D2-clone")
        ac(o,"Error: unable to debug-start a clone, try the clone's resource: D2\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource debug-start D3-master")
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

        o,r = pcs(temp_cib, "resource status")
        assert r == 0
        ac(o," Clone Set: DGroup-clone [DGroup]\n")

        o,r = pcs(temp_cib, "resource clone DGroup")
        ac(o,"Error: cannot clone a group that has already been cloned\n")
        assert r == 1

    def testGroupPromotableCreation(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup"
        )
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource promotable DGroup1")
        ac(o,"Error: unable to find group or resource: DGroup1\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource promotable DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource config")
        assert r == 0
        ac(o,"""\
 Clone: DGroup-clone
  Meta Attrs: promotable=true
  Group: DGroup
   Resource: D1 (class=ocf provider=heartbeat type=Dummy)
    Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
""")

        o,r = pcs(temp_cib, "resource promotable DGroup")
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

        o,r = pcs(temp_cib, "resource status")
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

        o,r = pcs(temp_cib, "resource status")
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

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-clone-monitor-interval-10s)
             Clone: dummy-clone-1
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success(
            "resource delete dummy",
            "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy clone"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-clone-monitor-interval-10s)
             Clone: dummy-clone-1
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

    def testResourcePromotableId(self):
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

        output, returnVal = pcs(temp_cib, "resource promotable dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-clone-monitor-interval-10s)
             Clone: dummy-clone-1
              Meta Attrs: promotable=true
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success(
            "resource delete dummy",
            "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            temp_cib,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy promotable"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (dummy-clone-monitor-interval-10s)
             Clone: dummy-clone-1
              Meta Attrs: promotable=true
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

    def testResourceCloneUpdate(self):
        o, r  = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone"
        )
        assert r == 0
        ac(o, "")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D1-clone
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        o, r = pcs(temp_cib, 'resource update D1-clone foo=bar')
        ac(o, "")
        self.assertEqual(0, r)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D1-clone
              Meta Attrs: foo=bar
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success("resource update D1-clone bar=baz")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D1-clone
              Meta Attrs: bar=baz foo=bar
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        o, r = pcs(temp_cib, 'resource update D1-clone foo=')
        assert r == 0
        ac(o, "")

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: D1-clone
              Meta Attrs: bar=baz
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (A-monitor-interval-10s)
             Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (B-monitor-interval-10s)
            """
        ))

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

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "AA")

        o,r = pcs(temp_cib, "constraint location AA-master prefers rh7-1")
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

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "AG", master_id="AGMaster")

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
        ac(o,"Error: Cannot remove all resources from a cloned group\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource delete B")
        assert r == 0
        o,r = pcs(temp_cib, "resource delete C")
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: AGMaster
              Meta Attrs: promotable=true
              Resource: A (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (A-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: DG-clone
              Group: DG
               Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
               Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
            """
        ))

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
        ac(
            output,
            "Error: Cannot remove all resources from a cloned group\n"
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ungroup DG D1 D2")
        ac(
            output,
            "Error: Cannot remove all resources from a cloned group\n"
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ungroup DG D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: DG-clone
              Group: DG
               Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        output, returnVal = pcs(temp_cib, "resource ungroup DG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success("resource config", outdent(
            """\
             Clone: DG-clone
              Resource: D2 (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (D2-monitor-interval-10s)
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config D1", outdent(
            """\
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Meta Attrs: target-role=Stopped
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success("resource config D1", outdent(
            """\
             Resource: D1 (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
            """
        ))

        # bad resource name
        o,r = pcs(temp_cib, "resource enable NoExist")
        ac(o,"Error: bundle/clone/group/resource 'NoExist' does not exist\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource disable NoExist")
        ac(o,"Error: bundle/clone/group/resource 'NoExist' does not exist\n")
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
        self.assert_pcs_success("resource config group0-clone", outdent(
            """\
             Clone: group0-clone
              Group: group0
               Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)
                Operations: migrate_from interval=0s timeout=20s (dummy0-migrate_from-interval-0s)
                            migrate_to interval=0s timeout=20s (dummy0-migrate_to-interval-0s)
                            monitor interval=10s timeout=20s (dummy0-monitor-interval-10s)
                            reload interval=0s timeout=20s (dummy0-reload-interval-0s)
                            start interval=0s timeout=20s (dummy0-start-interval-0s)
                            stop interval=0s timeout=20s (dummy0-stop-interval-0s)
            """
        ))
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

        # unmanaged resource - by resource defaults
        o,r = pcs(temp_cib, "resource defaults is-managed=false")
        ac(
            o,
            "Warning: Defaults do not apply to resources which override them "
                "with their own defined values\n"
        )
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource defaults is-managed=")
        ac(
            o,
            "Warning: Defaults do not apply to resources which override them "
                "with their own defined values\n"
        )
        assert r == 0

        # resource in an unmanaged group
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy"
        )
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource group add DG D3")
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
        o,r = pcs(temp_cib, "resource group add DG D4")
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
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy clone"
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

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        # disable clone, enable primitive
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

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

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        # disable via 'resource disable', enable via 'resource meta'
        output, retVal = pcs(temp_cib, "resource disable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Meta Attrs: target-role=Stopped
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        output, retVal = pcs(temp_cib, "resource meta dummy-clone target-role=")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        # disable via 'resource meta', enable via 'resource enable'
        output, retVal = pcs(
            temp_cib, "resource meta dummy-clone target-role=Stopped"
        )
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Meta Attrs: target-role=Stopped
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

        output, retVal = pcs(temp_cib, "resource enable dummy-clone")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
            """
        ))

    def testResourceEnableMaster(self):
        # These tests were moved to
        # pcs/lib/commands/test/resource/test_resource_enable_disable.py .
        # However those test the pcs library. I'm leaving these tests here to
        # test the cli part for now.

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(temp_cib, fixture_master_xml("dummy", all_ops=False))

        # disable primitive, enable master
        output, retVal = pcs(temp_cib, "resource disable dummy")
        ac(output, "")
        self.assertEqual(retVal, 0)

        output, retVal = pcs(temp_cib, "resource enable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
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

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
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

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
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

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        # disable via 'resource disable', enable via 'resource meta'
        output, retVal = pcs(temp_cib, "resource disable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true target-role=Stopped
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        output, retVal = pcs(temp_cib, "resource meta dummy-master target-role=")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
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

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true target-role=Stopped
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
            """
        ))

        output, retVal = pcs(temp_cib, "resource enable dummy-master")
        ac(output, "")
        self.assertEqual(retVal, 0)

        self.assert_pcs_success("resource config dummy-master", outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
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
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_success("resource disable dummy1 dummy2")
        self.assert_pcs_success(
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_success("resource disable dummy2 dummy3")
        self.assert_pcs_success(
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_success("resource enable dummy1 dummy2")
        self.assert_pcs_success(
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_fail(
            "resource enable dummy3 dummyX",
            "Error: bundle/clone/group/resource 'dummyX' does not exist\n"
        )
        self.assert_pcs_success(
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
                """
            )
        )

        self.assert_pcs_fail(
            "resource disable dummy1 dummyX",
            "Error: bundle/clone/group/resource 'dummyX' does not exist\n"
        )
        self.assert_pcs_success(
            "resource config",
            outdent(
                """\
                 Resource: dummy1 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
                 Resource: dummy2 (class=ocf provider=pacemaker type=Dummy)
                  Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
                 Resource: dummy3 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attrs: target-role=Stopped
                  Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
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

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (B-monitor-interval-10s)
             Resource: C (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (C-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "resource update B op monitor interval=30s monitor interval=31s role=master")
        ac(o,"Error: role must be: Stopped, Started, Slave or Master (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource update B op monitor interval=30s monitor interval=31s role=Master")
        ac(o,"")
        assert r == 0

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=30s (B-monitor-interval-30s)
                          monitor interval=31s role=Master (B-monitor-interval-31s)
             Resource: C (class=ocf provider=heartbeat type=Dummy)
              Operations: monitor interval=10s timeout=20s (C-monitor-interval-10s)
            """
        ))

        o,r = pcs(temp_cib, "resource update B op interval=5s")
        ac(o,"Error: interval=5s does not appear to be a valid operation action\n")
        assert r == 1

    def testCloneBadResources(self):
        self.setupClusterA(temp_cib)
        o,r = pcs(temp_cib, "resource clone ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource clone ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a clone resource\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource promotable ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource promotable ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a clone resource\n")
        assert r == 1

    def testGroupMSAndClone(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone"
        )
        ac(o,"")
        assert r == 0

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(temp_cib, fixture_master_xml("D2", all_ops=False))

        o,r = pcs(temp_cib, "resource group add DG D1")
        ac(o,"Error: cannot group clone resources\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource group add DG D2")
        ac(o,"Error: cannot group clone resources\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops D3 ocf:heartbeat:Dummy promotable --group xxx clone")
        ac(o,"Error: you can specify only one of clone, promotable, bundle or --group\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops D4 ocf:heartbeat:Dummy promotable --group xxx")
        ac(o,"Error: you can specify only one of clone, promotable, bundle or --group\n")
        assert r == 1

    def testResourceCloneGroup(self):
        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops dummy0 ocf:heartbeat:Dummy --group group"
        )
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone group")
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

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: myip (class=ocf provider=heartbeat type=IPaddr2)
              Operations: monitor interval=10s timeout=20s (myip-monitor-interval-10s)
             Resource: myip2 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ip=3.3.3.3
              Operations: monitor interval=10s timeout=20s (myip2-monitor-interval-10s)
             Resource: myfs (class=ocf provider=heartbeat type=Filesystem)
              Operations: monitor interval=20s timeout=40s (myfs-monitor-interval-20s)
             Resource: myfs2 (class=ocf provider=heartbeat type=Filesystem)
              Attributes: device=x directory=y
              Operations: monitor interval=20s timeout=40s (myfs2-monitor-interval-20s)
             Resource: myfs3 (class=ocf provider=heartbeat type=Filesystem)
              Attributes: device=x directory=y fstype=z
              Operations: monitor interval=20s timeout=40s (myfs3-monitor-interval-20s)
            """
        ))

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

        self.assert_pcs_success("resource config dummies-clone", outdent(
            """\
             Clone: dummies-clone
              Group: dummies
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
               Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
            """
        ))

        output, retVal = pcs(temp_cib, "resource unclone dummies-clone")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource status")
        ac(output, outdent(
            """\
             Resource Group: dummies
                 dummy1\t(ocf::heartbeat:Dummy):\tStopped
                 dummy2\t(ocf::heartbeat:Dummy):\tStopped
                 dummy3\t(ocf::heartbeat:Dummy):\tStopped
            """
        ))
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource clone dummies")
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success("resource config dummies-clone", outdent(
            """\
             Clone: dummies-clone
              Group: dummies
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
               Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success("resource delete dummies-clone", outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and clone) - dummy3
            """
        ))
        output, retVal = pcs(temp_cib, "resource status")
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

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "dummies")

        self.assert_pcs_success("resource config dummies-master", outdent(
            """\
             Clone: dummies-master
              Meta Attrs: promotable=true
              Group: dummies
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
               Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
            """
        ))

        output, retVal = pcs(temp_cib, "resource unclone dummies-master")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource status")
        ac(output, outdent(
            """\
             Resource Group: dummies
                 dummy1\t(ocf::heartbeat:Dummy):\tStopped
                 dummy2\t(ocf::heartbeat:Dummy):\tStopped
                 dummy3\t(ocf::heartbeat:Dummy):\tStopped
            """
        ))
        assert retVal == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(temp_cib, "dummies")

        self.assert_pcs_success("resource config dummies-master", outdent(
            """\
             Clone: dummies-master
              Meta Attrs: promotable=true
              Group: dummies
               Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy1-monitor-interval-10s)
               Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy2-monitor-interval-10s)
               Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                Operations: monitor interval=10s timeout=20s (dummy3-monitor-interval-10s)
            """
        ))

        self.assert_pcs_success("resource delete dummies-master", outdent(
            """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and M/S) - dummy3
            """
        ))
        output, retVal = pcs(temp_cib, "resource status")
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
            "resource create DC ocf:pacemaker:Dummy --no-default-ops clone"
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
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DG1-monitor-interval-10s)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DG2-monitor-interval-10s)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DC-monitor-interval-10s)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10s timeout=20s (DGC1-monitor-interval-10s)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10s timeout=20s (DGC2-monitor-interval-10s)
            """
        )

        cib_original, retVal = pcs(temp_cib, "cluster cib")
        self.assertEqual(0, retVal)

        resources = set([
            "D1", "DG1", "DG2", "GR", "DC", "DC-clone", "DGC1", "DGC2", "GRC",
            "GRC-clone"
        ])
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())

        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attrs: resource-stickiness=0
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Group: GR
              Meta Attrs: resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DG1-monitor-interval-10s)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DG2-monitor-interval-10s)
             Clone: DC-clone
              Meta Attrs: resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DC-monitor-interval-10s)
             Clone: GRC-clone
              Meta Attrs: resource-stickiness=0
              Group: GRC
               Meta Attrs: resource-stickiness=0
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10s timeout=20s (DGC1-monitor-interval-10s)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10s timeout=20s (DGC2-monitor-interval-10s)
            """
        ))

        resources = set(["D1", "DG1", "DC", "DGC1"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, resources
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attrs: resource-stickiness=0
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DG1-monitor-interval-10s)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DG2-monitor-interval-10s)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DC-monitor-interval-10s)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10s timeout=20s (DGC1-monitor-interval-10s)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10s timeout=20s (DGC2-monitor-interval-10s)
            """
        ))

        resources = set(["GRC-clone", "GRC", "DGC1", "DGC2"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GRC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DG1-monitor-interval-10s)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DG2-monitor-interval-10s)
             Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Operations: monitor interval=10s timeout=20s (DC-monitor-interval-10s)
             Clone: GRC-clone
              Meta Attrs: resource-stickiness=0
              Group: GRC
               Meta Attrs: resource-stickiness=0
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10s timeout=20s (DGC1-monitor-interval-10s)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attrs: resource-stickiness=0
                Operations: monitor interval=10s timeout=20s (DGC2-monitor-interval-10s)
            """
        ))

        resources = set(["GR", "DG1", "DG2", "DC-clone", "DC"])
        with open(temp_cib, "w") as f:
            f.write(cib_original)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GR", "DC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        output, retVal = pcs(temp_cib, "resource config")
        ac(output, status)
        self.assertEqual(0, retVal)
        with open(temp_cib, "w") as f:
            f.write(cib_out.toxml())
        self.assert_pcs_success("resource config", outdent(
            """\
             Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations: monitor interval=10s timeout=20s (D1-monitor-interval-10s)
             Group: GR
              Meta Attrs: resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DG1-monitor-interval-10s)
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DG2-monitor-interval-10s)
             Clone: DC-clone
              Meta Attrs: resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
               Meta Attrs: resource-stickiness=0
               Operations: monitor interval=10s timeout=20s (DC-monitor-interval-10s)
             Clone: GRC-clone
              Group: GRC
               Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10s timeout=20s (DGC1-monitor-interval-10s)
               Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                Operations: monitor interval=10s timeout=20s (DGC2-monitor-interval-10s)
            """
        ))

    def testResrourceUtilizationSet(self):
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

class ResourcesReferencedFromAcl(TestCase, AssertPcsMixin):
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

class CloneMasterUpdate(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_no_op_allowed_in_clone_update(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy clone"
        )
        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: migrate_from interval=0s timeout=20s (dummy-migrate_from-interval-0s)
                           migrate_to interval=0s timeout=20s (dummy-migrate_to-interval-0s)
                           monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
                           reload interval=0s timeout=20s (dummy-reload-interval-0s)
                           start interval=0s timeout=20s (dummy-start-interval-0s)
                           stop interval=0s timeout=20s (dummy-stop-interval-0s)
            """
        ))
        self.assert_pcs_fail(
            "resource update dummy-clone op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_fail(
            "resource update dummy-clone foo=bar op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_success("resource config dummy-clone", outdent(
            """\
             Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
               Operations: migrate_from interval=0s timeout=20s (dummy-migrate_from-interval-0s)
                           migrate_to interval=0s timeout=20s (dummy-migrate_to-interval-0s)
                           monitor interval=10s timeout=20s (dummy-monitor-interval-10s)
                           reload interval=0s timeout=20s (dummy-reload-interval-0s)
                           start interval=0s timeout=20s (dummy-start-interval-0s)
                           stop interval=0s timeout=20s (dummy-stop-interval-0s)
            """
        ))

    def test_no_op_allowed_in_master_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(temp_cib, fixture_master_xml("dummy"))
        show = outdent(
            """\
             Clone: dummy-master
              Meta Attrs: promotable=true
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
               Operations: monitor interval=10 role=Master timeout=20 (dummy-monitor-interval-10)
                           monitor interval=11 role=Slave timeout=20 (dummy-monitor-interval-11)
                           notify interval=0s timeout=5 (dummy-notify-interval-0s)
                           start interval=0s timeout=20 (dummy-start-interval-0s)
                           stop interval=0s timeout=20 (dummy-stop-interval-0s)
            """
        )
        self.assert_pcs_success("resource config dummy-master", show)
        self.assert_pcs_fail(
            "resource update dummy-master op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_fail(
            "resource update dummy-master foo=bar op stop timeout=300",
            "Error: op settings must be changed on base resource, not the clone\n"
        )
        self.assert_pcs_success("resource config dummy-master", show)


class TransforMasterToClone(ResourceTest):
    temp_cib = os.path.join(RESOURCES_TMP, "temp-cib.xml")

    def test_transform_master_without_meta_on_meta(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib, fixture_master_xml("dummy"))
        self.assert_effect(
            "resource meta dummy-master a=b",
            """<resources>
                <clone id="dummy-master">
                    <primitive class="ocf" id="dummy" provider="pacemaker"
                        type="Stateful"
                    >
                        <operations>
                            <op id="dummy-monitor-interval-10" interval="10"
                                name="monitor" role="Master" timeout="20"
                            />
                            <op id="dummy-monitor-interval-11" interval="11"
                                name="monitor" role="Slave" timeout="20"
                            />
                            <op id="dummy-notify-interval-0s" interval="0s"
                                name="notify" timeout="5"
                            />
                            <op id="dummy-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="dummy-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="dummy-master-meta_attributes">
                        <nvpair id="dummy-master-meta_attributes-promotable"
                              name="promotable" value="true"
                        />
                        <nvpair id="dummy-master-meta_attributes-a" name="a"
                            value="b"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_transform_master_with_meta_on_meta(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(
            self.temp_cib,
            fixture_master_xml("dummy", meta_dict=dict(a="A", b="B", c="C"))
        )
        self.assert_effect(
            "resource meta dummy-master a=AA b= d=D promotable=",
            """<resources>
                <clone id="dummy-master">
                    <primitive class="ocf" id="dummy" provider="pacemaker"
                        type="Stateful"
                    >
                        <operations>
                            <op id="dummy-monitor-interval-10" interval="10"
                                name="monitor" role="Master" timeout="20"
                            />
                            <op id="dummy-monitor-interval-11" interval="11"
                                name="monitor" role="Slave" timeout="20"
                            />
                            <op id="dummy-notify-interval-0s" interval="0s"
                                name="notify" timeout="5"
                            />
                            <op id="dummy-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="dummy-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="dummy-master-meta_attributes">
                        <nvpair id="dummy-master-meta_attributes-a" name="a"
                            value="AA"
                        />
                        <nvpair id="dummy-master-meta_attributes-c" name="c"
                            value="C"
                        />
                        <nvpair id="dummy-master-meta_attributes-d" name="d"
                            value="D"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_transform_master_without_meta_on_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib, fixture_master_xml("dummy"))
        self.assert_effect(
            "resource update dummy-master meta a=b",
            """<resources>
                <clone id="dummy-master">
                    <primitive class="ocf" id="dummy" provider="pacemaker"
                        type="Stateful"
                    >
                        <operations>
                            <op id="dummy-monitor-interval-10" interval="10"
                                name="monitor" role="Master" timeout="20"
                            />
                            <op id="dummy-monitor-interval-11" interval="11"
                                name="monitor" role="Slave" timeout="20"
                            />
                            <op id="dummy-notify-interval-0s" interval="0s"
                                name="notify" timeout="5"
                            />
                            <op id="dummy-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="dummy-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="dummy-master-meta_attributes">
                        <nvpair id="dummy-master-meta_attributes-promotable"
                              name="promotable" value="true"
                        />
                        <nvpair id="dummy-master-meta_attributes-a" name="a"
                            value="b"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

    def test_transform_master_with_meta_on_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(
            self.temp_cib,
            fixture_master_xml("dummy", meta_dict=dict(a="A", b="B", c="C"))
        )
        self.assert_effect(
            "resource update dummy-master meta a=AA b= d=D promotable=",
            """<resources>
                <clone id="dummy-master">
                    <primitive class="ocf" id="dummy" provider="pacemaker"
                        type="Stateful"
                    >
                        <operations>
                            <op id="dummy-monitor-interval-10" interval="10"
                                name="monitor" role="Master" timeout="20"
                            />
                            <op id="dummy-monitor-interval-11" interval="11"
                                name="monitor" role="Slave" timeout="20"
                            />
                            <op id="dummy-notify-interval-0s" interval="0s"
                                name="notify" timeout="5"
                            />
                            <op id="dummy-start-interval-0s" interval="0s"
                                name="start" timeout="20"
                            />
                            <op id="dummy-stop-interval-0s" interval="0s"
                                name="stop" timeout="20"
                            />
                        </operations>
                    </primitive>
                    <meta_attributes id="dummy-master-meta_attributes">
                        <nvpair id="dummy-master-meta_attributes-a" name="a"
                            value="AA"
                        />
                        <nvpair id="dummy-master-meta_attributes-c" name="c"
                            value="C"
                        />
                        <nvpair id="dummy-master-meta_attributes-d" name="d"
                            value="D"
                        />
                    </meta_attributes>
                </clone>
            </resources>"""
        )

class ResourceRemoveWithTicket(TestCase, AssertPcsMixin):
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
    temp_cib = os.path.join(RESOURCES_TMP, "temp-cib.xml")
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

    def fixture_bundle(self, name, container="docker"):
        self.assert_pcs_success(
            (
                "resource bundle create {0} container {1} image=pcs:test "
                "network control-port=1234"
            ).format(name, container)
        )


@skip_unless_pacemaker_supports_bundle
class BundleShow(BundleCommon):
    # TODO: add test for podman (requires pcmk features 3.2)
    empty_cib = rc("cib-empty.xml")
    def test_docker(self):
        self.fixture_bundle("B1", "docker")
        self.assert_pcs_success(
            "resource config B1",
            outdent("""\
             Bundle: B1
              Docker: image=pcs:test
              Network: control-port=1234
            """)
        )

    def test_rkt(self):
        self.fixture_bundle("B1", "rkt")
        self.assert_pcs_success(
            "resource config B1",
            outdent("""\
             Bundle: B1
              Rkt: image=pcs:test
              Network: control-port=1234
            """)
        )


@skip_unless_pacemaker_supports_bundle
class BundleDelete(BundleCommon):
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
        self.assert_pcs_fail(
            "resource group add bundles B",
            "Error: Unable to find resource: B\n"
        )

    def test_group_add_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource group add group R",
            "Error: cannot group bundle resources\n"
        )

    def test_group_delete_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource group delete B R",
            "Error: Group 'B' does not exist\n"
        )

    def test_group_remove_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource group remove B R",
            "Error: Group 'B' does not exist\n"
        )

    def test_ungroup_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource ungroup B",
            "Error: Group 'B' does not exist\n"
        )


@skip_unless_pacemaker_supports_bundle
class BundleClone(BundleCommon):
    def test_clone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource clone B",
            "Error: unable to find group or resource: B\n"
        )

    def test_clone_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource clone R",
            "Error: cannot clone bundle resource\n"
        )

    def test_unclone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
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
        self.assert_pcs_fail(
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
            "Error: unable to find a resource/clone/group: B\n"
        )

    def test_utilization(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource utilization B aaa=10",
            "Error: Unable to find a resource: B\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_start_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B",
            "Error: unable to debug-start a bundle\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_start_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B",
            "Error: unable to debug-start a bundle, try the bundle's resource: R\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_stop_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B",
            "Error: unable to debug-stop a bundle\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_stop_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B",
            "Error: unable to debug-stop a bundle, try the bundle's resource: R\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_monitor_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B",
            "Error: unable to debug-monitor a bundle\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_monitor_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B",
            "Error: unable to debug-monitor a bundle, try the bundle's resource: R\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_promote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B",
            "Error: unable to debug-promote a bundle\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_promote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B",
            "Error: unable to debug-promote a bundle, try the bundle's resource: R\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_demote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B",
            "Error: unable to debug-demote a bundle\n"
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_demote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B",
            "Error: unable to debug-demote a bundle, try the bundle's resource: R\n"
        )


class ResourceUpdateSpecialChecks(TestCase, AssertPcsMixin):
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
