from unittest import TestCase

from pcs.common import tools


class VersionTest(TestCase):
    # pylint: disable=invalid-name
    def assert_asterisk(self, expected, major, minor=None, revision=None):
        self.assertEqual(expected, (major, minor, revision))

    def assert_eq_tuple(self, a, b):
        self.assert_eq(tools.Version(*a), tools.Version(*b))

    def assert_lt_tuple(self, a, b):
        self.assert_lt(tools.Version(*a), tools.Version(*b))

    def assert_eq(self, a, b):
        self.assertTrue(a == b)
        self.assertFalse(a != b)
        self.assertFalse(a < b)
        self.assertTrue(a <= b)
        self.assertFalse(a > b)
        self.assertTrue(a >= b)

    def assert_lt(self, a, b):
        self.assertFalse(a == b)
        self.assertTrue(a != b)
        self.assertTrue(a < b)
        self.assertTrue(a <= b)
        self.assertFalse(a > b)
        self.assertFalse(a >= b)

    def test_major(self):
        ver = tools.Version(2)
        self.assert_asterisk((2, None, None), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, None)
        self.assertEqual(ver[1], None)
        self.assertEqual(ver.revision, None)
        self.assertEqual(ver[2], None)
        self.assertEqual(ver.as_full_tuple, (2, 0, 0))
        self.assertEqual(str(ver), "2")
        self.assertEqual(str(ver.normalize()), "2.0.0")

    def test_major_minor(self):
        ver = tools.Version(2, 3)
        self.assert_asterisk((2, 3, None), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, 3)
        self.assertEqual(ver[1], 3)
        self.assertEqual(ver.revision, None)
        self.assertEqual(ver[2], None)
        self.assertEqual(ver.as_full_tuple, (2, 3, 0))
        self.assertEqual(str(ver), "2.3")
        self.assertEqual(str(ver.normalize()), "2.3.0")

    def test_major_minor_revision(self):
        ver = tools.Version(2, 3, 4)
        self.assert_asterisk((2, 3, 4), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, 3)
        self.assertEqual(ver[1], 3)
        self.assertEqual(ver.revision, 4)
        self.assertEqual(ver[2], 4)
        self.assertEqual(ver.as_full_tuple, (2, 3, 4))
        self.assertEqual(str(ver), "2.3.4")
        self.assertEqual(str(ver.normalize()), "2.3.4")

    def test_compare(self):
        self.assert_eq_tuple((2,), (2,))
        self.assert_lt_tuple((2,), (3,))

        self.assert_eq_tuple((2, 0), (2, 0))
        self.assert_lt_tuple((2, 0), (2, 5))
        self.assert_lt_tuple((2, 0), (3, 5))

        self.assert_eq_tuple((2, 0), (2,))
        self.assert_lt_tuple((2, 0), (3,))
        self.assert_lt_tuple((2, 5), (3,))
        self.assert_lt_tuple((3,), (3, 5))

        self.assert_eq_tuple((2, 0, 0), (2, 0, 0))
        self.assert_lt_tuple((2, 0, 0), (2, 0, 1))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 0))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 1))
        self.assert_lt_tuple((2, 0, 0), (3, 0, 0))
        self.assert_lt_tuple((2, 0, 0), (3, 0, 1))
        self.assert_lt_tuple((2, 0, 0), (3, 5, 0))
        self.assert_lt_tuple((2, 0, 0), (3, 5, 1))

        self.assert_eq_tuple((2, 0, 0), (2, 0))
        self.assert_eq_tuple((2, 0, 0), (2,))
        self.assert_lt_tuple((2, 0, 0), (2, 5))
        self.assert_lt_tuple((2, 0, 0), (3,))

        self.assert_lt_tuple((2, 5, 0), (3,))
        self.assert_lt_tuple((2,), (2, 5, 0))
        self.assert_eq_tuple((2, 5, 0), (2, 5))
        self.assert_lt_tuple((2, 5, 0), (3, 5))

        self.assert_lt_tuple((2, 0), (2, 5, 1))
        self.assert_lt_tuple((2, 5), (2, 5, 1))
        self.assert_lt_tuple((2, 5, 1), (3, 5))
        self.assert_lt_tuple((2, 5, 1), (3,))
        self.assert_lt_tuple((2,), (2, 5, 1))
        self.assert_lt_tuple((2, 5, 1), (3,))

        self.assert_lt_tuple((2,), (3, 5, 1))
        self.assert_lt_tuple((3,), (3, 5, 1))
        self.assert_lt_tuple((2, 0), (3, 5, 1))
        self.assert_lt_tuple((2, 5), (3, 5, 1))
        self.assert_lt_tuple((3, 5), (3, 5, 1))


class TimeoutToSecondsTest(TestCase):
    def test_valid(self):
        self.assertEqual(10, tools.timeout_to_seconds(10))
        self.assertEqual(10, tools.timeout_to_seconds("10"))
        self.assertEqual(10, tools.timeout_to_seconds("10s"))
        self.assertEqual(10, tools.timeout_to_seconds("10sec"))
        self.assertEqual(600, tools.timeout_to_seconds("10m"))
        self.assertEqual(600, tools.timeout_to_seconds("10min"))
        self.assertEqual(36000, tools.timeout_to_seconds("10h"))
        self.assertEqual(36000, tools.timeout_to_seconds("10hr"))

    def test_invalid(self):
        self.assertEqual(None, tools.timeout_to_seconds(-10))
        self.assertEqual(None, tools.timeout_to_seconds("1a1s"))
        self.assertEqual(None, tools.timeout_to_seconds("10mm"))
        self.assertEqual(None, tools.timeout_to_seconds("10mim"))
        self.assertEqual(None, tools.timeout_to_seconds("aaa"))
        self.assertEqual(None, tools.timeout_to_seconds(""))
