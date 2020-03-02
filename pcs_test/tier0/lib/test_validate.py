import re
from unittest import TestCase
from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.lib import validate
from pcs.lib.cib.tools import IdProvider

# pylint: disable=no-self-use

### normalization

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

### compound validators

class ValidatorAll(TestCase):
    def test_collect_all_errors_from_specifications(self):
        assert_report_item_list_equal(
            validate.ValidatorAll(
                [
                    validate.NamesIn(["x", "y"]),
                    validate.MutuallyExclusive(["x", "y"]),
                    validate.ValuePositiveInteger("x"),
                    validate.ValueIn("y", ["a", "b"]),
                ]
            ).validate({
                "x": "abcd",
                "y": "defg",
                "z": "hijk",
            }),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["z"],
                    option_type=None,
                    allowed=["x", "y"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    option_names=["x", "y"],
                    option_type=None
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="abcd",
                    option_name="x",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="defg",
                    option_name="y",
                    allowed_values=["a", "b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValidatorFirstError(TestCase):
    class Validator(validate.ValueValidator):
        def _validate_value(self, value):
            severity = None
            if value.normalized == "a":
                severity = reports.ReportItemSeverity.error()
            if value.normalized == "b":
                severity = reports.ReportItemSeverity.warning()
            if severity is None:
                return []
            return [
                reports.item.ReportItem(
                    severity,
                    reports.messages.InvalidOptionValue(
                        self._option_name,
                        value.original,
                        "test report",
                    )
                )
            ]

    def setUp(self):
        self.validator = validate.ValidatorFirstError([
            self.Validator("name1"),
            self.Validator("name2"),
        ])

    def test_no_reports(self):
        assert_report_item_list_equal(
            self.validator.validate({"name1": "c", "name2": "d"}),
            []
        )

    def test_first_errors(self):
        assert_report_item_list_equal(
            self.validator.validate({"name1": "a", "name2": "d"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name1",
                    option_value="a",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_second_errors(self):
        assert_report_item_list_equal(
            self.validator.validate({"name1": "c", "name2": "a"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name2",
                    option_value="a",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_keep_warnings(self):
        assert_report_item_list_equal(
            self.validator.validate({"name1": "b", "name2": "a"}),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name1",
                    option_value="b",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name2",
                    option_value="a",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

### keys validators

class CorosyncOption(TestCase):
    def test_valid(self):
        assert_report_item_list_equal(
            validate.CorosyncOption().validate({
                "name_-/NAME09": "value",
            }),
            []
        )

    def test_forbidden_characters(self):
        bad_names = [f"na{char}me" for char in ".: {}#č"]
        assert_report_item_list_equal(
            validate.CorosyncOption().validate({
                name: "value" for name in bad_names
            }),
            [
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=sorted(bad_names),
                    option_type=None,
                    allowed_characters="a-z A-Z 0-9 /_-"
                )
            ]
        )

    def test_option_type(self):
        bad_names = [f"na{char}me" for char in ".: {}#č"]
        assert_report_item_list_equal(
            validate.CorosyncOption(option_type="type").validate({
                name: "value" for name in bad_names
            }),
            [
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=sorted(bad_names),
                    option_type="type",
                    allowed_characters="a-z A-Z 0-9 /_-"
                )
            ]
        )

class DependsOnOption(TestCase):
    def test_success_when_dependency_present(self):
        assert_report_item_list_equal(
            validate
                .DependsOnOption(["name"], "prerequisite", option_type="type")
                .validate({
                    "name": "value",
                    "prerequisite": "value",
                })
            ,
            []
        )

    def test_report_when_dependency_missing(self):
        assert_report_item_list_equal(
            validate
                .DependsOnOption(
                    ["name"],
                    "prerequisite",
                    option_type="type1",
                    prerequisite_type="type2"
                )
                .validate({"name": "value"})
            ,
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="name",
                    option_type="type1",
                    prerequisite_name="prerequisite",
                    prerequisite_type="type2",
                ),
            ]
        )

    def test_more_options(self):
        assert_report_item_list_equal(
            validate
                .DependsOnOption(["name1", "name2", "name3"], "prerequisite")
                .validate({
                    "name1": "value",
                    "name3": "value",
                })
            ,
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name=name,
                    option_type=None,
                    prerequisite_name="prerequisite",
                    prerequisite_type=None,
                ) for name in ["name1", "name3"]
            ]
        )

class IsRequiredAll(TestCase):
    def test_returns_no_report_when_required_is_present(self):
        assert_report_item_list_equal(
            validate
                .IsRequiredAll(["name"], "some type")
                .validate({"name": "monitor"})
            ,
            []
        )

    def test_returns_report_when_required_is_missing(self):
        assert_report_item_list_equal(
            validate
                .IsRequiredAll(["name"], "some type")
                .validate({})
            ,
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["name"],
                    option_type="some type",
                ),
            ]
        )

    def test_more_options(self):
        assert_report_item_list_equal(
            validate
                .IsRequiredAll(["name1", "name2", "name3"], "some type")
                .validate({"name2": "value2"})
            ,
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["name1", "name3"],
                    option_type="some type",
                ),
            ]
        )

class IsRequiredSome(TestCase):
    def test_returns_no_report_when_first_is_present(self):
        assert_report_item_list_equal(
            validate
            .IsRequiredSome(["first", "second"], "type")
                .validate({"first": "value"})
            ,
            []
        )

    def test_returns_no_report_when_second_is_present(self):
        assert_report_item_list_equal(
            validate
                .IsRequiredSome(["first", "second"], "type")
                .validate({"second": "value"})
            ,
            []
        )

    def test_returns_report_when_missing(self):
        assert_report_item_list_equal(
            validate
                .IsRequiredSome(["first", "second"], "type")
                .validate({"third": "value"})
            ,
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
                    option_names=["first", "second"],
                    option_type="type",
                ),
            ]
        )

class MutuallyExclusive(TestCase):
    def test_returns_empty_report_when_valid(self):
        assert_report_item_list_equal(
            validate
                .MutuallyExclusive(["a", "b"])
                .validate({"a": "A"})
            ,
            [],
        )

    def test_returns_mutually_exclusive_report_on_2_names_conflict(self):
        assert_report_item_list_equal(
            validate
                .MutuallyExclusive(["a", "b", "c"])
                .validate({
                    "a": "A",
                    "b": "B",
                    "d": "D",
                })
            ,
            [
                fixture.error(
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    option_type=None,
                    option_names=["a", "b"],
                ),
            ],
        )

    def test_returns_mutually_exclusive_report_on_multiple_name_conflict(self):
        assert_report_item_list_equal(
            validate
                .MutuallyExclusive(["a", "b", "c", "e"], option_type="option")
                .validate({
                    "a": "A",
                    "b": "B",
                    "c": "C",
                    "d": "D",
                })
            ,
            [
                fixture.error(
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    option_type="option",
                    option_names=["a", "b", "c"],
                ),
            ],
        )

class NamesIn(TestCase):
    def test_return_empty_report_on_allowed_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(["a", "b", "c"])
                .validate({"a": "A", "b": "B"})
            ,
            []
        )

    def test_return_error_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(["a", "b", "c"], option_type="option")
                .validate({"x": "X", "y": "Y"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "y"],
                    allowed=["a", "b", "c"],
                    option_type="option",
                    allowed_patterns=[],
                )
            ]
        )

    def test_return_error_on_banned_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(["a", "b"], banned_name_list=["x", "y", "z"])
                .validate({"x": "X", "a": "A", "z": "Z"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "z"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                )
            ]
        )

    def test_return_error_on_not_allowed_and_banned_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(["a", "b"], banned_name_list=["x", "y", "z"])
                .validate({"x": "X", "a": "A", "z": "Z", "c": "C"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["c", "x", "z"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                )
            ]
        )

    def test_return_error_on_not_allowed_and_banned_names_forceable(self):
        code = "force_code"
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b"],
                    banned_name_list=["x", "y", "z"],
                    code_for_warning=code,
                )
                .validate({"x": "X", "a": "A", "z": "Z", "c": "C", "d": "D"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code=code,
                    option_names=["c", "d"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "z"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_return_error_on_not_allowed_and_banned_names_forced(self):
        code = "force_code"
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b"],
                    banned_name_list=["x", "y", "z"],
                    code_for_warning=code,
                    produce_warning=True,
                )
                .validate({"x": "X", "a": "A", "z": "Z", "c": "C", "d": "D"})
            ,
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["c", "d"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "z"],
                    allowed=["a", "b"],
                    option_type=None,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_return_error_with_allowed_patterns(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b", "c"],
                    allowed_option_patterns=["pattern"]
                )
                .validate({"x": "X", "y": "Y"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "y"],
                    allowed=["a", "b", "c"],
                    option_type=None,
                    allowed_patterns=["pattern"],
                )
            ]
        )

    def test_return_error_on_not_allowed_names_without_force_code(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b", "c"],
                    #does now work without code_for_warning
                    produce_warning=True,
                )
                .validate({"x": "X", "y": "Y"})
            ,
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "y"],
                    allowed=["a", "b", "c"],
                    option_type=None,
                    allowed_patterns=[],
                )
            ]
        )

    def test_return_forceable_error_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b", "c"],
                    option_type="some option",
                    code_for_warning="FORCE_CODE",
                )
                .validate({"x": "X", "y": "Y"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    force_code="FORCE_CODE",
                    option_names=["x", "y"],
                    allowed=["a", "b", "c"],
                    option_type="some option",
                    allowed_patterns=[],
                )
            ]
        )

    def test_return_warning_on_not_allowed_names(self):
        assert_report_item_list_equal(
            validate
                .NamesIn(
                    ["a", "b", "c"],
                    option_type="some option",
                    code_for_warning="FORCE_CODE",
                    produce_warning=True,
                )
                .validate({"x": "X", "y": "Y"})
            ,
            [
                fixture.warn(
                    report_codes.INVALID_OPTIONS,
                    option_names=["x", "y"],
                    allowed=["a", "b", "c"],
                    option_type="some option",
                    allowed_patterns=[],
                )
            ]
        )

### values validators

class ValueValidatorImplementation(validate.ValueValidator):
    def _validate_value(self, value):
        return [
            reports.item.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    self._option_name,
                    value.original,
                    "test report",
                )
            )
        ]

class ValueValidator(TestCase):
    def test_value_not_specified(self):
        assert_report_item_list_equal(
            ValueValidatorImplementation("name")
                .validate({"name1": "value1"})
            ,
            []
        )

    def test_value_empty_and_empty_not_allowed(self):
        assert_report_item_list_equal(
            ValueValidatorImplementation("name")
                .validate({"name": ""})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name",
                    option_value="",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_value_empty_and_empty_allowed(self):
        validator = ValueValidatorImplementation("name")
        validator.empty_string_valid = True
        assert_report_item_list_equal(
            validator.validate({"name": ""}),
            []
        )

    def test_value_not_valid(self):
        assert_report_item_list_equal(
            ValueValidatorImplementation("name")
                .validate({"name": "value"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="name",
                    option_value="value",
                    allowed_values="test report",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

class ValuePredicateImplementation(validate.ValuePredicateBase):
    def _is_valid(self, value):
        return value == "b"

    def _get_allowed_values(self):
        return "allowed values"

    def set_value_cannot_be_empty(self, value):
        self._value_cannot_be_empty = value
        return self

    def set_forbidden_characters(self, value):
        self._forbidden_characters = value
        return self

class ValuePredicateBase(TestCase):
    def test_returns_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
                .validate({"a": "b"})
            ,
            []
        )

    def test_returns_empty_report_on_valid_normalized_option(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
            .validate({"a": validate.ValuePair(original="C", normalized="b")})
            ,
            []
        )

    def test_returns_report_about_invalid_option(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_value_cannot_be_empty(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
                .set_value_cannot_be_empty(True)
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )

    def test_forbidden_characters(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
                .set_forbidden_characters("xyz")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters="xyz",
                )
            ]
        )

    def test_support_option_value_pair(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a")
            .validate({"a": validate.ValuePair(original="b", normalized="c")})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="b",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_supports_another_report_option_name(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a", option_name_for_report="option a")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="option a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_supports_forceable_errors(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation("a", code_for_warning="FORCE")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code="FORCE",
                    option_name="a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

    def test_supports_warning(self):
        assert_report_item_list_equal(
            ValuePredicateImplementation(
                "a", code_for_warning="FORCE", produce_warning=True
            ).validate({"a": "c"})
            ,
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values="allowed values",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ]
        )

class ValueCorosyncValue(TestCase):
    def test_value_ok(self):
        assert_report_item_list_equal(
            validate.ValueCorosyncValue("a").validate({"a": "valid_value"}),
            []
        )

    def test_empty_value(self):
        assert_report_item_list_equal(
            validate.ValueCorosyncValue("a").validate({"a": ""}),
            []
        )

    def test_escaped_new_lines(self):
        assert_report_item_list_equal(
            validate.ValueCorosyncValue("a").validate({"a": "\\n\\r"}),
            []
        )

    def test_forbidden_characters_reported(self):
        bad_value_list = [
            "{",
            "}",
            "\n",
            "\r",
            "bad{value",
            "bad}value",
            "bad\nvalue",
            "bad\rvalue"
            "value\r\nsection {\n\rnew_key: new_value\r\n}\n\r",
        ]
        for value in bad_value_list:
            with self.subTest(value=value):
                assert_report_item_list_equal(
                    validate.ValueCorosyncValue("a").validate({"a": value}),
                    [
                        fixture.error(
                            report_codes.INVALID_OPTION_VALUE,
                            option_value=value,
                            option_name="a",
                            allowed_values=None,
                            cannot_be_empty=False,
                            forbidden_characters=r"{}\n\r",
                        ),
                    ]
                )

class ValueId(TestCase):
    def test_empty_id(self):
        assert_report_item_list_equal(
            validate.ValueId("id").validate({"id": ""}),
            [
                fixture.error(
                    report_codes.INVALID_ID_IS_EMPTY,
                    id_description=None,
                ),
            ]
        )

    def test_invalid_first_char(self):
        assert_report_item_list_equal(
            validate.ValueId("id", option_name_for_report="test id")
                .validate({"id": "0-test"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="0-test",
                    id_description="test id",
                    invalid_character="0",
                    is_first_char=True,
                ),
            ]
        )

    def test_invalid_char(self):
        assert_report_item_list_equal(
            validate.ValueId("id").validate({"id": "te#st"}),
            [
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="te#st",
                    id_description=None,
                    invalid_character="#",
                    is_first_char=False,
                ),
            ]
        )

    def test_used_id(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.ValueId("id", id_provider=id_provider)
                .validate({"id": "used"})
            ,
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id="used",
                ),
            ]
        )

    def test_pair_invalid(self):
        assert_report_item_list_equal(
            validate.ValueId("id")
                .validate({"id": validate.ValuePair("@&#", "")})
            ,
            [
                fixture.error(
                    report_codes.INVALID_ID_IS_EMPTY,
                    # TODO: This should be INVALID_ID_BAD_CHAR with value
                    # "@&#". However an old validator is used and it doesn't
                    # work with pairs and therefore the empty string is used.
                    id_description=None,
                ),
            ]
        )

    def test_pair_used_id(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.ValueId("id", id_provider=id_provider)
                .validate({
                    "id": validate.ValuePair("not-used", "used")
                })
            ,
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    # TODO: This should be "not-used". However an old
                    # validator is used and it doesn't work with pairs.
                    id="used",
                ),
            ]
        )

    def test_success(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.ValueId("id", id_provider=id_provider)
                .validate({"id": "correct"})
            ,
            []
        )

    def test_pair_success(self):
        id_provider = IdProvider(etree.fromstring("<a><test id='used' /></a>"))
        assert_report_item_list_equal(
            validate.ValueId("id", id_provider=id_provider)
                .validate({"id": validate.ValuePair("correct", "correct")})
            ,
            []
        )

class ValueIn(TestCase):
    def test_returns_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"]).validate({"a": "b"}),
            []
        )

    def test_returns_empty_report_on_valid_normalized_option(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"])
                .validate(
                    {"a": validate.ValuePair(original="C", normalized="b")}
                )
            ,
            []
        )

    def test_returns_report_about_invalid_option(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"]).validate({"a": "c"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values=["b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_support_option_value_pair(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"])
                .validate(
                    {"a": validate.ValuePair(original="C", normalized="c")}
                )
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="C",
                    allowed_values=["b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_supports_another_report_option_name(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"], option_name_for_report="option a")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="option a",
                    option_value="c",
                    allowed_values=["b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_supports_forceable_errors(self):
        assert_report_item_list_equal(
            validate.ValueIn("a", ["b"], code_for_warning="FORCE")
                .validate({"a": "c"})
            ,
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code="FORCE",
                    option_name="a",
                    option_value="c",
                    allowed_values=["b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_supports_warning(self):
        assert_report_item_list_equal(
            validate.ValueIn(
                "a",
                ["b"],
                code_for_warning="FORCE",
                produce_warning=True
            ).validate({"a": "c"})
            ,
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="c",
                    allowed_values=["b"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValueIntegerInRange(TestCase):
    # The real code only calls ValuePredicateBase and is_integer which are both
    # heavily tested on their own => only basic tests here.
    def fixture_validator(self):
        return validate.ValueIntegerInRange("key", -5, 5)

    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            self.fixture_validator().validate({"key": "2"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            self.fixture_validator().validate({"key": "6"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="6",
                    allowed_values="-5..5",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValueIpAddress(TestCase):
    # The real code only calls ValuePredicateBase and is_ipv4_address and
    # is_ipv6_address which are both heavily tested on their own => only basic
    # tests here.
    def fixture_validator(self):
        return validate.ValueIpAddress("key")

    def test_empty_report_on_ipv4(self):
        assert_report_item_list_equal(
            self.fixture_validator().validate({"key": "192.168.123.42"}),
            []
        )

    def test_empty_report_on_ipv6(self):
        assert_report_item_list_equal(
            self.fixture_validator().validate({"key": "::192:168:123:42"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            self.fixture_validator().validate({"key": "abcd"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="abcd",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValueNonnegativeInteger(TestCase):
    # The real code only calls ValuePredicateBase => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.ValueNonnegativeInteger("key").validate({"key": "10"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.ValueNonnegativeInteger("key").validate({"key": "-10"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="-10",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValueNotEmpty(TestCase):
    # The real code only calls ValuePredicateBase => only basic tests here.
    def test_empty_report_on_not_empty_value(self):
        assert_report_item_list_equal(
            validate.ValueNotEmpty("key", "description")
                .validate({"key": "abc"})
            ,
            []
        )

    def test_empty_report_on_zero_int_value(self):
        assert_report_item_list_equal(
            validate.ValueNotEmpty("key", "description").validate({"key": 0}),
            []
        )

    def test_report_on_empty_string(self):
        assert_report_item_list_equal(
            validate.ValueNotEmpty("key", "description").validate({"key": ""}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="",
                    allowed_values="description",
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
            ]
        )

class ValuePortNumber(TestCase):
    # The real code only calls ValuePredicateBase => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.ValuePortNumber("key").validate({"key": "54321"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.ValuePortNumber("key").validate({"key": "65536"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="65536",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValuePortRange(TestCase):
    # The real code only calls ValuePredicateBase => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.ValuePortRange("key").validate({"key": "100-200"}),
            []
        )

    def test_report_nonsense(self):
        assert_report_item_list_equal(
            validate.ValuePortRange("key").validate({"key": "10-20-30"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="10-20-30",
                    allowed_values="port-port",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_report_bad_start(self):
        assert_report_item_list_equal(
            validate.ValuePortRange("key").validate({"key": "0-100"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="0-100",
                    allowed_values="port-port",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_report_bad_end(self):
        assert_report_item_list_equal(
            validate.ValuePortRange("key").validate({"key": "100-65536"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="100-65536",
                    allowed_values="port-port",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValuePositiveInteger(TestCase):
    # The real code only calls ValuePredicateBase => only basic tests here.
    def test_empty_report_on_valid_option(self):
        assert_report_item_list_equal(
            validate.ValuePositiveInteger("key").validate({"key": "10"}),
            []
        )

    def test_report_invalid_value(self):
        assert_report_item_list_equal(
            validate.ValuePositiveInteger("key").validate({"key": "0"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="key",
                    option_value="0",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

class ValueTimeInterval(TestCase):
    def test_no_reports_for_valid_time_interval(self):
        for interval in ["0", "1s", "2sec", "3m", "4min", "5h", "6hr"]:
            with self.subTest(value=interval):
                assert_report_item_list_equal(
                    validate.ValueTimeInterval("a").validate({"a": interval}),
                    []
                )

    def test_reports_about_invalid_interval(self):
        assert_report_item_list_equal(
            validate.ValueTimeInterval("a").validate({"a": "invalid_value"}),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="a",
                    option_value="invalid_value",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

### predicates

class IsInteger(TestCase):
    def test_no_range(self):
        self.assertTrue(validate.is_integer(1))
        self.assertTrue(validate.is_integer("1"))
        self.assertTrue(validate.is_integer(-1))
        self.assertTrue(validate.is_integer("-1"))
        self.assertTrue(validate.is_integer(+1))
        self.assertTrue(validate.is_integer("+1"))

        self.assertFalse(validate.is_integer(" 1"))
        self.assertFalse(validate.is_integer("\n-1"))
        self.assertFalse(validate.is_integer("\r+1"))
        self.assertFalse(validate.is_integer("1\n"))
        self.assertFalse(validate.is_integer("-1 "))
        self.assertFalse(validate.is_integer("+1\r"))

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

class IsIpv4Address(TestCase):
    def test_valid(self):
        self.assertTrue(validate.is_ipv4_address("192.168.1.1"))
        self.assertTrue(validate.is_ipv4_address("1.2.3.4"))
        self.assertTrue(validate.is_ipv4_address("255.255.255.255"))
        self.assertTrue(validate.is_ipv4_address("0.0.0.0"))

    def test_bad(self):
        self.assertFalse(validate.is_ipv4_address("abcd"))
        self.assertFalse(validate.is_ipv4_address("192 168 1 1"))
        self.assertFalse(validate.is_ipv4_address("3232235521"))
        self.assertFalse(validate.is_ipv4_address("::1"))
        self.assertFalse(validate.is_ipv4_address(1234))

class IsIpv6Address(TestCase):
    def test_valid(self):
        self.assertTrue(validate.is_ipv6_address("fe80::5054:ff:fec6:8eaf"))
        self.assertTrue(validate.is_ipv6_address("::abc:7:def"))

    def test_bad(self):
        self.assertFalse(validate.is_ipv6_address("abcd"))
        self.assertFalse(validate.is_ipv6_address("192.168.1.1"))
        self.assertFalse(validate.is_ipv6_address(1234))

class IsPortNumber(TestCase):
    def test_valid_port(self):
        self.assertTrue(validate.is_port_number(1))
        self.assertTrue(validate.is_port_number("1"))
        self.assertTrue(validate.is_port_number(65535))
        self.assertTrue(validate.is_port_number("65535"))
        self.assertTrue(validate.is_port_number(8192))

    def test_bad_port(self):
        self.assertFalse(validate.is_port_number(0))
        self.assertFalse(validate.is_port_number("0"))
        self.assertFalse(validate.is_port_number(65536))
        self.assertFalse(validate.is_port_number("65536"))
        self.assertFalse(validate.is_port_number(" 8192 "))
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
