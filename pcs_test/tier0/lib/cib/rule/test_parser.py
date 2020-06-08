from textwrap import dedent
from unittest import TestCase

from pcs.lib.cib import rule


class Parser(TestCase):
    def test_success_parse_to_tree(self):
        test_data = [
            ("", "BOOL AND"),
            (
                "resource ::",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE"""
                ),
            ),
            (
                "resource ::dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE type=dummy"""
                ),
            ),
            (
                "resource ocf::",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE standard=ocf"""
                ),
            ),
            (
                "resource :pacemaker:",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE provider=pacemaker"""
                ),
            ),
            (
                "resource systemd::Dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE standard=systemd type=Dummy"""
                ),
            ),
            (
                "resource ocf:pacemaker:",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE standard=ocf provider=pacemaker"""
                ),
            ),
            (
                "resource :pacemaker:Dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE provider=pacemaker type=Dummy"""
                ),
            ),
            (
                "resource ocf:pacemaker:Dummy",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE standard=ocf provider=pacemaker type=Dummy"""
                ),
            ),
            (
                "op monitor",
                dedent(
                    """\
                    BOOL AND
                      OPERATION name=monitor"""
                ),
            ),
            (
                "op monitor interval=10",
                dedent(
                    """\
                    BOOL AND
                      OPERATION name=monitor interval=10"""
                ),
            ),
            (
                "resource ::dummy and op monitor",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE type=dummy
                      OPERATION name=monitor"""
                ),
            ),
            (
                "resource ::dummy or op monitor interval=15s",
                dedent(
                    """\
                    BOOL OR
                      RESOURCE type=dummy
                      OPERATION name=monitor interval=15s"""
                ),
            ),
            (
                "op monitor and resource ::dummy",
                dedent(
                    """\
                    BOOL AND
                      OPERATION name=monitor
                      RESOURCE type=dummy"""
                ),
            ),
            (
                "op monitor interval=5min or resource ::dummy",
                dedent(
                    """\
                    BOOL OR
                      OPERATION name=monitor interval=5min
                      RESOURCE type=dummy"""
                ),
            ),
            (
                "(resource ::dummy or resource ::delay) and op monitor",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE type=dummy
                        RESOURCE type=delay
                      OPERATION name=monitor"""
                ),
            ),
            (
                "(op start and op stop) or resource ::dummy",
                dedent(
                    """\
                    BOOL OR
                      BOOL AND
                        OPERATION name=start
                        OPERATION name=stop
                      RESOURCE type=dummy"""
                ),
            ),
            (
                "op monitor or (resource ::dummy and resource ::delay)",
                dedent(
                    """\
                    BOOL OR
                      OPERATION name=monitor
                      BOOL AND
                        RESOURCE type=dummy
                        RESOURCE type=delay"""
                ),
            ),
            (
                "resource ::dummy and (op start or op stop)",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE type=dummy
                      BOOL OR
                        OPERATION name=start
                        OPERATION name=stop"""
                ),
            ),
            (
                "resource ::dummy and resource ::delay and op monitor",
                dedent(
                    """\
                    BOOL AND
                      RESOURCE type=dummy
                      RESOURCE type=delay
                      OPERATION name=monitor"""
                ),
            ),
            (
                "resource ::rA or resource ::rB or resource ::rC and op monitor",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE type=rA
                        RESOURCE type=rB
                        RESOURCE type=rC
                      OPERATION name=monitor"""
                ),
            ),
            (
                "op start and op stop and op monitor or resource ::delay",
                dedent(
                    """\
                    BOOL OR
                      BOOL AND
                        OPERATION name=start
                        OPERATION name=stop
                        OPERATION name=monitor
                      RESOURCE type=delay"""
                ),
            ),
            (
                "(resource ::rA or resource ::rB or resource ::rC) and (op oX or op oY or op oZ)",
                dedent(
                    """\
                    BOOL AND
                      BOOL OR
                        RESOURCE type=rA
                        RESOURCE type=rB
                        RESOURCE type=rC
                      BOOL OR
                        OPERATION name=oX
                        OPERATION name=oY
                        OPERATION name=oZ"""
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
            ("resource ::rA and", (1, 15, 14, "Expected end of text")),
            ("resource ::rA and op ", (1, 15, 14, "Expected end of text")),
            ("resource ::rA and (", (1, 15, 14, "Expected end of text")),
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
