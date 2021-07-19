from unittest import TestCase

from pcs.cli.common import tools


class TimeoutToSecondsLegacyTest(TestCase):
    def test_valid(self):
        self.assertEqual(10, tools.timeout_to_seconds_legacy(10))
        self.assertEqual(10, tools.timeout_to_seconds_legacy("10"))
        self.assertEqual(10, tools.timeout_to_seconds_legacy("10s"))
        self.assertEqual(10, tools.timeout_to_seconds_legacy("10sec"))
        self.assertEqual(600, tools.timeout_to_seconds_legacy("10m"))
        self.assertEqual(600, tools.timeout_to_seconds_legacy("10min"))
        self.assertEqual(36000, tools.timeout_to_seconds_legacy("10h"))
        self.assertEqual(36000, tools.timeout_to_seconds_legacy("10hr"))

    def test_invalid(self):
        self.assertEqual(-10, tools.timeout_to_seconds_legacy(-10))
        self.assertEqual("1a1s", tools.timeout_to_seconds_legacy("1a1s"))
        self.assertEqual("10mm", tools.timeout_to_seconds_legacy("10mm"))
        self.assertEqual("10mim", tools.timeout_to_seconds_legacy("10mim"))
        self.assertEqual("aaa", tools.timeout_to_seconds_legacy("aaa"))
        self.assertEqual("", tools.timeout_to_seconds_legacy(""))
