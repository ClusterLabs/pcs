from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.cli.common.completion import (
    _find_suggestions,
    has_applicable_environment,
    make_suggestions,
    _split_words,
)

tree = {
    "resource": {
        "op": {
            "add": {},
            "defaults": {},
            "remove": {},
        },
        "clone": {},
    },
    "cluster": {
        "auth": {},
        "cib": {},
    }
}

class SuggestionTest(TestCase):
    def test_suggest_nothing_when_cursor_on_first_word(self):
        self.assertEqual([], _find_suggestions(tree, ['pcs'], 0))
        self.assertEqual([], _find_suggestions(tree, ['pcs', 'resource'], 0))

    def test_suggest_nothing_when_cursor_possition_out_of_range(self):
        self.assertEqual([], _find_suggestions(tree, ['pcs', 'resource'], 3))

    def test_suggest_when_last_word_not_started(self):
        self.assertEqual(
            ["clone", "op"],
            _find_suggestions(tree, ['pcs', 'resource'], 2)
        )

    def test_suggest_when_last_word_started(self):
        self.assertEqual(
            ["clone"],
            _find_suggestions(tree, ['pcs', 'resource', 'c'], 2)
        )

    def test_suggest_when_cursor_on_word_amid(self):
        self.assertEqual(
            ["clone"],
            _find_suggestions(tree, ['pcs', 'resource', 'c', 'add'], 2)
        )

    def test_suggest_nothing_when_previously_typed_word_not_match(self):
        self.assertEqual(
            [],
            _find_suggestions(tree, ['pcs', 'invalid', 'c'], 2)
        )

class HasCompletionEnvironmentTest(TestCase):
    def test_returns_false_if_environment_inapplicable(self):
        inapplicable_environments = [
            {
                'COMP_CWORD': '1',
                'PCS_AUTO_COMPLETE': '1',
            },
            {
                'COMP_WORDS': 'pcs resource',
                'PCS_AUTO_COMPLETE': '1',
            },
            {
                'COMP_WORDS': 'pcs resource',
                'COMP_CWORD': '1',
            },
            {
                'COMP_WORDS': 'pcs resource',
                'COMP_CWORD': '1',
                'PCS_AUTO_COMPLETE': '0',
            },
            {
                'COMP_WORDS': 'pcs resource',
                'COMP_CWORD': '1a',
                'PCS_AUTO_COMPLETE': '1',
            },
            {
                'COMP_WORDS': 'pcs resource',
                'COMP_CWORD': '1',
                'PCS_AUTO_COMPLETE': '1',
            },
        ]
        for environment in inapplicable_environments:
            self.assertFalse(
                has_applicable_environment(environment),
                'environment evaluated as applicable (should not be): '
                +repr(environment)
            )

    def test_returns_true_if_environment_is_set(self):
        self.assertTrue(has_applicable_environment({
            "COMP_WORDS": "pcs resource",
            "COMP_CWORD": '1',
            "COMP_LENGTHS": "3 8",
            "PCS_AUTO_COMPLETE": "1",
        }))

class MakeSuggestionsEnvironment(TestCase):
    def test_raises_for_incomlete_environment(self):
        self.assertRaises(
            EnvironmentError,
            lambda: make_suggestions(
                {
                    'COMP_CWORD': '1',
                    'PCS_AUTO_COMPLETE': '1',
                },
                suggestion_tree=tree
            )
        )

    def test_suggest_on_correct_environment(self):
        self.assertEqual(
            "clone\nop",
            make_suggestions(
                {
                    "COMP_WORDS": "pcs resource",
                    "COMP_CWORD": "2",
                    "COMP_LENGTHS": "3 8",
                    "PCS_AUTO_COMPLETE": "1",
                },
                suggestion_tree=tree
            )
        )

class SplitWordsTest(TestCase):
    def test_return_word_list_on_compatible_words_and_lenght(self):
        self.assertEqual(
            ["pcs", "resource", "op", "a"],
            _split_words("pcs resource op a", ["3", "8", "2", "1"])
        )

    def test_refuse_when_no_int_in_lengths(self):
        self.assertRaises(
            EnvironmentError,
            lambda: _split_words("pcs resource op a", ["3", "8", "2", "A"])
        )

    def test_refuse_when_lengths_are_too_big(self):
        self.assertRaises(
            EnvironmentError,
            lambda: _split_words("pcs resource op a", ["3", "8", "2", "10"])
        )

    def test_refuse_when_separator_doesnot_match(self):
        self.assertRaises(
            EnvironmentError,
            lambda: _split_words("pc sresource op a", ["3", "8", "2", "1"])
        )

    def test_refuse_when_lengths_are_too_small(self):
        self.assertRaises(
            EnvironmentError,
            lambda: _split_words("pcs resource op a ", ["3", "8", "2", "1"])
        )
