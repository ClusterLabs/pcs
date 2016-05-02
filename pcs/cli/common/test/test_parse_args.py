from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.cli.common.parse_args import split_list, prepare_options
from pcs.cli.common.errors import CmdLineInputError


class PrepareOptionsTest(TestCase):
    def test_refuse_option_without_value(self):
        self.assertRaises(
            CmdLineInputError, lambda: prepare_options(['abc'])
        )

    def test_prepare_option_dict_form_args(self):
        self.assertEqual({'a': 'b', 'c': 'd'}, prepare_options(['a=b', 'c=d']))

    def test_prepare_option_dict_with_empty_value(self):
        self.assertEqual({'a': ''}, prepare_options(['a=']))

    def test_refuse_option_without_key(self):
        self.assertRaises(
            CmdLineInputError, lambda: prepare_options(['=a'])
        )

class SplitListTest(TestCase):
    def test_returns_list_with_original_when_separator_not_in_original(self):
        self.assertEqual([['a', 'b']], split_list(['a', 'b'], 'c'))

    def test_returns_splited_list(self):
        self.assertEqual(
            [['a', 'b'], ['c', 'd']],
            split_list(['a', 'b', '|', 'c', 'd'], '|')
        )

    def test_behave_like_string_split_when_the_separator_edges(self):
        self.assertEqual(
            [[], ['a', 'b'], ['c', 'd'], []],
            split_list(['|','a', 'b', '|', 'c', 'd', "|"], '|')
        )
