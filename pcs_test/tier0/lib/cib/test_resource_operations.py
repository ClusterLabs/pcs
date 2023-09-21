from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import const
from pcs.common.pacemaker.resource.operations import CibResourceOperationDto
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.resource import operations
from pcs.lib.validate import ValuePair

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.misc import create_patcher

# pylint: disable=no-self-use


def _operation_fixture(name, interval="", role=None):
    return CibResourceOperationDto(
        id="",
        name=name,
        interval=interval,
        description=None,
        start_delay=None,
        interval_origin=None,
        timeout=None,
        enabled=None,
        record_pending=None,
        role=role,
        on_fail=None,
        meta_attributes=[],
        instance_attributes=[],
    )


patch_operations = create_patcher("pcs.lib.cib.resource.operations")


@patch_operations("_get_remaining_defaults")
@patch_operations("complete_operations_options")
@patch_operations("validate_different_intervals")
@patch_operations("_validate_operation_list")
@patch_operations("_normalized_to_operations")
@patch_operations("_operations_to_normalized")
class Prepare(TestCase):
    def test_prepare(
        self,
        operations_to_normalized,
        normalized_to_operations,
        validate_operation_list,
        validate_different_intervals,
        complete_operations_options,
        get_remaining_defaults,
    ):
        new_role_names_supported = False
        validate_operation_list.return_value = ["options_report"]
        validate_different_intervals.return_value = [
            "different_interval_report"
        ]
        operations_to_normalized.return_value = [
            {"name": ValuePair("Start", "start")},
            {"name": ValuePair("Monitor", "monitor")},
        ]
        normalized_to_operations.return_value = [
            {"name": "start"},
            {"name": "monitor"},
        ]

        report_processor = mock.MagicMock()
        report_processor.report_list.return_value = report_processor
        report_processor.has_errors = False

        raw_operation_list = [
            {"name": "Start"},
            {"name": "Monitor"},
        ]
        default_operation_list = [{"name": "stop", "interval": "10s"}]
        completed_default_operation_list = [
            {"name": "start", "interval": "0s"},
            {"name": "monitor", "interval": "60s"},
        ]
        allowed_operation_name_list = ["start", "stop", "monitor"]
        allow_invalid = True

        complete_operations_options.return_value = (
            completed_default_operation_list
        )

        operations.prepare(
            report_processor,
            raw_operation_list,
            default_operation_list,
            allowed_operation_name_list,
            new_role_names_supported,
            allow_invalid,
        )

        operations_to_normalized.assert_called_once_with(raw_operation_list)
        normalized_to_operations.assert_called_once_with(
            operations_to_normalized.return_value, new_role_names_supported
        )
        validate_operation_list.assert_called_once_with(
            operations_to_normalized.return_value,
            allowed_operation_name_list,
            allow_invalid,
        )
        validate_different_intervals.assert_called_once_with(
            normalized_to_operations.return_value
        )
        complete_operations_options.assert_has_calls(
            [mock.call(normalized_to_operations.return_value)]
        )
        get_remaining_defaults.assert_called_once_with(
            normalized_to_operations.return_value,
            default_operation_list,
        )
        report_processor.report_list.assert_has_calls(
            [
                mock.call(["options_report", "different_interval_report"]),
                mock.call([]),
            ]
        )


class ValidateDifferentIntervals(TestCase):
    def test_return_empty_reports_on_empty_list(self):
        operations.validate_different_intervals([])

    def test_return_empty_reports_on_operations_without_duplication(self):
        operations.validate_different_intervals(
            [
                {"name": "monitor", "interval": "10s"},
                {"name": "monitor", "interval": "5s"},
                {"name": "start", "interval": "5s"},
            ]
        )

    def test_return_report_on_duplicated_intervals(self):
        assert_report_item_list_equal(
            operations.validate_different_intervals(
                [
                    {"name": "monitor", "interval": "3600s"},
                    {"name": "monitor", "interval": "60m"},
                    {"name": "monitor", "interval": "1h"},
                    {"name": "monitor", "interval": "60s"},
                    {"name": "monitor", "interval": "1m"},
                    {"name": "monitor", "interval": "5s"},
                ]
            ),
            [
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
                )
            ],
        )


class MakeUniqueIntervals(TestCase):
    def test_return_copy_input_when_no_interval_duplication(self):
        operation_list = [
            _operation_fixture("monitor", "10s"),
            _operation_fixture("monitor", "5s"),
            _operation_fixture("monitor"),
            _operation_fixture("start", "5s"),
        ]
        (
            report_list,
            new_operation_list,
        ) = operations.uniquify_operations_intervals(operation_list)
        assert_report_item_list_equal(report_list, [])
        self.assertEqual(operation_list, new_operation_list)

    def test_adopt_duplicit_values(self):
        (
            report_list,
            new_operation_list,
        ) = operations.uniquify_operations_intervals(
            [
                _operation_fixture("monitor", "60s"),
                _operation_fixture("monitor", "1m"),
                _operation_fixture("monitor", "5s"),
                _operation_fixture("monitor", "6s"),
                _operation_fixture("monitor", "5s"),
                _operation_fixture("start", "5s"),
            ]
        )
        self.assertEqual(
            new_operation_list,
            [
                _operation_fixture("monitor", "60s"),
                _operation_fixture("monitor", "61"),
                _operation_fixture("monitor", "5s"),
                _operation_fixture("monitor", "6s"),
                _operation_fixture("monitor", "7"),
                _operation_fixture("start", "5s"),
            ],
        )

        assert_report_item_list_equal(
            report_list,
            [
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
            ],
        )

    def test_keep_duplicit_values_when_are_not_valid_interval(self):
        operation_list = [
            _operation_fixture("monitor", "some"),
            _operation_fixture("monitor", "some"),
        ]
        (
            report_list,
            new_operation_list,
        ) = operations.uniquify_operations_intervals(operation_list)
        assert_report_item_list_equal(report_list, [])
        self.assertEqual(new_operation_list, operation_list)


class Normalize(TestCase):
    # pylint: disable=protected-access
    def test_return_operation_with_the_same_values(self):
        operation = {
            "name": "monitor",
            "role": const.PCMK_ROLE_PROMOTED_LEGACY,
            "timeout": "10",
        }

        self.assertEqual(
            operation,
            {
                key: operations._normalize(key, value)
                for key, value in operation.items()
            },
        )

    def test_return_operation_with_normalized_values(self):
        self.assertEqual(
            {
                "name": "monitor",
                "role": const.PCMK_ROLE_PROMOTED_LEGACY,
                "timeout": "10",
                "on-fail": "ignore",
                "record-pending": "true",
                "enabled": "1",
            },
            {
                key: operations._normalize(key, value)
                for key, value in {
                    "name": "monitor",
                    "role": "master",
                    "timeout": "10",
                    "on-fail": "Ignore",
                    "record-pending": "True",
                    "enabled": "1",
                }.items()
            },
        )


class ValidateOperation(TestCase):
    def assert_operation_produces_report(self, operation, report_list):
        # pylint: disable=protected-access
        assert_report_item_list_equal(
            operations._validate_operation_list(
                [operation],
                ["monitor"],
            ),
            report_list,
        )

    def test_return_empty_report_on_valid_operation(self):
        self.assert_operation_produces_report(
            {"name": "monitor", "role": const.PCMK_ROLE_UNPROMOTED}, []
        )

    def test_validate_all_individual_options(self):
        self.assert_operation_produces_report(
            {
                "name": "monitro",
                "role": "a",
                "on-fail": "b",
                "record-pending": "c",
                "enabled": "d",
                "id": "0",
                "unknown": "invalid",
                "interval": "",
                "timeout": "e",
            },
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="resource operation",
                    allowed=[
                        "OCF_CHECK_LEVEL",
                        "description",
                        "enabled",
                        "id",
                        "interval",
                        "interval-origin",
                        "name",
                        "on-fail",
                        "record-pending",
                        "role",
                        "start-delay",
                        "timeout",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE,
                    option_value="monitro",
                    option_name="operation name",
                    allowed_values=["monitor"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a",
                    option_name="role",
                    allowed_values=const.PCMK_ROLES,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="b",
                    option_name="on-fail",
                    allowed_values=tuple(
                        sorted(
                            [
                                "block",
                                "demote",
                                "fence",
                                "ignore",
                                "restart",
                                "restart-container",
                                "standby",
                                "stop",
                            ]
                        )
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="c",
                    option_name="record-pending",
                    allowed_values="a pacemaker boolean value: '0', '1', 'false', 'n', 'no', 'off', 'on', 'true', 'y', 'yes'",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="d",
                    option_name="enabled",
                    allowed_values="a pacemaker boolean value: '0', '1', 'false', 'n', 'no', 'off', 'on', 'true', 'y', 'yes'",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="interval",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="e",
                    option_name="timeout",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="0",
                    id_description="operation id",
                    is_first_char=True,
                    invalid_character="0",
                ),
            ],
        )

    def test_return_error_when_unknown_operation_attribute(self):
        self.assert_operation_produces_report(
            {
                "name": "monitor",
                "unknown": "invalid",
            },
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["unknown"],
                        "option_type": "resource operation",
                        "allowed": sorted(operations.ATTRIBUTES),
                        "allowed_patterns": [],
                    },
                    None,
                ),
            ],
        )

    def test_return_error_when_missing_key_name(self):
        self.assert_operation_produces_report(
            {"role": const.PCMK_ROLE_PROMOTED},
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    {
                        "option_names": ["name"],
                        "option_type": "resource operation",
                    },
                    None,
                ),
            ],
        )

    def test_return_legacy_role_deprecation(self):
        self.assert_operation_produces_report(
            {
                "name": "monitor",
                "role": const.PCMK_ROLE_PROMOTED_LEGACY,
            },
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=const.PCMK_ROLE_PROMOTED_LEGACY,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
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
                        "option_type": "resource operation",
                    },
                    None,
                ),
            ],
        )

    def test_return_error_on_invalid_id(self):
        self.assert_operation_produces_report(
            {
                "name": "monitor",
                "id": "a#b",
            },
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_ID_BAD_CHAR,
                    {
                        "id": "a#b",
                        "id_description": "operation id",
                        "invalid_character": "#",
                        "is_first_char": False,
                    },
                    None,
                ),
            ],
        )


class GetRemainingDefaults(TestCase):
    def test_success(self):
        # pylint: disable=protected-access
        self.assertEqual(
            operations._get_remaining_defaults(
                operation_list=[{"name": "monitor"}],
                default_operation_list=[
                    _operation_fixture("monitor"),
                    _operation_fixture("start"),
                    _operation_fixture("stop"),
                ],
            ),
            [
                _operation_fixture("start"),
                _operation_fixture("stop"),
            ],
        )


class GetResourceOperations(TestCase):
    resource_el = etree.fromstring(
        """
        <primitive class="ocf" id="dummy" provider="pacemaker" type="Stateful">
            <operations>
                <op id="dummy-start" interval="0s" name="start" timeout="20"/>
                <op id="dummy-stop" interval="0s" name="stop" timeout="20"/>
                <op id="dummy-monitor-m" interval="10" name="monitor"
                    role="Master" timeout="20"/>
                <op id="dummy-monitor-s" interval="11" name="monitor"
                    role="Slave" timeout="20"/>
            </operations>
        </primitive>
    """
    )
    resource_noop_el = etree.fromstring(
        """
        <primitive class="ocf" id="dummy" provider="pacemaker" type="Stateful">
        </primitive>
    """
    )

    def assert_op_list(self, op_list, expected_ids):
        self.assertEqual([op.attrib.get("id") for op in op_list], expected_ids)

    def test_all_operations(self):
        self.assert_op_list(
            operations.get_resource_operations(self.resource_el),
            ["dummy-start", "dummy-stop", "dummy-monitor-m", "dummy-monitor-s"],
        )

    def test_filter_operations(self):
        self.assert_op_list(
            operations.get_resource_operations(self.resource_el, ["start"]),
            ["dummy-start"],
        )

    def test_filter_more_operations(self):
        self.assert_op_list(
            operations.get_resource_operations(
                self.resource_el, ["monitor", "stop"]
            ),
            ["dummy-stop", "dummy-monitor-m", "dummy-monitor-s"],
        )

    def test_filter_none(self):
        self.assert_op_list(
            operations.get_resource_operations(self.resource_el, ["promote"]),
            [],
        )

    def test_no_operations(self):
        self.assert_op_list(
            operations.get_resource_operations(self.resource_noop_el), []
        )
