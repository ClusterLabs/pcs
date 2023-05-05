# pylint: disable=too-many-lines
import json
from textwrap import dedent
from unittest import (
    TestCase,
    skip,
)

from lxml import etree

from pcs import (
    resource,
    utils,
)
from pcs.common import const
from pcs.common.str_tools import format_list_custom_last_separator
from pcs.constraint import LOCATION_NODE_VALIDATION_SKIP_MSG

from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.assertions import (
    AssertPcsMixin,
    ac,
    assert_pcs_status,
)
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.fixture_cib import (
    CachedCibFixture,
    fixture_master_xml,
    fixture_to_cib,
    wrap_element_by_master,
    wrap_element_by_master_file,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    is_minimum_pacemaker_version,
    is_pacemaker_21_without_20_compatibility,
    outdent,
    skip_unless_crm_rule,
    skip_unless_pacemaker_supports_op_onfail_demote,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)

# pylint: disable=invalid-name
# pylint: disable=no-self-use
# pylint: disable=line-too-long
# pylint: disable=too-many-public-methods
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-statements

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)

LOCATION_NODE_VALIDATION_SKIP_WARNING = (
    f"Warning: {LOCATION_NODE_VALIDATION_SKIP_MSG}\n"
)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)

empty_cib = rc("cib-empty.xml")
large_cib = rc("cib-large.xml")


class ResourceDescribe(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def fixture_description(self, advanced=False):
        advanced_params = """\
              trace_ra (advanced use only)
                Description: Set to 1 to turn on resource agent tracing (expect large output) The trace output will be saved to trace_file, if set, or by default to $HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/db.start.2012-11-27.08:37:08
                Type: integer
                Default: 0
              trace_file (advanced use only)
                Description: Path to a file to store resource agent tracing log
                Type: string
            """
        return outdent(
            """\
            ocf:pacemaker:HealthCPU - System health CPU usage

            System health agent that measures the CPU idling and updates the #health-cpu attribute.

            Resource options:
              state (unique)
                Description: Location to store the resource state in.
                Type: string
                Default: /var/run/health-cpu-HealthCPU.state
              yellow_limit (unique)
                Description: Lower (!) limit of idle percentage to switch the health attribute to yellow. I.e. the #health-cpu will go yellow if the %idle of the CPU falls below 50%.
                Type: string
                Default: 50
              red_limit
                Description: Lower (!) limit of idle percentage to switch the health attribute to red. I.e. the #health-cpu will go red if the %idle of the CPU falls below 10%.
                Type: string
                Default: 10
{0}
            Default operations:
              start:
                interval=0s
                timeout=10s
              stop:
                interval=0s
                timeout=10s
              monitor:
                interval=10s
                start-delay=0s
                timeout=10s
            """.format(
                advanced_params if advanced else ""
            )
        )

    def test_success(self):
        self.assert_pcs_success(
            "resource describe ocf:pacemaker:HealthCPU".split(),
            self.fixture_description(),
        )

    def test_full(self):
        self.assert_pcs_success(
            "resource describe ocf:pacemaker:HealthCPU --full".split(),
            self.fixture_description(True),
        )

    def test_success_guess_name(self):
        self.assert_pcs_success(
            "resource describe healthcpu".split(),
            "Assumed agent name 'ocf:pacemaker:HealthCPU' (deduced from"
            + " 'healthcpu')\n"
            + self.fixture_description(),
        )

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "resource describe ocf:pacemaker:nonexistent".split(),
            "Error: Agent 'ocf:pacemaker:nonexistent' is not installed or does "
            "not provide valid metadata: Metadata query for "
            "ocf:pacemaker:nonexistent failed: Input/output error\n"
            + ERRORS_HAVE_OCCURRED,
        )

    def test_nonextisting_agent_guess_name(self):
        self.assert_pcs_fail(
            "resource describe nonexistent".split(),
            (
                "Error: Unable to find agent 'nonexistent', try specifying"
                " its full name\n"
            ),
        )

    def test_more_agents_guess_name(self):
        self.assert_pcs_fail(
            "resource describe dummy".split(),
            (
                "Error: Multiple agents match 'dummy', please specify full"
                " name: 'ocf:heartbeat:Dummy' or 'ocf:pacemaker:Dummy'\n"
            ),
        )

    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "resource describe".split(),
            stdout_start="\nUsage: pcs resource describe...\n",
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "resource describe agent1 agent2".split(),
            stdout_start="\nUsage: pcs resource describe...\n",
        )

    def test_pcsd_interface(self):
        stdout, returncode = self.pcs_runner.run(
            "resource get_resource_agent_info ocf:pacemaker:Dummy".split()
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(
            json.loads(stdout),
            {
                "name": "ocf:pacemaker:Dummy",
                "standard": "ocf",
                "provider": "pacemaker",
                "type": "Dummy",
                "shortdesc": "Example stateless resource agent",
                "longdesc": "This is a Dummy Resource Agent. It does absolutely nothing except \nkeep track of whether its running or not.\nIts purpose in life is for testing and to serve as a template for RA writers.\n\nNB: Please pay attention to the timeouts specified in the actions\nsection below. They should be meaningful for the kind of resource\nthe agent manages. They should be the minimum advised timeouts,\nbut they shouldn't/cannot cover _all_ possible resource\ninstances. So, try to be neither overly generous nor too stingy,\nbut moderate. The minimum timeouts should never be below 10 seconds.",
                "parameters": [
                    {
                        "name": "state",
                        "shortdesc": "State file",
                        "longdesc": "Location to store the resource state in.",
                        "type": "string",
                        "default": "/var/run/Dummy-Dummy.state",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": "_pcs_unique_group_state",
                        "reloadable": True,
                    },
                    {
                        "name": "passwd",
                        "shortdesc": "Password",
                        "longdesc": "Fake password field",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": "_pcs_unique_group_passwd",
                        "reloadable": True,
                    },
                    {
                        "name": "fake",
                        "shortdesc": "Fake attribute that can be changed to cause a reload",
                        "longdesc": "Fake attribute that can be changed to cause a reload",
                        "type": "string",
                        "default": "dummy",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "op_sleep",
                        "shortdesc": "Operation sleep duration in seconds.",
                        "longdesc": "Number of seconds to sleep during operations.  This can be used to test how\nthe cluster reacts to operation timeouts.",
                        "type": "string",
                        "default": "0",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": "_pcs_unique_group_op_sleep",
                        "reloadable": True,
                    },
                    {
                        "name": "fail_start_on",
                        "shortdesc": "Report bogus start failure on specified host",
                        "longdesc": "Start actions will return failure if running on the host specified here, but\nthe resource will start successfully anyway (future monitor calls will find it\nrunning). This can be used to test on-fail=ignore.",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "envfile",
                        "shortdesc": "Environment dump file",
                        "longdesc": "If this is set, the environment will be dumped to this file for every call.",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": "_pcs_unique_group_envfile",
                        "reloadable": True,
                    },
                    {
                        "name": "trace_ra",
                        "shortdesc": "Set to 1 to turn on resource agent tracing (expect large output)",
                        "longdesc": "Set to 1 to turn on resource agent tracing (expect large output) The trace output will be saved to trace_file, if set, or by default to $HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/db.start.2012-11-27.08:37:08",
                        "type": "integer",
                        "default": "0",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "trace_file",
                        "shortdesc": "Path to a file to store resource agent tracing log",
                        "longdesc": "Path to a file to store resource agent tracing log",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                ],
                "actions": [
                    {
                        "name": "start",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "stop",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "monitor",
                        "timeout": "20s",
                        "interval": "10s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "reload",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_to",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_from",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "validate-all",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "meta-data",
                        "timeout": "5s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                ],
                "default_actions": [
                    {
                        "name": "start",
                        "timeout": "20s",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "stop",
                        "timeout": "20s",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "monitor",
                        "timeout": "20s",
                        "interval": "10s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "reload",
                        "timeout": "20s",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_to",
                        "timeout": "20s",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_from",
                        "timeout": "20s",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                ],
            },
        )


class ResourceTestCibFixture(CachedCibFixture):
    def _setup_cib(self):
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP2 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.92 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP3 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.93 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP4 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.94 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.95 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP6 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.96 op monitor interval=30s --force"
            ).split()
        )
        self.assert_pcs_success(
            "resource group add TestGroup1 ClusterIP".split()
        )
        self.assert_pcs_success(
            "resource group add TestGroup2 ClusterIP2 ClusterIP3".split()
        )
        self.assert_pcs_success("resource clone ClusterIP4".split())
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master_file(
            self.cache_path, "ClusterIP5", master_id="Master"
        )


CIB_FIXTURE = ResourceTestCibFixture("fixture_tier1_resource", empty_cib)


class Resource(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource")
        self.temp_large_cib = get_tmp_file("tier1_resource_large")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        write_file_to_tmpfile(large_cib, self.temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setupClusterA(self):
        write_file_to_tmpfile(CIB_FIXTURE.cache_path, self.temp_cib)

    def testCaseInsensitive(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 dummy".split(),
        )
        ac(
            o,
            "Error: Multiple agents match 'dummy', please specify full name: "
            "'ocf:heartbeat:Dummy' or 'ocf:pacemaker:Dummy'\n"
            + ERRORS_HAVE_OCCURRED,
        )
        assert r == 1

        self.assert_pcs_success(
            "resource create --no-default-ops D1 systemhealth".split(),
            "Assumed agent name 'ocf:pacemaker:SystemHealth'"
            " (deduced from 'systemhealth')\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 SYSTEMHEALTH".split(),
            "Assumed agent name 'ocf:pacemaker:SystemHealth'"
            " (deduced from 'SYSTEMHEALTH')\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D3 ipaddr2 ip=1.1.1.1".split(),
            "Assumed agent name 'ocf:heartbeat:IPaddr2'"
            " (deduced from 'ipaddr2')\n",
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D4 ipaddr3".split(),
        )
        ac(
            o,
            "Error: Unable to find agent 'ipaddr3', try specifying its full name\n"
            + ERRORS_HAVE_OCCURRED,
        )
        assert r == 1

    def testEmpty(self):
        output, returnVal = pcs(self.temp_cib.name, ["resource"])
        assert returnVal == 0, "Unable to list resources"
        assert output == "NO resources configured\n", "Bad output"

    def testAddResourcesLargeCib(self):
        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource create dummy0 ocf:heartbeat:Dummy --no-default-ops".split(),
        )
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource config dummy0".split()
        )
        assert returnVal == 0
        ac(
            output,
            outdent(
                """\
            Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy0-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )

    def _test_delete_remove_resources(self, command):
        assert command in {"delete", "remove"}

        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )

        self.assert_pcs_success(
            f"resource {command} ClusterIP".split(),
            "Deleting Resource - ClusterIP\n",
        )

        self.assert_pcs_fail(
            "resource config ClusterIP".split(),
            "Warning: Unable to find resource 'ClusterIP'\nError: No resource found\n",
        )

        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

        self.assert_pcs_fail(
            f"resource {command} ClusterIP".split(),
            "Error: Resource 'ClusterIP' does not exist.\n",
        )

    def testDeleteResources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource delete".split(),
            stdout_start="\nUsage: pcs resource delete...",
        )

        self._test_delete_remove_resources("delete")

    def testRemoveResources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource remove".split(),
            stdout_start="\nUsage: pcs resource remove...",
        )

        self._test_delete_remove_resources("remove")

    def testResourceShow(self):
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-30s
                  interval=30s
            """
            ),
        )

    def testAddOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )

        line = "resource op add"
        output, returnVal = pcs(self.temp_cib.name, line.split())
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = "resource op remove"
        output, returnVal = pcs(self.temp_cib.name, line.split())
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = "resource op add ClusterIP monitor interval=31s"
        output, returnVal = pcs(self.temp_cib.name, line.split())
        ac(
            output,
            """\
Error: operation monitor already specified for ClusterIP, use --force to override:
monitor interval=30s (ClusterIP-monitor-interval-30s)
""",
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource op add ClusterIP monitor interval=31s --force".split(),
        )
        assert returnVal == 0
        assert output == ""

        line = "resource op add ClusterIP monitor interval=31s"
        output, returnVal = pcs(self.temp_cib.name, line.split())
        ac(
            output,
            """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""",
        )
        assert returnVal == 1

        line = "resource op add ClusterIP monitor interval=31"
        output, returnVal = pcs(self.temp_cib.name, line.split())
        ac(
            output,
            """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""",
        )
        assert returnVal == 1

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource op add ClusterIP moni=tor interval=60".split(),
        )
        ac(
            output,
            """\
Error: moni=tor does not appear to be a valid operation action
""",
        )
        assert returnVal == 1

        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-30s
                  interval=30s
                monitor: ClusterIP-monitor-interval-31s
                  interval=31s
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1 enabled=0".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=1
                monitor: OPTest-monitor-interval-25s
                  interval=25s
                  enabled=0
                  OCF_CHECK_LEVEL=1
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest2 ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=2 op start timeout=30s".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest2 start timeout=1800s".split(),
        )
        ac(
            o,
            """\
Error: operation start with interval 0s already specified for OPTest2:
start interval=0s timeout=30s (OPTest2-start-interval-0s)
""",
        )
        assert r == 1

        output, retVal = pcs(
            self.temp_cib.name,
            "resource op add OPTest2 start interval=100".split(),
        )
        ac(
            output,
            """\
Error: operation start already specified for OPTest2, use --force to override:
start interval=0s timeout=30s (OPTest2-start-interval-0s)
""",
        )
        self.assertEqual(1, retVal)

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest2 monitor timeout=1800s".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest2".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest2-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=1
                monitor: OPTest2-monitor-interval-25s
                  interval=25s
                  OCF_CHECK_LEVEL=2
                start: OPTest2-start-interval-0s
                  interval=0s
                  timeout=30s
                monitor: OPTest2-monitor-interval-60s
                  interval=60s
                  timeout=1800s
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest3 ocf:heartbeat:Dummy op monitor OCF_CHECK_LEVEL=1".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest3".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest3-monitor-interval-60s
                  interval=60s
                  OCF_CHECK_LEVEL=1
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest4 ocf:heartbeat:Dummy op monitor interval=30s".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest4".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest4-monitor-interval-60s
                  interval=60s
                  OCF_CHECK_LEVEL=1
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest5 ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest5".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest5-monitor-interval-60s
                  interval=60s
                  OCF_CHECK_LEVEL=1
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest6 ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1".split(),
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource config OPTest6".split(),
            outdent(
                """\
            Resource: OPTest6 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest6-monitor-interval-10s
                  interval=10s
                  timeout=20s
                monitor: OPTest6-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=1
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OPTest7 ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update OPTest7 op monitor interval=60s OCF_CHECK_LEVEL=1".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1".split(),
        )
        ac(
            o,
            """\
Error: operation monitor already specified for OPTest7, use --force to override:
monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)
""",
        )
        self.assertEqual(1, r)

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1 --force".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OPTest7".split())
        ac(
            o,
            outdent(
                """\
            Resource: OPTest7 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OPTest7-monitor-interval-60s
                  interval=60s
                  OCF_CHECK_LEVEL=1
                monitor: OPTest7-monitor-interval-61s
                  interval=61s
                  OCF_CHECK_LEVEL=1
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OPTest7 monitor interval=60s OCF_CHECK_LEVEL=1".split(),
        )
        ac(
            o,
            """\
Error: operation monitor with interval 60s already specified for OPTest7:
monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)
""",
        )
        assert r == 1

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops OCFTest1 ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_fail(
            "resource op add OCFTest1 monitor interval=31s".split(),
            outdent(
                """\
                Error: operation monitor already specified for OCFTest1, use --force to override:
                monitor interval=10s timeout=20s (OCFTest1-monitor-interval-10s)
                """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OCFTest1 monitor interval=31s --force".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add OCFTest1 monitor interval=30s OCF_CHECK_LEVEL=15".split(),
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource config OCFTest1".split(),
            outdent(
                """\
                Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OCFTest1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                    monitor: OCFTest1-monitor-interval-31s
                      interval=31s
                    monitor: OCFTest1-monitor-interval-30s
                      interval=30s
                      OCF_CHECK_LEVEL=15
                """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource update OCFTest1 op monitor interval=61s OCF_CHECK_LEVEL=5".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OCFTest1".split())
        ac(
            o,
            outdent(
                """\
            Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OCFTest1-monitor-interval-61s
                  interval=61s
                  OCF_CHECK_LEVEL=5
                monitor: OCFTest1-monitor-interval-31s
                  interval=31s
                monitor: OCFTest1-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=15
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OCFTest1".split())
        ac(
            o,
            outdent(
                """\
            Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OCFTest1-monitor-interval-60s
                  interval=60s
                  OCF_CHECK_LEVEL=4
                monitor: OCFTest1-monitor-interval-31s
                  interval=31s
                monitor: OCFTest1-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=15
            """
            ),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4 interval=35s".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config OCFTest1".split())
        ac(
            o,
            outdent(
                """\
            Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: OCFTest1-monitor-interval-35s
                  interval=35s
                  OCF_CHECK_LEVEL=4
                monitor: OCFTest1-monitor-interval-31s
                  interval=31s
                monitor: OCFTest1-monitor-interval-30s
                  interval=30s
                  OCF_CHECK_LEVEL=15
            """
            ),
        )
        assert r == 0

        self.assert_pcs_success(
            "resource create --no-default-ops state ocf:pacemaker:Stateful".split(),
            "Warning: changing a monitor operation interval from 10s to 11 to"
            " make the operation unique\n",
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10".split(),
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)
                """
            ),
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10 role=Started".split(),
            outdent(
                """\
                Error: operation monitor with interval 10s already specified for state:
                monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)
                """
            ),
        )

        self.assert_pcs_success(
            "resource op add state monitor interval=15 role=Master --force".split()
        )

        self.assert_pcs_success(
            "resource config state".split(),
            outdent(
                f"""\
            Resource: state (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: state-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: state-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                monitor: state-monitor-interval-15
                  interval=15
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
            """
            ),
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_add_operation_onfail_demote_upgrade_cib(self):
        write_file_to_tmpfile(rc("cib-empty-3.3.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split()
        )
        self.assert_pcs_success(
            "resource op add R start on-fail=demote".split(),
            stdout_full="Cluster CIB has been upgraded to latest version\n",
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_update_add_operation_onfail_demote_upgrade_cib(self):
        write_file_to_tmpfile(rc("cib-empty-3.3.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split()
        )
        self.assert_pcs_success(
            "resource update R op start on-fail=demote".split(),
            stdout_full="Cluster CIB has been upgraded to latest version\n",
        )

    def _test_delete_remove_operation(self, command):
        assert command in {"delete", "remove"}

        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )

        self.assert_pcs_success(
            "resource op add ClusterIP monitor interval=31s --force".split()
        )

        self.assert_pcs_success(
            "resource op add ClusterIP monitor interval=32s --force".split()
        )

        self.assert_pcs_fail(
            f"resource op {command} ClusterIP-monitor-interval-32s-xxxxx".split(),
            "Error: unable to find operation id: "
            "ClusterIP-monitor-interval-32s-xxxxx\n",
        )

        self.assert_pcs_success(
            f"resource op {command} ClusterIP-monitor-interval-32s".split()
        )

        self.assert_pcs_success(
            f"resource op {command} ClusterIP monitor interval=30s".split()
        )

        self.assert_pcs_fail(
            f"resource op {command} ClusterIP monitor interval=30s".split(),
            "Error: Unable to find operation matching: monitor interval=30s\n",
        )

        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-31s
                  interval=31s
            """
            ),
        )

        self.assert_pcs_success(
            f"resource op {command} ClusterIP monitor interval=31s".split()
        )

        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
            """
            ),
        )

        self.assert_pcs_success(
            "resource op add ClusterIP monitor interval=31s".split()
        )

        self.assert_pcs_success(
            "resource op add ClusterIP monitor interval=32s --force".split()
        )

        self.assert_pcs_success(
            "resource op add ClusterIP stop timeout=34s".split()
        )

        self.assert_pcs_success(
            "resource op add ClusterIP start timeout=33s".split()
        )

        self.assert_pcs_success(
            f"resource op {command} ClusterIP monitor".split()
        )

        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                stop: ClusterIP-stop-interval-0s
                  interval=0s
                  timeout=34s
                start: ClusterIP-start-interval-0s
                  interval=0s
                  timeout=33s
            """
            ),
        )

    def testDeleteOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op delete".split(),
            stdout_start="\nUsage: pcs resource op delete...",
        )

        self._test_delete_remove_operation("delete")

    def testRemoveOperation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op remove".split(),
            stdout_start="\nUsage: pcs resource op remove...",
        )

        self._test_delete_remove_operation("remove")

    def testUpdateOperation(self):
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-30s
                  interval=30s
            """
            ),
        )

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=32s".split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-32s
                  interval=32s
            """
            ),
        )

        show_clusterip = outdent(
            """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-33s
                  interval=33s
                start: ClusterIP-start-interval-30s
                  interval=30s
                  timeout=180s
            """
        )
        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s".split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        self.assert_pcs_success(
            "resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s".split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        self.assert_pcs_success("resource update ClusterIP op".split())
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        self.assert_pcs_success("resource update ClusterIP op monitor".split())
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        # test invalid id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ab#cd".split(),
            "Error: invalid operation id 'ab#cd', '#' is not a valid character"
            " for a operation id\n",
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        # test existing id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ClusterIP".split(),
            "Error: id 'ClusterIP' is already in use, please specify another"
            " one\n",
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        # test id change
        # there is a bug:
        # - first an existing operation is removed
        # - then a new operation is created at the same place
        # - therefore options not specified for in the command are removed
        #    instead of them being kept from the old operation
        # This needs to be fixed. However it's not my task currently.
        # Moreover it is documented behavior.
        self.assert_pcs_success(
            "resource update ClusterIP op monitor id=abcd".split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            outdent(
                """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: abcd
                  interval=60s
                start: ClusterIP-start-interval-30s
                  interval=30s
                  timeout=180s
            """
            ),
        )

        # test two monitor operations:
        # - the first one is updated
        # - operation duplicity detection test
        self.assert_pcs_success(
            "resource create A ocf:heartbeat:Dummy op monitor interval=10 op monitor interval=20".split()
        )
        self.assert_pcs_success(
            "resource config A".split(),
            outdent(
                """\
            Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations:
                migrate_from: A-migrate_from-interval-0s
                  interval=0s
                  timeout=20s
                migrate_to: A-migrate_to-interval-0s
                  interval=0s
                  timeout=20s
                monitor: A-monitor-interval-10
                  interval=10
                monitor: A-monitor-interval-20
                  interval=20
                reload: A-reload-interval-0s
                  interval=0s
                  timeout=20s
                start: A-start-interval-0s
                  interval=0s
                  timeout=20s
                stop: A-stop-interval-0s
                  interval=0s
                  timeout=20s
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update A op monitor interval=20".split(),
        )
        ac(
            output,
            """\
Error: operation monitor with interval 20s already specified for A:
monitor interval=20 (A-monitor-interval-20)
""",
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update A op monitor interval=11".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config A".split(),
            outdent(
                """\
            Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations:
                migrate_from: A-migrate_from-interval-0s
                  interval=0s
                  timeout=20s
                migrate_to: A-migrate_to-interval-0s
                  interval=0s
                  timeout=20s
                monitor: A-monitor-interval-11
                  interval=11
                monitor: A-monitor-interval-20
                  interval=20
                reload: A-reload-interval-0s
                  interval=0s
                  timeout=20s
                start: A-start-interval-0s
                  interval=0s
                  timeout=20s
                stop: A-stop-interval-0s
                  interval=0s
                  timeout=20s
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create B ocf:heartbeat:Dummy --no-default-ops".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource op remove B-monitor-interval-10s".split()
        )

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=60s".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-60s
                  interval=60s
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=30".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-30
                  interval=30
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op start interval=0 timeout=10".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-30
                  interval=30
                start: B-start-interval-0
                  interval=0
                  timeout=10
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op start interval=0 timeout=20".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-30
                  interval=30
                start: B-start-interval-0
                  interval=0
                  timeout=20
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=33".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-33
                  interval=33
                start: B-start-interval-0
                  interval=0
                  timeout=20
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=100 role=Master".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                f"""\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-33
                  interval=33
                start: B-start-interval-0
                  interval=0
                  timeout=20
                monitor: B-monitor-interval-100
                  interval=100
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
            """
            ),
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource update B op start interval=0 timeout=22".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource config B".split())
        ac(
            output,
            outdent(
                f"""\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-33
                  interval=33
                start: B-start-interval-0
                  interval=0
                  timeout=22
                monitor: B-monitor-interval-100
                  interval=100
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
            """
            ),
        )
        self.assertEqual(0, returnVal)

    def testGroupDeleteTest(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AGroup".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AGroup".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy --group AGroup".split(),
        )
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource status".split())
        assert r == 0
        if is_pacemaker_21_without_20_compatibility():
            ac(
                o,
                outdent(
                    """\
                      * Resource Group: AGroup:
                        * A1\t(ocf:heartbeat:Dummy):\t Stopped
                        * A2\t(ocf:heartbeat:Dummy):\t Stopped
                        * A3\t(ocf:heartbeat:Dummy):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                o,
                """\
  * Resource Group: AGroup:
    * A1\t(ocf::heartbeat:Dummy):\tStopped
    * A2\t(ocf::heartbeat:Dummy):\tStopped
    * A3\t(ocf::heartbeat:Dummy):\tStopped
""",
            )
        else:
            ac(
                o,
                """\
 Resource Group: AGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
     A3\t(ocf::heartbeat:Dummy):\tStopped
""",
            )

        self.assert_pcs_success(
            "resource delete AGroup".split(),
            outdent(
                """\
            Removing group: AGroup (and all resources within group)
            Stopping all resources in group: AGroup...
            Deleting Resource - A1
            Deleting Resource - A2
            Deleting Resource (and group) - A3
            """
            ),
        )

        o, r = pcs(self.temp_cib.name, "resource status".split())
        assert r == 0
        ac(o, "NO resources configured\n")

    @skip_unless_crm_rule()
    def testGroupUngroup(self):
        self.setupClusterA()
        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP3 prefers rh7-1".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        self.assert_pcs_success(
            "resource delete ClusterIP2".split(),
            "Deleting Resource - ClusterIP2\n",
        )

        self.assert_pcs_success(
            "resource delete ClusterIP3".split(),
            outdent(
                """\
            Removing Constraint - location-ClusterIP3-rh7-1-INFINITY
            Deleting Resource (and group) - ClusterIP3
            """
            ),
        )

        # pylint: disable=unused-variable
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A4 ocf:heartbeat:Dummy".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A5 ocf:heartbeat:Dummy".split(),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource group add AGroup A1 A2 A3 A4 A5".split(),
        )
        assert r == 0

        self.assert_pcs_success(
            "resource config AGroup".split(),
            outdent(
                """\
            Group: AGroup
              Resource: A1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: A2 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A2-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: A3 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A3-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: A4 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A4-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: A5 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A5-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource group add dummies dummylarge".split(),
        )
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource delete dummies".split()
        )
        ac(
            output,
            outdent(
                """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group) - dummylarge
            """
            ),
        )
        assert returnVal == 0

    def testGroupOrder(self):
        # This was cosidered for removing during 'resource group add' command
        # and tests overhaul. However, this is the only test where "resource
        # group list" is called. Due to that this test was not deleted.
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops B ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops C ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops E ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops F ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops G ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops H ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops I ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops J ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops K ocf:heartbeat:Dummy".split(),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add RGA A B C E D K J I".split()
        )
        assert returnVal == 0
        assert output == "", output

        output, returnVal = pcs(self.temp_cib.name, ["resource"])
        assert returnVal == 0
        if is_pacemaker_21_without_20_compatibility():
            ac(
                output,
                outdent(
                    """\
                      * F\t(ocf:heartbeat:Dummy):\t Stopped
                      * G\t(ocf:heartbeat:Dummy):\t Stopped
                      * H\t(ocf:heartbeat:Dummy):\t Stopped
                      * Resource Group: RGA:
                        * A\t(ocf:heartbeat:Dummy):\t Stopped
                        * B\t(ocf:heartbeat:Dummy):\t Stopped
                        * C\t(ocf:heartbeat:Dummy):\t Stopped
                        * E\t(ocf:heartbeat:Dummy):\t Stopped
                        * D\t(ocf:heartbeat:Dummy):\t Stopped
                        * K\t(ocf:heartbeat:Dummy):\t Stopped
                        * J\t(ocf:heartbeat:Dummy):\t Stopped
                        * I\t(ocf:heartbeat:Dummy):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                output,
                """\
  * F\t(ocf::heartbeat:Dummy):\tStopped
  * G\t(ocf::heartbeat:Dummy):\tStopped
  * H\t(ocf::heartbeat:Dummy):\tStopped
  * Resource Group: RGA:
    * A\t(ocf::heartbeat:Dummy):\tStopped
    * B\t(ocf::heartbeat:Dummy):\tStopped
    * C\t(ocf::heartbeat:Dummy):\tStopped
    * E\t(ocf::heartbeat:Dummy):\tStopped
    * D\t(ocf::heartbeat:Dummy):\tStopped
    * K\t(ocf::heartbeat:Dummy):\tStopped
    * J\t(ocf::heartbeat:Dummy):\tStopped
    * I\t(ocf::heartbeat:Dummy):\tStopped
""",
            )
        else:
            ac(
                output,
                """\
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
""",
            )

        output, returnVal = pcs(
            self.temp_cib.name, "resource group list".split()
        )
        ac(output, "RGA: A B C E D K J I\n")
        assert returnVal == 0

    @skip_unless_crm_rule()
    def testClusterConfig(self):
        self.setupClusterA()

        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf"),
        }
        self.assert_pcs_success(
            ["config"],
            outdent(
                """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
              Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
                Attributes: ClusterIP6-instance_attributes
                  cidr_netmask=32
                  ip=192.168.0.96
                Operations:
                  monitor: ClusterIP6-monitor-interval-30s
                    interval=30s
              Group: TestGroup1
                Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.99
                  Operations:
                    monitor: ClusterIP-monitor-interval-30s
                      interval=30s
              Group: TestGroup2
                Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP2-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.92
                  Operations:
                    monitor: ClusterIP2-monitor-interval-30s
                      interval=30s
                Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP3-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.93
                  Operations:
                    monitor: ClusterIP3-monitor-interval-30s
                      interval=30s
              Clone: ClusterIP4-clone
                Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP4-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.94
                  Operations:
                    monitor: ClusterIP4-monitor-interval-30s
                      interval=30s
              Clone: Master
                Meta Attributes:
                  promotable=true
                Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP5-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.95
                  Operations:
                    monitor: ClusterIP5-monitor-interval-30s
                      interval=30s

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

            Tags:
             No tags defined

            Quorum:
              Options:
            """
            ),
        )

    def testCloneRemove(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "constraint location D1-clone prefers rh7-1".split(),
        )
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers rh7-1 --force".split(),
        )
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D1-clone
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete D1-clone".split(),
            outdent(
                """\
            Removing Constraint - location-D1-clone-rh7-1-INFINITY
            Removing Constraint - location-D1-rh7-1-INFINITY
            Deleting Resource - D1
            """
            ),
        )

        self.assert_pcs_success(
            "resource config".split(),
            "",
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource create d99 ocf:heartbeat:Dummy clone globally-unique=true".split(),
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource delete d99".split(), "Deleting Resource - d99\n"
        )

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource clone dummylarge".split()
        )
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource delete dummylarge".split()
        )
        ac(output, "Deleting Resource - dummylarge\n")
        assert returnVal == 0

    def testCloneGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource group add dummies dummylarge".split(),
        )
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource clone dummies".split()
        )
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource delete dummies".split()
        )
        ac(
            output,
            outdent(
                """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group and clone) - dummylarge
            """
            ),
        )
        assert returnVal == 0

    @skip_unless_crm_rule()
    def testMasterSlaveRemove(self):
        self.setupClusterA()
        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP5 prefers rh7-1 --force".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location Master prefers rh7-2".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        self.assert_pcs_success(
            "resource delete Master".split(),
            outdent(
                """\
            Removing Constraint - location-Master-rh7-2-INFINITY
            Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
            Deleting Resource - ClusterIP5
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP5 prefers rh7-1".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP5 prefers rh7-2".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING
        self.assert_pcs_success(
            "resource delete ClusterIP5".split(),
            outdent(
                """\
            Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
            Removing Constraint - location-ClusterIP5-rh7-2-INFINITY
            Deleting Resource - ClusterIP5
            """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.95 op monitor interval=30s"
            ).split()
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP5 prefers rh7-1".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location ClusterIP5 prefers rh7-2".split(),
        )
        assert returnVal == 0
        assert output == LOCATION_NODE_VALIDATION_SKIP_WARNING

        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf"),
        }
        self.assert_pcs_success(
            ["config"],
            outdent(
                """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:
              Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)
                Attributes: ClusterIP6-instance_attributes
                  cidr_netmask=32
                  ip=192.168.0.96
                Operations:
                  monitor: ClusterIP6-monitor-interval-30s
                    interval=30s
              Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)
                Attributes: ClusterIP5-instance_attributes
                  cidr_netmask=32
                  ip=192.168.0.95
                Operations:
                  monitor: ClusterIP5-monitor-interval-30s
                    interval=30s
              Group: TestGroup1
                Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.99
                  Operations:
                    monitor: ClusterIP-monitor-interval-30s
                      interval=30s
              Group: TestGroup2
                Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP2-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.92
                  Operations:
                    monitor: ClusterIP2-monitor-interval-30s
                      interval=30s
                Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP3-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.93
                  Operations:
                    monitor: ClusterIP3-monitor-interval-30s
                      interval=30s
              Clone: ClusterIP4-clone
                Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP4-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.94
                  Operations:
                    monitor: ClusterIP4-monitor-interval-30s
                      interval=30s

            Stonith Devices:
            Fencing Levels:

            Location Constraints:
              Resource: ClusterIP5
                Enabled on:
                  Node: rh7-1 (score:INFINITY) (id:location-ClusterIP5-rh7-1-INFINITY)
                  Node: rh7-2 (score:INFINITY) (id:location-ClusterIP5-rh7-2-INFINITY)
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
        del self.pcs_runner.mock_settings["corosync_conf_file"]

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_large_cib, "dummylarge")

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource delete dummylarge".split()
        )
        ac(output, "Deleting Resource - dummylarge\n")
        assert returnVal == 0

    def testMasterSlaveGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource group add dummies dummylarge".split(),
        )
        ac(output, "")
        assert returnVal == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_large_cib, "dummies")

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource delete dummies".split()
        )
        ac(
            output,
            outdent(
                """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource (and group and M/S) - dummylarge
            """
            ),
        )
        assert returnVal == 0

    def testMSGroup(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add Group D0 D1".split()
        )
        assert returnVal == 0
        assert output == "", [output]

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "Group", master_id="GroupMaster")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: GroupMaster
              Meta Attributes:
                promotable=true
              Group: Group
                Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D0-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete D0".split(), "Deleting Resource - D0\n"
        )

        self.assert_pcs_success(
            "resource delete D1".split(),
            "Deleting Resource (and group and M/S) - D1\n",
        )

    def testUnclone(self):
        # see also BundleClone
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy1 ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy2 ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add gr dummy1".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr".split()
        )
        ac(output, "Error: 'gr' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        # unclone with a clone itself specified
        output, returnVal = pcs(
            self.temp_cib.name, "resource group add gr dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource clone gr".split())
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: gr-clone
              Group: gr
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr-clone".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        # unclone with a cloned group specified
        output, returnVal = pcs(self.temp_cib.name, "resource clone gr".split())
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: gr-clone
              Group: gr
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Group: gr
              Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(self.temp_cib.name, "resource clone gr".split())
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: gr-clone
              Group: gr
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy1".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: gr-clone
              Group: gr
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )

    def testUncloneMaster(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pacemaker:Stateful".split(),
            "Warning: changing a monitor operation interval from 10s to 11 to make the operation unique\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pacemaker:Stateful".split(),
            "Warning: changing a monitor operation interval from 10s to 11 to make the operation unique\n",
        )

        # try to unclone a non-cloned resource
        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy1".split()
        )
        ac(output, "Error: 'dummy1' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add gr dummy1".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr".split()
        )
        ac(output, "Error: 'gr' is not a clone resource\n")
        self.assertEqual(1, returnVal)

        # unclone with a cloned primitive specified
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummy2")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy1-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            Clone: dummy2-master
              Meta Attributes:
                promotable=true
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy2-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy2-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: dummy2-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: dummy2-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy1-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        # unclone with a clone itself specified
        output, returnVal = pcs(
            self.temp_cib.name, "resource group add gr dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Clone: gr-master
              Meta Attributes:
                promotable=true
              Group: gr
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr-master".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy1-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy2-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy2-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        # unclone with a cloned group specified
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Clone: gr-master
              Meta Attributes:
                promotable=true
              Group: gr
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone gr".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Group: gr
              Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy1-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy1-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
              Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy2-monitor-interval-10s
                    interval=10s
                    timeout=20s
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy2-monitor-interval-11
                    interval=11
                    timeout=20s
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        # unclone with a cloned grouped resource specified
        output, returnVal = pcs(
            self.temp_cib.name, "resource ungroup gr dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: dummy2-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: dummy2-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            Clone: gr-master
              Meta Attributes:
                promotable=true
              Group: gr
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy1".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: dummy2-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: dummy2-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: dummy1-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: dummy1-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add gr dummy1 dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Clone: gr-master
              Meta Attributes:
                promotable=true
              Group: gr
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource unclone dummy2".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
              Operations:
                monitor: dummy2-monitor-interval-10s
                  interval=10s
                  timeout=20s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                monitor: dummy2-monitor-interval-11
                  interval=11
                  timeout=20s
                  role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            Clone: gr-master
              Meta Attributes:
                promotable=true
              Group: gr
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                      role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11
                      timeout=20s
                      role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
            """
            ),
        )

    def testCloneGroupMember(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy --group AG".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group AG".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource clone D0".split())
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, ["resource", "config"])
        ac(
            o,
            outdent(
                """\
            Group: AG
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D0-clone
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D0-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource clone D1".split())
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, ["resource", "config"])
        ac(
            o,
            outdent(
                """\
            Clone: D0-clone
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D0-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D1-clone
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )
        assert r == 0

    def testPromotableGroupMember(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy --group AG".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group AG".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource promotable D0".split())
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config".split())
        ac(
            o,
            outdent(
                """\
            Group: AG
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D0-clone
              Meta Attributes: D0-clone-meta_attributes
                promotable=true
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D0-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource promotable D1".split())
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource config".split())
        ac(
            o,
            outdent(
                """\
            Clone: D0-clone
              Meta Attributes: D0-clone-meta_attributes
                promotable=true
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D0-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D1-clone
              Meta Attributes: D1-clone-meta_attributes
                promotable=true
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )
        assert r == 0

    def testCloneMaster(self):
        # see also BundleClone
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy".split(),
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(self.temp_cib.name, "resource clone D0".split())
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource promotable D3 promotable=false".split(),
        )
        assert returnVal == 1
        assert (
            output
            == "Error: you cannot specify both promotable option and promotable keyword\n"
        ), [output]

        output, returnVal = pcs(
            self.temp_cib.name, "resource promotable D3".split()
        )
        assert returnVal == 0
        assert output == "", [output]

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(
            self.temp_cib, "D1", master_id="D1-master-custom"
        )

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "D2")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D0-clone
              Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D0-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D3-clone
              Meta Attributes: D3-clone-meta_attributes
                promotable=true
              Resource: D3 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D3-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D1-master-custom
              Meta Attributes:
                promotable=true
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D2-master
              Meta Attributes:
                promotable=true
              Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete D0".split(), "Deleting Resource - D0\n"
        )

        self.assert_pcs_success(
            "resource delete D2".split(), "Deleting Resource - D2\n"
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: D0-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: D2 (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: D2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: D3-clone
              Meta Attributes: D3-clone-meta_attributes
                promotable=true
              Resource: D3 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D3-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: D1-master-custom
              Meta Attributes:
                promotable=true
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testLSBResource(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D2 lsb:network foo=bar".split(),
            (
                "Error: invalid resource option 'foo', there are no options"
                " allowed, use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 lsb:network foo=bar --force".split(),
            "Warning: invalid resource option 'foo', there are no options"
            " allowed\n",
        )

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
                Resource: D2 (class=lsb type=network)
                  Attributes: D2-instance_attributes
                    foo=bar
                  Operations:
                    monitor: D2-monitor-interval-15
                      interval=15
                      timeout=15
                """
            ),
        )

        self.assert_pcs_fail(
            "resource update D2 bar=baz".split(),
            "Error: invalid resource option 'bar', there are no options"
            " allowed, use --force to override\n",
        )

        self.assert_pcs_success(
            "resource update D2 bar=baz --force".split(),
            "Warning: invalid resource option 'bar', there are no options"
            " allowed\n",
        )

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
                Resource: D2 (class=lsb type=network)
                  Attributes: D2-instance_attributes
                    bar=baz
                    foo=bar
                  Operations:
                    monitor: D2-monitor-interval-15
                      interval=15
                      timeout=15
                """
            ),
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def testDebugStartCloneGroup(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create D0 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create D1 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create D2 ocf:heartbeat:Dummy clone".split(),
        )
        ac(o, "")
        assert r == 0

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("D3"))

        o, r = pcs(self.temp_cib.name, "resource debug-start DGroup".split())
        ac(
            o,
            "Error: unable to debug-start a group, try one of the group's resource(s) (D0,D1)\n",
        )
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource debug-start D2-clone".split())
        ac(
            o,
            "Error: unable to debug-start a clone, try the clone's resource: D2\n",
        )
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource debug-start D3-master".split())
        ac(
            o,
            "Error: unable to debug-start a master, try the master's resource: D3\n",
        )
        assert r == 1

    def testGroupCloneCreation(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        assert r == 0
        assert o == ""

        o, r = pcs(self.temp_cib.name, "resource clone DGroup1".split())
        ac(o, "Error: unable to find group or resource: DGroup1\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource clone DGroup".split())
        assert r == 0
        assert o == ""

        o, r = pcs(self.temp_cib.name, "resource config".split())
        ac(
            o,
            outdent(
                """\
            Clone: DGroup-clone
              Group: DGroup
                Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource clone DGroup".split())
        ac(o, "Error: cannot clone a group that has already been cloned\n")
        assert r == 1

    def testGroupPromotableCreation(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        assert r == 0
        assert o == ""

        o, r = pcs(self.temp_cib.name, "resource promotable DGroup1".split())
        ac(o, "Error: unable to find group or resource: DGroup1\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource promotable DGroup".split())
        assert r == 0
        assert o == ""

        o, r = pcs(self.temp_cib.name, "resource config".split())
        assert r == 0
        ac(
            o,
            outdent(
                """\
            Clone: DGroup-clone
              Meta Attributes: DGroup-clone-meta_attributes
                promotable=true
              Group: DGroup
                Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        o, r = pcs(self.temp_cib.name, "resource promotable DGroup".split())
        ac(o, "Error: cannot clone a group that has already been cloned\n")
        assert r == 1

    @skip_unless_crm_rule()
    def testGroupRemoveWithConstraints1(self):
        # Load nodes into cib so move will work
        self.temp_cib.seek(0)
        xml = etree.fromstring(self.temp_cib.read())
        nodes_el = xml.find(".//nodes")
        etree.SubElement(nodes_el, "node", {"id": "1", "uname": "rh7-1"})
        etree.SubElement(nodes_el, "node", {"id": "2", "uname": "rh7-2"})
        write_data_to_tmpfile(etree.tounicode(xml), self.temp_cib)

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        assert r == 0
        ac(o, "")

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DGroup".split(),
        )
        assert r == 0
        ac(o, "")

        o, r = pcs(self.temp_cib.name, "resource status".split())
        assert r == 0
        if is_pacemaker_21_without_20_compatibility():
            ac(
                o,
                outdent(
                    """\
                      * Resource Group: DGroup:
                        * D1\t(ocf:heartbeat:Dummy):\t Stopped
                        * D2\t(ocf:heartbeat:Dummy):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                o,
                """\
  * Resource Group: DGroup:
    * D1\t(ocf::heartbeat:Dummy):\tStopped
    * D2\t(ocf::heartbeat:Dummy):\tStopped
""",
            )
        else:
            ac(
                o,
                """\
 Resource Group: DGroup
     D1\t(ocf::heartbeat:Dummy):\tStopped
     D2\t(ocf::heartbeat:Dummy):\tStopped
""",
            )

        o, r = pcs(self.temp_cib.name, "resource move DGroup rh7-1".split())
        ac(
            o,
            (
                "Warning: A move constraint has been created and the resource "
                "'DGroup' may or may not move depending on other configuration"
                "\n"
            ),
        )
        assert r == 0

        o, r = pcs(self.temp_cib.name, ["constraint"])
        assert r == 0
        ac(
            o,
            "Location Constraints:\n  Resource: DGroup\n    Enabled on:\n      Node: rh7-1 (score:INFINITY) (role:Started)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n",
        )

        self.assert_pcs_success(
            "resource delete D1".split(), "Deleting Resource - D1\n"
        )

        self.assert_pcs_success(
            "resource delete D2".split(),
            outdent(
                """\
            Removing Constraint - cli-prefer-DGroup
            Deleting Resource (and group) - D2
            """
            ),
        )

        o, r = pcs(self.temp_cib.name, "resource status".split())
        assert r == 0
        ac(o, "NO resources configured\n")

    def testResourceCloneCreation(self):
        # resource "dummy1" is already in "temp_large_cib
        output, returnVal = pcs(
            self.temp_large_cib.name, "resource clone dummy1".split()
        )
        ac(output, "")
        assert returnVal == 0

    def testResourceCloneId(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy-clone ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource clone dummy".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy-clone-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: dummy-clone-1
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummy".split(), "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy clone".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy-clone-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: dummy-clone-1
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testResourcePromotableId(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy-clone ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "resource promotable dummy".split()
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy-clone-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: dummy-clone-1
              Meta Attributes: dummy-clone-1-meta_attributes
                promotable=true
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummy".split(), "Deleting Resource - dummy\n"
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy promotable".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: dummy-clone-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Clone: dummy-clone-1
              Meta Attributes: dummy-clone-1-meta_attributes
                promotable=true
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testResourceCloneUpdate(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone".split(),
        )
        assert r == 0
        ac(o, "")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D1-clone
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name, "resource update D1-clone foo=bar".split()
        )
        ac(o, "")
        self.assertEqual(0, r)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D1-clone
              Meta Attributes: D1-clone-meta_attributes
                foo=bar
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        self.assert_pcs_success("resource update D1-clone bar=baz".split())

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D1-clone
              Meta Attributes: D1-clone-meta_attributes
                bar=baz
                foo=bar
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

        o, r = pcs(self.temp_cib.name, "resource update D1-clone foo=".split())
        assert r == 0
        ac(o, "")

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: D1-clone
              Meta Attributes: D1-clone-meta_attributes
                bar=baz
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: D1-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testGroupRemoveWithConstraints2(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG".split(),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG".split(),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name, "constraint location AG prefers rh7-1".split()
        )
        ac(o, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource ungroup AG".split())
        ac(o, "Removing Constraint - location-AG-rh7-1-INFINITY\n")
        assert r == 0

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: A (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: A-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AA".split(),
        )
        assert r == 0
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AA".split(),
        )
        assert r == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "AA")

        o, r = pcs(
            self.temp_cib.name,
            "constraint location AA-master prefers rh7-1".split(),
        )
        assert r == 0

        self.assert_pcs_success(
            "resource delete A1".split(), "Deleting Resource - A1\n"
        )

        self.assert_pcs_success(
            "resource delete A2".split(),
            outdent(
                """\
            Removing Constraint - location-AA-master-rh7-1-INFINITY
            Deleting Resource (and group and M/S) - A2
            """
            ),
        )

    def testMasteredGroup(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG".split(),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG".split(),
        )
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops C ocf:heartbeat:Dummy --group AG".split(),
        )
        assert r == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "AG", master_id="AGMaster")

        self.assert_pcs_fail(
            "resource create --no-default-ops A ocf:heartbeat:Dummy".split(),
            "Error: 'A' already exists\n",
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops AG ocf:heartbeat:Dummy".split(),
            "Error: 'AG' already exists\n",
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops AGMaster ocf:heartbeat:Dummy".split(),
            "Error: 'AGMaster' already exists\n",
        )

        o, r = pcs(self.temp_cib.name, "resource ungroup AG".split())
        ac(o, "Error: Cannot remove all resources from a cloned group\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource delete B".split())
        assert r == 0
        o, r = pcs(self.temp_cib.name, "resource delete C".split())
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource ungroup AG".split())
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: AGMaster
              Meta Attributes:
                promotable=true
              Resource: A (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  monitor: A-monitor-interval-10s
                    interval=10s
                    timeout=20s
            """
            ),
        )

    def testClonedGroup(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DG".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG".split(),
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "resource clone DG".split())
        ac(output, "")
        self.assertEqual(0, returnVal)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Clone: DG-clone
              Group: DG
                Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy".split(),
            "Error: 'D1' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG ocf:heartbeat:Dummy".split(),
            "Error: 'DG' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG-clone ocf:heartbeat:Dummy".split(),
            "Error: 'DG-clone' already exists\n",
        )

    def testOPOption(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops B ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource update B ocf:heartbeat:Dummy op monitor interval=30s blah=blah".split(),
        )
        ac(
            o,
            "Error: blah is not a valid op option (use --force to override)\n",
        )
        assert r == 1

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops C ocf:heartbeat:Dummy".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(
            self.temp_cib.name,
            "resource op add C monitor interval=30s blah=blah".split(),
        )
        ac(
            o,
            "Error: blah is not a valid op option (use --force to override)\n",
        )
        assert r == 1

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource op add C monitor interval=60 role=role".split(),
        )
        ac(
            output,
            "Error: role must be: {} (use --force to override)\n".format(
                format_list_custom_last_separator(const.PCMK_ROLES, " or ")
            ),
        )
        assert returnVal == 1

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: C (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: C-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=30s monitor interval=31s role=master".split(),
        )
        ac(
            o,
            "Error: role must be: {} (use --force to override)\n".format(
                format_list_custom_last_separator(const.PCMK_ROLES, " or ")
            ),
        )
        assert r == 1

        o, r = pcs(
            self.temp_cib.name,
            "resource update B op monitor interval=30s monitor interval=31s role=Master".split(),
        )
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                f"""\
            Resource: B (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: B-monitor-interval-30s
                  interval=30s
                monitor: B-monitor-interval-31s
                  interval=31s
                  role={const.PCMK_ROLE_PROMOTED_PRIMARY}
            Resource: C (class=ocf provider=heartbeat type=Dummy)
              Operations:
                monitor: C-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )

        o, r = pcs(
            self.temp_cib.name, "resource update B op interval=5s".split()
        )
        ac(
            o,
            "Error: interval=5s does not appear to be a valid operation action\n",
        )
        assert r == 1

    def testCloneBadResources(self):
        self.setupClusterA()
        o, r = pcs(self.temp_cib.name, "resource clone ClusterIP4".split())
        ac(o, "Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource clone ClusterIP5".split())
        ac(o, "Error: ClusterIP5 is already a clone resource\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource promotable ClusterIP4".split())
        ac(o, "Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o, r = pcs(self.temp_cib.name, "resource promotable ClusterIP5".split())
        ac(o, "Error: ClusterIP5 is already a clone resource\n")
        assert r == 1

    def testGroupMSAndClone(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy promotable --group xxx clone".split(),
        )
        ac(
            o,
            "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )
        assert r == 1

        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops D4 ocf:heartbeat:Dummy promotable --group xxx".split(),
        )
        ac(
            o,
            "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )
        assert r == 1

    def testResourceCloneGroup(self):
        o, r = pcs(
            self.temp_cib.name,
            "resource create --no-default-ops dummy0 ocf:heartbeat:Dummy --group group".split(),
        )
        ac(o, "")
        assert r == 0

        o, r = pcs(self.temp_cib.name, "resource clone group".split())
        ac(o, "")
        assert r == 0

        self.assert_pcs_success(
            "resource delete dummy0".split(),
            "Deleting Resource (and group and clone) - dummy0\n",
        )

    def testResourceMissingValues(self):
        self.assert_pcs_success(
            "resource create --no-default-ops myip IPaddr2 --force".split(),
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from 'IPaddr2')
                Warning: required resource option 'ip' is missing
                """
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops myip2 IPaddr2 ip=3.3.3.3".split(),
            "Assumed agent name 'ocf:heartbeat:IPaddr2'"
            " (deduced from 'IPaddr2')\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops myfs Filesystem --force".split(),
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')
                Warning: required resource options 'device', 'directory', 'fstype' are missing
                """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops myfs2 Filesystem device=x"
                " directory=y --force"
            ).split(),
            outdent(
                """\
                Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')
                Warning: required resource option 'fstype' is missing
                """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops myfs3 Filesystem device=x"
                " directory=y fstype=z"
            ).split(),
            "Assumed agent name 'ocf:heartbeat:Filesystem'"
            " (deduced from 'Filesystem')\n",
        )

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: myip (class=ocf provider=heartbeat type=IPaddr2)
              Operations:
                monitor: myip-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: myip2 (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: myip2-instance_attributes
                ip=3.3.3.3
              Operations:
                monitor: myip2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: myfs (class=ocf provider=heartbeat type=Filesystem)
              Operations:
                monitor: myfs-monitor-interval-20s
                  interval=20s
                  timeout=40s
            Resource: myfs2 (class=ocf provider=heartbeat type=Filesystem)
              Attributes: myfs2-instance_attributes
                device=x
                directory=y
              Operations:
                monitor: myfs2-monitor-interval-20s
                  interval=20s
                  timeout=40s
            Resource: myfs3 (class=ocf provider=heartbeat type=Filesystem)
              Attributes: myfs3-instance_attributes
                device=x
                directory=y
                fstype=z
              Operations:
                monitor: myfs3-monitor-interval-20s
                  interval=20s
                  timeout=40s
            """
            ),
        )

    def testClonedMasteredGroup(self):
        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0

        output, retVal = pcs(
            self.temp_cib.name, "resource clone dummies".split()
        )
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource config dummies-clone".split(),
            outdent(
                """\
            Clone: dummies-clone
              Group: dummies
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy3-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        output, retVal = pcs(
            self.temp_cib.name, "resource unclone dummies-clone".split()
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(self.temp_cib.name, "resource status".split())
        if is_pacemaker_21_without_20_compatibility():
            ac(
                output,
                outdent(
                    """\
                      * Resource Group: dummies:
                        * dummy1\t(ocf:heartbeat:Dummy):\t Stopped
                        * dummy2\t(ocf:heartbeat:Dummy):\t Stopped
                        * dummy3\t(ocf:heartbeat:Dummy):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                output,
                outdent(
                    """\
                  * Resource Group: dummies:
                    * dummy1\t(ocf::heartbeat:Dummy):\tStopped
                    * dummy2\t(ocf::heartbeat:Dummy):\tStopped
                    * dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )
        else:
            ac(
                output,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::heartbeat:Dummy):\tStopped
                     dummy2\t(ocf::heartbeat:Dummy):\tStopped
                     dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )
        assert retVal == 0

        output, retVal = pcs(
            self.temp_cib.name, "resource clone dummies".split()
        )
        ac(output, "")
        assert retVal == 0

        self.assert_pcs_success(
            "resource config dummies-clone".split(),
            outdent(
                """\
            Clone: dummies-clone
              Group: dummies
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy3-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummies-clone".split(),
            outdent(
                """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and clone) - dummy3
            """
            ),
        )
        output, retVal = pcs(self.temp_cib.name, "resource status".split())
        ac(output, "NO resources configured\n")
        assert retVal == 0

        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(
            self.temp_cib.name,
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
        )
        ac(output, "")
        assert retVal == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummies")

        self.assert_pcs_success(
            "resource config dummies-master".split(),
            outdent(
                """\
            Clone: dummies-master
              Meta Attributes:
                promotable=true
              Group: dummies
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy3-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        output, retVal = pcs(
            self.temp_cib.name, "resource unclone dummies-master".split()
        )
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(self.temp_cib.name, "resource status".split())
        if is_pacemaker_21_without_20_compatibility():
            ac(
                output,
                outdent(
                    """\
                      * Resource Group: dummies:
                        * dummy1\t(ocf:heartbeat:Dummy):\t Stopped
                        * dummy2\t(ocf:heartbeat:Dummy):\t Stopped
                        * dummy3\t(ocf:heartbeat:Dummy):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                output,
                outdent(
                    """\
                  * Resource Group: dummies:
                    * dummy1\t(ocf::heartbeat:Dummy):\tStopped
                    * dummy2\t(ocf::heartbeat:Dummy):\tStopped
                    * dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )
        else:
            ac(
                output,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::heartbeat:Dummy):\tStopped
                     dummy2\t(ocf::heartbeat:Dummy):\tStopped
                     dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )
        assert retVal == 0

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummies")

        self.assert_pcs_success(
            "resource config dummies-master".split(),
            outdent(
                """\
            Clone: dummies-master
              Meta Attributes:
                promotable=true
              Group: dummies
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy3-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummies-master".split(),
            outdent(
                """\
            Removing group: dummies (and all resources within group)
            Stopping all resources in group: dummies...
            Deleting Resource - dummy1
            Deleting Resource - dummy2
            Deleting Resource (and group and M/S) - dummy3
            """
            ),
        )
        output, retVal = pcs(self.temp_cib.name, "resource status".split())
        ac(output, "NO resources configured\n")
        assert retVal == 0

    def test_relocate_stickiness(self):
        self.assert_pcs_success(
            "resource create D1 ocf:pacemaker:Dummy --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create DG1 ocf:pacemaker:Dummy --no-default-ops --group GR".split()
        )
        self.assert_pcs_success(
            "resource create DG2 ocf:pacemaker:Dummy --no-default-ops --group GR".split()
        )
        self.assert_pcs_success(
            "resource create DC ocf:pacemaker:Dummy --no-default-ops clone".split()
        )
        self.assert_pcs_success(
            "resource create DGC1 ocf:pacemaker:Dummy --no-default-ops --group GRC".split()
        )
        self.assert_pcs_success(
            "resource create DGC2 ocf:pacemaker:Dummy --no-default-ops --group GRC".split()
        )
        self.assert_pcs_success("resource clone GRC".split())

        status = outdent(
            """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: GRC-clone
              Group: GRC
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
        )

        cib_original, retVal = pcs(self.temp_cib.name, "cluster cib".split())
        self.assertEqual(0, retVal)

        resources = set(
            [
                "D1",
                "DG1",
                "DG2",
                "GR",
                "DC",
                "DC-clone",
                "DGC1",
                "DGC2",
                "GRC",
                "GRC-clone",
            ]
        )
        self.assert_pcs_success("resource config".split(), status)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        self.assert_pcs_success("resource config".split(), status)
        write_data_to_tmpfile(cib_out.toxml(), self.temp_cib)

        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attributes: D1-meta_attributes
                resource-stickiness=0
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Group: GR
              Meta Attributes: GR-meta_attributes
                resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DG1-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DG2-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: DC-clone
              Meta Attributes: DC-clone-meta_attributes
                resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DC-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: GRC-clone
              Meta Attributes: GRC-clone-meta_attributes
                resource-stickiness=0
              Group: GRC
                Meta Attributes: GRC-meta_attributes
                  resource-stickiness=0
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: DGC1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: DGC2-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        resources = set(["D1", "DG1", "DC", "DGC1"])
        write_data_to_tmpfile(cib_original, self.temp_cib)
        self.assert_pcs_success("resource config".split(), status)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, resources
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        self.assert_pcs_success("resource config".split(), status)
        write_data_to_tmpfile(cib_out.toxml(), self.temp_cib)
        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Meta Attributes: D1-meta_attributes
                resource-stickiness=0
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DG1-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DC-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: GRC-clone
              Group: GRC
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: DGC1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        resources = set(["GRC-clone", "GRC", "DGC1", "DGC2"])
        write_data_to_tmpfile(cib_original, self.temp_cib)
        self.assert_pcs_success("resource config".split(), status)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GRC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        self.assert_pcs_success("resource config".split(), status)
        write_data_to_tmpfile(cib_out.toxml(), self.temp_cib)
        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: GRC-clone
              Meta Attributes: GRC-clone-meta_attributes
                resource-stickiness=0
              Group: GRC
                Meta Attributes: GRC-meta_attributes
                  resource-stickiness=0
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: DGC1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: DGC2-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )

        resources = set(["GR", "DG1", "DG2", "DC-clone", "DC"])
        write_data_to_tmpfile(cib_original, self.temp_cib)
        self.assert_pcs_success("resource config".split(), status)
        cib_in = utils.parseString(cib_original)
        cib_out, updated_resources = resource.resource_relocate_set_stickiness(
            cib_in, ["GR", "DC-clone"]
        )
        self.assertFalse(cib_in is cib_out)
        self.assertEqual(resources, updated_resources)
        self.assert_pcs_success("resource config".split(), status)
        write_data_to_tmpfile(cib_out.toxml(), self.temp_cib)
        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Group: GR
              Meta Attributes: GR-meta_attributes
                resource-stickiness=0
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DG1-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s
                    timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DG2-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: DC-clone
              Meta Attributes: DC-clone-meta_attributes
                resource-stickiness=0
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Meta Attributes: DC-meta_attributes
                  resource-stickiness=0
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s
                    timeout=20s
            Clone: GRC-clone
              Group: GRC
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s
                      timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s
                      timeout=20s
            """
            ),
        )


class OperationDeleteRemoveMixin(
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
        self.temp_cib = get_tmp_file("tier1_resource_operation_delete")
        self.temp_large_cib = get_tmp_file(
            "tier1_resource_large_operation_delete"
        )
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        write_file_to_tmpfile(large_cib, self.temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.command = "to-be-overridden"

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    fixture_xml_1_monitor = """
        <resources>
            <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                <operations>
                    <op id="R-monitor-interval-10s" interval="10s"
                        name="monitor" timeout="20s"
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
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split(),
            self.fixture_xml_1_monitor,
        )

    def fixture_monitor_20(self):
        self.assert_effect(
            "resource op add R monitor interval=20s timeout=20s --force".split(),
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                            <op id="R-monitor-interval-20s" interval="20s"
                                name="monitor" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </resources>
            """,
        )

    def fixture_start(self):
        self.assert_effect(
            "resource op add R start timeout=20s".split(),
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-monitor-interval-10s" interval="10s"
                                name="monitor" timeout="20s"
                            />
                            <op id="R-monitor-interval-20s" interval="20s"
                                name="monitor" timeout="20s"
                            />
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </resources>
            """,
        )

    def test_remove_missing_op(self):
        assert self.command in {"delete", "remove"}
        self.fixture_resource()
        self.assert_pcs_fail(
            f"resource op {self.command} R-monitor-interval-30s".split(),
            "Error: unable to find operation id: R-monitor-interval-30s\n",
        )

    def test_keep_empty_operations(self):
        assert self.command in {"delete", "remove"}
        self.fixture_resource()
        self.assert_effect(
            f"resource op {self.command} R-monitor-interval-10s".split(),
            self.fixture_xml_empty_operations,
        )

    def test_remove_by_id_success(self):
        assert self.command in {"delete", "remove"}
        self.fixture_resource()
        self.fixture_monitor_20()
        self.assert_effect(
            f"resource op {self.command} R-monitor-interval-20s".split(),
            self.fixture_xml_1_monitor,
        )

    def test_remove_all_monitors(self):
        assert self.command in {"delete", "remove"}
        self.fixture_resource()
        self.fixture_monitor_20()
        self.fixture_start()
        self.assert_effect(
            f"resource op {self.command} R monitor".split(),
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pacemaker"
                        type="Dummy"
                    >
                        <operations>
                            <op id="R-start-interval-0s" interval="0s"
                                name="start" timeout="20s"
                            />
                        </operations>
                    </primitive>
                </resources>
            """,
        )


class OperationDelete(OperationDeleteRemoveMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.command = "delete"

    def test_usage(self):
        self.assert_pcs_fail(
            "resource op delete".split(),
            stdout_start="\nUsage: pcs resource op delete...",
        )


class OperationRemove(OperationDeleteRemoveMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.command = "remove"

    def test_usage(self):
        self.assert_pcs_fail(
            "resource op remove".split(),
            stdout_start="\nUsage: pcs resource op remove...",
        )


class Utilization(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = get_tmp_file("tier1_resource_utilization")
        self.temp_large_cib = get_tmp_file("tier1_resource_utilization_large")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        write_file_to_tmpfile(large_cib, self.temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    @staticmethod
    def fixture_xml_resource_no_utilization():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split(),
            self.fixture_xml_resource_no_utilization(),
        )

    def fixture_resource_utilization(self):
        self.fixture_resource()
        self.assert_effect(
            "resource utilization R test=100".split(),
            self.fixture_xml_resource_with_utilization(),
        )

    def testResourceUtilizationSet(self):
        # see also BundleMiscCommands
        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource utilization dummy test1=10".split(),
        )
        ac("", output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy1".split()
        )
        expected_out = """\
Resource Utilization:
 dummy1: \n"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy".split()
        )
        expected_out = """\
Resource Utilization:
 dummy: test1=10
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource utilization dummy test1=-10 test4=1234".split(),
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy".split()
        )
        expected_out = """\
Resource Utilization:
 dummy: test1=-10 test4=1234
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource utilization dummy1 test2=321 empty=".split(),
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy1".split()
        )
        expected_out = """\
Resource Utilization:
 dummy1: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization".split()
        )
        expected_out = """\
Resource Utilization:
 dummy: test1=-10 test4=1234
 dummy1: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

    def test_resource_utilization_set_invalid(self):
        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy test".split()
        )
        expected_out = """\
Error: missing value of 'test' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy =10".split()
        )
        expected_out = """\
Error: missing key in '=10' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name, "resource utilization dummy0".split()
        )
        expected_out = """\
Error: Unable to find a resource: dummy0
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource utilization dummy0 test=10".split(),
        )
        expected_out = """\
Error: Unable to find a resource: dummy0
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_large_cib.name,
            "resource utilization dummy1 test1=10 test=int".split(),
        )
        expected_out = """\
Error: Value of utilization attribute must be integer: 'test=int'
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

    def test_keep_empty_nvset(self):
        self.fixture_resource_utilization()
        self.assert_effect(
            "resource utilization R test=".split(),
            self.fixture_xml_resource_empty_utilization(),
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource utilization R test=".split(),
            self.fixture_xml_resource_no_utilization(),
        )


class MetaAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = get_tmp_file("tier1_resource_meta")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()

    @staticmethod
    def fixture_xml_resource_no_meta():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split(),
            self.fixture_xml_resource_no_meta(),
        )

    def fixture_resource_meta(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy meta a=b".split(),
            self.fixture_xml_resource_with_meta(),
        )

    def testMetaAttrs(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D0 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30 meta"
                " test5=test5a test6=test6a"
            ).split(),
            "Warning: invalid resource options: 'test', 'test2', allowed"
            " options are: 'fake', 'state', 'trace_file', 'trace_ra'\n",
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D1 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30"
            ).split(),
            "Warning: invalid resource options: 'test', 'test2', allowed"
            " options are: 'fake', 'state', 'trace_file', 'trace_ra'\n",
        )

        self.assert_pcs_success(
            (
                "resource update --force D0 test=testC test2=test2a op monitor "
                "interval=35 meta test7=test7a test6="
            ).split()
        )

        output, returnVal = pcs(
            self.temp_cib.name, "resource meta D1 d1meta=superd1meta".split()
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            self.temp_cib.name, "resource group add TestRG D1".split()
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(
            self.temp_cib.name,
            "resource meta TestRG testrgmeta=mymeta testrgmeta2=mymeta2".split(),
        )
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(self.temp_cib.name, "resource config".split())
        ac(
            output,
            outdent(
                """\
            Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Attributes: D0-instance_attributes
                test=testC
                test2=test2a
              Meta Attributes: D0-meta_attributes
                test5=test5a
                test7=test7a
              Operations:
                monitor: D0-monitor-interval-35
                  interval=35
            Group: TestRG
              Meta Attributes: TestRG-meta_attributes
                testrgmeta=mymeta
                testrgmeta2=mymeta2
              Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                Attributes: D1-instance_attributes
                  test=testA
                  test2=test2a
                Meta Attributes: D1-meta_attributes
                  d1meta=superd1meta
                Operations:
                  monitor: D1-monitor-interval-30
                    interval=30
            """
            ),
        )
        assert returnVal == 0

    def test_resource_meta_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource meta R a=".split(), self.fixture_xml_resource_empty_meta()
        )

    def test_resource_update_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource update R meta a=".split(),
            self.fixture_xml_resource_empty_meta(),
        )

    def test_resource_meta_dont_create_meta_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource meta R a=".split(), self.fixture_xml_resource_no_meta()
        )

    def test_resource_update_dont_create_meta_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R meta a=".split(),
            self.fixture_xml_resource_no_meta(),
        )


class UpdateInstanceAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    # The idempotency with remote-node is tested in
    # pcs_test/tier1/legacy/test_cluster_pcmk_remote.py in
    # NodeAddGuest.test_success_when_guest_node_matches_with_existing_guest

    # see also BundleMiscCommands

    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = get_tmp_file("tier1_resource_update_instance_attrs")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()

    @staticmethod
    def fixture_xml_resource_no_attrs():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
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
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </resources>
            """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split(),
            self.fixture_xml_resource_no_attrs(),
        )

    def fixture_resource_attrs(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pacemaker:Dummy fake=F".split(),
            self.fixture_xml_resource_with_attrs(),
        )

    def test_usage(self):
        self.assert_pcs_fail(
            "resource update".split(),
            stdout_start="\nUsage: pcs resource update...\n",
        )

    def testBadInstanceVariables(self):
        self.assert_pcs_fail(
            (
                "resource create --no-default-ops D0 ocf:heartbeat:Dummy"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ).split(),
            (
                "Error: invalid resource options: 'test', 'test2', 'test4',"
                " allowed options are: 'fake', 'state', 'trace_file', "
                "'trace_ra', use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D0 ocf:heartbeat:Dummy"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ).split(),
            "Warning: invalid resource options: 'test', 'test2', 'test4',"
            " allowed options are: 'fake', 'state', 'trace_file', "
            "'trace_ra'\n",
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA test2=testB test3=testD".split(),
            "Error: invalid resource option 'test3', allowed options"
            " are: 'fake', 'state', 'trace_file', 'trace_ra', use --force "
            "to override\n",
        )

        self.assert_pcs_success(
            "resource update D0 test=testB test2=testC test3=testD --force".split(),
            "Warning: invalid resource option 'test3',"
            " allowed options are: 'fake', 'state', 'trace_file', "
            "'trace_ra'\n",
        )

        self.assert_pcs_success(
            "resource config D0".split(),
            outdent(
                """\
            Resource: D0 (class=ocf provider=heartbeat type=Dummy)
              Attributes: D0-instance_attributes
                test=testB
                test2=testC
                test3=testD
                test4=test4A
              Meta Attributes: D0-meta_attributes
                test6=
                test7=test7a
              Operations:
                monitor: D0-monitor-interval-35
                  interval=35
            """
            ),
        )

    def test_nonexisting_agent(self):
        agent = "ocf:pacemaker:nonexistent"
        message = (
            f"Agent '{agent}' is not installed or does "
            "not provide valid metadata: Metadata query for "
            f"{agent} failed: Input/output error"
        )
        self.assert_pcs_success(
            f"resource create --force D0 {agent}".split(),
            f"Warning: {message}\n",
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA".split(),
            f"Error: {message}, use --force to override\n",
        )
        self.assert_pcs_success(
            "resource update --force D0 test=testA".split(),
            f"Warning: {message}\n",
        )

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
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split(),
            xml.format(ip="192.168.0.99"),
        )

        self.assert_effect(
            "resource update ClusterIP ip=192.168.0.100".split(),
            xml.format(ip="192.168.0.100"),
        )

    def test_keep_empty_nvset(self):
        self.fixture_resource_attrs()
        self.assert_effect(
            "resource update R fake=".split(),
            self.fixture_xml_resource_empty_attrs(),
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R fake=".split(),
            self.fixture_xml_resource_no_attrs(),
        )

    def test_agent_self_validation_failure(self):
        self.fixture_resource()
        self.assert_pcs_fail(
            [
                "resource",
                "update",
                "R",
                "fake=is_invalid=True",
                "--agent-validation",
            ],
            stdout_start="Error: Validation result from agent (use --force to override):",
        )


class ResourcesReferencedFromAcl(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_referenced_from_acl")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_remove_referenced_primitive_resource(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "acl role create read-dummy read id dummy".split()
        )
        self.assert_pcs_success(
            "resource delete dummy".split(), ["Deleting Resource - dummy"]
        )

    def test_remove_group_with_referenced_primitive_resource(self):
        self.assert_pcs_success(
            "resource create dummy1 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource group add dummy-group dummy1 dummy2".split()
        )
        self.assert_pcs_success(
            "acl role create read-dummy read id dummy2".split()
        )
        self.assert_pcs_success(
            "resource delete dummy-group".split(),
            [
                "Removing group: dummy-group (and all resources within group)",
                "Stopping all resources in group: dummy-group...",
                "Deleting Resource - dummy1",
                "Deleting Resource (and group) - dummy2",
            ],
        )

    def test_remove_referenced_group(self):
        self.assert_pcs_success(
            "resource create dummy1 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource group add dummy-group dummy1 dummy2".split()
        )
        self.assert_pcs_success(
            "acl role create acl-role-a read id dummy-group".split()
        )
        self.assert_pcs_success(
            "resource delete dummy-group".split(),
            [
                "Removing group: dummy-group (and all resources within group)",
                "Stopping all resources in group: dummy-group...",
                "Deleting Resource - dummy1",
                "Deleting Resource (and group) - dummy2",
            ],
        )


class CloneMasterUpdate(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_clone_master_update")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_no_op_allowed_in_clone_update(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy clone".split()
        )
        self.assert_pcs_success(
            "resource config dummy-clone".split(),
            outdent(
                """\
            Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  migrate_from: dummy-migrate_from-interval-0s
                    interval=0s
                    timeout=20s
                  migrate_to: dummy-migrate_to-interval-0s
                    interval=0s
                    timeout=20s
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
                  reload: dummy-reload-interval-0s
                    interval=0s
                    timeout=20s
                  start: dummy-start-interval-0s
                    interval=0s
                    timeout=20s
                  stop: dummy-stop-interval-0s
                    interval=0s
                    timeout=20s
            """
            ),
        )
        self.assert_pcs_fail(
            "resource update dummy-clone op stop timeout=300".split(),
            "Error: op settings must be changed on base resource, not the clone\n",
        )
        self.assert_pcs_fail(
            "resource update dummy-clone foo=bar op stop timeout=300".split(),
            "Error: op settings must be changed on base resource, not the clone\n",
        )
        self.assert_pcs_success(
            "resource config dummy-clone".split(),
            outdent(
                """\
            Clone: dummy-clone
              Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                Operations:
                  migrate_from: dummy-migrate_from-interval-0s
                    interval=0s
                    timeout=20s
                  migrate_to: dummy-migrate_to-interval-0s
                    interval=0s
                    timeout=20s
                  monitor: dummy-monitor-interval-10s
                    interval=10s
                    timeout=20s
                  reload: dummy-reload-interval-0s
                    interval=0s
                    timeout=20s
                  start: dummy-start-interval-0s
                    interval=0s
                    timeout=20s
                  stop: dummy-stop-interval-0s
                    interval=0s
                    timeout=20s
            """
            ),
        )

    def test_no_op_allowed_in_master_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("dummy"))
        show = outdent(
            f"""\
            Clone: dummy-master
              Meta Attributes:
                promotable=true
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy-monitor-interval-10
                    interval=10
                    timeout=20
                    role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy-monitor-interval-11
                    interval=11
                    timeout=20
                    role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  notify: dummy-notify-interval-0s
                    interval=0s
                    timeout=5
                  start: dummy-start-interval-0s
                    interval=0s
                    timeout=20
                  stop: dummy-stop-interval-0s
                    interval=0s
                    timeout=20
            """
        )
        self.assert_pcs_success("resource config dummy-master".split(), show)
        self.assert_pcs_fail(
            "resource update dummy-master op stop timeout=300".split(),
            "Error: op settings must be changed on base resource, not the clone\n",
        )
        self.assert_pcs_fail(
            "resource update dummy-master foo=bar op stop timeout=300".split(),
            "Error: op settings must be changed on base resource, not the clone\n",
        )
        self.assert_pcs_success("resource config dummy-master".split(), show)


class TransforMasterToClone(ResourceTest):
    def test_transform_master_without_meta_on_meta(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("dummy"))
        self.assert_effect(
            "resource meta dummy-master a=b".split(),
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
            </resources>""",
        )

    def test_transform_master_with_meta_on_meta(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(
            self.temp_cib.name,
            fixture_master_xml("dummy", meta_dict=dict(a="A", b="B", c="C")),
        )
        self.assert_effect(
            "resource meta dummy-master a=AA b= d=D promotable=".split(),
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
            </resources>""",
        )

    def test_transform_master_without_meta_on_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("dummy"))
        self.assert_effect(
            "resource update dummy-master meta a=b".split(),
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
            </resources>""",
        )

    def test_transform_master_with_meta_on_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(
            self.temp_cib.name,
            fixture_master_xml("dummy", meta_dict=dict(a="A", b="B", c="C")),
        )
        self.assert_effect(
            "resource update dummy-master meta a=AA b= d=D promotable=".split(),
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
            </resources>""",
        )


class ResourceRemoveWithTicket(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_remove_with_ticket")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_remove_ticket(self):
        self.assert_pcs_success("resource create A ocf:heartbeat:Dummy".split())
        self.assert_pcs_success(
            "constraint ticket add T master A loss-policy=fence".split()
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            [
                "Ticket Constraints:",
                "  Master A loss-policy=fence ticket=T",
            ],
        )
        self.assert_pcs_success(
            "resource delete A".split(),
            [
                "Removing Constraint - ticket-T-A-Master",
                "Deleting Resource - A",
            ],
        )


class BundleCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_bundle")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_primitive(self, name, bundle):
        self.assert_pcs_success(
            [
                "resource",
                "create",
                name,
                "ocf:heartbeat:Dummy",
                "bundle",
                bundle,
            ]
        )

    def fixture_bundle(self, name, container="docker"):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                name,
                "container",
                container,
                "image=pcs:test",
                "network",
                "control-port=1234",
            ]
        )


class BundleShow(BundleCommon):
    # TODO: add test for podman (requires pcmk features 3.2)
    empty_cib = rc("cib-empty.xml")

    def test_docker(self):
        self.fixture_bundle("B1", "docker")
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
            Bundle: B1
              Docker: image=pcs:test
              Network: control-port=1234
            """
            ),
        )

    def test_rkt(self):
        self.fixture_bundle("B1", "rkt")
        self.assert_pcs_success(
            "resource config B1".split(),
            outdent(
                """\
            Bundle: B1
              Rkt: image=pcs:test
              Network: control-port=1234
            """
            ),
        )


class BundleDelete(BundleCommon):
    def test_without_primitive(self):
        self.fixture_bundle("B")
        self.assert_effect(
            "resource delete B".split(), "<resources/>", "Deleting bundle 'B'\n"
        )

    def test_with_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "resource delete B".split(),
            "<resources/>",
            dedent(
                """\
                Deleting bundle 'B' and its inner resource 'R'
                Deleting Resource - R
            """
            ),
        )

    def test_remove_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "resource delete R".split(),
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


class BundleGroup(BundleCommon):
    def test_group_delete_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource group delete B R".split(),
            "Error: Group 'B' does not exist\n",
        )

    def test_group_remove_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource group remove B R".split(),
            "Error: Group 'B' does not exist\n",
        )

    def test_ungroup_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource ungroup B".split(), "Error: Group 'B' does not exist\n"
        )


class BundleClone(BundleCommon):
    def test_clone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource clone B".split(),
            "Error: unable to find group or resource: B\n",
        )

    def test_clone_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "resource clone R".split(), "Error: cannot clone bundle resource\n"
        )

    def test_unclone_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource unclone B".split(), "Error: could not find resource: B\n"
        )


class BundleMiscCommands(BundleCommon):
    def test_resource_enable_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success("resource enable B".split())

    def test_resource_disable_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success("resource disable B".split())

    def test_resource_manage_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success("resource manage B".split())

    def test_resource_unmanage_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_success("resource unmanage B".split())

    def test_op_add(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource op add B monitor interval=30".split(),
            "Error: Unable to find resource: B\n",
        )

    def test_op_remove(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource op remove B monitor interval=30".split(),
            "Error: Unable to find resource: B\n",
        )

    def test_update(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource update B meta aaa=bbb".split(),
            "Error: Unable to find resource: B\n",
        )

    def test_meta(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource meta B aaa=bbb".split(),
            "Error: unable to find a resource/clone/group: B\n",
        )

    def test_utilization(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail(
            "resource utilization B aaa=10".split(),
            "Error: Unable to find a resource: B\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_start_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B".split(),
            "Error: unable to debug-start a bundle\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_start_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-start B".split(),
            "Error: unable to debug-start a bundle, try the bundle's resource: R\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_stop_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B".split(),
            "Error: unable to debug-stop a bundle\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_stop_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-stop B".split(),
            "Error: unable to debug-stop a bundle, try the bundle's resource: R\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_monitor_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B".split(),
            "Error: unable to debug-monitor a bundle\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_monitor_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-monitor B".split(),
            "Error: unable to debug-monitor a bundle, try the bundle's resource: R\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_promote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B".split(),
            "Error: unable to debug-promote a bundle\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_promote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-promote B".split(),
            "Error: unable to debug-promote a bundle, try the bundle's resource: R\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_demote_bundle(self):
        self.fixture_bundle("B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B".split(),
            "Error: unable to debug-demote a bundle\n",
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_demote_with_resource(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail_regardless_of_force(
            "resource debug-demote B".split(),
            "Error: unable to debug-demote a bundle, try the bundle's resource: R\n",
        )


class ResourceUpdateRemoteAndGuestChecks(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_update_remote_guest")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_update_fail_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy".split())
        self.assert_pcs_fail(
            "resource update R meta remote-node=HOST".split(),
            (
                "Error: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest', use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_update_warn_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy".split())
        self.assert_pcs_success(
            "resource update R meta remote-node=HOST --force".split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )

    def test_update_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )
        self.assert_pcs_fail(
            "resource update R meta remote-node=".split(),
            (
                "Error: this command is not sufficient for removing a guest "
                "node, use 'pcs cluster node remove-guest', use --force "
                "to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_update_warn_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )
        self.assert_pcs_success(
            "resource update R meta remote-node= --force".split(),
            "Warning: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest'\n",
        )

    def test_meta_fail_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy".split())
        self.assert_pcs_fail(
            "resource meta R remote-node=HOST".split(),
            (
                "Error: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest', use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_meta_warn_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:heartbeat:Dummy".split())
        self.assert_pcs_success(
            "resource meta R remote-node=HOST --force".split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )

    def test_meta_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )
        self.assert_pcs_fail(
            "resource meta R remote-node=".split(),
            (
                "Error: this command is not sufficient for removing a guest "
                "node, use 'pcs cluster node remove-guest', use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_meta_warn_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            "Warning: this command is not sufficient for creating a guest node,"
            " use 'pcs cluster node add-guest'\n",
        )
        self.assert_pcs_success(
            "resource meta R remote-node= --force".split(),
            "Warning: this command is not sufficient for removing a guest node,"
            " use 'pcs cluster node remove-guest'\n",
        )


class ResourceUpdateUniqueAttrChecks(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_update_unique_attr")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")

    def tearDown(self):
        self.temp_cib.close()

    def test_unique_err(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:Dummy".split()
        )
        self.assert_pcs_fail(
            "resource update R2 state=1".split(),
            "Error: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1', "
            "use --force to override\n",
        )

    def test_unique_setting_same_value(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:Dummy --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n",
        )
        res_config = outdent(
            """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=1
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
        )
        self.assert_pcs_success("resource config".split(), res_config)
        # make sure that it doesn't check against resource itself
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n",
        )
        self.assert_pcs_success("resource config".split(), res_config)
        res_config = outdent(
            """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=2
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
        )
        self.assert_pcs_success("resource update R2 state=2".split())
        self.assert_pcs_success("resource config".split(), res_config)
        self.assert_pcs_success("resource update R2 state=2".split())
        self.assert_pcs_success("resource config".split(), res_config)

    def test_unique_warn(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pacemaker:Dummy state=1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pacemaker:Dummy --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R3 ocf:pacemaker:Dummy --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1'\n",
        )
        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=1
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R3 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: R3-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )
        self.assert_pcs_success(
            "resource update R3 state=1 --force".split(),
            "Warning: Value '1' of option 'state' is not unique across "
            "'ocf:pacemaker:Dummy' resources. Following resources are "
            "configured with the same value of the instance attribute: 'R1', "
            "'R2'\n",
        )
        self.assert_pcs_success(
            "resource config".split(),
            outdent(
                """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=1
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s
                  timeout=20s
            Resource: R3 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R3-instance_attributes
                state=1
              Operations:
                monitor: R3-monitor-interval-10s
                  interval=10s
                  timeout=20s
            """
            ),
        )
