# Exporting rule xml elements to strings is an integral part of exporting rule
# xml elements to DTOs. There are extensive tests for that in
# pcs_test/tier0/lib/cib/rule/test_cib_to_dto.py and other tests in
# pcs_test/tier0/lib/cib/test_nvpair_multi.py and
# pcs_test/tier0/lib/commands/test_cib_options.py.
# Therefore we don't duplicate those here. However, if there's a need to write
# specific tests here, feel free to do so.


from unittest import TestCase

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
