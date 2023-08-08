from unittest import TestCase

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.parse_args import (
    prepare_resource_sets,
    prepare_set_args,
)


class PrepareResourceSetsTest(TestCase):
    def test_prepare_resource_sets(self):
        self.assertEqual(
            prepare_resource_sets(
                [
                    "resA",
                    "resB",
                    "id=resource-set-1",
                    "set",
                    "resC",
                    "id=resource-set-2",
                    "sequential=true",
                ]
            ),
            [
                {"ids": ["resA", "resB"], "options": {"id": "resource-set-1"}},
                {
                    "ids": ["resC"],
                    "options": {"id": "resource-set-2", "sequential": "true"},
                },
            ],
        )

    def test_has_no_responsibility_to_assess_the_content(self):
        self.assertEqual(
            prepare_resource_sets([]),
            [{"ids": [], "options": {}}],
        )


class PrepareSetArgvTest(TestCase):
    def test_right_distribute_full_args(self):
        self.assertEqual(
            prepare_set_args(["A", "b=c", "setoptions", "d=e"]),
            ([{"ids": ["A"], "options": {"b": "c"}}], {"d": "e"}),
        )

    def test_right_distribute_args_without_options(self):
        self.assertEqual(
            prepare_set_args(["A", "b=c"]),
            ([{"ids": ["A"], "options": {"b": "c"}}], {}),
        )

    def test_right_distribute_args_with_empty_options(self):
        self.assertEqual(
            prepare_set_args(["A", "b=c", "setoptions"]),
            ([{"ids": ["A"], "options": {"b": "c"}}], {}),
        )

    def test_raises_when_no_set_specified(self):
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args([]))

    def test_raises_when_no_resource_in_set(self):
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args(["b=c"]))

    def test_raises_when_setoption_more_than_once(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: prepare_set_args(
                ["A", "b=c", "setoptions", "c=d", "setoptions", "e=f"]
            ),
        )
