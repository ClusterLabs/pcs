from pcs.cli.common.errors import (
    SEE_MAN_CHANGES,
    CmdLineInputError,
)
from pcs.cli.common.parse_args import (
    group_by_keywords,
    prepare_options,
)


def parse_create_simple(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
    )

    parts = {
        "meta": prepare_options(groups.get("meta", [])),
        "options": prepare_options(groups.get("options", [])),
        "op": [
            prepare_options(op) for op in build_operations(groups.get("op", []))
        ],
    }

    return parts


def parse_clone(arg_list, promotable=False):
    parts = {
        "clone_id": None,
        "meta": {},
    }
    allowed_keywords = set(["op", "meta"])
    if (
        arg_list
        and arg_list[0] not in allowed_keywords
        and "=" not in arg_list[0]
    ):
        parts["clone_id"] = arg_list.pop(0)
    groups = group_by_keywords(
        arg_list,
        allowed_keywords,
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
        only_found_keywords=True,
    )
    if "op" in groups:
        raise CmdLineInputError(
            "op settings must be changed on base resource, not the clone",
        )

    if "meta" in groups:
        deprecation_warning(
            "option 'meta' is deprecated and will be removed in a future release."
        )

    parts["meta"] = prepare_options(
        groups.get("options", []) + groups.get("meta", []),
    )
    if promotable:
        if "promotable" in parts["meta"]:
            raise CmdLineInputError(
                "you cannot specify both promotable option and promotable "
                "keyword"
            )
        parts["meta"]["promotable"] = "true"
    return parts


def parse_create(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta", "clone", "promotable", "bundle"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
        only_found_keywords=True,
    )

    try:
        parts = {
            "meta": prepare_options(groups.get("meta", [])),
            "options": prepare_options(groups.get("options", [])),
            "op": [
                prepare_options(op)
                for op in build_operations(groups.get("op", []))
            ],
        }

        if "clone" in groups:
            if groups["clone"] and "=" not in groups["clone"][0]:
                parts["clone_id"] = groups["clone"].pop(0)
            parts["clone"] = prepare_options(groups["clone"])
        if "promotable" in groups:
            if groups["promotable"] and "=" not in groups["promotable"][0]:
                parts["clone_id"] = groups["promotable"].pop(0)
            parts["promotable"] = prepare_options(groups["promotable"])
        if "bundle" in groups:
            parts["bundle"] = groups["bundle"]
    except CmdLineInputError as e:
        # Print error messages which point users to the changes section in pcs
        # manpage.
        # To be removed in the next significant version.
        if e.message == "missing value of 'master' option":
            raise CmdLineInputError(
                message=e.message,
                hint=(
                    "Master/Slave resources have been renamed to promotable "
                    "clones, please use the 'promotable' keyword instead of "
                    "'master'. " + SEE_MAN_CHANGES.format("0.10")
                ),
            ) from e
        raise

    return parts


def _parse_bundle_groups(arg_list):
    """
    Commandline options: no options
    """
    repeatable_keyword_list = ["port-map", "storage-map"]
    keyword_list = ["meta", "container", "network"] + repeatable_keyword_list
    groups = group_by_keywords(
        arg_list,
        set(keyword_list),
        group_repeated_keywords=repeatable_keyword_list,
        only_found_keywords=True,
    )
    for keyword in keyword_list:
        if keyword not in groups:
            continue
        if keyword in repeatable_keyword_list:
            for repeated_section in groups[keyword]:
                if not repeated_section:
                    raise CmdLineInputError(
                        "No {0} options specified".format(keyword)
                    )
        else:
            if not groups[keyword]:
                raise CmdLineInputError(
                    "No {0} options specified".format(keyword)
                )
    return groups


def parse_bundle_create_options(arg_list):
    """
    Commandline options: no options
    """
    groups = _parse_bundle_groups(arg_list)
    container_options = groups.get("container", [])
    container_type = ""
    if container_options and "=" not in container_options[0]:
        container_type = container_options.pop(0)
    parts = {
        "container_type": container_type,
        "container": prepare_options(container_options),
        "network": prepare_options(groups.get("network", [])),
        "port_map": [
            prepare_options(port_map) for port_map in groups.get("port-map", [])
        ],
        "storage_map": [
            prepare_options(storage_map)
            for storage_map in groups.get("storage-map", [])
        ],
        "meta": prepare_options(groups.get("meta", [])),
    }
    return parts


def parse_bundle_reset_options(arg_list):
    """
    Commandline options: no options
    """
    groups = _parse_bundle_groups(arg_list)
    container_options = groups.get("container", [])
    parts = {
        "container": prepare_options(container_options),
        "network": prepare_options(groups.get("network", [])),
        "port_map": [
            prepare_options(port_map) for port_map in groups.get("port-map", [])
        ],
        "storage_map": [
            prepare_options(storage_map)
            for storage_map in groups.get("storage-map", [])
        ],
        "meta": prepare_options(groups.get("meta", [])),
    }
    return parts


def _split_bundle_map_update_op_and_options(
    map_arg_list, result_parts, map_name
):
    """
    Commandline options: no options
    """
    if len(map_arg_list) < 2:
        raise _bundle_map_update_not_valid(map_name)
    op, options = map_arg_list[0], map_arg_list[1:]
    if op == "add":
        result_parts["add"].append(prepare_options(options))
    elif op in {"delete", "remove"}:
        result_parts["remove"].extend(options)
    else:
        raise _bundle_map_update_not_valid(map_name)


def _bundle_map_update_not_valid(map_name):
    """
    Commandline options: no options
    """
    return CmdLineInputError(
        (
            "When using '{map}' you must specify either 'add' and options or "
            "either of 'delete' or 'remove' and id(s)"
        ).format(map=map_name)
    )


def parse_bundle_update_options(arg_list):
    """
    Commandline options: no options
    """
    groups = _parse_bundle_groups(arg_list)
    port_map = {"add": [], "remove": []}
    for map_group in groups.get("port-map", []):
        _split_bundle_map_update_op_and_options(map_group, port_map, "port-map")
    storage_map = {"add": [], "remove": []}
    for map_group in groups.get("storage-map", []):
        _split_bundle_map_update_op_and_options(
            map_group, storage_map, "storage-map"
        )
    parts = {
        "container": prepare_options(groups.get("container", [])),
        "network": prepare_options(groups.get("network", [])),
        "port_map_add": port_map["add"],
        "port_map_remove": port_map["remove"],
        "storage_map_add": storage_map["add"],
        "storage_map_remove": storage_map["remove"],
        "meta": prepare_options(groups.get("meta", [])),
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
        # empty operation is not allowed
        if not op_group:
            raise __not_enough_parts_in_operation()

        # every operation group needs to start with operation name
        if "=" in op_group[0]:
            raise __every_operation_needs_name()

        for arg in op_group:
            if "=" not in arg:
                operation_list.append(["name={0}".format(arg)])
            else:
                operation_list[-1].append(arg)

    # every operation needs at least name and one option
    # there can be more than one operation in op_group: check is after
    # processing
    if any(len(operation) < 2 for operation in operation_list):
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
