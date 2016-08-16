from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.constraint_ticket import parse_args
from pcs.cli.common.errors import CmdLineInputError

class ParseAddTest(TestCase):
    def test_parse_add_args(self):
        self.assertEqual(
            parse_args.parse_add(
                ["T", "resource1", "ticket=T", "loss-policy=fence"]
            ),
            (
                "T",
                "resource1",
                "",
                {
                    "ticket": "T",
                    "loss-policy": "fence",
                }
            )
        )

    def test_parse_add_args_with_resource_role(self):
        self.assertEqual(
            parse_args.parse_add(
                ["T", "master",  "resource1", "ticket=T", "loss-policy=fence"]
            ),
            (
                "T",
                "resource1",
                "master",
                {
                    "ticket": "T",
                    "loss-policy": "fence",
                }
            )
        )

    def test_raises_when_invalid_resource_specification(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_add(
                ["T", "master", "resource1", "something_else"]
            )
        )

    def test_raises_when_ticket_and_resource_not_specified(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_add(
                ["loss-policy=fence"]
            )
        )

    def test_raises_when_resource_not_specified(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: parse_args.parse_add(
                ["T", "loss-policy=fence"]
            )
        )

class SeparateTailOptionCandidatesTest(TestCase):
    def test_separate_when_both_parts_there(self):
        self.assertEqual(
            (["a", "b"], ["c=d", "e=f"]),
            parse_args.separate_tail_option_candidates(["a", "b", "c=d", "e=f"])
        )

    def test_returns_empty_head_when_options_there_only(self):
        self.assertEqual(
            ([], ["c=d", "e=f"]),
            parse_args.separate_tail_option_candidates(["c=d", "e=f"])
        )

    def test_returns_empty_tail_when_no_options_there(self):
        self.assertEqual(
            (["a", "b"], []),
            parse_args.separate_tail_option_candidates(["a", "b"])
        )
