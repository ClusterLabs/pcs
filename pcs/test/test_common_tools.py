from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.common import tools


class CommonToolsTest(TestCase):
    pass


class TestException(Exception):
    pass


class SimpleCacheTest(CommonToolsTest):
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
