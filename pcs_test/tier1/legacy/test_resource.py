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
from pcs_test.tier1.legacy.common import FIXTURE_UTILIZATION_WARNING
from pcs_test.tools.assertions import (
    AssertPcsMixin,
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
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import XmlManipulation

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)

LOCATION_NODE_VALIDATION_SKIP_WARNING = (
    f"Warning: {LOCATION_NODE_VALIDATION_SKIP_MSG}\n"
)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
DEPRECATED_DASH_DASH_GROUP = (
    "Deprecation Warning: Using '--group' is deprecated and will be replaced "
    "with 'group' in a future release. Specify --future to switch to the future "
    "behavior.\n"
)

empty_cib = rc("cib-empty.xml")
large_cib = rc("cib-large.xml")


class ResourceDescribe(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    @staticmethod
    def fixture_description(advanced=False):
        advanced_params = """\
              trace_ra (advanced use only)
                Description: Set to 1 to turn on resource agent tracing (expect large output) The trace output will be saved to trace_file, if set, or by default to $HA_VARRUN/ra_trace/<type>/<id>.<action>.<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/db.start.2012-11-27.08:37:08
                Type: integer
                Default: 0
              trace_file (advanced use only)
                Description: Path to a file to store resource agent tracing log
                Type: string
            """
        return dedent(
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
                interval=0s timeout=10s
              stop:
                interval=0s timeout=10s
              monitor:
                interval=10s start-delay=0s timeout=10s
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
            stdout_full=self.fixture_description(),
            stderr_full=(
                "Assumed agent name 'ocf:pacemaker:HealthCPU' (deduced from "
                "'healthcpu')\n"
            ),
        )

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "resource describe ocf:pacemaker:nonexistent".split(),
            (
                "Error: Agent 'ocf:pacemaker:nonexistent' is not installed or does "
                "not provide valid metadata: Metadata query for "
                "ocf:pacemaker:nonexistent failed: Input/output error\n"
                + ERRORS_HAVE_OCCURRED
            ),
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
            stderr_start="\nUsage: pcs resource describe...\n",
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "resource describe agent1 agent2".split(),
            stderr_start="\nUsage: pcs resource describe...\n",
        )

    def test_pcsd_interface(self):
        stdout, stderr, returncode = self.pcs_runner.run(
            "resource get_resource_agent_info ocf:pacemaker:Dummy".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        self.assertEqual(
            json.loads(stdout),
            {
                "name": "ocf:pacemaker:Dummy",
                "standard": "ocf",
                "provider": "pacemaker",
                "type": "Dummy",
                "shortdesc": "Example stateless resource agent",
                "longdesc": "This is a dummy OCF resource agent. It does absolutely nothing except keep track\nof whether it is running or not, and can be configured so that actions fail or\ntake a long time. Its purpose is primarily for testing, and to serve as a\ntemplate for resource agent writers.",
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
                        "unique_group": "state",
                        "reloadable": False,
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
                        "unique_group": None,
                        "reloadable": True,
                    },
                    {
                        "name": "fake",
                        "shortdesc": "Fake attribute that can be changed to cause an agent reload",
                        "longdesc": "Fake attribute that can be changed to cause an agent reload",
                        "type": "string",
                        "default": "dummy",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": True,
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
                        "unique_group": None,
                        "reloadable": True,
                    },
                    {
                        "name": "fail_start_on",
                        "shortdesc": "Report bogus start failure on specified host",
                        "longdesc": "Start, migrate_from, and reload-agent actions will return failure if running on\nthe host specified here, but the resource will run successfully anyway (future\nmonitor calls will find it running). This can be used to test on-fail=ignore.",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": True,
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
                        "unique_group": None,
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
                        "name": "reload-agent",
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
                        "name": "reload-agent",
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
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource")
        self.temp_large_cib = get_tmp_file("tier1_resource_large")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        write_file_to_tmpfile(large_cib, self.temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setup_cluster_a(self):
        write_file_to_tmpfile(CIB_FIXTURE.cache_path, self.temp_cib)

    def test_case_insensitive(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D0 dummy".split(),
            (
                "Error: Multiple agents match 'dummy', please specify full name: "
                "'ocf:heartbeat:Dummy' or 'ocf:pacemaker:Dummy'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D1 systemhealth".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pacemaker:SystemHealth'"
                " (deduced from 'systemhealth')\n"
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 SYSTEMHEALTH".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pacemaker:SystemHealth'"
                " (deduced from 'SYSTEMHEALTH')\n"
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D3 ipaddr2 ip=1.1.1.1".split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:IPaddr2'"
                " (deduced from 'ipaddr2')\n"
            ),
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops D4 ipaddr3".split(),
            (
                "Error: Unable to find agent 'ipaddr3', try specifying its full name\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_empty(self):
        self.assert_pcs_success(["resource"], "NO resources configured\n")

    def test_add_resources_large_cib(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success(
            "resource create dummy0 ocf:heartbeat:Dummy --no-default-ops".split(),
        )
        self.assert_pcs_success(
            "resource config dummy0".split(),
            dedent(
                """\
                Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy0-monitor-interval-10s
                      interval=10s timeout=20s
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
            stderr_full="Deleting Resource - ClusterIP\n",
        )

        self.assert_pcs_fail(
            "resource config ClusterIP".split(),
            "Warning: Unable to find resource 'ClusterIP'\nError: No resource found\n",
        )

        self.assert_pcs_success(
            "resource status".split(),
            "NO resources configured\n",
        )

        self.assert_pcs_fail(
            f"resource {command} ClusterIP".split(),
            "Error: Resource 'ClusterIP' does not exist.\n",
        )

    def test_delete_resources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource delete".split(),
            stderr_start="\nUsage: pcs resource delete...",
        )

        self._test_delete_remove_resources("delete")

    def test_remove_resources(self):
        # Verify deleting resources works
        # Additional tests are in class BundleDeleteTest
        self.assert_pcs_fail(
            "resource remove".split(),
            stderr_start="\nUsage: pcs resource remove...",
        )

        self._test_delete_remove_resources("remove")

    def test_resource_show(self):
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            dedent(
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

    def test_add_operation(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )

        self.assert_pcs_fail(
            "resource op add".split(),
            stderr_start="\nUsage: pcs resource op add...",
        )
        self.assert_pcs_fail(
            "resource op remove".split(),
            stderr_start="\nUsage: pcs resource op remove...",
        )

        self.assert_pcs_fail(
            "resource op add ClusterIP monitor interval=31s".split(),
            (
                "Error: operation monitor already specified for ClusterIP, "
                "use --force to override:\n"
                "monitor interval=30s (ClusterIP-monitor-interval-30s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource op add ClusterIP monitor interval=31s --force".split(),
        )

        self.assert_pcs_fail(
            "resource op add ClusterIP monitor interval=31s".split(),
            (
                "Error: operation monitor with interval 31s already specified "
                "for ClusterIP:\n"
                "monitor interval=31s (ClusterIP-monitor-interval-31s)\n"
            ),
        )

        self.assert_pcs_fail(
            "resource op add ClusterIP monitor interval=31".split(),
            (
                "Error: operation monitor with interval 31s already specified "
                "for ClusterIP:\n"
                "monitor interval=31s (ClusterIP-monitor-interval-31s)\n"
            ),
        )

        self.assert_pcs_fail(
            "resource op add ClusterIP moni=tor interval=60".split(),
            "Error: moni=tor does not appear to be a valid operation action\n",
        )

        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            dedent(
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

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1 enabled=0".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest".split(),
            dedent(
                """\
                Resource: OPTest (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=1
                    monitor: OPTest-monitor-interval-25s
                      interval=25s enabled=0 OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest2 ocf:heartbeat:Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=2 op start timeout=30s".split(),
        )

        self.assert_pcs_fail(
            "resource op add OPTest2 start timeout=1800s".split(),
            (
                "Error: operation start with interval 0s already specified for OPTest2:\n"
                "start interval=0s timeout=30s (OPTest2-start-interval-0s)\n"
            ),
        )

        self.assert_pcs_fail(
            "resource op add OPTest2 start interval=100".split(),
            (
                "Error: operation start already specified for OPTest2, use --force to override:\n"
                "start interval=0s timeout=30s (OPTest2-start-interval-0s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource op add OPTest2 monitor timeout=1800s".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest2".split(),
            dedent(
                """\
                Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest2-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=1
                    monitor: OPTest2-monitor-interval-25s
                      interval=25s OCF_CHECK_LEVEL=2
                    start: OPTest2-start-interval-0s
                      interval=0s timeout=30s
                    monitor: OPTest2-monitor-interval-60s
                      interval=60s timeout=1800s
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest3 ocf:heartbeat:Dummy op monitor OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest3".split(),
            dedent(
                """\
                Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest3-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest4 ocf:heartbeat:Dummy op monitor interval=30s".split(),
        )

        self.assert_pcs_success(
            "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest4".split(),
            dedent(
                """\
                Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest4-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest5 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest5".split(),
            dedent(
                """\
                Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest5-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest6 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest6".split(),
            dedent(
                """\
                Resource: OPTest6 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest6-monitor-interval-10s
                      interval=10s timeout=20s
                    monitor: OPTest6-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest7 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource update OPTest7 op monitor interval=60s OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_fail(
            "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1".split(),
            (
                "Error: operation monitor already specified for OPTest7, use --force to override:\n"
                "monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1 --force".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest7".split(),
            dedent(
                """\
                Resource: OPTest7 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OPTest7-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                    monitor: OPTest7-monitor-interval-61s
                      interval=61s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_fail(
            "resource op add OPTest7 monitor interval=60s OCF_CHECK_LEVEL=1".split(),
            (
                "Error: operation monitor with interval 60s already specified for OPTest7:\n"
                "monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OCFTest1 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_fail(
            "resource op add OCFTest1 monitor interval=31s".split(),
            (
                "Error: operation monitor already specified for OCFTest1, use --force to override:\n"
                "monitor interval=10s timeout=20s (OCFTest1-monitor-interval-10s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource op add OCFTest1 monitor interval=31s --force".split(),
        )

        self.assert_pcs_success(
            "resource op add OCFTest1 monitor interval=30s OCF_CHECK_LEVEL=15".split(),
        )

        self.assert_pcs_success(
            "resource config OCFTest1".split(),
            dedent(
                """\
                Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OCFTest1-monitor-interval-10s
                      interval=10s timeout=20s
                    monitor: OCFTest1-monitor-interval-31s
                      interval=31s
                    monitor: OCFTest1-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=15
                """
            ),
        )

        self.assert_pcs_success(
            "resource update OCFTest1 op monitor interval=61s OCF_CHECK_LEVEL=5".split(),
        )

        self.assert_pcs_success(
            "resource config OCFTest1".split(),
            dedent(
                """\
                Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OCFTest1-monitor-interval-61s
                      interval=61s OCF_CHECK_LEVEL=5
                    monitor: OCFTest1-monitor-interval-31s
                      interval=31s
                    monitor: OCFTest1-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=15
                """
            ),
        )

        self.assert_pcs_success(
            "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4".split(),
        )

        self.assert_pcs_success(
            "resource config OCFTest1".split(),
            dedent(
                """\
                Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OCFTest1-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=4
                    monitor: OCFTest1-monitor-interval-31s
                      interval=31s
                    monitor: OCFTest1-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=15
                """
            ),
        )

        self.assert_pcs_success(
            "resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4 interval=35s".split(),
        )

        self.assert_pcs_success(
            "resource config OCFTest1".split(),
            dedent(
                """\
                Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: OCFTest1-monitor-interval-35s
                      interval=35s OCF_CHECK_LEVEL=4
                    monitor: OCFTest1-monitor-interval-31s
                      interval=31s
                    monitor: OCFTest1-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=15
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops state ocf:pacemaker:Stateful".split(),
            stderr_full=(
                "Warning: changing a monitor operation interval from 10s to 11 to"
                " make the operation unique\n"
            ),
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10".split(),
            (
                "Error: operation monitor with interval 10s already specified for state:\n"
                "monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)\n"
            ),
        )

        self.assert_pcs_fail(
            "resource op add state monitor interval=10 role=Started".split(),
            (
                "Error: operation monitor with interval 10s already specified for state:\n"
                "monitor interval=10s role=Master timeout=20s (state-monitor-interval-10s)\n"
            ),
        )

        self.assert_pcs_success(
            "resource op add state monitor interval=15 role=Master --force".split()
        )

        self.assert_pcs_success(
            "resource config state".split(),
            dedent(
                f"""\
                Resource: state (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: state-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: state-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    monitor: state-monitor-interval-15
                      interval=15 role={const.PCMK_ROLE_PROMOTED_PRIMARY}
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
            stderr_full="Cluster CIB has been upgraded to latest version\n",
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_update_add_operation_onfail_demote_upgrade_cib(self):
        write_file_to_tmpfile(rc("cib-empty-3.3.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pacemaker:Dummy".split()
        )
        self.assert_pcs_success(
            "resource update R op start on-fail=demote".split(),
            stderr_full="Cluster CIB has been upgraded to latest version\n",
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
            (
                "Error: unable to find operation id: "
                "ClusterIP-monitor-interval-32s-xxxxx\n"
            ),
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
            dedent(
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
            dedent(
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
            dedent(
                """\
                Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.99
                  Operations:
                    stop: ClusterIP-stop-interval-0s
                      interval=0s timeout=34s
                    start: ClusterIP-start-interval-0s
                      interval=0s timeout=33s
                """
            ),
        )

    def test_delete_operation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op delete".split(),
            stderr_start="\nUsage: pcs resource op delete...",
        )

        self._test_delete_remove_operation("delete")

    def test_remove_operation(self):
        # see also BundleMiscCommands
        self.assert_pcs_fail(
            "resource op remove".split(),
            stderr_start="\nUsage: pcs resource op remove...",
        )

        self._test_delete_remove_operation("remove")

    def test_update_operation(self):
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2"
                " cidr_netmask=32 ip=192.168.0.99 op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            dedent(
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
            dedent(
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

        show_clusterip = dedent(
            """\
            Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
              Attributes: ClusterIP-instance_attributes
                cidr_netmask=32
                ip=192.168.0.99
              Operations:
                monitor: ClusterIP-monitor-interval-33s
                  interval=33s
                start: ClusterIP-start-interval-30s
                  interval=30s timeout=180s
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
            (
                "Error: invalid operation id 'ab#cd', '#' is not a valid character"
                " for a operation id\n"
            ),
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(), show_clusterip
        )

        # test existing id
        self.assert_pcs_fail_regardless_of_force(
            "resource update ClusterIP op monitor interval=30 id=ClusterIP".split(),
            (
                "Error: id 'ClusterIP' is already in use, please specify another"
                " one\n"
            ),
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
            dedent(
                """\
                Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: ClusterIP-instance_attributes
                    cidr_netmask=32
                    ip=192.168.0.99
                  Operations:
                    monitor: abcd
                      interval=60s
                    start: ClusterIP-start-interval-30s
                      interval=30s timeout=180s
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
            dedent(
                """\
                Resource: A (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    migrate_from: A-migrate_from-interval-0s
                      interval=0s timeout=20s
                    migrate_to: A-migrate_to-interval-0s
                      interval=0s timeout=20s
                    monitor: A-monitor-interval-10
                      interval=10
                    monitor: A-monitor-interval-20
                      interval=20
                    reload: A-reload-interval-0s
                      interval=0s timeout=20s
                    start: A-start-interval-0s
                      interval=0s timeout=20s
                    stop: A-stop-interval-0s
                      interval=0s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource update A op monitor interval=20".split(),
            (
                "Error: operation monitor with interval 20s already specified for A:\n"
                "monitor interval=20 (A-monitor-interval-20)\n"
            ),
        )

        self.assert_pcs_success(
            "resource update A op monitor interval=11".split(),
        )

        self.assert_pcs_success(
            "resource config A".split(),
            dedent(
                """\
                Resource: A (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    migrate_from: A-migrate_from-interval-0s
                      interval=0s timeout=20s
                    migrate_to: A-migrate_to-interval-0s
                      interval=0s timeout=20s
                    monitor: A-monitor-interval-11
                      interval=11
                    monitor: A-monitor-interval-20
                      interval=20
                    reload: A-reload-interval-0s
                      interval=0s timeout=20s
                    start: A-start-interval-0s
                      interval=0s timeout=20s
                    stop: A-stop-interval-0s
                      interval=0s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource create B ocf:heartbeat:Dummy --no-default-ops".split(),
        )

        self.assert_pcs_success(
            "resource op remove B-monitor-interval-10s".split()
        )

        self.assert_pcs_success(
            "resource config B".split(),
            "Resource: B (class=ocf provider=heartbeat type=Dummy)\n",
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=60s".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-60s
                      interval=60s
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=30".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-30
                      interval=30
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op start interval=0 timeout=10".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-30
                      interval=30
                    start: B-start-interval-0
                      interval=0 timeout=10
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op start interval=0 timeout=20".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-30
                      interval=30
                    start: B-start-interval-0
                      interval=0 timeout=20
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=33".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-33
                      interval=33
                    start: B-start-interval-0
                      interval=0 timeout=20
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=100 role=Master".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                f"""\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-33
                      interval=33
                    start: B-start-interval-0
                      interval=0 timeout=20
                    monitor: B-monitor-interval-100
                      interval=100 role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success(
            "resource update B op start interval=0 timeout=22".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                f"""\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-33
                      interval=33
                    start: B-start-interval-0
                      interval=0 timeout=22
                    monitor: B-monitor-interval-100
                      interval=100 role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                """
            ),
        )

    def test_group_delete_test(self):
        self.assert_pcs_success(
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy --group AGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        stdout, stderr, returncode = self.pcs_runner.run(
            "resource status".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        if is_pacemaker_21_without_20_compatibility():
            self.assertEqual(
                stdout,
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
                stdout,
                """\
  * Resource Group: AGroup:
    * A1\t(ocf::heartbeat:Dummy):\tStopped
    * A2\t(ocf::heartbeat:Dummy):\tStopped
    * A3\t(ocf::heartbeat:Dummy):\tStopped
""",
            )
        else:
            self.assertEqual(
                stdout,
                """\
 Resource Group: AGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped
     A2\t(ocf::heartbeat:Dummy):\tStopped
     A3\t(ocf::heartbeat:Dummy):\tStopped
""",
            )

        self.assert_pcs_success(
            "resource delete AGroup".split(),
            stderr_full=dedent(
                """\
                Removing group: AGroup (and all resources within group)
                Stopping all resources in group: AGroup...
                Deleting Resource - A1
                Deleting Resource - A2
                Deleting Resource (and group) - A3
                """
            ),
        )

        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

    @skip_unless_crm_rule()
    def test_group_ungroup(self):
        self.setup_cluster_a()
        self.assert_pcs_success(
            "constraint location ClusterIP3 prefers rh7-1".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "resource delete ClusterIP2".split(),
            stderr_full="Deleting Resource - ClusterIP2\n",
        )

        self.assert_pcs_success(
            "resource delete ClusterIP3".split(),
            stderr_full=dedent(
                """\
                Removing Constraint - location-ClusterIP3-rh7-1-INFINITY
                Deleting Resource (and group) - ClusterIP3
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A3 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A4 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A5 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource group add AGroup A1 A2 A3 A4 A5".split(),
        )

        self.assert_pcs_success(
            "resource config AGroup".split(),
            dedent(
                """\
                Group: AGroup
                  Resource: A1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A2 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A2-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A3 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A3-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A4 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A4-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A5 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A5-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_group_large_resource_remove(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success(
            "resource group add dummies dummylarge".split(),
        )
        self.assert_pcs_success(
            "resource delete dummies".split(),
            stderr_full=dedent(
                """\
                Removing group: dummies (and all resources within group)
                Stopping all resources in group: dummies...
                Deleting Resource (and group) - dummylarge
                """
            ),
        )

    def test_group_order(self):
        # This was cosidered for removing during 'resource group add' command
        # and tests overhaul. However, this is the only test where "resource
        # group list" is called. Due to that this test was not deleted.
        self.assert_pcs_success(
            "resource create --no-default-ops A ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops E ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops F ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops G ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops H ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops I ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops J ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops K ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "resource group add RGA A B C E D K J I".split()
        )

        stdout, stderr, returncode = self.pcs_runner.run(["resource"])
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        if is_pacemaker_21_without_20_compatibility():
            self.assertEqual(
                stdout,
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
                stdout,
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
            self.assertEqual(
                stdout,
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

        self.assert_pcs_success(
            "resource group list".split(), "RGA: A B C E D K J I\n"
        )

    @skip_unless_crm_rule()
    def test_cluster_config(self):
        self.setup_cluster_a()

        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf"),
        }
        self.assert_pcs_success(
            ["config"],
            dedent(
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
                """
            ),
        )

    def test_clone_remove(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone".split(),
        )

        self.assert_pcs_success(
            "constraint location D1-clone prefers rh7-1".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "constraint location D1 prefers rh7-1 --force".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete D1-clone".split(),
            stderr_full=dedent(
                """\
                Removing Constraint - location-D1-clone-rh7-1-INFINITY
                Removing Constraint - location-D1-rh7-1-INFINITY
                Deleting Resource - D1
                """
            ),
        )

        self.assert_pcs_success(
            "resource config".split(),
        )

        self.assert_pcs_success(
            "resource create d99 ocf:heartbeat:Dummy clone globally-unique=true".split(),
            stderr_full=(
                "Deprecation Warning: Configuring clone meta attributes without "
                "specifying the 'meta' keyword after the 'clone' keyword is "
                "deprecated and will be removed in a future release. Specify "
                "--future to switch to the future behavior.\n"
            ),
        )

        self.assert_pcs_success(
            "resource delete d99".split(),
            stderr_full="Deleting Resource - d99\n",
        )

    def test_clone_remove_large(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success("resource clone dummylarge".split())
        self.assert_pcs_success(
            "resource delete dummylarge".split(),
            stderr_full="Deleting Resource - dummylarge\n",
        )

    def test_clone_group_large_resource_remove(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success(
            "resource group add dummies dummylarge".split(),
        )
        self.assert_pcs_success("resource clone dummies".split())
        self.assert_pcs_success(
            "resource delete dummies".split(),
            stderr_full=dedent(
                """\
                Removing group: dummies (and all resources within group)
                Stopping all resources in group: dummies...
                Deleting Resource (and group and clone) - dummylarge
                """
            ),
        )

    @skip_unless_crm_rule()
    def test_master_slave_remove(self):
        self.setup_cluster_a()
        self.assert_pcs_success(
            "constraint location ClusterIP5 prefers rh7-1 --force".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "constraint location Master prefers rh7-2".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "resource delete Master".split(),
            stderr_full=dedent(
                """\
                Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
                Removing Constraint - location-Master-rh7-2-INFINITY
                Deleting Resource - ClusterIP5
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops ClusterIP5 ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_success(
            "constraint location ClusterIP5 prefers rh7-1".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "constraint location ClusterIP5 prefers rh7-2".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "resource delete ClusterIP5".split(),
            stderr_full=dedent(
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

        self.assert_pcs_success(
            "constraint location ClusterIP5 prefers rh7-1".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "constraint location ClusterIP5 prefers rh7-2".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.pcs_runner.mock_settings = {
            "corosync_conf_file": rc("corosync.conf"),
        }
        self.assert_pcs_success(
            ["config"],
            dedent(
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

                Location Constraints:
                  resource 'ClusterIP5' prefers node 'rh7-1' with score INFINITY (id: location-ClusterIP5-rh7-1-INFINITY)
                  resource 'ClusterIP5' prefers node 'rh7-2' with score INFINITY (id: location-ClusterIP5-rh7-2-INFINITY)
            """
            ),
        )
        del self.pcs_runner.mock_settings["corosync_conf_file"]

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_large_cib, "dummylarge")

        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success(
            "resource delete dummylarge".split(),
            stderr_full="Deleting Resource - dummylarge\n",
        )

    def test_master_slave_group_large_resource_remove(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_success(
            "resource group add dummies dummylarge".split(),
        )
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_large_cib, "dummies")
        self.assert_pcs_success(
            "resource delete dummies".split(),
            stderr_full=dedent(
                """\
                Removing group: dummies (and all resources within group)
                Stopping all resources in group: dummies...
                Deleting Resource (and group and M/S) - dummylarge
                """
            ),
        )

    def test_ms_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success("resource group add Group D0 D1".split())

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "Group", master_id="GroupMaster")

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: GroupMaster
                  Meta Attributes:
                    promotable=true
                  Group: Group
                    Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D0-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )
        self.assert_pcs_success(
            "resource delete D0".split(),
            stderr_full="Deleting Resource - D0\n",
        )
        self.assert_pcs_success(
            "resource delete D1".split(),
            stderr_full="Deleting Resource (and group and M/S) - D1\n",
        )

    def test_unclone(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success("resource group add gr dummy1".split())

        self.assert_pcs_fail(
            "resource unclone gr".split(),
            "Error: 'gr' is not a clone resource\n",
        )

        # unclone with a clone itself specified
        self.assert_pcs_success("resource group add gr dummy2".split())
        self.assert_pcs_success("resource clone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: gr-clone
                  Group: gr
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr-clone".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Group: gr
                  Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        # unclone with a cloned group specified
        self.assert_pcs_success("resource clone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: gr-clone
                  Group: gr
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Group: gr
                  Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        # unclone with a cloned grouped resource specified
        self.assert_pcs_success("resource clone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: gr-clone
                  Group: gr
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy1".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: gr-clone
                  Group: gr
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy2".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

    def test_unclone_master(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pacemaker:Stateful".split(),
            stderr_full=(
                "Warning: changing a monitor operation interval from 10s to 11 "
                "to make the operation unique\n"
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pacemaker:Stateful".split(),
            stderr_full=(
                "Warning: changing a monitor operation interval from 10s to 11 "
                "to make the operation unique\n"
            ),
        )

        # try to unclone a non-cloned resource
        self.assert_pcs_fail(
            "resource unclone dummy1".split(),
            "Error: 'dummy1' is not a clone resource\n",
        )

        self.assert_pcs_success("resource group add gr dummy1".split())

        self.assert_pcs_fail(
            "resource unclone gr".split(),
            "Error: 'gr' is not a clone resource\n",
        )

        # unclone with a cloned primitive specified
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummy2")
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Group: gr
                  Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: dummy2-master
                  Meta Attributes:
                    promotable=true
                  Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy2".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Group: gr
                  Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        # unclone with a clone itself specified
        self.assert_pcs_success("resource group add gr dummy2".split())
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr-master".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Group: gr
                  Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
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
            dedent(
                f"""\
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Group: gr
                  Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11
                        interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        # unclone with a cloned grouped resource specified
        self.assert_pcs_success("resource ungroup gr dummy2".split())
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy1".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource group add gr dummy1 dummy2".split())

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "gr")
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy2".split())

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pacemaker type=Stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11
                      interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pacemaker type=Stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11
                          interval=11 timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

    def test_clone_group_member(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_success("resource clone D0".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Group: AG
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D0-clone
                  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource clone D1".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Clone: D0-clone
                  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D1-clone
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_promotable_group_member(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_success("resource promotable D0".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Group: AG
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D0-clone
                  Meta Attributes: D0-clone-meta_attributes
                    promotable=true
                  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource promotable D1".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Clone: D0-clone
                  Meta Attributes: D0-clone-meta_attributes
                    promotable=true
                  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D1-clone
                  Meta Attributes: D1-clone-meta_attributes
                    promotable=true
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_clone_master(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success("resource clone D0".split())

        self.assert_pcs_fail(
            "resource promotable D3 meta promotable=false".split(),
            "Error: you cannot specify both promotable option and promotable keyword\n",
        )

        self.assert_pcs_success("resource promotable D3".split())

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
            dedent(
                """\
                Clone: D0-clone
                  Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D3-clone
                  Meta Attributes: D3-clone-meta_attributes
                    promotable=true
                  Resource: D3 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D3-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D1-master-custom
                  Meta Attributes:
                    promotable=true
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D2-master
                  Meta Attributes:
                    promotable=true
                  Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D2-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete D0".split(),
            stderr_full="Deleting Resource - D0\n",
        )
        self.assert_pcs_success(
            "resource delete D2".split(),
            stderr_full="Deleting Resource - D2\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: D0 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D0-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: D2-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: D3-clone
                  Meta Attributes: D3-clone-meta_attributes
                    promotable=true
                  Resource: D3 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D3-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D1-master-custom
                  Meta Attributes:
                    promotable=true
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_lsb_resource(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D2 lsb:network foo=bar".split(),
            (
                "Error: invalid resource option 'foo', there are no options"
                " allowed, use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 lsb:network foo=bar --force".split(),
            stderr_full=(
                "Warning: invalid resource option 'foo', there are no options"
                " allowed\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: D2 (class=lsb type=network)
                  Attributes: D2-instance_attributes
                    foo=bar
                  Operations:
                    monitor: D2-monitor-interval-15
                      interval=15 timeout=15
                """
            ),
        )

        self.assert_pcs_fail(
            "resource update D2 bar=baz".split(),
            (
                "Error: invalid resource option 'bar', there are no options"
                " allowed, use --force to override\n"
            ),
        )
        self.assert_pcs_success(
            "resource update D2 bar=baz --force".split(),
            stderr_full=(
                "Warning: invalid resource option 'bar', there are no options"
                " allowed\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: D2 (class=lsb type=network)
                  Attributes: D2-instance_attributes
                    bar=baz
                    foo=bar
                  Operations:
                    monitor: D2-monitor-interval-15
                      interval=15 timeout=15
                """
            ),
        )

    @skip(
        "test of 'pcs resource debug-*' to be moved to pcs.lib with the "
        "command itself"
    )
    def test_debug_start_clone_group(self):
        self.assert_pcs_success(
            "resource create D0 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create D1 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create D2 ocf:heartbeat:Dummy clone".split(),
        )

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("D3"))

        self.assert_pcs_fail(
            "resource debug-start DGroup".split(),
            "Error: unable to debug-start a group, try one of the group's resource(s) (D0,D1)\n",
        )
        self.assert_pcs_fail(
            "resource debug-start D2-clone".split(),
            "Error: unable to debug-start a clone, try the clone's resource: D2\n",
        )
        self.assert_pcs_fail(
            "resource debug-start D3-master".split(),
            "Error: unable to debug-start a master, try the master's resource: D3\n",
        )

    def test_group_clone_creation(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_fail(
            "resource clone DGroup1".split(),
            "Error: unable to find group or resource: DGroup1\n",
        )

        self.assert_pcs_success("resource clone DGroup".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: DGroup-clone
                  Group: DGroup
                    Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource clone DGroup".split(),
            "Error: cannot clone a group that has already been cloned\n",
        )

    def test_group_promotable_creation(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_fail(
            "resource promotable DGroup1".split(),
            "Error: unable to find group or resource: DGroup1\n",
        )

        self.assert_pcs_success("resource promotable DGroup".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: DGroup-clone
                  Meta Attributes: DGroup-clone-meta_attributes
                    promotable=true
                  Group: DGroup
                    Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource promotable DGroup".split(),
            "Error: cannot clone a group that has already been cloned\n",
        )

    @skip_unless_crm_rule()
    def test_group_remove_with_constraints1(self):
        # The mock executable for crm_resource does not support the
        # `move-with-constraint` command, and so the real executable is used.
        self.pcs_runner.mock_settings = {}

        # Load nodes into cib so move will work
        self.temp_cib.seek(0)
        xml = etree.fromstring(self.temp_cib.read())
        nodes_el = xml.find(".//nodes")
        etree.SubElement(nodes_el, "node", {"id": "1", "uname": "rh7-1"})
        etree.SubElement(nodes_el, "node", {"id": "2", "uname": "rh7-2"})
        write_data_to_tmpfile(etree.tounicode(xml), self.temp_cib)

        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        stdout, stderr, returncode = self.pcs_runner.run(
            "resource status".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        if is_pacemaker_21_without_20_compatibility():
            self.assertEqual(
                stdout,
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
                stdout,
                """\
  * Resource Group: DGroup:
    * D1\t(ocf::heartbeat:Dummy):\tStopped
    * D2\t(ocf::heartbeat:Dummy):\tStopped
""",
            )
        else:
            self.assertEqual(
                stdout,
                """\
 Resource Group: DGroup
     D1\t(ocf::heartbeat:Dummy):\tStopped
     D2\t(ocf::heartbeat:Dummy):\tStopped
""",
            )

        self.assert_pcs_success(
            "resource move-with-constraint DGroup rh7-1".split(),
            stderr_full=(
                "Warning: A move constraint has been created and the resource "
                "'DGroup' may or may not move depending on other configuration"
                "\n"
            ),
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                  Started resource 'DGroup' prefers node 'rh7-1' with score INFINITY
                """
            ),
        )
        self.assert_pcs_success(
            "resource delete D1".split(),
            stderr_full="Deleting Resource - D1\n",
        )
        self.assert_pcs_success(
            "resource delete D2".split(),
            stderr_full=dedent(
                """\
                Removing Constraint - cli-prefer-DGroup
                Deleting Resource (and group) - D2
                """
            ),
        )

        self.assert_pcs_success(
            "resource status".split(),
            "NO resources configured\n",
        )

    def test_resource_clone_creation(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        # resource "dummy1" is already in "temp_large_cib
        self.assert_pcs_success("resource clone dummy1".split())

    def test_resource_clone_id(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success("resource clone dummy".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummy".split(),
            stderr_full="Deleting Resource - dummy\n",
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy clone".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_resource_promotable_id(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy".split(),
        )
        self.assert_pcs_success("resource promotable dummy".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Meta Attributes: dummy-clone-1-meta_attributes
                    promotable=true
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummy".split(),
            stderr_full="Deleting Resource - dummy\n",
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:heartbeat:Dummy promotable".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Meta Attributes: dummy-clone-1-meta_attributes
                    promotable=true
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_resource_clone_update(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy clone".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource update D1-clone foo=bar".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Meta Attributes: D1-clone-meta_attributes
                    foo=bar
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource update D1-clone bar=baz".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Meta Attributes: D1-clone-meta_attributes
                    bar=baz
                    foo=bar
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource update D1-clone foo=".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Meta Attributes: D1-clone-meta_attributes
                    bar=baz
                  Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_group_remove_with_constraints2(self):
        self.assert_pcs_success(
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "constraint location AG prefers rh7-1".split(),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

        self.assert_pcs_success(
            "resource ungroup AG".split(),
            stderr_full="Removing Constraint - location-AG-rh7-1-INFINITY\n",
        )

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: A (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: A-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops A1 ocf:heartbeat:Dummy --group AA".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A2 ocf:heartbeat:Dummy --group AA".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "AA")
        self.assert_pcs_success(
            "constraint location AA-master prefers rh7-1".split(),
            stderr_full=(
                "Warning: Validation for node existence in the cluster will be skipped\n"
            ),
        )

        self.assert_pcs_success(
            "resource delete A1".split(),
            stderr_full="Deleting Resource - A1\n",
        )
        self.assert_pcs_success(
            "resource delete A2".split(),
            stderr_full=dedent(
                """\
                Removing Constraint - location-AA-master-rh7-1-INFINITY
                Deleting Resource (and group and M/S) - A2
                """
            ),
        )

    def test_mastered_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops A ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:heartbeat:Dummy --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
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

        self.assert_pcs_fail(
            "resource ungroup AG".split(),
            "Error: Cannot remove all resources from a cloned group\n",
        )

        self.assert_pcs_success(
            "resource delete B".split(),
            stderr_full="Deleting Resource - B\n",
        )
        self.assert_pcs_success(
            "resource delete C".split(),
            stderr_full="Deleting Resource - C\n",
        )
        self.assert_pcs_success("resource ungroup AG".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: AGMaster
                  Meta Attributes:
                    promotable=true
                  Resource: A (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      monitor: A-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_cloned_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:heartbeat:Dummy --group DG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:heartbeat:Dummy --group DG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone DG".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: DG-clone
                  Group: DG
                    Resource: D1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: D2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: D2-monitor-interval-10s
                          interval=10s timeout=20s
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

    def test_op_option(self):
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_fail(
            "resource update B ocf:heartbeat:Dummy op monitor interval=30s blah=blah".split(),
            "Error: blah is not a valid op option (use --force to override)\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:heartbeat:Dummy".split(),
        )

        self.assert_pcs_fail(
            "resource op add C monitor interval=30s blah=blah".split(),
            "Error: blah is not a valid op option (use --force to override)\n",
        )

        self.assert_pcs_fail(
            "resource op add C monitor interval=60 role=role".split(),
            "Error: role must be: {} (use --force to override)\n".format(
                format_list_custom_last_separator(const.PCMK_ROLES, " or ")
            ),
        )

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: C (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: C-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource update B op monitor interval=30s monitor interval=31s role=master".split(),
            "Error: role must be: {} (use --force to override)\n".format(
                format_list_custom_last_separator(const.PCMK_ROLES, " or ")
            ),
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=30s monitor interval=31s role=Master".split(),
        )

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: B (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: B-monitor-interval-30s
                      interval=30s
                    monitor: B-monitor-interval-31s
                      interval=31s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                Resource: C (class=ocf provider=heartbeat type=Dummy)
                  Operations:
                    monitor: C-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource update B op interval=5s".split(),
            "Error: interval=5s does not appear to be a valid operation action\n",
        )

    def test_clone_bad_resources(self):
        self.setup_cluster_a()
        self.assert_pcs_fail(
            "resource clone ClusterIP4".split(),
            "Error: ClusterIP4 is already a clone resource\n",
        )
        self.assert_pcs_fail(
            "resource clone ClusterIP5".split(),
            "Error: ClusterIP5 is already a clone resource\n",
        )
        self.assert_pcs_fail(
            "resource promotable ClusterIP4".split(),
            "Error: ClusterIP4 is already a clone resource\n",
        )
        self.assert_pcs_fail(
            "resource promotable ClusterIP5".split(),
            "Error: ClusterIP5 is already a clone resource\n",
        )

    def test_group_ms_and_clone(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D3 ocf:heartbeat:Dummy promotable --group xxx clone".split(),
            DEPRECATED_DASH_DASH_GROUP
            + "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops D4 ocf:heartbeat:Dummy promotable --group xxx".split(),
            DEPRECATED_DASH_DASH_GROUP
            + "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )

    def test_resource_clone_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy0 ocf:heartbeat:Dummy --group group".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone group".split())
        self.assert_pcs_success(
            "resource delete dummy0".split(),
            stderr_full="Deleting Resource (and group and clone) - dummy0\n",
        )

    def test_resource_missing_values(self):
        self.assert_pcs_success(
            "resource create --no-default-ops myip IPaddr2 --force".split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from 'IPaddr2')\n"
                "Warning: required resource option 'ip' is missing\n"
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops myip2 IPaddr2 ip=3.3.3.3".split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:IPaddr2' (deduced from 'IPaddr2')\n"
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops myfs Filesystem --force".split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')\n"
                "Warning: required resource options 'device', 'directory', 'fstype' are missing\n"
            ),
        )
        self.assert_pcs_success(
            (
                "resource create --no-default-ops myfs2 Filesystem device=x"
                " directory=y --force"
            ).split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')\n"
                "Warning: required resource option 'fstype' is missing\n"
            ),
        )
        self.assert_pcs_success(
            (
                "resource create --no-default-ops myfs3 Filesystem device=x"
                " directory=y fstype=z"
            ).split(),
            stderr_full=(
                "Assumed agent name 'ocf:heartbeat:Filesystem' (deduced from 'Filesystem')\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: myip (class=ocf provider=heartbeat type=IPaddr2)
                  Operations:
                    monitor: myip-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: myip2 (class=ocf provider=heartbeat type=IPaddr2)
                  Attributes: myip2-instance_attributes
                    ip=3.3.3.3
                  Operations:
                    monitor: myip2-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: myfs (class=ocf provider=heartbeat type=Filesystem)
                  Operations:
                    monitor: myfs-monitor-interval-20s
                      interval=20s timeout=40s
                Resource: myfs2 (class=ocf provider=heartbeat type=Filesystem)
                  Attributes: myfs2-instance_attributes
                    device=x
                    directory=y
                  Operations:
                    monitor: myfs2-monitor-interval-20s
                      interval=20s timeout=40s
                Resource: myfs3 (class=ocf provider=heartbeat type=Filesystem)
                  Attributes: myfs3-instance_attributes
                    device=x
                    directory=y
                    fstype=z
                  Operations:
                    monitor: myfs3-monitor-interval-20s
                      interval=20s timeout=40s
                """
            ),
        )

    def test_cloned_mastered_group(self):
        self.assert_pcs_success(
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone dummies".split())
        self.assert_pcs_success(
            "resource config dummies-clone".split(),
            dedent(
                """\
                Clone: dummies-clone
                  Group: dummies
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy3-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummies-clone".split())
        stdout, stderr, returncode = self.pcs_runner.run(
            "resource status".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        if is_pacemaker_21_without_20_compatibility():
            self.assertEqual(
                stdout,
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
                stdout,
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
            self.assertEqual(
                stdout,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::heartbeat:Dummy):\tStopped
                     dummy2\t(ocf::heartbeat:Dummy):\tStopped
                     dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )

        self.assert_pcs_success("resource clone dummies".split())
        self.assert_pcs_success(
            "resource config dummies-clone".split(),
            dedent(
                """\
                Clone: dummies-clone
                  Group: dummies
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy3-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummies-clone".split(),
            stderr_full=dedent(
                """\
                Removing group: dummies (and all resources within group)
                Stopping all resources in group: dummies...
                Deleting Resource - dummy1
                Deleting Resource - dummy2
                Deleting Resource (and group and clone) - dummy3
                """
            ),
        )
        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

        self.assert_pcs_success(
            "resource create dummy1 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy3 ocf:heartbeat:Dummy --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummies")

        self.assert_pcs_success(
            "resource config dummies-master".split(),
            dedent(
                """\
                Clone: dummies-master
                  Meta Attributes:
                    promotable=true
                  Group: dummies
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy3-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummies-master".split())
        stdout, stderr, returncode = self.pcs_runner.run(
            "resource status".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        if is_pacemaker_21_without_20_compatibility():
            self.assertEqual(
                stdout,
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
                stdout,
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
            self.assertEqual(
                stdout,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::heartbeat:Dummy):\tStopped
                     dummy2\t(ocf::heartbeat:Dummy):\tStopped
                     dummy3\t(ocf::heartbeat:Dummy):\tStopped
                """
                ),
            )

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "dummies")
        self.assert_pcs_success(
            "resource config dummies-master".split(),
            dedent(
                """\
                Clone: dummies-master
                  Meta Attributes:
                    promotable=true
                  Group: dummies
                    Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)
                      Operations:
                        monitor: dummy3-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource delete dummies-master".split(),
            stderr_full=dedent(
                """\
                Removing group: dummies (and all resources within group)
                Stopping all resources in group: dummies...
                Deleting Resource - dummy1
                Deleting Resource - dummy2
                Deleting Resource (and group and M/S) - dummy3
                """
            ),
        )
        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

    def test_relocate_stickiness(self):
        # pylint: disable=too-many-statements
        self.assert_pcs_success(
            "resource create D1 ocf:pacemaker:Dummy --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create DG1 ocf:pacemaker:Dummy --no-default-ops --group GR".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DG2 ocf:pacemaker:Dummy --no-default-ops --group GR".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DC ocf:pacemaker:Dummy --no-default-ops clone".split()
        )
        self.assert_pcs_success(
            "resource create DGC1 ocf:pacemaker:Dummy --no-default-ops --group GRC".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DGC2 ocf:pacemaker:Dummy --no-default-ops --group GRC".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone GRC".split())

        status = dedent(
            """\
            Resource: D1 (class=ocf provider=pacemaker type=Dummy)
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s timeout=20s
            Group: GR
              Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s timeout=20s
              Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s timeout=20s
            Clone: DC-clone
              Resource: DC (class=ocf provider=pacemaker type=Dummy)
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s timeout=20s
            Clone: GRC-clone
              Group: GRC
                Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: DGC2-monitor-interval-10s
                      interval=10s timeout=20s
            """
        )

        cib_original, stderr, returncode = self.pcs_runner.run(
            "cluster cib".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)

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
            dedent(
                """\
                Resource: D1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: D1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Meta Attributes: GR-meta_attributes
                    resource-stickiness=0
                  Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DG2-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Meta Attributes: DC-clone-meta_attributes
                    resource-stickiness=0
                  Resource: DC (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DC-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
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
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                      Meta Attributes: DGC2-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
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
            dedent(
                """\
                Resource: D1 (class=ocf provider=pacemaker type=Dummy)
                  Meta Attributes: D1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Resource: DC (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DC-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: GRC-clone
                  Group: GRC
                    Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                      Meta Attributes: DGC1-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
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
            dedent(
                """\
                Resource: D1 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Resource: DC (class=ocf provider=pacemaker type=Dummy)
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
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
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                      Meta Attributes: DGC2-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
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
            dedent(
                """\
                Resource: D1 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Meta Attributes: GR-meta_attributes
                    resource-stickiness=0
                  Resource: DG1 (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DG2-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Meta Attributes: DC-clone-meta_attributes
                    resource-stickiness=0
                  Resource: DC (class=ocf provider=pacemaker type=Dummy)
                    Meta Attributes: DC-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: GRC-clone
                  Group: GRC
                    Resource: DGC1 (class=ocf provider=pacemaker type=Dummy)
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pacemaker type=Dummy)
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )


class OperationDeleteRemoveMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
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
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")
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
            stderr_start="\nUsage: pcs resource op delete...",
        )


class OperationRemove(OperationDeleteRemoveMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.command = "remove"

    def test_usage(self):
        self.assert_pcs_fail(
            "resource op remove".split(),
            stderr_start="\nUsage: pcs resource op remove...",
        )


class Utilization(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = get_tmp_file("tier1_resource_utilization")
        self.temp_large_cib = get_tmp_file("tier1_resource_utilization_large")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        write_file_to_tmpfile(large_cib, self.temp_large_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

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
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )

    def test_resource_utilization_set(self):
        # see also BundleMiscCommands
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)

        self.assert_pcs_success(
            "resource utilization dummy test1=10".split(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy1".split(),
            dedent(
                """\
                Resource Utilization:
                 dummy1: 
                """
            ),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy".split(),
            dedent(
                """\
                Resource Utilization:
                 dummy: test1=10
                """
            ),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy test1=-10 test4=1234".split(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy".split(),
            dedent(
                """\
                Resource Utilization:
                 dummy: test1=-10 test4=1234
                """
            ),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy1 test2=321 empty=".split(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization dummy1".split(),
            dedent(
                """\
                Resource Utilization:
                 dummy1: test2=321
                """
            ),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )
        self.assert_pcs_success(
            "resource utilization".split(),
            dedent(
                """\
                Resource Utilization:
                 dummy: test1=-10 test4=1234
                 dummy1: test2=321
                """
            ),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )

    def test_no_warning_printed_placement_strategy_is_set(self):
        self.fixture_resource()
        self.assert_effect(
            "property set placement-strategy=minimal".split(),
            self.fixture_xml_resource_no_utilization(),
        )
        self.assert_resources_xml_in_cib(
            """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-placement-strategy"
                        name="placement-strategy" value="minimal"
                    />
                </cluster_property_set>
            </crm_config>
            """,
            get_cib_part_func=lambda cib: etree.tostring(
                etree.parse(cib).findall(".//crm_config")[0],
            ),
        )
        self.assert_effect(
            "resource utilization R test=100".split(),
            self.fixture_xml_resource_with_utilization(),
        )
        self.assert_pcs_success(
            "resource utilization".split(),
            dedent(
                """\
                Resource Utilization:
                 R: test=100
                """
            ),
        )

    def test_resource_utilization_set_invalid(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.assert_pcs_fail(
            "resource utilization dummy test".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: missing value of 'test' option\n"
            ),
        )
        self.assert_pcs_fail(
            "resource utilization dummy =10".split(),
            f"{FIXTURE_UTILIZATION_WARNING}Error: missing key in '=10' option\n",
        )
        self.assert_pcs_fail(
            "resource utilization dummy0".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Unable to find a resource: dummy0\n"
            ),
        )
        self.assert_pcs_fail(
            "resource utilization dummy0 test=10".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Unable to find a resource: dummy0\n"
            ),
        )
        self.assert_pcs_fail(
            "resource utilization dummy1 test1=10 test=int".split(),
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Value of utilization attribute must be integer: "
                "'test=int'\n"
            ),
        )

    def test_keep_empty_nvset(self):
        self.fixture_resource_utilization()
        self.assert_effect(
            "resource utilization R test=".split(),
            self.fixture_xml_resource_empty_utilization(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource utilization R test=".split(),
            self.fixture_xml_resource_no_utilization(),
            stderr_full=FIXTURE_UTILIZATION_WARNING,
        )


class MetaAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = get_tmp_file("tier1_resource_meta")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    def tearDown(self):
        self.temp_cib.close()

    def set_cib_file(self, *xml_string_list):
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", *xml_string_list)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    @staticmethod
    def _fixture_xml_resource_no_meta():
        return """
        <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
            <operations>
                <op id="R-monitor-interval-10s" interval="10s"
                    name="monitor" timeout="20s"
                />
            </operations>
        </primitive>
        """

    @staticmethod
    def fixture_xml_resource_no_meta():
        return f"""
            <resources>
            {MetaAttrs._fixture_xml_resource_no_meta()}
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

    def test_meta_attrs(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D0 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30 meta"
                " test5=test5a test6=test6a"
            ).split(),
            stderr_full=(
                "Warning: invalid resource options: 'test', 'test2', allowed"
                " options are: 'fake', 'state', 'trace_file', 'trace_ra'\n"
            ),
        )
        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D1 ocf:heartbeat:Dummy"
                " test=testA test2=test2a op monitor interval=30"
            ).split(),
            stderr_full=(
                "Warning: invalid resource options: 'test', 'test2', allowed"
                " options are: 'fake', 'state', 'trace_file', 'trace_ra'\n"
            ),
        )
        self.assert_pcs_success(
            (
                "resource update --force D0 test=testC test2=test2a op monitor "
                "interval=35 meta test7=test7a test6="
            ).split()
        )
        self.assert_pcs_success("resource meta D1 d1meta=superd1meta".split())
        self.assert_pcs_success("resource group add TestRG D1".split())
        self.assert_pcs_success(
            "resource meta TestRG testrgmeta=mymeta testrgmeta2=mymeta2".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
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

    def test_resource_meta_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource meta R a=".split(),
            self.fixture_xml_resource_empty_meta(),
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
            "resource meta R a=".split(),
            self.fixture_xml_resource_no_meta(),
        )

    def test_resource_update_dont_create_meta_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R meta a=".split(),
            self.fixture_xml_resource_no_meta(),
        )

    @staticmethod
    def fixture_not_ocf_clone():
        return """
            <clone id="clone-R">
                <primitive class="systemd" id="R" type="pacemaker">
                    <instance_attributes id="R-instance_attributes" />
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </clone>
            """

    def test_clone_promotable_not_ocf(self):
        self.set_cib_file(self.fixture_not_ocf_clone())
        self.assert_pcs_fail(
            "resource meta clone-R promotable=1".split(),
            (
                "Error: Clone option 'promotable' is not compatible with "
                "'systemd:pacemaker' resource agent of resource 'R'\n"
            ),
        )

    def test_clone_globally_unique_not_ocf(self):
        self.set_cib_file(self.fixture_not_ocf_clone())
        self.assert_pcs_fail(
            "resource meta clone-R globally-unique=1".split(),
            (
                "Error: Clone option 'globally-unique' is not compatible with "
                "'systemd:pacemaker' resource agent of resource 'R'\n"
            ),
        )

    def test_clone_promotable_unsupported(self):
        self.set_cib_file(
            f"""
            <clone id="clone-R">
                {self._fixture_xml_resource_no_meta()}
            </clone>
            """
        )
        self.assert_pcs_fail(
            "resource meta clone-R promotable=1".split(),
            (
                "Error: Clone option 'promotable' is not compatible with "
                "'ocf:pacemaker:Dummy' resource agent of resource 'R', use --force to override\n"
            ),
        )

    def test_clone_promotable_unsupported_force(self):
        self.set_cib_file(
            f"""
            <clone id="clone-R">
                {self._fixture_xml_resource_no_meta()}
            </clone>
            """
        )
        self.assert_effect(
            "resource meta clone-R promotable=1 --force".split(),
            """
                <resources>
                    <clone id="clone-R">
                        <primitive class="ocf" id="R" provider="pacemaker"
                            type="Dummy"
                        >
                            <operations>
                                <op id="R-monitor-interval-10s" interval="10s"
                                    name="monitor" timeout="20s"
                                />
                            </operations>
                        </primitive>
                        <meta_attributes id="clone-R-meta_attributes">
                            <nvpair id="clone-R-meta_attributes-promotable"
                                name="promotable" value="1"
                            />
                        </meta_attributes>
                    </clone>
                </resources>
            """,
            stderr_full=(
                "Warning: Clone option 'promotable' is not compatible with "
                "'ocf:pacemaker:Dummy' resource agent of resource 'R'\n"
            ),
        )


class UpdateInstanceAttrs(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
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
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

    def tearDown(self):
        self.temp_cib.close()

    def set_cib_file(self, *xml_string_list):
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", *xml_string_list)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

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
    def _fixture_xml_resource_empty_attrs():
        return """
            <primitive class="ocf" id="R" provider="pacemaker" type="Dummy">
                <instance_attributes id="R-instance_attributes" />
                <operations>
                    <op id="R-monitor-interval-10s" interval="10s"
                        name="monitor" timeout="20s"
                    />
                </operations>
            </primitive>
        """

    @staticmethod
    def fixture_xml_resource_empty_attrs():
        return f"""
            <resources>
            {UpdateInstanceAttrs._fixture_xml_resource_empty_attrs()}
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
            stderr_start="\nUsage: pcs resource update...\n",
        )

    def test_bad_instance_variables(self):
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
            stderr_full=(
                "Warning: invalid resource options: 'test', 'test2', 'test4',"
                " allowed options are: 'fake', 'state', 'trace_file', "
                "'trace_ra'\n"
            ),
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA test2=testB test3=testD".split(),
            (
                "Error: invalid resource option 'test3', allowed options"
                " are: 'fake', 'state', 'trace_file', 'trace_ra', use --force "
                "to override\n"
            ),
        )

        self.assert_pcs_success(
            "resource update D0 test=testB test2=testC test3=testD --force".split(),
            stderr_full=(
                "Warning: invalid resource option 'test3',"
                " allowed options are: 'fake', 'state', 'trace_file', "
                "'trace_ra'\n"
            ),
        )

        self.assert_pcs_success(
            "resource config D0".split(),
            dedent(
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
            stderr_full=f"Warning: {message}\n",
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA".split(),
            f"Error: {message}, use --force to override\n",
        )
        self.assert_pcs_success(
            "resource update --force D0 test=testA".split(),
            stderr_full=f"Warning: {message}\n",
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
            stderr_start=(
                "Error: Validation result from agent (use --force to override):"
            ),
        )

    @staticmethod
    def fixture_not_ocf_clone():
        return """
            <clone id="clone-R">
                <primitive class="systemd" id="R" type="pacemaker">
                    <instance_attributes id="R-instance_attributes" />
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </clone>
            """

    def test_clone_promotable_not_ocf(self):
        self.set_cib_file(self.fixture_not_ocf_clone())
        self.assert_pcs_fail_regardless_of_force(
            "resource update clone-R promotable=1".split(),
            (
                "Error: Clone option 'promotable' is not compatible with "
                "'systemd:pacemaker' resource agent of resource 'R'\n"
            ),
        )

    def test_clone_globally_unique_not_ocf(self):
        self.set_cib_file(self.fixture_not_ocf_clone())
        self.assert_pcs_fail_regardless_of_force(
            "resource update clone-R globally-unique=1".split(),
            (
                "Error: Clone option 'globally-unique' is not compatible with "
                "'systemd:pacemaker' resource agent of resource 'R'\n"
            ),
        )

    def test_clone_promotable_unsupported(self):
        self.set_cib_file(
            f"""
            <clone id="clone-R">
                {self._fixture_xml_resource_empty_attrs()}
            </clone>
            """
        )
        self.assert_pcs_fail(
            "resource update clone-R promotable=1".split(),
            (
                "Error: Clone option 'promotable' is not compatible with "
                "'ocf:pacemaker:Dummy' resource agent of resource 'R', "
                "use --force to override\n"
            ),
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
            "resource delete dummy".split(),
            stderr_full="Deleting Resource - dummy\n",
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
            stderr_full=(
                "Removing group: dummy-group (and all resources within group)\n"
                "Stopping all resources in group: dummy-group...\n"
                "Deleting Resource - dummy1\n"
                "Deleting Resource (and group) - dummy2\n"
            ),
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
            stderr_full=(
                "Removing group: dummy-group (and all resources within group)\n"
                "Stopping all resources in group: dummy-group...\n"
                "Deleting Resource - dummy1\n"
                "Deleting Resource (and group) - dummy2\n"
            ),
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
            dedent(
                """\
                Clone: dummy-clone
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      migrate_from: dummy-migrate_from-interval-0s
                        interval=0s timeout=20s
                      migrate_to: dummy-migrate_to-interval-0s
                        interval=0s timeout=20s
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                      reload: dummy-reload-interval-0s
                        interval=0s timeout=20s
                      start: dummy-start-interval-0s
                        interval=0s timeout=20s
                      stop: dummy-stop-interval-0s
                        interval=0s timeout=20s
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
            dedent(
                """\
                Clone: dummy-clone
                  Resource: dummy (class=ocf provider=heartbeat type=Dummy)
                    Operations:
                      migrate_from: dummy-migrate_from-interval-0s
                        interval=0s timeout=20s
                      migrate_to: dummy-migrate_to-interval-0s
                        interval=0s timeout=20s
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                      reload: dummy-reload-interval-0s
                        interval=0s timeout=20s
                      start: dummy-start-interval-0s
                        interval=0s timeout=20s
                      stop: dummy-stop-interval-0s
                        interval=0s timeout=20s
                """
            ),
        )

    def test_no_op_allowed_in_master_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("dummy"))
        show = dedent(
            f"""\
            Clone: dummy-master
              Meta Attributes:
                promotable=true
              Resource: dummy (class=ocf provider=pacemaker type=Stateful)
                Operations:
                  monitor: dummy-monitor-interval-10
                    interval=10 timeout=20 role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                  monitor: dummy-monitor-interval-11
                    interval=11 timeout=20 role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  notify: dummy-notify-interval-0s
                    interval=0s timeout=5
                  start: dummy-start-interval-0s
                    interval=0s timeout=20
                  stop: dummy-stop-interval-0s
                    interval=0s timeout=20
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


class TransformMasterToClone(ResourceTest):
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
        role = str(const.PCMK_ROLE_PROMOTED_LEGACY).lower()
        self.assert_pcs_success(
            f"constraint ticket add T {role} A loss-policy=fence".split(),
            stderr_full=(
                f"Deprecation Warning: Value '{role}' of option role is "
                "deprecated and might be removed in future, therefore it "
                "should not be used, use "
                f"'{const.PCMK_ROLE_PROMOTED}' value instead\n"
            ),
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            (
                "Ticket Constraints:\n"
                f"  {const.PCMK_ROLE_PROMOTED_PRIMARY} resource 'A' depends on ticket 'T'\n"
                "    loss-policy=fence\n"
            ),
        )
        self.assert_pcs_success(
            "resource delete A".split(),
            stderr_full=(
                "Removing Constraint - ticket-T-A-Master\n"
                "Deleting Resource - A\n"
            ),
        )


class BundleCommon(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
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
            dedent(
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
            dedent(
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
            "resource delete B".split(),
            "<resources/>",
            stderr_full="Deleting bundle 'B'\n",
        )

    def test_with_primitive(self):
        self.fixture_bundle("B")
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "resource delete B".split(),
            "<resources/>",
            stderr_full=(
                "Deleting bundle 'B' and its inner resource 'R'\n"
                "Deleting Resource - R\n"
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
            stderr_full="Deleting Resource - R\n",
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
            (
                f"{FIXTURE_UTILIZATION_WARNING}"
                "Error: Unable to find a resource: B\n"
            ),
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
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )

    def test_update_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
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
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )
        self.assert_pcs_success(
            "resource update R meta remote-node= --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for removing a guest node,"
                " use 'pcs cluster node remove-guest'\n"
            ),
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
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )

    def test_meta_fail_on_pacemaker_guest_attempt_remove(self):
        self.assert_pcs_success(
            (
                "resource create R ocf:heartbeat:Dummy meta remote-node=HOST"
                " --force"
            ).split(),
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
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
            stderr_full=(
                "Warning: this command is not sufficient for creating a guest node,"
                " use 'pcs cluster node add-guest'\n"
            ),
        )
        self.assert_pcs_success(
            "resource meta R remote-node= --force".split(),
            stderr_full=(
                "Warning: this command is not sufficient for removing a guest node,"
                " use 'pcs cluster node remove-guest'\n"
            ),
        )


class ResourceUpdateUniqueAttrChecks(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_update_unique_attr")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_exec")

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
            (
                "Error: Value '1' of option 'state' is not unique across "
                "'ocf:pacemaker:Dummy' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1', "
                "use --force to override\n"
            ),
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
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pacemaker:Dummy' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        res_config = dedent(
            """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=1
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s timeout=20s
            """
        )
        self.assert_pcs_success("resource config".split(), res_config)
        # make sure that it doesn't check against resource itself
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pacemaker:Dummy' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        self.assert_pcs_success("resource config".split(), res_config)
        res_config = dedent(
            """\
            Resource: R1 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s timeout=20s
            Resource: R2 (class=ocf provider=pacemaker type=Dummy)
              Attributes: R2-instance_attributes
                state=2
              Operations:
                monitor: R2-monitor-interval-10s
                  interval=10s timeout=20s
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
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pacemaker:Dummy' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: R1 (class=ocf provider=pacemaker type=Dummy)
                  Attributes: R1-instance_attributes
                    state=1
                  Operations:
                    monitor: R1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R2 (class=ocf provider=pacemaker type=Dummy)
                  Attributes: R2-instance_attributes
                    state=1
                  Operations:
                    monitor: R2-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R3 (class=ocf provider=pacemaker type=Dummy)
                  Operations:
                    monitor: R3-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )
        self.assert_pcs_success(
            "resource update R3 state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pacemaker:Dummy' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1', "
                "'R2'\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: R1 (class=ocf provider=pacemaker type=Dummy)
                  Attributes: R1-instance_attributes
                    state=1
                  Operations:
                    monitor: R1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R2 (class=ocf provider=pacemaker type=Dummy)
                  Attributes: R2-instance_attributes
                    state=1
                  Operations:
                    monitor: R2-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R3 (class=ocf provider=pacemaker type=Dummy)
                  Attributes: R3-instance_attributes
                    state=1
                  Operations:
                    monitor: R3-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )
