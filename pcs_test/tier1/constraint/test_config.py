import json
from shlex import split
from unittest import TestCase

from pcs.common.interface.dto import to_dict
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.cib.tools import get_resources

from pcs_test.tools import fixture_cib
from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import RuleInEffectEvalMock
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    outdent,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import (
    XmlManipulation,
    etree_to_str,
)

RULE_EVAL = RuleInEffectEvalMock(
    {
        "loc_constr_with_expired_rule-rule": CibRuleInEffectStatus.EXPIRED,
        "loc_constr_with_not_expired_rule-rule": CibRuleInEffectStatus.IN_EFFECT,
        "loc_constr_with_not_expired_rule-rule-1": CibRuleInEffectStatus.IN_EFFECT,
    }
)


class ConstraintConfigJson(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-all.xml"),
        )

    def test_all_option(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--output-format=json", "--all"]
        )
        expected = get_all_constraints(RULE_EVAL, include_expired=True)
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_success(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--output-format=json"]
        )
        expected = get_all_constraints(RULE_EVAL, include_expired=False)
        self.assertEqual(
            json.loads(stdout), json.loads(json.dumps(to_dict(expected)))
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_full_option(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--output-format=json", "--full"]
        )
        self.assertEqual(stdout, "")
        self.assertEqual(
            stderr,
            "Error: Option '--full' is not compatible with 'json' output format.\n",
        )
        self.assertEqual(retval, 1)


class ConstraintConfigCmdMixin:
    orig_cib_file_path = get_test_resource("cib-all.xml")

    def setUp(self):
        # pylint: disable=invalid-name
        self.new_cib_file = get_tmp_file(self._get_tmp_file_name())
        self.pcs_runner_orig = PcsRunner(cib_file=self.orig_cib_file_path)
        self.pcs_runner_new = PcsRunner(cib_file=self.new_cib_file.name)
        write_data_to_tmpfile(
            fixture_cib.modify_cib_file(
                get_test_resource("cib-empty.xml"),
                resources=etree_to_str(
                    get_resources(
                        XmlManipulation.from_file(self.orig_cib_file_path).tree
                    )
                ),
            ),
            self.new_cib_file,
        )
        self.maxDiff = None

    def tearDown(self):
        # pylint: disable=invalid-name
        self.new_cib_file.close()

    def _get_as_json(self, runner, use_all):
        cmd = ["constraint", "config", "--output-format=json"]
        if use_all:
            cmd.append("--all")
        stdout, stderr, retval = runner.run(cmd)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def _test_success(self, use_all):
        cmd = ["constraint", "config", "--output-format=cmd"]
        if use_all:
            cmd.append("--all")
        stdout, stderr, retval = self.pcs_runner_orig.run(cmd)
        self.assertEqual(retval, 0)
        cmds = [
            split(cmd)[1:]
            for cmd in stdout.replace("\\\n", "").strip().split(";\n")
        ]
        for cmd in cmds:
            stdout, stderr, retval = self.pcs_runner_new.run(cmd)
            self.assertEqual(
                retval,
                0,
                (
                    f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                    f"stderr:\n{stderr}"
                ),
            )
        self.assertEqual(
            self._get_as_json(self.pcs_runner_new, use_all),
            self._get_as_json(self.pcs_runner_orig, use_all),
        )

    def test_all(self):
        self._test_success(True)

    def test_not_all(self):
        self._test_success(False)


class ConstraintConfigCmd(ConstraintConfigCmdMixin, TestCase):
    @staticmethod
    def _get_tmp_file_name():
        return "tier1_constraint_test_config_cib.xml"


class ConstraintConfigCmdSpaceInDate(ConstraintConfigCmdMixin, TestCase):
    # This class tests that pcs exports dates from location rules constraint
    # with spaces replaced by T in pcs commands, so that they can be run and
    # processed by pcs correctly.
    orig_cib_file_path = get_test_resource("cib-rule-with-spaces-in-date.xml")

    @staticmethod
    def _get_tmp_file_name():
        return "tier1_constraint_test_config_cib_date_space.xml"

    @staticmethod
    def _replace(struct, search_replace):
        if isinstance(struct, dict):
            for key, val in struct.items():
                struct[key] = ConstraintConfigCmdSpaceInDate._replace(
                    val, search_replace
                )
            return struct
        if isinstance(struct, list):
            return [
                ConstraintConfigCmdSpaceInDate._replace(val, search_replace)
                for val in struct
            ]
        for search, replace in search_replace:
            if struct == search:
                return replace
        return struct

    def _get_as_json(self, runner, use_all):
        data = super()._get_as_json(runner, use_all)
        data = self._replace(
            data,
            [
                ("2023-01-01 12:00", "2023-01-01T12:00"),
                ("2023-12-31 12:00", "2023-12-31T12:00"),
            ],
        )
        return data

    def test_commands(self):
        stdout, stderr, retval = self.pcs_runner_orig.run(
            ["constraint", "config", "--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")
        self.assertEqual(
            stdout,
            (
                "pcs -- constraint location resource%R1 rule \\\n"
                "  id=location-R1-rule constraint-id=location-R1 score=INFINITY \\\n"
                "  '#uname' eq node1 and date gt 2023-01-01T12:00 and "
                "date lt 2023-12-31T12:00 and date in_range 2023-01-01T12:00 "
                "to 2023-12-31T12:00;\n"
                "pcs -- constraint rule add location-R1 \\\n"
                "  id=location-R1-rule-1 score=INFINITY \\\n"
                "  '#uname' eq node1 and date gt 2023-01-01T12:00 and "
                "date lt 2023-12-31T12:00 and date in_range 2023-01-01T12:00 "
                "to 2023-12-31T12:00\n"
            ),
        )


class ConstraintConfigText(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.pcs_runner = PcsRunner(
            cib_file=get_test_resource("cib-all.xml"),
        )

    def test_success(self):
        stdout, stderr, retval = self.pcs_runner.run(["constraint", "config"])
        expected = outdent(
            """\
            Location Constraints:
              resource 'R7' avoids node 'non-existing-node' with score 10000
              resource 'R7' avoids node 'another-one' with score INFINITY
              resource 'R7' prefers node 'localhost' with score INFINITY
                resource-discovery=always
              resource 'G2' prefers node 'localhost' with score INFINITY
              resource pattern 'R*' prefers node 'localhost' with score INFINITY
              resource 'R6-clone'
                Rules:
                  Rule: boolean-op=and role=Unpromoted score=500
                    Expression: #uname eq node1
                    Expression: date gt 2000-01-01
                  Rule: boolean-op=and role=Promoted score-attribute=test-attr
                    Expression: date gt 2010-12-31
                    Expression: #uname eq node1
            Colocation Constraints:
              Promoted resource 'G1-clone' with Stopped resource 'R6-clone'
                score=-100
            Colocation Set Constraints:
              Set Constraint:
                score=-1
                Resource Set:
                  Resources: 'G2', 'R7'
                  role=Started
                Resource Set:
                  Resources: 'B2', 'R6-clone'
                  sequential=0
            Order Constraints:
              stop resource 'R7' then stop resource 'G2'
                symmetrical=0 require-all=0 score=-123
              start resource 'G2' then start resource 'B2'
                kind=Optional
            Order Set Constraints:
              Set Constraint:
                kind=Optional
                Resource Set:
                  Resources: 'B2', 'R6-clone'
                  require-all=0 action=stop
                Resource Set:
                  Resources: 'G1-clone'
                  sequential=0 action=promote
            Ticket Constraints:
              Promoted resource 'G1-clone' depends on ticket 'custom-ticket1'
                loss-policy=demote
            Ticket Set Constraints:
              Set Constraint:
                ticket=ticket2
                Resource Set:
                  Resources: 'B2', 'G2', 'R7'
                  role=Stopped
            """
        )
        self.assertEqual(stdout, expected)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_all_option(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--all"]
        )
        expected = outdent(
            """\
            Location Constraints:
              resource 'R7' avoids node 'non-existing-node' with score 10000
              resource 'R7' avoids node 'another-one' with score INFINITY
              resource 'R7' prefers node 'localhost' with score INFINITY
                resource-discovery=always
              resource 'G2' prefers node 'localhost' with score INFINITY
              resource pattern 'R*' prefers node 'localhost' with score INFINITY
              resource 'B2'
                Rules:
                  Rule (expired): score=500
                    Expression: date lt 2000-01-01
              resource 'R6-clone'
                Rules:
                  Rule: boolean-op=and role=Unpromoted score=500
                    Expression: #uname eq node1
                    Expression: date gt 2000-01-01
                  Rule: boolean-op=and role=Promoted score-attribute=test-attr
                    Expression: date gt 2010-12-31
                    Expression: #uname eq node1
            Colocation Constraints:
              Promoted resource 'G1-clone' with Stopped resource 'R6-clone'
                score=-100
            Colocation Set Constraints:
              Set Constraint:
                score=-1
                Resource Set:
                  Resources: 'G2', 'R7'
                  role=Started
                Resource Set:
                  Resources: 'B2', 'R6-clone'
                  sequential=0
            Order Constraints:
              stop resource 'R7' then stop resource 'G2'
                symmetrical=0 require-all=0 score=-123
              start resource 'G2' then start resource 'B2'
                kind=Optional
            Order Set Constraints:
              Set Constraint:
                kind=Optional
                Resource Set:
                  Resources: 'B2', 'R6-clone'
                  require-all=0 action=stop
                Resource Set:
                  Resources: 'G1-clone'
                  sequential=0 action=promote
            Ticket Constraints:
              Promoted resource 'G1-clone' depends on ticket 'custom-ticket1'
                loss-policy=demote
            Ticket Set Constraints:
              Set Constraint:
                ticket=ticket2
                Resource Set:
                  Resources: 'B2', 'G2', 'R7'
                  role=Stopped
            """
        )
        self.assertEqual(stdout, expected)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_full_option(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--full"]
        )
        expected = outdent(
            """\
            Location Constraints:
              resource 'R7' avoids node 'non-existing-node' with score 10000 (id: location-R7-non-existing-node--10000)
              resource 'R7' avoids node 'another-one' with score INFINITY (id: location-R7-another-one--INFINITY)
              resource 'R7' prefers node 'localhost' with score INFINITY (id: location-R7-localhost-INFINITY)
                resource-discovery=always
              resource 'G2' prefers node 'localhost' with score INFINITY (id: location-G2-localhost-INFINITY)
              resource pattern 'R*' prefers node 'localhost' with score INFINITY (id: location-R-localhost-INFINITY)
              resource 'R6-clone' (id: loc_constr_with_not_expired_rule)
                Rules:
                  Rule: boolean-op=and role=Unpromoted score=500 (id: loc_constr_with_not_expired_rule-rule)
                    Expression: #uname eq node1 (id: loc_constr_with_not_expired_rule-rule-expr)
                    Expression: date gt 2000-01-01 (id: loc_constr_with_not_expired_rule-rule-expr-1)
                  Rule: boolean-op=and role=Promoted score-attribute=test-attr (id: loc_constr_with_not_expired_rule-rule-1)
                    Expression: date gt 2010-12-31 (id: loc_constr_with_not_expired_rule-rule-1-expr)
                    Expression: #uname eq node1 (id: loc_constr_with_not_expired_rule-rule-1-expr-1)
            Colocation Constraints:
              Promoted resource 'G1-clone' with Stopped resource 'R6-clone' (id: colocation-G1-clone-R6-clone--100)
                score=-100
            Colocation Set Constraints:
              Set Constraint: colocation_set_R7G2B2
                score=-1
                Resource Set: colocation_set_R7G2B2_set
                  Resources: 'G2', 'R7'
                  role=Started
                Resource Set: colocation_set_R7G2B2_set-1
                  Resources: 'B2', 'R6-clone'
                  sequential=0
            Order Constraints:
              stop resource 'R7' then stop resource 'G2' (id: order-R7-G2-mandatory)
                symmetrical=0 require-all=0 score=-123
              start resource 'G2' then start resource 'B2' (id: order-G2-B2-Optional)
                kind=Optional
            Order Set Constraints:
              Set Constraint: order_set_B2R6-cloneSe
                kind=Optional
                Resource Set: order_set_B2R6-cloneSe_set
                  Resources: 'B2', 'R6-clone'
                  require-all=0 action=stop
                Resource Set: order_set_B2R6-cloneSe_set-1
                  Resources: 'G1-clone'
                  sequential=0 action=promote
            Ticket Constraints:
              Promoted resource 'G1-clone' depends on ticket 'custom-ticket1' (id: ticket-custom-ticket1-G1-clone-Promoted)
                loss-policy=demote
            Ticket Set Constraints:
              Set Constraint: ticket_set_R7B2G2
                ticket=ticket2
                Resource Set: ticket_set_R7B2G2_set
                  Resources: 'B2', 'G2', 'R7'
                  role=Stopped
            """
        )
        self.assertEqual(stdout, expected)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_all_full_options(self):
        stdout, stderr, retval = self.pcs_runner.run(
            ["constraint", "config", "--full", "--all"]
        )
        expected = outdent(
            """\
            Location Constraints:
              resource 'R7' avoids node 'non-existing-node' with score 10000 (id: location-R7-non-existing-node--10000)
              resource 'R7' avoids node 'another-one' with score INFINITY (id: location-R7-another-one--INFINITY)
              resource 'R7' prefers node 'localhost' with score INFINITY (id: location-R7-localhost-INFINITY)
                resource-discovery=always
              resource 'G2' prefers node 'localhost' with score INFINITY (id: location-G2-localhost-INFINITY)
              resource pattern 'R*' prefers node 'localhost' with score INFINITY (id: location-R-localhost-INFINITY)
              resource 'B2' (id: loc_constr_with_expired_rule)
                Rules:
                  Rule (expired): score=500 (id: loc_constr_with_expired_rule-rule)
                    Expression: date lt 2000-01-01 (id: loc_constr_with_expired_rule-rule-expr)
              resource 'R6-clone' (id: loc_constr_with_not_expired_rule)
                Rules:
                  Rule: boolean-op=and role=Unpromoted score=500 (id: loc_constr_with_not_expired_rule-rule)
                    Expression: #uname eq node1 (id: loc_constr_with_not_expired_rule-rule-expr)
                    Expression: date gt 2000-01-01 (id: loc_constr_with_not_expired_rule-rule-expr-1)
                  Rule: boolean-op=and role=Promoted score-attribute=test-attr (id: loc_constr_with_not_expired_rule-rule-1)
                    Expression: date gt 2010-12-31 (id: loc_constr_with_not_expired_rule-rule-1-expr)
                    Expression: #uname eq node1 (id: loc_constr_with_not_expired_rule-rule-1-expr-1)
            Colocation Constraints:
              Promoted resource 'G1-clone' with Stopped resource 'R6-clone' (id: colocation-G1-clone-R6-clone--100)
                score=-100
            Colocation Set Constraints:
              Set Constraint: colocation_set_R7G2B2
                score=-1
                Resource Set: colocation_set_R7G2B2_set
                  Resources: 'G2', 'R7'
                  role=Started
                Resource Set: colocation_set_R7G2B2_set-1
                  Resources: 'B2', 'R6-clone'
                  sequential=0
            Order Constraints:
              stop resource 'R7' then stop resource 'G2' (id: order-R7-G2-mandatory)
                symmetrical=0 require-all=0 score=-123
              start resource 'G2' then start resource 'B2' (id: order-G2-B2-Optional)
                kind=Optional
            Order Set Constraints:
              Set Constraint: order_set_B2R6-cloneSe
                kind=Optional
                Resource Set: order_set_B2R6-cloneSe_set
                  Resources: 'B2', 'R6-clone'
                  require-all=0 action=stop
                Resource Set: order_set_B2R6-cloneSe_set-1
                  Resources: 'G1-clone'
                  sequential=0 action=promote
            Ticket Constraints:
              Promoted resource 'G1-clone' depends on ticket 'custom-ticket1' (id: ticket-custom-ticket1-G1-clone-Promoted)
                loss-policy=demote
            Ticket Set Constraints:
              Set Constraint: ticket_set_R7B2G2
                ticket=ticket2
                Resource Set: ticket_set_R7B2G2_set
                  Resources: 'B2', 'G2', 'R7'
                  role=Stopped
            """
        )
        self.assertEqual(stdout, expected)
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
