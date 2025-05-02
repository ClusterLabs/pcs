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
        self.pcs_runner.mock_settings = get_mock_settings()

    @staticmethod
    def fixture_description(advanced=False):
        advanced_params = """
              advanced (advanced use only)
                Description: This parameter should not be set usually
                Type: string"""
        return dedent(
            """\
            ocf:pcsmock:params - Mock agent for pcs tests - agent with various parameters

            This is a mock agent for pcs test - agent with parameters

            Resource options:
              mandatory (required)
                Description: A generic mandatory string parameter
                Type: string
              optional
                Description: A generic optional string parameter
                Type: string
                Default: if not specified
              enum
                Description: An optional enum parameter
                Allowed values: 'value1', 'value2', 'value3'
                Default: value1{0}
              unique1 (unique group: group-A)
                Description: First parameter in a unique group
                Type: string
              unique2 (unique group: group-A)
                Description: Second parameter in a unique group
                Type: string

            Default operations:
              start:
                interval=0s timeout=20s
              stop:
                interval=0s timeout=20s
              monitor:
                interval=10s timeout=20s
              reload:
                interval=0s timeout=20s
              reload-agent:
                interval=0s timeout=20s
              migrate_to:
                interval=0s timeout=20s
              migrate_from:
                interval=0s timeout=20s
            """.format(advanced_params if advanced else "")
        )

    def test_success(self):
        self.assert_pcs_success(
            "resource describe ocf:pcsmock:params".split(),
            self.fixture_description(),
        )

    def test_full(self):
        self.assert_pcs_success(
            "resource describe ocf:pcsmock:params --full".split(),
            self.fixture_description(True),
        )

    def test_success_guess_name(self):
        self.assert_pcs_success(
            "resource describe params".split(),
            stdout_full=self.fixture_description(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:params' (deduced from 'params')\n"
            ),
        )

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "resource describe ocf:pcsmock:nonexistent".split(),
            (
                "Error: Agent 'ocf:pcsmock:nonexistent' is not installed or does "
                "not provide valid metadata: "
                "pcs mock error message: unable to load agent metadata\n"
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
            "resource describe pcsmock".split(),
            (
                "Error: Multiple agents match 'pcsmock', please specify full"
                " name: 'ocf:heartbeat:pcsMock' or 'ocf:pacemaker:pcsMock'\n"
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
        self.maxDiff = None
        stdout, stderr, returncode = self.pcs_runner.run(
            "resource get_resource_agent_info ocf:pcsmock:params".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(returncode, 0)
        self.assertEqual(
            json.loads(stdout),
            {
                "name": "ocf:pcsmock:params",
                "standard": "ocf",
                "provider": "pcsmock",
                "type": "params",
                "shortdesc": "Mock agent for pcs tests - agent with various parameters",
                "longdesc": "This is a mock agent for pcs test - agent with parameters",
                "parameters": [
                    {
                        "advanced": False,
                        "default": None,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": "A generic mandatory string parameter",
                        "name": "mandatory",
                        "reloadable": False,
                        "required": True,
                        "shortdesc": "mandatory string parameter",
                        "type": "string",
                        "unique_group": None,
                    },
                    {
                        "advanced": False,
                        "default": "if not specified",
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": "A generic optional string parameter",
                        "name": "optional",
                        "reloadable": False,
                        "required": False,
                        "shortdesc": "optional string parameter",
                        "type": "string",
                        "unique_group": None,
                    },
                    {
                        "advanced": False,
                        "default": "value1",
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": ["value1", "value2", "value3"],
                        "longdesc": "An optional enum parameter",
                        "name": "enum",
                        "reloadable": False,
                        "required": False,
                        "shortdesc": "optional enum parameter",
                        "type": "select",
                        "unique_group": None,
                    },
                    {
                        "advanced": True,
                        "default": None,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": "This parameter should not be set usually",
                        "name": "advanced",
                        "reloadable": False,
                        "required": False,
                        "shortdesc": "advanced parameter",
                        "type": "string",
                        "unique_group": None,
                    },
                    {
                        "advanced": False,
                        "default": None,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": "First parameter in a unique group",
                        "name": "unique1",
                        "reloadable": False,
                        "required": False,
                        "shortdesc": "unique param 1",
                        "type": "string",
                        "unique_group": "group-A",
                    },
                    {
                        "advanced": False,
                        "default": None,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": "Second parameter in a unique group",
                        "name": "unique2",
                        "reloadable": False,
                        "required": False,
                        "shortdesc": "unique param 2",
                        "type": "string",
                        "unique_group": "group-A",
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
                "resource create --no-default-ops ClusterIP ocf:pcsmock:minimal"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP2 ocf:pcsmock:minimal"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP3 ocf:pcsmock:minimal"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP4 ocf:pcsmock:minimal"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP5 ocf:pcsmock:minimal"
            ).split()
        )
        self.assert_pcs_success_ignore_output(
            (
                "resource create --no-default-ops ClusterIP6 ocf:pcsmock:minimal"
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
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setup_cluster_a(self):
        write_file_to_tmpfile(CIB_FIXTURE.cache_path, self.temp_cib)

    def test_case_insensitive(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D0 pcsmock".split(),
            (
                "Error: Multiple agents match 'pcsmock', please specify full name: "
                "'ocf:heartbeat:pcsMock' or 'ocf:pacemaker:pcsMock'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D1 camelcase".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:CamelCase'"
                " (deduced from 'camelcase')\n"
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops D2 CAMELCASE".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:CamelCase'"
                " (deduced from 'CAMELCASE')\n"
            ),
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops D4 camel_case".split(),
            (
                "Error: Unable to find agent 'camel_case', try specifying its full name\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_empty(self):
        self.assert_pcs_success(["resource"], "NO resources configured\n")

    def test_add_resources_large_cib(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()
        self.assert_pcs_success(
            "resource create dummy0 ocf:pcsmock:minimal --no-default-ops".split(),
        )
        self.assert_pcs_success(
            "resource config dummy0".split(),
            dedent(
                """\
                Resource: dummy0 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy0-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

    def test_resource_show(self):
        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:pcsmock:params"
                " mandatory=mandat optional=opti op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            dedent(
                """\
                Resource: ClusterIP (class=ocf provider=pcsmock type=params)
                  Attributes: ClusterIP-instance_attributes
                    mandatory=mandat
                    optional=opti
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
                "resource create --no-default-ops ClusterIP ocf:pcsmock:minimal"
                " op monitor interval=30s"
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: ClusterIP-monitor-interval-30s
                      interval=30s
                    monitor: ClusterIP-monitor-interval-31s
                      interval=31s
                """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops OPTest ocf:pcsmock:minimal "
                "op monitor interval=30s OCF_CHECK_LEVEL=1 "
                "op monitor interval=25s OCF_CHECK_LEVEL=1 enabled=0"
            ).split(),
        )

        self.assert_pcs_success(
            "resource config OPTest".split(),
            dedent(
                """\
                Resource: OPTest (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: OPTest-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=1
                    monitor: OPTest-monitor-interval-25s
                      interval=25s enabled=0 OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops OPTest2 ocf:pcsmock:minimal "
                "op monitor interval=30s OCF_CHECK_LEVEL=1 "
                "op monitor interval=25s OCF_CHECK_LEVEL=2 "
                "op start timeout=30s"
            ).split(),
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
                Resource: OPTest2 (class=ocf provider=pcsmock type=minimal)
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
            (
                "resource create --no-default-ops OPTest3 ocf:pcsmock:minimal "
                "op monitor OCF_CHECK_LEVEL=1"
            ).split(),
        )

        self.assert_pcs_success(
            "resource config OPTest3".split(),
            dedent(
                """\
                Resource: OPTest3 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: OPTest3-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops OPTest4 ocf:pcsmock:minimal "
                "op monitor interval=30s"
            ).split(),
        )

        self.assert_pcs_success(
            "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest4".split(),
            dedent(
                """\
                Resource: OPTest4 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: OPTest4-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest5 ocf:pcsmock:minimal".split(),
        )

        self.assert_pcs_success(
            "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest5".split(),
            dedent(
                """\
                Resource: OPTest5 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: OPTest5-monitor-interval-60s
                      interval=60s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest6 ocf:pcsmock:minimal".split(),
        )

        self.assert_pcs_success(
            "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1".split(),
        )

        self.assert_pcs_success(
            "resource config OPTest6".split(),
            dedent(
                """\
                Resource: OPTest6 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: OPTest6-monitor-interval-10s
                      interval=10s timeout=20s
                    monitor: OPTest6-monitor-interval-30s
                      interval=30s OCF_CHECK_LEVEL=1
                """
            ),
        )

        self.assert_pcs_success(
            "resource create --no-default-ops OPTest7 ocf:pcsmock:minimal".split(),
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
                Resource: OPTest7 (class=ocf provider=pcsmock type=minimal)
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
            "resource create --no-default-ops OCFTest1 ocf:pcsmock:minimal".split(),
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
                Resource: OCFTest1 (class=ocf provider=pcsmock type=minimal)
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
                Resource: OCFTest1 (class=ocf provider=pcsmock type=minimal)
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
                Resource: OCFTest1 (class=ocf provider=pcsmock type=minimal)
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
                Resource: OCFTest1 (class=ocf provider=pcsmock type=minimal)
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
            "resource create --no-default-ops state ocf:pcsmock:stateful".split(),
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
                Resource: state (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: state-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: state-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    monitor: state-monitor-interval-15
                      interval=15 role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                """
            ),
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_add_operation_onfail_demote_upgrade_cib(self):
        write_file_to_tmpfile(rc("cib-empty-3.3.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pcsmock:minimal".split()
        )
        self.assert_pcs_success(
            "resource op add R start on-fail=demote".split(),
            stderr_full="Cluster CIB has been upgraded to latest version\n",
        )

    @skip_unless_pacemaker_supports_op_onfail_demote()
    def test_update_add_operation_onfail_demote_upgrade_cib(self):
        write_file_to_tmpfile(rc("cib-empty-3.3.xml"), self.temp_cib)
        self.assert_pcs_success(
            "resource create --no-default-ops R ocf:pcsmock:minimal".split()
        )
        self.assert_pcs_success(
            "resource update R op start on-fail=demote".split(),
            stderr_full="Cluster CIB has been upgraded to latest version\n",
        )

    def _test_delete_remove_operation(self, command):
        assert command in {"delete", "remove"}

        self.assert_pcs_success(
            (
                "resource create --no-default-ops ClusterIP ocf:pcsmock:minimal"
                " op monitor interval=30s"
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=minimal)
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=minimal)
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=minimal)
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
                "resource create --no-default-ops ClusterIP ocf:pcsmock:params"
                " mandatory=value op monitor interval=30s"
            ).split()
        )
        self.assert_pcs_success(
            "resource config ClusterIP".split(),
            dedent(
                """\
                Resource: ClusterIP (class=ocf provider=pcsmock type=params)
                  Attributes: ClusterIP-instance_attributes
                    mandatory=value
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=params)
                  Attributes: ClusterIP-instance_attributes
                    mandatory=value
                  Operations:
                    monitor: ClusterIP-monitor-interval-32s
                      interval=32s
                """
            ),
        )

        show_clusterip = dedent(
            """\
            Resource: ClusterIP (class=ocf provider=pcsmock type=params)
              Attributes: ClusterIP-instance_attributes
                mandatory=value
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
                Resource: ClusterIP (class=ocf provider=pcsmock type=params)
                  Attributes: ClusterIP-instance_attributes
                    mandatory=value
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
            "resource create A ocf:pcsmock:minimal op monitor interval=10 op monitor interval=20".split()
        )
        self.assert_pcs_success(
            "resource config A".split(),
            dedent(
                """\
                Resource: A (class=ocf provider=pcsmock type=minimal)
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
                    reload-agent: A-reload-agent-interval-0s
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
                Resource: A (class=ocf provider=pcsmock type=minimal)
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
                    reload-agent: A-reload-agent-interval-0s
                      interval=0s timeout=20s
                    start: A-start-interval-0s
                      interval=0s timeout=20s
                    stop: A-stop-interval-0s
                      interval=0s timeout=20s
                """
            ),
        )

        self.assert_pcs_success(
            "resource create B ocf:pcsmock:minimal --no-default-ops".split(),
        )

        self.assert_pcs_success(
            "resource op remove B-monitor-interval-10s".split()
        )

        self.assert_pcs_success(
            "resource config B".split(),
            "Resource: B (class=ocf provider=pcsmock type=minimal)\n",
        )

        self.assert_pcs_success(
            "resource update B op monitor interval=60s".split(),
        )

        self.assert_pcs_success(
            "resource config B".split(),
            dedent(
                """\
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
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

    @skip_unless_crm_rule()
    def test_group_ungroup(self):
        self.assert_pcs_success(
            "resource create --no-default-ops A1 ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A2 ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A3 ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A4 ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops A5 ocf:pcsmock:minimal".split(),
        )

        self.assert_pcs_success(
            "resource group add AGroup A1 A2 A3 A4 A5".split(),
        )

        self.assert_pcs_success(
            "resource config AGroup".split(),
            dedent(
                """\
                Group: AGroup
                  Resource: A1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A2 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A2-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A3 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A3-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A4 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A4-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: A5 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A5-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_group_order(self):
        # This was cosidered for removing during 'resource group add' command
        # and tests overhaul. However, this is the only test where "resource
        # group list" is called. Due to that this test was not deleted.
        self.assert_pcs_success(
            "resource create --no-default-ops A ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops E ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops F ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops G ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops H ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops I ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops J ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops K ocf:pcsmock:minimal".split(),
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
                      * F\t(ocf:pcsmock:minimal):\t Stopped
                      * G\t(ocf:pcsmock:minimal):\t Stopped
                      * H\t(ocf:pcsmock:minimal):\t Stopped
                      * Resource Group: RGA:
                        * A\t(ocf:pcsmock:minimal):\t Stopped
                        * B\t(ocf:pcsmock:minimal):\t Stopped
                        * C\t(ocf:pcsmock:minimal):\t Stopped
                        * E\t(ocf:pcsmock:minimal):\t Stopped
                        * D\t(ocf:pcsmock:minimal):\t Stopped
                        * K\t(ocf:pcsmock:minimal):\t Stopped
                        * J\t(ocf:pcsmock:minimal):\t Stopped
                        * I\t(ocf:pcsmock:minimal):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                stdout,
                """\
  * F\t(ocf::pcsmock:minimal):\tStopped
  * G\t(ocf::pcsmock:minimal):\tStopped
  * H\t(ocf::pcsmock:minimal):\tStopped
  * Resource Group: RGA:
    * A\t(ocf::pcsmock:minimal):\tStopped
    * B\t(ocf::pcsmock:minimal):\tStopped
    * C\t(ocf::pcsmock:minimal):\tStopped
    * E\t(ocf::pcsmock:minimal):\tStopped
    * D\t(ocf::pcsmock:minimal):\tStopped
    * K\t(ocf::pcsmock:minimal):\tStopped
    * J\t(ocf::pcsmock:minimal):\tStopped
    * I\t(ocf::pcsmock:minimal):\tStopped
""",
            )
        else:
            self.assertEqual(
                stdout,
                """\
 F\t(ocf::pcsmock:minimal):\tStopped
 G\t(ocf::pcsmock:minimal):\tStopped
 H\t(ocf::pcsmock:minimal):\tStopped
 Resource Group: RGA
     A\t(ocf::pcsmock:minimal):\tStopped
     B\t(ocf::pcsmock:minimal):\tStopped
     C\t(ocf::pcsmock:minimal):\tStopped
     E\t(ocf::pcsmock:minimal):\tStopped
     D\t(ocf::pcsmock:minimal):\tStopped
     K\t(ocf::pcsmock:minimal):\tStopped
     J\t(ocf::pcsmock:minimal):\tStopped
     I\t(ocf::pcsmock:minimal):\tStopped
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
                  Resource: ClusterIP6 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: ClusterIP6-monitor-interval-10s
                        interval=10s timeout=20s
                  Group: TestGroup1
                    Resource: ClusterIP (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: ClusterIP-monitor-interval-10s
                          interval=10s timeout=20s
                  Group: TestGroup2
                    Resource: ClusterIP2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: ClusterIP2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: ClusterIP3 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: ClusterIP3-monitor-interval-10s
                          interval=10s timeout=20s
                  Clone: ClusterIP4-clone
                    Resource: ClusterIP4 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: ClusterIP4-monitor-interval-10s
                          interval=10s timeout=20s
                  Clone: Master
                    Meta Attributes:
                      promotable=true
                    Resource: ClusterIP5 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: ClusterIP5-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

    def test_ms_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:minimal".split(),
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
                    Resource: D0 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: D0-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: D1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

    def test_unclone(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pcsmock:minimal".split()
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pcsmock:minimal".split(),
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: gr-clone
                  Group: gr
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
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
                Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

    def test_unclone_master(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops dummy1 ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy2 ocf:pcsmock:stateful".split(),
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
                  Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: dummy2-master
                  Meta Attributes:
                    promotable=true
                  Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy2".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Group: gr
                  Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr-master".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Group: gr
                  Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone gr".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Group: gr
                  Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy1-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy1-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                  Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy2-monitor-interval-10s
                        interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                      monitor: dummy2-monitor-interval-11s
                        interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
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
                Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy1".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy1-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy1-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                    Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy2-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

        self.assert_pcs_success("resource unclone dummy2".split())

        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                f"""\
                Resource: dummy2 (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy2-monitor-interval-10s
                      interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                    monitor: dummy2-monitor-interval-11s
                      interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                Clone: gr-master
                  Meta Attributes:
                    promotable=true
                  Group: gr
                    Resource: dummy1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                        monitor: dummy1-monitor-interval-11s
                          interval=11s timeout=20s role={const.PCMK_ROLE_UNPROMOTED_PRIMARY}
                """
            ),
        )

    def test_clone_group_member(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:pcsmock:minimal --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:minimal --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_success("resource clone D0".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Group: AG
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D0-clone
                  Resource: D0 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: D0 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: D1-clone
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_promotable_group_member(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:pcsmock:stateful --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:stateful --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )

        self.assert_pcs_success("resource promotable D0".split())
        self.assert_pcs_success(
            ["resource", "config"],
            dedent(
                """\
                Group: AG
                  Resource: D1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D1-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                Clone: D0-clone
                  Meta Attributes: D0-clone-meta_attributes
                    promotable=true
                  Resource: D0 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D0-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
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
                  Resource: D0 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D0-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                Clone: D1-clone
                  Meta Attributes: D1-clone-meta_attributes
                    promotable=true
                  Resource: D1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D1-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                """
            ),
        )

    def test_clone_master(self):
        # see also BundleClone
        self.assert_pcs_success(
            "resource create --no-default-ops D0 ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D3 ocf:pcsmock:stateful".split(),
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
                  Resource: D0 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D0-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D0-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                Clone: D3-clone
                  Meta Attributes: D3-clone-meta_attributes
                    promotable=true
                  Resource: D3 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D3-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D3-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                Clone: D1-master-custom
                  Meta Attributes:
                    promotable=true
                  Resource: D1 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D1-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                Clone: D2-master
                  Meta Attributes:
                    promotable=true
                  Resource: D2 (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: D2-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: D2-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                """
            ),
        )

    def test_lsb_resource(self):
        self.assert_pcs_fail(
            "resource create --no-default-ops D2 lsb:pcsmock foo=bar".split(),
            (
                "Error: invalid resource option 'foo', there are no options"
                " allowed, use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 lsb:pcsmock foo=bar --force".split(),
            stderr_full=(
                "Warning: invalid resource option 'foo', there are no options"
                " allowed\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: D2 (class=lsb type=pcsmock)
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
                Resource: D2 (class=lsb type=pcsmock)
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
            "resource create D0 ocf:pcsmock:minimal --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create D1 ocf:pcsmock:minimal --group DGroup".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create D2 ocf:pcsmock:minimal clone".split(),
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
            "resource create --no-default-ops D1 ocf:pcsmock:minimal --group DGroup".split(),
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
                    Resource: D1 (class=ocf provider=pcsmock type=minimal)
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
            "resource create --no-default-ops D1 ocf:pcsmock:stateful --group DGroup".split(),
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
                    Resource: D1 (class=ocf provider=pcsmock type=stateful)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s role=Promoted
                        monitor: D1-monitor-interval-11s
                          interval=11s timeout=20s role=Unpromoted
                """
            ),
        )

        self.assert_pcs_fail(
            "resource promotable DGroup".split(),
            "Error: cannot clone a group that has already been cloned\n",
        )

    def test_resource_clone_creation(self):
        self.pcs_runner = PcsRunner(self.temp_large_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()
        # resource "dummy1" is already in "temp_large_cib
        self.assert_pcs_success("resource clone dummy1".split())

    def test_resource_clone_id_clone_command(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success("resource clone dummy".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Resource: dummy (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_resource_clone_id_create_command(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:pcsmock:minimal".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:pcsmock:minimal clone".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s
                Clone: dummy-clone-1
                  Resource: dummy (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_resource_promotable_id_promotable_command(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success("resource promotable dummy".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s role=Promoted
                    monitor: dummy-clone-monitor-interval-11s
                      interval=11s timeout=20s role=Unpromoted
                Clone: dummy-clone-1
                  Meta Attributes: dummy-clone-1-meta_attributes
                    promotable=true
                  Resource: dummy (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: dummy-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                """
            ),
        )

    def test_resource_promotable_id_create_command(self):
        self.assert_pcs_success(
            "resource create --no-default-ops dummy-clone ocf:pcsmock:stateful".split(),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops dummy ocf:pcsmock:stateful promotable".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: dummy-clone (class=ocf provider=pcsmock type=stateful)
                  Operations:
                    monitor: dummy-clone-monitor-interval-10s
                      interval=10s timeout=20s role=Promoted
                    monitor: dummy-clone-monitor-interval-11s
                      interval=11s timeout=20s role=Unpromoted
                Clone: dummy-clone-1
                  Meta Attributes: dummy-clone-1-meta_attributes
                    promotable=true
                  Resource: dummy (class=ocf provider=pcsmock type=stateful)
                    Operations:
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s role=Promoted
                      monitor: dummy-monitor-interval-11s
                        interval=11s timeout=20s role=Unpromoted
                """
            ),
        )

    def test_resource_clone_update(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:minimal clone".split(),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: D1-clone
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
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
                  Resource: D1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: D1-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_mastered_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops A ocf:pcsmock:minimal --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:pcsmock:minimal --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:pcsmock:minimal --group AG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "AG", master_id="AGMaster")

        self.assert_pcs_fail(
            "resource create --no-default-ops A ocf:pcsmock:minimal".split(),
            "Error: 'A' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops AG ocf:pcsmock:minimal".split(),
            "Error: 'AG' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops AGMaster ocf:pcsmock:minimal".split(),
            "Error: 'AGMaster' already exists\n",
        )

        self.assert_pcs_fail(
            "resource ungroup AG".split(),
            "Error: Cannot remove all resources from a cloned group\n",
        )

        self.assert_pcs_success(
            "resource delete B".split(),
            stderr_full=dedent(
                """\
                Removing references:
                  Resource 'B' from:
                    Group: 'AG'
                """
            ),
        )
        self.assert_pcs_success(
            "resource delete C".split(),
            stderr_full=dedent(
                """\
                Removing references:
                  Resource 'C' from:
                    Group: 'AG'
                """
            ),
        )
        self.assert_pcs_success("resource ungroup AG".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: AGMaster
                  Meta Attributes:
                    promotable=true
                  Resource: A (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: A-monitor-interval-10s
                        interval=10s timeout=20s
                """
            ),
        )

    def test_cloned_group(self):
        self.assert_pcs_success(
            "resource create --no-default-ops D1 ocf:pcsmock:minimal --group DG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create --no-default-ops D2 ocf:pcsmock:minimal --group DG".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone DG".split())
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Clone: DG-clone
                  Group: DG
                    Resource: D1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: D1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: D2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: D2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        self.assert_pcs_fail(
            "resource create --no-default-ops D1 ocf:pcsmock:minimal".split(),
            "Error: 'D1' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG ocf:pcsmock:minimal".split(),
            "Error: 'DG' already exists\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops DG-clone ocf:pcsmock:minimal".split(),
            "Error: 'DG-clone' already exists\n",
        )

    def test_op_option(self):
        self.assert_pcs_success(
            "resource create --no-default-ops B ocf:pcsmock:minimal".split(),
        )

        self.assert_pcs_fail(
            "resource update B ocf:pcsmock:minimal op monitor interval=30s blah=blah".split(),
            "Error: blah is not a valid op option (use --force to override)\n",
        )

        self.assert_pcs_success(
            "resource create --no-default-ops C ocf:pcsmock:minimal".split(),
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: B-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: C (class=ocf provider=pcsmock type=minimal)
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
                Resource: B (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: B-monitor-interval-30s
                      interval=30s
                    monitor: B-monitor-interval-31s
                      interval=31s role={const.PCMK_ROLE_PROMOTED_PRIMARY}
                Resource: C (class=ocf provider=pcsmock type=minimal)
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
            "resource create --no-default-ops D3 ocf:pcsmock:minimal promotable --group xxx clone".split(),
            DEPRECATED_DASH_DASH_GROUP
            + "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )
        self.assert_pcs_fail(
            "resource create --no-default-ops D4 ocf:pcsmock:minimal promotable --group xxx".split(),
            DEPRECATED_DASH_DASH_GROUP
            + "Error: you can specify only one of clone, promotable, bundle or --group\n",
        )

    def test_resource_missing_values(self):
        self.assert_pcs_success(
            "resource create --no-default-ops myip params --force".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:params' (deduced from 'params')\n"
                "Warning: required resource option 'mandatory' is missing\n"
            ),
        )
        self.assert_pcs_success(
            "resource create --no-default-ops myip2 params mandatory=value".split(),
            stderr_full=(
                "Assumed agent name 'ocf:pcsmock:params' (deduced from 'params')\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: myip (class=ocf provider=pcsmock type=params)
                  Operations:
                    monitor: myip-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: myip2 (class=ocf provider=pcsmock type=params)
                  Attributes: myip2-instance_attributes
                    mandatory=value
                  Operations:
                    monitor: myip2-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )

    def test_cloned_mastered_group(self):
        self.assert_pcs_success(
            "resource create dummy1 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy3 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone dummies".split())
        self.assert_pcs_success(
            "resource config dummies-clone".split(),
            dedent(
                """\
                Clone: dummies-clone
                  Group: dummies
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=pcsmock type=minimal)
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
                        * dummy1\t(ocf:pcsmock:minimal):\t Stopped
                        * dummy2\t(ocf:pcsmock:minimal):\t Stopped
                        * dummy3\t(ocf:pcsmock:minimal):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                stdout,
                outdent(
                    """\
                  * Resource Group: dummies:
                    * dummy1\t(ocf::pcsmock:minimal):\tStopped
                    * dummy2\t(ocf::pcsmock:minimal):\tStopped
                    * dummy3\t(ocf::pcsmock:minimal):\tStopped
                """
                ),
            )
        else:
            self.assertEqual(
                stdout,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::pcsmock:minimal):\tStopped
                     dummy2\t(ocf::pcsmock:minimal):\tStopped
                     dummy3\t(ocf::pcsmock:minimal):\tStopped
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=pcsmock type=minimal)
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
                Removing dependant elements:
                  Group: 'dummies'
                  Resources: 'dummy1', 'dummy2', 'dummy3'
                """
            ),
        )
        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

        self.assert_pcs_success(
            "resource create dummy1 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create dummy3 ocf:pcsmock:minimal --no-default-ops --group dummies".split(),
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=pcsmock type=minimal)
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
                        * dummy1\t(ocf:pcsmock:minimal):\t Stopped
                        * dummy2\t(ocf:pcsmock:minimal):\t Stopped
                        * dummy3\t(ocf:pcsmock:minimal):\t Stopped
                    """
                ),
            )
        elif PCMK_2_0_3_PLUS:
            assert_pcs_status(
                stdout,
                outdent(
                    """\
                  * Resource Group: dummies:
                    * dummy1\t(ocf::pcsmock:minimal):\tStopped
                    * dummy2\t(ocf::pcsmock:minimal):\tStopped
                    * dummy3\t(ocf::pcsmock:minimal):\tStopped
                """
                ),
            )
        else:
            self.assertEqual(
                stdout,
                outdent(
                    """\
                 Resource Group: dummies
                     dummy1\t(ocf::pcsmock:minimal):\tStopped
                     dummy2\t(ocf::pcsmock:minimal):\tStopped
                     dummy3\t(ocf::pcsmock:minimal):\tStopped
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
                    Resource: dummy1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: dummy2-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: dummy3 (class=ocf provider=pcsmock type=minimal)
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
                Removing dependant elements:
                  Group: 'dummies'
                  Resources: 'dummy1', 'dummy2', 'dummy3'
                """
            ),
        )
        self.assert_pcs_success(
            "resource status".split(), "NO resources configured\n"
        )

    def test_relocate_stickiness(self):
        # pylint: disable=too-many-statements
        self.assert_pcs_success(
            "resource create D1 ocf:pcsmock:minimal --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create DG1 ocf:pcsmock:minimal --no-default-ops --group GR".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DG2 ocf:pcsmock:minimal --no-default-ops --group GR".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DC ocf:pcsmock:minimal --no-default-ops clone".split()
        )
        self.assert_pcs_success(
            "resource create DGC1 ocf:pcsmock:minimal --no-default-ops --group GRC".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success(
            "resource create DGC2 ocf:pcsmock:minimal --no-default-ops --group GRC".split(),
            stderr_full=DEPRECATED_DASH_DASH_GROUP,
        )
        self.assert_pcs_success("resource clone GRC".split())

        status = dedent(
            """\
            Resource: D1 (class=ocf provider=pcsmock type=minimal)
              Operations:
                monitor: D1-monitor-interval-10s
                  interval=10s timeout=20s
            Group: GR
              Resource: DG1 (class=ocf provider=pcsmock type=minimal)
                Operations:
                  monitor: DG1-monitor-interval-10s
                    interval=10s timeout=20s
              Resource: DG2 (class=ocf provider=pcsmock type=minimal)
                Operations:
                  monitor: DG2-monitor-interval-10s
                    interval=10s timeout=20s
            Clone: DC-clone
              Resource: DC (class=ocf provider=pcsmock type=minimal)
                Operations:
                  monitor: DC-monitor-interval-10s
                    interval=10s timeout=20s
            Clone: GRC-clone
              Group: GRC
                Resource: DGC1 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: DGC1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: DGC2 (class=ocf provider=pcsmock type=minimal)
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

        resources = {
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
        }
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
                Resource: D1 (class=ocf provider=pcsmock type=minimal)
                  Meta Attributes: D1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Meta Attributes: GR-meta_attributes
                    resource-stickiness=0
                  Resource: DG1 (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DG2-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Meta Attributes: DC-clone-meta_attributes
                    resource-stickiness=0
                  Resource: DC (class=ocf provider=pcsmock type=minimal)
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
                    Resource: DGC1 (class=ocf provider=pcsmock type=minimal)
                      Meta Attributes: DGC1-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pcsmock type=minimal)
                      Meta Attributes: DGC2-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        resources = {"D1", "DG1", "DC", "DGC1"}
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
                Resource: D1 (class=ocf provider=pcsmock type=minimal)
                  Meta Attributes: D1-meta_attributes
                    resource-stickiness=0
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Resource: DG1 (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Resource: DC (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DC-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: GRC-clone
                  Group: GRC
                    Resource: DGC1 (class=ocf provider=pcsmock type=minimal)
                      Meta Attributes: DGC1-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        resources = {"GRC-clone", "GRC", "DGC1", "DGC2"}
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
                Resource: D1 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Resource: DG1 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Resource: DC (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: GRC-clone
                  Meta Attributes: GRC-clone-meta_attributes
                    resource-stickiness=0
                  Group: GRC
                    Meta Attributes: GRC-meta_attributes
                      resource-stickiness=0
                    Resource: DGC1 (class=ocf provider=pcsmock type=minimal)
                      Meta Attributes: DGC1-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pcsmock type=minimal)
                      Meta Attributes: DGC2-meta_attributes
                        resource-stickiness=0
                      Operations:
                        monitor: DGC2-monitor-interval-10s
                          interval=10s timeout=20s
                """
            ),
        )

        resources = {"GR", "DG1", "DG2", "DC-clone", "DC"}
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
                Resource: D1 (class=ocf provider=pcsmock type=minimal)
                  Operations:
                    monitor: D1-monitor-interval-10s
                      interval=10s timeout=20s
                Group: GR
                  Meta Attributes: GR-meta_attributes
                    resource-stickiness=0
                  Resource: DG1 (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DG1-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG1-monitor-interval-10s
                        interval=10s timeout=20s
                  Resource: DG2 (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DG2-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DG2-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: DC-clone
                  Meta Attributes: DC-clone-meta_attributes
                    resource-stickiness=0
                  Resource: DC (class=ocf provider=pcsmock type=minimal)
                    Meta Attributes: DC-meta_attributes
                      resource-stickiness=0
                    Operations:
                      monitor: DC-monitor-interval-10s
                        interval=10s timeout=20s
                Clone: GRC-clone
                  Group: GRC
                    Resource: DGC1 (class=ocf provider=pcsmock type=minimal)
                      Operations:
                        monitor: DGC1-monitor-interval-10s
                          interval=10s timeout=20s
                    Resource: DGC2 (class=ocf provider=pcsmock type=minimal)
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
        self.pcs_runner.mock_settings = get_mock_settings()
        self.command = "to-be-overridden"

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    fixture_xml_1_monitor = """
        <resources>
            <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
            <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
                <operations>
                </operations>
            </primitive>
        </resources>
    """

    def fixture_resource(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pcsmock:minimal".split(),
            self.fixture_xml_1_monitor,
        )

    def fixture_monitor_20(self):
        self.assert_effect(
            "resource op add R monitor interval=20s timeout=20s --force".split(),
            """
                <resources>
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
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
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
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
                    <primitive class="ocf" id="R" provider="pcsmock"
                        type="minimal"
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
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()
        self.temp_large_cib.close()

    @staticmethod
    def fixture_xml_resource_no_utilization():
        return """
            <resources>
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
            "resource create --no-default-ops R ocf:pcsmock:minimal".split(),
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
        self.pcs_runner.mock_settings = get_mock_settings()

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
        self.pcs_runner.mock_settings = get_mock_settings()
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
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def set_cib_file(self, *xml_string_list):
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", *xml_string_list)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    @staticmethod
    def _fixture_xml_resource_no_meta():
        return """
        <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
                <primitive class="ocf" id="R" provider="pcsmock" type="minimal">
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
            "resource create --no-default-ops R ocf:pcsmock:minimal".split(),
            self.fixture_xml_resource_no_meta(),
        )

    def fixture_resource_meta(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pcsmock:minimal meta a=b".split(),
            self.fixture_xml_resource_with_meta(),
        )

    def test_meta_attrs(self):
        # see also BundleMiscCommands
        self.assert_pcs_success(
            (
                "resource create --no-default-ops D0 ocf:pcsmock:params"
                " mandatory=test1a optional=test2a op monitor interval=30 meta"
                " test5=test5a test6=test6a"
            ).split(),
        )
        self.assert_pcs_success(
            (
                "resource create --no-default-ops D1 ocf:pcsmock:params"
                " mandatory=test1a optional=test2a op monitor interval=30"
            ).split(),
        )
        self.assert_pcs_success(
            (
                "resource update D0 mandatory=test1b optional=test2a op monitor "
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
                Resource: D0 (class=ocf provider=pcsmock type=params)
                  Attributes: D0-instance_attributes
                    mandatory=test1b
                    optional=test2a
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
                  Resource: D1 (class=ocf provider=pcsmock type=params)
                    Attributes: D1-instance_attributes
                      mandatory=test1a
                      optional=test2a
                    Meta Attributes: D1-meta_attributes
                      d1meta=superd1meta
                    Operations:
                      monitor: D1-monitor-interval-30
                        interval=30
                """
            ),
        )

    def test_resource_update_keep_empty_meta(self):
        self.fixture_resource_meta()
        self.assert_effect(
            "resource update R meta a=".split(),
            self.fixture_xml_resource_empty_meta(),
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
                <primitive class="systemd" id="R" type="pcsmock">
                    <instance_attributes id="R-instance_attributes" />
                    <operations>
                        <op id="R-monitor-interval-10s" interval="10s"
                            name="monitor" timeout="20s"
                        />
                    </operations>
                </primitive>
            </clone>
            """


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
        self.pcs_runner.mock_settings = get_mock_settings()

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
                <primitive class="ocf" id="R" provider="pcsmock" type="params">
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
            <primitive class="ocf" id="R" provider="pcsmock" type="params">
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
                <primitive class="ocf" id="R" provider="pcsmock" type="params">
                    <instance_attributes id="R-instance_attributes">
                        <nvpair id="R-instance_attributes-mandatory"
                            name="mandatory" value="F"
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
            "resource create --no-default-ops R ocf:pcsmock:params --force".split(),
            self.fixture_xml_resource_no_attrs(),
            stderr_full="Warning: required resource option 'mandatory' is missing\n",
        )

    def fixture_resource_attrs(self):
        self.assert_effect(
            "resource create --no-default-ops R ocf:pcsmock:params mandatory=F".split(),
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
                "resource create --no-default-ops D0 ocf:pcsmock:params"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ).split(),
            (
                "Error: invalid resource options: 'test', 'test2', 'test4', "
                "allowed options are: 'advanced', 'enum', 'mandatory', "
                "'optional', 'unique1', 'unique2', use --force to override\n"
                "Error: required resource option 'mandatory' is missing, "
                "use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            (
                "resource create --no-default-ops --force D0 ocf:pcsmock:params"
                " test=testC test2=test2a test4=test4A op monitor interval=35"
                " meta test7=test7a test6="
            ).split(),
            stderr_full=(
                "Warning: invalid resource options: 'test', 'test2', 'test4',"
                " allowed options are: 'advanced', 'enum', 'mandatory', "
                "'optional', 'unique1', 'unique2'\n"
                "Warning: required resource option 'mandatory' is missing\n"
            ),
        )

        self.assert_pcs_fail(
            "resource update D0 test=testA test2=testB test3=testD".split(),
            (
                "Error: invalid resource option 'test3', allowed options"
                " are: 'advanced', 'enum', 'mandatory', 'optional', 'unique1', "
                "'unique2', use --force to override\n"
            ),
        )

        self.assert_pcs_success(
            "resource update D0 test=testB test2=testC test3=testD --force".split(),
            stderr_full=(
                "Warning: invalid resource option 'test3',"
                " allowed options are: 'advanced', 'enum', 'mandatory', "
                "'optional', 'unique1', 'unique2'\n"
            ),
        )

        self.assert_pcs_success(
            "resource config D0".split(),
            dedent(
                """\
                Resource: D0 (class=ocf provider=pcsmock type=params)
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
        agent = "ocf:pcsmock:nonexistent"
        message = (
            f"Agent '{agent}' is not installed or does "
            "not provide valid metadata: "
            "pcs mock error message: unable to load agent metadata"
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
                <primitive class="ocf" id="Dummy" provider="pcsmock"
                    type="params"
                >
                    <instance_attributes id="Dummy-instance_attributes">
                        <nvpair id="Dummy-instance_attributes-mandatory"
                            name="mandatory" value="manda"
                        />
                        <nvpair id="Dummy-instance_attributes-optional"
                            name="optional" value="{optional}"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="Dummy-monitor-interval-30s" interval="30s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
        """
        self.assert_effect(
            (
                "resource create --no-default-ops Dummy ocf:pcsmock:params"
                " mandatory=manda optional=opti1 op monitor interval=30s"
            ).split(),
            xml.format(optional="opti1"),
        )

        self.assert_effect(
            "resource update Dummy optional=opti2".split(),
            xml.format(optional="opti2"),
        )

    def test_keep_empty_nvset(self):
        self.fixture_resource_attrs()
        self.assert_effect(
            "resource update R mandatory= --force".split(),
            self.fixture_xml_resource_empty_attrs(),
            stderr_full="Warning: required resource option 'mandatory' is missing\n",
        )

    def test_dont_create_nvset_on_removal(self):
        self.fixture_resource()
        self.assert_effect(
            "resource update R mandatory= --force".split(),
            self.fixture_xml_resource_no_attrs(),
            stderr_full="Warning: required resource option 'mandatory' is missing\n",
        )

    def test_agent_self_validation_failure(self):
        self.fixture_resource()
        self.assert_pcs_fail(
            [
                "resource",
                "update",
                "R",
                "mandatory=is_invalid=True",
                "--agent-validation",
            ],
            stderr_full=(
                "Error: Validation result from agent (use --force to override):\n"
                "  pcsmock validation failure\n"
            ),
        )

    @staticmethod
    def fixture_not_ocf_clone():
        return """
            <clone id="clone-R">
                <primitive class="systemd" id="R" type="pcsmock">
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
                "'systemd:pcsmock' resource agent of resource 'R'\n"
            ),
        )

    def test_clone_globally_unique_not_ocf(self):
        self.set_cib_file(self.fixture_not_ocf_clone())
        self.assert_pcs_fail_regardless_of_force(
            "resource update clone-R globally-unique=1".split(),
            (
                "Error: Clone option 'globally-unique' is not compatible with "
                "'systemd:pcsmock' resource agent of resource 'R'\n"
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
                "'ocf:pcsmock:params' resource agent of resource 'R', "
                "use --force to override\n"
            ),
        )


class CloneMasterUpdate(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_clone_master_update")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def test_no_op_allowed_in_clone_update(self):
        self.assert_pcs_success(
            "resource create dummy ocf:pcsmock:minimal clone".split()
        )
        self.assert_pcs_success(
            "resource config dummy-clone".split(),
            dedent(
                """\
                Clone: dummy-clone
                  Resource: dummy (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      migrate_from: dummy-migrate_from-interval-0s
                        interval=0s timeout=20s
                      migrate_to: dummy-migrate_to-interval-0s
                        interval=0s timeout=20s
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                      reload: dummy-reload-interval-0s
                        interval=0s timeout=20s
                      reload-agent: dummy-reload-agent-interval-0s
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
                  Resource: dummy (class=ocf provider=pcsmock type=minimal)
                    Operations:
                      migrate_from: dummy-migrate_from-interval-0s
                        interval=0s timeout=20s
                      migrate_to: dummy-migrate_to-interval-0s
                        interval=0s timeout=20s
                      monitor: dummy-monitor-interval-10s
                        interval=10s timeout=20s
                      reload: dummy-reload-interval-0s
                        interval=0s timeout=20s
                      reload-agent: dummy-reload-agent-interval-0s
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
              Resource: dummy (class=ocf provider=pcsmock type=stateful)
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
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings()

    def test_transform_master_without_meta_on_update(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("dummy"))
        self.assert_effect(
            "resource update dummy-master meta a=b".split(),
            """<resources>
                <clone id="dummy-master">
                    <primitive class="ocf" id="dummy" provider="pcsmock"
                        type="stateful"
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
                    <primitive class="ocf" id="dummy" provider="pcsmock"
                        type="stateful"
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
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def fixture_primitive(self, name, bundle):
        self.assert_pcs_success(
            [
                "resource",
                "create",
                name,
                "ocf:pcsmock:minimal",
                "bundle",
                bundle,
            ]
        )

    def fixture_bundle(self, name, container="docker"):
        deprecated_rkt = (
            "Deprecation Warning: Value 'rkt' of option container type is "
            "deprecated and might be removed in a future release, therefore it should "
            "not be used\n"
        )
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
            ],
            stderr_full=(deprecated_rkt if container == "rkt" else None),
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
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def test_update_fail_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:pcsmock:minimal".split())
        self.assert_pcs_fail(
            "resource update R meta remote-node=HOST".split(),
            (
                "Error: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest', use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_update_warn_on_pacemaker_guest_attempt(self):
        self.assert_pcs_success("resource create R ocf:pcsmock:minimal".split())
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
                "resource create R ocf:pcsmock:minimal meta remote-node=HOST"
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
                "resource create R ocf:pcsmock:minimal meta remote-node=HOST"
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


class ResourceUpdateUniqueAttrChecks(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_update_unique_attr")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings()

    def tearDown(self):
        self.temp_cib.close()

    def test_unique_err(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pcsmock:unique state=1".split()
        )
        self.assert_pcs_success("resource create R2 ocf:pcsmock:unique".split())
        self.assert_pcs_fail(
            "resource update R2 state=1".split(),
            (
                "Error: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1', "
                "use --force to override\n"
            ),
        )

    def test_unique_setting_same_value(self):
        self.assert_pcs_success(
            "resource create R1 ocf:pcsmock:unique state=1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pcsmock:unique --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        res_config = dedent(
            """\
            Resource: R1 (class=ocf provider=pcsmock type=unique)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s timeout=20s
            Resource: R2 (class=ocf provider=pcsmock type=unique)
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
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        self.assert_pcs_success("resource config".split(), res_config)
        res_config = dedent(
            """\
            Resource: R1 (class=ocf provider=pcsmock type=unique)
              Attributes: R1-instance_attributes
                state=1
              Operations:
                monitor: R1-monitor-interval-10s
                  interval=10s timeout=20s
            Resource: R2 (class=ocf provider=pcsmock type=unique)
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
            "resource create R1 ocf:pcsmock:unique state=1 --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R2 ocf:pcsmock:unique --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource create R3 ocf:pcsmock:unique --no-default-ops".split()
        )
        self.assert_pcs_success(
            "resource update R2 state=1 --force".split(),
            stderr_full=(
                "Warning: Value '1' of option 'state' is not unique across "
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1'\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: R1 (class=ocf provider=pcsmock type=unique)
                  Attributes: R1-instance_attributes
                    state=1
                  Operations:
                    monitor: R1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R2 (class=ocf provider=pcsmock type=unique)
                  Attributes: R2-instance_attributes
                    state=1
                  Operations:
                    monitor: R2-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R3 (class=ocf provider=pcsmock type=unique)
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
                "'ocf:pcsmock:unique' resources. Following resources are "
                "configured with the same value of the instance attribute: 'R1', "
                "'R2'\n"
            ),
        )
        self.assert_pcs_success(
            "resource config".split(),
            dedent(
                """\
                Resource: R1 (class=ocf provider=pcsmock type=unique)
                  Attributes: R1-instance_attributes
                    state=1
                  Operations:
                    monitor: R1-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R2 (class=ocf provider=pcsmock type=unique)
                  Attributes: R2-instance_attributes
                    state=1
                  Operations:
                    monitor: R2-monitor-interval-10s
                      interval=10s timeout=20s
                Resource: R3 (class=ocf provider=pcsmock type=unique)
                  Attributes: R3-instance_attributes
                    state=1
                  Operations:
                    monitor: R3-monitor-interval-10s
                      interval=10s timeout=20s
                """
            ),
        )
