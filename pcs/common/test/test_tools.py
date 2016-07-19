from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.common.tools import merge_dicts

class MergeDictsTest(TestCase):
    def test_merge_last_win(self):
        self.assertEqual(
            merge_dicts(
                {"a": 1, "b": 2},
                {"a": 3, "c": 4}
            ),
            {
                "a": 3,
                "b": 2,
                "c": 4,
            }
        )
