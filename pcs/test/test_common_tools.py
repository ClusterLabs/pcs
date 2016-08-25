from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
import time

from pcs.common import tools


class TestException(Exception):
    pass


class SimpleCacheTestCase(TestCase):
    def test_called_only_once(self):
        counter = []

        @tools.simple_cache
        def adder():
            counter.append(None)
            return len(counter)

        self.assertEqual(1, adder())
        self.assertEqual(1, len(counter))
        self.assertEqual(1, adder())
        self.assertEqual(1, len(counter))
        counter.append(None)
        self.assertEqual(1, adder())
        self.assertEqual(2, len(counter))

    def test_exception_not_cached(self):
        counter = []

        @tools.simple_cache
        def adder():
            counter.append(None)
            raise TestException()

        self.assertRaises(TestException, adder)
        self.assertEqual(1, len(counter))
        self.assertRaises(TestException, adder)
        self.assertEqual(2, len(counter))


class RunParallelTestCase(TestCase):
    def test_run_all(self):
        data_list = [([i], {}) for i in range(5)]
        out_list = []
        tools.run_parallel(out_list.append, data_list)
        self.assertEqual(sorted(out_list), [i for i in range(5)])

    def test_parallelism(self):
        x = 5
        data_list = [[[i + 1], {}] for i in range(x)]
        start_time = time.time()
        # this should last for least x seconds, but less than sum of all times
        tools.run_parallel(time.sleep, data_list)
        finish_time = time.time()
        elapsed_time = finish_time - start_time
        self.assertTrue(elapsed_time > x)
        self.assertTrue(elapsed_time < sum([i + 1 for i in range(x)]))


class JoinMultilinesTest(TestCase):
    def test_empty_input(self):
        self.assertEqual(
            "",
            tools.join_multilines([])
        )

    def test_two_strings(self):
        self.assertEqual(
            "a\nb",
            tools.join_multilines(["a", "b"])
        )

    def test_strip(self):
        self.assertEqual(
            "a\nb",
            tools.join_multilines(["  a\n", "  b\n"])
        )

    def test_skip_empty(self):
        self.assertEqual(
            "a\nb",
            tools.join_multilines(["  a\n", "   \n", "  b\n"])
        )

    def test_multiline(self):
        self.assertEqual(
            "a\nA\nb\nB",
            tools.join_multilines(["a\nA\n", "b\nB\n"])
        )
