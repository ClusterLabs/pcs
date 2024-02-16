# Exporting rule xml elements to strings is an integral part of exporting rule
# xml elements to DTOs. There are extensive tests for that in
# pcs_test/tier0/lib/cib/rule/test_cib_to_dto.py and other tests in
# pcs_test/tier0/lib/cib/test_nvpair_multi.py and
# pcs_test/tier0/lib/commands/test_cib_options.py.
# Therefore we don't duplicate those here. However, if there's a need to write
# specific tests here, feel free to do so.


from unittest import TestCase

from lxml import etree

from pcs.lib.cib.rule.cib_to_str import RuleToStr


class IsoToStr(TestCase):
    # pylint: disable=protected-access
    def test_no_change(self):
        self.assertEqual(RuleToStr._date_to_str("2023-06"), "2023-06")
        self.assertEqual(RuleToStr._date_to_str("202306"), "202306")
        self.assertEqual(RuleToStr._date_to_str("2023-06-30"), "2023-06-30")
        self.assertEqual(RuleToStr._date_to_str("20230630"), "20230630")
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30T16:30"), "2023-06-30T16:30"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630T1630"), "20230630T1630"
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30T16:30Z"), "2023-06-30T16:30Z"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630T1630+2"), "20230630T1630+2"
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30T16:30:40+2:00"),
            "2023-06-30T16:30:40+2:00",
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630T1630+02:00"), "20230630T1630+02:00"
        )

    def test_remove_spaces(self):
        self.assertEqual(RuleToStr._date_to_str("- 2023"), "-2023")
        self.assertEqual(RuleToStr._date_to_str("+ 2023"), "+2023")
        self.assertEqual(RuleToStr._date_to_str("2023- 06"), "2023-06")
        self.assertEqual(RuleToStr._date_to_str("2023 -06- 30"), "2023-06-30")
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30  T16:30"), "2023-06-30T16:30"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630T   1630"), "20230630T1630"
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30 T 16:30  Z"), "2023-06-30T16:30Z"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630  T 1630 + 2"), "20230630T1630+2"
        )
        self.assertEqual(
            RuleToStr._date_to_str(
                "2023 -  06 - 30  T 16 :  30 :  40 +  2: 00"
            ),
            "2023-06-30T16:30:40+2:00",
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630  T   1630+ 02:00"),
            "20230630T1630+02:00",
        )

    def test_add_time_separator(self):
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30  16:30"), "2023-06-30T16:30"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630 1630"), "20230630T1630"
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30 16:30  Z"), "2023-06-30T16:30Z"
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630   1630 + 2"), "20230630T1630+2"
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023 -  06 - 30   16 :  30 :  40 +  2: 00"),
            "2023-06-30T16:30:40+2:00",
        )
        self.assertEqual(
            RuleToStr._date_to_str("20230630     1630+ 02:00"),
            "20230630T1630+02:00",
        )

    def test_extra_spaces(self):
        self.assertEqual(
            RuleToStr._date_to_str("2023-06-30 16:30:40 +2 00"),
            "2023-06-30T16:30:40+2 00",
        )
        self.assertEqual(
            RuleToStr._date_to_str("2023 06 30 16 30 +02"),
            "2023T06 30 16 30+02",
        )


class NormalizedStr(TestCase):
    def test_success(self):
        xml = etree.fromstring(
            """
            <rule boolean-op="or" id="R1" score="INFINITY">
              <rule id="R1-rule-1" boolean-op="and" score="0">
                <date_expression id="R1-rule-1-expr" operation="date_spec">
                  <date_spec id="R1-rule-1-expr-datespec"
                      weekdays="1-5" hours="12-23"
                  />
                </date_expression>
                <date_expression id="R1-rule-1-expr-1"
                    operation="in_range" start="2014-07-26"
                >
                  <duration id="R1-rule-1-expr-1-duration" months="1"/>
                </date_expression>
              </rule>
              <rule id="R1-rule" boolean-op="and" score="0">
                <expression id="R1-rule-expr-1"
                    attribute="foo" operation="gt" type="version" value="1.2"
                />
                <expression id="R1-rule-expr"
                    attribute="#uname" operation="eq" value="node3 4"
                />
              </rule>
            </rule>
            """
        )
        self.assertEqual(
            RuleToStr(normalize=True).get_str(xml),
            (
                '(#uname eq string "node3 4" and foo gt version 1.2) or '
                "(date in_range 2014-07-26 to duration months=1 and "
                "date-spec hours=12-23 weekdays=1-5)"
            ),
        )
