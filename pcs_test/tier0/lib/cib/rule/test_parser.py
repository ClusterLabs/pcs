from dataclasses import fields
from textwrap import dedent
from unittest import TestCase

from pcs.common.str_tools import indent
from pcs.lib.cib import rule
from pcs.lib.cib.rule.expression_part import BoolExpr


def _parsed_to_str(parsed):
    if isinstance(parsed, BoolExpr):
        str_args = []
        for arg in parsed.children:
            str_args.extend(_parsed_to_str(arg).splitlines())
        return "\n".join(
            [f"{parsed.__class__.__name__} {parsed.operator}"]
            + indent(str_args)
        )

    parts = [parsed.__class__.__name__]
    for field in fields(parsed):
        value = getattr(parsed, field.name)
        if value is not None:
            parts.append(f"{field.name}={value}")
    return " ".join(parts)


class Parser(TestCase):
    def test_success_parse_to_tree(self):
        test_data = [
            ("", "BoolExpr AND"),
            (
                "resource ::",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr"""
                ),
            ),
            (
                "resource ::dummy",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr type=dummy"""
                ),
            ),
            (
                "resource ocf::",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr standard=ocf"""
                ),
            ),
            (
                "resource :pacemaker:",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr provider=pacemaker"""
                ),
            ),
            (
                "resource systemd::Dummy",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr standard=systemd type=Dummy"""
                ),
            ),
            (
                "resource ocf:pacemaker:",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr standard=ocf provider=pacemaker"""
                ),
            ),
            (
                "resource :pacemaker:Dummy",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr provider=pacemaker type=Dummy"""
                ),
            ),
            (
                "resource ocf:pacemaker:Dummy",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr standard=ocf provider=pacemaker type=Dummy"""
                ),
            ),
            (
                "op monitor",
                dedent(
                    """\
                    BoolExpr AND
                      OpExpr name=monitor"""
                ),
            ),
            (
                "op monitor interval=10",
                dedent(
                    """\
                    BoolExpr AND
                      OpExpr name=monitor interval=10"""
                ),
            ),
            (
                "resource ::dummy and op monitor",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr type=dummy
                      OpExpr name=monitor"""
                ),
            ),
            (
                "resource ::dummy or op monitor interval=15s",
                dedent(
                    """\
                    BoolExpr OR
                      RscExpr type=dummy
                      OpExpr name=monitor interval=15s"""
                ),
            ),
            (
                "op monitor and resource ::dummy",
                dedent(
                    """\
                    BoolExpr AND
                      OpExpr name=monitor
                      RscExpr type=dummy"""
                ),
            ),
            (
                "op monitor interval=5min or resource ::dummy",
                dedent(
                    """\
                    BoolExpr OR
                      OpExpr name=monitor interval=5min
                      RscExpr type=dummy"""
                ),
            ),
            (
                "(resource ::dummy or resource ::delay) and op monitor",
                dedent(
                    """\
                    BoolExpr AND
                      BoolExpr OR
                        RscExpr type=dummy
                        RscExpr type=delay
                      OpExpr name=monitor"""
                ),
            ),
            (
                "(op start and op stop) or resource ::dummy",
                dedent(
                    """\
                    BoolExpr OR
                      BoolExpr AND
                        OpExpr name=start
                        OpExpr name=stop
                      RscExpr type=dummy"""
                ),
            ),
            (
                "op monitor or (resource ::dummy and resource ::delay)",
                dedent(
                    """\
                    BoolExpr OR
                      OpExpr name=monitor
                      BoolExpr AND
                        RscExpr type=dummy
                        RscExpr type=delay"""
                ),
            ),
            (
                "resource ::dummy and (op start or op stop)",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr type=dummy
                      BoolExpr OR
                        OpExpr name=start
                        OpExpr name=stop"""
                ),
            ),
            (
                "resource ::dummy and resource ::delay and op monitor",
                dedent(
                    """\
                    BoolExpr AND
                      RscExpr type=dummy
                      RscExpr type=delay
                      OpExpr name=monitor"""
                ),
            ),
            (
                "resource ::rA or resource ::rB or resource ::rC and op monitor",
                dedent(
                    """\
                    BoolExpr AND
                      BoolExpr OR
                        RscExpr type=rA
                        RscExpr type=rB
                        RscExpr type=rC
                      OpExpr name=monitor"""
                ),
            ),
            (
                "op start and op stop and op monitor or resource ::delay",
                dedent(
                    """\
                    BoolExpr OR
                      BoolExpr AND
                        OpExpr name=start
                        OpExpr name=stop
                        OpExpr name=monitor
                      RscExpr type=delay"""
                ),
            ),
            (
                "(resource ::rA or resource ::rB or resource ::rC) and (op oX or op oY or op oZ)",
                dedent(
                    """\
                    BoolExpr AND
                      BoolExpr OR
                        RscExpr type=rA
                        RscExpr type=rB
                        RscExpr type=rC
                      BoolExpr OR
                        OpExpr name=oX
                        OpExpr name=oY
                        OpExpr name=oZ"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self.assertEqual(
                    rule_tree,
                    _parsed_to_str(
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
