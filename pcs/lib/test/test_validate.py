from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree
import re

from pcs.common import report_codes
from pcs.lib import validate
from pcs.lib.cib.tools import IdProvider
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


class DependsOn(TestCase):
    def test_success_when_dependency_present(self):
        assert_report_item_list_equal(
            validate.depends_on_option("name", "prerequisite", "type")({
                "name": "value",
                "prerequisite": "value",
            }),
            []
        )

    def test_report_when_dependency_missing(self):
        assert_report_item_list_equal(
            validate.depends_on_option(
                "name", "prerequisite", "type1", "type2"
            )({
                "name": "value",
            }),
            [
                (
                    severities.ERROR,
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    {
                        "option_name": "name",
                        "option_type": "type1",
                        "prerequisite_name": "prerequisite",
                        "prerequisite_type": "type2",
                    },
                    None
                ),
            ]
        )


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


class IsRequiredSomeOf(TestCase):
    def test_returns_no_report_when_first_is_present(self):
        assert_report_item_list_equal(
            validate.is_required_some_of(["first", "second"], "type")({
                "first": "value",
            }),
            []
        )

    def test_returns_no_report_when_second_is_present(self):
        assert_report_item_list_equal(
            validate.is_required_some_of(["first", "second"], "type")({
                "second": "value",
            }),
            []
        )

    def test_returns_report_when_missing(self):
        assert_report_item_list_equal(
            validate.is_required_some_of(["first", "second"], "type")({
                "third": "value",
            }),
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    {
                        "option_names": ["first", "second"],
                        "option_type": "type",
                    },
                    None
                ),
            ]
        )


class ValueCondTest(TestCase):
    def setUp(self):
        self.predicate = lambda a: a == "b"

    def test_returns_empty_report_on_valid_option(self):
        self.assertEqual(
            [],
            validate.value_cond("a", self.predicate, "test")({"a": "b"})
        )

    def test_returns_empty_report_on_valid_normalized_option(self):
        self.assertEqual(
            [],
            validate.value_cond("a", self.predicate, "test")(
                {"a": validate.ValuePair(original="C", normalized="b")}
            ),
        )

    def test_returns_report_about_invalid_option(self):
        assert_report_item_list_equal(
            validate.value_cond("a", self.predicate, "test")({"a": "c"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": "test",
                    },
                    None
                ),
            ]
        )

    def test_support_OptionValuePair(self):
        assert_report_item_list_equal(
            validate.value_cond("a", self.predicate, "test")(
                {"a": validate.ValuePair(original="b", normalized="c")}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "b",
                        "allowed_values": "test",
                    },
                    None
                ),
            ]
        )

    def test_supports_another_report_option_name(self):
        assert_report_item_list_equal(
            validate.value_cond(
                "a", self.predicate, "test", option_name_for_report="option a"
            )(
                {"a": "c"}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "option a",
                        "option_value": "c",
                        "allowed_values": "test",
                    },
                    None
                ),
            ]
        )

    def test_supports_forceable_errors(self):
        assert_report_item_list_equal(
            validate.value_cond(
                "a", self.predicate, "test", code_to_allow_extra_values="FORCE"
            )(
                {"a": "c"}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": "test",
                    },
                    "FORCE"
                ),
            ]
        )

    def test_supports_warning(self):
        assert_report_item_list_equal(
            validate.value_cond(
                "a",
                self.predicate,
                "test",
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
                        "allowed_values": "test",
                    },
                    None
                ),
            ]
        )


class ValueEmptyOrValid(TestCase):
    def setUp(self):
        self.validator = validate.value_cond("a", lambda a: a == "b", "test")

    def test_missing(self):
        assert_report_item_list_equal(
            validate.value_empty_or_valid("a", self.validator)({"b": "c"}),
            [
            ]
        )

    def test_empty(self):
        assert_report_item_list_equal(
            validate.value_empty_or_valid("a", self.validator)({"a": ""}),
            [
            ]
        )

    def test_valid(self):
        assert_report_item_list_equal(
            validate.value_empty_or_valid("a", self.validator)({"a": "b"}),
            [
            ]
        )

    def test_not_valid(self):
        assert_report_item_list_equal(
            validate.value_empty_or_valid("a", self.validator)({"a": "c"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "a",
                        "option_value": "c",
                        "allowed_values": "test",
                    },
                    None
                ),
            ]
        )


class ValueId(TestCase):
    def test_empty_id(self):
        assert_report_item_list_equal(
            validate.value_id("id", "test id")({"id": ""}),
            [
                (
                    severities.ERROR,
                    report_codes.EMPTY_ID,
                    {
                        "id": "",
                        "id_description": "test id",
                    },
                    None
                ),
            ]
        )

    def test_invalid_first_char(self):
        assert_report_item_list_equal(
            validate.value_id("id", "test id")({"id": "0-test"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_ID,
                    {
                        "id": "0-test",
                        "id_description": "test id",
                        "invalid_character": "0",
                        "is_first_char": True,
                    },
                    None
                ),
            ]
        )

    def test_invalid_char(self):
        assert_report_item_list_equal(
            validate.value_id("id", "test id")({"id": "te#st"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_ID,
                    {
                        "id": "te#st",
                        "id_description": "test id",
                        "invalid_character": "#",
                        "is_first_char": False,
                    },
                    None
                ),
            ]
        )

    def test_used_id(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.value_id("id", "test id", id_provider)({"id": "used"}),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": "used",
                    },
                    None
                ),
            ]
        )

    def test_pair_invalid(self):
        assert_report_item_list_equal(
            validate.value_id("id", "test id")({
                "id": validate.ValuePair("@&#", "")
            }),
            [
                (
                    severities.ERROR,
                    report_codes.EMPTY_ID,
                    {
                        # TODO: This should be "@&#". However an old validator
                        # is used and it doesn't work with pairs.
                        "id": "",
                        "id_description": "test id",
                    },
                    None
                ),
            ]
        )

    def test_pair_used_id(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.value_id("id", "test id", id_provider)({
                "id": validate.ValuePair("not-used", "used")
            }),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        # TODO: This should be "not-used". However an old
                        # validator is used and it doesn't work with pairs.
                        "id": "used",
                    },
                    None
                ),
            ]
        )

    def test_success(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.value_id("id", "test id", id_provider)({"id": "correct"}),
            []
        )

    def test_pair_success(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.value_id("id", "test id", id_provider)({
                "id": validate.ValuePair("correct", "correct")
            }),
            []
        )


class ValueIn(TestCase):
    def test_returns_empty_report_on_valid_option(self):
        self.assertEqual(
            [],
            validate.value_in("a", ["b"])({"a": "b"})
        )

    def test_returns_empty_report_on_valid_normalized_option(self):
        self.assertEqual(
            [],
            validate.value_in("a", ["b"])(
                {"a": validate.ValuePair(original="C", normalized="b")}
            ),
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


class ValueNonnegativeInteger(TestCase):
    # The real code only calls value_cond => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.value_nonnegative_integer("key")({"key": "10"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.value_nonnegative_integer("key")({"key": "-10"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "-10",
                        "allowed_values": "a non-negative integer",
                    },
                    None
                ),
            ]
        )


class ValueNotEmpty(TestCase):
    def test_empty_report_on_not_empty_value(self):
        assert_report_item_list_equal(
            validate.value_not_empty("key", "description")({"key": "abc"}),
            []
        )

    def test_empty_report_on_zero_int_value(self):
        assert_report_item_list_equal(
            validate.value_not_empty("key", "description")({"key": 0}),
            []
        )

    def test_report_on_empty_string(self):
        assert_report_item_list_equal(
            validate.value_not_empty("key", "description")({"key": ""}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "",
                        "allowed_values": "description",
                    },
                    None
                ),
            ]
        )


class ValuePortNumber(TestCase):
    # The real code only calls value_cond => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.value_port_number("key")({"key": "54321"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.value_port_number("key")({"key": "65536"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "65536",
                        "allowed_values": "a port number (1-65535)",
                    },
                    None
                ),
            ]
        )


class ValuePortRange(TestCase):
    # The real code only calls value_cond => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.value_port_range("key")({"key": "100-200"}),
            []
        )

    def test_report_nonsense(self):
        assert_report_item_list_equal(
            validate.value_port_range("key")({"key": "10-20-30"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "10-20-30",
                        "allowed_values": "port-port",
                    },
                    None
                ),
            ]
        )

    def test_report_bad_start(self):
        assert_report_item_list_equal(
            validate.value_port_range("key")({"key": "0-100"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "0-100",
                        "allowed_values": "port-port",
                    },
                    None
                ),
            ]
        )

    def test_report_bad_end(self):
        assert_report_item_list_equal(
            validate.value_port_range("key")({"key": "100-65536"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "100-65536",
                        "allowed_values": "port-port",
                    },
                    None
                ),
            ]
        )


class ValuePositiveInteger(TestCase):
    # The real code only calls value_cond => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.value_positive_integer("key")({"key": "10"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.value_positive_integer("key")({"key": "0"}),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "key",
                        "option_value": "0",
                        "allowed_values": "a positive integer",
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


class IsInteger(TestCase):
    def test_no_range(self):
        self.assertTrue(validate.is_integer(1))
        self.assertTrue(validate.is_integer("1"))
        self.assertTrue(validate.is_integer(-1))
        self.assertTrue(validate.is_integer("-1"))
        self.assertTrue(validate.is_integer(+1))
        self.assertTrue(validate.is_integer("+1"))
        self.assertTrue(validate.is_integer(" 1"))
        self.assertTrue(validate.is_integer("-1 "))
        self.assertTrue(validate.is_integer("+1 "))

        self.assertFalse(validate.is_integer(""))
        self.assertFalse(validate.is_integer("1a"))
        self.assertFalse(validate.is_integer("a1"))
        self.assertFalse(validate.is_integer("aaa"))
        self.assertFalse(validate.is_integer(1.0))
        self.assertFalse(validate.is_integer("1.0"))

    def test_at_least(self):
        self.assertTrue(validate.is_integer(5, 5))
        self.assertTrue(validate.is_integer(5, 4))
        self.assertTrue(validate.is_integer("5", 5))
        self.assertTrue(validate.is_integer("5", 4))

        self.assertFalse(validate.is_integer(5, 6))
        self.assertFalse(validate.is_integer("5", 6))

    def test_at_most(self):
        self.assertTrue(validate.is_integer(5, None, 5))
        self.assertTrue(validate.is_integer(5, None, 6))
        self.assertTrue(validate.is_integer("5", None, 5))
        self.assertTrue(validate.is_integer("5", None, 6))

        self.assertFalse(validate.is_integer(5, None, 4))
        self.assertFalse(validate.is_integer("5", None, 4))

    def test_range(self):
        self.assertTrue(validate.is_integer(5, 5, 5))
        self.assertTrue(validate.is_integer(5, 4, 6))
        self.assertTrue(validate.is_integer("5", 5, 5))
        self.assertTrue(validate.is_integer("5", 4, 6))

        self.assertFalse(validate.is_integer(3, 4, 6))
        self.assertFalse(validate.is_integer(7, 4, 6))
        self.assertFalse(validate.is_integer("3", 4, 6))
        self.assertFalse(validate.is_integer("7", 4, 6))


class IsPortNumber(TestCase):
    def test_valid_port(self):
        self.assertTrue(validate.is_port_number(1))
        self.assertTrue(validate.is_port_number("1"))
        self.assertTrue(validate.is_port_number(65535))
        self.assertTrue(validate.is_port_number("65535"))
        self.assertTrue(validate.is_port_number(8192))
        self.assertTrue(validate.is_port_number(" 8192 "))

    def test_bad_port(self):
        self.assertFalse(validate.is_port_number(0))
        self.assertFalse(validate.is_port_number("0"))
        self.assertFalse(validate.is_port_number(65536))
        self.assertFalse(validate.is_port_number("65536"))
        self.assertFalse(validate.is_port_number(-128))
        self.assertFalse(validate.is_port_number("-128"))
        self.assertFalse(validate.is_port_number("abcd"))


class MatchesRegexp(TestCase):
    def test_matches_string(self):
        self.assertTrue(validate.matches_regexp("abcdcba", "^[a-d]+$"))

    def test_matches_regexp(self):
        self.assertTrue(validate.matches_regexp(
            "abCDCBa",
            re.compile("^[a-d]+$", re.IGNORECASE)
        ))

    def test_not_matches_string(self):
        self.assertFalse(validate.matches_regexp("abcDcba", "^[a-d]+$"))

    def test_not_matches_regexp(self):
        self.assertFalse(validate.matches_regexp(
            "abCeCBa",
            re.compile("^[a-d]+$", re.IGNORECASE)
        ))


class IsEmptyString(TestCase):
    def test_empty_string(self):
        self.assertTrue(validate.is_empty_string(""))

    def test_not_empty_string(self):
        self.assertFalse(validate.is_empty_string("a"))
        self.assertFalse(validate.is_empty_string("0"))
        self.assertFalse(validate.is_empty_string(0))
