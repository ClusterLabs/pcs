from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import defaultdict
from functools import partial

from lxml import etree

from pcs.common import report_codes
from pcs.lib import reports, validate
from pcs.lib.resource_agent import get_default_interval, complete_all_intervals
from pcs.lib.cib.nvpair import append_new_instance_attributes
from pcs.lib.cib.tools import create_subelement_id
from pcs.lib.pacemaker.values import timeout_to_seconds

OPERATION_NVPAIR_ATTRIBUTES = [
    "OCF_CHECK_LEVEL",
]

ATTRIBUTES = [
    "id",
    "description",
    "enabled",
    "interval",
    "interval-origin",
    "name",
    "on-fail",
    "record-pending",
    "requires",
    "role",
    "start-delay",
    "timeout",
    "OCF_CHECK_LEVEL",
]

ROLE_VALUES = [
    "Stopped",
    "Started",
    "Slave",
    "Master",
]

REQUIRES_VALUES = [
    "nothing",
    "quorum",
    "fencing",
    "unfencing",
]

ON_FAIL_VALUES = [
    "ignore",
    "block",
    "stop",
    "restart",
    "standby",
    "fence",
    "restart-container",
]

BOOLEAN_VALUES = [
    "0",
    "1",
    "true",
    "false",
]

#normalize(key, value) -> normalized_value
normalize = validate.option_value_normalization({
    "role": lambda value: value.lower().capitalize(),
    "requires": lambda value: value.lower(),
    "on-fail": lambda value: value.lower(),
    "record-pending": lambda value: value.lower(),
    "enabled": lambda value: value.lower(),
})

OPERATION_OPTIONS_VALIDATORS = [
    validate.is_required("name", "resource operation option"),
    validate.value_in("role", ROLE_VALUES),
    validate.value_in("requires", REQUIRES_VALUES),
    validate.value_in("on-fail", ON_FAIL_VALUES),
    validate.value_in("record-pending", BOOLEAN_VALUES),
    validate.value_in("enabled", BOOLEAN_VALUES),
    validate.mutually_exclusive(
        ["interval-origin", "start-delay"],
        "resource operation option"
    )
]

def prepare(
    report_processor, raw_operation_list, default_operation_list,
    allowed_operation_name_list, allow_invalid=False
):
    """
    Return operation_list prepared from raw_operation_list and
    default_operation_list.

    report_processor is tool for warning/info/error reporting
    list of dicts raw_operation_list are entered operations that require
        follow-up care
    list of dicts default_operation_list are operations defined as default by
        (most probably) resource agent
    bool allow_invalid is flag for validation skipping
    """
    operations_to_validate = [
        validate.values_to_pairs(op, normalize) for op in raw_operation_list
    ]

    report_list = validate.names_in(
        allowed_operation_name_list,
        [o["name"].normalized for o in operations_to_validate if "name" in o],
        option_type="resource operation name",
        code_to_allow_extra_names=report_codes.FORCE_OPTIONS,
        allow_extra_names=allow_invalid,
    )

    for operation in operations_to_validate:
        report_list.extend(validate_operation(operation))

    operation_list = [
        validate.pairs_to_values(op) for op in operations_to_validate
    ]

    report_list.extend(validate_different_intervals(operation_list))

    #can raise LibraryError
    report_processor.process_list(report_list)

    return complete_all_intervals(operation_list) + get_remaining_defaults(
        report_processor,
        operation_list,
        default_operation_list
    )

def validate_operation(operation):
    """
    Return a list with reports (ReportItems) about problems inside
        operation.
    dict operation contains attributes of operation
    """
    report_list = validate.names_in(
        ATTRIBUTES,
        operation.keys(),
        "resource operation option",
    )

    report_list.extend(validate.run_collection_of_option_validators(
        operation,
        OPERATION_OPTIONS_VALIDATORS
    ))

    return report_list

def get_remaining_defaults(
    report_processor, operation_list, default_operation_list
):
    """
    Return operations not mentioned in operation_list but contained in
        default_operation_list.
    report_processor is tool for warning/info/error reporting
    list operation_list contains dictionaries with attributes of operation
    list default_operation_list contains dictionaries with attributes of the
        operation
    """
    return make_unique_intervals(
        report_processor,
        [
            default_operation for default_operation in default_operation_list
            if default_operation["name"] not in [
                operation["name"] for operation in operation_list
            ]
        ]
    )

def get_uniq_interval(
    report_processor, used_intervals, operation_name, initial_interval
):
    """
    Returns unique interval for operation_name based on initial_interval.
    report_processor is tool for warning/info/error reporting
    defaultdict used_intervals contains already used intervals
    string operation_name is name of contextual operation for interval
    initial_interval is starting point for finding free value
    """
    interval = timeout_to_seconds(initial_interval)
    if interval is None:
        return initial_interval

    if interval not in used_intervals[operation_name]:
        used_intervals[operation_name].add(interval)
        return initial_interval

    while interval in used_intervals[operation_name]:
        interval += 1
    used_intervals[operation_name].add(interval)

    report_processor.process(
        reports.resource_operation_interval_adapted(
            operation_name,
            initial_interval,
            str(interval),
        )
    )
    return str(interval)

def make_unique_intervals(report_processor, operation_list):
    """
    Return operation list similar to operation_list where intervals for the same
        operation are unique
    report_processor is tool for warning/info/error reporting
    list operation_list contains dictionaries with attributes of operation
    """
    uniq = partial(get_uniq_interval, report_processor, defaultdict(set))
    adapted_operation_list = []
    for operation in operation_list:
        adapted = operation.copy()
        if "interval" in adapted:
            adapted["interval"] = uniq(operation["name"], operation["interval"])
        adapted_operation_list.append(adapted)
    return adapted_operation_list

def validate_different_intervals(operation_list):
    """
    Check that the same operations (e.g. monitor) have different interval.
    list operation_list contains dictionaries with attributes of operation
    return see resource operation in pcs/lib/exchange_formats.md
    """
    duplication_map = defaultdict(lambda: defaultdict(list))
    for operation in operation_list:
        interval = operation.get(
            "interval",
            get_default_interval(operation["name"])
        )
        seconds = timeout_to_seconds(interval)
        duplication_map[operation["name"]][seconds].append(interval)

    duplications = defaultdict(list)
    for name, interval_map in duplication_map.items():
        for timeout in sorted(interval_map.values()):
            if len(timeout) > 1:
                duplications[name].append(timeout)

    if duplications:
        return [reports.resource_operation_interval_duplication(
            dict(duplications)
        )]
    return []

def create_id(context_element, name, interval):
    """
    Create id for op element.
    etree context_element is used for the name building
    string name is the name of the operation
    mixed interval is the interval attribute of operation
    """
    return create_subelement_id(
        context_element,
        "{0}-interval-{1}".format(name, interval)
    )

def create_operations(primitive_element, operation_list):
    """
    Create operation element containing operations from operation_list
    list operation_list contains dictionaries with attributes of operation
    etree primitive_element is context element
    """
    operations_element = etree.SubElement(primitive_element, "operations")
    for operation in sorted(operation_list, key=lambda op: op["name"]):
        append_new_operation(operations_element, operation)

def append_new_operation(operations_element, options):
    """
    Create op element and apend it to operations_element.
    etree operations_element is the context element
    dict options are attributes of operation
    """
    attribute_map = dict(
        (key, value) for key, value in options.items()
        if key not in OPERATION_NVPAIR_ATTRIBUTES
    )
    attribute_map.update({
        "id": create_id(
            operations_element.getparent(),
            options["name"],
            options["interval"]
        )
    })
    op_element = etree.SubElement(
        operations_element,
        "op",
        attribute_map,
    )
    nvpair_attribute_map = dict(
        (key, value) for key, value in options.items()
        if key in OPERATION_NVPAIR_ATTRIBUTES
    )

    if nvpair_attribute_map:
        append_new_instance_attributes(op_element, nvpair_attribute_map)

    return op_element
