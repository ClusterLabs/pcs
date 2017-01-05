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
from pcs.test.tools.misc import create_patcher
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import TestCase, mock


patch_operations = create_patcher("pcs.lib.cib.resource.operations")

@patch_operations("get_remaining_defaults")
@patch_operations("complete")
@patch_operations("validate_different_intervals")
@patch_operations("validate")
@patch_operations("normalize")
class Prepare(TestCase):
    def setUp(self):
        self.report_processor = mock.Mock()
        self.run = partial(
            operations.prepare,
            self.report_processor,
            [{"name": "start"}],
            [{"name": "stop"}],
            ["start", "stop"]
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
            [{"name": "start", "normalized": True}],
            ["start", "stop"], #allowed_operation_name_list
            False #allow_invalid
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
        validate.assert_called_once_with(
            [{"name": "start", "normalized": True}],
            ["start", "stop"], #allowed_operation_name_list
            True #allow_invalid
        )




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
    def assert_operation_produces_report(
        self, operation, report_list, check_warning=True
    ):
        if check_warning:
            #report_list will be empty after assert execution
            warning_report_list = [
                (severities.WARNING, report[1], report[2], None)
                for report in report_list
            ]

        assert_report_item_list_equal(
            operations.get_validation_report(operation),
            report_list
        )

        if check_warning:
            assert_report_item_list_equal(
                operations.get_validation_report(operation, allow_invalid=True),
                warning_report_list,
            )


    def test_return_empty_report_on_valid_operation(self):
        self.assert_operation_produces_report(
            {
                "name": "monitoring",
                "role": "Master"
            },
            []
        )

    def test_return_error_when_invalid_role_value(self):
        self.assert_operation_produces_report(
            {
                "name": "monitoring",
                "role": "invalid",
            },
            [
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

    def test_return_error_when_unknown_operation_attribute(self):
        self.assert_operation_produces_report(
            {
                "name": "monitoring",
                "unknown": "invalid",
            },
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["unknown"],
                        "option_type": "resource operation option",
                        "allowed": sorted(operations.ATTRIBUTES),
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ],
        )

    def test_return_errror_when_missing_key_name(self):
        self.assert_operation_produces_report(
            {
                "role": "Master"
            },
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {
                        "option_names": ["name"],
                        "option_type": "resource operation option",
                    },
                ),
            ],
            check_warning=False
        )

class Validate(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()
        self.allowed_operation_name_list = ["monitor", "start"]
        self.validate = partial(
            operations.validate,
            allowed_operation_name_list=self.allowed_operation_name_list
        )

    def assert_operations_produce_report(
        self, operation_list, report_list, allow_invalid=False
    ):
        assert_report_item_list_equal(
            self.validate(operation_list, allow_invalid=allow_invalid),
            report_list,
        )

    def test_return_nothing_on_valid_operations(self):
        self.assert_operations_produce_report(
            [{"name": "monitor", "role": "Master"}],
            []
        )

    @patch_operations("get_validation_report")
    def test_collect_operation_validation_errors(self, get_validation_report):
        get_validation_report.side_effect = lambda operation, allow_invalid: {
            "monitor": ["a", "b"],
            "start": ["c", "d"],
        }[operation["name"]]

        self.assertEqual(
            ["a", "b", "c", "d"],
            self.validate([
                {"name": "monitor"},
                {"name": "start"},
            ])
        )

    @patch_operations("get_validation_report", mock.Mock(return_value=[]))
    def test_returns_error_on_invalid_operation_names(self):
        self.assert_operations_produce_report(
            [
                {"name": "monitorrr"},
                {"name": "monitor"},
                {"name": "starttt"},
            ],
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["monitorrr", "starttt"],
                        "option_type": "resource operation name",
                        "allowed": sorted(self.allowed_operation_name_list),
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    @patch_operations("get_validation_report", mock.Mock(return_value=[]))
    def test_returns_warning_on_invalid_operation_names(self):
        self.assert_operations_produce_report(
            [
                {"name": "monitorrr"},
                {"name": "monitor"},
                {"name": "starttt"},
            ],
            [
                (
                    severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_names": ["monitorrr", "starttt"],
                        "option_type": "resource operation name",
                        "allowed": sorted(self.allowed_operation_name_list),
                    },
                ),
            ],
            allow_invalid=True
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
