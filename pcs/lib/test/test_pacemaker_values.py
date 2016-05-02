from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.lib.pacemaker_values import is_score_value

class IsScoreValueTest(TestCase):
    def test_returns_true_for_number(self):
        self.assertTrue(is_score_value("1"))

    def test_returns_true_for_minus_number(self):
        self.assertTrue(is_score_value("-1"))

    def test_returns_true_for_plus_number(self):
        self.assertTrue(is_score_value("+1"))

    def test_returns_true_for_infinity(self):
        self.assertTrue(is_score_value("INFINITY"))

    def test_returns_true_for_minus_infinity(self):
        self.assertTrue(is_score_value("-INFINITY"))

    def test_returns_true_for_plus_infinity(self):
        self.assertTrue(is_score_value("+INFINITY"))

    def test_returns_false_for_nonumber_noinfinity(self):
        self.assertFalse(is_score_value("something else"))

    def test_returns_false_for_multiple_operators(self):
        self.assertFalse(is_score_value("++INFINITY"))
