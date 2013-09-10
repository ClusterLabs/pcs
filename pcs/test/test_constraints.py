import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs,ac

empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ConstraintTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.setupClusterA(temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource and clones
    def setupClusterA(self,temp_cib):
        line = "resource create D1 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D2 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D3 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D4 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D5 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D6 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D7 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D8 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D9 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create D0 Dummy"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create M1 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create M2 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource create M3 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M4 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M5 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M6 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M7 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M8 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M9 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == "",[returnVal, output]

        line = "resource create M10 Dummy --master"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource group add G1 D0"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0 and output == ""

        line = "resource group add G2 D1 D2"
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
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D2 rule score=-INFINITY '#uname' eq c00n04")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=pingd defined pingd")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D4 rule score=INFINITY date start=2005-001 gt")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D5 rule score=INFINITY date start=2005-001 end=2006-001 in_range")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint location D6 rule score=INFINITY date-spec operation=date_spec years=2005")
        assert output == "", [output]
        assert returnVal == 0

# We don't support and/or yet
#        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=-INFINITY not_defined pingd or pingd lte 0")
#        assert returnVal == 0
#        assert output == "", [output]

#        output, returnVal = pcs(temp_cib, "constraint location D3 rule score=-INFINITY not_defined pingd and pingd lte 0")
#        assert returnVal == 0
#        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0
        ac (output,'Location Constraints:\n  Resource: D1\n      Rule: score=222  (id:location-D1-rule) \n        Expression: #uname eq c00n03  (id:location-D1-rule-expr) \n  Resource: D2\n      Rule: score=-INFINITY  (id:location-D2-rule) \n        Expression: #uname eq c00n04  (id:location-D2-rule-expr) \n  Resource: D3\n      Rule: score-attribute=pingd  (id:location-D3-rule) \n        Expression: defined pingd  (id:location-D3-rule-expr) \n  Resource: D4\n      Rule: score=INFINITY  (id:location-D4-rule) \n        Expression: start=2005-001 operation=gt  (id:location-D4-rule-expr) \n  Resource: D5\n      Rule: score=INFINITY  (id:location-D5-rule) \n        Expression: start=2005-001 operation=in_range end=2006-001  (id:location-D5-rule-expr) \n  Resource: D6\n      Rule: score=INFINITY  (id:location-D6-rule) \n        Expression:  (id:location-D6-rule-expr) \n          Date Spec: years=2005  (id:location-D6-rule-expr-datespec) \nOrdering Constraints:\nColocation Constraints:\n')
#        assert output == 'Location Constraints:\n  Resource: D6\n  Resource: D4\n  Resource: D5\n  Resource: D2\n  Resource: D3\n  Resource: D1\n    Location Constraint: Resource D3\n      Rule: score-attribute=pingd  \n        Expression: attribute=pingd operation=defined  \n    Location Constraint: Resource D2\n      Rule: score=-INFINITY  \n        Expression: attribute=#uname operation=eq value=c00n04  \n    Location Constraint: Resource D1\n      Rule: score=222  \n        Expression: attribute=#uname operation=eq value=c00n03  \n    Location Constraint: Resource D6\n      Rule: score=INFINITY  \n        Expression: operation=date_spec  \n          Date Spec: years=2005  \n    Location Constraint: Resource D5\n      Rule: score=INFINITY  \n        Expression: start=2005-001 operation=in_range end=2006-001  \n    Location Constraint: Resource D4\n      Rule: score=INFINITY  \n        Expression: start=2005-001 operation=gt  \nOrdering Constraints:\nColocation Constraints:\n', [output]

    def testEmptyConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint")
        assert returnVal == 0 and output == "Location Constraints:\nOrdering Constraints:\nColocation Constraints:\n", output

    def testAllConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint order D4 then D5")
        assert returnVal == 0 and output == "Adding D4 D5 (kind: Mandatory) (Options: first-action=start then-action=start)\n", output

        output, returnVal = pcs(temp_cib, "constraint colocation add D4 with D5")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint --full")
        assert returnVal == 0 and output == "Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)\nOrdering Constraints:\n  start D4 then start D5 (Mandatory) (id:order-D4-D5-mandatory)\nColocation Constraints:\n  D4 with D5 (INFINITY) (id:colocation-D4-D5-INFINITY)\n", output

        output, returnVal = pcs(temp_cib, "constraint show --full")
        assert returnVal == 0 and output == "Location Constraints:\n  Resource: D5\n    Enabled on: node1 (score:INFINITY) (id:location-D5-node1-INFINITY)\nOrdering Constraints:\n  start D4 then start D5 (Mandatory) (id:order-D4-D5-mandatory)\nColocation Constraints:\n  D4 with D5 (INFINITY) (id:colocation-D4-D5-INFINITY)\n", output

    def testLocationConstraints(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint location D5 avoids node2")
        assert returnVal == 0 and output == "", output

        output, returnVal = pcs(temp_cib, "constraint location add location-D5-node1-INFINITY ")
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs constraint"), output

    def testConstraintRemoval(self):
        output, returnVal = pcs(temp_cib, "constraint location D5 prefers node1")
        assert returnVal == 0 and output == "", output
        
        output, returnVal = pcs(temp_cib, "constraint remove blahblah")
        assert returnVal == 1 and output.startswith("Error: Unable to find constraint - 'blahblah'"), output

    def testColocationConstraints(self):
        o, r = pcs(temp_cib, "constraint colocation add D1 D3")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add D1 D2 100")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add D4 with D5 100")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add master M1 with master M2")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add M3 with M4")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add slave M5 with started M6 500")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add M7 with Master M8")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint colocation add Slave M9 with M10")
        assert r == 0 and o == "", o

        o, r = pcs(temp_cib, "constraint")
        assert r == 0 and o == 'Location Constraints:\nOrdering Constraints:\nColocation Constraints:\n  D1 with D3\n  D1 with D2 (100)\n  D4 with D5 (100)\n  M1 with M2 (rsc-role:Master) (with-rsc-role:Master)\n  M3 with M4\n  M5 with M6 (500) (rsc-role:Slave) (with-rsc-role:Started)\n  M7 with M8 (rsc-role:Started) (with-rsc-role:Master)\n  M9 with M10 (rsc-role:Slave) (with-rsc-role:Started)\n', [o]
        
    def testColocationSets(self):
        o, r = pcs(temp_cib, "constraint colocation set D5 D6 D7 sequential=false set D8 D9 sequential=true setoptions score=INFINITY ")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint colocation set D5 D6")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint colocation set D5 D6 set D7 D8 set D8 D9")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint colocation --full")
        ac(o,"Colocation Constraints:\n  Resource Sets:\n    set D5 D6 D7 sequential=false (id:pcs_rsc_set) set D8 D9 sequential=true (id:pcs_rsc_set-1) setoptions score=INFINITY (id:pcs_rsc_colocation)\n    set D5 D6 (id:pcs_rsc_set-2) (id:pcs_rsc_colocation-1)\n    set D5 D6 (id:pcs_rsc_set-3) set D7 D8 (id:pcs_rsc_set-4) set D8 D9 (id:pcs_rsc_set-5) (id:pcs_rsc_colocation-2)\n")
        assert r == 0

        o, r = pcs(temp_cib, "constraint remove pcs_rsc_colocation-1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint colocation --full")
        ac(o,"Colocation Constraints:\n  Resource Sets:\n    set D5 D6 D7 sequential=false (id:pcs_rsc_set) set D8 D9 sequential=true (id:pcs_rsc_set-1) setoptions score=INFINITY (id:pcs_rsc_colocation)\n    set D5 D6 (id:pcs_rsc_set-3) set D7 D8 (id:pcs_rsc_set-4) set D8 D9 (id:pcs_rsc_set-5) (id:pcs_rsc_colocation-2)\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource delete D5")
        ac(o,"Removing D5 from set pcs_rsc_set\nRemoving D5 from set pcs_rsc_set-3\nDeleting Resource - D5\n")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource delete D6")
        ac(o,"Removing D6 from set pcs_rsc_set\nRemoving D6 from set pcs_rsc_set-3\nRemoving set pcs_rsc_set-3\nDeleting Resource - D6\n")
        assert r == 0
        
        o, r = pcs(temp_cib, "constraint ref D7")
        ac(o,"Resource: D7\n  pcs_rsc_colocation\n  pcs_rsc_colocation-2\n")
        assert r == 0
        
        o, r = pcs(temp_cib, "constraint ref D8")
        ac(o,"Resource: D8\n  pcs_rsc_colocation\n  pcs_rsc_colocation-2\n")
        assert r == 0
        
    def testOrderSets(self):
        o, r = pcs(temp_cib, "constraint order set D5 D6 D7 sequential=false set D8 D9 sequential=true")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "constraint order set D5 D6")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order set D5 D6 set D7 D8 set D8 D9")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order --full")
        assert r == 0
        ac(o,"Ordering Constraints:\n  Resource Sets:\n    set D5 D6 D7 sequential=false (id:pcs_rsc_set) set D8 D9 sequential=true (id:pcs_rsc_set-1) (id:pcs_rsc_order)\n    set D5 D6 (id:pcs_rsc_set-2) (id:pcs_rsc_order-1)\n    set D5 D6 (id:pcs_rsc_set-3) set D7 D8 (id:pcs_rsc_set-4) set D8 D9 (id:pcs_rsc_set-5) (id:pcs_rsc_order-2)\n")

        o, r = pcs(temp_cib, "constraint remove pcs_rsc_order-1")
        assert r == 0
        ac(o,"")

        o, r = pcs(temp_cib, "constraint order --full")
        assert r == 0
        ac(o,"Ordering Constraints:\n  Resource Sets:\n    set D5 D6 D7 sequential=false (id:pcs_rsc_set) set D8 D9 sequential=true (id:pcs_rsc_set-1) (id:pcs_rsc_order)\n    set D5 D6 (id:pcs_rsc_set-3) set D7 D8 (id:pcs_rsc_set-4) set D8 D9 (id:pcs_rsc_set-5) (id:pcs_rsc_order-2)\n")
        
        o, r = pcs(temp_cib, "resource delete D5")
        ac(o,"Removing D5 from set pcs_rsc_set\nRemoving D5 from set pcs_rsc_set-3\nDeleting Resource - D5\n")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource delete D6")
        ac(o,"Removing D6 from set pcs_rsc_set\nRemoving D6 from set pcs_rsc_set-3\nRemoving set pcs_rsc_set-3\nDeleting Resource - D6\n")
        assert r == 0

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
        ac(o,'Location Constraints:\n  Resource: D1\n      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule) \n        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-expr) \n      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule-1) \n        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-1-expr) \n      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule-2) \n        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-2-expr) \n  Resource: D2\n      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule) \n        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr) \n          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec) \nOrdering Constraints:\nColocation Constraints:\n')
        
        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule-1")
        ac(o,"Removing Rule: location-D1-rh7-1-INFINITY-rule-1\n")
        assert r == 0
        
        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule-2")
        assert r == 0 and o == "Removing Rule: location-D1-rh7-1-INFINITY-rule-2\n", o

        o, r = pcs(temp_cib, "constraint --full")
        assert r == 0
        ac (o,'Location Constraints:\n  Resource: D1\n      Rule: score=INFINITY  (id:location-D1-rh7-1-INFINITY-rule) \n        Expression: #uname eq rh7-1  (id:location-D1-rh7-1-INFINITY-rule-expr) \n  Resource: D2\n      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule) \n        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr) \n          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec) \nOrdering Constraints:\nColocation Constraints:\n')

        o, r = pcs(temp_cib, "constraint rule remove location-D1-rh7-1-INFINITY-rule")
        assert r == 0 and o == "Removing Constraint: location-D1-rh7-1-INFINITY\n", o

        o, r = pcs(temp_cib, "constraint --full")
        assert r == 0
        ac (o,'Location Constraints:\n  Resource: D2\n      Rule: score=INFINITY  (id:location-D2-rh7-2-INFINITY-rule) \n        Expression:  (id:location-D2-rh7-2-INFINITY-rule-expr) \n          Date Spec: hours=9-16 weekdays=1-5  (id:location-D2-rh7-2-INFINITY-rule-expr-datespec) \nOrdering Constraints:\nColocation Constraints:\n')

    def testLocationBadRules(self):
        o,r = pcs("resource create stateful0 Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location stateful0 rule role=master '#uname' eq rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint --full")
        ac(o,"Location Constraints:\n  Resource: stateful0\n      Rule: score=INFINITY role=master  (id:location-stateful0-rule) \n        Expression: #uname eq rh7-1  (id:location-stateful0-rule-expr) \nOrdering Constraints:\nColocation Constraints:\n")
        assert r == 0

        o,r = pcs("resource create stateful1 Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location stateful1 rule rulename '#uname' eq rh7-1")
        ac(o,"Error: 'rulename #uname eq rh7-1' is not a valid rule expression\n")
        assert r == 1

        o,r = pcs("constraint location stateful1 rule role=master rulename '#uname' eq rh7-1")
        ac(o,"Error: 'rulename #uname eq rh7-1' is not a valid rule expression\n")
        assert r == 1

if __name__ == "__main__":
    unittest.main()

