from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.common.parse_args import(
    split_list,
    prepare_options,
    group_by_keywords,
)
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

class SplitByKeywords(TestCase):
    def test_split_with_implicit_first_keyword(self):
        self.assertEqual(
            group_by_keywords(
                [0, "first", 1, 2, "second", 3],
                set(["first", "second"]),
                implicit_first_keyword="zero"
            ),
            {
                "zero": [0],
                "first": [1, 2],
                "second": [3],
            }
        )

    def test_splict_without_implict_keyword(self):
        self.assertEqual(
            group_by_keywords(
                ["first", 1, 2, "second", 3],
                set(["first", "second"]),
            ),
            {
                "first": [1, 2],
                "second": [3],
            }
        )

    def test_raises_when_args_do_not_start_with_keyword_nor_implicit(self):
        self.assertRaises(CmdLineInputError, lambda: group_by_keywords(
            [0, "first", 1, 2, "second", 3],
            set(["first", "second"]),
        ))

    def test_returns_dict_with_empty_lists_for_no_args(self):
        self.assertEqual(
            group_by_keywords(
                [],
                set(["first", "second"])
            ),
            {
                "first": [],
                "second": [],
            }
        )

    def test_returns_dict_with_empty_lists_for_no_args_implicit_case(self):
        self.assertEqual(
            group_by_keywords(
                [],
                set(["first", "second"]),
                implicit_first_keyword="zero",
            ),
            {
                "zero": [],
                "first": [],
                "second": [],
            }
        )

    def test_allow_keywords_repeating(self):
        self.assertEqual(
            group_by_keywords(
                ["first", 1, 2, "second", 3, "first", 4],
                set(["first", "second"]),
            ),
            {
                "first": [1, 2, 4],
                "second": [3],
            }
        )

    def test_can_disallow_keywords_repeating(self):
        self.assertRaises(CmdLineInputError, lambda: group_by_keywords(
            ["first", 1, 2, "second", 3, "first"],
            set(["first", "second"]),
            keyword_repeat_allowed=False,
        ))
