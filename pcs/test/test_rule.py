from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from pcs.test.tools import pcs_unittest as unittest
import xml.dom.minidom

from pcs import rule
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import pcs

empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")

class DateValueTest(unittest.TestCase):

    def testParse(self):
        for value, item in enumerate(rule.DateCommonValue.allowed_items, 1):
            self.assertEqual(
                str(value),
                rule.DateCommonValue("%s=%s" % (item, value)).parts[item]
            )

        value = rule.DateCommonValue(
            "hours=1 monthdays=2 weekdays=3 yeardays=4 months=5 weeks=6 "
            "years=7 weekyears=8 moon=9"
        )
        self.assertEqual("1", value.parts["hours"])
        self.assertEqual("2", value.parts["monthdays"])
        self.assertEqual("3", value.parts["weekdays"])
        self.assertEqual("4", value.parts["yeardays"])
        self.assertEqual("5", value.parts["months"])
        self.assertEqual("6", value.parts["weeks"])
        self.assertEqual("7", value.parts["years"])
        self.assertEqual("8", value.parts["weekyears"])
        self.assertEqual("9", value.parts["moon"])

        value = rule.DateCommonValue("hours=1 monthdays=2 hours=3")
        self.assertEqual("2", value.parts["monthdays"])
        self.assertEqual("3", value.parts["hours"])

        value = rule.DateCommonValue(" hours=1   monthdays=2   hours=3 ")
        self.assertEqual("2", value.parts["monthdays"])
        self.assertEqual("3", value.parts["hours"])

        self.assertSyntaxError(
            "missing one of 'hours=', 'monthdays=', 'weekdays=', 'yeardays=', "
            "'months=', 'weeks=', 'years=', 'weekyears=', 'moon=' in date-spec",
            "",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "missing value after 'hours=' in date-spec",
            "hours=",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "missing =value after 'hours' in date-spec",
            "hours",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "unexpected 'foo=bar' in date-spec",
            "foo=bar",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "unexpected 'foo=bar' in date-spec",
            "hours=1 foo=bar",
            rule.DateSpecValue
        )

    def testDurationValidate(self):
        for value, item in enumerate(rule.DateCommonValue.allowed_items, 1):
            self.assertEqual(
                str(value),
                rule.DateDurationValue("%s=%s" % (item, value)).parts[item]
            )
        for item in rule.DateCommonValue.allowed_items:
            self.assertSyntaxError(
                "invalid %s '%s' in 'duration'" % (item, "foo"),
                "%s=foo" % item,
                rule.DateDurationValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'duration'" % (item, "-1"),
                "%s=-1" % item,
                rule.DateDurationValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'duration'" % (item, "2foo"),
                "%s=2foo" % item,
                rule.DateDurationValue
            )

    def testDateSpecValidation(self):
        for item in rule.DateCommonValue.allowed_items:
            value = 1
            self.assertEqual(
                str(value),
                rule.DateSpecValue("%s=%s" % (item, value)).parts[item]
            )
            self.assertEqual(
                "%s-%s" % (value, value + 1),
                rule.DateSpecValue(
                    "%s=%s-%s" % (item, value, value + 1)
                ).parts[item]
            )
        self.assertEqual(
            "hours=9-16 weekdays=1-5",
            str(rule.DateSpecValue("hours=9-16 weekdays=1-5"))
        )
        for item in rule.DateCommonValue.allowed_items:
            self.assertSyntaxError(
                "invalid %s '%s' in 'date-spec'" % (item, "foo"),
                "%s=foo" % item,
                rule.DateSpecValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'date-spec'" % (item, "1-foo"),
                "%s=1-foo" % item,
                rule.DateSpecValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'date-spec'" % (item, "foo-1"),
                "%s=foo-1" % item,
                rule.DateSpecValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'date-spec'" % (item, "1-2-3"),
                "%s=1-2-3" % item,
                rule.DateSpecValue
            )
            self.assertSyntaxError(
                "invalid %s '%s' in 'date-spec'" % (item, "2-1"),
                "%s=2-1" % item,
                rule.DateSpecValue
            )
        self.assertSyntaxError(
            "invalid hours '24' in 'date-spec'",
            "hours=24",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid monthdays '32' in 'date-spec'",
            "monthdays=32",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid weekdays '8' in 'date-spec'",
            "weekdays=8",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid yeardays '367' in 'date-spec'",
            "yeardays=367",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid months '13' in 'date-spec'",
            "months=13",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid weeks '54' in 'date-spec'",
            "weeks=54",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid weekyears '54' in 'date-spec'",
            "weekyears=54",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid moon '8' in 'date-spec'",
            "moon=8",
            rule.DateSpecValue
        )
        self.assertSyntaxError(
            "invalid hours '12-8' in 'date-spec'",
            "hours=12-8",
            rule.DateSpecValue
        )

    def assertSyntaxError(self, syntax_error, parts_string, value_class=None):
        value_class = value_class if value_class else rule.DateCommonValue
        self.assertRaises(rule.SyntaxError, value_class, parts_string)
        try:
            value_class(parts_string)
        except rule.SyntaxError as e:
            self.assertEqual(syntax_error, str(e))


class ParserTest(unittest.TestCase):

    def setUp(self):
        self.parser = rule.RuleParser()

    def testEmptyInput(self):
        self.assertRaises(rule.UnexpectedEndOfInput, self.parser.parse, [])

    def testSingleLiteral(self):
        self.assertSyntaxError(
            "missing one of 'eq', 'ne', 'lt', 'gt', 'lte', 'gte', 'in_range', "
            "'defined', 'not_defined', 'date-spec'",
            ["#uname"]
        )
        self.assertSyntaxError(
            "missing one of 'eq', 'ne', 'lt', 'gt', 'lte', 'gte', 'in_range', "
            "'defined', 'not_defined', 'date-spec'",
            ["string", "node1"]
        )

    def testSingleLiteralDatespec(self):
        self.assertEqual(
            "(date-spec (literal hours=1))",
            str(self.parser.parse(["date-spec", "hours=1"]))
        )
        self.assertEqual(
            "(date-spec (literal hours=1-14 monthdays=20-30 months=1))",
            str(self.parser.parse([
                "date-spec", "hours=1-14 months=1 monthdays=20-30"
            ]))
        )
        self.assertUnexpectedEndOfInput(["date-spec"])

    def testSimpleExpression(self):
        self.assertEqual(
            "(eq (literal #uname) (literal node1))",
            str(self.parser.parse(["#uname", "eq", "node1"]))
        )
        self.assertEqual(
            "(ne (literal #uname) (literal node2))",
            str(self.parser.parse(["#uname", "ne", "node2"]))
        )
        self.assertEqual(
            "(gt (literal int) (literal 123))",
            str(self.parser.parse(["int", "gt", "123"]))
        )
        self.assertEqual(
            "(gte (literal int) (literal 123))",
            str(self.parser.parse(["int", "gte", "123"]))
        )
        self.assertEqual(
            "(lt (literal int) (literal 123))",
            str(self.parser.parse(["int", "lt", "123"]))
        )
        self.assertEqual(
            "(lte (literal int) (literal 123))",
            str(self.parser.parse(["int", "lte", "123"]))
        )

    def testSimpleExpressionBad(self):
        self.assertSyntaxError(
            "unexpected 'eq'",
            ["eq"]
        )
        self.assertUnexpectedEndOfInput(["#uname", "eq"])
        self.assertSyntaxError(
            "unexpected 'node1'",
            ["#uname", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'eq'",
            ["eq", "#uname"]
        )
        self.assertSyntaxError(
            "unexpected 'eq'",
            ["eq", "lt"]
        )
        self.assertSyntaxError(
            "unexpected 'string' before 'eq'",
            ["string", "#uname", "eq", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'date-spec' before 'eq'",
            ["date-spec", "hours=1", "eq", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'date-spec' after 'eq'",
            ["#uname", "eq", "date-spec", "hours=1"]
        )
        self.assertSyntaxError(
            "unexpected 'duration' before 'eq'",
            ["duration", "hours=1", "eq", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'duration' after 'eq'",
            ["#uname", "eq", "duration", "hours=1"]
        )

    def testDefinedExpression(self):
        self.assertEqual(
            "(defined (literal pingd))",
            str(self.parser.parse(["defined", "pingd"]))
        )
        self.assertEqual(
            "(not_defined (literal pingd))",
            str(self.parser.parse(["not_defined", "pingd"]))
        )

    def testDefinedExpressionBad(self):
        self.assertUnexpectedEndOfInput(["defined"])
        self.assertUnexpectedEndOfInput(["not_defined"])
        self.assertSyntaxError(
            "unexpected 'eq'",
            ["defined", "eq"]
        )
        self.assertSyntaxError(
            "unexpected 'and'",
            ["defined", "and"]
        )
        self.assertSyntaxError(
            "unexpected 'string' after 'defined'",
            ["defined", "string", "pingd"]
        )
        self.assertSyntaxError(
            "unexpected 'date-spec' after 'defined'",
            ["defined", "date-spec", "hours=1"]
        )
        self.assertSyntaxError(
            "unexpected 'duration' after 'defined'",
            ["defined", "duration", "hours=1"]
        )

    def testTypeExpression(self):
        self.assertEqual(
            "(eq (literal #uname) (string (literal node1)))",
            str(self.parser.parse(["#uname", "eq", "string", "node1"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (integer (literal 12345)))",
            str(self.parser.parse(["#uname", "eq", "integer", "12345"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (integer (literal -12345)))",
            str(self.parser.parse(["#uname", "eq", "integer", "-12345"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (version (literal 1)))",
            str(self.parser.parse(["#uname", "eq", "version", "1"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (version (literal 1.2.3)))",
            str(self.parser.parse(["#uname", "eq", "version", "1.2.3"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (string (literal string)))",
            str(self.parser.parse(["#uname", "eq", "string", "string"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (string (literal and)))",
            str(self.parser.parse(["#uname", "eq", "string", "and"]))
        )
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (string (literal integer))) "
                "(ne (literal #uname) (string (literal version)))"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "string", "integer",
                "and",
                "#uname", "ne", "string", "version"
            ]))
        )

    def testTypeExpressionBad(self):
        self.assertUnexpectedEndOfInput(["string"])
        self.assertUnexpectedEndOfInput(["#uname", "eq", "string"])
        self.assertSyntaxError(
            "unexpected 'string' before 'eq'",
            ["string", "#uname", "eq", "node1"]
        )
        self.assertSyntaxError(
            "invalid integer value 'node1'",
            ["#uname", "eq", "integer", "node1"]
        )
        self.assertSyntaxError(
            "invalid version value 'node1'",
            ["#uname", "eq", "version", "node1"]
        )

    def testDateExpression(self):
        self.assertEqual(
            "(gt (literal date) (literal 2014-06-26))",
            str(self.parser.parse(["date", "gt", "2014-06-26"]))
        )
        self.assertEqual(
            "(lt (literal date) (literal 2014-06-26))",
            str(self.parser.parse(["date", "lt", "2014-06-26"]))
        )
        self.assertEqual(
            "(in_range "
                "(literal date) (literal 2014-06-26) (literal 2014-07-26)"
            ")",
            str(self.parser.parse([
                "date", "in_range", "2014-06-26", "to", "2014-07-26"
            ]))
        )
        self.assertEqual(
            "(in_range "
                "(literal date) "
                "(literal 2014-06-26) (duration (literal years=1))"
            ")",
            str(self.parser.parse([
                "date", "in_range", "2014-06-26", "to", "duration", "years=1"
            ]))
        )

    def testDateExpressionBad(self):
        self.assertUnexpectedEndOfInput(
            ["date", "in_range"]
        )
        self.assertSyntaxError(
            "missing 'to'",
            ["date", "in_range", '2014-06-26']
        )
        self.assertUnexpectedEndOfInput(
            ["date", "in_range", "2014-06-26", "to"]
        )
        self.assertSyntaxError(
            "unexpected 'in_range'",
            ["in_range", '2014-06-26', "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "expecting 'to', got 'eq'",
            ["date", "in_range", '#uname', "eq", "node1", "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "invalid date '#uname' in 'in_range ... to'",
            ["date", "in_range", "2014-06-26", "to", '#uname', "eq", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'defined' after 'in_range'",
            ["date", "in_range", "defined", "pingd", "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "unexpected 'defined' after 'in_range ... to'",
            ["date", "in_range", "2014-06-26", "to", "defined", "pingd"]
        )
        self.assertSyntaxError(
            "unexpected 'string' before 'in_range'",
            ["string", "date", "in_range", '2014-06-26', "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "unexpected 'string' after 'in_range'",
            ["date", "in_range", "string", '2014-06-26', "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "unexpected 'string' after 'in_range ... to'",
            ["date", "in_range", '2014-06-26', "to", "string", "2014-07-26"]
        )
        self.assertSyntaxError(
            "unexpected 'string' after '2014-06-26'",
            ["date", "in_range", '2014-06-26', "string", "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "unexpected '#uname' before 'in_range'",
            ["#uname", "in_range", '2014-06-26', "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "invalid date '2014-13-26' in 'in_range ... to'",
            ["date", "in_range", '2014-13-26', "to", "2014-07-26"]
        )
        self.assertSyntaxError(
            "invalid date '2014-13-26' in 'in_range ... to'",
            ["date", "in_range", '2014-06-26', "to", "2014-13-26"]
        )

    def testAndOrExpression(self):
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(ne (literal #uname) (literal node2))"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1", "and", "#uname", "ne", "node2"
            ]))
        )
        self.assertEqual(
            "(or "
                "(eq (literal #uname) (literal node1)) "
                "(eq (literal #uname) (literal node2))"
            ")",
            str(self.parser.parse([
                "#uname", "eq", "node1", "or", "#uname", "eq", "node2"
            ]))
        )
        self.assertEqual(
            "(and "
                "(and "
                    "(ne (literal #uname) (literal node1)) "
                    "(ne (literal #uname) (literal node2))"
                ") "
                "(ne (literal #uname) (literal node3))"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1",
                "and", "#uname", "ne", "node2",
                "and", "#uname", "ne", "node3"
            ]))
        )
        self.assertEqual(
            "(or "
                "(and "
                    "(ne (literal #uname) (literal node1)) "
                    "(ne (literal #uname) (literal node2))"
                ") "
                "(eq (literal #uname) (literal node3))"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1",
                "and", "#uname", "ne", "node2",
                "or", "#uname", "eq", "node3"
            ]))
        )
        self.assertEqual(
            "(and "
                "(or "
                    "(eq (literal #uname) (literal node1)) "
                    "(eq (literal #uname) (literal node2))"
                ") "
                "(ne (literal #uname) (literal node3))"
            ")",
            str(self.parser.parse([
                "#uname", "eq", "node1",
                "or", "#uname", "eq", "node2",
                "and", "#uname", "ne", "node3"
            ]))
        )
        self.assertEqual(
            "(and "
                "(defined (literal pingd)) "
                "(lte (literal pingd) (literal 1))"
            ")",
            str(self.parser.parse([
                "defined", "pingd", "and", "pingd", "lte", "1"
            ]))
        )
        self.assertEqual(
            "(or "
                "(gt (literal pingd) (literal 1)) "
                "(not_defined (literal pingd))"
            ")",
            str(self.parser.parse([
                "pingd", "gt", "1", "or", "not_defined", "pingd"
            ]))
        )

    def testAndOrExpressionDateSpec(self):
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(date-spec (literal hours=1-12))"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1", "and", "date-spec", "hours=1-12"
            ]))
        )
        self.assertEqual(
            "(or "
                "(date-spec (literal monthdays=1-12)) "
                "(ne (literal #uname) (literal node1))"
            ")",
            str(self.parser.parse([
                "date-spec", "monthdays=1-12", "or", "#uname", "ne", "node1"
            ]))
        )
        self.assertEqual(
            "(or "
                "(date-spec (literal monthdays=1-10)) "
                "(date-spec (literal monthdays=11-20))"
            ")",
            str(self.parser.parse([
                "date-spec", "monthdays=1-10",
                "or",
                "date-spec", "monthdays=11-20"
            ]))
        )

    def testAndOrExpressionDate(self):
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(in_range "
                    "(literal date) (literal 2014-06-26) (literal 2014-07-26)"
                ")"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1",
                "and",
                "date", "in_range", "2014-06-26", "to", "2014-07-26"
            ]))
        )
        self.assertEqual(
            "(and "
                "(in_range "
                    "(literal date) (literal 2014-06-26) (literal 2014-07-26)"
                ") "
                "(ne (literal #uname) (literal node1))"
            ")",
            str(self.parser.parse([
                "date", "in_range", "2014-06-26", "to", "2014-07-26",
                "and",
                "#uname", "ne", "node1"
            ]))
        )

    def testAndOrExpressionBad(self):
        self.assertSyntaxError(
            "unexpected 'and'",
            ["and"]
        )
        self.assertSyntaxError(
            "unexpected 'or'",
            ["or"]
        )
        self.assertSyntaxError(
            "unexpected '#uname' before 'and'",
            ["#uname", "and", "node1"]
        )
        self.assertSyntaxError(
            "unexpected '#uname' before 'or'",
            ["#uname", "or", "node1"]
        )
        self.assertSyntaxError(
            "unexpected '#uname' before 'or'",
            ["#uname", "or", "eq"]
        )
        self.assertSyntaxError(
            "unexpected 'node2' after 'and'",
            ["#uname", "eq", "node1", "and", "node2"]
        )
        self.assertUnexpectedEndOfInput(["#uname", "eq", "node1", "and"])
        self.assertUnexpectedEndOfInput(
            ["#uname", "eq", "node1", "and", "#uname", "eq"]
        )
        self.assertSyntaxError(
            "unexpected 'and'",
            ["and", "#uname", "eq", "node1"]
        )
        self.assertSyntaxError(
            "unexpected 'duration' after 'and'",
            ["#uname", "ne", "node1", "and", "duration", "hours=1"]
        )
        self.assertSyntaxError(
            "unexpected 'duration' before 'or'",
            ["duration", "monthdays=1", "or", "#uname", "ne", "node1"]
        )

    def testParenthesizedExpression(self):
        self.assertSyntaxError(
            "missing one of 'eq', 'ne', 'lt', 'gt', 'lte', 'gte', 'in_range', "
            "'defined', 'not_defined', 'date-spec'",
            ["(", "#uname", ")"]
        )
        self.assertEqual(
            "(date-spec (literal hours=1))",
            str(self.parser.parse(["(", "date-spec", "hours=1", ")"]))
        )
        self.assertEqual(
            "(eq (literal #uname) (literal node1))",
            str(self.parser.parse(["(", "#uname", "eq", "node1", ")"]))
        )
        self.assertEqual(
            "(defined (literal pingd))",
            str(self.parser.parse(["(", "defined", "pingd", ")"]))
        )
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(ne (literal #uname) (literal node2))"
            ")",
            str(self.parser.parse([
                "(",
                    "#uname", "ne", "node1", "and", "#uname", "ne", "node2",
                ")"
            ]))
        )
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(ne (literal #uname) (literal node2))"
            ")",
            str(self.parser.parse([
                "(", "#uname", "ne", "node1", ")",
                "and",
                "(", "#uname", "ne", "node2", ")"
            ]))
        )
        self.assertEqual(
            "(or "
                "(and "
                    "(ne (literal #uname) (literal node1)) "
                    "(ne (literal #uname) (literal node2))"
                ") "
                "(eq (literal #uname) (literal node3))"
            ")",
            str(self.parser.parse([
                "(",
                    "#uname", "ne", "node1", "and", "#uname", "ne", "node2",
                ")",
                "or", "#uname", "eq", "node3"
            ]))
        )
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(or "
                    "(ne (literal #uname) (literal node2)) "
                    "(eq (literal #uname) (literal node3))"
                ")"
            ")",
            str(self.parser.parse([
                "#uname", "ne", "node1",
                "and",
                "(", "#uname", "ne", "node2", "or", "#uname", "eq", "node3", ")"
            ]))
        )
        self.assertEqual(
            "(and "
                "(ne (literal #uname) (literal node1)) "
                "(or "
                    "(ne (literal #uname) (literal node2)) "
                    "(eq (literal #uname) (literal node3))"
                ")"
            ")",
            str(self.parser.parse([
                "(", "(",
                    "(", "#uname", "ne", "node1", ")",
                    "and",
                    "(", "(",
                        "(", "#uname", "ne", "node2", ")",
                        "or",
                        "(", "#uname", "eq", "node3", ")",
                    ")", ")",
                ")", ")"
            ]))
        )
        self.assertEqual(
            "(in_range "
                "(literal date) (literal 2014-06-26) (literal 2014-07-26)"
            ")",
            str(self.parser.parse([
                "(", "date", "in_range", "2014-06-26", "to", "2014-07-26", ")"
            ]))
        )

    def testParenthesizedExpressionBad(self):
        self.assertUnexpectedEndOfInput(["("])
        self.assertSyntaxError(
            "unexpected ')'",
            ["(", ")"]
        )
        self.assertSyntaxError(
            "missing ')'",
            ["(", "#uname"]
        )
        self.assertUnexpectedEndOfInput(["(", "#uname", "eq"])
        self.assertSyntaxError(
            "missing ')'",
            ["(", "#uname", "eq", "node1"]
        )

    def assertUnexpectedEndOfInput(self, program):
        self.assertRaises(rule.UnexpectedEndOfInput, self.parser.parse, program)

    def assertSyntaxError(self, syntax_error, program):
        self.assertRaises(
            rule.SyntaxError, self.parser.parse, program
        )
        try:
            self.parser.parse(program)
        except rule.SyntaxError as e:
            self.assertEqual(syntax_error, str(e))


class CibBuilderTest(unittest.TestCase):

    def setUp(self):
        self.parser = rule.RuleParser()
        self.builder = rule.CibBuilder()

    def testSingleLiteralDatespec(self):
        self.assertExpressionXml(
            ["date-spec", "hours=1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="date_spec">
            <date_spec hours="1" id="location-dummy-rule-expr-datespec"/>
        </date_expression>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date-spec", "hours=1-14 monthdays=20-30 months=1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="date_spec">
            <date_spec hours="1-14" id="location-dummy-rule-expr-datespec" monthdays="20-30" months="1"/>
        </date_expression>
    </rule>
</rsc_location>
            """
        )

    def testSimpleExpression(self):
        self.assertExpressionXml(
            ["#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "ne", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "gt", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="gt" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "gte", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="gte" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "lt", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="lt" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "lte", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="lte" value="node1"/>
    </rule>
</rsc_location>
            """
        )

    def testTypeExpression(self):
        self.assertExpressionXml(
            ["#uname", "eq", "string", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" type="string" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "eq", "integer", "12345"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" type="number" value="12345"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "eq", "version", "1.2.3"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" type="version" value="1.2.3"/>
    </rule>
</rsc_location>
            """
        )

    def testDefinedExpression(self):
        self.assertExpressionXml(
            ["defined", "pingd"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="pingd" id="location-dummy-rule-expr" operation="defined"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["not_defined", "pingd"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="pingd" id="location-dummy-rule-expr" operation="not_defined"/>
    </rule>
</rsc_location>
            """
        )

    def testDateExpression(self):
        self.assertExpressionXml(
            ["date", "gt", "2014-06-26"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="gt" start="2014-06-26"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "lt", "2014-06-26"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression end="2014-06-26" id="location-dummy-rule-expr" operation="lt"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "in_range", "2014-06-26", "to", "2014-07-26"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression end="2014-07-26" id="location-dummy-rule-expr" operation="in_range" start="2014-06-26"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "in_range", "2014-06-26", "to", "duration", "years=1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="in_range" start="2014-06-26">
            <duration id="location-dummy-rule-expr-duration" years="1"/>
        </date_expression>
    </rule>
</rsc_location>
            """
        )

    def testNotDateExpression(self):
        self.assertExpressionXml(
            ["date", "eq", "2014-06-26"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="date" id="location-dummy-rule-expr" operation="eq" value="2014-06-26"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "gt", "string", "2014-06-26"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="date" id="location-dummy-rule-expr" operation="gt" type="string" value="2014-06-26"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "gt", "integer", "12345"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="date" id="location-dummy-rule-expr" operation="gt" type="number" value="12345"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date", "gt", "version", "1.2.3"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule">
        <expression attribute="date" id="location-dummy-rule-expr" operation="gt" type="version" value="1.2.3"/>
    </rule>
</rsc_location>
            """
        )

    def testAndOrExpression(self):
        self.assertExpressionXml(
            ["#uname", "ne", "node1", "and", "#uname", "ne", "node2"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-1" operation="ne" value="node2"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["#uname", "eq", "node1", "or", "#uname", "eq", "node2"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-1" operation="eq" value="node2"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "#uname", "ne", "node1",
                "and", "#uname", "ne", "node2",
                "and", "#uname", "ne", "node3"
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-1" operation="ne" value="node2"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-2" operation="ne" value="node3"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "#uname", "ne", "node1",
                "and", "#uname", "ne", "node2",
                "or", "#uname", "eq", "node3"
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <rule boolean-op="and" id="location-dummy-rule-rule">
            <expression attribute="#uname" id="location-dummy-rule-rule-expr" operation="ne" value="node1"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-expr-1" operation="ne" value="node2"/>
        </rule>
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node3"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "#uname", "eq", "node1",
                "or", "#uname", "eq", "node2",
                "and", "#uname", "ne", "node3"
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <rule boolean-op="or" id="location-dummy-rule-rule">
            <expression attribute="#uname" id="location-dummy-rule-rule-expr" operation="eq" value="node1"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-expr-1" operation="eq" value="node2"/>
        </rule>
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node3"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["defined", "pingd", "and", "pingd", "lte", "1"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="pingd" id="location-dummy-rule-expr" operation="defined"/>
        <expression attribute="pingd" id="location-dummy-rule-expr-1" operation="lte" value="1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["pingd", "gt", "1", "or", "not_defined", "pingd"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <expression attribute="pingd" id="location-dummy-rule-expr" operation="gt" value="1"/>
        <expression attribute="pingd" id="location-dummy-rule-expr-1" operation="not_defined"/>
    </rule>
</rsc_location>
            """
        )

    def testAndOrExpressionDateSpec(self):
        self.assertExpressionXml(
            ["#uname", "ne", "node1", "and", "date-spec", "hours=1-12"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
        <date_expression id="location-dummy-rule-expr-1" operation="date_spec">
            <date_spec hours="1-12" id="location-dummy-rule-expr-1-datespec"/>
        </date_expression>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date-spec", "monthdays=1-12", "or", "#uname", "ne", "node1"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="date_spec">
            <date_spec id="location-dummy-rule-expr-datespec" monthdays="1-12"/>
        </date_expression>
        <expression attribute="#uname" id="location-dummy-rule-expr-1" operation="ne" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["date-spec", "monthdays=1-10", "or", "date-spec", "monthdays=11-20"],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <date_expression id="location-dummy-rule-expr" operation="date_spec">
            <date_spec id="location-dummy-rule-expr-datespec" monthdays="1-10"/>
        </date_expression>
        <date_expression id="location-dummy-rule-expr-1" operation="date_spec">
            <date_spec id="location-dummy-rule-expr-1-datespec" monthdays="11-20"/>
        </date_expression>
    </rule>
</rsc_location>
            """
        )

    def testParenthesizedExpression(self):
        self.assertExpressionXml(
            [
                "(",
                    "#uname", "ne", "node1", "and", "#uname", "ne", "node2",
                ")",
                "or", "#uname", "eq", "node3"
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <rule boolean-op="and" id="location-dummy-rule-rule">
            <expression attribute="#uname" id="location-dummy-rule-rule-expr" operation="ne" value="node1"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-expr-1" operation="ne" value="node2"/>
        </rule>
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node3"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "#uname", "ne", "node1",
                "and",
                "(", "#uname", "ne", "node2", "or", "#uname", "eq", "node3", ")"
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
        <rule boolean-op="or" id="location-dummy-rule-rule">
            <expression attribute="#uname" id="location-dummy-rule-rule-expr" operation="ne" value="node2"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-expr-1" operation="eq" value="node3"/>
        </rule>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "(",
                    "#uname", "ne", "node1", "and", "#uname", "ne", "node2",
                ")",
                "or",
                "(",
                    "#uname", "ne", "node3", "and", "#uname", "ne", "node4",
                ")",
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="or" id="location-dummy-rule">
        <rule boolean-op="and" id="location-dummy-rule-rule">
            <expression attribute="#uname" id="location-dummy-rule-rule-expr" operation="ne" value="node1"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-expr-1" operation="ne" value="node2"/>
        </rule>
        <rule boolean-op="and" id="location-dummy-rule-rule-1">
            <expression attribute="#uname" id="location-dummy-rule-rule-1-expr" operation="ne" value="node3"/>
            <expression attribute="#uname" id="location-dummy-rule-rule-1-expr-1" operation="ne" value="node4"/>
        </rule>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            [
                "(",
                    "#uname", "ne", "node1", "and", "#uname", "ne", "node2",
                ")",
                "and",
                "(",
                    "#uname", "ne", "node3", "and", "#uname", "ne", "node4",
                ")",
            ],
            """
<rsc_location id="location-dummy">
    <rule boolean-op="and" id="location-dummy-rule">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="ne" value="node1"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-1" operation="ne" value="node2"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-2" operation="ne" value="node3"/>
        <expression attribute="#uname" id="location-dummy-rule-expr-3" operation="ne" value="node4"/>
    </rule>
</rsc_location>
            """
        )

    def assertExpressionXml(self, rule_expression, rule_xml):
        cib_dom = xml.dom.minidom.parse(empty_cib)
        constraints = cib_dom.getElementsByTagName("constraints")[0]
        constraint_el = constraints.appendChild(
            cib_dom.createElement("rsc_location")
        )
        constraint_el.setAttribute("id", "location-dummy")
        ac(
            self.builder.build(
                constraint_el,
                self.parser.parse(rule_expression)
            ).parentNode.toprettyxml(indent="    "),
            rule_xml.lstrip().rstrip(" ")
        )


class TokenPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.preprocessor = rule.TokenPreprocessor()

    def testNoChanges(self):
        self.assertEqual([], self.preprocessor.run([]))
        self.assertEqual(
            ["#uname", "eq", "node1"],
            self.preprocessor.run(["#uname", "eq", "node1"])
        )

    def testDateSpec(self):
        self.assertEqual(
            ["date-spec"],
            self.preprocessor.run(["date-spec"])
        )
        self.assertEqual(
            ["date-spec", "hours=14"],
            self.preprocessor.run(["date-spec", "hours=14"])
        )
        self.assertEqual(
            ["date-spec", "hours weeks=6 months= moon=1"],
            self.preprocessor.run(
                ["date-spec", "hours", "weeks=6", "months=", "moon=1"]
            )
        )
        self.assertEqual(
            ["date-spec", "foo", "hours=14"],
            self.preprocessor.run(["date-spec", "foo", "hours=14"])
        )
        self.assertEqual(
            ["date-spec", "hours=14", "foo", "hours=14"],
            self.preprocessor.run(["date-spec", "hours=14", "foo", "hours=14"])
        )
        self.assertEqual(
            [
                "date-spec",
                "hours=1 monthdays=2 weekdays=3 yeardays=4 months=5 "
                "weeks=6 years=7 weekyears=8 moon=9"
            ],
            self.preprocessor.run([
                "date-spec",
                "hours=1", "monthdays=2", "weekdays=3", "yeardays=4",
                "months=5","weeks=6", "years=7", "weekyears=8", "moon=9"
            ])
        )
        self.assertEqual(
            ["#uname", "eq", "node1", "or", "date-spec", "hours=14"],
            self.preprocessor.run([
                "#uname", "eq", "node1", "or", "date-spec", "hours=14"
            ])
        )
        self.assertEqual(
            ["date-spec", "hours=14", "or", "#uname", "eq", "node1"],
            self.preprocessor.run([
                "date-spec", "hours=14", "or", "#uname", "eq", "node1",
            ])
        )

    def testDuration(self):
        self.assertEqual(
            ["duration"],
            self.preprocessor.run(["duration"])
        )
        self.assertEqual(
            ["duration", "hours=14"],
            self.preprocessor.run(["duration", "hours=14"])
        )
        self.assertEqual(
            ["duration", "hours weeks=6 months= moon=1"],
            self.preprocessor.run(
                ["duration", "hours", "weeks=6", "months=", "moon=1"]
            )
        )
        self.assertEqual(
            ["duration", "foo", "hours=14"],
            self.preprocessor.run(["duration", "foo", "hours=14"])
        )
        self.assertEqual(
            ["duration", "hours=14", "foo", "hours=14"],
            self.preprocessor.run(["duration", "hours=14", "foo", "hours=14"])
        )
        self.assertEqual(
            [
                "duration",
                "hours=1 monthdays=2 weekdays=3 yeardays=4 months=5 "
                "weeks=6 years=7 weekyears=8 moon=9"
            ],
            self.preprocessor.run([
                "duration",
                "hours=1", "monthdays=2", "weekdays=3", "yeardays=4",
                "months=5","weeks=6", "years=7", "weekyears=8", "moon=9"
            ])
        )
        self.assertEqual(
            ["#uname", "eq", "node1", "or", "duration", "hours=14"],
            self.preprocessor.run([
                "#uname", "eq", "node1", "or", "duration", "hours=14"
            ])
        )
        self.assertEqual(
            ["duration", "hours=14", "or", "#uname", "eq", "node1"],
            self.preprocessor.run([
                "duration", "hours=14", "or", "#uname", "eq", "node1",
            ])
        )

    def testOperationDatespec(self):
        self.assertEqual(
            ["date-spec", "weeks=6 moon=1"],
            self.preprocessor.run(
                ["date-spec", "operation=date_spec", "weeks=6", "moon=1"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6 moon=1"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "operation=date_spec", "moon=1"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6", "foo", "moon=1"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "operation=date_spec", "foo", "moon=1"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6", "foo", "operation=date_spec", "moon=1"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "foo", "operation=date_spec", "moon=1"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6 moon=1"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "moon=1", "operation=date_spec"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6 moon=1", "foo"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "moon=1", "operation=date_spec", "foo"]
            )
        )
        self.assertEqual(
            ["date-spec"],
            self.preprocessor.run(
                ["date-spec", "operation=date_spec"]
            )
        )
        self.assertEqual(
            ["date-spec", "weeks=6", "operation=foo", "moon=1"],
            self.preprocessor.run(
                ["date-spec", "weeks=6", "operation=foo", "moon=1"]
            )
        )

    def testDateLegacySyntax(self):
        # valid syntax
        self.assertEqual(
            ["date", "gt", "2014-06-26"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "gt"
            ])
        )
        self.assertEqual(
            ["date", "lt", "2014-06-26"],
            self.preprocessor.run([
                "date", "end=2014-06-26", "lt"
            ])
        )
        self.assertEqual(
            ["date", "in_range", "2014-06-26", "to", "2014-07-26"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "end=2014-07-26", "in_range"
            ])
        )
        self.assertEqual(
            ["date", "in_range", "2014-06-26", "to", "2014-07-26"],
            self.preprocessor.run([
                "date", "end=2014-07-26", "start=2014-06-26", "in_range"
            ])
        )

        self.assertEqual(
            ["date", "gt", "2014-06-26", "foo"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "gt", "foo"
            ])
        )
        self.assertEqual(
            ["date", "lt", "2014-06-26", "foo"],
            self.preprocessor.run([
                "date", "end=2014-06-26", "lt", "foo"
            ])
        )
        self.assertEqual(
            ["date", "in_range", "2014-06-26", "to", "2014-07-26", "foo"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "end=2014-07-26", "in_range", "foo"
            ])
        )
        self.assertEqual(
            ["date", "in_range", "2014-06-26", "to", "2014-07-26", "foo"],
            self.preprocessor.run([
                "date", "end=2014-07-26", "start=2014-06-26", "in_range", "foo"
            ])
        )

        # invalid syntax - no change
        self.assertEqual(
            ["date"],
            self.preprocessor.run([
                "date"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26"],
            self.preprocessor.run([
                "date", "start=2014-06-26"
            ])
        )
        self.assertEqual(
            ["date", "end=2014-06-26"],
            self.preprocessor.run([
                "date", "end=2014-06-26"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26", "end=2014-07-26"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "end=2014-07-26"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26", "end=2014-07-26", "lt"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "end=2014-07-26", "lt"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26", "lt", "foo"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "lt", "foo"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26", "end=2014-07-26", "gt", "foo"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "end=2014-07-26", "gt", "foo"
            ])
        )
        self.assertEqual(
            ["date", "end=2014-06-26", "gt"],
            self.preprocessor.run([
                "date", "end=2014-06-26", "gt"
            ])
        )
        self.assertEqual(
            ["date", "start=2014-06-26", "in_range", "foo"],
            self.preprocessor.run([
                "date", "start=2014-06-26", "in_range", "foo"
            ])
        )
        self.assertEqual(
            ["date", "end=2014-07-26", "in_range"],
            self.preprocessor.run([
                "date", "end=2014-07-26", "in_range"
            ])
        )
        self.assertEqual(
            ["foo", "start=2014-06-26", "gt"],
            self.preprocessor.run([
                "foo", "start=2014-06-26", "gt"
            ])
        )
        self.assertEqual(
            ["foo", "end=2014-06-26", "lt"],
            self.preprocessor.run([
                "foo", "end=2014-06-26", "lt"
            ])
        )

    def testParenthesis(self):
        self.assertEqual(
            ["("],
            self.preprocessor.run(["("])
        )
        self.assertEqual(
            [")"],
            self.preprocessor.run([")"])
        )
        self.assertEqual(
            ["(", "(", ")", ")"],
            self.preprocessor.run(["(", "(", ")", ")"])
        )
        self.assertEqual(
            ["(", "(", ")", ")"],
            self.preprocessor.run(["(())"])
        )
        self.assertEqual(
            ["a", "(", "b", ")", "c"],
            self.preprocessor.run(["a", "(", "b", ")", "c"])
        )
        self.assertEqual(
            ["a", "(", "b", "c", ")", "d"],
            self.preprocessor.run(["a", "(", "b", "c", ")", "d"])
        )
        self.assertEqual(
            ["a", ")", "b", "(", "c"],
            self.preprocessor.run(["a", ")", "b", "(", "c"])
        )
        self.assertEqual(
            ["a", "(", "b", ")", "c"],
            self.preprocessor.run(["a", "(b)", "c"])
        )
        self.assertEqual(
            ["a", "(", "b", ")", "c"],
            self.preprocessor.run(["a(", "b", ")c"])
        )
        self.assertEqual(
            ["a", "(", "b", ")", "c"],
            self.preprocessor.run(["a(b)c"])
        )
        self.assertEqual(
            ["aA", "(", "bB", ")", "cC"],
            self.preprocessor.run(["aA(bB)cC"])
        )
        self.assertEqual(
            ["(", "aA", "(", "bB", ")", "cC", ")"],
            self.preprocessor.run(["(aA(bB)cC)"])
        )
        self.assertEqual(
            ["(", "aA", "(", "(", "bB", ")", "cC", ")"],
            self.preprocessor.run(["(aA(", "(bB)cC)"])
        )
        self.assertEqual(
            ["(", "aA", "(", "(", "(", "bB", ")", "cC", ")"],
            self.preprocessor.run(["(aA(", "(", "(bB)cC)"])
        )

class ExportAsExpressionTest(unittest.TestCase):

    def test_success(self):
        self.assertXmlExport(
            """
            <rule id="location-dummy-rule" score="INFINITY">
                <expression attribute="#uname" id="location-dummy-rule-expr"
                    operation="eq" value="node1"/>
            </rule>
            """,
            "#uname eq node1",
            "#uname eq string node1"
        )
        self.assertXmlExport(
            """
            <rule id="location-dummy-rule" score="INFINITY">
                <expression attribute="foo" id="location-dummy-rule-expr"
                    operation="gt" type="version" value="1.2.3"/>
            </rule>
            """,
            "foo gt version 1.2.3",
            "foo gt version 1.2.3"
        )
        self.assertXmlExport(
            """
<rule boolean-op="or" id="complexRule" score="INFINITY">
    <rule boolean-op="and" id="complexRule-rule-1" score="0">
        <date_expression id="complexRule-rule-1-expr" operation="date_spec">
            <date_spec id="complexRule-rule-1-expr-datespec" weekdays="1-5" hours="12-23"/>
        </date_expression>
        <date_expression id="complexRule-rule-1-expr-1" operation="in_range" start="2014-07-26">
            <duration id="complexRule-rule-1-expr-1-duration" months="1"/>
        </date_expression>
    </rule>
    <rule boolean-op="and" id="complexRule-rule" score="0">
        <expression attribute="foo" id="complexRule-rule-expr-1" operation="gt" type="version" value="1.2"/>
        <expression attribute="#uname" id="complexRule-rule-expr" operation="eq" value="node3 4"/>
    </rule>
</rule>
            """,
            "(date-spec hours=12-23 weekdays=1-5 and date in_range 2014-07-26 to duration months=1) or (foo gt version 1.2 and #uname eq \"node3 4\")",
            "(#uname eq string \"node3 4\" and foo gt version 1.2) or (date in_range 2014-07-26 to duration months=1 and date-spec hours=12-23 weekdays=1-5)"
        )

    def assertXmlExport(self, rule_xml, export, export_normalized):
        ac(
            export + "\n",
            rule.ExportAsExpression().get_string(
                xml.dom.minidom.parseString(rule_xml).documentElement,
                normalize=False
            ) + "\n"
        )
        ac(
            export_normalized + "\n",
            rule.ExportAsExpression().get_string(
                xml.dom.minidom.parseString(rule_xml).documentElement,
                normalize=True
            ) + "\n"
        )


class DomRuleAddTest(unittest.TestCase):

    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        output, returnVal = pcs(
            temp_cib,
            "resource create dummy1 ocf:heartbeat:Dummy"
        )
        assert returnVal == 0 and output == ""

    def test_success_xml(self):
        self.assertExpressionXml(
            ["#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" score="INFINITY">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["id=myRule", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="myRule" score="INFINITY">
        <expression attribute="#uname" id="myRule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["score=INFINITY", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" score="INFINITY">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["score=100", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" score="100">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["score-attribute=pingd", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" score-attribute="pingd">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["role=master", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" role="master" score="INFINITY">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["role=slave", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="location-dummy-rule" role="slave" score="INFINITY">
        <expression attribute="#uname" id="location-dummy-rule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )
        self.assertExpressionXml(
            ["score=100", "id=myRule", "role=master", "#uname", "eq", "node1"],
            """
<rsc_location id="location-dummy">
    <rule id="myRule" role="master" score="100">
        <expression attribute="#uname" id="myRule-expr" operation="eq" value="node1"/>
    </rule>
</rsc_location>
            """
        )

    def test_success(self):
        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule #uname eq node1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule id=MyRule score=100 role=master #uname eq node2"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule id=complexRule (#uname eq node3 and foo gt version 1.2) or (date-spec hours=12-23 weekdays=1-5 and date in_range 2014-07-26 to duration months=1)"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score=INFINITY  (id:location-dummy1-rule)
        Expression: #uname eq node1  (id:location-dummy1-rule-expr)
    Constraint: location-dummy1-1
      Rule: role=master score=100  (id:MyRule)
        Expression: #uname eq node2  (id:MyRule-expr)
    Constraint: location-dummy1-2
      Rule: boolean-op=or score=INFINITY  (id:complexRule)
        Rule: boolean-op=and score=0  (id:complexRule-rule)
          Expression: #uname eq node3  (id:complexRule-rule-expr)
          Expression: foo gt version 1.2  (id:complexRule-rule-expr-1)
        Rule: boolean-op=and score=0  (id:complexRule-rule-1)
          Expression:  (id:complexRule-rule-1-expr)
            Date Spec: hours=12-23 weekdays=1-5  (id:complexRule-rule-1-expr-datespec)
          Expression: date in_range 2014-07-26 to duration  (id:complexRule-rule-1-expr-1)
            Duration: months=1  (id:complexRule-rule-1-expr-1-duration)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint location show")
        ac(output, """\
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
""")
        self.assertEqual(0, returnVal)

    def test_invalid_score(self):
        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule score=pingd defined pingd"
        )
        ac(
            output,
            "Warning: invalid score 'pingd', setting score-attribute=pingd "
                "instead\n"
        )
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score-attribute=pingd  (id:location-dummy1-rule)
        Expression: defined pingd  (id:location-dummy1-rule-expr)
""")
        self.assertEqual(0, returnVal)

    def test_invalid_rule(self):
        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule score=100"
        )
        ac(output, "Error: no rule expression was specified\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule #uname eq"
        )
        ac(
            output,
            "Error: '#uname eq' is not a valid rule expression: unexpected end "
                "of rule\n"
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule string #uname eq node1"
        )
        ac(
            output,
            "Error: 'string #uname eq node1' is not a valid rule expression: "
                "unexpected 'string' before 'eq'\n"
        )
        self.assertEqual(1, returnVal)

    def test_ivalid_options(self):
        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule role=foo #uname eq node1"
        )
        ac(output, "Error: invalid role 'foo', use 'master' or 'slave'\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule score=100 score-attribute=pingd #uname eq node1"
        )
        ac(output, "Error: can not specify both score and score-attribute\n")
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule id=1foo #uname eq node1"
        )
        ac(
            output,
            "Error: invalid rule id '1foo', '1' is not a valid first character "
                "for a rule id\n"
        )
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, "Location Constraints:\n")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule id=MyRule #uname eq node1"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint location show --full")
        ac(output, """\
Location Constraints:
  Resource: dummy1
    Constraint: location-dummy1
      Rule: score=INFINITY  (id:MyRule)
        Expression: #uname eq node1  (id:MyRule-expr)
""")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "constraint location dummy1 rule id=MyRule #uname eq node1"
        )
        ac(
            output,
            "Error: id 'MyRule' is already in use, please specify another one\n"
        )
        self.assertEqual(1, returnVal)

    def assertExpressionXml(self, rule_expression, rule_xml):
        cib_dom = xml.dom.minidom.parse(empty_cib)
        constraints = cib_dom.getElementsByTagName("constraints")[0]
        constraint_el = constraints.appendChild(
            cib_dom.createElement("rsc_location")
        )
        constraint_el.setAttribute("id", "location-dummy")
        options, rule_argv = rule.parse_argv(rule_expression)
        rule.dom_rule_add(constraint_el, options, rule_argv)
        ac(
            constraint_el.toprettyxml(indent="    "),
            rule_xml.lstrip().rstrip(" ")
        )
