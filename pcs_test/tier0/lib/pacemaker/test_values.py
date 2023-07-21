import os
from unittest import TestCase

import pcs.lib.pacemaker.values as lib
from pcs import settings
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes

from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.custom_mock import get_runner_mock

# pylint: disable=no-self-use


class BooleanTest(TestCase):
    def test_true_is_true(self):
        self.assertTrue(lib.is_true("true"))
        self.assertTrue(lib.is_true("tRue"))
        self.assertTrue(lib.is_true("on"))
        self.assertTrue(lib.is_true("ON"))
        self.assertTrue(lib.is_true("yes"))
        self.assertTrue(lib.is_true("yeS"))
        self.assertTrue(lib.is_true("y"))
        self.assertTrue(lib.is_true("Y"))
        self.assertTrue(lib.is_true("1"))

    def test_nontrue_is_not_true(self):
        self.assertFalse(lib.is_true(""))
        self.assertFalse(lib.is_true(" 1 "))
        self.assertFalse(lib.is_true("a"))
        self.assertFalse(lib.is_true("2"))
        self.assertFalse(lib.is_true("10"))
        self.assertFalse(lib.is_true("yes please"))

    def test_true_is_boolean(self):
        self.assertTrue(lib.is_boolean("true"))
        self.assertTrue(lib.is_boolean("tRue"))
        self.assertTrue(lib.is_boolean("on"))
        self.assertTrue(lib.is_boolean("ON"))
        self.assertTrue(lib.is_boolean("yes"))
        self.assertTrue(lib.is_boolean("yeS"))
        self.assertTrue(lib.is_boolean("y"))
        self.assertTrue(lib.is_boolean("Y"))
        self.assertTrue(lib.is_boolean("1"))

    def test_false_is_false(self):
        self.assertTrue(lib.is_false("false"))
        self.assertTrue(lib.is_false("faLse"))
        self.assertTrue(lib.is_false("off"))
        self.assertTrue(lib.is_false("OFF"))
        self.assertTrue(lib.is_false("no"))
        self.assertTrue(lib.is_false("nO"))
        self.assertTrue(lib.is_false("n"))
        self.assertTrue(lib.is_false("N"))
        self.assertTrue(lib.is_false("0"))

    def test_nonfalse_is_not_false(self):
        self.assertFalse(lib.is_false(""))
        self.assertFalse(lib.is_false(" 0 "))
        self.assertFalse(lib.is_false("x"))
        self.assertFalse(lib.is_false("-1"))
        self.assertFalse(lib.is_false("10"))
        self.assertFalse(lib.is_false("heck no"))

    def test_false_is_boolean(self):
        self.assertTrue(lib.is_boolean("false"))
        self.assertTrue(lib.is_boolean("fAlse"))
        self.assertTrue(lib.is_boolean("off"))
        self.assertTrue(lib.is_boolean("oFf"))
        self.assertTrue(lib.is_boolean("no"))
        self.assertTrue(lib.is_boolean("nO"))
        self.assertTrue(lib.is_boolean("n"))
        self.assertTrue(lib.is_boolean("N"))
        self.assertTrue(lib.is_boolean("0"))

    def test_nonboolean_is_not_boolean(self):
        self.assertFalse(lib.is_boolean(""))
        self.assertFalse(lib.is_boolean("a"))
        self.assertFalse(lib.is_boolean("2"))
        self.assertFalse(lib.is_boolean("10"))
        self.assertFalse(lib.is_boolean("yes please"))
        self.assertFalse(lib.is_boolean(" y"))
        self.assertFalse(lib.is_boolean("n "))
        self.assertFalse(lib.is_boolean("NO!"))


class ValidateIdTest(TestCase):
    def test_valid(self):
        self.assertEqual(None, lib.validate_id("dummy"))
        self.assertEqual(None, lib.validate_id("DUMMY"))
        self.assertEqual(None, lib.validate_id("dUmMy"))
        self.assertEqual(None, lib.validate_id("dummy0"))
        self.assertEqual(None, lib.validate_id("dum0my"))
        self.assertEqual(None, lib.validate_id("dummy-"))
        self.assertEqual(None, lib.validate_id("dum-my"))
        self.assertEqual(None, lib.validate_id("dummy."))
        self.assertEqual(None, lib.validate_id("dum.my"))
        self.assertEqual(None, lib.validate_id("_dummy"))
        self.assertEqual(None, lib.validate_id("dummy_"))
        self.assertEqual(None, lib.validate_id("dum_my"))

    def test_invalid_empty(self):
        assert_raise_library_error(
            lambda: lib.validate_id("", "test id"),
            (
                severity.ERROR,
                report_codes.INVALID_ID_IS_EMPTY,
                {
                    "id_description": "test id",
                },
            ),
        )

    def test_invalid_first_character(self):
        desc = "test id"
        info = {
            "id": "",
            "id_description": desc,
            "invalid_character": "",
            "is_first_char": True,
        }
        report = (severity.ERROR, report_codes.INVALID_ID_BAD_CHAR, info)

        info["id"] = "0"
        info["invalid_character"] = "0"
        assert_raise_library_error(lambda: lib.validate_id("0", desc), report)

        info["id"] = "-"
        info["invalid_character"] = "-"
        assert_raise_library_error(lambda: lib.validate_id("-", desc), report)

        info["id"] = "."
        info["invalid_character"] = "."
        assert_raise_library_error(lambda: lib.validate_id(".", desc), report)

        info["id"] = ":"
        info["invalid_character"] = ":"
        assert_raise_library_error(lambda: lib.validate_id(":", desc), report)

        info["id"] = "0dummy"
        info["invalid_character"] = "0"
        assert_raise_library_error(
            lambda: lib.validate_id("0dummy", desc), report
        )

        info["id"] = "-dummy"
        info["invalid_character"] = "-"
        assert_raise_library_error(
            lambda: lib.validate_id("-dummy", desc), report
        )

        info["id"] = ".dummy"
        info["invalid_character"] = "."
        assert_raise_library_error(
            lambda: lib.validate_id(".dummy", desc), report
        )

        info["id"] = ":dummy"
        info["invalid_character"] = ":"
        assert_raise_library_error(
            lambda: lib.validate_id(":dummy", desc), report
        )

    def test_invalid_character(self):
        desc = "test id"
        info = {
            "id": "",
            "id_description": desc,
            "invalid_character": "",
            "is_first_char": False,
        }
        report = (severity.ERROR, report_codes.INVALID_ID_BAD_CHAR, info)

        info["id"] = "dum:my"
        info["invalid_character"] = ":"
        assert_raise_library_error(
            lambda: lib.validate_id("dum:my", desc), report
        )

        info["id"] = "dummy:"
        info["invalid_character"] = ":"
        assert_raise_library_error(
            lambda: lib.validate_id("dummy:", desc), report
        )

        info["id"] = "dum?my"
        info["invalid_character"] = "?"
        assert_raise_library_error(
            lambda: lib.validate_id("dum?my", desc), report
        )

        info["id"] = "dummy?"
        info["invalid_character"] = "?"
        assert_raise_library_error(
            lambda: lib.validate_id("dummy?", desc), report
        )


class SanitizeId(TestCase):
    def test_dont_change_valid_id(self):
        self.assertEqual("d", lib.sanitize_id("d"))
        self.assertEqual("dummy", lib.sanitize_id("dummy"))
        self.assertEqual("dum0my", lib.sanitize_id("dum0my"))
        self.assertEqual("dum-my", lib.sanitize_id("dum-my"))
        self.assertEqual("dum.my", lib.sanitize_id("dum.my"))
        self.assertEqual("dum_my", lib.sanitize_id("dum_my"))
        self.assertEqual("_dummy", lib.sanitize_id("_dummy"))

    def test_empty(self):
        self.assertEqual("", lib.sanitize_id(""))

    def test_invalid_id(self):
        self.assertEqual("", lib.sanitize_id("0"))
        self.assertEqual("", lib.sanitize_id("-"))
        self.assertEqual("", lib.sanitize_id("."))
        self.assertEqual("", lib.sanitize_id(":", "_"))

        self.assertEqual("dummy", lib.sanitize_id("0dummy"))
        self.assertEqual("dummy", lib.sanitize_id("-dummy"))
        self.assertEqual("dummy", lib.sanitize_id(".dummy"))
        self.assertEqual("dummy", lib.sanitize_id(":dummy", "_"))

        self.assertEqual("dummy", lib.sanitize_id("dum:my"))
        self.assertEqual("dum_my", lib.sanitize_id("dum:my", "_"))


class IsScoreValueTest(TestCase):
    def test_returns_true_for_number(self):
        self.assertTrue(lib.is_score("1"))

    def test_returns_true_for_minus_number(self):
        self.assertTrue(lib.is_score("-1"))

    def test_returns_true_for_plus_number(self):
        self.assertTrue(lib.is_score("+1"))

    def test_returns_true_for_infinity(self):
        self.assertTrue(lib.is_score("INFINITY"))

    def test_returns_true_for_minus_infinity(self):
        self.assertTrue(lib.is_score("-INFINITY"))

    def test_returns_true_for_plus_infinity(self):
        self.assertTrue(lib.is_score("+INFINITY"))

    def test_returns_false_for_nonumber_noinfinity(self):
        self.assertFalse(lib.is_score("something else"))

    def test_returns_false_for_multiple_operators(self):
        self.assertFalse(lib.is_score("++INFINITY"))


class IsDurationValueTest(TestCase):
    def assert_is_duration(self, return_value):
        duration = "P"
        mock_runner = get_runner_mock(returncode=0 if return_value else 1)
        self.assertEqual(lib.is_duration(mock_runner, duration), return_value)
        mock_runner.run.assert_called_once_with(
            [
                os.path.join(settings.pacemaker_binaries, "iso8601"),
                "--duration",
                duration,
            ]
        )

    def test_duration_valid(self):
        self.assert_is_duration(True)

    def test_duration_invalid(self):
        self.assert_is_duration(False)
