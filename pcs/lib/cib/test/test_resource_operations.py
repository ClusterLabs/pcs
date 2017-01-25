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
from pcs.test.tools.assertions import assert_report_item_list_equal
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.misc import create_patcher
from pcs.test.tools.pcs_unittest import TestCase, mock
from pcs.lib.validate import ValuePair


patch_operations = create_patcher("pcs.lib.cib.resource.operations")

@patch_operations("OPERATION_OPTIONS_VALIDATORS", [])
@patch_operations("get_remaining_defaults")
@patch_operations("complete_all_intervals")
@patch_operations("validate_different_intervals")
@patch_operations("validate.value_in")
@patch_operations("validate_operation")
class Prepare(TestCase):
    def test_prepare(
        self, validate_operation, validate_value_in,
        validate_different_intervals, complete_all_intervals,
        get_remaining_defaults
    ):
        validate_operation.side_effect = lambda operation, validator_list: [
            operation["name"].normalized #values commes here in ValuePairs
        ]
        validate_value_in.return_value = "value_in"
        validate_different_intervals.return_value = ["different_interval"]


        report_processor = mock.MagicMock()
        raw_operation_list = [
            {"name": "start"},
            {"name": "monitor"},
        ]
        default_operation_list = [
            {"name": "stop"},
        ]
        allowed_operation_name_list = ["start", "stop", "monitor"]
        allow_invalid = True

        operations.prepare(
            report_processor,
            raw_operation_list,
            default_operation_list,
            allowed_operation_name_list,
            allow_invalid,
        )

        validate_value_in.assert_called_once_with(
            "name",
            allowed_operation_name_list,
            option_name_for_report="operation name",
            code_to_allow_extra_values=report_codes.FORCE_OPTIONS,
            allow_extra_values=allow_invalid,
        )

        validate_different_intervals.assert_called_once_with(raw_operation_list)
        report_processor.process_list.assert_called_once_with([
            "start",
            "monitor",
            "different_interval",
        ])
        validate_operation.assert_has_calls(
            [
                mock.call(
                    {"name": ValuePair("monitor", "monitor")},
                    ["value_in"]
                ),
                mock.call({"name": ValuePair("start", "start")}, ["value_in"]),
            ],
            any_order=True
        )

        complete_all_intervals.assert_called_once_with(raw_operation_list)

class ValidateDifferentIntervals(TestCase):
    def test_return_empty_reports_on_empty_list(self):
        operations.validate_different_intervals([])

    def test_return_empty_reports_on_operations_without_duplication(self):
        operations.validate_different_intervals([
            {"name": "monitor", "interval": "10s"},
            {"name": "monitor", "interval": "5s"},
            {"name": "start", "interval": "5s"},
        ])

    def test_return_report_on_duplicated_intervals(self):
        assert_report_item_list_equal(
            operations.validate_different_intervals([
                {"name": "monitor", "interval": "3600s"},
                {"name": "monitor", "interval": "60m"},
                {"name": "monitor", "interval": "1h"},
                {"name": "monitor", "interval": "60s"},
                {"name": "monitor", "interval": "1m"},
                {"name": "monitor", "interval": "5s"},
            ]),
            [(
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
            )]
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

        self.assertEqual(operation, dict([
            (key, operations.normalize(key, value))
            for key, value in operation.items()
        ]))

    def test_return_operation_with_normalized_values(self):
        self.assertEqual(
            {
                "name": "monitor",
                "role": "Master",
                "timeout": "10",
                "requires": "nothing",
                "on-fail": "ignore",
                "record-pending": "true",
                "enabled": "1",
            },
            dict([(key, operations.normalize(key, value)) for key, value in {
                "name": "monitor",
                "role": "master",
                "timeout": "10",
                "requires": "Nothing",
                "on-fail": "Ignore",
                "record-pending": "True",
                "enabled": "1",
            }.items()])
        )

class ValidateOperation(TestCase):
    def assert_operation_produces_report(self, operation, report_list):
        assert_report_item_list_equal(
            operations.validate_operation(
                operation,
                operations.OPERATION_OPTIONS_VALIDATORS
            ),
            report_list
        )

    def test_return_empty_report_on_valid_operation(self):
        self.assert_operation_produces_report(
            {
                "name": "monitoring",
                "role": "Master"
            },
            []
        )

    def test_validate_all_individual_options(self):
        self.assertEqual(
            ["REQUIRES REPORT", "ROLE REPORT"],
            sorted(operations.validate_operation({"name": "monitoring"}, [
                mock.Mock(return_value=["ROLE REPORT"]),
                mock.Mock(return_value=["REQUIRES REPORT"]),
            ]))
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
                    None
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
                    None
                ),
            ],
        )

    def test_return_error_when_both_interval_origin_and_start_delay(self):
        self.assert_operation_produces_report(
            {
                "name": "monitor",
                "interval-origin": "a",
                "start-delay": "b",
            },
            [
                (
                    severities.ERROR,
                    report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    {
                        "option_names": ["interval-origin", "start-delay"],
                        "option_type": "resource operation option",
                    },
                    None
                ),
            ],
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
