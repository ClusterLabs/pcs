from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.cli.common.parse_args import group_by_keywords, prepare_options
from pcs.cli.common.errors import CmdLineInputError

def parse_create(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta", "clone"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
        only_appeared_keywords=True,
    )

    parts = {
        "meta":  prepare_options(groups.get("meta", [])),
        "options":  prepare_options(groups.get("options", [])),
        "op": [
            prepare_options(op)
            for op in __build_operations(groups.get("op", []))
        ],
    }

    if "clone" in groups:
        parts["clone"] = prepare_options(groups["clone"])

    return parts

def __build_operations(op_group_list):
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


