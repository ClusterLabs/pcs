from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.common.tools import (
    is_string,
    Version
)

class IsString(TestCase):
    def test_recognize_plain_string(self):
        self.assertTrue(is_string(""))

    def test_recognize_unicode_string(self):
        #in python3 this is str type
        self.assertTrue(is_string(u""))

    def test_rcognize_bytes(self):
        #in python3 this is str type
        self.assertTrue(is_string(b""))

    def test_list_of_string_is_not_string(self):
        self.assertFalse(is_string(["a", "b"]))


class VersionTest(TestCase):
    def assert_asterisk(self, expected, major, minor=None, revision=None):
        self.assertEqual(expected, (major, minor, revision))

    def assert_eq_tuple(self, a, b):
        self.assert_eq(Version(*a), Version(*b))
        self.assert_eq(a, Version(*b))
        self.assert_eq(Version(*a), b)

    def assert_lt_tuple(self, a, b):
        self.assert_lt(Version(*a), Version(*b))
        self.assert_lt(a, Version(*b))
        self.assert_lt(Version(*a), b)

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
        ver = Version(2)
        self.assert_asterisk((2, None, None), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, None)
        self.assertEqual(ver[1], None)
        self.assertEqual(ver.revision, None)
        self.assertEqual(ver[2], None)
        self.assertEqual(str(ver), "2")
        self.assertEqual(str(ver.normalize()), "2.0.0")

    def test_major_minor(self):
        ver = Version(2, 3)
        self.assert_asterisk((2, 3, None), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, 3)
        self.assertEqual(ver[1], 3)
        self.assertEqual(ver.revision, None)
        self.assertEqual(ver[2], None)
        self.assertEqual(str(ver), "2.3")
        self.assertEqual(str(ver.normalize()), "2.3.0")

    def test_major_minor_revision(self):
        ver = Version(2, 3, 4)
        self.assert_asterisk((2, 3, 4), *ver)
        self.assertEqual(ver.major, 2)
        self.assertEqual(ver[0], 2)
        self.assertEqual(ver.minor, 3)
        self.assertEqual(ver[1], 3)
        self.assertEqual(ver.revision, 4)
        self.assertEqual(ver[2], 4)
        self.assertEqual(str(ver), "2.3.4")
        self.assertEqual(str(ver.normalize()), "2.3.4")

    def test_compare(self):
        self.assert_eq_tuple((2, ), (2, ))
        self.assert_lt_tuple((2, ), (3, ))


        self.assert_eq_tuple((2, 0), (2, 0))
        self.assert_lt_tuple((2, 0), (2, 5))
        self.assert_lt_tuple((2, 0), (3, 5))

        self.assert_eq_tuple((2, 0), (2,  ))
        self.assert_lt_tuple((2, 0), (3,  ))
        self.assert_lt_tuple((2, 5), (3,  ))
        self.assert_lt_tuple((3,  ), (3, 5))


        self.assert_eq_tuple((2, 0, 0), (2, 0, 0))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 0))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 1))
        self.assert_lt_tuple((2, 0, 0), (3, 5, 1))

        self.assert_eq_tuple((2, 0, 0), (2, 0))
        self.assert_eq_tuple((2, 0, 0), (2,  ))
        self.assert_lt_tuple((2, 0, 0), (2, 5))
        self.assert_lt_tuple((2, 0, 0), (3,  ))

        self.assert_lt_tuple((2, 5, 0), (3,  ))
        self.assert_lt_tuple((2,  ), (2, 5, 0))
        self.assert_eq_tuple((2, 5, 0), (2, 5))
        self.assert_lt_tuple((2, 5, 0), (3, 5))

        self.assert_lt_tuple((2, 0), (2, 5, 1))
        self.assert_lt_tuple((2, 5), (2, 5, 1))
        self.assert_lt_tuple((2, 5, 1), (3, 5))
        self.assert_lt_tuple((2, 5, 1), (3,  ))
        self.assert_lt_tuple((2,  ), (2, 5, 1))
        self.assert_lt_tuple((2, 5, 1), (3,  ))

        self.assert_lt_tuple((2,  ), (3, 5, 1))
        self.assert_lt_tuple((3,  ), (3, 5, 1))
        self.assert_lt_tuple((2, 0), (3, 5, 1))
        self.assert_lt_tuple((2, 5), (3, 5, 1))
        self.assert_lt_tuple((3, 5), (3, 5, 1))
