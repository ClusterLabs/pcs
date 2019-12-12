import time
from unittest import TestCase

from pcs.common import tools


class RunParallelTestCase(TestCase):
    def test_run_all(self):
        data_list = [([i], {}) for i in range(5)]
        out_list = []
        tools.run_parallel(out_list.append, data_list)
        self.assertEqual(sorted(out_list), list(range(5)))

    def test_parallelism(self):
        timeout = 5
        data_list = [[[i + 1], {}] for i in range(timeout)]
        start_time = time.time()
        # this should last for least timeout seconds, but less than sum of all
        # times
        tools.run_parallel(time.sleep, data_list)
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        self.assertTrue(elapsed_time > timeout)
        self.assertTrue(elapsed_time < sum([i + 1 for i in range(timeout)]))


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
        self.assert_lt_tuple((2, 0, 0), (2, 0, 1))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 0))
        self.assert_lt_tuple((2, 0, 0), (2, 5, 1))
        self.assert_lt_tuple((2, 0, 0), (3, 0, 0))
        self.assert_lt_tuple((2, 0, 0), (3, 0, 1))
        self.assert_lt_tuple((2, 0, 0), (3, 5, 0))
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
