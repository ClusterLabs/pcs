from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.common import report_codes
from pcs.lib.cib.resource import operations
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import TestCase, mock

@mock.patch("pcs.lib.cib.resource.operations.get_remaining_defaults")
@mock.patch("pcs.lib.cib.resource.operations.complete")
@mock.patch("pcs.lib.cib.resource.operations.validate_different_intervals")
@mock.patch("pcs.lib.cib.resource.operations.validate")
@mock.patch("pcs.lib.cib.resource.operations.normalize")
class Prepare(TestCase):
    def setUp(self):
        self.report_processor = mock.Mock()
        self.run = partial(
            operations.prepare,
            self.report_processor, [{"name": "start"}], [{"name": "stop"}]
        )

    def prepare_mocks(self, normalize, complete, get_remaining_defaults):
        def normalize_effect(operation):
            normalized_operation = operation.copy()
            normalized_operation["normalized"] = True
            return normalized_operation

        normalize.side_effect = normalize_effect
        complete.return_value = "completed operations"
        get_remaining_defaults.return_value = ["remaining defaults"]

    def check_mocks(
        self,
        prepared_operations, complete, normalize, validate_different_intervals,
        get_remaining_defaults
    ):
        self.assertEqual(prepared_operations, complete.return_value)
        normalize.assert_called_once_with({"name": "start"})
        validate_different_intervals.assert_called_once_with([
            {"name": "start", "normalized": True},
        ])
        complete.assert_called_once_with([
            {"name": "start", "normalized": True},
            "remaining defaults"
        ])
        get_remaining_defaults.assert_called_once_with(
            self.report_processor,
            [{"name": "start", "normalized": True}],
            [{"name": "stop"}],
        )

    def test_prepare_with_validation(
        self, normalize, validate, validate_different_intervals, complete,
        get_remaining_defaults
    ):
        self.prepare_mocks(normalize, complete, get_remaining_defaults)

        prepared_operations = self.run()

        self.check_mocks(
            prepared_operations, complete, normalize,
            validate_different_intervals, get_remaining_defaults
        )
        validate.assert_called_once_with(
            self.report_processor, [{"name": "start", "normalized": True}]
        )

    def test_prepare_without_validation(
        self, normalize, validate, validate_different_intervals, complete,
        get_remaining_defaults
    ):
        self.prepare_mocks(normalize, complete, get_remaining_defaults)

        prepared_operations = self.run(allow_invalid=True)

        self.check_mocks(
            prepared_operations, complete, normalize,
            validate_different_intervals, get_remaining_defaults
        )
        validate.assert_not_called()




class ValidateDifferentIntervals(TestCase):
    def test_no_raises_on_empty_operation_list(self):
        operations.validate_different_intervals([])

    def test_no_raises_on_operations_without_duplication(self):
        operations.validate_different_intervals([
            {"name": "monitor", "interval": "10s"},
            {"name": "monitor", "interval": "5s"},
            {"name": "start", "interval": "5s"},
        ])

    def test_raises_on_duplicated_intervals(self):
        assert_raise_library_error(
            lambda:operations.validate_different_intervals([
                {"name": "monitor", "interval": "3600s"},
                {"name": "monitor", "interval": "60m"},
                {"name": "monitor", "interval": "1h"},
                {"name": "monitor", "interval": "60s"},
                {"name": "monitor", "interval": "1m"},
                {"name": "monitor", "interval": "5s"},
            ]),
            (
                severities.ERROR,
                report_codes.RESOURCE_OPERATION_INTERVAL_DUPLICATION,
                {
                    "duplications": {
                        "monitor": [
                            ["3600s", "60m", "1h"],
                            ["60s", "1m"],
                        ],
                    },
                },
            ),
        )

class MakeUniqueIntervals(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()
        self.run = partial(
            operations.make_unique_intervals,
            self.report_processor
        )

    def test_return_copy_input_when_no_interval_duplication(self):
        operation_list = [
            {"name": "monitor", "interval": "10s"},
            {"name": "monitor", "interval": "5s"},
            {"name": "monitor", },
            {"name": "monitor", "interval": ""},
            {"name": "start", "interval": "5s"},
        ]
        self.assertEqual(operation_list, self.run(operation_list))

    def test_adopt_duplicit_values(self):
        self.assertEqual(
            self.run([
                {"name": "monitor", "interval": "60s"},
                {"name": "monitor", "interval": "1m"},
                {"name": "monitor", "interval": "5s"},
                {"name": "monitor", "interval": "6s"},
                {"name": "monitor", "interval": "5s"},
                {"name": "start", "interval": "5s"},
            ]),
            [
                {"name": "monitor", "interval": "60s"},
                {"name": "monitor", "interval": "61"},
                {"name": "monitor", "interval": "5s"},
                {"name": "monitor", "interval": "6s"},
                {"name": "monitor", "interval": "7"},
                {"name": "start", "interval": "5s"},
            ]
        )

        assert_report_item_list_equal(self.report_processor.report_item_list, [
            (
                severities.WARNING,
                report_codes.RESOURCE_OPERATION_INTERVAL_ADAPTED,
                {
                    "operation_name": "monitor",
                    "original_interval": "1m",
                    "adapted_interval": "61",
                },
            ),
            (
                severities.WARNING,
                report_codes.RESOURCE_OPERATION_INTERVAL_ADAPTED,
                {
                    "operation_name": "monitor",
                    "original_interval": "5s",
                    "adapted_interval": "7",
                },
            ),
        ])

class Normalize(TestCase):
    def test_return_operation_with_the_same_values(self):
        operation = {
            "name": "monitor",
            "role": "Master",
            "timeout": "10",
        }

        self.assertEqual(operation, operations.normalize(operation))

    def test_return_operation_with_normalized_values(self):
        self.assertEqual(
            {
                "name": "monitor",
                "role": "Master",
                "timeout": "10",
            },
            operations.normalize({
                "name": "monitor",
                "role": "master",
                "timeout": "10",
            })
        )

class NormalizeAttribute(TestCase):
    def test_return_the_same_value_commonly(self):
        description = "There is some description"
        self.assertEqual(
            description,
            operations.normalize_attr("description", description)
        )

    def test_normalize_role(self):
        self.assertEqual(
            "Master",
            operations.normalize_attr("role", "master")
        )
        #no valid normalizes as well
        self.assertEqual(
            "Faster",
            operations.normalize_attr("role", "faster")
        )

class GetValidationReport(TestCase):
    def test_return_empty_report_on_valid_operation(self):
        self.assertEqual([], operations.get_validation_report({
            "name": "monitoring",
            "role": "Master"
        }))
    def test_return_report_with_all_problems(self):
        assert_report_item_list_equal(
            operations.get_validation_report({
                "unknown": "some",
                "role": "invalid",
            }),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["unknown"],
                        "option_type": "resource operation",
                        "allowed": sorted(operations.ATTRIBUTES),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "role",
                        "option_value": "invalid",
                        "allowed_values": operations.ROLE_VALUES,
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ],
        )

class Validate(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()
        self.run = partial(operations.validate, self.report_processor)

    def test_report_nothing_on_valid_operations(self):
        self.run([{"name": "monitoring", "role": "Master"}])
        self.assertEqual([], self.report_processor.report_item_list)

    def test_report_about_all_errors_in_operations(self):
        expected_errors = [
            (
                severities.ERROR,
                report_codes.INVALID_OPTION,
                {
                    "option_names": ["unknown"],
                    "option_type": "resource operation",
                    "allowed": sorted(operations.ATTRIBUTES),
                },
                report_codes.FORCE_OPTIONS
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "role",
                    "option_value": "invalid",
                    "allowed_values": operations.ROLE_VALUES,
                },
                report_codes.FORCE_OPTIONS
            ),
        ]
        assert_raise_library_error(
            lambda: self.run([
                {
                    "unknown": "some",
                },
                {
                    "role": "invalid",
                },
            ]),
            *expected_errors
        )
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            expected_errors
        )

class GetRemainingDefaults(TestCase):
    @mock.patch("pcs.lib.cib.resource.operations.make_unique_intervals")
    def test_returns_remining_operations(self, make_unique_intervals):
        make_unique_intervals.side_effect = (
            lambda report_processor, operations: operations
        )
        self.assertEqual(
            operations.get_remaining_defaults(
                report_processor=None,
                operation_list =[{"name": "monitor"}],
                default_operation_list=[{"name": "monitor"}, {"name": "start"}]
            ),
            [{"name": "start"}]
        )

class Complete(TestCase):
    def test_returns_the_same_operation_list_when_nothing_is_missing(self):
        operation_list = [
            {"name": "start", "interval": "1s"},
            {"name": "monitor", "interval": "70s"},
        ]
        self.assertEqual(operations.complete(operation_list),  operation_list)

    def test_complete_operation(self):
        self.assertEqual(operations.complete([{"name": "start"}]), [
            {"name": "start", "interval": "0s"},
            {"name": "monitor", "interval": "60s"},
        ])
