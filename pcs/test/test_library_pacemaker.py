from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import unittest
import os.path
import sys

currentdir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(currentdir))

import library_pacemaker as lib

class MiscTest(unittest.TestCase):
    def test_get_timeout_seconds(self):
        self.assertEqual(lib._get_timeout_seconds("10"), 10)
        self.assertEqual(lib._get_timeout_seconds("10s"), 10)
        self.assertEqual(lib._get_timeout_seconds("10sec"), 10)
        self.assertEqual(lib._get_timeout_seconds("10m"), 600)
        self.assertEqual(lib._get_timeout_seconds("10min"), 600)
        self.assertEqual(lib._get_timeout_seconds("10h"), 36000)
        self.assertEqual(lib._get_timeout_seconds("10hr"), 36000)

        self.assertEqual(lib._get_timeout_seconds("1a1s"), None)
        self.assertEqual(lib._get_timeout_seconds("10mm"), None)
        self.assertEqual(lib._get_timeout_seconds("10mim"), None)
        self.assertEqual(lib._get_timeout_seconds("aaa"), None)
        self.assertEqual(lib._get_timeout_seconds(""), None)

        self.assertEqual(lib._get_timeout_seconds("1a1s", True), "1a1s")
        self.assertEqual(lib._get_timeout_seconds("10mm", True), "10mm")
        self.assertEqual(lib._get_timeout_seconds("10mim", True), "10mim")
        self.assertEqual(lib._get_timeout_seconds("aaa", True), "aaa")
        self.assertEqual(lib._get_timeout_seconds("", True), "")


if __name__ == "__main__":
    unittest.main()
