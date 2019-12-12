from unittest import TestCase

from pcs.common import str_tools as tools


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


class IndentTest(TestCase):
    def test_indent_list_of_lines(self):
        self.assertEqual(
            tools.indent([
                "first",
                "second"
            ]),
            [
                "  first",
                "  second"
            ]
        )
