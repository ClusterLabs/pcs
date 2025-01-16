from typing import (
    Any,
    Optional,
    cast,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    ArgsByKeywords,
    Argv,
    InputModifiers,
    group_by_keywords,
)
from pcs.common import reports
from pcs.common.resource_status import (
    EXACT_CHECK_STATES,
    InstancesQuantifierUnsupportedException,
    MembersQuantifierUnsupportedException,
    MoreChildrenQuantifierType,
    QueryException,
    ResourceException,
    ResourceNonExistentException,
    ResourceNotInGroupException,
    ResourcesStatusFacade,
    ResourceState,
    ResourceStateExactCheck,
    ResourceType,
    ResourceUnexpectedTypeException,
    can_be_promotable,
    can_be_unique,
)
from pcs.common.str_tools import (
    format_list,
    format_optional,
)


def _handle_query_result(result: bool, quiet: bool) -> SystemExit:
    if not quiet:
        print(result)

    if result:
        return SystemExit(0)
    return SystemExit(2)


def _handle_resource_exception(e: ResourceException) -> None:
    resource_id = f"{e.resource_id}{format_optional(e.instance_id, ':{}')}"
    if isinstance(e, ResourceNonExistentException):
        raise CmdLineInputError(f"Resource '{resource_id}' does not exist")
    if isinstance(e, ResourceNotInGroupException):
        raise CmdLineInputError(f"Resource '{resource_id}' is not in a group")
    if isinstance(e, ResourceUnexpectedTypeException):
        raise CmdLineInputError(
            (
                "Resource '{id}' has unexpected type '{real}'. This command "
                "works only for resources of type {expected}"
            ).format(
                id=resource_id,
                real=e.resource_type.value,
                expected=format_list(t.value for t in e.expected_types),
            )
        )
    raise CmdLineInputError(f"Unknown error with resource '{resource_id}'")


def _handle_query_exception(e: QueryException) -> None:
    if isinstance(e, MembersQuantifierUnsupportedException):
        raise CmdLineInputError(
            "'members' quantifier can be used only on group resources or "
            "group instances of cloned groups"
        )
    if isinstance(e, InstancesQuantifierUnsupportedException):
        raise CmdLineInputError(
            (
                "'instances' quantifier can be used only on clone resources "
                "and their instances, or on bundle resources and their replicas"
            )
        )
    raise CmdLineInputError(
        "Unknown error with the query", show_both_usage_and_message=True
    )


def _handle_is_modifiers(modifiers: InputModifiers) -> bool:
    modifiers.ensure_only_supported("--quiet", "-f")

    return modifiers.is_specified("--quiet")


def _handle_get_modifiers(modifiers: InputModifiers) -> None:
    modifiers.ensure_only_supported("-f")


def _get_resource_status_facade(lib: Any) -> ResourcesStatusFacade:
    dto = lib.status.resources_status()
    return ResourcesStatusFacade.from_resources_status_dto(dto)


def _parse_more_members_quantifier(
    sections: ArgsByKeywords,
    keyword: str,
) -> Optional[MoreChildrenQuantifierType]:
    if not sections.has_keyword(keyword):
        return None

    args = sections.get_args_flat(keyword)
    if len(args) != 1:
        raise CmdLineInputError()

    try:
        return MoreChildrenQuantifierType[args[0].upper()]
    except KeyError as e:
        raise CmdLineInputError(
            reports.messages.InvalidOptionValue(
                keyword,
                args[0],
                [
                    quantifier.name.lower()
                    for quantifier in MoreChildrenQuantifierType
                ],
            ).message
        ) from e


def _parse_expected_state(
    state_section: Argv,
) -> tuple[ResourceState, Optional[str]]:
    if not state_section or len(state_section) > 2:
        raise CmdLineInputError()

    try:
        expected_state = ResourceState[state_section[0].upper()]
    except KeyError as e:
        raise CmdLineInputError(
            reports.messages.InvalidOptionValue(
                "state",
                state_section[0],
                [state.name.lower() for state in ResourceState],
            ).message
        ) from e

    if len(state_section) == 1:
        return expected_state, None

    if expected_state not in EXACT_CHECK_STATES:
        raise CmdLineInputError()

    return expected_state, state_section[1]


def _pop_resource_id(argv: Argv) -> tuple[str, Optional[str]]:
    if len(argv) < 1:
        raise CmdLineInputError()
    resource_id = argv.pop(0)

    if not resource_id:
        raise CmdLineInputError()

    if ":" in resource_id:
        resource_id, instance_id = resource_id.rsplit(":", 1)
        return resource_id, instance_id

    return resource_id, None


def exists(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)
    if argv:
        raise CmdLineInputError()

    quiet = _handle_is_modifiers(modifiers)

    raise _handle_query_result(
        _get_resource_status_facade(lib).exists(resource_id, instance_id),
        quiet,
    )


def is_type(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    quiet = _handle_is_modifiers(modifiers)

    sections = group_by_keywords(argv, ["unique", "promotable"], "type")
    sections.ensure_unique_keywords()

    type_section = sections.get_args_flat("type")
    if len(type_section) != 1:
        raise CmdLineInputError()
    try:
        expected_type = ResourceType[type_section[0].upper()]
    except KeyError as e:
        raise CmdLineInputError(
            reports.messages.InvalidOptionValue(
                option_name="resource type",
                option_value=type_section[0],
                allowed_values=[
                    resource_type.value for resource_type in ResourceType
                ],
            ).message
        ) from e

    check_unique = sections.has_keyword("unique")
    if check_unique:
        if sections.get_args_flat("unique"):
            raise CmdLineInputError()
        if not can_be_unique(expected_type):
            raise CmdLineInputError(
                f"type '{expected_type.value}' cannot be unique"
            )

    check_promotable = sections.has_keyword("promotable")
    if check_promotable:
        if sections.get_args_flat("promotable"):
            raise CmdLineInputError()
        if not can_be_promotable(expected_type):
            raise CmdLineInputError(
                f"type '{expected_type.value}' cannot be promotable"
            )

    resources_status = _get_resource_status_facade(lib)
    try:
        result = (
            resources_status.get_type(resource_id, instance_id) == expected_type
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    if result and check_unique:
        result = resources_status.is_unique(resource_id, instance_id)

    if result and check_promotable:
        result = resources_status.is_promotable(resource_id, instance_id)

    raise _handle_query_result(result, quiet)


def get_type(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    if argv:
        raise CmdLineInputError()

    _handle_get_modifiers(modifiers)
    resource_status = _get_resource_status_facade(lib)

    try:
        resource_type = resource_status.get_type(resource_id, instance_id)
    except ResourceException as e:
        _handle_resource_exception(e)

    output = [resource_type.value]
    if can_be_unique(resource_type) and resource_status.is_unique(
        resource_id, instance_id
    ):
        output.append("unique")
    if can_be_promotable(resource_type) and resource_status.is_promotable(
        resource_id, instance_id
    ):
        output.append("promotable")

    print(" ".join(output))


def is_stonith(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)
    if argv:
        raise CmdLineInputError()

    quiet = _handle_is_modifiers(modifiers)

    try:
        result = _get_resource_status_facade(lib).is_stonith(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    raise _handle_query_result(result, quiet)


def get_members(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)
    if argv:
        raise CmdLineInputError()

    _handle_get_modifiers(modifiers)

    try:
        members = _get_resource_status_facade(lib).get_members(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    print("\n".join(members))


def get_nodes(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    if argv:
        raise CmdLineInputError()

    _handle_get_modifiers(modifiers)
    try:
        nodes = _get_resource_status_facade(lib).get_nodes(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    print("\n".join(nodes))


def is_state(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    # pylint: disable=too-many-locals
    resource_id, instance_id = _pop_resource_id(argv)

    sections = group_by_keywords(
        argv,
        {"on-node", "members", "instances"},
        implicit_first_keyword="state",
    )
    sections.ensure_unique_keywords()

    expected_state, expected_value = _parse_expected_state(
        sections.get_args_flat("state")
    )

    expected_node_name = None
    if sections.has_keyword("on-node"):
        node_section = sections.get_args_flat("on-node")
        if len(node_section) != 1:
            raise CmdLineInputError()
        expected_node_name = node_section[0]

    members_quantifier = _parse_more_members_quantifier(sections, "members")
    instances_quantifier = _parse_more_members_quantifier(sections, "instances")

    quiet = _handle_is_modifiers(modifiers)

    resource_status = _get_resource_status_facade(lib)
    try:
        if expected_value is not None and (
            expected_state in (ResourceState.LOCKED_TO, ResourceState.PENDING)
        ):
            result = resource_status.is_state_exact_value(
                resource_id,
                instance_id,
                cast(ResourceStateExactCheck, expected_state),
                expected_value,
                expected_node_name,
                members_quantifier,
                instances_quantifier,
            )
        else:
            result = resource_status.is_state(
                resource_id,
                instance_id,
                expected_state,
                expected_node_name,
                members_quantifier,
                instances_quantifier,
            )
    except ResourceException as e:
        _handle_resource_exception(e)
    except QueryException as e:
        _handle_query_exception(e)
    except NotImplementedError as e:
        raise CmdLineInputError(str(e)) from e

    raise _handle_query_result(result, quiet)


def _handle_is_in_container(
    real_id: Optional[str], expected_id: Optional[str], quiet: bool
) -> SystemExit:
    is_in_container = real_id is not None and (
        expected_id is None or real_id == expected_id
    )

    if not quiet:
        print(is_in_container)
        if real_id is not None:
            print(real_id)

    if not is_in_container:
        return SystemExit(2)
    return SystemExit(0)


def is_in_group(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)
    if len(argv) > 1:
        raise CmdLineInputError()
    expected_group_id = argv[0] if argv else None

    quiet = _handle_is_modifiers(modifiers)

    try:
        group_id = _get_resource_status_facade(lib).get_parent_group_id(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    raise _handle_is_in_container(group_id, expected_group_id, quiet)


def is_in_clone(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    if len(argv) > 1:
        raise CmdLineInputError()
    expected_clone_id = argv[0] if argv else None

    quiet = _handle_is_modifiers(modifiers)

    try:
        clone_id = _get_resource_status_facade(lib).get_parent_clone_id(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    raise _handle_is_in_container(clone_id, expected_clone_id, quiet)


def is_in_bundle(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    if len(argv) > 1:
        raise CmdLineInputError()
    expected_bundle_id = argv[0] if argv else None

    quiet = _handle_is_modifiers(modifiers)

    try:
        bundle_id = _get_resource_status_facade(lib).get_parent_bundle_id(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    raise _handle_is_in_container(bundle_id, expected_bundle_id, quiet)


def get_index_in_group(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
        * -f - CIB file
        * --quiet - do not print anything to output
    """
    resource_id, instance_id = _pop_resource_id(argv)

    if argv:
        raise CmdLineInputError()

    _handle_get_modifiers(modifiers)

    try:
        index = _get_resource_status_facade(lib).get_index_in_group(
            resource_id, instance_id
        )
    except ResourceException as e:
        _handle_resource_exception(e)

    print(index)
