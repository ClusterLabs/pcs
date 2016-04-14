from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint.parse_args import prepare_set_args, prepare_resource_sets


try:
    import unittest.mock as mock
except ImportError:
    import mock


@mock.patch("pcs.cli.common.parse_args.prepare_options")
class PrepareResourceSetsTest(TestCase):
    def test_prepare_resource_sets(self, options):
        opts = [{"id": "1"}, {"id": "2", "sequential": "true"}]
        options.side_effect = opts
        self.assertEqual(
            [
                {"ids": ["resA", "resB"], "attrib":opts[0]},
                {"ids": ["resC"], "attrib": opts[1]},
            ],
            prepare_resource_sets([
                "resA", "resB", "id=resource-set-1",
                "set",
                "resC", "id=resource-set-2", "sequential=true",
            ])
        )

    def test_has_no_responsibility_to_assess_the_content(self, options):
        options.return_value = {}
        self.assertEqual([{"ids":[], "attrib":{}}], prepare_resource_sets([]))

@mock.patch("pcs.cli.common.parse_args.prepare_options")
@mock.patch("pcs.cli.constraint.parse_args.prepare_resource_sets")
class PrepareSetArgvTest(TestCase):
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
        res_sets.return_value = [{"ids": [], "attrib": {"b": "c"}}]
        self.assertRaises(CmdLineInputError, lambda: prepare_set_args(["b=c"]))
        res_sets.assert_called_once_with(["b=c"])
