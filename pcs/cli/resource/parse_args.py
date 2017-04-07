from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.cli.common.parse_args import group_by_keywords, prepare_options
from pcs.cli.common.errors import CmdLineInputError


def parse_create_simple(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
    )

    parts = {
        "meta":  prepare_options(groups.get("meta", [])),
        "options":  prepare_options(groups.get("options", [])),
        "op": [
            prepare_options(op)
            for op in build_operations(groups.get("op", []))
        ],
    }

    return parts

def parse_create(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta", "clone", "master"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
        only_found_keywords=True,
    )

    parts = {
        "meta":  prepare_options(groups.get("meta", [])),
        "options":  prepare_options(groups.get("options", [])),
        "op": [
            prepare_options(op)
            for op in build_operations(groups.get("op", []))
        ],
    }

    if "clone" in groups:
        parts["clone"] = prepare_options(groups["clone"])

    if "master" in groups:
        parts["master"] = prepare_options(groups["master"])

    return parts

def parse_bundle_create_options(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["container", "network", "port-map", "storage-map"]),
        group_repeated_keywords=["port-map", "storage-map"]
    )
    container_options = groups.get("container", [])
    container_type = None
    if container_options and "=" not in container_options[0]:
        container_type = container_options.pop(0)
    parts = {
        "container_type": container_type,
        "container": prepare_options(container_options),
        "network": prepare_options(groups.get("network", [])),
        "port_map": [
            prepare_options(port_map)
            for port_map in groups.get("port-map", [])
        ],
        "storage_map": [
            prepare_options(storage_map)
            for storage_map in groups.get("storage-map", [])
        ],
    }
    return parts

def build_operations(op_group_list):
    """
    Return a list of dicts. Each dict represents one operation.
    list of list op_group_list contains items that have parameters after "op"
        (so item can contain multiple operations) for example: [
            [monitor timeout=1 start timeout=2],
            [monitor timeout=3 interval=10],
        ]
    """
    operation_list = []
    for op_group in op_group_list:
        #empty operation is not allowed
        if not op_group:
            raise __not_enough_parts_in_operation()

        #every operation group needs to start with operation name
        if "=" in op_group[0]:
            raise __every_operation_needs_name()

        for arg in op_group:
            if "=" not in arg:
                operation_list.append(["name={0}".format(arg)])
            else:
                operation_list[-1].append(arg)

    #every operation needs at least name and one option
    #there can be more than one operation in op_group: check is after processing
    if any([len(operation) < 2 for operation in operation_list]):
        raise __not_enough_parts_in_operation()

    return operation_list

def __not_enough_parts_in_operation():
    return CmdLineInputError(
        "When using 'op' you must specify an operation name"
        " and at least one option"
    )

def __every_operation_needs_name():
    return CmdLineInputError(
        "When using 'op' you must specify an operation name after 'op'"
    )


