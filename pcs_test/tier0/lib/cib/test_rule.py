from textwrap import dedent
from unittest import TestCase

from pcs.lib.cib import rule


class Parser(TestCase):
    def test_success_parse_to_tree(self):
        test_data = [
            ("", "BOOL AND"),
            (
                "resource dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        dummy"""
                ),
            ),
            (
                "resource systemd:Dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        systemd:Dummy"""
                ),
            ),
            (
                "resource ocf:pacemaker:Dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        ocf:pacemaker:Dummy"""
                ),
            ),
            (
                "op monitor",
                dedent(
                    """\
                    BOOL AND
                      OPERATION
                        monitor"""
                ),
            ),
            (
                "op monitor interval=10",
                dedent(
                    """\
                    BOOL AND
                      OPERATION
                        monitor
                        NAME-VALUE
                          interval
                          10"""
                ),
            ),
            (
                "resource dummy and op monitor",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        dummy
                      OPERATION
                        monitor"""
                ),
            ),
            (
                "resource dummy or op monitor interval=15s",
                dedent(
                    """\
                    BOOL OR
                      RESOURCE
                        dummy
                      OPERATION
                        monitor
                        NAME-VALUE
                          interval
                          15s"""
                ),
            ),
            (
                "op monitor and resource dummy",
                dedent(
                    """\
                    BOOL AND
                      OPERATION
                        monitor
                      RESOURCE
                        dummy"""
                ),
            ),
            (
                "op monitor interval=5min or resource dummy",
                dedent(
                    """\
                    BOOL OR
                      OPERATION
                        monitor
                        NAME-VALUE
                          interval
                          5min
                      RESOURCE
                        dummy"""
                ),
            ),
            (
                "(resource dummy or resource delay) and op monitor",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE
                          dummy
                        RESOURCE
                          delay
                      OPERATION
                        monitor"""
                ),
            ),
            (
                "(op start and op stop) or resource dummy",
                dedent(
                    """\
                    BOOL OR
                      BOOL AND
                        OPERATION
                          start
                        OPERATION
                          stop
                      RESOURCE
                        dummy"""
                ),
            ),
            (
                "op monitor or (resource dummy and resource delay)",
                dedent(
                    """\
                    BOOL OR
                      OPERATION
                        monitor
                      BOOL AND
                        RESOURCE
                          dummy
                        RESOURCE
                          delay"""
                ),
            ),
            (
                "resource dummy and (op start or op stop)",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        dummy
                      BOOL OR
                        OPERATION
                          start
                        OPERATION
                          stop"""
                ),
            ),
            (
                "resource dummy and resource delay and op monitor",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE
                        dummy
                      RESOURCE
                        delay
                      OPERATION
                        monitor"""
                ),
            ),
            (
                "resource rA or resource rB or resource rC and op monitor",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE
                          rA
                        RESOURCE
                          rB
                        RESOURCE
                          rC
                      OPERATION
                        monitor"""
                ),
            ),
            (
                "op start and op stop and op monitor or resource delay",
                dedent(
                    """\
                    BOOL OR
                      BOOL AND
                        OPERATION
                          start
                        OPERATION
                          stop
                        OPERATION
                          monitor
                      RESOURCE
                        delay"""
                ),
            ),
            (
                "(resource rA or resource rB or resource rC) and (op oX or op oY or op oZ)",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE
                          rA
                        RESOURCE
                          rB
                        RESOURCE
                          rC
                      BOOL OR
                        OPERATION
                          oX
                        OPERATION
                          oY
                        OPERATION
                          oZ"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self.assertEqual(
                    rule_tree,
                    str(
                        rule.parse_rule(
                            rule_string, allow_rsc_expr=True, allow_op_expr=True
                        )
                    ),
                )

    def test_not_valid_rule(self):
        test_data = [
            ("resource", (1, 9, 8, "Expected <resource name>")),
            ("op", (1, 3, 2, "Expected <operation name>")),
            ("resource rA and", (1, 13, 12, "Expected end of text")),
            ("resource rA and op ", (1, 13, 12, "Expected end of text")),
            ("resource rA and (", (1, 13, 12, "Expected end of text")),
        ]

        for rule_string, exception_data in test_data:
            with self.subTest(rule_string=rule_string):
                with self.assertRaises(rule.RuleParseError) as cm:
                    rule.parse_rule(
                        rule_string, allow_rsc_expr=True, allow_op_expr=True
                    )
            e = cm.exception
            self.assertEqual(exception_data, (e.lineno, e.colno, e.pos, e.msg))
            self.assertEqual(rule_string, e.rule_string)
