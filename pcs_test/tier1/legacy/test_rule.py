from unittest import TestCase

from pcs_test.tools.assertions import ac
from pcs_test.tools.misc import (
    get_test_resource as rc,
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.misc import skip_unless_crm_rule
from pcs_test.tools.pcs_runner import pcs

# pylint: disable=invalid-name
# pylint: disable=line-too-long

empty_cib = rc("cib-empty.xml")


class DomRuleAddTest(TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_rule_dom_rule_add")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        output, returnVal = pcs(
            self.temp_cib.name, "resource create dummy1 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0 and output == ""

    def tearDown(self):
        self.temp_cib.close()

    @skip_unless_crm_rule
    def test_success(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule #uname eq node1",
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule id=MyRule score=100 role=master #uname eq node2",
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule id=complexRule (#uname eq node3 and foo gt version 1.2) or (date-spec hours=12-23 weekdays=1-5 and date in_range 2014-07-26 to duration months=1)",
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "constraint location show --full"
        )
        ac(
            output,
            """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score=INFINITY (id:location-dummy1-rule)
        Expression: #uname eq node1 (id:location-dummy1-rule-expr)
    Constraint: location-dummy1-1
      Rule: role=master score=100 (id:MyRule)
        Expression: #uname eq node2 (id:MyRule-expr)
    Constraint: location-dummy1-2
      Rule: boolean-op=or score=INFINITY (id:complexRule)
        Rule: boolean-op=and score=0 (id:complexRule-rule)
          Expression: #uname eq node3 (id:complexRule-rule-expr)
          Expression: foo gt version 1.2 (id:complexRule-rule-expr-1)
        Rule: boolean-op=and score=0 (id:complexRule-rule-1)
          Expression: (id:complexRule-rule-1-expr)
            Date Spec: hours=12-23 weekdays=1-5 (id:complexRule-rule-1-expr-datespec)
          Expression: date in_range 2014-07-26 to duration (id:complexRule-rule-1-expr-1)
            Duration: months=1 (id:complexRule-rule-1-expr-1-duration)
""",
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(self.temp_cib.name, "constraint location show")
        ac(
            output,
            """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score=INFINITY
        Expression: #uname eq node1
    Constraint: location-dummy1-1
      Rule: role=master score=100
        Expression: #uname eq node2
    Constraint: location-dummy1-2
      Rule: boolean-op=or score=INFINITY
        Rule: boolean-op=and score=0
          Expression: #uname eq node3
          Expression: foo gt version 1.2
        Rule: boolean-op=and score=0
          Expression:
            Date Spec: hours=12-23 weekdays=1-5
          Expression: date in_range 2014-07-26 to duration
            Duration: months=1
""",
        )
        self.assertEqual(0, returnVal)

    @skip_unless_crm_rule
    def test_invalid_score(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule score=pingd defined pingd",
        )
        ac(
            output,
            "Warning: invalid score 'pingd', setting score-attribute=pingd "
            "instead\n",
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "constraint location show --full"
        )
        ac(
            output,
            """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score-attribute=pingd (id:location-dummy1-rule)
        Expression: defined pingd (id:location-dummy1-rule-expr)
""",
        )
        self.assertEqual(0, returnVal)

    def test_invalid_rule(self):
        output, returnVal = pcs(
            self.temp_cib.name, "constraint location dummy1 rule score=100"
        )
        ac(output, "Error: no rule expression was specified\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "constraint location dummy1 rule #uname eq"
        )
        ac(
            output,
            "Error: '#uname eq' is not a valid rule expression: unexpected end "
            "of rule\n",
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule string #uname eq node1",
        )
        ac(
            output,
            "Error: 'string #uname eq node1' is not a valid rule expression: "
            "unexpected 'string' before 'eq'\n",
        )
        self.assertEqual(1, returnVal)

    @skip_unless_crm_rule
    def test_ivalid_options(self):
        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule role=foo #uname eq node1",
        )
        ac(output, "Error: invalid role 'foo', use 'master' or 'slave'\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule score=100 score-attribute=pingd #uname eq node1",
        )
        ac(output, "Error: can not specify both score and score-attribute\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule id=1foo #uname eq node1",
        )
        ac(
            output,
            "Error: invalid rule id '1foo', '1' is not a valid first character "
            "for a rule id\n",
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "constraint location show --full"
        )
        ac(output, "Location Constraints:\n")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule id=MyRule #uname eq node1",
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name, "constraint location show --full"
        )
        ac(
            output,
            """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score=INFINITY (id:MyRule)
        Expression: #uname eq node1 (id:MyRule-expr)
""",
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            self.temp_cib.name,
            "constraint location dummy1 rule id=MyRule #uname eq node1",
        )
        ac(
            output,
            "Error: id 'MyRule' is already in use, please specify another one\n",
        )
        self.assertEqual(1, returnVal)
