from dataclasses import dataclass
from typing import Optional

from pcs.cli.common.errors import (
    SEE_MAN_CHANGES,
    CmdLineInputError,
)
from pcs.cli.common.parse_args import (
    FUTURE_OPTION,
    ArgsByKeywords,
    Argv,
    InputModifiers,
    KeyValueParser,
    group_by_keywords,
)
from pcs.cli.reports.output import deprecation_warning


@dataclass(frozen=True)
class PrimitiveOptions:
    instance_attrs: dict[str, str]
    meta_attrs: dict[str, str]
    operations: list[dict[str, str]]


@dataclass(frozen=True)
class CloneOptions:
    clone_id: Optional[str]
    meta_attrs: dict[str, str]


@dataclass(frozen=True)
class GroupOptions:
    group_id: str
    after_resource: Optional[str]
    before_resource: Optional[str]


@dataclass(frozen=True)
class ComplexResourceOptions:
    primitive: PrimitiveOptions
    group: Optional[GroupOptions]
    clone: Optional[CloneOptions]
    promotable: Optional[CloneOptions]
    bundle_id: Optional[str]


@dataclass(frozen=True)
class BundleCreateOptions:
    container_type: str
    container: dict[str, str]
    network: dict[str, str]
    port_map: list[dict[str, str]]
    storage_map: list[dict[str, str]]
    meta_attrs: dict[str, str]


@dataclass(frozen=True)
class BundleUpdateOptions:
    container: dict[str, str]
    network: dict[str, str]
    port_map_add: list[dict[str, str]]
    port_map_remove: list[str]
    storage_map_add: list[dict[str, str]]
    storage_map_remove: list[str]
    meta_attrs: dict[str, str]


@dataclass(frozen=True)
class AddRemoveOptions:
    add: list[dict[str, str]]
    remove: list[str]


def parse_primitive(arg_list: Argv) -> PrimitiveOptions:
    groups = group_by_keywords(
        arg_list, set(["op", "meta"]), implicit_first_keyword="instance"
    )

    parts = PrimitiveOptions(
        instance_attrs=KeyValueParser(
            groups.get_args_flat("instance")
        ).get_unique(),
        meta_attrs=KeyValueParser(groups.get_args_flat("meta")).get_unique(),
        operations=[
            KeyValueParser(op).get_unique()
            for op in build_operations(groups.get_args_groups("op"))
        ],
    )

    return parts


def parse_clone(arg_list: Argv, promotable: bool = False) -> CloneOptions:
    clone_id = None
    allowed_keywords = set(["op", "meta"])
    if (
        arg_list
        and arg_list[0] not in allowed_keywords
        and "=" not in arg_list[0]
    ):
        clone_id = arg_list.pop(0)
    groups = group_by_keywords(
        arg_list, allowed_keywords, implicit_first_keyword="options"
    )

    if groups.has_keyword("op"):
        raise CmdLineInputError(
            "op settings must be changed on base resource, not the clone",
        )
    if groups.has_keyword("options"):
        # deprecated since 0.11.6
        deprecation_warning(
            "configuring meta attributes without specifying the 'meta' keyword "
            "is deprecated and will be removed in a future release"
        )

    meta = KeyValueParser(
        groups.get_args_flat("options") + groups.get_args_flat("meta")
    ).get_unique()
    if promotable:
        if "promotable" in meta:
            raise CmdLineInputError(
                "you cannot specify both promotable option and promotable "
                "keyword"
            )
        meta["promotable"] = "true"
    return CloneOptions(clone_id=clone_id, meta_attrs=meta)


def parse_create_new(arg_list: Argv) -> ComplexResourceOptions:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    try:
        top_groups = group_by_keywords(
            arg_list,
            set(["clone", "promotable", "bundle", "group"]),
            implicit_first_keyword="primitive",
        )
        top_groups.ensure_unique_keywords()

        primitive_groups = group_by_keywords(
            top_groups.get_args_flat("primitive"),
            set(["op", "meta"]),
            implicit_first_keyword="instance",
        )
        primitive_options = PrimitiveOptions(
            instance_attrs=KeyValueParser(
                primitive_groups.get_args_flat("instance")
            ).get_unique(),
            meta_attrs=KeyValueParser(
                primitive_groups.get_args_flat("meta")
            ).get_unique(),
            operations=[
                KeyValueParser(op).get_unique()
                for op in build_operations(
                    primitive_groups.get_args_groups("op")
                )
            ],
        )

        group_options = None
        if top_groups.has_keyword("group"):
            group_groups = group_by_keywords(
                top_groups.get_args_flat("group"),
                set(["before", "after", "op", "meta"]),
                implicit_first_keyword="group_id",
            )
            if group_groups.has_keyword("meta"):
                raise CmdLineInputError(
                    "meta options must be defined on the base resource, "
                    "not the group"
                )
            if group_groups.has_keyword("op"):
                raise CmdLineInputError(
                    "op settings must be defined on the base resource, "
                    "not the group"
                )
            if len(group_groups.get_args_flat("group_id")) != 1:
                raise CmdLineInputError(
                    "You have to specify exactly one group after 'group'"
                )
            position: dict[str, Optional[str]] = {"after": None, "before": None}
            for where in position:
                if group_groups.has_keyword(where):
                    if len(group_groups.get_args_flat(where)) != 1:
                        raise CmdLineInputError(
                            f"You have to specify exactly one resource after '{where}'"
                        )
                    position[where] = group_groups.get_args_flat(where)[0]
            group_options = GroupOptions(
                group_id=group_groups.get_args_flat("group_id")[0],
                before_resource=position["before"],
                after_resource=position["after"],
            )

        clone_options: dict[str, Optional[CloneOptions]] = {
            "clone": None,
            "promotable": None,
        }
        for clone_type in clone_options:
            if not top_groups.has_keyword(clone_type):
                continue
            clone_groups = group_by_keywords(
                top_groups.get_args_flat(clone_type),
                set(["op", "meta"]),
                implicit_first_keyword="options",
            )
            clone_id = None
            options = clone_groups.get_args_flat("options")
            if options and "=" not in options[0]:
                clone_id = options.pop(0)
            if options:
                raise CmdLineInputError(
                    f"Specifying instance attributes for a {clone_type} "
                    f"is not supported. Use 'meta' after '{clone_type}' "
                    "if you want to specify meta attributes."
                )
            if clone_groups.has_keyword("op"):
                raise CmdLineInputError(
                    "op settings must be defined on the base resource, "
                    f"not the {clone_type}"
                )
            clone_options[clone_type] = CloneOptions(
                clone_id=clone_id,
                meta_attrs=KeyValueParser(
                    clone_groups.get_args_flat("meta")
                ).get_unique(),
            )

        bundle_id = None
        if top_groups.has_keyword("bundle"):
            bundle_groups = group_by_keywords(
                top_groups.get_args_flat("bundle"),
                set(["op", "meta"]),
                implicit_first_keyword="options",
            )
            if bundle_groups.has_keyword("meta"):
                raise CmdLineInputError(
                    "meta options must be defined on the base resource, "
                    "not the bundle"
                )
            if bundle_groups.has_keyword("op"):
                raise CmdLineInputError(
                    "op settings must be defined on the base resource, "
                    "not the bundle"
                )
            if len(bundle_groups.get_args_flat("options")) != 1:
                raise CmdLineInputError(
                    "you have to specify exactly one bundle"
                )
            bundle_id = bundle_groups.get_args_flat("options")[0]

        return ComplexResourceOptions(
            primitive=primitive_options,
            group=group_options,
            clone=clone_options["clone"],
            promotable=clone_options["promotable"],
            bundle_id=bundle_id,
        )

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


# deprecated since 0.11.6
def parse_create_old(
    arg_list: Argv, modifiers: InputModifiers
) -> ComplexResourceOptions:
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    try:
        top_groups = group_by_keywords(
            arg_list,
            set(["clone", "promotable", "bundle"]),
            implicit_first_keyword="primitive",
        )

        primitive_groups = group_by_keywords(
            top_groups.get_args_flat("primitive"),
            set(["op", "meta"]),
            implicit_first_keyword="instance",
        )
        primitive_instance_attrs = primitive_groups.get_args_flat("instance")
        primitive_meta_attrs = primitive_groups.get_args_flat("meta")
        primitive_operations = primitive_groups.get_args_groups("op")

        group_options = None
        if modifiers.is_specified("--group"):
            dash_deprecation = (
                "Using '--{option}' is deprecated and will be replaced with "
                "'{option}' in a future release. "
                f"Specify {FUTURE_OPTION} to switch to the future behavior."
            )
            deprecation_warning(dash_deprecation.format(option="group"))
            before_resource = None
            if modifiers.get("--before"):
                before_resource = str(modifiers.get("--before"))
                deprecation_warning(dash_deprecation.format(option="before"))
            after_resource = None
            if modifiers.get("--after"):
                after_resource = str(modifiers.get("--after"))
                deprecation_warning(dash_deprecation.format(option="after"))
            group_options = GroupOptions(
                group_id=str(modifiers.get("--group")),
                before_resource=before_resource,
                after_resource=after_resource,
            )
        else:
            for option in ("--before", "--after"):
                if modifiers.is_specified(option):
                    raise CmdLineInputError(
                        f"you cannot use {option} without --group"
                    )

        clone_options: dict[str, Optional[CloneOptions]] = {
            "clone": None,
            "promotable": None,
        }
        for clone_type in clone_options:
            if not top_groups.has_keyword(clone_type):
                continue
            clone_groups = group_by_keywords(
                top_groups.get_args_flat(clone_type),
                set(["op", "meta"]),
                implicit_first_keyword="options",
            )
            clone_id = None
            options = clone_groups.get_args_flat("options")
            if options and "=" not in options[0]:
                clone_id = options.pop(0)
            if options:
                deprecation_warning(
                    f"Configuring {clone_type} meta attributes without specifying "
                    f"the 'meta' keyword after the '{clone_type}' keyword "
                    "is deprecated and will be removed in a future release. "
                    f"Specify {FUTURE_OPTION} to switch to the future behavior."
                )
            if clone_groups.has_keyword("op"):
                deprecation_warning(
                    f"Specifying 'op' after '{clone_type}' now defines "
                    "operations for the base resource. In future, this "
                    f"will be removed and operations will have to be specified "
                    f"before '{clone_type}'. "
                    f"Specify {FUTURE_OPTION} to switch to the future behavior."
                )
                primitive_operations += clone_groups.get_args_groups("op")
            if clone_groups.has_keyword("meta"):
                deprecation_warning(
                    f"Specifying 'meta' after '{clone_type}' now defines "
                    "meta attributes for the base resource. In future, this "
                    f"will define meta attributes for the {clone_type}. "
                    f"Specify {FUTURE_OPTION} to switch to the future behavior."
                )
                primitive_meta_attrs += clone_groups.get_args_flat("meta")
            clone_options[clone_type] = CloneOptions(
                clone_id=clone_id,
                meta_attrs=KeyValueParser(options).get_unique(),
            )

        bundle_id = None
        if top_groups.has_keyword("bundle"):
            bundle_groups = group_by_keywords(
                top_groups.get_args_flat("bundle"),
                set(["op", "meta"]),
                implicit_first_keyword="options",
            )
            if bundle_groups.has_keyword("meta"):
                deprecation_warning(
                    "Specifying 'meta' after 'bundle' now defines meta options for "
                    "the base resource. In future, this will be removed and meta "
                    "options will have to be specified before 'bundle'. "
                    f"Specify {FUTURE_OPTION} to switch to the future behavior."
                )
                primitive_meta_attrs += bundle_groups.get_args_flat("meta")
            if bundle_groups.has_keyword("op"):
                deprecation_warning(
                    "Specifying 'op' after 'bundle' now defines operations for the "
                    "base resource. In future, this will be removed and operations "
                    "will have to be specified before 'bundle'. "
                    f"Specify {FUTURE_OPTION} to switch to the future behavior."
                )
                primitive_operations += bundle_groups.get_args_groups("op")
            if len(bundle_groups.get_args_flat("options")) != 1:
                raise CmdLineInputError(
                    "you have to specify exactly one bundle"
                )
            bundle_id = bundle_groups.get_args_flat("options")[0]

        return ComplexResourceOptions(
            primitive=PrimitiveOptions(
                KeyValueParser(primitive_instance_attrs).get_unique(),
                KeyValueParser(primitive_meta_attrs).get_unique(),
                [
                    KeyValueParser(op).get_unique()
                    for op in build_operations(primitive_operations)
                ],
            ),
            group=group_options,
            clone=clone_options["clone"],
            promotable=clone_options["promotable"],
            bundle_id=bundle_id,
        )
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


def _parse_bundle_groups(arg_list: Argv) -> ArgsByKeywords:
    """
    Commandline options: no options
    """
    repeatable_keyword_list = ["port-map", "storage-map"]
    keyword_list = ["meta", "container", "network"] + repeatable_keyword_list
    groups = group_by_keywords(arg_list, set(keyword_list))
    for keyword in keyword_list:
        if not groups.has_keyword(keyword):
            continue
        if keyword in repeatable_keyword_list:
            for repeated_section in groups.get_args_groups(keyword):
                if not repeated_section:
                    raise CmdLineInputError(f"No {keyword} options specified")
        else:
            if not groups.get_args_flat(keyword):
                raise CmdLineInputError(f"No {keyword} options specified")
    return groups


def _parse_bundle_create_or_reset(
    arg_list: Argv, reset: bool
) -> BundleCreateOptions:
    """
    Commandline options: no options
    """
    groups = _parse_bundle_groups(arg_list)
    container_options = groups.get_args_flat("container")
    container_type = ""
    if not reset and container_options and "=" not in container_options[0]:
        container_type = container_options.pop(0)
    return BundleCreateOptions(
        container_type=container_type,
        container=KeyValueParser(container_options).get_unique(),
        network=KeyValueParser(groups.get_args_flat("network")).get_unique(),
        port_map=[
            KeyValueParser(port_map).get_unique()
            for port_map in groups.get_args_groups("port-map")
        ],
        storage_map=[
            KeyValueParser(storage_map).get_unique()
            for storage_map in groups.get_args_groups("storage-map")
        ],
        meta_attrs=KeyValueParser(groups.get_args_flat("meta")).get_unique(),
    )


def parse_bundle_create_options(arg_list: Argv) -> BundleCreateOptions:
    """
    Commandline options: no options
    """
    return _parse_bundle_create_or_reset(arg_list, reset=False)


def parse_bundle_reset_options(arg_list: Argv) -> BundleCreateOptions:
    """
    Commandline options: no options
    """
    return _parse_bundle_create_or_reset(arg_list, reset=True)


def _split_bundle_map_update_op_and_options(
    map_arg_list: Argv, result_parts: AddRemoveOptions, map_name: str
) -> None:
    if len(map_arg_list) < 2:
        raise _bundle_map_update_not_valid(map_name)
    op, options = map_arg_list[0], map_arg_list[1:]
    if op == "add":
        result_parts.add.append(KeyValueParser(options).get_unique())
    elif op in {"delete", "remove"}:
        result_parts.remove.extend(options)
    else:
        raise _bundle_map_update_not_valid(map_name)


def _bundle_map_update_not_valid(map_name: str) -> CmdLineInputError:
    return CmdLineInputError(
        (
            "When using '{map}' you must specify either 'add' and options or "
            "either of 'delete' or 'remove' and id(s)"
        ).format(map=map_name)
    )


def parse_bundle_update_options(arg_list: Argv) -> BundleUpdateOptions:
    """
    Commandline options: no options
    """
    groups = _parse_bundle_groups(arg_list)
    port_map = AddRemoveOptions(add=[], remove=[])
    for map_group in groups.get_args_groups("port-map"):
        _split_bundle_map_update_op_and_options(map_group, port_map, "port-map")
    storage_map = AddRemoveOptions(add=[], remove=[])
    for map_group in groups.get_args_groups("storage-map"):
        _split_bundle_map_update_op_and_options(
            map_group, storage_map, "storage-map"
        )
    return BundleUpdateOptions(
        container=KeyValueParser(
            groups.get_args_flat("container")
        ).get_unique(),
        network=KeyValueParser(groups.get_args_flat("network")).get_unique(),
        port_map_add=port_map.add,
        port_map_remove=port_map.remove,
        storage_map_add=storage_map.add,
        storage_map_remove=storage_map.remove,
        meta_attrs=KeyValueParser(groups.get_args_flat("meta")).get_unique(),
    )


def build_operations(op_group_list: list[Argv]) -> list[Argv]:
    """
    Return a list of dicts. Each dict represents one operation.

    op_group_list -- contains items that have parameters after "op"
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


def __not_enough_parts_in_operation() -> CmdLineInputError:
    return CmdLineInputError(
        "When using 'op' you must specify an operation name"
        " and at least one option"
    )


def __every_operation_needs_name() -> CmdLineInputError:
    return CmdLineInputError(
        "When using 'op' you must specify an operation name after 'op'"
    )
