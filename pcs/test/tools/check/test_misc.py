from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.misc import outdent

class OutdentTest(TestCase):
    def test_returns_the_same_text_when_not_indented(self):
        text = "\n".join([
            "first line",
            "  second line",
            "    third line",
        ])
        self.assertEqual(text, outdent(text))

    def test_remove_the_smallest_indentation(self):
        self.assertEqual(
            "\n".join([
                "  first line",
                "second line",
                "  third line",
            ]),
            outdent("\n".join([
                "    first line",
                "  second line",
                "    third line",
            ]))
        )

    def test_very_ugly_indented_text(self):
        self.assertEqual(
            """\
Cluster Name: test99
  Options:
""",
            outdent("""\
                Cluster Name: test99
                  Options:
                """
            )
        )
