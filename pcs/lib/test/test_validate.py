from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib import validate
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_report_item_list_equal
from pcs.test.tools.pcs_unittest import TestCase

class ValuesToPairs(TestCase):
    def test_create_from_plain_values(self):
        self.assertEqual(
            {
                "first": validate.ValuePair("A", "a"),
                "second": validate.ValuePair("B", "b"),
            },
            validate.values_to_pairs(
                {
                    "first": "A",
                    "second": "B",
                },
                lambda key, value: value.lower()
            )
        )

    def test_keep_pair_if_is_already_there(self):
        self.assertEqual(
            {
                "first": validate.ValuePair("A", "aaa"),
                "second": validate.ValuePair("B", "b"),
            },
            validate.values_to_pairs(
                {
                    "first": validate.ValuePair("A", "aaa"),
                    "second": "B",
                },
                lambda key, value: value.lower()
            )
        )

class PairsToValues(TestCase):
    def test_keep_values_if_is_not_pair(self):
        self.assertEqual(
            {
                "first": "A",
                "second": "B",
            },
            validate.pairs_to_values(
                {
                    "first": "A",
                    "second": "B",
                }
            )
        )

    def test_extract_normalized_values(self):
        self.assertEqual(
            {
                "first": "aaa",
                "second": "B",
            },
            validate.pairs_to_values(
                {
                    "first": validate.ValuePair(
                        original="A",
                        normalized="aaa"
                    ),
                    "second": "B",
                }
            )
        )

class OptionValueNormalization(TestCase):
    def test_return_normalized_value_if_normalization_for_key_specified(self):
        normalize = validate.option_value_normalization({
            "first": lambda value: value.upper()
        })
        self.assertEqual("ONE", normalize("first", "one"))

    def test_return_value_if_normalization_for_key_unspecified(self):
        normalize = validate.option_value_normalization({})
        self.assertEqual("one", normalize("first", "one"))

class IsRequired(TestCase):
    def test_returns_no_report_when_required_is_present(self):
        assert_report_item_list_equal(
            validate.is_required("name", "some type")({"name": "monitor"}),
            []
        )

    def test_returns_report_when_required_is_missing(self):
        assert_report_item_list_equal(
            validate.is_required("name", "some type")({}),
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {
                        "option_names": ["name"],
                        "option_type": "some type",
                    },
                    None
                ),
            ]
        )

class ValueIn(TestCase):
    def test_returns_empty_report_on_valid_option(self):
        self.assertEqual(
            [],
            validate.value_in("a", ["b"])({"a": "b"})
        )

    def test_returns_report_about_invalid_option(self):
        assert_report_item_list_equal(
            validate.value_in("a", ["b"])({"a": "c"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": ["b"],
                    },
                    None
                ),
            ]
        )

    def test_support_OptionValuePair(self):
        assert_report_item_list_equal(
            validate.value_in("a", ["b"])(
                {"a": validate.ValuePair(original="C", normalized="c")}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "C",
                        "allowed_values": ["b"],
                    },
                    None
                ),
            ]
        )

    def test_supports_another_report_option_name(self):
        assert_report_item_list_equal(
            validate.value_in("a", ["b"], option_name_for_report="option a")(
                {"a": "c"}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "option a",
                        "option_value": "c",
                        "allowed_values": ["b"],
                    },
                    None
                ),
            ]
        )

    def test_supports_forceable_errors(self):
        assert_report_item_list_equal(
            validate.value_in("a", ["b"], code_to_allow_extra_values="FORCE")(
                {"a": "c"}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": ["b"],
                    },
                    "FORCE"
                ),
            ]
        )

    def test_supports_warning(self):
        assert_report_item_list_equal(
            validate.value_in(
                "a",
                ["b"],
                code_to_allow_extra_values="FORCE",
                allow_extra_values=True
            )(
                {"a": "c"}
            ),
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": ["b"],
                    },
                    None
                ),
            ]
        )

class MutuallyExclusive(TestCase):
    def test_returns_empty_report_when_valid(self):
        assert_report_item_list_equal(
            validate.mutually_exclusive(["a", "b"])({"a": "A"}),
            [],
        )

    def test_returns_mutually_exclusive_report_on_2_names_conflict(self):
        assert_report_item_list_equal(
            validate.mutually_exclusive(["a", "b", "c"])({
                "a": "A",
                "b": "B",
                "d": "D",
            }),
            [
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_type": "option",
                        "option_names": ["a", "b"],
                    },
                    None
                ),
            ],
        )

    def test_returns_mutually_exclusive_report_on_multiple_name_conflict(self):
        assert_report_item_list_equal(
            validate.mutually_exclusive(["a", "b", "c", "e"])({
                "a": "A",
                "b": "B",
                "c": "C",
                "d": "D",
            }),
            [
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_type": "option",
                        "option_names": ["a", "b", "c"],
                    },
                    None
                ),
            ],
        )

class CollectOptionValidations(TestCase):
    def test_collect_all_errors_from_specifications(self):
        specification = [
            lambda option_dict: ["A{0}".format(option_dict["x"])],
            lambda option_dict: ["B"],
        ]

        self.assertEqual(
            ["Ay", "B"],
            validate.run_collection_of_option_validators(
                {"x": "y"},
                specification
            )
        )

class NamesIn(TestCase):
    def test_return_empty_report_on_allowed_names(self):
        assert_report_item_list_equal(
            validate.names_in(
                ["a", "b", "c"],
                ["a", "b"],
            ),
            [],
        )

    def test_return_error_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate.names_in(
                ["a", "b", "c"],
                ["x", "y"],
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["x", "y"],
                        "allowed": ["a", "b", "c"],
                        "option_type": "option",
                    },
                    None
                )
            ]
        )

    def test_return_error_on_not_allowed_names_without_force_code(self):
        assert_report_item_list_equal(
            validate.names_in(
                ["a", "b", "c"],
                ["x", "y"],
                 #does now work without code_to_allow_extra_names
                allow_extra_names=True,
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["x", "y"],
                        "allowed": ["a", "b", "c"],
                        "option_type": "option",
                    },
                    None
                )
            ]
        )

    def test_return_forceable_error_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate.names_in(
                ["a", "b", "c"],
                ["x", "y"],
                option_type="some option",
                code_to_allow_extra_names="FORCE_CODE",
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["x", "y"],
                        "allowed": ["a", "b", "c"],
                        "option_type": "some option",
                    },
                    "FORCE_CODE"
                )
            ]
        )

    def test_return_warning_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate.names_in(
                ["a", "b", "c"],
                ["x", "y"],
                option_type="some option",
                code_to_allow_extra_names="FORCE_CODE",
                allow_extra_names=True,
            ),
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["x", "y"],
                        "allowed": ["a", "b", "c"],
                        "option_type": "some option",
                    },
                    None
                )
            ]
        )
