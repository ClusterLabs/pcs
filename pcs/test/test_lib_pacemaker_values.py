from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.test.library_test_tools import LibraryAssertionMixin

import pcs.lib.error_codes as error_codes
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.pacemaker_values as lib

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


class ValidateIdTest(TestCase, LibraryAssertionMixin):
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
        self.assert_raise_library_error(
            lambda: lib.validate_id("", "test id"),
            (
                severity.ERROR,
                error_codes.INVALID_ID,
                {
                    "id": "",
                    "description": "test id",
                    "reason": "empty",
                }
            )
        )

    def test_invalid_first_character(self):
        desc = "test id"
        info = {
            "id": "",
            "description": desc,
            "reason": "invalid first character",
            "invalid_character": "",
        }
        report = (severity.ERROR, error_codes.INVALID_ID, info)

        info["id"] = "0"
        info["invalid_character"] = "0"
        self.assert_raise_library_error(
            lambda: lib.validate_id("0", desc),
            report
        )

        info["id"] = "-"
        info["invalid_character"] = "-"
        self.assert_raise_library_error(
            lambda: lib.validate_id("-", desc),
            report
        )

        info["id"] = "."
        info["invalid_character"] = "."
        self.assert_raise_library_error(
            lambda: lib.validate_id(".", desc),
            report
        )

        info["id"] = ":"
        info["invalid_character"] = ":"
        self.assert_raise_library_error(
            lambda: lib.validate_id(":", desc),
            report
        )

        info["id"] = "0dummy"
        info["invalid_character"] = "0"
        self.assert_raise_library_error(
            lambda: lib.validate_id("0dummy", desc),
            report
        )

        info["id"] = "-dummy"
        info["invalid_character"] = "-"
        self.assert_raise_library_error(
            lambda: lib.validate_id("-dummy", desc),
            report
        )

        info["id"] = ".dummy"
        info["invalid_character"] = "."
        self.assert_raise_library_error(
            lambda: lib.validate_id(".dummy", desc),
            report
        )

        info["id"] = ":dummy"
        info["invalid_character"] = ":"
        self.assert_raise_library_error(
            lambda: lib.validate_id(":dummy", desc),
            report
        )

    def test_invalid_character(self):
        desc = "test id"
        info = {
            "id": "",
            "description": desc,
            "reason": "invalid character",
            "invalid_character": "",
        }
        report = (severity.ERROR, error_codes.INVALID_ID, info)

        info["id"] = "dum:my"
        info["invalid_character"] = ":"
        self.assert_raise_library_error(
            lambda: lib.validate_id("dum:my", desc),
            report
        )

        info["id"] = "dummy:"
        info["invalid_character"] = ":"
        self.assert_raise_library_error(
            lambda: lib.validate_id("dummy:", desc),
            report
        )

        info["id"] = "dum?my"
        info["invalid_character"] = "?"
        self.assert_raise_library_error(
            lambda: lib.validate_id("dum?my", desc),
            report
        )

        info["id"] = "dummy?"
        info["invalid_character"] = "?"
        self.assert_raise_library_error(
            lambda: lib.validate_id("dummy?", desc),
            report
        )

