import dataclasses
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
    for field in dataclasses.fields(parsed):
        value = getattr(parsed, field.name)
        if value is not None:
            if field.name in ("duration_parts", "date_parts"):
                parts.append(f"{field.name}=(\n ")
                parts.extend([f"{key}={val}" for key, val in value])
                parts.append("\n)")
            else:
                parts.append(f"{field.name}={value}")
    return " ".join(parts)


class Parser(TestCase):
    def _assert_success(self, rule_string, rule_tree):
        self.assertEqual(
            rule_tree,
            _parsed_to_str(rule.parse_rule(rule_string)),
        )

    def test_success_trivial(self):
        test_data = [
            ("", "BoolExpr AND"),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_resource_op_simple(self):
        test_data = [
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
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_resource_op_complex(self):
        test_data = [
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
                self._assert_success(rule_string, rule_tree)

    def test_success_node_attr_simple(self):
        test_data = [
            (
                "defined pingd",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=DEFINED attr_name=pingd"""
                ),
            ),
            (
                "not_defined pingd",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NOT_DEFINED attr_name=pingd"""
                ),
            ),
            (
                "#uname eq node1",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node1"""
                ),
            ),
            (
                "#uname ne node2",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node2"""
                ),
            ),
            (
                "int gt 123",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=GT attr_name=int attr_value=123"""
                ),
            ),
            (
                "int gte 123",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=GTE attr_name=int attr_value=123"""
                ),
            ),
            (
                "int lt 123",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=LT attr_name=int attr_value=123"""
                ),
            ),
            (
                "int lte 123",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=LTE attr_name=int attr_value=123"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_node_attr_with_optional_parts(self):
        test_data = [
            (
                "#uname eq string node1",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node1 attr_type=STRING"""
                ),
            ),
            (
                "#uname eq integer 12345",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=12345 attr_type=INTEGER"""
                ),
            ),
            (
                "#uname eq integer -12345",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=-12345 attr_type=INTEGER"""
                ),
            ),
            (
                "#uname eq number 12345",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=12345 attr_type=NUMBER"""
                ),
            ),
            (
                "#uname eq number -12345",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=-12345 attr_type=NUMBER"""
                ),
            ),
            (
                "#uname eq version 1",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=1 attr_type=VERSION"""
                ),
            ),
            (
                "#uname eq version 1.2.3",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=1.2.3 attr_type=VERSION"""
                ),
            ),
            (
                "#uname eq string string",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=string attr_type=STRING"""
                ),
            ),
            (
                "#uname eq string and",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=and attr_type=STRING"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_and_or(self):
        test_data = [
            (
                "#uname ne node1 and #uname ne node2",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node2"""
                ),
            ),
            (
                "#uname eq node1 or #uname eq node2",
                dedent(
                    """\
                    BoolExpr OR
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node1
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node2"""
                ),
            ),
            (
                "#uname ne node1 and #uname ne node2 and #uname ne node3",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node2
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "#uname ne node1 and #uname ne node2 or #uname eq node3",
                dedent(
                    """\
                    BoolExpr OR
                      BoolExpr AND
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node2
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "#uname eq node1 or #uname eq node2 and #uname ne node3",
                dedent(
                    """\
                    BoolExpr AND
                      BoolExpr OR
                        NodeAttrExpr operator=EQ attr_name=#uname attr_value=node1
                        NodeAttrExpr operator=EQ attr_name=#uname attr_value=node2
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "defined pingd and pingd lte 1",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=DEFINED attr_name=pingd
                      NodeAttrExpr operator=LTE attr_name=pingd attr_value=1"""
                ),
            ),
            (
                "pingd gt 1 or not_defined pingd",
                dedent(
                    """\
                    BoolExpr OR
                      NodeAttrExpr operator=GT attr_name=pingd attr_value=1
                      NodeAttrExpr operator=NOT_DEFINED attr_name=pingd"""
                ),
            ),
            (
                "#uname ne string integer and #uname ne string version",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=integer attr_type=STRING
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=version attr_type=STRING"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_date_simple(self):
        test_data = [
            (
                "date gt 2014-06-26",
                dedent(
                    """\
                    BoolExpr AND
                      DateUnaryExpr operator=GT date=2014-06-26"""
                ),
            ),
            (
                "date gt 2014-06-26T12:00:00",
                dedent(
                    """\
                    BoolExpr AND
                      DateUnaryExpr operator=GT date=2014-06-26T12:00:00"""
                ),
            ),
            (
                "date lt 2014-06-26",
                dedent(
                    """\
                    BoolExpr AND
                      DateUnaryExpr operator=LT date=2014-06-26"""
                ),
            ),
            (
                "date lt 2014-06-26T12:00:00",
                dedent(
                    """\
                    BoolExpr AND
                      DateUnaryExpr operator=LT date=2014-06-26T12:00:00"""
                ),
            ),
            (
                "date in_range 2014-06-26 to 2014-07-26",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26 date_end=2014-07-26"""
                ),
            ),
            (
                "date in_range 2014-06-26T12:00:00 to 2014-07-26T13:00:00",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26T12:00:00 date_end=2014-07-26T13:00:00"""
                ),
            ),
            (
                "date in_range to 2014-07-26",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_end=2014-07-26"""
                ),
            ),
            (
                "date in_range to 2014-07-26T12:00:00",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_end=2014-07-26T12:00:00"""
                ),
            ),
            (
                "date in_range 2014-06-26 to duration years=1",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26 duration_parts=(
                        years=1 
                      )"""
                ),
            ),
            (
                "date in_range 2014-06-26T12:00:00 to duration years=1",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26T12:00:00 duration_parts=(
                        years=1 
                      )"""
                ),
            ),
            (
                "date in_range 2014-06-26 to duration a=1 b=2 a=3",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26 duration_parts=(
                        a=1 b=2 a=3 
                      )"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_datespec(self):
        test_data = [
            (
                "date-spec hours=1",
                dedent(
                    """\
                    BoolExpr AND
                      DatespecExpr date_parts=(
                        hours=1 
                      )"""
                ),
            ),
            (
                "date-spec hours=1-14 months=1 hours=14-20",
                dedent(
                    """\
                    BoolExpr AND
                      DatespecExpr date_parts=(
                        hours=1-14 months=1 hours=14-20 
                      )"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_and_or_date_datespec(self):
        test_data = [
            (
                "#uname ne node1 and date-spec hours=1-12",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      DatespecExpr date_parts=(
                        hours=1-12 
                      )"""
                ),
            ),
            (
                "date-spec monthdays=1-12 or #uname ne node1",
                dedent(
                    """\
                    BoolExpr OR
                      DatespecExpr date_parts=(
                        monthdays=1-12 
                      )
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1"""
                ),
            ),
            (
                "date-spec monthdays=1-10 or date-spec monthdays=11-20",
                dedent(
                    """\
                    BoolExpr OR
                      DatespecExpr date_parts=(
                        monthdays=1-10 
                      )
                      DatespecExpr date_parts=(
                        monthdays=11-20 
                      )"""
                ),
            ),
            (
                "#uname ne node1 and date in_range 2014-06-26 to 2014-07-26",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      DateInRangeExpr date_start=2014-06-26 date_end=2014-07-26"""
                ),
            ),
            (
                "date in_range 2014-06-26 to 2014-07-26 and #uname ne node1",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26 date_end=2014-07-26
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_braces(self):
        test_data = [
            (
                "(date-spec hours=1)",
                dedent(
                    """\
                    BoolExpr AND
                      DatespecExpr date_parts=(
                        hours=1 
                      )"""
                ),
            ),
            (
                "(#uname eq node1)",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node1"""
                ),
            ),
            (
                "(defined pingd)",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=DEFINED attr_name=pingd"""
                ),
            ),
            (
                "(#uname ne node1 and #uname ne node2)",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node2"""
                ),
            ),
            (
                "(#uname ne node1) and (#uname ne node2)",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node2"""
                ),
            ),
            (
                "(#uname ne node1 and #uname ne node2) or #uname eq node3",
                dedent(
                    """\
                    BoolExpr OR
                      BoolExpr AND
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node2
                      NodeAttrExpr operator=EQ attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "#uname ne node1 and (#uname ne node2 or #uname eq node3)",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      BoolExpr OR
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node2
                        NodeAttrExpr operator=EQ attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "(((#uname ne node1) and (((#uname ne node2) or (#uname eq node3)))))",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=NE attr_name=#uname attr_value=node1
                      BoolExpr OR
                        NodeAttrExpr operator=NE attr_name=#uname attr_value=node2
                        NodeAttrExpr operator=EQ attr_name=#uname attr_value=node3"""
                ),
            ),
            (
                "(date in_range 2014-06-26 to 2014-07-26)",
                dedent(
                    """\
                    BoolExpr AND
                      DateInRangeExpr date_start=2014-06-26 date_end=2014-07-26"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_success_not_date(self):
        test_data = [
            (
                "date eq 2014-06-26",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=EQ attr_name=date attr_value=2014-06-26"""
                ),
            ),
            (
                "date gt string 2014-06-26",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=GT attr_name=date attr_value=2014-06-26 attr_type=STRING"""
                ),
            ),
            (
                "date gt integer 12345",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=GT attr_name=date attr_value=12345 attr_type=INTEGER"""
                ),
            ),
            (
                "date gt version 1.2.3",
                dedent(
                    """\
                    BoolExpr AND
                      NodeAttrExpr operator=GT attr_name=date attr_value=1.2.3 attr_type=VERSION"""
                ),
            ),
        ]
        for rule_string, rule_tree in test_data:
            with self.subTest(rule_string=rule_string):
                self._assert_success(rule_string, rule_tree)

    def test_not_valid_rule(self):
        test_data = [
            # node attr misc
            ("#uname", (1, 7, 6, "Expected 'eq'")),
            ("string node1", (1, 8, 7, "Expected 'eq'")),
            # node attr unary
            ("defined", (1, 8, 7, "Expected <attribute name>")),
            ("not_defined", (1, 12, 11, "Expected <attribute name>")),
            ("defined string pingd", (1, 16, 15, "Expected end of text")),
            ("defined date-spec hours=1", (1, 19, 18, "Expected end of text")),
            ("defined duration hours=1", (1, 18, 17, "Expected end of text")),
            # node attr binary
            ("eq", (1, 3, 2, "Expected 'eq'")),
            ("#uname eq", (1, 10, 9, "Expected <attribute value>")),
            ("#uname node1", (1, 8, 7, "Expected 'eq'")),
            ("eq #uname", (1, 4, 3, "Expected 'eq'")),
            ("eq lt", (1, 6, 5, "Expected <attribute value>")),
            ("string #uname eq node1", (1, 8, 7, "Expected 'eq'")),
            ("date-spec hours=1 eq node1", (1, 19, 18, "Expected end of text")),
            (
                "#uname eq date-spec hours=1",
                (1, 21, 20, "Expected end of text"),
            ),
            ("duration hours=1 eq node1", (1, 10, 9, "Expected 'eq'")),
            ("#uname eq duration hours=1", (1, 20, 19, "Expected end of text")),
            # node attr binary with optional parts
            ("string", (1, 7, 6, "Expected 'eq'")),
            ("#uname eq string", (1, 17, 16, "Expected <attribute value>")),
            ("string #uname eq node1", (1, 8, 7, "Expected 'eq'")),
            # resource, op
            ("resource", (1, 9, 8, "Expected 'eq'")),
            ("op", (1, 3, 2, "Expected 'eq'")),
            ("resource ::rA and", (1, 15, 14, "Expected end of text")),
            ("resource ::rA and op ", (1, 15, 14, "Expected end of text")),
            ("resource ::rA and (", (1, 15, 14, "Expected end of text")),
            # and, or
            ("and", (1, 4, 3, "Expected 'eq'")),
            ("or", (1, 3, 2, "Expected 'eq'")),
            ("#uname and node1", (1, 8, 7, "Expected 'eq'")),
            ("#uname or node1", (1, 8, 7, "Expected 'eq'")),
            ("#uname or eq", (1, 8, 7, "Expected 'eq'")),
            ("#uname eq node1 and node2", (1, 17, 16, "Expected end of text")),
            ("#uname eq node1 and", (1, 17, 16, "Expected end of text")),
            (
                "#uname eq node1 and #uname eq",
                (1, 17, 16, "Expected end of text"),
            ),
            ("and #uname eq node1", (1, 5, 4, "Expected 'eq'")),
            (
                "#uname ne node1 and duration hours=1",
                (1, 17, 16, "Expected end of text"),
            ),
            (
                "duration monthdays=1 or #uname ne node1",
                (1, 10, 9, "Expected 'eq'"),
            ),
            # date
            ("date in_range", (1, 14, 13, "Expected 'to'")),
            ("date in_range 2014-06-26", (1, 15, 14, "Expected 'to'")),
            ("date in_range 2014-06-26 to", (1, 28, 27, "Expected <date>")),
            ("in_range 2014-06-26 to 2014-07-26", (1, 10, 9, "Expected 'eq'")),
            (
                "date in_range #uname eq node1 to 2014-07-26",
                (1, 15, 14, "Expected 'to'"),
            ),
            (
                "date in_range 2014-06-26 to #uname eq node1",
                (1, 36, 35, "Expected end of text"),
            ),
            (
                "date in_range defined pingd to 2014-07-26",
                (1, 15, 14, "Expected 'to'"),
            ),
            (
                "date in_range 2014-06-26 to defined pingd",
                (1, 37, 36, "Expected end of text"),
            ),
            (
                "string date in_range 2014-06-26 to 2014-07-26",
                (1, 8, 7, "Expected 'eq'"),
            ),
            (
                "date in_range string 2014-06-26 to 2014-07-26",
                (1, 15, 14, "Expected 'to'"),
            ),
            (
                "date in_range 2014-06-26 to string 2014-07-26",
                (1, 36, 35, "Expected end of text"),
            ),
            (
                "date in_range 2014-06-26 string to 2014-07-26",
                (1, 15, 14, "Expected 'to'"),
            ),
            (
                "#uname in_range 2014-06-26 to 2014-07-26",
                (1, 8, 7, "Expected 'eq'"),
            ),
            (
                "date gt 2014-06-24 12:00:00",
                (1, 20, 19, "Expected end of text"),
            ),
            (
                "date lt 2014-06-24 12:00:00",
                (1, 20, 19, "Expected end of text"),
            ),
            (
                "date in_range 2014-06-26 12:00:00 to 2014-07-26",
                (1, 15, 14, "Expected 'to'"),
            ),
            (
                "date in_range 2014-06-26 to 2014-07-26 12:00:00",
                (1, 40, 39, "Expected end of text"),
            ),
            # braces
            ("(#uname)", (1, 8, 7, "Expected 'eq'")),
            ("(", (1, 2, 1, "Expected 'date'")),
            ("()", (1, 2, 1, "Expected 'date'")),
            ("(#uname", (1, 8, 7, "Expected 'eq'")),
            ("(#uname eq", (1, 11, 10, "Expected <attribute value>")),
            # pyparsing 2 uses double quotes, pyparsing 3 uses single quotes
            ("(#uname eq node1", (1, 17, 16, {"Expected ')'", 'Expected ")"'})),
        ]
        for rule_string, exception_data in test_data:
            with self.subTest(rule_string=rule_string):
                with self.assertRaises(rule.RuleParseError) as cm:
                    rule.parse_rule(rule_string)
                e = cm.exception
                if isinstance(exception_data[3], set):
                    self.assertIn(e.msg, exception_data[3])
                    self.assertEqual(
                        exception_data[0:3], (e.lineno, e.colno, e.pos)
                    )
                else:
                    self.assertEqual(
                        exception_data, (e.lineno, e.colno, e.pos, e.msg)
                    )
                self.assertEqual(rule_string, e.rule_string)
