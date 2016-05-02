from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.cli.common.console_report import indent

class IndentTest(TestCase):
    def test_indent_list_of_lines(self):
        self.assertEqual(
            indent([
                "first",
                "second"
            ]),
            [
                "  first",
                "  second"
            ]
        )
