# pylint: disable=too-many-lines
import datetime
import os
import unittest
from collections import namedtuple
from textwrap import dedent

from lxml import etree

from pcs import settings
from pcs.common import const
from pcs.common.str_tools import format_list
from pcs.constraint import (
    CRM_RULE_MISSING_MSG,
    LOCATION_NODE_VALIDATION_SKIP_MSG,
)

from pcs_test.tools.assertions import (
    AssertPcsMixin,
    ac,
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
from pcs_test.tools.misc import ParametrizedTestMetaClass
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    outdent,
    skip_unless_crm_rule,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)

# pylint: disable=too-many-public-methods
# pylint: disable=invalid-name
# pylint: disable=too-many-statements

LOCATION_NODE_VALIDATION_SKIP_WARNING = (
    f"Warning: {LOCATION_NODE_VALIDATION_SKIP_MSG}\n"
)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)

empty_cib = rc("cib-empty-3.7.xml")
large_cib = rc("cib-large.xml")


class ConstraintTestCibFixture(CachedCibFixture):
    def _setup_cib(self):
        line = "resource create D1 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource create D2 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource create D3 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource create D4 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource create D5 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource create D6 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        line = "resource clone D3".split()
        stdout, stderr, retval = pcs(self.cache_path, line)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master_file(self.cache_path, "D4", master_id="Master")


CIB_FIXTURE = ConstraintTestCibFixture("fixture_tier1_constraints", empty_cib)


@skip_unless_crm_rule()
class ConstraintTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_constraints")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.temp_corosync_conf = None
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()
        if self.temp_corosync_conf:
            self.temp_corosync_conf.close()

    def fixture_resources(self):
        write_file_to_tmpfile(CIB_FIXTURE.cache_path, self.temp_cib)

    def testConstraintRules(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule score=222 #uname eq c00n03".split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule score=-INFINITY #uname eq c00n04".split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create C1 ocf:heartbeat:Dummy --group C1-group".split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location D3 rule score=-INFINITY "
                "not_defined pingd or pingd lte 0 --force"
            ).split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location D3 rule score=-INFINITY "
                "not_defined pingd and pingd lte 0 --force"
            ).split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full --all".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: score=222 (id:location-D1-rule)
        Expression: #uname eq c00n03 (id:location-D1-rule-expr)
  Resource: D2
    Constraint: location-D2
      Rule: score=-INFINITY (id:location-D2-rule)
        Expression: #uname eq c00n04 (id:location-D2-rule-expr)
  Resource: D3
    Constraint: location-D3
      Rule: boolean-op=or score=-INFINITY (id:location-D3-rule)
        Expression: not_defined pingd (id:location-D3-rule-expr)
        Expression: pingd lte 0 (id:location-D3-rule-expr-1)
    Constraint: location-D3-1
      Rule: boolean-op=and score=-INFINITY (id:location-D3-1-rule)
        Expression: not_defined pingd (id:location-D3-1-rule-expr)
        Expression: pingd lte 0 (id:location-D3-1-rule-expr-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testAdvancedConstraintRule(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location D1 rule score=INFINITY "
                "not_defined pingd or pingd lte 0"
            ).split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: boolean-op=or score=INFINITY (id:location-D1-rule)
        Expression: not_defined pingd (id:location-D1-rule-expr)
        Expression: pingd lte 0 (id:location-D1-rule-expr-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testEmptyConstraints(self):
        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        ac(
            stdout,
            "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testMultipleOrderConstraints(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stop D1 then stop D2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: first-action=stop then-action=stop)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then start D2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            "Location Constraints:\nOrdering Constraints:\n  stop D1 then stop D2 (kind:Mandatory) (id:order-D1-D2-mandatory)\n  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-1)\nColocation Constraints:\nTicket Constraints:\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_order_options_empty_value(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 option1=".split(),
        )
        self.assertIn("value of 'option1' option is empty", stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def test_order_too_many_resources(self):
        msg = (
            "Error: Multiple 'then's cannot be specified.\n"
            "Hint: Use the 'pcs constraint order set' command if you want to "
            "create a constraint for more than two resources.\n"
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 then D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then start D2 then start D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then D2 then D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then start D2 then D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 then start D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then D2 then start D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then start D2 then start D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then D2 then start D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def testOrderConstraintRequireAll(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "cluster cib-upgrade".split()
        )
        self.assertEqual(
            stderr, "Cluster CIB has been upgraded to latest version\n"
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then start D2 require-all=false".split(),
        )
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: require-all=false first-action=start then-action=start)\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
Ordering Constraints:
  start D1 then start D2 (kind:Mandatory) (Options: require-all=false) (id:order-D1-D2-mandatory)
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testAllConstraints(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 prefers node1".split(),
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order Master then D5".split()
        )
        self.assertEqual(retval, 0)
        ac(
            stderr,
            "Adding Master D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add Master with D5".split(),
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: D5
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)
            Ordering Constraints:
              start Master then start D5 (kind:Mandatory) (id:order-Master-D5-mandatory)
            Colocation Constraints:
              Master with D5 (score:INFINITY) (id:colocation-Master-D5-INFINITY)
            Ticket Constraints:
            """
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint config --full".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: D5
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)
            Ordering Constraints:
              start Master then start D5 (kind:Mandatory) (id:order-Master-D5-mandatory)
            Colocation Constraints:
              Master with D5 (score:INFINITY) (id:colocation-Master-D5-INFINITY)
            Ticket Constraints:
            """
            ),
        )

    # see also BundleLocation
    def testLocationConstraints(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 prefers node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 avoids node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 prefers node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 avoids node2".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location add location-D5-node1-INFINITY".split(),
        )
        self.assertEqual(retval, 1)
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: D5
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)
                Disabled on:
                  Node: node2 (score:-INFINITY) (id:location-D5-node2--INFINITY)
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location delete location-D5-node1-INFINITY".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location remove location-D5-node2--INFINITY".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

    def testConstraintRemoval(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D5 prefers node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D6 prefers node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint remove blahblah".split()
        )
        self.assertEqual(retval, 1)
        self.assertTrue(
            stderr.startswith("Error: Unable to find constraint - 'blahblah'"),
            stderr,
        )
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint delete blahblah".split()
        )
        self.assertEqual(retval, 1)
        self.assertTrue(
            stderr.startswith("Error: Unable to find constraint - 'blahblah'"),
            stderr,
        )
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint location config --full".split()
        )
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: D5
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)
              Resource: D6
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-D6-node1-INFINITY)
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint remove location-D5-node1-INFINITY location-D6-node1-INFINITY".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint location config --full".split()
        )
        ac(stdout, "Location Constraints:\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    # see also BundleColocation
    def testColocationConstraints(self):
        self.fixture_resources()
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(
            self.temp_cib.name,
            "\n".join(
                ["<resources>"]
                + [fixture_master_xml(f"M{i}") for i in range(1, 11)]
                + ["</resources>"]
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D3-clone".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 100".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "--force -- constraint colocation add D1 with D2 -100".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add Master with D5 100".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint colocation add {const.PCMK_ROLE_PROMOTED} M1-master with {const.PCMK_ROLE_PROMOTED} M2-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add M3-master with M4-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        role = str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint colocation add {role} M5-master with started M6-master 500".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            f"Deprecation Warning: Role value '{role}' is deprecated and "
            f"should not be used, use '{const.PCMK_ROLE_UNPROMOTED}' instead\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint colocation add M7-master with {const.PCMK_ROLE_PROMOTED} M8-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint colocation add {const.PCMK_ROLE_UNPROMOTED} M9-master with M10-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        ac(
            stdout,
            outdent(
                f"""\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
              D1 with D3-clone (score:INFINITY)
              D1 with D2 (score:100)
              D1 with D2 (score:-100)
              Master with D5 (score:100)
              M1-master with M2-master (score:INFINITY) (rsc-role:{const.PCMK_ROLE_PROMOTED_PRIMARY}) (with-rsc-role:{const.PCMK_ROLE_PROMOTED_PRIMARY})
              M3-master with M4-master (score:INFINITY)
              M5-master with M6-master (score:500) (rsc-role:{const.PCMK_ROLE_UNPROMOTED_PRIMARY}) (with-rsc-role:Started)
              M7-master with M8-master (score:INFINITY) (rsc-role:Started) (with-rsc-role:{const.PCMK_ROLE_PROMOTED_PRIMARY})
              M9-master with M10-master (score:INFINITY) (rsc-role:{const.PCMK_ROLE_UNPROMOTED_PRIMARY}) (with-rsc-role:Started)
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation delete M1-master M2-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation remove M5-master M6-master".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        ac(
            stdout,
            outdent(
                f"""\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
              D1 with D3-clone (score:INFINITY)
              D1 with D2 (score:100)
              D1 with D2 (score:-100)
              Master with D5 (score:100)
              M3-master with M4-master (score:INFINITY)
              M7-master with M8-master (score:INFINITY) (rsc-role:Started) (with-rsc-role:{const.PCMK_ROLE_PROMOTED_PRIMARY})
              M9-master with M10-master (score:INFINITY) (rsc-role:{const.PCMK_ROLE_UNPROMOTED_PRIMARY}) (with-rsc-role:Started)
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_colocation_syntax_errors(self):
        def assert_usage(command):
            stdout, stderr, retval = pcs(self.temp_cib.name, command)
            self.assertTrue(
                stderr.startswith(
                    "\nUsage: pcs constraint [constraints]...\n    colocation add"
                ),
                stderr,
            )
            self.assertEqual(stdout, "")
            self.assertEqual(retval, 1)

        role = str(const.PCMK_ROLE_PROMOTED).lower()

        assert_usage("constraint colocation add D1".split())
        assert_usage(f"constraint colocation add {role} D1".split())
        assert_usage("constraint colocation add D1 with".split())
        assert_usage(f"constraint colocation add {role} D1 with".split())

        assert_usage("constraint colocation add D1 D2".split())
        assert_usage(f"constraint colocation add {role} D1 D2".split())
        assert_usage(f"constraint colocation add D1 {role} D2".split())
        assert_usage(f"constraint colocation add {role} D1 {role} D2".split())

        assert_usage("constraint colocation add D1 D2 D3".split())

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        self.assertEqual(
            stdout,
            outdent(
                """\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_colocation_errors(self):
        self.fixture_resources()

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D20".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: Resource 'D20' does not exist\n")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D10 with D20".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: Resource 'D10' does not exist\n")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        self.assertEqual(
            stdout,
            outdent(
                """\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_colocation_with_score_and_options(self):
        self.fixture_resources()

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "-- constraint colocation add D1 with D2 -100 id=abcd node-attribute=y".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        self.assertEqual(
            stdout,
            outdent(
                """\
            Location Constraints:
            Ordering Constraints:
            Colocation Constraints:
              D1 with D2 (score:-100) (node-attribute:y)
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_colocation_invalid_role(self):
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add abc D1 with D2".split(),
        )
        ac(
            stderr,
            "Error: invalid role value 'abc', allowed values are: {}\n".format(
                format_list(const.PCMK_ROLES)
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with def D2".split(),
        )
        ac(
            stderr,
            "Error: invalid role value 'def', allowed values are: {}\n".format(
                format_list(const.PCMK_ROLES)
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add abc D1 with def D2".split(),
        )
        ac(
            stderr,
            "Error: invalid role value 'abc', allowed values are: {}\n".format(
                format_list(const.PCMK_ROLES)
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def test_colocation_too_many_resources(self):
        msg = (
            "Error: Multiple 'with's cannot be specified.\n"
            "Hint: Use the 'pcs constraint colocation set' command if you want "
            "to create a constraint for more than two resources.\n"
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 with D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add master D1 with D2 with D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with master D2 with D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 with master D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add master D1 with master D2 with D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add master D1 with D2 with master D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with master D2 with master D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add master D1 with master D2 with master D3".split(),
        )
        self.assertIn(msg, stderr)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def test_colocation_options_empty_value(self):
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 option1=".split(),
        )
        self.assertEqual(stdout, "")
        self.assertIn("value of 'option1' option is empty", stderr)
        self.assertEqual(retval, 1)

    # see also BundleColocation
    def testColocationSets(self):
        self.fixture_resources()
        line = "resource create D7 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        line = "resource create D8 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        line = "resource create D9 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation set".split()
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D7 D8 set".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D7 D8 set set D8 D9".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set setoptions score=100".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint colocation "
                "set D5 D6 D7 sequential=false require-all=true "
                "set D8 D9 sequential=true require-all=false action=start role=Stopped "
                "setoptions score=INFINITY"
            ).split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation set D5 D6".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint colocation "
                f"set D5 D6 action=stop role=Started set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} "
                f"set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY}"
            ).split(),
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation --full".split()
        )
        ac(
            stdout,
            f"""\
Colocation Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:colocation_set_D5D6D7_set) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:colocation_set_D5D6D7_set-1) setoptions score=INFINITY (id:colocation_set_D5D6D7)
    set D5 D6 (id:colocation_set_D5D6_set) setoptions score=INFINITY (id:colocation_set_D5D6)
    set D5 D6 action=stop role=Started (id:colocation_set_D5D6D7-1_set) set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} (id:colocation_set_D5D6D7-1_set-1) set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY} (id:colocation_set_D5D6D7-1_set-2) setoptions score=INFINITY (id:colocation_set_D5D6D7-1)
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint delete colocation_set_D5D6".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation --full".split()
        )
        ac(
            stdout,
            f"""\
Colocation Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:colocation_set_D5D6D7_set) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:colocation_set_D5D6D7_set-1) setoptions score=INFINITY (id:colocation_set_D5D6D7)
    set D5 D6 action=stop role=Started (id:colocation_set_D5D6D7-1_set) set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} (id:colocation_set_D5D6D7-1_set-1) set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY} (id:colocation_set_D5D6D7-1_set-2) setoptions score=INFINITY (id:colocation_set_D5D6D7-1)
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete D5".split()
        )
        ac(
            stderr,
            outdent(
                """\
            Removing D5 from set colocation_set_D5D6D7_set
            Removing D5 from set colocation_set_D5D6D7-1_set
            Deleting Resource - D5
            """
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete D6".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            outdent(
                """\
            Removing D6 from set colocation_set_D5D6D7_set
            Removing D6 from set colocation_set_D5D6D7-1_set
            Removing set colocation_set_D5D6D7-1_set
            Deleting Resource - D6
            """
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint ref D7".split()
        )
        ac(
            stdout,
            outdent(
                """\
            Resource: D7
              colocation_set_D5D6D7
              colocation_set_D5D6D7-1
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint ref D8".split()
        )
        ac(
            stdout,
            outdent(
                """\
            Resource: D8
              colocation_set_D5D6D7
              colocation_set_D5D6D7-1
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 sequential=foo".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid sequential value, use 'false', 'true'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 require-all=foo".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid require-all value, use 'false', 'true'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 role=foo".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid role value, use {}\n"
                + ERRORS_HAVE_OCCURRED
            ).format(format_list(const.PCMK_ROLES)),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 action=foo".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid action value, use 'demote', 'promote', 'start', 'stop'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 foo=bar".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Error: invalid set option 'foo', allowed options are: 'action', 'require-all', 'role', 'sequential'\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 setoptions foo=bar".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid option 'foo', allowed options are: 'id', 'score'\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 setoptions score=foo".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid score 'foo', use integer or INFINITY or -INFINITY\n",
        )
        self.assertEqual(retval, 1)

    def testConstraintResourceDiscoveryRules(self):
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create crd ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create crd1 ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location crd rule resource-discovery=exclusive "
                "score=-INFINITY opsrole ne controller0 and opsrole ne controller1"
            ).split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location crd1 rule resource-discovery=exclusive "
                "score=-INFINITY opsrole2 ne controller2"
            ).split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            "\n".join(
                [
                    "Location Constraints:",
                    "  Resource: crd",
                    "    Constraint: location-crd (resource-discovery=exclusive)",
                    "      Rule: boolean-op=and score=-INFINITY (id:location-crd-rule)",
                    "        Expression: opsrole ne controller0 (id:location-crd-rule-expr)",
                    "        Expression: opsrole ne controller1 (id:location-crd-rule-expr-1)",
                    "  Resource: crd1",
                    "    Constraint: location-crd1 (resource-discovery=exclusive)",
                    "      Rule: score=-INFINITY (id:location-crd1-rule)",
                    "        Expression: opsrole2 ne controller2 (id:location-crd1-rule-expr)",
                    "Ordering Constraints:",
                    "Colocation Constraints:",
                    "Ticket Constraints:",
                ]
            )
            + "\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testConstraintResourceDiscovery(self):
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create crd ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create crd1 ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "-- constraint location add my_constraint_id crd my_node -INFINITY resource-discovery=always".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "-- constraint location add my_constraint_id2 crd1 my_node -INFINITY resource-discovery=never".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: crd
                Disabled on:
                  Node: my_node (score:-INFINITY) (resource-discovery=always) (id:my_constraint_id)
              Resource: crd1
                Disabled on:
                  Node: my_node (score:-INFINITY) (resource-discovery=never) (id:my_constraint_id2)
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "-- constraint location add my_constraint_id3 crd1 my_node2 -INFINITY bad-opt=test".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Error: bad option 'bad-opt', use --force to override\n"
        )
        self.assertEqual(retval, 1)

    def testOrderSetsRemoval(self):
        for i in range(9):
            stdout, stderr, retval = pcs(
                self.temp_cib.name,
                f"resource create T{i} ocf:heartbeat:Dummy".split(),
            )
            self.assertEqual(stdout, "")
            self.assertEqual(stderr, "")
            self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set T0 T1 T2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set T2 T3".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order remove T1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order remove T1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Error: No matching resources found in ordering list\n"
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order delete T1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Error: No matching resources found in ordering list\n"
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order".split()
        )
        ac(
            stdout,
            "Ordering Constraints:\n  Resource Sets:\n    set T0 T2\n    set T2 T3\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order delete T2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order".split()
        )
        ac(
            stdout,
            "Ordering Constraints:\n  Resource Sets:\n    set T0\n    set T3\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order delete T0".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order".split()
        )
        ac(stdout, "Ordering Constraints:\n  Resource Sets:\n    set T3\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order remove T3".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order".split()
        )
        ac(stdout, "Ordering Constraints:\n")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    # see also BundleOrder
    def testOrderSets(self):
        self.fixture_resources()
        line = "resource create D7 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        line = "resource create D8 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        line = "resource create D9 ocf:heartbeat:Dummy".split()
        stdout, stderr, retval = pcs(self.temp_cib.name, line)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set".split()
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D7 D8 set".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D7 D8 set set D8 D9".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set setoptions score=100".split(),
        )
        self.assertEqual(stdout, "")
        self.assertTrue(stderr.startswith("\nUsage: pcs constraint"), stderr)
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint order "
                "set D5 D6 D7 sequential=false require-all=true "
                "set D8 D9 sequential=true require-all=false action=start role=Stopped"
            ).split(),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set D5 D6".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint order "
                "set D5 D6 action=stop role=Started "
                f"set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_LEGACY} "
                f"set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED}"
            ).split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                f"Deprecation Warning: Value "
                f"'{const.PCMK_ROLE_UNPROMOTED_LEGACY}' of option "
                "role is deprecated and should not be used, use "
                f"'{const.PCMK_ROLE_UNPROMOTED}' value instead\n"
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order --full".split()
        )
        self.assertEqual(retval, 0)
        ac(
            stdout,
            f"""\
Ordering Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:order_set_D5D6D7_set) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:order_set_D5D6D7_set-1) (id:order_set_D5D6D7)
    set D5 D6 (id:order_set_D5D6_set) (id:order_set_D5D6)
    set D5 D6 action=stop role=Started (id:order_set_D5D6D7-1_set) set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-1) set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-2) (id:order_set_D5D6D7-1)
""",
        )
        self.assertEqual(stderr, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint remove order_set_D5D6".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order --full".split()
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        ac(
            stdout,
            f"""\
Ordering Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:order_set_D5D6D7_set) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:order_set_D5D6D7_set-1) (id:order_set_D5D6D7)
    set D5 D6 action=stop role=Started (id:order_set_D5D6D7-1_set) set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-1) set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-2) (id:order_set_D5D6D7-1)
""",
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete D5".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            outdent(
                """\
            Removing D5 from set order_set_D5D6D7_set
            Removing D5 from set order_set_D5D6D7-1_set
            Deleting Resource - D5
            """
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete D6".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            outdent(
                """\
            Removing D6 from set order_set_D5D6D7_set
            Removing D6 from set order_set_D5D6D7-1_set
            Removing set order_set_D5D6D7-1_set
            Deleting Resource - D6
            """
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 sequential=foo".split(),
        )
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid sequential value, use 'false', 'true'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 require-all=foo".split(),
        )
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid require-all value, use 'false', 'true'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 role=foo".split(),
        )
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid role value, use {}\n"
                + ERRORS_HAVE_OCCURRED
            ).format(format_list(const.PCMK_ROLES)),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 action=foo".split(),
        )
        ac(
            stderr,
            (
                "Error: 'foo' is not a valid action value, use 'demote', 'promote', 'start', 'stop'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 foo=bar".split(),
        )
        ac(
            stderr,
            (
                "Error: invalid set option 'foo', allowed options are: 'action', 'require-all', 'role', 'sequential'\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions foo=bar".split(),
        )
        ac(
            stderr,
            """\
Error: invalid option 'foo', allowed options are: 'id', 'kind', 'symmetrical'
""",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions kind=foo".split(),
        )
        ac(
            stderr,
            "Error: 'foo' is not a valid kind value, use 'Mandatory', 'Optional', 'Serialize'\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions symmetrical=foo".split(),
        )
        ac(
            stderr,
            "Error: 'foo' is not a valid symmetrical value, use 'false', 'true'\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions symmetrical=false kind=mandatory".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            f"""\
Location Constraints:
Ordering Constraints:
  Resource Sets:
    set D7 require-all=true sequential=false (id:order_set_D5D6D7_set) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:order_set_D5D6D7_set-1) (id:order_set_D5D6D7)
    set D7 D8 action=promote role={const.PCMK_ROLE_UNPROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-1) set D8 D9 action=demote role={const.PCMK_ROLE_PROMOTED_PRIMARY} (id:order_set_D5D6D7-1_set-2) (id:order_set_D5D6D7-1)
    set D1 D2 (id:order_set_D1D2_set) setoptions kind=Mandatory symmetrical=false (id:order_set_D1D2)
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testLocationConstraintRule(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers rh7-1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 prefers rh7-2".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D2-rh7-2-INFINITY date-spec hours=9-16 weekdays=1-5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: location-D1-rh7-1-INFINITY
      Rule: score=INFINITY (id:location-D1-rh7-1-INFINITY-rule)
        Expression: #uname eq rh7-1 (id:location-D1-rh7-1-INFINITY-rule-expr)
      Rule: score=INFINITY (id:location-D1-rh7-1-INFINITY-rule-1)
        Expression: #uname eq rh7-1 (id:location-D1-rh7-1-INFINITY-rule-1-expr)
      Rule: score=INFINITY (id:location-D1-rh7-1-INFINITY-rule-2)
        Expression: #uname eq rh7-1 (id:location-D1-rh7-1-INFINITY-rule-2-expr)
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY (id:location-D2-rh7-2-INFINITY-rule)
        Expression: (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5 (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule remove location-D1-rh7-1-INFINITY-rule-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Removing Rule: location-D1-rh7-1-INFINITY-rule-1\n"
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule remove location-D1-rh7-1-INFINITY-rule-2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Removing Rule: location-D1-rh7-1-INFINITY-rule-2\n"
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: location-D1-rh7-1-INFINITY
      Rule: score=INFINITY (id:location-D1-rh7-1-INFINITY-rule)
        Expression: #uname eq rh7-1 (id:location-D1-rh7-1-INFINITY-rule-expr)
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY (id:location-D2-rh7-2-INFINITY-rule)
        Expression: (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5 (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule delete location-D1-rh7-1-INFINITY-rule".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr, "Removing Constraint: location-D1-rh7-1-INFINITY\n"
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        self.assertEqual(retval, 0)
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY (id:location-D2-rh7-2-INFINITY-rule)
        Expression: (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5 (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint location D1 rule role={const.PCMK_ROLE_PROMOTED}".split(),
        )
        self.assertEqual(stderr, "Error: no rule expression was specified\n")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint location non-existent-resource rule role={const.PCMK_ROLE_PROMOTED} #uname eq rh7-1".split(),
        )
        self.assertEqual(
            stderr, "Error: Resource 'non-existent-resource' does not exist\n"
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-2".split(),
        )
        ac(
            stderr,
            "Error: Unable to find constraint: location-D1-rh7-1-INFINITY\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint rule add location-D2-rh7-2-INFINITY id=123 #uname eq rh7-2".split(),
        )
        ac(
            stderr,
            "Error: invalid rule id '123', '1' is not a valid first character for a rule id\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def testLocationBadRules(self):
        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("stateful0"))

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            (
                "constraint location stateful0 rule role={role} #uname eq "
                "rh7-1 --force"
            )
            .format(role=str(const.PCMK_ROLE_PROMOTED).lower())
            .split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            f"""\
Location Constraints:
  Resource: stateful0
    Constraint: location-stateful0
      Rule: role={const.PCMK_ROLE_PROMOTED_PRIMARY} score=INFINITY (id:location-stateful0-rule)
        Expression: #uname eq rh7-1 (id:location-stateful0-rule-expr)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("stateful1"))

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location stateful1 rule rulename #uname eq rh7-1 --force".split(),
        )
        ac(
            stderr,
            "Error: 'rulename #uname eq rh7-1' is not a valid rule expression: unexpected '#uname'\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint location stateful1 rule role={const.PCMK_ROLE_PROMOTED} rulename #uname eq rh7-1 --force".split(),
        )
        ac(
            stderr,
            "Error: 'rulename #uname eq rh7-1' is not a valid rule expression: unexpected '#uname'\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            f"constraint location stateful1 rule role={const.PCMK_ROLE_PROMOTED} 25 --force".split(),
        )
        ac(
            stderr,
            "Error: '25' is not a valid rule expression: missing one of 'eq', 'ne', 'lt', 'gt', 'lte', 'gte', 'in_range', 'defined', 'not_defined', 'date-spec'\n",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

    def testMasterSlaveConstraint(self):
        cibadmin = os.path.join(settings.pacemaker_binaries, "cibadmin")
        os.system(
            "CIB_file="
            + self.temp_cib.name
            + f' {cibadmin} -R --scope nodes --xml-text \'<nodes><node id="1" uname="rh7-1"/><node id="2" uname="rh7-2"/></nodes>\''
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create dummy1 ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("stateful1"))

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create stateful2 ocf:pacemaker:Stateful --group statefulG".split(),
            mock_settings=get_mock_settings("crm_resource_binary"),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Warning: changing a monitor operation interval from 10s to 11 to make the operation unique\n",
        )
        self.assertEqual(retval, 0)

        # pcs no longer allows turning resources into masters but supports
        # existing ones. In order to test it, we need to put a master in the
        # CIB without pcs.
        wrap_element_by_master(self.temp_cib, "statefulG")

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location stateful1 prefers rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            LOCATION_NODE_VALIDATION_SKIP_WARNING
            + "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location statefulG prefers rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            LOCATION_NODE_VALIDATION_SKIP_WARNING
            + "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location stateful1 rule #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location statefulG rule #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stateful1 then dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order dummy1 then statefulG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set stateful1 dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set dummy1 statefulG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add stateful1 with dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add dummy1 with statefulG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set dummy1 stateful1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set statefulG dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: statefulG is a clone resource, you should use the clone id: statefulG-master when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location stateful1 prefers rh7-1 --force".split(),
        )
        ac(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location statefulG rule #uname eq rh7-1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stateful1 then dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding stateful1 dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set stateful1 dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Warning: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add stateful1 with dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set stateful1 dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Warning: stateful1 is a clone resource, you should use the clone id: stateful1-master when adding constraints\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: stateful1
    Enabled on:
      Node: rh7-1 (score:INFINITY) (id:location-stateful1-rh7-1-INFINITY)
  Resource: statefulG
    Constraint: location-statefulG
      Rule: score=INFINITY (id:location-statefulG-rule)
        Expression: #uname eq rh7-1 (id:location-statefulG-rule-expr)
Ordering Constraints:
  start stateful1 then start dummy1 (kind:Mandatory) (id:order-stateful1-dummy1-mandatory)
  Resource Sets:
    set stateful1 dummy1 (id:order_set_s1d1_set) (id:order_set_s1d1)
Colocation Constraints:
  stateful1 with dummy1 (score:INFINITY) (id:colocation-stateful1-dummy1-INFINITY)
  Resource Sets:
    set stateful1 dummy1 (id:colocation_set_s1d1_set) setoptions score=INFINITY (id:colocation_set_s1d1)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testCloneConstraint(self):
        cibadmin = os.path.join(settings.pacemaker_binaries, "cibadmin")
        os.system(
            "CIB_file="
            + self.temp_cib.name
            + f' {cibadmin} -R --scope nodes --xml-text \'<nodes><node id="1" uname="rh7-1"/><node id="2" uname="rh7-2"/></nodes>\''
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create dummy1 ocf:heartbeat:Dummy".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create dummy ocf:heartbeat:Dummy clone".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "resource create dummy2 ocf:heartbeat:Dummy --group dummyG".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource clone dummyG".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummy prefers rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            LOCATION_NODE_VALIDATION_SKIP_WARNING
            + "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummyG prefers rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            LOCATION_NODE_VALIDATION_SKIP_WARNING
            + "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummy rule #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummyG rule #uname eq rh7-1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order dummy then dummy1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order dummy1 then dummyG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set dummy1 dummy".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set dummyG dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add dummy with dummy1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add dummy1 with dummyG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set dummy1 dummy".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set dummy1 dummyG".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints, use --force to override\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummy prefers rh7-1 --force".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummyG rule #uname eq rh7-1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order dummy then dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding dummy dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set dummy1 dummy --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Warning: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add dummy with dummy1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set dummy1 dummy --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Warning: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: dummy
    Enabled on:
      Node: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
  Resource: dummyG
    Constraint: location-dummyG
      Rule: score=INFINITY (id:location-dummyG-rule)
        Expression: #uname eq rh7-1 (id:location-dummyG-rule-expr)
Ordering Constraints:
  start dummy then start dummy1 (kind:Mandatory) (id:order-dummy-dummy1-mandatory)
  Resource Sets:
    set dummy1 dummy (id:order_set_d1dy_set) (id:order_set_d1dy)
Colocation Constraints:
  dummy with dummy1 (score:INFINITY) (id:colocation-dummy-dummy1-INFINITY)
  Resource Sets:
    set dummy1 dummy (id:colocation_set_d1dy_set) setoptions score=INFINITY (id:colocation_set_d1dy)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testMissingRole(self):
        cibadmin = os.path.join(settings.pacemaker_binaries, "cibadmin")
        os.system(
            "CIB_file="
            + self.temp_cib.name
            + f' {cibadmin} -R --scope nodes --xml-text \'<nodes><node id="1" uname="rh7-1"/><node id="2" uname="rh7-2"/></nodes>\''
        )

        # pcs no longer allows creating masters but supports existing ones. In
        # order to test it, we need to put a master in the CIB without pcs.
        fixture_to_cib(self.temp_cib.name, fixture_master_xml("stateful0"))

        os.system(
            "CIB_file="
            + self.temp_cib.name
            + f' {cibadmin} -R --scope constraints --xml-text \'<constraints><rsc_location id="cli-prefer-stateful0-master" role="Master" rsc="stateful0-master" node="rh7-1" score="INFINITY"/><rsc_location id="cli-ban-stateful0-master-on-rh7-1" rsc="stateful0-master" role="Slave" node="rh7-1" score="-INFINITY"/></constraints>\''
        )

        stdout, stderr, retval = pcs(self.temp_cib.name, ["constraint"])
        ac(
            stdout,
            outdent(
                f"""\
            Location Constraints:
              Resource: stateful0-master
                Enabled on:
                  Node: rh7-1 (score:INFINITY) (role:{const.PCMK_ROLE_PROMOTED_PRIMARY})
                Disabled on:
                  Node: rh7-1 (score:-INFINITY) (role:{const.PCMK_ROLE_UNPROMOTED_PRIMARY})
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testManyConstraints(self):
        write_file_to_tmpfile(large_cib, self.temp_cib)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummy prefers rh7-1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location config resources dummy --full".split(),
        )
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: dummy
                Enabled on:
                  Node: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location remove location-dummy-rh7-1-INFINITY".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add dummy1 with dummy2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation remove dummy1 dummy2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order dummy1 then dummy2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding dummy1 dummy2 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order remove dummy1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location dummy prefers rh7-1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location config resources dummy --full".split(),
        )
        ac(
            stdout,
            outdent(
                """\
            Location Constraints:
              Resource: dummy
                Enabled on:
                  Node: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
            """
            ),
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint remove location-dummy-rh7-1-INFINITY".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testConstraintResourceCloneUpdate(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers rh7-1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order D1 then D5".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order D6 then D1".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D6 D1 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        self.assertEqual(retval, 0)
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource clone D1".split()
        )
        self.assertEqual(stderr, "")
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1-clone
    Enabled on:
      Node: rh7-1 (score:INFINITY) (id:location-D1-rh7-1-INFINITY)
Ordering Constraints:
  start D1-clone then start D5 (kind:Mandatory) (id:order-D1-D5-mandatory)
  start D6 then start D1-clone (kind:Mandatory) (id:order-D6-D1-mandatory)
Colocation Constraints:
  D1-clone with D5 (score:INFINITY) (id:colocation-D1-D5-INFINITY)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testConstraintGroupCloneUpdate(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource group add DG D1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location DG prefers rh7-1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add DG with D5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order DG then D5".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding DG D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order D6 then DG".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D6 DG (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        self.assertEqual(retval, 0)
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource clone DG".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: DG-clone
    Enabled on:
      Node: rh7-1 (score:INFINITY) (id:location-DG-rh7-1-INFINITY)
Ordering Constraints:
  start DG-clone then start D5 (kind:Mandatory) (id:order-DG-D5-mandatory)
  start D6 then start DG-clone (kind:Mandatory) (id:order-D6-DG-mandatory)
Colocation Constraints:
  DG-clone with D5 (score:INFINITY) (id:colocation-DG-D5-INFINITY)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testRemoteNodeConstraintsRemove(self):
        self.temp_corosync_conf = get_tmp_file("tier1_test_constraints")
        write_file_to_tmpfile(rc("corosync.conf"), self.temp_corosync_conf)
        self.fixture_resources()
        # constraints referencing the remote node's name,
        # deleting the remote node resource
        self.assert_pcs_success(
            (
                "resource create vm-guest1 ocf:heartbeat:VirtualDomain "
                "hypervisor=qemu:///system config=/root/guest1.xml "
                "meta remote-node=guest1 --force"
            ).split(),
            stdout_full="",
            stderr_start=(
                "Warning: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest'\n",
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers node1=100".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers guest1=200".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 avoids node2=300".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 avoids guest1=400".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Enabled on:
      Node: node1 (score:100) (id:location-D1-node1-100)
      Node: guest1 (score:200) (id:location-D1-guest1-200)
  Resource: D2
    Disabled on:
      Node: node2 (score:-300) (id:location-D2-node2--300)
      Node: guest1 (score:-400) (id:location-D2-guest1--400)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete vm-guest1".split()
        )
        self.assertEqual(
            stderr,
            outdent(
                """\
            Removing Constraint - location-D1-guest1-200
            Removing Constraint - location-D2-guest1--400
            Deleting Resource - vm-guest1
            """
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Enabled on:
      Node: node1 (score:100) (id:location-D1-node1-100)
  Resource: D2
    Disabled on:
      Node: node2 (score:-300) (id:location-D2-node2--300)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")

        # constraints referencing the remote node's name,
        # removing the remote node
        self.assert_pcs_success(
            (
                "resource create vm-guest1 ocf:heartbeat:VirtualDomain "
                "hypervisor=qemu:///system config=/root/guest1.xml "
                "meta remote-node=guest1 --force"
            ).split(),
            stdout_full="",
            stderr_start=(
                "Warning: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest'\n",
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 prefers guest1=200".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 avoids guest1=400".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Enabled on:
      Node: node1 (score:100) (id:location-D1-node1-100)
      Node: guest1 (score:200) (id:location-D1-guest1-200)
  Resource: D2
    Disabled on:
      Node: node2 (score:-300) (id:location-D2-node2--300)
      Node: guest1 (score:-400) (id:location-D2-guest1--400)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "cluster node remove-guest guest1".split(),
            corosync_conf_opt=self.temp_corosync_conf.name,
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            outdent(
                """\
            Running action(s) 'pacemaker_remote disable', 'pacemaker_remote stop' on 'guest1' was skipped because the command does not run on a live cluster (e.g. -f was used). Please, run the action(s) manually.
            Removing 'pacemaker authkey' from 'guest1' was skipped because the command does not run on a live cluster (e.g. -f was used). Please, remove the file(s) manually.
            """
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Enabled on:
      Node: node1 (score:100) (id:location-D1-node1-100)
      Node: guest1 (score:200) (id:location-D1-guest1-200)
  Resource: D2
    Disabled on:
      Node: node2 (score:-300) (id:location-D2-node2--300)
      Node: guest1 (score:-400) (id:location-D2-guest1--400)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete vm-guest1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Deleting Resource - vm-guest1\n")
        self.assertEqual(retval, 0)

        # constraints referencing the remote node resource
        # deleting the remote node resource
        self.assert_pcs_success(
            (
                "resource create vm-guest1 ocf:heartbeat:VirtualDomain "
                "hypervisor=qemu:///system config=/root/guest1.xml "
                "meta remote-node=guest1 --force"
            ).split(),
            stdout_full="",
            stderr_start=(
                "Warning: this command is not sufficient for creating a guest "
                "node, use 'pcs cluster node add-guest'\n",
            ),
        )

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location vm-guest1 prefers node1".split(),
        )
        self.assertEqual(stderr, LOCATION_NODE_VALIDATION_SKIP_WARNING)
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "resource delete vm-guest1".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            outdent(
                """\
            Removing Constraint - location-vm-guest1-node1-INFINITY
            Removing Constraint - location-D1-guest1-200
            Removing Constraint - location-D2-guest1--400
            Deleting Resource - vm-guest1
            """
            ),
        )
        self.assertEqual(retval, 0)

    def testDuplicateOrder(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order D1 then D2".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order D1 then D2".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then start D2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory)
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-1)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D1 then start D2 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D2 then start D5".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D2 D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D2 then start D5".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  start D2 then start D5 (kind:Mandatory) (id:order-D2-D5-mandatory)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order start D2 then start D5 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D2 D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stop D5 then stop D6".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D5 D6 (kind: Mandatory) (Options: first-action=stop then-action=stop)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stop D5 then stop D6".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  stop D5 then stop D6 (kind:Mandatory) (id:order-D5-D6-mandatory)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order stop D5 then stop D6 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D5 D6 (kind: Mandatory) (Options: first-action=stop then-action=stop)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
Ordering Constraints:
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory)
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-1)
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-2)
  start D2 then start D5 (kind:Mandatory) (id:order-D2-D5-mandatory)
  start D2 then start D5 (kind:Mandatory) (id:order-D2-D5-mandatory-1)
  stop D5 then stop D6 (kind:Mandatory) (id:order-D5-D6-mandatory)
  stop D5 then stop D6 (kind:Mandatory) (id:order-D5-D6-mandatory-1)
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testDuplicateColocation(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2".split(),
        )
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
""",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 50".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 50 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add started D1 with started D2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
  D1 with D2 (score:50) (id:colocation-D1-D2-50)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add started D1 with started D2 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add started D2 with started D5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add stopped D2 with stopped D5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add stopped D2 with stopped D5".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  D2 with D5 (score:INFINITY) (rsc-role:Stopped) (with-rsc-role:Stopped) (id:colocation-D2-D5-INFINITY-1)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add stopped D2 with stopped D5 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
  D1 with D2 (score:50) (id:colocation-D1-D2-50)
  D1 with D2 (score:INFINITY) (rsc-role:Started) (with-rsc-role:Started) (id:colocation-D1-D2-INFINITY-1)
  D2 with D5 (score:INFINITY) (rsc-role:Started) (with-rsc-role:Started) (id:colocation-D2-D5-INFINITY)
  D2 with D5 (score:INFINITY) (rsc-role:Stopped) (with-rsc-role:Stopped) (id:colocation-D2-D5-INFINITY-1)
  D2 with D5 (score:INFINITY) (rsc-role:Stopped) (with-rsc-role:Stopped) (id:colocation-D2-D5-INFINITY-2)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")

    def testDuplicateSetConstraints(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set D1 D2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set D1 D2".split()
        )
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:order_set_D1D2_set) (id:order_set_D1D2)\n"
                "Error: duplicate constraint already exists, use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 --force".split(),
        )
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:order_set_D1D2_set) (id:order_set_D1D2)\n"
                "Warning: duplicate constraint already exists\n"
            ),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 set D5 D6".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 set D5 D6".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:order_set_D1D2D5_set) set D5 D6 (id:order_set_D1D2D5_set-1) (id:order_set_D1D2D5)\n"
                "Error: duplicate constraint already exists, use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 set D5 D6 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:order_set_D1D2D5_set) set D5 D6 (id:order_set_D1D2D5_set-1) (id:order_set_D1D2D5)\n"
                "Warning: duplicate constraint already exists\n"
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation set D1 D2".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation set D1 D2".split()
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:colocation_set_D1D2_set) setoptions score=INFINITY (id:colocation_set_D1D2)\n"
                "Error: duplicate constraint already exists, use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:colocation_set_D1D2_set) setoptions score=INFINITY (id:colocation_set_D1D2)\n"
                "Warning: duplicate constraint already exists\n"
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 set D5 D6".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 set D5 D6".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:colocation_set_D1D2D5_set) set D5 D6 (id:colocation_set_D1D2D5_set-1) setoptions score=INFINITY (id:colocation_set_D1D2D5)\n"
                "Error: duplicate constraint already exists, use --force to "
                "override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 set D5 D6 --force".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            (
                "Duplicate constraints:\n"
                "  set D1 D2 (id:colocation_set_D1D2D5_set) set D5 D6 (id:colocation_set_D1D2D5_set-1) setoptions score=INFINITY (id:colocation_set_D1D2D5)\n"
                "Warning: duplicate constraint already exists\n"
            ),
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint colocation set D6 D1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint order set D6 D1".split()
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
Ordering Constraints:
  Resource Sets:
    set D1 D2 (id:order_set_D1D2_set) (id:order_set_D1D2)
    set D1 D2 (id:order_set_D1D2-1_set) (id:order_set_D1D2-1)
    set D1 D2 (id:order_set_D1D2D5_set) set D5 D6 (id:order_set_D1D2D5_set-1) (id:order_set_D1D2D5)
    set D1 D2 (id:order_set_D1D2D5-1_set) set D5 D6 (id:order_set_D1D2D5-1_set-1) (id:order_set_D1D2D5-1)
    set D6 D1 (id:order_set_D6D1_set) (id:order_set_D6D1)
Colocation Constraints:
  Resource Sets:
    set D1 D2 (id:colocation_set_D1D2_set) setoptions score=INFINITY (id:colocation_set_D1D2)
    set D1 D2 (id:colocation_set_D1D2-1_set) setoptions score=INFINITY (id:colocation_set_D1D2-1)
    set D1 D2 (id:colocation_set_D1D2D5_set) set D5 D6 (id:colocation_set_D1D2D5_set-1) setoptions score=INFINITY (id:colocation_set_D1D2D5)
    set D1 D2 (id:colocation_set_D1D2D5-1_set) set D5 D6 (id:colocation_set_D1D2D5-1_set-1) setoptions score=INFINITY (id:colocation_set_D1D2D5-1)
    set D6 D1 (id:colocation_set_D6D1_set) setoptions score=INFINITY (id:colocation_set_D6D1)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")

    def testDuplicateLocationRules(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule #uname eq node1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule #uname eq node1".split(),
        )
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D1
    Rule: score=INFINITY (id:location-D1-rule)
      Expression: #uname eq node1 (id:location-D1-rule-expr)
""",
        )
        self.assertEqual(stdout, "")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule #uname eq node1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule #uname eq node1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule #uname eq node1 or #uname eq node2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule #uname eq node1 or #uname eq node2".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D2-1
    Rule: boolean-op=or score=INFINITY (id:location-D2-1-rule)
      Expression: #uname eq node1 (id:location-D2-1-rule-expr)
      Expression: #uname eq node2 (id:location-D2-1-rule-expr-1)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule #uname eq node2 or #uname eq node1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D2-1
    Rule: boolean-op=or score=INFINITY (id:location-D2-1-rule)
      Expression: #uname eq node1 (id:location-D2-1-rule-expr)
      Expression: #uname eq node2 (id:location-D2-1-rule-expr-1)
""",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule #uname eq node2 or #uname eq node1 --force".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: score=INFINITY (id:location-D1-rule)
        Expression: #uname eq node1 (id:location-D1-rule-expr)
    Constraint: location-D1-1
      Rule: score=INFINITY (id:location-D1-1-rule)
        Expression: #uname eq node1 (id:location-D1-1-rule-expr)
  Resource: D2
    Constraint: location-D2
      Rule: score=INFINITY (id:location-D2-rule)
        Expression: #uname eq node1 (id:location-D2-rule-expr)
    Constraint: location-D2-1
      Rule: boolean-op=or score=INFINITY (id:location-D2-1-rule)
        Expression: #uname eq node1 (id:location-D2-1-rule-expr)
        Expression: #uname eq node2 (id:location-D2-1-rule-expr-1)
    Constraint: location-D2-2
      Rule: boolean-op=or score=INFINITY (id:location-D2-2-rule)
        Expression: #uname eq node2 (id:location-D2-2-rule-expr)
        Expression: #uname eq node1 (id:location-D2-2-rule-expr-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def testConstraintsCustomId(self):
        self.fixture_resources()
        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 id=1id".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid constraint id '1id', '1' is not a valid first character for a constraint id\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 id=id1".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D1 with D2 id=id1".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: id 'id1' is already in use, please specify another one\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation add D2 with D1 100 id=id2".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 setoptions id=3id".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid constraint id '3id', '3' is not a valid first character for a constraint id\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 setoptions id=id3".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D1 D2 setoptions id=id3".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: 'id3' already exists\n")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint colocation set D2 D1 setoptions score=100 id=id4".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions id=5id".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid constraint id '5id', '5' is not a valid first character for a constraint id\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions id=id5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D1 D2 setoptions id=id5".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "Error: 'id5' already exists\n")
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order set D2 D1 setoptions kind=Mandatory id=id6".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 id=7id".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid constraint id '7id', '7' is not a valid first character for a constraint id\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 id=id7".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D1 D2 (kind: Mandatory) (Options: id=id7 first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D1 then D2 id=id7".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: id 'id7' is already in use, please specify another one\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint order D2 then D1 kind=Optional id=id8".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Adding D2 D1 (kind: Optional) (Options: id=id8 first-action=start then-action=start)\n",
        )
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule constraint-id=9id defined pingd".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: invalid constraint id '9id', '9' is not a valid first character for a constraint id\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule constraint-id=id9 defined pingd".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D1 rule constraint-id=id9 defined pingd".split(),
        )
        self.assertEqual(stdout, "")
        ac(
            stderr,
            "Error: id 'id9' is already in use, please specify another one\n",
        )
        self.assertEqual(retval, 1)

        stdout, stderr, retval = pcs(
            self.temp_cib.name,
            "constraint location D2 rule score=100 constraint-id=id10 id=rule1 defined pingd".split(),
        )
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

        stdout, stderr, retval = pcs(
            self.temp_cib.name, "constraint --full".split()
        )
        ac(
            stdout,
            """\
Location Constraints:
  Resource: D1
    Constraint: id9
      Rule: score=INFINITY (id:id9-rule)
        Expression: defined pingd (id:id9-rule-expr)
  Resource: D2
    Constraint: id10
      Rule: score=100 (id:rule1)
        Expression: defined pingd (id:rule1-expr)
Ordering Constraints:
  start D1 then start D2 (kind:Mandatory) (id:id7)
  start D2 then start D1 (kind:Optional) (id:id8)
  Resource Sets:
    set D1 D2 (id:id5_set) (id:id5)
    set D2 D1 (id:id6_set) setoptions kind=Mandatory (id:id6)
Colocation Constraints:
  D1 with D2 (score:INFINITY) (id:id1)
  D2 with D1 (score:100) (id:id2)
  Resource Sets:
    set D1 D2 (id:id3_set) setoptions score=INFINITY (id:id3)
    set D2 D1 (id:id4_set) setoptions score=100 (id:id4)
Ticket Constraints:
""",
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)


class ConstraintBaseTest(unittest.TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty-3.7.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_constraint")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.assert_pcs_success("resource create A ocf:heartbeat:Dummy".split())
        self.assert_pcs_success("resource create B ocf:heartbeat:Dummy".split())

    def tearDown(self):
        self.temp_cib.close()


class CommonCreateWithSet(ConstraintBaseTest):
    def test_refuse_when_resource_does_not_exist(self):
        self.assert_pcs_fail(
            "constraint ticket set A C setoptions ticket=T".split(),
            ["Error: bundle/clone/group/resource 'C' does not exist"],
        )


class TicketCreateWithSet(ConstraintBaseTest):
    def test_create_ticket(self):
        self.assert_pcs_success(
            "constraint ticket set A B setoptions ticket=T loss-policy=fence".split()
        )

    def test_can_skip_loss_policy(self):
        self.assert_pcs_success(
            "constraint ticket set A B setoptions ticket=T".split()
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            stdout_full=[
                "Ticket Constraints:",
                "  Resource Sets:",
                "    set A B setoptions ticket=T",
            ],
        )

    def test_refuse_bad_loss_policy(self):
        self.assert_pcs_fail(
            "constraint ticket set A B setoptions ticket=T loss-policy=none".split(),
            [
                "Error: 'none' is not a valid loss-policy value, use 'demote', "
                + "'fence', 'freeze', 'stop'",
            ],
        )

    def test_refuse_when_ticket_option_is_missing(self):
        self.assert_pcs_fail(
            "constraint ticket set A B setoptions loss-policy=fence".split(),
            ["Error: required option 'ticket' is missing"],
        )

    def test_refuse_when_option_is_invalid(self):
        self.assert_pcs_fail(
            "constraint ticket set A B setoptions loss-policy".split(),
            "Error: missing value of 'loss-policy' option\n",
        )


class TicketAdd(ConstraintBaseTest):
    def test_create_minimal(self):
        self.assert_pcs_success("constraint ticket add T A".split())
        self.assert_pcs_success(
            "constraint ticket config".split(),
            dedent(
                """\
                Ticket Constraints:
                  A ticket=T
                """
            ),
        )

    def test_create_all_options(self):
        self.assert_pcs_success(
            (
                f"constraint ticket add T {const.PCMK_ROLE_PROMOTED} A "
                "loss-policy=fence id=my-constraint"
            ).split()
        )
        self.assert_pcs_success(
            "constraint ticket config --full".split(),
            dedent(
                f"""\
                Ticket Constraints:
                  {const.PCMK_ROLE_PROMOTED} A loss-policy=fence ticket=T (id:my-constraint)
                """
            ),
        )

    def test_refuse_bad_option(self):
        self.assert_pcs_fail(
            "constraint ticket add T A loss_policy=fence".split(),
            (
                "Error: invalid option 'loss_policy', allowed options are: "
                "'id', 'loss-policy'\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_refuse_noexistent_resource_id(self):
        self.assert_pcs_fail(
            "constraint ticket add T master AA loss-policy=fence".split(),
            ["Error: bundle/clone/group/resource 'AA' does not exist"],
        )

    def test_refuse_invalid_role(self):
        self.assert_pcs_fail(
            "constraint ticket add T bad-role A loss-policy=fence".split(),
            (
                "Error: 'bad-role' is not a valid role value, use {}\n".format(
                    format_list(const.PCMK_ROLES)
                )
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_refuse_duplicate_ticket(self):
        self.assert_pcs_success(
            (
                f"constraint ticket add T {const.PCMK_ROLE_UNPROMOTED} A "
                "loss-policy=fence"
            ).split(),
        )
        role = str(const.PCMK_ROLE_UNPROMOTED_LEGACY).lower()
        self.assert_pcs_fail(
            f"constraint ticket add T {role} A loss-policy=fence".split(),
            (
                f"Deprecation Warning: Value '{role}' of option role is "
                f"deprecated and should not be used, use "
                f"'{const.PCMK_ROLE_UNPROMOTED}' value instead\n"
                "Duplicate constraints:\n"
                f"  {const.PCMK_ROLE_UNPROMOTED} A loss-policy=fence ticket=T (id:ticket-T-A-{const.PCMK_ROLE_UNPROMOTED})\n"
                "Error: duplicate constraint already exists, use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_accept_duplicate_ticket_with_force(self):
        role = str(const.PCMK_ROLE_PROMOTED_LEGACY).lower()
        self.assert_pcs_success(
            f"constraint ticket add T {role} A loss-policy=fence".split(),
            stderr_full=(
                f"Deprecation Warning: Value '{role}' of option role is "
                f"deprecated and should not be used, use "
                f"'{const.PCMK_ROLE_PROMOTED}' value instead\n"
            ),
        )
        promoted_role = const.PCMK_ROLE_PROMOTED_PRIMARY
        self.assert_pcs_success(
            (
                f"constraint ticket add T {const.PCMK_ROLE_PROMOTED} A "
                "loss-policy=fence --force"
            ).split(),
            stderr_full=[
                "Duplicate constraints:",
                f"  {promoted_role} A loss-policy=fence ticket=T (id:ticket-T-A-{promoted_role})",
                "Warning: duplicate constraint already exists",
            ],
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            stdout_full=[
                "Ticket Constraints:",
                f"  {promoted_role} A loss-policy=fence ticket=T",
                f"  {promoted_role} A loss-policy=fence ticket=T",
            ],
        )


class TicketDeleteRemoveTest(ConstraintBaseTest):
    command = None

    def _test_usage(self):
        self.assert_pcs_fail(
            ["constraint", "ticket", self.command],
            stderr_start=outdent(
                f"""
                Usage: pcs constraint [constraints]...
                    ticket {self.command} <"""
            ),
        )

    def _test_remove_multiple_tickets(self):
        # fixture
        self.assert_pcs_success("constraint ticket add T A".split())
        self.assert_pcs_success(
            "constraint ticket add T A --force".split(),
            stderr_full=[
                "Duplicate constraints:",
                "  A ticket=T (id:ticket-T-A)",
                "Warning: duplicate constraint already exists",
            ],
        )
        self.assert_pcs_success(
            "constraint ticket set A B setoptions ticket=T".split()
        )
        self.assert_pcs_success(
            "constraint ticket set A setoptions ticket=T".split()
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            stdout_full=[
                "Ticket Constraints:",
                "  A ticket=T",
                "  A ticket=T",
                "  Resource Sets:",
                "    set A B setoptions ticket=T",
                "    set A setoptions ticket=T",
            ],
        )

        # test
        self.assert_pcs_success(
            ["constraint", "ticket", self.command, "T", "A"]
        )

        self.assert_pcs_success(
            "constraint ticket config".split(),
            stdout_full=[
                "Ticket Constraints:",
                "  Resource Sets:",
                "    set B setoptions ticket=T",
            ],
        )

    def _test_fail_when_no_matching_ticket_constraint_here(self):
        self.assert_pcs_success(
            "constraint ticket config".split(),
            stdout_full=["Ticket Constraints:"],
        )
        self.assert_pcs_fail(
            ["constraint", "ticket", self.command, "T", "A"],
            ["Error: no matching ticket constraint found"],
        )


class TicketDeleteTest(
    TicketDeleteRemoveTest, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class TicketRemoveTest(
    TicketDeleteRemoveTest, metaclass=ParametrizedTestMetaClass
):
    command = "remove"


class TicketShow(ConstraintBaseTest):
    def test_show_set(self):
        self.assert_pcs_success(
            "constraint ticket set A B setoptions ticket=T".split()
        )
        role = str(const.PCMK_ROLE_PROMOTED_LEGACY).lower()
        self.assert_pcs_success(
            f"constraint ticket add T {role} A loss-policy=fence".split(),
            stderr_full=(
                f"Deprecation Warning: Value '{role}' of option role is "
                f"deprecated and should not be used, use "
                f"'{const.PCMK_ROLE_PROMOTED}' value instead\n"
            ),
        )
        self.assert_pcs_success(
            "constraint ticket config".split(),
            [
                "Ticket Constraints:",
                f"  {const.PCMK_ROLE_PROMOTED_PRIMARY} A loss-policy=fence ticket=T",
                "  Resource Sets:",
                "    set A B setoptions ticket=T",
            ],
        )


class ConstraintEffect(
    unittest.TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//constraints")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_constraint")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def fixture_primitive(self, name):
        self.assert_pcs_success(
            ["resource", "create", name, "ocf:heartbeat:Dummy"]
        )


class LocationTypeId(ConstraintEffect):
    # This was written while implementing rsc-pattern to location constraints.
    # Thus it focuses only the new feature (rsc-pattern) and it is NOT a
    # complete test of location constraints. Instead it relies on legacy tests
    # to test location constraints with plain resource name.
    def test_prefers(self):
        self.fixture_primitive("A")
        self.assert_effect(
            [
                "constraint location A prefers node1".split(),
                "constraint location %A prefers node1".split(),
                "constraint location resource%A prefers node1".split(),
            ],
            """<constraints>
                <rsc_location id="location-A-node1-INFINITY" node="node1"
                    rsc="A" score="INFINITY"
                />
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_avoids(self):
        self.fixture_primitive("A")
        self.assert_effect(
            [
                "constraint location A avoids node1".split(),
                "constraint location %A avoids node1".split(),
                "constraint location resource%A avoids node1".split(),
            ],
            """<constraints>
                <rsc_location id="location-A-node1--INFINITY" node="node1"
                    rsc="A" score="-INFINITY"
                />
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_add(self):
        self.fixture_primitive("A")
        self.assert_effect(
            [
                "constraint location add my-id A node1 INFINITY".split(),
                "constraint location add my-id %A node1 INFINITY".split(),
                "constraint location add my-id resource%A node1 INFINITY".split(),
            ],
            """<constraints>
                <rsc_location id="my-id" node="node1" rsc="A" score="INFINITY"/>
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_rule(self):
        self.fixture_primitive("A")
        self.assert_effect(
            [
                "constraint location A rule #uname eq node1".split(),
                "constraint location %A rule #uname eq node1".split(),
                "constraint location resource%A rule #uname eq node1".split(),
            ],
            """<constraints>
                <rsc_location id="location-A" rsc="A">
                    <rule id="location-A-rule" score="INFINITY">
                        <expression id="location-A-rule-expr"
                            operation="eq" attribute="#uname" value="node1"
                        />
                    </rule>
                </rsc_location>
            </constraints>""",
        )


class LocationTypePattern(ConstraintEffect):
    # This was written while implementing rsc-pattern to location constraints.
    # Thus it focuses only the new feature (rsc-pattern) and it is NOT a
    # complete test of location constraints. Instead it relies on legacy tests
    # to test location constraints with plain resource name.
    def test_prefers(self):
        self.assert_effect(
            "constraint location regexp%res_[0-9] prefers node1".split(),
            """<constraints>
                <rsc_location id="location-res_0-9-node1-INFINITY" node="node1"
                    rsc-pattern="res_[0-9]" score="INFINITY"
                />
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_avoids(self):
        self.assert_effect(
            "constraint location regexp%res_[0-9] avoids node1".split(),
            """<constraints>
                <rsc_location id="location-res_0-9-node1--INFINITY" node="node1"
                    rsc-pattern="res_[0-9]" score="-INFINITY"
                />
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_add(self):
        self.assert_effect(
            "constraint location add my-id regexp%res_[0-9] node1 INFINITY".split(),
            """<constraints>
                <rsc_location id="my-id" node="node1" rsc-pattern="res_[0-9]"
                    score="INFINITY"
                />
            </constraints>""",
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_rule(self):
        self.assert_effect(
            "constraint location regexp%res_[0-9] rule #uname eq node1".split(),
            """<constraints>
                <rsc_location id="location-res_0-9" rsc-pattern="res_[0-9]">
                    <rule id="location-res_0-9-rule" score="INFINITY">
                        <expression id="location-res_0-9-rule-expr"
                            operation="eq" attribute="#uname" value="node1"
                        />
                    </rule>
                </rsc_location>
            </constraints>""",
        )


@skip_unless_crm_rule()
class LocationShowWithPattern(ConstraintBaseTest):
    # This was written while implementing rsc-pattern to location constraints.
    # Thus it focuses only the new feature (rsc-pattern) and it is NOT a
    # complete test of location constraints. Instead it relies on legacy tests
    # to test location constraints with plain resource name.
    def fixture(self):
        self.assert_pcs_success_all(
            [
                "resource create R1 ocf:heartbeat:Dummy".split(),
                "resource create R2 ocf:heartbeat:Dummy".split(),
                "resource create R3 ocf:heartbeat:Dummy".split(),
                "constraint location R1 prefers node1 node2=20".split(),
                "constraint location R1 avoids node3=30 node4".split(),
                "constraint location R2 prefers node3 node4=20".split(),
                "constraint location R2 avoids node1=30 node2".split(),
                "constraint location regexp%R_[0-9]+ prefers node1 node2=20".split(),
                "constraint location regexp%R_[0-9]+ avoids node3=30".split(),
                "constraint location regexp%R_[a-z]+ avoids node3=30".split(),
                "constraint location add my-id1 R3 node1 -INFINITY resource-discovery=never".split(),
                "constraint location add my-id2 R3 node2 -INFINITY resource-discovery=never".split(),
                "constraint location add my-id3 regexp%R_[0-9]+ node4 -INFINITY resource-discovery=never".split(),
                "constraint location regexp%R_[0-9]+ rule score=20 defined pingd".split(),
            ]
        )

    def test_show(self):
        self.fixture()
        self.assert_pcs_success(
            "constraint location config --all --full".split(),
            outdent(
                """\
            Location Constraints:
              Resource pattern: R_[0-9]+
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-R_0-9-node1-INFINITY)
                  Node: node2 (score:20) (id:location-R_0-9-node2-20)
                Disabled on:
                  Node: node3 (score:-30) (id:location-R_0-9-node3--30)
                  Node: node4 (score:-INFINITY) (resource-discovery=never) (id:my-id3)
                Constraint: location-R_0-9
                  Rule: score=20 (id:location-R_0-9-rule)
                    Expression: defined pingd (id:location-R_0-9-rule-expr)
              Resource pattern: R_[a-z]+
                Disabled on:
                  Node: node3 (score:-30) (id:location-R_a-z-node3--30)
              Resource: R1
                Enabled on:
                  Node: node1 (score:INFINITY) (id:location-R1-node1-INFINITY)
                  Node: node2 (score:20) (id:location-R1-node2-20)
                Disabled on:
                  Node: node3 (score:-30) (id:location-R1-node3--30)
                  Node: node4 (score:-INFINITY) (id:location-R1-node4--INFINITY)
              Resource: R2
                Enabled on:
                  Node: node3 (score:INFINITY) (id:location-R2-node3-INFINITY)
                  Node: node4 (score:20) (id:location-R2-node4-20)
                Disabled on:
                  Node: node1 (score:-30) (id:location-R2-node1--30)
                  Node: node2 (score:-INFINITY) (id:location-R2-node2--INFINITY)
              Resource: R3
                Disabled on:
                  Node: node1 (score:-INFINITY) (resource-discovery=never) (id:my-id1)
                  Node: node2 (score:-INFINITY) (resource-discovery=never) (id:my-id2)
            """
            ),
        )

        self.assert_pcs_success(
            "constraint location config".split(),
            outdent(
                """\
            Location Constraints:
              Resource pattern: R_[0-9]+
                Enabled on:
                  Node: node1 (score:INFINITY)
                  Node: node2 (score:20)
                Disabled on:
                  Node: node3 (score:-30)
                  Node: node4 (score:-INFINITY) (resource-discovery=never)
                Constraint: location-R_0-9
                  Rule: score=20
                    Expression: defined pingd
              Resource pattern: R_[a-z]+
                Disabled on:
                  Node: node3 (score:-30)
              Resource: R1
                Enabled on:
                  Node: node1 (score:INFINITY)
                  Node: node2 (score:20)
                Disabled on:
                  Node: node3 (score:-30)
                  Node: node4 (score:-INFINITY)
              Resource: R2
                Enabled on:
                  Node: node3 (score:INFINITY)
                  Node: node4 (score:20)
                Disabled on:
                  Node: node1 (score:-30)
                  Node: node2 (score:-INFINITY)
              Resource: R3
                Disabled on:
                  Node: node1 (score:-INFINITY) (resource-discovery=never)
                  Node: node2 (score:-INFINITY) (resource-discovery=never)
            """
            ),
        )

        self.assert_pcs_success(
            "constraint location config nodes --full".split(),
            outdent(
                """\
            Location Constraints:
              Node: 
                Allowed to run:
                  Resource pattern: R_[0-9]+ (score:0) (id:location-R_0-9)
              Node: node1
                Allowed to run:
                  Resource: R1 (score:INFINITY) (id:location-R1-node1-INFINITY)
                  Resource pattern: R_[0-9]+ (score:INFINITY) (id:location-R_0-9-node1-INFINITY)
                Not allowed to run:
                  Resource: R2 (score:-30) (id:location-R2-node1--30)
                  Resource: R3 (score:-INFINITY) (resource-discovery=never) (id:my-id1)
              Node: node2
                Allowed to run:
                  Resource: R1 (score:20) (id:location-R1-node2-20)
                  Resource pattern: R_[0-9]+ (score:20) (id:location-R_0-9-node2-20)
                Not allowed to run:
                  Resource: R2 (score:-INFINITY) (id:location-R2-node2--INFINITY)
                  Resource: R3 (score:-INFINITY) (resource-discovery=never) (id:my-id2)
              Node: node3
                Allowed to run:
                  Resource: R2 (score:INFINITY) (id:location-R2-node3-INFINITY)
                Not allowed to run:
                  Resource: R1 (score:-30) (id:location-R1-node3--30)
                  Resource pattern: R_[0-9]+ (score:-30) (id:location-R_0-9-node3--30)
                  Resource pattern: R_[a-z]+ (score:-30) (id:location-R_a-z-node3--30)
              Node: node4
                Allowed to run:
                  Resource: R2 (score:20) (id:location-R2-node4-20)
                Not allowed to run:
                  Resource: R1 (score:-INFINITY) (id:location-R1-node4--INFINITY)
                  Resource pattern: R_[0-9]+ (score:-INFINITY) (resource-discovery=never) (id:my-id3)
              Resource pattern: R_[0-9]+
                Constraint: location-R_0-9
                  Rule: score=20 (id:location-R_0-9-rule)
                    Expression: defined pingd (id:location-R_0-9-rule-expr)
            """
            ),
        )

        self.assert_pcs_success(
            "constraint location config nodes node2".split(),
            outdent(
                """\
            Location Constraints:
              Node: node2
                Allowed to run:
                  Resource: R1 (score:20)
                  Resource pattern: R_[0-9]+ (score:20)
                Not allowed to run:
                  Resource: R2 (score:-INFINITY)
                  Resource: R3 (score:-INFINITY) (resource-discovery=never)
              Resource pattern: R_[0-9]+
                Constraint: location-R_0-9
                  Rule: score=20
                    Expression: defined pingd
            """
            ),
        )

        self.assert_pcs_success(
            "constraint location config resources regexp%R_[0-9]+".split(),
            outdent(
                """\
            Location Constraints:
              Resource pattern: R_[0-9]+
                Enabled on:
                  Node: node1 (score:INFINITY)
                  Node: node2 (score:20)
                Disabled on:
                  Node: node3 (score:-30)
                  Node: node4 (score:-INFINITY) (resource-discovery=never)
                Constraint: location-R_0-9
                  Rule: score=20
                    Expression: defined pingd
            """
            ),
        )


class Bundle(ConstraintEffect):
    def setUp(self):
        super().setUp()
        self.fixture_bundle("B")

    def fixture_primitive(self, name, bundle=None):
        # pylint:disable=arguments-differ
        if not bundle:
            super().fixture_primitive(name)
            return
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

    def fixture_bundle(self, name):
        self.assert_pcs_success(
            [
                "resource",
                "bundle",
                "create",
                name,
                "container",
                "docker",
                "image=pcs:test",
                "network",
                "control-port=1234",
            ]
        )


class BundleLocation(Bundle):
    def test_bundle_prefers(self):
        self.assert_effect(
            "constraint location B prefers node1".split(),
            """
                <constraints>
                    <rsc_location id="location-B-node1-INFINITY" node="node1"
                        rsc="B" score="INFINITY"
                    />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_bundle_avoids(self):
        self.assert_effect(
            "constraint location B avoids node1".split(),
            """
                <constraints>
                    <rsc_location id="location-B-node1--INFINITY" node="node1"
                        rsc="B" score="-INFINITY"
                    />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_bundle_location(self):
        self.assert_effect(
            "constraint location add id B node1 100".split(),
            """
                <constraints>
                    <rsc_location id="id" node="node1" rsc="B" score="100" />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_primitive_prefers(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint location R prefers node1".split(),
            (
                LOCATION_NODE_VALIDATION_SKIP_WARNING
                + "Error: R is a bundle resource, you should use the bundle id: "
                "B when adding constraints. Use --force to override.\n"
            ),
        )

    def test_primitive_prefers_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint location R prefers node1 --force".split(),
            """
                <constraints>
                    <rsc_location id="location-R-node1-INFINITY" node="node1"
                        rsc="R" score="INFINITY"
                    />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_primitive_avoids(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint location R avoids node1".split(),
            (
                LOCATION_NODE_VALIDATION_SKIP_WARNING
                + "Error: R is a bundle resource, you should use the bundle id: "
                "B when adding constraints. Use --force to override.\n"
            ),
        )

    def test_primitive_avoids_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint location R avoids node1 --force".split(),
            """
                <constraints>
                    <rsc_location id="location-R-node1--INFINITY" node="node1"
                        rsc="R" score="-INFINITY"
                    />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def test_primitive_location(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint location add id R node1 100".split(),
            (
                LOCATION_NODE_VALIDATION_SKIP_WARNING
                + "Error: R is a bundle resource, you should use the bundle id: "
                "B when adding constraints. Use --force to override.\n"
            ),
        )

    def test_primitive_location_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint location add id R node1 100 --force".split(),
            """
                <constraints>
                    <rsc_location id="id" node="node1" rsc="R" score="100" />
                </constraints>
            """,
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )


class BundleColocation(Bundle):
    def setUp(self):
        super().setUp()
        self.fixture_primitive("X")

    def test_bundle(self):
        self.assert_effect(
            "constraint colocation add B with X".split(),
            """
                <constraints>
                    <rsc_colocation id="colocation-B-X-INFINITY"
                        rsc="B" with-rsc="X" score="INFINITY" />
                </constraints>
            """,
        )

    def test_primitive(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint colocation add R with X".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints. Use --force to override.\n",
        )

    def test_primitive_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint colocation add R with X --force".split(),
            """
                <constraints>
                    <rsc_colocation id="colocation-R-X-INFINITY"
                        rsc="R" with-rsc="X" score="INFINITY" />
                </constraints>
            """,
        )

    def test_bundle_set(self):
        self.assert_effect(
            "constraint colocation set B X".split(),
            """
                <constraints>
                    <rsc_colocation id="colocation_set_BBXX" score="INFINITY">
                        <resource_set id="colocation_set_BBXX_set">
                            <resource_ref id="B" />
                            <resource_ref id="X" />
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )

    def test_primitive_set(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint colocation set R X".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints, use --force to override\n",
        )

    def test_primitive_set_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint colocation set R X --force".split(),
            """
                <constraints>
                    <rsc_colocation id="colocation_set_RRXX" score="INFINITY">
                        <resource_set id="colocation_set_RRXX_set">
                            <resource_ref id="R" />
                            <resource_ref id="X" />
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
            stderr_full=(
                "Warning: R is a bundle resource, you should use the bundle "
                "id: B when adding constraints\n"
            ),
        )


class BundleOrder(Bundle):
    def setUp(self):
        super().setUp()
        self.fixture_primitive("X")

    def test_bundle(self):
        self.assert_effect(
            "constraint order B then X".split(),
            """
                <constraints>
                    <rsc_order id="order-B-X-mandatory"
                        first="B" first-action="start"
                        then="X" then-action="start" />
                </constraints>
            """,
            stderr_full=(
                "Adding B X (kind: Mandatory) (Options: first-action=start "
                "then-action=start)\n"
            ),
        )

    def test_primitive(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint order R then X".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints. Use --force to override.\n",
        )

    def test_primitive_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint order R then X --force".split(),
            """
                <constraints>
                    <rsc_order id="order-R-X-mandatory"
                        first="R" first-action="start"
                        then="X" then-action="start" />
                </constraints>
            """,
            stderr_full=(
                "Adding R X (kind: Mandatory) (Options: first-action=start "
                "then-action=start)\n"
            ),
        )

    def test_bundle_set(self):
        self.assert_effect(
            "constraint order set B X".split(),
            """
                <constraints>
                    <rsc_order id="order_set_BBXX">
                        <resource_set id="order_set_BBXX_set">
                            <resource_ref id="B" />
                            <resource_ref id="X" />
                        </resource_set>
                    </rsc_order>
                </constraints>
            """,
        )

    def test_primitive_set(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint order set R X".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints, use --force to override\n",
        )

    def test_primitive_set_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint order set R X --force".split(),
            """
                <constraints>
                    <rsc_order id="order_set_RRXX">
                        <resource_set id="order_set_RRXX_set">
                            <resource_ref id="R" />
                            <resource_ref id="X" />
                        </resource_set>
                    </rsc_order>
                </constraints>
            """,
            stderr_full=(
                "Warning: R is a bundle resource, you should use the bundle id: B "
                "when adding constraints\n"
            ),
        )


class BundleTicket(Bundle):
    def test_bundle(self):
        self.assert_effect(
            "constraint ticket add T B".split(),
            """
                <constraints>
                    <rsc_ticket id="ticket-T-B" rsc="B" ticket="T" />
                </constraints>
            """,
        )

    def test_primitive(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint ticket add T R".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints, use --force to override\n",
        )

    def test_primitive_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint ticket add T R --force".split(),
            """
                <constraints>
                    <rsc_ticket id="ticket-T-R" rsc="R" ticket="T" />
                </constraints>
            """,
            stderr_full=(
                "Warning: R is a bundle resource, you should use the bundle id: B "
                "when adding constraints\n"
            ),
        )

    def test_bundle_set(self):
        self.assert_effect(
            "constraint ticket set B setoptions ticket=T".split(),
            """
                <constraints>
                    <rsc_ticket id="ticket_set_BB" ticket="T">
                        <resource_set id="ticket_set_BB_set">
                            <resource_ref id="B" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """,
        )

    def test_primitive_set(self):
        self.fixture_primitive("R", "B")
        self.assert_pcs_fail(
            "constraint ticket set R setoptions ticket=T".split(),
            "Error: R is a bundle resource, you should use the bundle id: B "
            "when adding constraints, use --force to override\n",
        )

    def test_primitive_set_force(self):
        self.fixture_primitive("R", "B")
        self.assert_effect(
            "constraint ticket set R setoptions ticket=T --force".split(),
            """
                <constraints>
                    <rsc_ticket id="ticket_set_RR" ticket="T">
                        <resource_set id="ticket_set_RR_set">
                            <resource_ref id="R" />
                        </resource_set>
                    </rsc_ticket>
                </constraints>
            """,
            stderr_full=(
                "Warning: R is a bundle resource, you should use the bundle id: B "
                "when adding constraints\n"
            ),
        )


NodeScore = namedtuple("NodeScore", "node score")


class LocationPrefersAvoidsMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//constraints")[0]
        )
    )
):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_constraint_location")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.command = "to-be-overridden"

    def tearDown(self):
        self.temp_cib.close()

    def xml_score(self, score):
        # pylint: disable=no-self-use
        return score if score else "INFINITY"

    @staticmethod
    def _unpack_node_score_list_to_cmd(node_score_list):
        return [
            "{node}{score}".format(
                node=item.node,
                score="" if item.score is None else f"={item.score}",
            )
            for item in node_score_list
        ]

    def _construct_xml(self, node_score_list):
        return "\n".join(
            [
                "<constraints>",
                "\n".join(
                    """
                <rsc_location id="location-dummy-{node}-{score}"
                node="{node}" rsc="dummy" score="{score}"/>
                """.format(
                        node=item.node,
                        score=self.xml_score(item.score),
                    )
                    for item in node_score_list
                ),
                "</constraints>",
            ]
        )

    def assert_success(self, node_score_list):
        assert self.command in {"prefers", "avoids"}
        self.fixture_primitive("dummy")
        self.assert_effect(
            (
                ["constraint", "location", "dummy", self.command]
                + self._unpack_node_score_list_to_cmd(node_score_list)
            ),
            self._construct_xml(node_score_list),
            stderr_full=LOCATION_NODE_VALIDATION_SKIP_WARNING,
        )

    def assert_failure(self, node_score_list, error_msg):
        assert self.command in {"prefers", "avoids"}
        self.fixture_primitive("dummy")
        self.assert_pcs_fail(
            (
                ["constraint", "location", "dummy", self.command]
                + self._unpack_node_score_list_to_cmd(node_score_list)
            ),
            LOCATION_NODE_VALIDATION_SKIP_WARNING + error_msg,
        )
        self.assert_resources_xml_in_cib("<constraints/>")

    def test_single_implicit_success(self):
        node1 = NodeScore("node1", None)
        self.assert_success([node1])

    def test_single_explicit_success(self):
        node1 = NodeScore("node1", "10")
        self.assert_success([node1])

    def test_multiple_implicit_success(self):
        node1 = NodeScore("node1", None)
        node2 = NodeScore("node2", None)
        node3 = NodeScore("node3", None)
        self.assert_success([node1, node2, node3])

    def test_multiple_mixed_success(self):
        node1 = NodeScore("node1", None)
        node2 = NodeScore("node2", "300")
        node3 = NodeScore("node3", None)
        self.assert_success([node1, node2, node3])

    def test_multiple_explicit_success(self):
        node1 = NodeScore("node1", "100")
        node2 = NodeScore("node2", "300")
        node3 = NodeScore("node3", "200")
        self.assert_success([node1, node2, node3])

    def test_empty_score(self):
        node1 = NodeScore("node1", "")
        self.assert_failure(
            [node1],
            "Error: invalid score '', use integer or INFINITY or -INFINITY\n",
        )

    def test_single_explicit_fail(self):
        node1 = NodeScore("node1", "aaa")
        self.assert_failure(
            [node1],
            "Error: invalid score 'aaa', use integer or INFINITY or -INFINITY\n",
        )

    def test_multiple_implicit_fail(self):
        node1 = NodeScore("node1", "whatever")
        node2 = NodeScore("node2", "dontcare")
        node3 = NodeScore("node3", "never")
        self.assert_failure(
            [node1, node2, node3],
            "Error: invalid score 'whatever', use integer or INFINITY or "
            "-INFINITY\n",
        )

    def test_multiple_mixed_fail(self):
        node1 = NodeScore("node1", None)
        node2 = NodeScore("node2", "invalid")
        node3 = NodeScore("node3", "200")
        self.assert_failure(
            [node1, node2, node3],
            "Error: invalid score 'invalid', use integer or INFINITY or "
            "-INFINITY\n",
        )


class LocationPrefers(ConstraintEffect, LocationPrefersAvoidsMixin):
    command = "prefers"


class LocationAvoids(ConstraintEffect, LocationPrefersAvoidsMixin):
    command = "avoids"

    def xml_score(self, score):
        score = super().xml_score(score)
        return score[1:] if score[0] == "-" else "-" + score


class LocationAdd(ConstraintEffect):
    def test_invalid_score(self):
        self.assert_pcs_fail(
            "constraint location add location1 D1 rh7-1 bar".split(),
            (
                LOCATION_NODE_VALIDATION_SKIP_WARNING
                + "Error: invalid score 'bar', use integer or INFINITY or "
                "-INFINITY\n"
            ),
        )
        self.assert_resources_xml_in_cib("<constraints/>")

    def test_invalid_location(self):
        self.assert_pcs_fail(
            "constraint location add loc:dummy D1 rh7-1 100".split(),
            (
                LOCATION_NODE_VALIDATION_SKIP_WARNING
                + "Error: invalid constraint id 'loc:dummy', ':' is not a valid "
                "character for a constraint id\n"
            ),
        )
        self.assert_resources_xml_in_cib("<constraints/>")


@skip_unless_crm_rule()
class ExpiredConstraints(ConstraintBaseTest):
    _tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).strftime(
        "%Y-%m-%d"
    )

    def fixture_group(self):
        self.assert_pcs_success(
            "resource create dummy1 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create dummy2 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource group add dummy_group dummy1 dummy2".split()
        )

    def fixture_primitive(self):
        self.assert_pcs_success(
            "resource create dummy ocf:heartbeat:Dummy".split()
        )

    def fixture_multiple_primitive(self):
        self.assert_pcs_success(
            "resource create D1 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create D2 ocf:heartbeat:Dummy".split()
        )
        self.assert_pcs_success(
            "resource create D3 ocf:heartbeat:Dummy".split()
        )

    def test_crm_rule_missing(self):
        self.pcs_runner = PcsRunner(
            self.temp_cib.name, mock_settings={"crm_rule": ""}
        )
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY
                        Expression: date lt 2019-01-01
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
            stderr_full=f"Warning: {CRM_RULE_MISSING_MSG}\n",
        )

    def test_in_effect_primitive_plain(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date gt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
            Location Constraints:
              Resource: dummy
                Constraint: location-dummy
                  Rule: score=INFINITY
                    Expression: date gt 2019-01-01
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

    def test_in_effect_primitive_full(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date gt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full".split(),
            outdent(
                """\
            Location Constraints:
              Resource: dummy
                Constraint: location-dummy
                  Rule: score=INFINITY (id:test-rule)
                    Expression: date gt 2019-01-01 (id:test-rule-expr)
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

    def test_in_effect_primitive_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date gt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --all".split(),
            outdent(
                """\
            Location Constraints:
              Resource: dummy
                Constraint: location-dummy
                  Rule: score=INFINITY
                    Expression: date gt 2019-01-01
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

    def test_in_effect_primitive_full_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date gt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY (id:test-rule)
                        Expression: date gt 2019-01-01 (id:test-rule-expr)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_in_effect_group_plain(self):
        self.fixture_group()
        self.assert_pcs_success(
            (
                "constraint location dummy_group rule id=test-rule score=INFINITY "
                "date gt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
            Location Constraints:
              Resource: dummy_group
                Constraint: location-dummy_group
                  Rule: score=INFINITY
                    Expression: date gt 2019-01-01
            Ordering Constraints:
            Colocation Constraints:
            Ticket Constraints:
            """
            ),
        )

    def test_expired_primitive_plain(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_expired_primitive_full(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full".split(),
            outdent(
                """\
                Location Constraints:
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_expired_primitive_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint (expired): location-dummy
                      Rule (expired): score=INFINITY
                        Expression: date lt 2019-01-01
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_expired_primitive_full_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint (expired): location-dummy
                      Rule (expired): score=INFINITY (id:test-rule)
                        Expression: date lt 2019-01-01 (id:test-rule-expr)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_expired_group_plain(self):
        self.fixture_group()
        self.assert_pcs_success(
            (
                "constraint location dummy_group rule id=test-rule score=INFINITY "
                "date lt 2019-01-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_indeterminate_primitive_plain(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date eq 2019-01-01 or date eq 2019-03-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: boolean-op=or score=INFINITY
                        Expression: date eq 2019-01-01
                        Expression: date eq 2019-03-01
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_indeterminate_primitive_full(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date eq 2019-01-01 or date eq 2019-03-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: boolean-op=or score=INFINITY (id:test-rule)
                        Expression: date eq 2019-01-01 (id:test-rule-expr)
                        Expression: date eq 2019-03-01 (id:test-rule-expr-1)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_indeterminate_primitive_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date eq 2019-01-01 or date eq 2019-03-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: boolean-op=or score=INFINITY
                        Expression: date eq 2019-01-01
                        Expression: date eq 2019-03-01
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_indeterminate_primitive_full_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            (
                "constraint location dummy rule id=test-rule score=INFINITY "
                "date eq 2019-01-01 or date eq 2019-03-01"
            ).split()
        )
        self.assert_pcs_success(
            "constraint --full --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: boolean-op=or score=INFINITY (id:test-rule)
                        Expression: date eq 2019-01-01 (id:test-rule-expr)
                        Expression: date eq 2019-03-01 (id:test-rule-expr-1)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_indeterminate_group_plain(self):
        self.fixture_group()
        self.assert_pcs_success(
            (
                "constraint location dummy_group rule id=test-rule score=INFINITY "
                "date eq 2019-01-01 or date eq 2019-03-01"
            ).split()
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                  Resource: dummy_group
                    Constraint: location-dummy_group
                      Rule: boolean-op=or score=INFINITY
                        Expression: date eq 2019-01-01
                        Expression: date eq 2019-03-01
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_not_yet_in_effect_primitive_plain(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            "constraint location dummy rule id=test-rule score=INFINITY date gt".split()
            + [self._tomorrow]
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                f"""\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY
                        Expression: date gt {self._tomorrow}
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_not_yet_in_effect_primitive_full(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            "constraint location dummy rule id=test-rule score=INFINITY date gt".split()
            + [self._tomorrow]
        )
        self.assert_pcs_success(
            "constraint --full".split(),
            outdent(
                f"""\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY (id:test-rule)
                        Expression: date gt {self._tomorrow} (id:test-rule-expr)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_not_yet_in_effect_primitive_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            "constraint location dummy rule id=test-rule score=INFINITY date gt".split()
            + [self._tomorrow]
        )
        self.assert_pcs_success(
            "constraint --all".split(),
            outdent(
                f"""\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY
                        Expression: date gt {self._tomorrow}
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_not_yet_in_effect_primitive_full_all(self):
        self.fixture_primitive()
        self.assert_pcs_success(
            "constraint location dummy rule id=test-rule score=INFINITY date gt".split()
            + [self._tomorrow]
        )
        self.assert_pcs_success(
            "constraint --full --all".split(),
            outdent(
                f"""\
                Location Constraints:
                  Resource: dummy
                    Constraint: location-dummy
                      Rule: score=INFINITY (id:test-rule)
                        Expression: date gt {self._tomorrow} (id:test-rule-expr)
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_not_yet_in_effect_group_plain(self):
        self.fixture_group()
        self.assert_pcs_success(
            "constraint location dummy_group rule id=test-rule score=INFINITY date gt".split()
            + [self._tomorrow]
        )
        self.assert_pcs_success(
            ["constraint"],
            outdent(
                f"""\
                Location Constraints:
                  Resource: dummy_group
                    Constraint: location-dummy_group
                      Rule: score=INFINITY
                        Expression: date gt {self._tomorrow}
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_complex_primitive_plain(self):
        self.fixture_multiple_primitive()
        self.assert_pcs_success(
            (
                "constraint location D1 rule id=test-rule-D1-1 score=INFINITY "
                "not_defined pingd"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D1 rule id=test-rule-D1-2 score=INFINITY "
                "( date eq 2019-01-01 or date eq 2019-01-30 ) and #uname eq node1"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D2 rule id=test-constr-D2 score=INFINITY "
                "date in_range 2019-01-01 to 2019-02-01"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint rule add location-D2 id=test-duration score=INFINITY "
                "date in_range 2019-03-01 to duration weeks=2"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D3 rule id=test-rule-D3-0 score=INFINITY "
                "date in_range 2019-03-01 to duration weeks=2"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint rule add location-D3 id=test-defined score=INFINITY "
                "not_defined pingd"
            ).split()
        )

        self.assert_pcs_success(
            ["constraint"],
            outdent(
                """\
                Location Constraints:
                  Resource: D1
                    Constraint: location-D1
                      Rule: score=INFINITY
                        Expression: not_defined pingd
                    Constraint: location-D1-1
                      Rule: boolean-op=and score=INFINITY
                        Rule: boolean-op=or score=0
                          Expression: date eq 2019-01-01
                          Expression: date eq 2019-01-30
                        Expression: #uname eq node1
                  Resource: D3
                    Constraint: location-D3
                      Rule: score=INFINITY
                        Expression: date in_range 2019-03-01 to duration
                          Duration: weeks=2
                      Rule: score=INFINITY
                        Expression: not_defined pingd
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )

    def test_complex_primitive_all(self):
        self.fixture_multiple_primitive()
        self.assert_pcs_success(
            (
                "constraint location D1 rule id=test-rule-D1 score=INFINITY "
                "not_defined pingd"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D1 rule id=test-rule-D1-2 score=INFINITY "
                "( date eq 2019-01-01 or date eq 2019-01-30 ) and #uname eq node1"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D2 rule id=test-constr-D2 score=INFINITY "
                "date in_range 2019-01-01 to 2019-02-01"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint rule add location-D2 id=test-duration score=INFINITY "
                "date in_range 2019-03-01 to duration weeks=2"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint location D3 rule id=test-rule-D3-0 score=INFINITY "
                "date in_range 2019-03-01 to duration weeks=2"
            ).split()
        )
        self.assert_pcs_success(
            (
                "constraint rule add location-D3 id=test-defined score=INFINITY "
                "not_defined pingd"
            ).split()
        )

        self.assert_pcs_success(
            "constraint --all".split(),
            outdent(
                """\
                Location Constraints:
                  Resource: D1
                    Constraint: location-D1
                      Rule: score=INFINITY
                        Expression: not_defined pingd
                    Constraint: location-D1-1
                      Rule: boolean-op=and score=INFINITY
                        Rule: boolean-op=or score=0
                          Expression: date eq 2019-01-01
                          Expression: date eq 2019-01-30
                        Expression: #uname eq node1
                  Resource: D2
                    Constraint (expired): location-D2
                      Rule (expired): score=INFINITY
                        Expression: date in_range 2019-01-01 to 2019-02-01
                      Rule (expired): score=INFINITY
                        Expression: date in_range 2019-03-01 to duration
                          Duration: weeks=2
                  Resource: D3
                    Constraint: location-D3
                      Rule (expired): score=INFINITY
                        Expression: date in_range 2019-03-01 to duration
                          Duration: weeks=2
                      Rule: score=INFINITY
                        Expression: not_defined pingd
                Ordering Constraints:
                Colocation Constraints:
                Ticket Constraints:
                """
            ),
        )


class OrderVsGroup(unittest.TestCase, AssertPcsMixin):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_constraint_order_vs_group")
        write_file_to_tmpfile(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.assert_pcs_success(
            "resource create A ocf:heartbeat:Dummy --group grAB".split()
        )
        self.assert_pcs_success(
            "resource create B ocf:heartbeat:Dummy --group grAB".split()
        )
        self.assert_pcs_success(
            "resource create C ocf:heartbeat:Dummy --group grC".split()
        )
        self.assert_pcs_success("resource create D ocf:heartbeat:Dummy".split())

    def tearDown(self):
        self.temp_cib.close()

    def test_deny_resources_in_one_group(self):
        self.assert_pcs_fail(
            "constraint order A then B".split(),
            "Error: Cannot create an order constraint for resources in the same group\n",
        )

    def test_allow_resources_in_different_groups(self):
        self.assert_pcs_success(
            "constraint order A then C".split(),
            stderr_full=(
                "Adding A C (kind: Mandatory) (Options: first-action=start "
                "then-action=start)\n"
            ),
        )

    def test_allow_grouped_and_not_grouped_resource(self):
        self.assert_pcs_success(
            "constraint order A then D".split(),
            stderr_full=(
                "Adding A D (kind: Mandatory) (Options: first-action=start "
                "then-action=start)\n"
            ),
        )

    def test_allow_group_and_resource(self):
        self.assert_pcs_success(
            "constraint order grAB then C".split(),
            stderr_full=(
                "Adding grAB C (kind: Mandatory) (Options: first-action=start "
                "then-action=start)\n"
            ),
        )
