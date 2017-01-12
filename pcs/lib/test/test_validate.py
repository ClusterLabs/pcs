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
