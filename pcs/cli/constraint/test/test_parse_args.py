from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.parse_args import prepare_set_args, prepare_resource_sets
from pcs.test.tools.pcs_unittest import mock


@mock.patch("pcs.cli.common.parse_args.prepare_options")
class PrepareResourceSetsTest(TestCase):
    def test_prepare_resource_sets(self, options):
        opts = [{"id": "1"}, {"id": "2", "sequential": "true"}]
        options.side_effect = opts
        self.assertEqual(
            [
                {"ids": ["resA", "resB"], "options":opts[0]},
                {"ids": ["resC"], "options": opts[1]},
            ],
            prepare_resource_sets([
                "resA", "resB", "id=resource-set-1",
                "set",
                "resC", "id=resource-set-2", "sequential=true",
            ])
        )

    def test_has_no_responsibility_to_assess_the_content(self, options):
        options.return_value = {}
        self.assertEqual([{"ids":[], "options":{}}], prepare_resource_sets([]))

@mock.patch("pcs.cli.common.parse_args.prepare_options")
@mock.patch("pcs.cli.constraint.parse_args.prepare_resource_sets")
class PrepareSetArgvTest(TestCase):
    def test_return_tuple_of_given_resource_set_list_and_options(
        self, res_sets, options
    ):
        res_sets.return_value = [{"ids": "A"}]
        options.return_value = 'O'

        self.assertEqual(
            ([{"ids": "A"}], "O"),
            prepare_set_args(['A', 'b=c', "setoptions", "d=e"])
        )

    def test_right_distribute_full_args(self, res_sets, options):
        prepare_set_args(['A', 'b=c', "setoptions", "d=e"])
        res_sets.assert_called_once_with(['A', 'b=c'])
        options.assert_called_once_with(["d=e"])

    def test_right_distribute_args_without_options(self, res_sets, options):
        prepare_set_args(['A', 'b=c'])
        res_sets.assert_called_once_with(['A', 'b=c'])
        options.assert_not_called()

    def test_right_distribute_args_with_empty_options(self, res_sets, options):
        prepare_set_args(['A', 'b=c', 'setoptions'])
        res_sets.assert_called_once_with(['A', 'b=c'])
        options.assert_not_called()

    def test_raises_when_no_set_specified(self, res_sets, options):
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args([]))
        res_sets.assert_not_called()

    def test_raises_when_no_resource_in_set(self, res_sets, options):
        res_sets.return_value = [{"ids": [], "options": {"b": "c"}}]
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args(["b=c"]))
        res_sets.assert_called_once_with(["b=c"])

    def test_raises_when_setoption_more_than_once(self, res_sets, options):
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args(
            ['A', 'b=c', 'setoptions', "c=d", "setoptions", "e=f"]
        ))
