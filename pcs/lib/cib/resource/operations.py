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
from pcs.lib import reports
from pcs.lib.cib.nvpair import append_new_instance_attributes
from pcs.lib.cib.tools import create_subelement_id
from pcs.lib.errors import LibraryError
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

get_report_creator = partial(reports.get_creator, report_codes.FORCE_OPTIONS)

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
    operation_list = [normalize(operation) for operation in raw_operation_list]

    report_processor.process_list(
        validate(operation_list, allowed_operation_name_list, allow_invalid)
    )
    validate_different_intervals(operation_list)

    return complete(operation_list + get_remaining_defaults(
            report_processor,
            operation_list,
            default_operation_list
        )
    )

def normalize_attr(key, value):
    """
    Normalizes attributes of operation.
    string key is attribute name
    value is unnormalized sugested value
    """
    if key == "role":
        return value.lower().capitalize()
    return value

def normalize(operation):
    """
    Return normalized copy of operation.
    dict operation
    """
    return dict([
        (key, normalize_attr(key, value)) for key, value in operation.items()
    ])

def get_validation_report(operation, allow_invalid=False):
    """
    Return list of validation reports.
    dict operation contains attributes of operation
    """
    report_list = []
    invalid_options = list(set(operation.keys()) - set(ATTRIBUTES))
    if invalid_options:
        #Invalid attribute is always unforceable error. Forced invalid operation
        #attribute cause invalid cib (because it does not conform the schema).
        report_list.append(reports.invalid_option(
            invalid_options,
            sorted(ATTRIBUTES),
            "resource operation option",
        ))

    if "role" in operation and operation["role"] not in ROLE_VALUES:
        #Invalid role is always unforceable -it does not conform the schema
        report_list.append(reports.invalid_option_value(
            "role",
            operation["role"],
            ROLE_VALUES,
        ))

    if "name" not in operation:
        #this is always unforceable error
        report_list.append(reports.required_option_is_missing(
            ["name"],
            "resource operation option",
        ))

    return report_list

def validate(operation_list, allowed_operation_name_list, allow_invalid=False):
    """
    Validate operation_list and report about problems if needed.
    list operation_list contains dictionaries with attributes of operation
    """
    report_list = []
    for operation in operation_list:
        report_list.extend(get_validation_report(operation, allow_invalid))

    operation_name_list = [
        operation["name"]
        for operation in operation_list if "name" in operation
    ]
    invalid_names = set(operation_name_list) - set(allowed_operation_name_list)
    if invalid_names:
        report_list.append(get_report_creator(allow_invalid)(
            reports.invalid_option,
            sorted(invalid_names),
            sorted(allowed_operation_name_list),
            "resource operation name",
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
    list default_operation_list contains dictionaries with attributes of operation
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

def complete(operation_list):
    """
    Returns a copy of operation_list completeted with the missing parts.
    list operation_list contains dictionaries with attributes of operation

    Operation monitor is required always! No matter if --no-default-ops was
    entered or if agent does not specify it. See
    http://clusterlabs.org/doc/en-US/Pacemaker/1.1-pcs/html-single/Pacemaker_Explained/index.html#_resource_operations
    """
    completed_list = [operation.copy() for operation in operation_list]

    if "monitor" not in [operation["name"] for operation in completed_list]:
        completed_list.append({"name": "monitor"})

    for operation in completed_list:
        if "interval" not in operation:
            operation["interval"] = get_default_interval(operation["name"])

    return completed_list

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
        raise LibraryError(
            reports.resource_operation_interval_duplication(dict(duplications))
        )

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

def get_default_interval(operation_name):
    """
    Return default operation for given operation_name.
    string operation_name
    """
    return "60s" if operation_name == "monitor" else "0s"
