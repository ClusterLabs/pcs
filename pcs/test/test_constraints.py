from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import shutil
from pcs.test.tools import pcs_unittest as unittest

from pcs.test.tools.assertions import AssertPcsMixin, console_report
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
    is_minimum_pacemaker_version,
)
from pcs.test.tools.pcs_runner import pcs, PcsRunner


empty_cib = rc("cib-empty.xml")
empty_cib_1_2 = rc("cib-empty-1.2.xml")
temp_cib = rc("temp-cib.xml")
large_cib = rc("cib-large.xml")

class ConstraintTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.setupClusterA(temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource and clones
    def setupClusterA(self,temp_cib):
        line = "resource create D1 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D2 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D3 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D4 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D5 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D6 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource clone D3"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource master Master D4"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

    def testConstraintRules(self):
        output, returnVal = pcs(temp_cib, "constraint location D1 rule score=222 '#uname' eq c00n03")
        assert output == "", [output]
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location D2 rule score=-INFINITY '#uname' eq c00n04")
        assert returnVal == 0
        assert output == "", [output]

        o, r = pcs(
            temp_cib,
            "resource create C1 ocf:heartbeat:Dummy --group C1-group"
        )
        assert r == 0 and o == "", o

        output, returnVal = pcs(temp_cib, "constraint location C1-group rule score=pingd defined pingd")
        assert returnVal == 0
        assert output == "Warning: invalid score 'pingd', setting score-attribute=pingd instead\n", [output]

        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=pingd defined pingd --force")
        assert returnVal == 0
        assert output == "Warning: invalid score 'pingd', setting score-attribute=pingd instead\n", [output]

        output, returnVal = pcs(temp_cib, "constraint location D4 rule score=INFINITY date start=2005-001 gt --force")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D5 rule score=INFINITY date start=2005-001 end=2006-001 in_range")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D6 rule score=INFINITY date-spec operation=date_spec years=2005")
        assert output == "", [output]
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=-INFINITY not_defined pingd or pingd lte 0 --force")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=-INFINITY not_defined pingd and pingd lte 0 --force")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0
        ac(output, """\
Location Constraints:
  Resource: C1-group
    Constraint: location-C1-group
      Rule: score-attribute=pingd  (id:location-C1-group-rule)
        Expression: defined pingd  (id:location-C1-group-rule-expr)
  Resource: D1
    Constraint: location-D1
      Rule: score=222  (id:location-D1-rule)
        Expression: #uname eq c00n03  (id:location-D1-rule-expr)
  Resource: D2
    Constraint: location-D2
      Rule: score=-INFINITY  (id:location-D2-rule)
        Expression: #uname eq c00n04  (id:location-D2-rule-expr)
  Resource: D3
    Constraint: location-D3
      Rule: score-attribute=pingd  (id:location-D3-rule)
        Expression: defined pingd  (id:location-D3-rule-expr)
    Constraint: location-D3-1
      Rule: boolean-op=or score=-INFINITY  (id:location-D3-1-rule)
        Expression: not_defined pingd  (id:location-D3-1-rule-expr)
        Expression: pingd lte 0  (id:location-D3-1-rule-expr-1)
    Constraint: location-D3-2
      Rule: boolean-op=and score=-INFINITY  (id:location-D3-2-rule)
        Expression: not_defined pingd  (id:location-D3-2-rule-expr)
        Expression: pingd lte 0  (id:location-D3-2-rule-expr-1)
  Resource: D4
    Constraint: location-D4
      Rule: score=INFINITY  (id:location-D4-rule)
        Expression: date gt 2005-001  (id:location-D4-rule-expr)
  Resource: D5
    Constraint: location-D5
      Rule: score=INFINITY  (id:location-D5-rule)
        Expression: date in_range 2005-001 to 2006-001  (id:location-D5-rule-expr)
  Resource: D6
    Constraint: location-D6
      Rule: score=INFINITY  (id:location-D6-rule)
        Expression:  (id:location-D6-rule-expr)
          Date Spec: years=2005  (id:location-D6-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        o,r = pcs("constraint remove location-C1-group")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint remove location-D4-rule")
        ac(o,"")
        assert r == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0
        ac(output, """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: score=222  (id:location-D1-rule)
        Expression: #uname eq c00n03  (id:location-D1-rule-expr)
  Resource: D2
    Constraint: location-D2
      Rule: score=-INFINITY  (id:location-D2-rule)
        Expression: #uname eq c00n04  (id:location-D2-rule-expr)
  Resource: D3
    Constraint: location-D3
      Rule: score-attribute=pingd  (id:location-D3-rule)
        Expression: defined pingd  (id:location-D3-rule-expr)
    Constraint: location-D3-1
      Rule: boolean-op=or score=-INFINITY  (id:location-D3-1-rule)
        Expression: not_defined pingd  (id:location-D3-1-rule-expr)
        Expression: pingd lte 0  (id:location-D3-1-rule-expr-1)
    Constraint: location-D3-2
      Rule: boolean-op=and score=-INFINITY  (id:location-D3-2-rule)
        Expression: not_defined pingd  (id:location-D3-2-rule-expr)
        Expression: pingd lte 0  (id:location-D3-2-rule-expr-1)
  Resource: D5
    Constraint: location-D5
      Rule: score=INFINITY  (id:location-D5-rule)
        Expression: date in_range 2005-001 to 2006-001  (id:location-D5-rule-expr)
  Resource: D6
    Constraint: location-D6
      Rule: score=INFINITY  (id:location-D6-rule)
        Expression:  (id:location-D6-rule-expr)
          Date Spec: years=2005  (id:location-D6-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

    def testAdvancedConstraintRule(self):
        o,r = pcs(temp_cib, "constraint location D1 rule score=INFINITY not_defined pingd or pingd lte 0")
        ac(o,"")
        assert r == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0
        ac(output, """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: boolean-op=or score=INFINITY  (id:location-D1-rule)
        Expression: not_defined pingd  (id:location-D1-rule-expr)
        Expression: pingd lte 0  (id:location-D1-rule-expr-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

    def testEmptyConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint")
        assert returnVal == 0 and output == "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n", output

    def testMultipleOrderConstraints(self):
        o,r = pcs("constraint order stop D1 then stop D2")
        ac(o,"Adding D1 D2 (kind: Mandatory) (Options: first-action=stop then-action=stop)\n")
        assert r == 0

        o,r = pcs("constraint order start D1 then start D2")
        ac(o,"Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)\n")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\nOrdering Constraints:\n  stop D1 then stop D2 (kind:Mandatory) (id:order-D1-D2-mandatory)\n  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-1)\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

    def testOrderConstraintRequireAll(self):
        if not is_minimum_pacemaker_version(1, 1, 12):
            print("WARNING: Pacemaker version is too old (must be >= 1.1.12) to test require-all")
            return

        o,r = pcs("cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        o,r = pcs("constraint order start D1 then start D2 require-all=false")
        ac(o,"Adding D1 D2 (kind: Mandatory) (Options: require-all=false first-action=start then-action=start)\n")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o, """\
Location Constraints:
Ordering Constraints:
  start D1 then start D2 (kind:Mandatory) (Options: require-all=false) (id:order-D1-D2-mandatory)
Colocation Constraints:
Ticket Constraints:
""")
        assert r == 0

    def testAllConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint order Master then D5")
        assert returnVal == 0 and output == "Adding Master D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n", output

        output, returnVal = pcs(temp_cib, "constraint colocation add Master with D5")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0
        ac (output,"Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)\nOrdering Constraints:\n  start Master then start D5 (kind:Mandatory) (id:order-Master-D5-mandatory)\nColocation Constraints:\n  Master with D5 (score:INFINITY) (id:colocation-Master-D5-INFINITY)\nTicket Constraints:\n")

        output, returnVal = pcs(temp_cib, "constraint show --full")
        assert returnVal == 0
        ac(output,"Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)\nOrdering Constraints:\n  start Master then start D5 (kind:Mandatory) (id:order-Master-D5-mandatory)\nColocation Constraints:\n  Master with D5 (score:INFINITY) (id:colocation-Master-D5-INFINITY)\nTicket Constraints:\n")

    def testLocationConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node2")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint")
        assert returnVal == 0
        ac(output, "Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY)\n    Disabled on: node2 (score:-INFINITY)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")

        output, returnVal = pcs(temp_cib, "constraint location add location-D5-node1-INFINITY ")
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs constraint"), output

    def testConstraintRemoval(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location D6 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint remove blahblah")
        assert returnVal == 1 and output.startswith("Error: Unable to find constraint - 'blahblah'"), output

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, "Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)\n  Resource: D6\n    Enabled on: node1 (score:INFINITY) (id:location-D6-node1-INFINITY)\n")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint remove location-D5-node1-INFINITY location-D6-node1-INFINITY")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, "Location Constraints:\n")
        assert returnVal == 0

    def testColocationConstraints(self):
        line = "resource create M1 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create M2 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create M3 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M4 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M5 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M6 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M7 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M8 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M9 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M10 ocf:heartbeat:Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        o, r = pcs(temp_cib, "constraint colocation add D1 D3-clone")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add D1 D2 100")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add D1 D2 -100 --force")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add Master with D5 100")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add master M1-master with master M2-master")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add M3-master with M4-master")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add slave M5-master with started M6-master 500")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add M7-master with Master M8-master")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add Slave M9-master with M10-master")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint")
        assert r == 0
        ac(o,'Location Constraints:\nOrdering Constraints:\nColocation Constraints:\n  D1 with D3-clone (score:INFINITY)\n  D1 with D2 (score:100)\n  D1 with D2 (score:-100)\n  Master with D5 (score:100)\n  M1-master with M2-master (score:INFINITY) (rsc-role:Master) (with-rsc-role:Master)\n  M3-master with M4-master (score:INFINITY)\n  M5-master with M6-master (score:500) (rsc-role:Slave) (with-rsc-role:Started)\n  M7-master with M8-master (score:INFINITY) (rsc-role:Started) (with-rsc-role:Master)\n  M9-master with M10-master (score:INFINITY) (rsc-role:Slave) (with-rsc-role:Started)\nTicket Constraints:\n')

    def testColocationSets(self):
        line = "resource create D7 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D8 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D9 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        o, r = pcs(temp_cib, "constraint colocation set")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint colocation set D7 D8 set")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint colocation set D7 D8 set set D8 D9")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint colocation set setoptions score=100")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint colocation set D5 D6 D7 sequential=false require-all=true set D8 D9 sequential=true require-all=false action=start role=Stopped setoptions score=INFINITY ")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint colocation set D5 D6")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint colocation set D5 D6 action=stop role=Started set D7 D8 action=promote role=Slave set D8 D9 action=demote role=Master")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint colocation --full")
        ac(o, """\
Colocation Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:pcs_rsc_set_D5_D6_D7) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:pcs_rsc_set_D8_D9) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D5_D6_D7_set_D8_D9)
    set D5 D6 (id:pcs_rsc_set_D5_D6) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D5_D6)
    set D5 D6 action=stop role=Started (id:pcs_rsc_set_D5_D6-1) set D7 D8 action=promote role=Slave (id:pcs_rsc_set_D7_D8) set D8 D9 action=demote role=Master (id:pcs_rsc_set_D8_D9-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D5_D6_set_D7_D8_set_D8_D9)
""")
        assert r == 0

        o, r = pcs(temp_cib, "constraint remove pcs_rsc_colocation_set_D5_D6")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint colocation --full")
        ac(o, """\
Colocation Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:pcs_rsc_set_D5_D6_D7) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:pcs_rsc_set_D8_D9) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D5_D6_D7_set_D8_D9)
    set D5 D6 action=stop role=Started (id:pcs_rsc_set_D5_D6-1) set D7 D8 action=promote role=Slave (id:pcs_rsc_set_D7_D8) set D8 D9 action=demote role=Master (id:pcs_rsc_set_D8_D9-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D5_D6_set_D7_D8_set_D8_D9)
""")
        assert r == 0

        o, r = pcs(temp_cib, "resource delete D5")
        ac(o,"Removing D5 from set pcs_rsc_set_D5_D6_D7\nRemoving D5 from set pcs_rsc_set_D5_D6-1\nDeleting Resource - D5\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource delete D6")
        ac(o,"Removing D6 from set pcs_rsc_set_D5_D6_D7\nRemoving D6 from set pcs_rsc_set_D5_D6-1\nRemoving set pcs_rsc_set_D5_D6-1\nDeleting Resource - D6\n")
        assert r == 0

        o, r = pcs(temp_cib, "constraint ref D7")
        ac(o,"Resource: D7\n  pcs_rsc_colocation_set_D5_D6_D7_set_D8_D9\n  pcs_rsc_colocation_set_D5_D6_set_D7_D8_set_D8_D9\n")
        assert r == 0

        o, r = pcs(temp_cib, "constraint ref D8")
        ac(o,"Resource: D8\n  pcs_rsc_colocation_set_D5_D6_D7_set_D8_D9\n  pcs_rsc_colocation_set_D5_D6_set_D7_D8_set_D8_D9\n")
        assert r == 0

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 sequential=foo")
        ac(output, "Error: 'foo' is not a valid sequential value, use true, false\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 require-all=foo")
        ac(output, "Error: 'foo' is not a valid require-all value, use true, false\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 role=foo")
        ac(output, "Error: 'foo' is not a valid role value, use Stopped, Started, Master, Slave\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 action=foo")
        ac(output, "Error: 'foo' is not a valid action value, use start, promote, demote, stop\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 foo=bar")
        ac(output, "Error: invalid option 'foo', allowed options are: action, require-all, role, sequential\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 setoptions foo=bar")
        ac(output, "Error: invalid option 'foo', allowed options are: id, score, score-attribute, score-attribute-mangle\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 setoptions score=foo")
        ac(output, "Error: invalid score 'foo', use integer or INFINITY or -INFINITY\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 setoptions score=100 score-attribute=foo")
        ac(output, "Error: you cannot specify multiple score options\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint colocation set D1 D2 setoptions score-attribute=foo")
        ac(output, "")
        self.assertEqual(0, retValue)

    def testConstraintResourceDiscovery(self):
        if not is_minimum_pacemaker_version(1, 1, 12):
            print("WARNING: Pacemaker version is too old (must be >= 1.1.12) to test resource-discovery")
            return

        o,r = pcs("resource create crd ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create crd1 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location crd rule resource-discovery=exclusive score=-INFINITY opsrole ne controller0 and opsrole ne controller1")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        o,r = pcs("constraint location crd1 rule resource-discovery=exclusive score=-INFINITY opsrole2 ne controller2")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o, '\n'.join([
            'Location Constraints:',
            '  Resource: crd',
            '    Constraint: location-crd (resource-discovery=exclusive)',
            '      Rule: boolean-op=and score=-INFINITY  (id:location-crd-rule)',
            '        Expression: opsrole ne controller0  (id:location-crd-rule-expr)',
            '        Expression: opsrole ne controller1  (id:location-crd-rule-expr-1)',
            '  Resource: crd1',
            '    Constraint: location-crd1 (resource-discovery=exclusive)',
            '      Rule: score=-INFINITY  (id:location-crd1-rule)',
            '        Expression: opsrole2 ne controller2  (id:location-crd1-rule-expr)',
            'Ordering Constraints:',
            'Colocation Constraints:',
            'Ticket Constraints:',
        ])+'\n')
        assert r == 0

        o,r = pcs("constraint delete location-crd")
        ac(o,"")
        assert r==0

        o,r = pcs("constraint delete location-crd1")
        ac(o,"")
        assert r==0

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

        o,r = pcs("constraint location add my_constraint_id crd my_node -INFINITY resource-discovery=always")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location add my_constraint_id2 crd1 my_node -INFINITY resource-discovery=never")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\n  Resource: crd\n    Disabled on: my_node (score:-INFINITY) (resource-discovery=always) (id:my_constraint_id)\n  Resource: crd1\n    Disabled on: my_node (score:-INFINITY) (resource-discovery=never) (id:my_constraint_id2)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

        o,r = pcs("constraint location add my_constraint_id3 crd1 my_node2 -INFINITY bad-opt=test")
        ac(o,"Error: bad option 'bad-opt', use --force to override\n")
        assert r == 1

    def testOrderSetsRemoval(self):
        o,r = pcs("resource create T0 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T1 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T2 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T3 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T4 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T5 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T6 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T7 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource create T8 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("constraint order set T0 T1 T2")
        ac(o,"")
        assert r == 0
        o,r = pcs("constraint order set T2 T3")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order remove T1")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order remove T1")
        ac(o,"Error: No matching resources found in ordering list\n")
        assert r == 1

        o,r = pcs("constraint order")
        ac(o,"Ordering Constraints:\n  Resource Sets:\n    set T0 T2\n    set T2 T3\n")
        assert r == 0

        o,r = pcs("constraint order remove T2")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order")
        ac(o,"Ordering Constraints:\n  Resource Sets:\n    set T0\n    set T3\n")
        assert r == 0

        o,r = pcs("constraint order remove T0")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order")
        ac(o,"Ordering Constraints:\n  Resource Sets:\n    set T3\n")
        assert r == 0

        o,r = pcs("constraint order remove T3")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order")
        ac(o,"Ordering Constraints:\n")
        assert r == 0

    def testOrderSets(self):
        line = "resource create D7 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D8 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D9 ocf:heartbeat:Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        o, r = pcs(temp_cib, "constraint order set")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint order set D7 D8 set")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint order set D7 D8 set set D8 D9")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint order set setoptions score=100")
        assert o.startswith("\nUsage: pcs constraint")
        assert r == 1

        o, r = pcs(temp_cib, "constraint order set D5 D6 D7 sequential=false require-all=true set D8 D9 sequential=true require-all=false action=start role=Stopped")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint order set D5 D6")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order set D5 D6 action=stop role=Started set D7 D8 action=promote role=Slave set D8 D9 action=demote role=Master")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order --full")
        assert r == 0
        ac(o,"""\
Ordering Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:pcs_rsc_set_D5_D6_D7) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:pcs_rsc_set_D8_D9) (id:pcs_rsc_order_set_D5_D6_D7_set_D8_D9)
    set D5 D6 (id:pcs_rsc_set_D5_D6) (id:pcs_rsc_order_set_D5_D6)
    set D5 D6 action=stop role=Started (id:pcs_rsc_set_D5_D6-1) set D7 D8 action=promote role=Slave (id:pcs_rsc_set_D7_D8) set D8 D9 action=demote role=Master (id:pcs_rsc_set_D8_D9-1) (id:pcs_rsc_order_set_D5_D6_set_D7_D8_set_D8_D9)
""")

        o, r = pcs(temp_cib, "constraint remove pcs_rsc_order_set_D5_D6")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order --full")
        assert r == 0
        ac(o,"""\
Ordering Constraints:
  Resource Sets:
    set D5 D6 D7 require-all=true sequential=false (id:pcs_rsc_set_D5_D6_D7) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:pcs_rsc_set_D8_D9) (id:pcs_rsc_order_set_D5_D6_D7_set_D8_D9)
    set D5 D6 action=stop role=Started (id:pcs_rsc_set_D5_D6-1) set D7 D8 action=promote role=Slave (id:pcs_rsc_set_D7_D8) set D8 D9 action=demote role=Master (id:pcs_rsc_set_D8_D9-1) (id:pcs_rsc_order_set_D5_D6_set_D7_D8_set_D8_D9)
""")

        o, r = pcs(temp_cib, "resource delete D5")
        ac(o,"Removing D5 from set pcs_rsc_set_D5_D6_D7\nRemoving D5 from set pcs_rsc_set_D5_D6-1\nDeleting Resource - D5\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource delete D6")
        ac(o,"Removing D6 from set pcs_rsc_set_D5_D6_D7\nRemoving D6 from set pcs_rsc_set_D5_D6-1\nRemoving set pcs_rsc_set_D5_D6-1\nDeleting Resource - D6\n")
        assert r == 0

        output, retValue = pcs(temp_cib, "constraint order set D1 D2 sequential=foo")
        ac(output, "Error: 'foo' is not a valid sequential value, use true, false\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint order set D1 D2 require-all=foo")
        ac(output, "Error: 'foo' is not a valid require-all value, use true, false\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint order set D1 D2 role=foo")
        ac(output, "Error: 'foo' is not a valid role value, use Stopped, Started, Master, Slave\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint order set D1 D2 action=foo")
        ac(output, "Error: 'foo' is not a valid action value, use start, promote, demote, stop\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(temp_cib, "constraint order set D1 D2 foo=bar")
        ac(output, "Error: invalid option 'foo', allowed options are: action, require-all, role, sequential\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions foo=bar"
        )
        ac(output, """\
Error: invalid option 'foo', allowed options are: id, kind, symmetrical
""")
        self.assertEqual(1, retValue)

        output, retValue = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions kind=foo"
        )
        ac(output, "Error: 'foo' is not a valid kind value, use Optional, Mandatory, Serialize\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions symmetrical=foo"
        )
        ac(output, "Error: 'foo' is not a valid symmetrical value, use true, false\n")
        self.assertEqual(1, retValue)

        output, retValue = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions symmetrical=false kind=mandatory"
        )
        ac(output, "")
        self.assertEqual(0, retValue)

        output, retValue = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
  Resource Sets:
    set D7 require-all=true sequential=false (id:pcs_rsc_set_D5_D6_D7) set D8 D9 action=start require-all=false role=Stopped sequential=true (id:pcs_rsc_set_D8_D9) (id:pcs_rsc_order_set_D5_D6_D7_set_D8_D9)
    set D7 D8 action=promote role=Slave (id:pcs_rsc_set_D7_D8) set D8 D9 action=demote role=Master (id:pcs_rsc_set_D8_D9-1) (id:pcs_rsc_order_set_D5_D6_set_D7_D8_set_D8_D9)
    set D1 D2 (id:pcs_rsc_set_D1_D2) setoptions kind=Mandatory symmetrical=false (id:pcs_rsc_order_set_D1_D2)
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, retValue)

    def testLocationConstraintRule(self):
        o, r = pcs(temp_cib, "constraint location D1 prefers rh7-1")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint location D2 prefers rh7-2")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint rule add location-D1-rh7-1-INFINITY #uname eq rh7-1")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint rule add location-D2-rh7-2-INFINITY date-spec hours=9-16 weekdays=1-5")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint --full")
        assert r == 0
        ac(o, """\
Location Constraints:
  Resource: D1
    Constraint: location-D1-rh7-1-INFINITY
      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule)
        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-expr)
      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule-1)
        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-1-expr)
      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule-2)
        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-2-expr)
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule)
        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule-1")
        ac(o,"Removing Rule: location-D1-rh7-1-INFINITY-rule-1\n")
        assert r == 0

        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule-2")
        assert r == 0 and o == "Removing Rule: location-D1-rh7-1-INFINITY-rule-2\n", o

        o, r = pcs(temp_cib, "constraint --full")
        assert r == 0
        ac(o, """\
Location Constraints:
  Resource: D1
    Constraint: location-D1-rh7-1-INFINITY
      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule)
        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-expr)
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule)
        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule")
        assert r == 0 and o == "Removing Constraint: location-D1-rh7-1-INFINITY\n", o

        o, r = pcs(temp_cib, "constraint --full")
        assert r == 0
        ac(o, """\
Location Constraints:
  Resource: D2
    Constraint: location-D2-rh7-2-INFINITY
      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule)
        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr)
          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")

        o,r = pcs("constraint location D1 rule role=master")
        ac (o,"Error: no rule expression was specified\n")
        assert r == 1

        o,r = pcs("constraint location non-existant-resource rule role=master '#uname' eq rh7-1")
        ac (o,"Error: Resource 'non-existant-resource' does not exist\n")
        assert r == 1

        output, returnVal = pcs(temp_cib, "constraint rule add location-D1-rh7-1-INFINITY '#uname' eq rh7-2")
        ac(output, "Error: Unable to find constraint: location-D1-rh7-1-INFINITY\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "constraint rule add location-D2-rh7-2-INFINITY id=123 #uname eq rh7-2")
        ac(output, "Error: invalid rule id '123', '1' is not a valid first character for a rule id\n")
        assert returnVal == 1

    def testLocationBadRules(self):
        o,r = pcs("resource create stateful0 ocf:heartbeat:Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location stateful0 rule role=master '#uname' eq rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o, """\
Location Constraints:
  Resource: stateful0
    Constraint: location-stateful0
      Rule: role=master score=INFINITY  (id:location-stateful0-rule)
        Expression: #uname eq rh7-1  (id:location-stateful0-rule-expr)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        assert r == 0

        o,r = pcs("resource create stateful1 ocf:heartbeat:Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location stateful1 rule rulename '#uname' eq rh7-1 --force")
        ac(o,"Error: 'rulename #uname eq rh7-1' is not a valid rule expression: unexpected '#uname'\n")
        assert r == 1

        o,r = pcs("constraint location stateful1 rule role=master rulename '#uname' eq rh7-1 --force")
        ac(o,"Error: 'rulename #uname eq rh7-1' is not a valid rule expression: unexpected '#uname'\n")
        assert r == 1

        o,r = pcs("constraint location stateful1 rule role=master 25 --force")
        ac(o,"Error: '25' is not a valid rule expression: missing one of 'eq', 'ne', 'lt', 'gt', 'lte', 'gte', 'in_range', 'defined', 'not_defined', 'date-spec'\n")
        assert r == 1

        o,r = pcs("constraint location D1 prefers rh7-1=foo")
        ac(o,"Error: invalid score 'foo', use integer or INFINITY or -INFINITY\n")
        assert r == 1

        o,r = pcs("constraint location D1 avoids rh7-1=")
        ac(o,"Error: invalid score '', use integer or INFINITY or -INFINITY\n")
        assert r == 1

        o,r = pcs("constraint location add location1 D1 rh7-1 bar")
        ac(o,"Error: invalid score 'bar', use integer or INFINITY or -INFINITY\n")
        assert r == 1

        output, returnVal = pcs(temp_cib, "constraint location add loc:dummy D1 rh7-1 100")
        assert returnVal == 1
        ac(output, "Error: invalid constraint id 'loc:dummy', ':' is not a valid character for a constraint id\n")

    def testMasterSlaveConstraint(self):
        os.system("CIB_file="+temp_cib+" cibadmin -R --scope nodes --xml-text '<nodes><node id=\"1\" uname=\"rh7-1\"/><node id=\"2\" uname=\"rh7-2\"/></nodes>'")

        o,r = pcs("resource create dummy1 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create stateful1 ocf:pacemaker:Stateful --master")
        ac(o, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        assert r == 0

        o,r = pcs(
            "resource create stateful2 ocf:pacemaker:Stateful --group statefulG"
        )
        ac(o, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        assert r == 0

        o,r = pcs("resource master statefulG")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location stateful1 prefers rh7-1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location statefulG prefers rh7-1")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location stateful1 rule #uname eq rh7-1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location statefulG rule #uname eq rh7-1")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order stateful1 then dummy1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order dummy1 then statefulG")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order set stateful1 dummy1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint order set dummy1 statefulG")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint colocation add stateful1 with dummy1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint colocation add dummy1 with statefulG")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint colocation set dummy1 stateful1")
        ac(o,"Error: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint colocation set statefulG dummy1")
        ac(o,"Error: statefulG is a master/slave resource, you should use the master id: statefulG-master when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

        o,r = pcs("constraint location stateful1 prefers rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location statefulG rule #uname eq rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order stateful1 then dummy1 --force")
        ac(o,"Adding stateful1 dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)\n")
        assert r == 0

        o,r = pcs("constraint order set stateful1 dummy1 --force")
        ac(o,"Warning: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints\n")
        assert r == 0

        o,r = pcs("constraint colocation add stateful1 with dummy1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint colocation set stateful1 dummy1 --force")
        ac(o,"Warning: stateful1 is a master/slave resource, you should use the master id: stateful1-master when adding constraints\n")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o, """\
Location Constraints:
  Resource: stateful1
    Enabled on: rh7-1 (score:INFINITY) (id:location-stateful1-rh7-1-INFINITY)
  Resource: statefulG
    Constraint: location-statefulG
      Rule: score=INFINITY  (id:location-statefulG-rule)
        Expression: #uname eq rh7-1  (id:location-statefulG-rule-expr)
Ordering Constraints:
  start stateful1 then start dummy1 (kind:Mandatory) (id:order-stateful1-dummy1-mandatory)
  Resource Sets:
    set stateful1 dummy1 (id:pcs_rsc_set_stateful1_dummy1) (id:pcs_rsc_order_set_stateful1_dummy1)
Colocation Constraints:
  stateful1 with dummy1 (score:INFINITY) (id:colocation-stateful1-dummy1-INFINITY)
  Resource Sets:
    set stateful1 dummy1 (id:pcs_rsc_set_stateful1_dummy1-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_stateful1_dummy1)
Ticket Constraints:
""")
        assert r == 0

    def testMasterSlaveConstraintAutocorrect(self):
        output, returnVal = pcs("resource create dummy1 ocf:heartbeat:Dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "resource create stateful1 ocf:pacemaker:Stateful --master"
        )
        ac(output, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "resource create stateful2 ocf:pacemaker:Stateful --group statefulG"
        )
        ac(output, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("resource master statefulG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location stateful1 prefers rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location statefulG prefers rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location stateful1 rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location statefulG rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order stateful1 then dummy1 --autocorrect"
        )
        ac(output, """\
Adding stateful1-master dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order dummy1 then statefulG --autocorrect"
        )
        ac(output, """\
Adding dummy1 statefulG-master (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set stateful1 dummy1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set dummy1 statefulG --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stateful1 with dummy1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add dummy1 with statefulG --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 stateful1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set statefulG dummy1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint --full")
        ac(output, """\
Location Constraints:
  Resource: stateful1-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-stateful1-rh7-1-INFINITY)
    Constraint: location-stateful1-master
      Rule: score=INFINITY  (id:location-stateful1-master-rule)
        Expression: #uname eq rh7-1  (id:location-stateful1-master-rule-expr)
  Resource: statefulG-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-statefulG-rh7-1-INFINITY)
    Constraint: location-statefulG-master
      Rule: score=INFINITY  (id:location-statefulG-master-rule)
        Expression: #uname eq rh7-1  (id:location-statefulG-master-rule-expr)
Ordering Constraints:
  start stateful1-master then start dummy1 (kind:Mandatory) (id:order-stateful1-master-dummy1-mandatory)
  start dummy1 then start statefulG-master (kind:Mandatory) (id:order-dummy1-statefulG-master-mandatory)
  Resource Sets:
    set stateful1-master dummy1 (id:pcs_rsc_set_stateful1-master_dummy1) (id:pcs_rsc_order_set_stateful1_dummy1)
    set dummy1 statefulG-master (id:pcs_rsc_set_dummy1_statefulG-master) (id:pcs_rsc_order_set_dummy1_statefulG)
Colocation Constraints:
  stateful1-master with dummy1 (score:INFINITY) (id:colocation-stateful1-master-dummy1-INFINITY)
  dummy1 with statefulG-master (score:INFINITY) (id:colocation-dummy1-statefulG-master-INFINITY)
  Resource Sets:
    set dummy1 stateful1-master (id:pcs_rsc_set_dummy1_stateful1-master) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_stateful1)
    set statefulG-master dummy1 (id:pcs_rsc_set_statefulG-master_dummy1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_statefulG_dummy1)
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location stateful1 rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-stateful1-master
    Rule: score=INFINITY  (id:location-stateful1-master-rule)
      Expression: #uname eq rh7-1  (id:location-stateful1-master-rule-expr)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint location stateful1 rule #uname eq rh7-1 --autocorrect --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order stateful1 then dummy1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  start stateful1-master then start dummy1 (kind:Mandatory) (id:order-stateful1-master-dummy1-mandatory)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order stateful1 then dummy1 --autocorrect --force"
        )
        ac(output, """\
Adding stateful1-master dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set stateful1 dummy1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set stateful1-master dummy1 (id:pcs_rsc_set_stateful1-master_dummy1) (id:pcs_rsc_order_set_stateful1_dummy1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order set stateful1 dummy1 --autocorrect --force"
        )
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set stateful1-master dummy1 (id:pcs_rsc_set_stateful1-master_dummy1) (id:pcs_rsc_order_set_stateful1_dummy1)",
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stateful1 with dummy1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  stateful1-master with dummy1 (score:INFINITY) (id:colocation-stateful1-master-dummy1-INFINITY)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stateful1 with dummy1 --autocorrect --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 stateful1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set dummy1 stateful1-master (id:pcs_rsc_set_dummy1_stateful1-master) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_stateful1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 stateful1 --autocorrect --force"
        )
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set dummy1 stateful1-master (id:pcs_rsc_set_dummy1_stateful1-master) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_stateful1)",
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint --full")
        ac(output, """\
Location Constraints:
  Resource: stateful1-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-stateful1-rh7-1-INFINITY)
    Constraint: location-stateful1-master
      Rule: score=INFINITY  (id:location-stateful1-master-rule)
        Expression: #uname eq rh7-1  (id:location-stateful1-master-rule-expr)
    Constraint: location-stateful1-master-1
      Rule: score=INFINITY  (id:location-stateful1-master-1-rule)
        Expression: #uname eq rh7-1  (id:location-stateful1-master-1-rule-expr)
  Resource: statefulG-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-statefulG-rh7-1-INFINITY)
    Constraint: location-statefulG-master
      Rule: score=INFINITY  (id:location-statefulG-master-rule)
        Expression: #uname eq rh7-1  (id:location-statefulG-master-rule-expr)
Ordering Constraints:
  start stateful1-master then start dummy1 (kind:Mandatory) (id:order-stateful1-master-dummy1-mandatory)
  start dummy1 then start statefulG-master (kind:Mandatory) (id:order-dummy1-statefulG-master-mandatory)
  start stateful1-master then start dummy1 (kind:Mandatory) (id:order-stateful1-master-dummy1-mandatory-1)
  Resource Sets:
    set stateful1-master dummy1 (id:pcs_rsc_set_stateful1-master_dummy1) (id:pcs_rsc_order_set_stateful1_dummy1)
    set dummy1 statefulG-master (id:pcs_rsc_set_dummy1_statefulG-master) (id:pcs_rsc_order_set_dummy1_statefulG)
    set stateful1-master dummy1 (id:pcs_rsc_set_stateful1-master_dummy1-1) (id:pcs_rsc_order_set_stateful1_dummy1-1)
Colocation Constraints:
  stateful1-master with dummy1 (score:INFINITY) (id:colocation-stateful1-master-dummy1-INFINITY)
  dummy1 with statefulG-master (score:INFINITY) (id:colocation-dummy1-statefulG-master-INFINITY)
  stateful1-master with dummy1 (score:INFINITY) (id:colocation-stateful1-master-dummy1-INFINITY-1)
  Resource Sets:
    set dummy1 stateful1-master (id:pcs_rsc_set_dummy1_stateful1-master) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_stateful1)
    set statefulG-master dummy1 (id:pcs_rsc_set_statefulG-master_dummy1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_statefulG_dummy1)
    set dummy1 stateful1-master (id:pcs_rsc_set_dummy1_stateful1-master-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_stateful1-1)
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

    def testCloneConstraint(self):
        os.system("CIB_file="+temp_cib+" cibadmin -R --scope nodes --xml-text '<nodes><node id=\"1\" uname=\"rh7-1\"/><node id=\"2\" uname=\"rh7-2\"/></nodes>'")

        o,r = pcs("resource create dummy1 ocf:heartbeat:Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create dummy ocf:heartbeat:Dummy --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create dummy2 ocf:heartbeat:Dummy --group dummyG")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource clone dummyG")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location dummy prefers rh7-1")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location dummyG prefers rh7-1")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location dummy rule #uname eq rh7-1")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint location dummyG rule #uname eq rh7-1")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order dummy then dummy1")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order dummy1 then dummyG")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint order set dummy1 dummy")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint order set dummyG dummy1")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint colocation add dummy with dummy1")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint colocation add dummy1 with dummyG")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints. Use --force to override.\n")
        assert r == 1

        o,r = pcs("constraint colocation set dummy1 dummy")
        ac(o,"Error: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint colocation set dummy1 dummyG")
        ac(o,"Error: dummyG is a clone resource, you should use the clone id: dummyG-clone when adding constraints, use --force to override\n")
        assert r == 1

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

        o,r = pcs("constraint location dummy prefers rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location dummyG rule #uname eq rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint order dummy then dummy1 --force")
        ac(o,"Adding dummy dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)\n")
        assert r == 0

        o,r = pcs("constraint order set dummy1 dummy --force")
        ac(o,"Warning: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints\n")
        assert r == 0

        o,r = pcs("constraint colocation add dummy with dummy1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint colocation set dummy1 dummy --force")
        ac(o,"Warning: dummy is a clone resource, you should use the clone id: dummy-clone when adding constraints\n")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o, """\
Location Constraints:
  Resource: dummy
    Enabled on: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
  Resource: dummyG
    Constraint: location-dummyG
      Rule: score=INFINITY  (id:location-dummyG-rule)
        Expression: #uname eq rh7-1  (id:location-dummyG-rule-expr)
Ordering Constraints:
  start dummy then start dummy1 (kind:Mandatory) (id:order-dummy-dummy1-mandatory)
  Resource Sets:
    set dummy1 dummy (id:pcs_rsc_set_dummy1_dummy) (id:pcs_rsc_order_set_dummy1_dummy)
Colocation Constraints:
  dummy with dummy1 (score:INFINITY) (id:colocation-dummy-dummy1-INFINITY)
  Resource Sets:
    set dummy1 dummy (id:pcs_rsc_set_dummy1_dummy-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy)
Ticket Constraints:
""")
        assert r == 0

    def testCloneConstraintAutocorrect(self):
        output, returnVal = pcs("resource create dummy1 ocf:heartbeat:Dummy")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "resource create dummy ocf:heartbeat:Dummy --clone"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "resource create dummy2 ocf:heartbeat:Dummy --group dummyG"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("resource clone dummyG")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location dummy prefers rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location dummyG prefers rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location dummy rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location dummyG rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order dummy then dummy1 --autocorrect"
        )
        ac(output, """\
Adding dummy-clone dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order dummy1 then dummyG --autocorrect"
        )
        ac(output, """\
Adding dummy1 dummyG-clone (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set dummy1 dummy --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set dummyG dummy1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add dummy with dummy1 --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add dummy1 with dummyG --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 dummy --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 dummyG --autocorrect"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
    Constraint: location-dummy-clone
      Rule: score=INFINITY  (id:location-dummy-clone-rule)
        Expression: #uname eq rh7-1  (id:location-dummy-clone-rule-expr)
  Resource: dummyG-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-dummyG-rh7-1-INFINITY)
    Constraint: location-dummyG-clone
      Rule: score=INFINITY  (id:location-dummyG-clone-rule)
        Expression: #uname eq rh7-1  (id:location-dummyG-clone-rule-expr)
Ordering Constraints:
  start dummy-clone then start dummy1 (kind:Mandatory) (id:order-dummy-clone-dummy1-mandatory)
  start dummy1 then start dummyG-clone (kind:Mandatory) (id:order-dummy1-dummyG-clone-mandatory)
  Resource Sets:
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone) (id:pcs_rsc_order_set_dummy1_dummy)
    set dummyG-clone dummy1 (id:pcs_rsc_set_dummyG-clone_dummy1) (id:pcs_rsc_order_set_dummyG_dummy1)
Colocation Constraints:
  dummy-clone with dummy1 (score:INFINITY) (id:colocation-dummy-clone-dummy1-INFINITY)
  dummy1 with dummyG-clone (score:INFINITY) (id:colocation-dummy1-dummyG-clone-INFINITY)
  Resource Sets:
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy)
    set dummy1 dummyG-clone (id:pcs_rsc_set_dummy1_dummyG-clone) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummyG)
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location dummy rule #uname eq rh7-1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-dummy-clone
    Rule: score=INFINITY  (id:location-dummy-clone-rule)
      Expression: #uname eq rh7-1  (id:location-dummy-clone-rule-expr)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint location dummy rule #uname eq rh7-1 --autocorrect --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order dummy then dummy1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  start dummy-clone then start dummy1 (kind:Mandatory) (id:order-dummy-clone-dummy1-mandatory)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order dummy then dummy1 --autocorrect --force"
        )
        ac(output, """\
Adding dummy-clone dummy1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint order set dummy1 dummy --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone) (id:pcs_rsc_order_set_dummy1_dummy)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order set dummy1 dummy --autocorrect --force"
        )
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone) (id:pcs_rsc_order_set_dummy1_dummy)",
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add dummy with dummy1 --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  dummy-clone with dummy1 (score:INFINITY) (id:colocation-dummy-clone-dummy1-INFINITY)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation add dummy with dummy1 --autocorrect --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 dummy --autocorrect"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation set dummy1 dummy --autocorrect --force"
        )
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy)",
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)
    Constraint: location-dummy-clone
      Rule: score=INFINITY  (id:location-dummy-clone-rule)
        Expression: #uname eq rh7-1  (id:location-dummy-clone-rule-expr)
    Constraint: location-dummy-clone-1
      Rule: score=INFINITY  (id:location-dummy-clone-1-rule)
        Expression: #uname eq rh7-1  (id:location-dummy-clone-1-rule-expr)
  Resource: dummyG-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-dummyG-rh7-1-INFINITY)
    Constraint: location-dummyG-clone
      Rule: score=INFINITY  (id:location-dummyG-clone-rule)
        Expression: #uname eq rh7-1  (id:location-dummyG-clone-rule-expr)
Ordering Constraints:
  start dummy-clone then start dummy1 (kind:Mandatory) (id:order-dummy-clone-dummy1-mandatory)
  start dummy1 then start dummyG-clone (kind:Mandatory) (id:order-dummy1-dummyG-clone-mandatory)
  start dummy-clone then start dummy1 (kind:Mandatory) (id:order-dummy-clone-dummy1-mandatory-1)
  Resource Sets:
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone) (id:pcs_rsc_order_set_dummy1_dummy)
    set dummyG-clone dummy1 (id:pcs_rsc_set_dummyG-clone_dummy1) (id:pcs_rsc_order_set_dummyG_dummy1)
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-2) (id:pcs_rsc_order_set_dummy1_dummy-1)
Colocation Constraints:
  dummy-clone with dummy1 (score:INFINITY) (id:colocation-dummy-clone-dummy1-INFINITY)
  dummy1 with dummyG-clone (score:INFINITY) (id:colocation-dummy1-dummyG-clone-INFINITY)
  dummy-clone with dummy1 (score:INFINITY) (id:colocation-dummy-clone-dummy1-INFINITY-1)
  Resource Sets:
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy)
    set dummy1 dummyG-clone (id:pcs_rsc_set_dummy1_dummyG-clone) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummyG)
    set dummy1 dummy-clone (id:pcs_rsc_set_dummy1_dummy-clone-3) setoptions score=INFINITY (id:pcs_rsc_colocation_set_dummy1_dummy-1)
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

    def testMissingRole(self):
        os.system("CIB_file="+temp_cib+" cibadmin -R --scope nodes --xml-text '<nodes><node id=\"1\" uname=\"rh7-1\"/><node id=\"2\" uname=\"rh7-2\"/></nodes>'")
        o,r = pcs("resource create stateful0 ocf:pacemaker:Stateful --master")
        os.system("CIB_file="+temp_cib+" cibadmin -R --scope constraints --xml-text '<constraints><rsc_location id=\"cli-prefer-stateful0-master\" role=\"Master\" rsc=\"stateful0-master\" node=\"rh7-1\" score=\"INFINITY\"/><rsc_location id=\"cli-ban-stateful0-master-on-rh7-1\" rsc=\"stateful0-master\" role=\"Slave\" node=\"rh7-1\" score=\"-INFINITY\"/></constraints>'")

        o,r = pcs("constraint")
        ac(o,"Location Constraints:\n  Resource: stateful0-master\n    Enabled on: rh7-1 (score:INFINITY) (role: Master)\n    Disabled on: rh7-1 (score:-INFINITY) (role: Slave)\nOrdering Constraints:\nColocation Constraints:\nTicket Constraints:\n")
        assert r == 0

    def testManyConstraints(self):
        shutil.copy(large_cib, temp_cib)

        output, returnVal = pcs(temp_cib, "constraint location dummy prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location show resources dummy --full")
        ac(output, "Location Constraints:\n  Resource: dummy\n    Enabled on: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)\n")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location remove location-dummy-rh7-1-INFINITY")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation add dummy1 with dummy2")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation remove dummy1 dummy2")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order dummy1 then dummy2")
        ac(output, "Adding dummy1 dummy2 (kind: Mandatory) (Options: first-action=start then-action=start)\n")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order remove dummy1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location dummy prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location show resources dummy --full")
        ac(output, "Location Constraints:\n  Resource: dummy\n    Enabled on: rh7-1 (score:INFINITY) (id:location-dummy-rh7-1-INFINITY)\n")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint remove location-dummy-rh7-1-INFINITY")
        ac(output, "")
        assert returnVal == 0

    def testConstraintResourceCloneUpdate(self):
        output, returnVal = pcs(temp_cib, "constraint location D1 prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation add D1 with D5")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D1 then D5")
        ac(output, """\
Adding D1 D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D6 then D1")
        ac(output, """\
Adding D6 D1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource clone D1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-D1-rh7-1-INFINITY)
Ordering Constraints:
  start D1-clone then start D5 (kind:Mandatory) (id:order-D1-D5-mandatory)
  start D6 then start D1-clone (kind:Mandatory) (id:order-D6-D1-mandatory)
Colocation Constraints:
  D1-clone with D5 (score:INFINITY) (id:colocation-D1-D5-INFINITY)
Ticket Constraints:
""")
        assert returnVal == 0

    def testConstraintResourceMasterUpdate(self):
        output, returnVal = pcs(temp_cib, "constraint location D1 prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation add D1 with D5")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D1 then D5")
        ac(output, """\
Adding D1 D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D6 then D1")
        ac(output, """\
Adding D6 D1 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource master D1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-D1-rh7-1-INFINITY)
Ordering Constraints:
  start D1-master then start D5 (kind:Mandatory) (id:order-D1-D5-mandatory)
  start D6 then start D1-master (kind:Mandatory) (id:order-D6-D1-mandatory)
Colocation Constraints:
  D1-master with D5 (score:INFINITY) (id:colocation-D1-D5-INFINITY)
Ticket Constraints:
""")
        assert returnVal == 0

    def testConstraintGroupCloneUpdate(self):
        output, returnVal = pcs(temp_cib, "resource group add DG D1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location DG prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation add DG with D5")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order DG then D5")
        ac(output, """\
Adding DG D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D6 then DG")
        ac(output, """\
Adding D6 DG (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource clone DG")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: DG-clone
    Enabled on: rh7-1 (score:INFINITY) (id:location-DG-rh7-1-INFINITY)
Ordering Constraints:
  start DG-clone then start D5 (kind:Mandatory) (id:order-DG-D5-mandatory)
  start D6 then start DG-clone (kind:Mandatory) (id:order-D6-DG-mandatory)
Colocation Constraints:
  DG-clone with D5 (score:INFINITY) (id:colocation-DG-D5-INFINITY)
Ticket Constraints:
""")
        assert returnVal == 0

    def testConstraintGroupMasterUpdate(self):
        output, returnVal = pcs(temp_cib, "resource group add DG D1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint location DG prefers rh7-1")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint colocation add DG with D5")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order DG then D5")
        ac(output, """\
Adding DG D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint order D6 then DG")
        ac(output, """\
Adding D6 DG (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        assert returnVal == 0

        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource master DG")
        ac(output, "")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: DG-master
    Enabled on: rh7-1 (score:INFINITY) (id:location-DG-rh7-1-INFINITY)
Ordering Constraints:
  start DG-master then start D5 (kind:Mandatory) (id:order-DG-D5-mandatory)
  start D6 then start DG-master (kind:Mandatory) (id:order-D6-DG-mandatory)
Colocation Constraints:
  DG-master with D5 (score:INFINITY) (id:colocation-DG-D5-INFINITY)
Ticket Constraints:
""")
        assert returnVal == 0

    def testRemoteNodeConstraintsRemove(self):
        # constraints referencing the remote node's name,
        # deleting the remote node resource
        output, returnVal = pcs(
            temp_cib,
            'resource create vm-guest1 ocf:heartbeat:VirtualDomain hypervisor="qemu:///system" config="/root/guest1.xml" meta remote-node=guest1'
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D1 prefers node1=100"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D1 prefers guest1=200"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D2 avoids node2=300"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D2 avoids guest1=400"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Enabled on: node1 (score:100) (id:location-D1-node1-100)
    Enabled on: guest1 (score:200) (id:location-D1-guest1-200)
  Resource: D2
    Disabled on: node2 (score:-300) (id:location-D2-node2--300)
    Disabled on: guest1 (score:-400) (id:location-D2-guest1--400)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource delete vm-guest1")
        ac(output, """\
Removing Constraint - location-D1-guest1-200
Removing Constraint - location-D2-guest1--400
Deleting Resource - vm-guest1
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Enabled on: node1 (score:100) (id:location-D1-node1-100)
  Resource: D2
    Disabled on: node2 (score:-300) (id:location-D2-node2--300)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        # constraints referencing the remote node's name,
        # removing the remote node
        output, returnVal = pcs(
            temp_cib,
            'resource create vm-guest1 ocf:heartbeat:VirtualDomain hypervisor="qemu:///system" config="/root/guest1.xml" meta remote-node=guest1'
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D1 prefers guest1=200"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location D2 avoids guest1=400"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Enabled on: node1 (score:100) (id:location-D1-node1-100)
    Enabled on: guest1 (score:200) (id:location-D1-guest1-200)
  Resource: D2
    Disabled on: node2 (score:-300) (id:location-D2-node2--300)
    Disabled on: guest1 (score:-400) (id:location-D2-guest1--400)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "cluster remote-node remove guest1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Enabled on: node1 (score:100) (id:location-D1-node1-100)
  Resource: D2
    Disabled on: node2 (score:-300) (id:location-D2-node2--300)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource delete vm-guest1")
        ac(output, """\
Deleting Resource - vm-guest1
""")
        self.assertEqual(0, returnVal)

        # constraints referencing the remote node resource
        # deleting the remote node resource
        output, returnVal = pcs(
            temp_cib,
            'resource create vm-guest1 ocf:heartbeat:VirtualDomain hypervisor="qemu:///system" config="/root/guest1.xml" meta remote-node=guest1'
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "constraint location vm-guest1 prefers node1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource delete vm-guest1")
        ac(output, """\
Removing Constraint - location-vm-guest1-node1-INFINITY
Deleting Resource - vm-guest1
""")
        self.assertEqual(0, returnVal)

    def testDuplicateOrder(self):
        output, returnVal = pcs("constraint order D1 then D2")
        ac(output, """\
Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order D1 then D2")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint order D1 then D2 --force")
        ac(output, """\
Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order start D1 then start D2")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory)
  start D1 then start D2 (kind:Mandatory) (id:order-D1-D2-mandatory-1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order start D1 then start D2 --force"
        )
        ac(output, """\
Adding D1 D2 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order start D2 then start D5")
        ac(output, """\
Adding D2 D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order start D2 then start D5")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  start D2 then start D5 (kind:Mandatory) (id:order-D2-D5-mandatory)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint order start D2 then start D5 --force"
        )
        ac(output, """\
Adding D2 D5 (kind: Mandatory) (Options: first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order stop D5 then stop D6")
        ac(output, """\
Adding D5 D6 (kind: Mandatory) (Options: first-action=stop then-action=stop)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order stop D5 then stop D6")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  stop D5 then stop D6 (kind:Mandatory) (id:order-D5-D6-mandatory)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint order stop D5 then stop D6 --force")
        ac(output, """\
Adding D5 D6 (kind: Mandatory) (Options: first-action=stop then-action=stop)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
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
""")
        self.assertEqual(0, returnVal)

    def testDuplicateColocation(self):
        output, returnVal = pcs("constraint colocation add D1 with D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint colocation add D1 with D2")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint colocation add D1 with D2 50")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation add D1 with D2 50 --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add started D1 with started D2"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  D1 with D2 (score:INFINITY) (id:colocation-D1-D2-INFINITY)
  D1 with D2 (score:50) (id:colocation-D1-D2-50)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation add started D1 with started D2 --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add started D2 with started D5"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stopped D2 with stopped D5"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stopped D2 with stopped D5"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  D2 with D5 (score:INFINITY) (rsc-role:Stopped) (with-rsc-role:Stopped) (id:colocation-D2-D5-INFINITY-1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation add stopped D2 with stopped D5 --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
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
""")

    def testDuplicateSetConstraints(self):
        output, returnVal = pcs("constraint order set D1 D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order set D1 D2")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set D1 D2 (id:pcs_rsc_set_D1_D2) (id:pcs_rsc_order_set_D1_D2)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint order set D1 D2 --force")
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set D1 D2 (id:pcs_rsc_set_D1_D2) (id:pcs_rsc_order_set_D1_D2)",
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order set D1 D2 set D5 D6")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order set D1 D2 set D5 D6")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set D1 D2 (id:pcs_rsc_set_D1_D2-2) set D5 D6 (id:pcs_rsc_set_D5_D6) (id:pcs_rsc_order_set_D1_D2_set_D5_D6)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint order set D1 D2 set D5 D6 --force")
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set D1 D2 (id:pcs_rsc_set_D1_D2-2) set D5 D6 (id:pcs_rsc_set_D5_D6) (id:pcs_rsc_order_set_D1_D2_set_D5_D6)",
        ))
        self.assertEqual(0, returnVal)


        output, returnVal = pcs("constraint colocation set D1 D2")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint colocation set D1 D2")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set D1 D2 (id:pcs_rsc_set_D1_D2-4) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs("constraint colocation set D1 D2 --force")
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set D1 D2 (id:pcs_rsc_set_D1_D2-4) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2)"
        ))
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint colocation set D1 D2 set D5 D6")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint colocation set D1 D2 set D5 D6")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  set D1 D2 (id:pcs_rsc_set_D1_D2-6) set D5 D6 (id:pcs_rsc_set_D5_D6-2) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2_set_D5_D6)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint colocation set D1 D2 set D5 D6 --force"
        )
        ac(output, console_report(
            "Warning: duplicate constraint already exists",
            "  set D1 D2 (id:pcs_rsc_set_D1_D2-6) set D5 D6 (id:pcs_rsc_set_D5_D6-2) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2_set_D5_D6)"
        ))
        self.assertEqual(0, returnVal)


        output, returnVal = pcs("constraint colocation set D6 D1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint order set D6 D1")
        ac(output, "")
        self.assertEqual(0, returnVal)


        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
  Resource Sets:
    set D1 D2 (id:pcs_rsc_set_D1_D2) (id:pcs_rsc_order_set_D1_D2)
    set D1 D2 (id:pcs_rsc_set_D1_D2-1) (id:pcs_rsc_order_set_D1_D2-1)
    set D1 D2 (id:pcs_rsc_set_D1_D2-2) set D5 D6 (id:pcs_rsc_set_D5_D6) (id:pcs_rsc_order_set_D1_D2_set_D5_D6)
    set D1 D2 (id:pcs_rsc_set_D1_D2-3) set D5 D6 (id:pcs_rsc_set_D5_D6-1) (id:pcs_rsc_order_set_D1_D2_set_D5_D6-1)
    set D6 D1 (id:pcs_rsc_set_D6_D1-1) (id:pcs_rsc_order_set_D6_D1)
Colocation Constraints:
  Resource Sets:
    set D1 D2 (id:pcs_rsc_set_D1_D2-4) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2)
    set D1 D2 (id:pcs_rsc_set_D1_D2-5) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2-1)
    set D1 D2 (id:pcs_rsc_set_D1_D2-6) set D5 D6 (id:pcs_rsc_set_D5_D6-2) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2_set_D5_D6)
    set D1 D2 (id:pcs_rsc_set_D1_D2-7) set D5 D6 (id:pcs_rsc_set_D5_D6-3) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D1_D2_set_D5_D6-1)
    set D6 D1 (id:pcs_rsc_set_D6_D1) setoptions score=INFINITY (id:pcs_rsc_colocation_set_D6_D1)
Ticket Constraints:
""")

    def testDuplicateLocationRules(self):
        output, returnVal = pcs("constraint location D1 rule #uname eq node1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint location D1 rule #uname eq node1")
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D1
    Rule: score=INFINITY  (id:location-D1-rule)
      Expression: #uname eq node1  (id:location-D1-rule-expr)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint location D1 rule #uname eq node1 --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs("constraint location D2 rule #uname eq node1")
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location D2 rule #uname eq node1 or #uname eq node2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            "constraint location D2 rule #uname eq node1 or #uname eq node2"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D2-1
    Rule: boolean-op=or score=INFINITY  (id:location-D2-1-rule)
      Expression: #uname eq node1  (id:location-D2-1-rule-expr)
      Expression: #uname eq node2  (id:location-D2-1-rule-expr-1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint location D2 rule #uname eq node2 or #uname eq node1"
        )
        ac(output, """\
Error: duplicate constraint already exists, use --force to override
  Constraint: location-D2-1
    Rule: boolean-op=or score=INFINITY  (id:location-D2-1-rule)
      Expression: #uname eq node1  (id:location-D2-1-rule-expr)
      Expression: #uname eq node2  (id:location-D2-1-rule-expr-1)
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            "constraint location D2 rule #uname eq node2 or #uname eq node1 --force"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Constraint: location-D1
      Rule: score=INFINITY  (id:location-D1-rule)
        Expression: #uname eq node1  (id:location-D1-rule-expr)
    Constraint: location-D1-1
      Rule: score=INFINITY  (id:location-D1-1-rule)
        Expression: #uname eq node1  (id:location-D1-1-rule-expr)
  Resource: D2
    Constraint: location-D2
      Rule: score=INFINITY  (id:location-D2-rule)
        Expression: #uname eq node1  (id:location-D2-rule-expr)
    Constraint: location-D2-1
      Rule: boolean-op=or score=INFINITY  (id:location-D2-1-rule)
        Expression: #uname eq node1  (id:location-D2-1-rule-expr)
        Expression: #uname eq node2  (id:location-D2-1-rule-expr-1)
    Constraint: location-D2-2
      Rule: boolean-op=or score=INFINITY  (id:location-D2-2-rule)
        Expression: #uname eq node2  (id:location-D2-2-rule-expr)
        Expression: #uname eq node1  (id:location-D2-2-rule-expr-1)
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

    def testConstraintsCustomId(self):
        output, returnVal = pcs(
            temp_cib,
            "constraint colocation add D1 with D2 id=1id"
        )
        ac(output, """\
Error: invalid constraint id '1id', '1' is not a valid first character for a constraint id
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation add D1 with D2 id=id1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation add D1 with D2 id=id1"
        )
        ac(output, """\
Error: id 'id1' is already in use, please specify another one
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation add D2 with D1 100 id=id2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation set D1 D2 setoptions id=3id"
        )
        ac(output, """\
Error: invalid constraint id '3id', '3' is not a valid first character for a constraint id
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation set D1 D2 setoptions id=id3"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation set D1 D2 setoptions id=id3"
        )
        ac(output, "Error: 'id3' already exists\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint colocation set D2 D1 setoptions score=100 id=id4"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions id=5id"
        )
        ac(output, """\
Error: invalid constraint id '5id', '5' is not a valid first character for a constraint id
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions id=id5"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order set D1 D2 setoptions id=id5"
        )
        ac(output, "Error: 'id5' already exists\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order set D2 D1 setoptions kind=Mandatory id=id6"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order D1 then D2 id=7id"
        )
        ac(output, """\
Error: invalid constraint id '7id', '7' is not a valid first character for a constraint id
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order D1 then D2 id=id7"
        )
        ac(output, """\
Adding D1 D2 (kind: Mandatory) (Options: id=id7 first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order D1 then D2 id=id7"
        )
        ac(output, """\
Error: id 'id7' is already in use, please specify another one
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint order D2 then D1 kind=Optional id=id8"
        )
        ac(output, """\
Adding D2 D1 (kind: Optional) (Options: id=id8 first-action=start then-action=start)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location D1 rule constraint-id=9id defined pingd"
        )
        ac(output, """\
Error: invalid constraint id '9id', '9' is not a valid first character for a constraint id
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location D1 rule constraint-id=id9 defined pingd"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location D1 rule constraint-id=id9 defined pingd"
        )
        ac(output, """\
Error: id 'id9' is already in use, please specify another one
""")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location D2 rule score=100 constraint-id=id10 id=rule1 defined pingd"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: D1
    Constraint: id9
      Rule: score=INFINITY  (id:id9-rule)
        Expression: defined pingd  (id:id9-rule-expr)
  Resource: D2
    Constraint: id10
      Rule: score=100  (id:rule1)
        Expression: defined pingd  (id:rule1-expr)
Ordering Constraints:
  start D1 then start D2 (kind:Mandatory) (id:id7)
  start D2 then start D1 (kind:Optional) (id:id8)
  Resource Sets:
    set D1 D2 (id:pcs_rsc_set_D1_D2-1) (id:id5)
    set D2 D1 (id:pcs_rsc_set_D2_D1-1) setoptions kind=Mandatory (id:id6)
Colocation Constraints:
  D1 with D2 (score:INFINITY) (id:id1)
  D2 with D1 (score:100) (id:id2)
  Resource Sets:
    set D1 D2 (id:pcs_rsc_set_D1_D2) setoptions score=INFINITY (id:id3)
    set D2 D1 (id:pcs_rsc_set_D2_D1) setoptions score=100 (id:id4)
Ticket Constraints:
""")
        self.assertEqual(0, returnVal)

class ConstraintBaseTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)
        self.assert_pcs_success('resource create A ocf:heartbeat:Dummy')
        self.assert_pcs_success('resource create B ocf:heartbeat:Dummy')


class CommonCreateWithSet(ConstraintBaseTest):
    def test_refuse_when_resource_does_not_exist(self):
        self.assert_pcs_fail(
            'constraint ticket set A C setoptions ticket=T',
            ["Error: Resource 'C' does not exist"]
        )

class TicketCreateWithSet(ConstraintBaseTest):
    def test_create_ticket(self):
        self.assert_pcs_success(
            'constraint ticket set A B setoptions ticket=T loss-policy=fence'
        )

    def test_can_skip_loss_policy(self):
        self.assert_pcs_success('constraint ticket set A B setoptions ticket=T')
        self.assert_pcs_success('constraint ticket show', stdout_full=[
            "Ticket Constraints:",
            "  Resource Sets:",
            "    set A B setoptions ticket=T",
        ])

    def test_refuse_bad_loss_policy(self):
        self.assert_pcs_fail(
            'constraint ticket set A B setoptions ticket=T loss-policy=none',
            ["Error: 'none' is not a valid loss-policy value, use fence, stop, freeze, demote"]
        )

    def test_refuse_when_ticket_option_is_missing(self):
        self.assert_pcs_fail(
            'constraint ticket set A B setoptions loss-policy=fence',
            ["Error: required option 'ticket' is missing"]
        )

    def test_refuse_when_option_is_invalid(self):
        self.assert_pcs_fail(
            'constraint ticket set A B setoptions loss-policy',
            stdout_start=["Error: missing value of 'loss-policy' option"]
        )

class TicketAdd(ConstraintBaseTest):
    def test_create_ticket(self):
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence'
        )
        self.assert_pcs_success('constraint ticket show', stdout_full=[
            "Ticket Constraints:",
            "  Master A loss-policy=fence ticket=T",
        ])

    def test_refuse_noexistent_resource_id(self):
        self.assert_pcs_fail(
            'constraint ticket add T master AA loss-policy=fence',
            ["Error: Resource 'AA' does not exist"]
        )

    def test_refuse_invalid_role(self):
        self.assert_pcs_fail(
            'constraint ticket add T bad-role A loss-policy=fence',
            ["Error: 'bad-role' is not a valid rsc-role value, use Stopped, Started, Master, Slave"]
        )

    def test_refuse_duplicate_ticket(self):
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence'
        )
        self.assert_pcs_fail(
            'constraint ticket add T master A loss-policy=fence',
            [
                'Error: duplicate constraint already exists, use --force to override',
                '  Master A loss-policy=fence ticket=T (id:ticket-T-A-Master)'
            ]
        )

    def test_accept_duplicate_ticket_with_force(self):
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence'
        )
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence --force', [
                "Warning: duplicate constraint already exists",
                "  Master A loss-policy=fence ticket=T (id:ticket-T-A-Master)"
            ]
        )
        self.assert_pcs_success('constraint ticket show', stdout_full=[
            "Ticket Constraints:",
            "  Master A loss-policy=fence ticket=T",
            "  Master A loss-policy=fence ticket=T",
        ])

class TicketRemoveTest(ConstraintBaseTest):
    def test_remove_multiple_tickets(self):
        #fixture
        self.assert_pcs_success('constraint ticket add T A')
        self.assert_pcs_success(
            'constraint ticket add T A --force',
            stdout_full=[
                "Warning: duplicate constraint already exists",
                "  A ticket=T (id:ticket-T-A)"
            ]
        )
        self.assert_pcs_success(
            'constraint ticket set A B setoptions ticket=T'
        )
        self.assert_pcs_success(
            'constraint ticket set A setoptions ticket=T'
        )
        self.assert_pcs_success("constraint ticket show", stdout_full=[
            "Ticket Constraints:",
            "  A ticket=T",
            "  A ticket=T",
            "  Resource Sets:",
            "    set A B setoptions ticket=T",
            "    set A setoptions ticket=T",
        ])

        #test
        self.assert_pcs_success("constraint ticket remove T A")

        self.assert_pcs_success("constraint ticket show", stdout_full=[
            "Ticket Constraints:",
            "  Resource Sets:",
            "    set B setoptions ticket=T",
        ])

    def test_fail_when_no_matching_ticket_constraint_here(self):
        self.assert_pcs_success("constraint ticket show", stdout_full=[
            "Ticket Constraints:",
        ])
        self.assert_pcs_fail("constraint ticket remove T A", [
            "Error: no matching ticket constraint found"
        ])


class TicketShow(ConstraintBaseTest):
    def test_show_set(self):
        self.assert_pcs_success('constraint ticket set A B setoptions ticket=T')
        self.assert_pcs_success(
            'constraint ticket add T master A loss-policy=fence'
        )
        self.assert_pcs_success(
            'constraint ticket show',
            [
                "Ticket Constraints:",
                "  Master A loss-policy=fence ticket=T",
                "  Resource Sets:",
                "    set A B setoptions ticket=T",
            ]
        )
