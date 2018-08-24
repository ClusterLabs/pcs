from unittest import TestCase

from pcs.cli.common.parse_args import(
    group_by_keywords,
    parse_typed_arg,
    prepare_options,
    split_list,
    filter_out_non_option_negative_numbers,
    filter_out_options,
    is_num,
    is_negative_num,
    is_short_option_expecting_value,
    is_long_option_expecting_value,
    is_option_expecting_value,
    upgrade_args,
    InputModifiers,
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

    def test_refuse_options_with_same_key_and_differend_value(self):
        self.assertRaises(
            CmdLineInputError, lambda: prepare_options(['a=a', "a=b"])
        )

    def test_accept_options_with_same_key_and_same_value(self):
        self.assertEqual({'a': '1'}, prepare_options(["a=1", "a=1"]))

    def test_allow_repeatable(self):
        self.assertEqual(
            {'a': ['1', '2']},
            prepare_options(["a=1", "a=2"], allowed_repeatable_options=("a"))
        )

    def test_allow_repeatable_only_once(self):
        self.assertEqual(
            {'a': ['1']},
            prepare_options(["a=1"], allowed_repeatable_options=("a"))
        )

    def test_allow_repeatable_multiple(self):
        self.assertEqual(
            {'a': ['1', '3', '2', '4']},
            prepare_options(
                ["a=1", "a=3", "a=2", "a=4"], allowed_repeatable_options=("a")
            )
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
                implicit_first_group_key="zero"
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
                implicit_first_group_key="zero",
            ),
            {
                "zero": [],
                "first": [],
                "second": [],
            }
        )

    def test_returns_dict_with_empty_lists_for_no_opts_and_only_found_kws(self):
        self.assertEqual(
            group_by_keywords(
                ["first"],
                set(["first", "second"]),
                only_found_keywords=True,
            ),
            {
                "first": [],
            }
        )

    def test_returns_empty_lists_no_opts_and_only_found_kws_with_grouping(self):
        self.assertEqual(
            group_by_keywords(
                ["second", 1, "second", "second", 2, 3],
                set(["first", "second"]),
                group_repeated_keywords=["second"],
                only_found_keywords=True,
            ),
            {
                "second": [
                    [1],
                    [],
                    [2, 3],
                ],
            }
        )

    def test_empty_repeatable(self):
        self.assertEqual(
            group_by_keywords(
                ["second"],
                set(["first", "second"]),
                group_repeated_keywords=["second"],
                only_found_keywords=True,
            ),
            {
                "second": [
                    [],
                ],
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

    def test_group_repeating_keyword_occurences(self):
        self.assertEqual(
            group_by_keywords(
                ["first", 1, 2, "second", 3, "first", 4],
                set(["first", "second"]),
                group_repeated_keywords=["first"]
            ),
            {
                "first": [[1, 2], [4]],
                "second": [3],
            }
        )

    def test_raises_on_group_repeated_keywords_inconsistency(self):
        self.assertRaises(AssertionError, lambda: group_by_keywords(
            [],
            set(["first", "second"]),
            group_repeated_keywords=["first", "third"],
            implicit_first_group_key="third"
        ))

    def test_implicit_first_kw_not_applyed_in_the_middle(self):
        self.assertEqual(
            group_by_keywords(
                [1, 2, "first", 3, "zero", 4],
                set(["first"]),
                implicit_first_group_key="zero"
            ),
            {
                "zero": [1, 2],
                "first": [3, "zero", 4],
            }
        )
    def test_implicit_first_kw_applyed_in_the_middle_when_is_in_kwds(self):
        self.assertEqual(
            group_by_keywords(
                [1, 2, "first", 3, "zero", 4],
                set(["first", "zero"]),
                implicit_first_group_key="zero"
            ),
            {
                "zero": [1, 2, 4],
                "first": [3],
            }
        )


class ParseTypedArg(TestCase):
    def assert_parse(self, arg, parsed):
        self.assertEqual(
            parse_typed_arg(arg, ["t0", "t1", "t2"], "t0"),
            parsed
        )

    def test_no_type(self):
        self.assert_parse("value", ("t0", "value"))

    def test_escape(self):
        self.assert_parse("%value", ("t0", "value"))

    def test_allowed_type(self):
        self.assert_parse("t1%value", ("t1", "value"))

    def test_bad_type(self):
        self.assertRaises(
            CmdLineInputError,
            lambda: self.assert_parse("tX%value", "aaa")
        )

    def test_escape_delimiter(self):
        self.assert_parse("%%value", ("t0", "%value"))
        self.assert_parse("%val%ue", ("t0", "val%ue"))

    def test_more_delimiters(self):
        self.assert_parse("t2%va%lu%e", ("t2", "va%lu%e"))
        self.assert_parse("t2%%va%lu%e", ("t2", "%va%lu%e"))

class FilterOutNonOptionNegativeNumbers(TestCase):
    def test_does_not_remove_anything_when_no_negative_numbers(self):
        args = ["first", "second"]
        self.assertEqual(args, filter_out_non_option_negative_numbers(args))

    def test_remove_negative_number(self):
        self.assertEqual(
            ["first"],
            filter_out_non_option_negative_numbers(["first", "-1"])
        )

    def test_remove_negative_infinity(self):
        self.assertEqual(
            ["first"],
            filter_out_non_option_negative_numbers(["first", "-INFINITY"])
        )
        self.assertEqual(
            ["first"],
            filter_out_non_option_negative_numbers(["first", "-infinity"])
        )

    def test_not_remove_follower_of_short_signed_option(self):
        self.assertEqual(
            ["first", "-f", "-1"],
            filter_out_non_option_negative_numbers(["first", "-f", "-1"])
        )

    def test_remove_follower_of_short_unsigned_option(self):
        self.assertEqual(
            ["first", "-h"],
            filter_out_non_option_negative_numbers(["first", "-h", "-1"])
        )

    def test_not_remove_follower_of_long_signed_option(self):
        self.assertEqual(
            ["first", "--name", "-1"],
            filter_out_non_option_negative_numbers(["first", "--name", "-1"])
        )

    def test_remove_follower_of_long_unsigned_option(self):
        self.assertEqual(
            ["first", "--clone"],
            filter_out_non_option_negative_numbers(["first", "--clone", "-1"])
        )

    def test_does_not_remove_dash(self):
        self.assertEqual(
            ["first", "-"],
            filter_out_non_option_negative_numbers(["first", "-"])
        )

    def test_does_not_remove_dash_dash(self):
        self.assertEqual(
            ["first", "--"],
            filter_out_non_option_negative_numbers(["first", "--"])
        )

class FilterOutOptions(TestCase):
    def test_does_not_remove_anything_when_no_options(self):
        args = ["first", "second"]
        self.assertEqual(args, filter_out_options(args))

    def test_remove_unsigned_short_option(self):
        self.assertEqual(
            ["first", "second"],
            filter_out_options(["first", "-h", "second"])
        )

    def test_remove_signed_short_option_with_value(self):
        self.assertEqual(
            ["first"],
            filter_out_options(["first", "-f", "second"])
        )

    def test_not_remove_value_of_signed_short_option_when_value_bundled(self):
        self.assertEqual(
            ["first", "second"],
            filter_out_options(["first", "-fvalue", "second"])
        )

    def test_remove_unsigned_long_option(self):
        self.assertEqual(
            ["first", "second"],
            filter_out_options(["first", "--clone", "second"])
        )

    def test_remove_signed_long_option_with_value(self):
        self.assertEqual(
            ["first"],
            filter_out_options(["first", "--name", "second"])
        )

    def test_not_remove_value_of_signed_long_option_when_value_bundled(self):
        self.assertEqual(
            ["first", "second"],
            filter_out_options(["first", "--name=value", "second"])
        )

    def test_does_not_remove_dash(self):
        self.assertEqual(
            ["first", "-"],
            filter_out_options(["first", "-"])
        )

    def test_remove_dash_dash(self):
        self.assertEqual(
            ["first"],
            filter_out_options(["first", "--"])
        )

class IsNum(TestCase):
    def test_returns_true_on_number(self):
        self.assertTrue(is_num("10"))

    def test_returns_true_on_infinity(self):
        self.assertTrue(is_num("infinity"))

    def test_returns_false_on_no_number(self):
        self.assertFalse(is_num("no-num"))

class IsNegativeNum(TestCase):
    def test_returns_true_on_negative_number(self):
        self.assertTrue(is_negative_num("-10"))

    def test_returns_true_on_infinity(self):
        self.assertTrue(is_negative_num("-INFINITY"))

    def test_returns_false_on_positive_number(self):
        self.assertFalse(is_negative_num("10"))

    def test_returns_false_on_no_number(self):
        self.assertFalse(is_negative_num("no-num"))

class IsShortOptionExpectingValue(TestCase):
    def test_returns_true_on_short_option_with_value(self):
        self.assertTrue(is_short_option_expecting_value("-f"))

    def test_returns_false_on_short_option_without_value(self):
        self.assertFalse(is_short_option_expecting_value("-h"))

    def test_returns_false_on_unknown_short_option(self):
        self.assertFalse(is_short_option_expecting_value("-x"))

    def test_returns_false_on_dash(self):
        self.assertFalse(is_short_option_expecting_value("-"))

    def test_returns_false_on_option_without_dash(self):
        self.assertFalse(is_short_option_expecting_value("ff"))

    def test_returns_false_on_option_including_value(self):
        self.assertFalse(is_short_option_expecting_value("-fvalue"))

class IsLongOptionExpectingValue(TestCase):
    def test_returns_true_on_long_option_with_value(self):
        self.assertTrue(is_long_option_expecting_value("--name"))

    def test_returns_false_on_long_option_without_value(self):
        self.assertFalse(is_long_option_expecting_value("--clone"))

    def test_returns_false_on_unknown_long_option(self):
        self.assertFalse(is_long_option_expecting_value("--not-specified-long-opt"))

    def test_returns_false_on_dash_dash(self):
        self.assertFalse(is_long_option_expecting_value("--"))

    def test_returns_false_on_option_without_dash_dash(self):
        self.assertFalse(is_long_option_expecting_value("-long-option"))

    def test_returns_false_on_option_including_value(self):
        self.assertFalse(is_long_option_expecting_value("--name=Name"))

class IsOptionExpectingValue(TestCase):
    def test_returns_true_on_short_option_with_value(self):
        self.assertTrue(is_option_expecting_value("-f"))

    def test_returns_true_on_long_option_with_value(self):
        self.assertTrue(is_option_expecting_value("--name"))

    def test_returns_false_on_short_option_without_value(self):
        self.assertFalse(is_option_expecting_value("-h"))

    def test_returns_false_on_long_option_without_value(self):
        self.assertFalse(is_option_expecting_value("--clone"))

    def test_returns_false_on_unknown_short_option(self):
        self.assertFalse(is_option_expecting_value("-x"))

    def test_returns_false_on_unknown_long_option(self):
        self.assertFalse(is_option_expecting_value("--not-specified-long-opt"))

    def test_returns_false_on_dash(self):
        self.assertFalse(is_option_expecting_value("-"))

    def test_returns_false_on_dash_dash(self):
        self.assertFalse(is_option_expecting_value("--"))

    def test_returns_false_on_option_including_value(self):
        self.assertFalse(is_option_expecting_value("--name=Name"))
        self.assertFalse(is_option_expecting_value("-fvalue"))

class UpgradeArgs(TestCase):
    def test_returns_the_same_args_when_no_older_versions_detected(self):
        args = ["first", "second"]
        self.assertEqual(args, upgrade_args(args))

    def test_upgrade_2dash_cloneopt(self):
        self.assertEqual(
            ["first", "clone", "second"],
            upgrade_args(["first", "--cloneopt", "second"])
        )

    def test_upgrade_2dash_clone(self):
        self.assertEqual(
            ["first", "clone", "second"],
            upgrade_args(["first", "--clone", "second"])
        )

    def test_upgrade_2dash_cloneopt_with_value(self):
        self.assertEqual(
            ["first", "clone", "1", "second"],
            upgrade_args(["first", "--cloneopt=1", "second"])
        )


class InputModifiersTest(TestCase):
    def setUp(self):
        self.supported = ["a", "b", "c"]
        self.bool_opts = [
            "--all",
            "--autocorrect",
            "--autodelete",
            "--config",
            "--corosync",
            "--debug",
            "--defaults",
            "--disabled",
            "--enable",
            "--force",
            "--full",
            "--groups",
            "--hide-inactive",
            "--interactive",
            "--local",
            "--master",
            "--monitor",
            "--no-default-ops",
            "--no-watchdog-validation",
            "--nodesc",
            "--off",
            "--pacemaker",
            "--skip-offline",
            "--start",
        ]
        self.val_opts = [
            "--after",
            "--before",
            "--booth-conf",
            "--booth-key",
            "--corosync_conf",
            "--from",
            "--group",
            "--name",
            "--node",
            "--request-timeout",
            "--to",
            # "--wait", # --wait is a special case, it has its own tests
            "-f",
            "-p",
            "-u",
        ]

    def _get_specified(self, *keys):
        return {key: i for i, key in enumerate(keys)}

    def ensure(self, *specified):
        InputModifiers(self._get_specified(*specified)).ensure_only_supported(
            *self.supported
        )

    def test_supported_one(self):
        self.ensure("a")

    def test_supported_multiple(self):
        self.ensure("a", "b")

    def test_not_supported_one(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.ensure("a", "e")
        self.assertEqual(
            "Specified options 'e' are not supported in this command",
            cm.exception.message
        )

    def test_not_supported_multiple(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.ensure("a", "g", "d", "c", "b", "e")
        self.assertEqual(
            "Specified options 'd', 'e', 'g' are not supported in this command",
            cm.exception.message
        )

    def test_get_existing(self):
        self.assertEqual(1, InputModifiers({"a": 1}).get("a"))

    def test_get_existing_with_default(self):
        self.assertEqual(1, InputModifiers({"a": 1}).get("a", default=2))

    def test_multiple_get_existing(self):
        self.assertEqual(
            2, InputModifiers(dict(c=3, a=1, b=2)).get("b")
        )

    def test_multiple_get_existing_with_default(self):
        self.assertEqual(
            2, InputModifiers(dict(c=3, a=1, b=2)).get("b", default=1)
        )

    def test_default(self):
        self.assertEqual(2, InputModifiers({"a": 1}).get("b", default=2))

    def test_debug_implicit(self):
        InputModifiers({"--debug": ""}).ensure_only_supported()

    def test_bool_options(self):
        for opt in self.bool_opts:
            with self.subTest(opt=opt):
                self.assertTrue(InputModifiers({opt: ""}).get(opt), opt)

    def test_bool_options_defaults(self):
        for opt in self.bool_opts:
            with self.subTest(opt=opt):
                self.assertFalse(InputModifiers({}).get(opt), opt)

    def test_val_options(self):
        val = "something"
        for opt in self.val_opts:
            with self.subTest(opt=opt):
                self.assertEqual(val, InputModifiers({opt: val}).get(opt), opt)

    def test_val_options_defaults(self):
        for opt in self.val_opts:
            with self.subTest(opt=opt):
                self.assertIsNone(InputModifiers({}).get(opt), opt)

    def test_wait(self):
        opt = "--wait"
        val = "something"
        self.assertEqual(val, InputModifiers({opt: val}).get(opt))

    def test_wait_default(self):
        self.assertFalse(InputModifiers({}).get("--wait"))

    def test_explicit_default(self):
        val = "something"
        self.assertEqual(val, InputModifiers({}).get("--force", default=val))

    def test_explicit_default_not_used(self):
        opt = "--force"
        self.assertTrue(InputModifiers({opt: ""}).get(opt, default=False))

    def test_get_non_existing(self):
        opt = "not_existing_option"
        with self.assertRaises(AssertionError) as cm:
            InputModifiers({}).get(opt)
        self.assertEqual(
            f"Non existing default value for '{opt}'", str(cm.exception)
        )

    def test_is_specified(self):
        self.assertTrue(InputModifiers({"a": "1"}).is_specified("a"))

    def test_not_specified(self):
        self.assertFalse(InputModifiers({"a": "1"}).is_specified("b"))

    def test_not_specified_default(self):
        self.assertFalse(InputModifiers({"a": "1"}).is_specified("--debug"))
