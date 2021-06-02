# pylint: disable=too-many-lines
from contextlib import contextmanager
from functools import partial
from typing import (
    cast,
    Any,
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
)

from lxml.etree import _Element

from pcs.common import file_type_codes
from pcs.common.interface import dto
from pcs.common import reports
from pcs.common.reports import ReportItemList
from pcs.common.reports.item import ReportItem
from pcs.common.tools import Version
from pcs.lib.cib import (
    resource,
    status as cib_status,
)
from pcs.lib.cib.tag import (
    expand_tag,
    TAG_TAG,
)
from pcs.lib.cib.tools import (
    find_element_by_tag_and_id,
    get_resources,
    get_status,
    IdProvider,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.external import CommandRunner
from pcs.lib.node import get_existing_nodes_names_addrs
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker import simulate as simulate_tools
from pcs.lib.pacemaker.live import (
    has_resource_unmove_unban_expired_support,
    resource_ban,
    resource_move,
    resource_unmove_unban,
    simulate_cib,
    wait_for_idle,
)
from pcs.lib.pacemaker.state import (
    ensure_resource_state,
    get_resource_state,
    info_resource_state,
    is_resource_managed,
    ResourceNotFound,
)
from pcs.lib.pacemaker.values import (
    timeout_to_seconds,
    validate_id,
)
from pcs.lib.resource_agent import (
    find_valid_resource_agent_by_name as get_agent,
)
from pcs.lib.validate import ValueTimeInterval


WaitType = Union[None, bool, int]


@contextmanager
def resource_environment(
    env,
    wait=False,
    wait_for_resource_ids=None,
    resource_state_reporter=info_resource_state,
    required_cib_version=None,
):
    env.ensure_wait_satisfiable(wait)
    yield get_resources(env.get_cib(required_cib_version))
    _push_cib_wait(env, wait, wait_for_resource_ids, resource_state_reporter)


def _push_cib_wait(
    env: LibraryEnvironment,
    wait: WaitType = False,
    wait_for_resource_ids: Optional[Iterable[str]] = None,
    resource_state_reporter: Callable[
        [_Element, str], ReportItem
    ] = info_resource_state,
) -> None:
    env.push_cib(wait=wait)
    if wait is not False and wait_for_resource_ids:
        state = env.get_cluster_state()
        if env.report_processor.report_list(
            [
                resource_state_reporter(state, res_id)
                for res_id in wait_for_resource_ids
            ]
        ).has_errors:
            raise LibraryError()


def _ensure_disabled_after_wait(disabled_after_wait):
    def inner(state, resource_id):
        return ensure_resource_state(
            not disabled_after_wait, state, resource_id
        )

    return inner


def _validate_remote_connection(
    resource_agent,
    existing_nodes_addrs,
    resource_id,
    instance_attributes,
    allow_not_suitable_command,
):
    if resource_agent.get_name() != resource.remote_node.AGENT_NAME.full_name:
        return []

    report_list = []
    report_list.append(
        ReportItem(
            severity=reports.item.get_severity(
                reports.codes.FORCE_NOT_SUITABLE_COMMAND,
                allow_not_suitable_command,
            ),
            message=reports.messages.UseCommandNodeAddRemote(),
        )
    )

    report_list.extend(
        resource.remote_node.validate_host_not_conflicts(
            existing_nodes_addrs, resource_id, instance_attributes
        )
    )
    return report_list


def _validate_guest_change(
    tree,
    existing_nodes_names,
    existing_nodes_addrs,
    meta_attributes,
    allow_not_suitable_command,
    detect_remove=False,
):
    if not resource.guest_node.is_node_name_in_options(meta_attributes):
        return []

    node_name = resource.guest_node.get_node_name_from_options(meta_attributes)

    report_list = []
    if detect_remove and not resource.guest_node.get_guest_option_value(
        meta_attributes
    ):
        report_msg = reports.messages.UseCommandNodeRemoveGuest()
    else:
        report_msg = reports.messages.UseCommandNodeAddGuest()

    report_list.append(
        ReportItem(
            severity=reports.item.get_severity(
                reports.codes.FORCE_NOT_SUITABLE_COMMAND,
                allow_not_suitable_command,
            ),
            message=report_msg,
        )
    )

    report_list.extend(
        resource.guest_node.validate_conflicts(
            tree,
            existing_nodes_names,
            existing_nodes_addrs,
            node_name,
            meta_attributes,
        )
    )

    return report_list


def _get_nodes_to_validate_against(env, tree):
    if not env.is_corosync_conf_live and env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired(
                    [file_type_codes.COROSYNC_CONF]
                )
            )
        )

    if not env.is_cib_live and env.is_corosync_conf_live:
        # we do not try to get corosync.conf from live cluster when cib is not
        # taken from live cluster
        return get_existing_nodes_names_addrs(cib=tree)

    return get_existing_nodes_names_addrs(env.get_corosync_conf(), cib=tree)


def _check_special_cases(
    env,
    resource_agent,
    resources_section,
    resource_id,
    meta_attributes,
    instance_attributes,
    allow_not_suitable_command,
):
    # fmt: off
    if (
        resource_agent.get_name() != resource.remote_node.AGENT_NAME.full_name
        and
        not resource.guest_node.is_node_name_in_options(meta_attributes)
    ):
        # if no special case happens we won't take care about corosync.conf that
        # is needed for getting nodes to validate against
        return
    # fmt: on

    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = _get_nodes_to_validate_against(env, resources_section)

    report_list.extend(
        _validate_remote_connection(
            resource_agent,
            existing_nodes_addrs,
            resource_id,
            instance_attributes,
            allow_not_suitable_command,
        )
    )
    report_list.extend(
        _validate_guest_change(
            resources_section,
            existing_nodes_names,
            existing_nodes_addrs,
            meta_attributes,
            allow_not_suitable_command,
        )
    )

    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()


_find_bundle = partial(find_element_by_tag_and_id, resource.bundle.TAG)


def _get_required_cib_version_for_container(
    container_options, container_type=None
):
    if container_type == "podman":
        return Version(3, 2, 0)

    if "promoted-max" in container_options:
        return Version(3, 0, 0)

    if container_type == "rkt":
        return Version(2, 10, 0)

    return Version(2, 8, 0)


def create(
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: Iterable[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create a primitive resource in a cib.

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
        e.g. [{"name": "monitor", "timeout": "10s"}]
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
        a resource representing
        - pacemaker remote node (resource agent is ocf:pacemaker:remote)
        - or pacemaker guest node (contains meta attribute remote-node)
        should not be created by this function since the creation of such
        resource should be accompanied by further actions (see
        pcs.lib.commands.remote_node);
        in the case of remote/guest node forcible error is produced when this
        flag is set to False and warning is produced otherwise
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)


def create_as_clone(
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: Iterable[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    clone_meta_options: Mapping[str, str],
    clone_id: Optional[str] = None,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create a primitive resource in a clone

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    clone_meta_options -- contains attributes for clone/meta_attributes
    clone_id -- optional custom clone id, if not set then clone id is generated
        from primitive resource or group id
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
            or resource.common.is_clone_deactivated_by_meta(clone_meta_options)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if clone_id is not None:
            if env.report_processor.report_list(
                resource.clone.validate_clone_id(clone_id, id_provider),
            ).has_errors:
                raise LibraryError()
        clone_element = resource.clone.append_new(
            resources_section,
            id_provider,
            primitive_element,
            clone_meta_options,
            clone_id=clone_id,
        )
        if ensure_disabled:
            resource.common.disable(clone_element, id_provider)


def create_in_group(
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    group_id: str,
    operation_list: Iterable[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    adjacent_resource_id: Optional[str] = None,
    put_after_adjacent: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create resource in a cib and put it into defined group

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    group_id -- is identificator for group to put primitive resource inside
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    adjacent_resource_id -- identify neighbor of a newly created resource
    put_after_adjacent -- is flag to put a newly create resource befor/after
        adjacent resource
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)
        validate_id(group_id, "group name")
        resource.group.place_resource(
            resource.group.provide_group(resources_section, group_id),
            primitive_element,
            adjacent_resource_id,
            put_after_adjacent,
        )


def create_into_bundle(
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: Iterable[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    bundle_id: str,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
    allow_not_accessible_resource: bool = False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create a new resource in a cib and put it into an existing bundle

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for
        primitive/instance_attributes
    bundle_id -- is id of an existing bundle to put the created resource in
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
    allow_not_accessible_resource -- flag for
        FORCE_RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    required_cib_version = get_required_cib_version_for_primitive(
        operation_list
    )
    if not required_cib_version:
        required_cib_version = Version(2, 8, 0)
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=required_cib_version,
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)

        bundle_el = _find_bundle(resources_section, bundle_id)
        if not resource.bundle.is_pcmk_remote_accessible(bundle_el):
            if env.report_processor.report(
                ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE_RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                        allow_not_accessible_resource,
                    ),
                    message=reports.messages.ResourceInBundleNotAccessible(
                        bundle_id,
                        resource_id,
                    ),
                )
            ).has_errors:
                raise LibraryError()
        resource.bundle.add_resource(bundle_el, primitive_element)


def bundle_create(
    env,
    bundle_id,
    container_type,
    container_options=None,
    network_options=None,
    port_map=None,
    storage_map=None,
    meta_attributes=None,
    force_options=False,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Create a new bundle containing no resources

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the new bundle
    string container_type -- container engine name (docker, lxc...)
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- a list of port mapping options
    list of dict storage_map -- a list of storage mapping options
    dict meta_attributes -- bundle's meta attributes
    bool force_options -- return warnings instead of forceable errors
    bool ensure_disabled -- set the bundle's target-role to "Stopped"
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    container_options = container_options or {}
    network_options = network_options or {}
    port_map = port_map or []
    storage_map = storage_map or []
    meta_attributes = meta_attributes or {}

    with resource_environment(
        env,
        wait,
        [bundle_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=_get_required_cib_version_for_container(
            container_options,
            container_type,
        ),
    ) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        if env.report_processor.report_list(
            resource.bundle.validate_new(
                id_provider,
                bundle_id,
                container_type,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()
        bundle_element = resource.bundle.append_new(
            resources_section,
            id_provider,
            bundle_id,
            container_type,
            container_options,
            network_options,
            port_map,
            storage_map,
            meta_attributes,
        )
        if ensure_disabled:
            resource.common.disable(bundle_element, id_provider)


def bundle_reset(
    env,
    bundle_id,
    container_options=None,
    network_options=None,
    port_map=None,
    storage_map=None,
    meta_attributes=None,
    force_options=False,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Remove configuration of bundle bundle_id and create new one into it.

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the bundle to reset
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- a list of port mapping options
    list of dict storage_map -- a list of storage mapping options
    dict meta_attributes -- bundle's meta attributes
    bool force_options -- return warnings instead of forceable errors
    bool ensure_disabled -- set the bundle's target-role to "Stopped"
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    container_options = container_options or {}
    network_options = network_options or {}
    port_map = port_map or []
    storage_map = storage_map or []
    meta_attributes = meta_attributes or {}

    with resource_environment(
        env,
        wait,
        [bundle_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=_get_required_cib_version_for_container(
            container_options
        ),
    ) as resources_section:
        bundle_element = _find_bundle(resources_section, bundle_id)
        if env.report_processor.report_list(
            resource.bundle.validate_reset_to_minimal(bundle_element)
        ).has_errors:
            raise LibraryError()
        resource.bundle.reset_to_minimal(bundle_element)

        id_provider = IdProvider(resources_section)
        if env.report_processor.report_list(
            resource.bundle.validate_reset(
                id_provider,
                bundle_element,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()

        resource.bundle.update(
            id_provider,
            bundle_element,
            container_options,
            network_options,
            port_map_add=port_map,
            port_map_remove=[],
            storage_map_add=storage_map,
            storage_map_remove=[],
            meta_attributes=meta_attributes,
        )

        if ensure_disabled:
            resource.common.disable(bundle_element, id_provider)


def bundle_update(
    env,
    bundle_id,
    container_options=None,
    network_options=None,
    port_map_add=None,
    port_map_remove=None,
    storage_map_add=None,
    storage_map_remove=None,
    meta_attributes=None,
    force_options=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Modify an existing bundle (does not touch encapsulated resources)

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the bundle to modify
    dict container_options -- container options to modify
    dict network_options -- network options to modify
    list of dict port_map_add -- list of port mapping options to add
    list of string port_map_remove -- list of port mapping ids to remove
    list of dict storage_map_add -- list of storage mapping options to add
    list of string storage_map_remove -- list of storage mapping ids to remove
    dict meta_attributes -- meta attributes to update
    bool force_options -- return warnings instead of forceable errors
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    container_options = container_options or {}
    network_options = network_options or {}
    port_map_add = port_map_add or []
    port_map_remove = port_map_remove or []
    storage_map_add = storage_map_add or []
    storage_map_remove = storage_map_remove or []
    meta_attributes = meta_attributes or {}

    with resource_environment(
        env,
        wait,
        [bundle_id],
        required_cib_version=_get_required_cib_version_for_container(
            container_options
        ),
    ) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        bundle_element = _find_bundle(resources_section, bundle_id)
        if env.report_processor.report_list(
            resource.bundle.validate_update(
                id_provider,
                bundle_element,
                container_options,
                network_options,
                port_map_add,
                port_map_remove,
                storage_map_add,
                storage_map_remove,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()
        resource.bundle.update(
            id_provider,
            bundle_element,
            container_options,
            network_options,
            port_map_add,
            port_map_remove,
            storage_map_add,
            storage_map_remove,
            meta_attributes,
        )


def _disable_validate_and_edit_cib(
    env: LibraryEnvironment,
    cib: _Element,
    resource_or_tag_ids: Iterable[str],
) -> List[_Element]:
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)
    if env.report_processor.report_list(
        _resource_list_enable_disable(
            resource_el_list,
            resource.common.disable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    ).has_errors:
        raise LibraryError()
    return resource_el_list


def _disable_get_element_ids(
    disabled_resource_el_list: Iterable[_Element],
) -> Tuple[Set[str], Set[str]]:
    """
    Turn a list of elements asked by a user to be disabled to a list of their
    IDs and a list of IDs of their inner elements. Remember, the user can
    specify tags instead of resources. Therefore the list of disabled
    resources' IDs returned by this function may be different than the list of
    IDs entered in the command.
    """
    inner_resource_id_set = set()
    disabled_resource_id_set = set()
    for resource_el in disabled_resource_el_list:
        disabled_resource_id_set.add(cast(Optional[str], resource_el.get("id")))
        inner_resource_id_set.update(
            {
                cast(Optional[str], inner_resource_el.get("id"))
                for inner_resource_el in resource.common.get_all_inner_resources(
                    resource_el
                )
            }
        )
    # Make sure we only return found IDs and not None to match the function's
    # return type annotation.
    return (
        set(filter(None, disabled_resource_id_set)),
        set(filter(None, inner_resource_id_set)),
    )


def _disable_run_simulate(
    cmd_runner: CommandRunner,
    cib: _Element,
    disabled_resource_ids: Set[str],
    inner_resource_ids: Set[str],
    strict: bool,
) -> Tuple[str, Set[str]]:
    plaintext_status, transitions, dummy_cib = simulate_cib(cmd_runner, cib)
    simulated_operations = simulate_tools.get_operations_from_transitions(
        transitions
    )
    other_affected: Set[str] = set()
    if strict:
        other_affected = set(
            simulate_tools.get_resources_from_operations(
                simulated_operations, exclude=disabled_resource_ids
            )
        )
    else:
        other_affected = set(
            simulate_tools.get_resources_left_stopped(
                simulated_operations, exclude=disabled_resource_ids
            )
            + simulate_tools.get_resources_left_demoted(
                simulated_operations, exclude=disabled_resource_ids
            )
        )

    # Stopping a clone stops all its inner resources. That should not block
    # stopping the clone.
    other_affected = other_affected - inner_resource_ids
    return plaintext_status, other_affected


def disable(
    env: LibraryEnvironment,
    resource_or_tag_ids: Iterable[str],
    wait: WaitType = False,
):
    """
    Disallow specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    env.ensure_wait_satisfiable(wait)
    _disable_validate_and_edit_cib(env, env.get_cib(), resource_or_tag_ids)
    _push_cib_wait(
        env, wait, resource_or_tag_ids, _ensure_disabled_after_wait(True)
    )


def disable_safe(
    env: LibraryEnvironment,
    resource_or_tag_ids: Iterable[str],
    strict: bool,
    wait: WaitType = False,
):
    """
    Disallow specified resources to be started by the cluster only if there is
    no effect on other resources

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    strict -- if False, allow resources to be migrated
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    # pylint: disable=too-many-locals
    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )

    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    resource_el_list = _disable_validate_and_edit_cib(
        env, cib, resource_or_tag_ids
    )
    disabled_resource_id_set, inner_resource_id_set = _disable_get_element_ids(
        resource_el_list
    )
    plaintext_status, other_affected = _disable_run_simulate(
        env.cmd_runner(),
        cib,
        disabled_resource_id_set,
        inner_resource_id_set,
        strict,
    )
    if other_affected:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceDisableAffectsOtherResources(
                    sorted(disabled_resource_id_set),
                    sorted(other_affected),
                    plaintext_status,
                )
            )
        )
    _push_cib_wait(
        env, wait, disabled_resource_id_set, _ensure_disabled_after_wait(True)
    )


def disable_simulate(
    env: LibraryEnvironment, resource_or_tag_ids: Iterable[str], strict: bool
) -> Mapping[str, Union[str, List[str]]]:
    """
    Simulate disallowing specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    bool strict -- if False, allow resources to be migrated
    """
    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )

    cib = env.get_cib()
    resource_el_list = _disable_validate_and_edit_cib(
        env, cib, resource_or_tag_ids
    )
    disabled_resource_id_set, inner_resource_id_set = _disable_get_element_ids(
        resource_el_list
    )
    plaintext_status, other_affected = _disable_run_simulate(
        env.cmd_runner(),
        cib,
        disabled_resource_id_set,
        inner_resource_id_set,
        strict,
    )
    return dict(
        plaintext_simulated_status=plaintext_status,
        other_affected_resource_list=sorted(other_affected),
    )


def enable(
    env: LibraryEnvironment,
    resource_or_tag_ids: Iterable[str],
    wait: WaitType = False,
):
    """
    Allow specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become enabled, or in case
        of tag ids, all resources in tags are to be enabled
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    to_enable_set = set()
    for el in resource_el_list:
        to_enable_set.update(resource.common.find_resources_to_enable(el))

    if env.report_processor.report_list(
        _resource_list_enable_disable(
            to_enable_set,
            resource.common.enable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    ).has_errors:
        raise LibraryError()
    _push_cib_wait(
        env,
        wait,
        [str(el.get("id", "")) for el in resource_el_list],
        _ensure_disabled_after_wait(False),
    )


def _resource_list_enable_disable(
    resource_el_list, func, id_provider, cluster_state
):
    report_list = []
    for resource_el in resource_el_list:
        res_id = resource_el.attrib["id"]
        try:
            if not is_resource_managed(cluster_state, res_id):
                report_list.append(
                    ReportItem.warning(
                        reports.messages.ResourceIsUnmanaged(res_id)
                    )
                )
            func(resource_el, id_provider)
        except ResourceNotFound:
            report_list.append(
                ReportItem.error(
                    reports.messages.IdNotFound(
                        res_id,
                        ["bundle", "clone", "group", "master", "primitive"],
                    )
                )
            )
    return report_list


def unmanage(
    env: LibraryEnvironment,
    resource_or_tag_ids: Iterable[str],
    with_monitor: bool = False,
) -> None:
    """
    Set specified resources not to be managed by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become unmanaged, or in case
        of tag ids, all resources in tags are to be managed
    with_monitor -- disable resources' monitor operations
    """
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids, resource.common.find_resources_to_unmanage
    )
    env.report_processor.report_list(report_list)
    if env.report_processor.has_errors:
        raise LibraryError()

    primitives_set = set()
    for resource_el in resource_el_list:
        resource.common.unmanage(resource_el, IdProvider(cib))
        if with_monitor:
            primitives_set.update(resource.common.find_primitives(resource_el))

    for resource_el in primitives_set:
        for op in resource.operations.get_resource_operations(
            resource_el, ["monitor"]
        ):
            resource.operations.disable(op)
    env.push_cib()


def manage(
    env: LibraryEnvironment,
    resource_or_tag_ids: Iterable[str],
    with_monitor: bool = False,
) -> None:
    """
    Set specified resources to be managed by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become managed, or in case
        of tag id, all resources in tag are to be managed
    with_monitor -- enable resources' monitor operations
    """
    cib = env.get_cib()

    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids, resource.common.find_resources_to_manage
    )

    primitives_set = set()
    for resource_el in resource_el_list:
        resource.common.manage(resource_el, IdProvider(cib))
        primitives_set.update(resource.common.find_primitives(resource_el))

    for resource_el in sorted(
        primitives_set, key=lambda element: element.get("id", "")
    ):
        op_list = resource.operations.get_resource_operations(
            resource_el, ["monitor"]
        )
        if with_monitor:
            for op in op_list:
                resource.operations.enable(op)
        else:
            monitor_enabled = False
            for op in op_list:
                if resource.operations.is_enabled(op):
                    monitor_enabled = True
                    break
            if op_list and not monitor_enabled:
                # do not advise enabling monitors if there are none defined
                report_list.append(
                    ReportItem.warning(
                        reports.messages.ResourceManagedNoMonitorEnabled(
                            str(resource_el.get("id", ""))
                        )
                    )
                )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    env.push_cib()


def group_add(
    env,
    group_id,
    resource_id_list,
    adjacent_resource_id=None,
    put_after_adjacent=True,
    wait=False,
):
    """
    Move specified resources into an existing or new group

    LibraryEnvironment env provides all for communication with externals
    string group_id -- id of the target group
    iterable resource_id_list -- ids of resources to put into the group
    string adjacent_resource_id -- put resources beside this one if specified
    bool put_after_adjacent -- put resources after or before the adjacent one
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    with resource_environment(env, wait, [group_id]) as resources_section:
        id_provider = IdProvider(resources_section)

        validator = resource.hierarchy.ValidateMoveResourcesToGroupByIds(
            group_id,
            resource_id_list,
            adjacent_resource_id=adjacent_resource_id,
        )
        if env.report_processor.report_list(
            validator.validate(resources_section, id_provider)
        ).has_errors:
            raise LibraryError()

        # If we get no group element from the validator and there were no
        # errors, then the element does not exist and we can create it.
        group_element = validator.group_element()
        if group_element is None:
            group_element = resource.group.append_new(
                resources_section, group_id
            )

        resource.hierarchy.move_resources_to_group(
            group_element,
            validator.resource_element_list(),
            adjacent_resource=validator.adjacent_resource_element(),
            put_after_adjacent=put_after_adjacent,
        )


def get_failcounts(
    env, resource=None, node=None, operation=None, interval=None
):
    # pylint: disable=redefined-outer-name
    """
    List resources failcounts, optionally filtered by a resource, node or op

    LibraryEnvironment env
    string resource -- show failcounts for the specified resource only
    string node -- show failcounts for the specified node only
    string operation -- show failcounts for the specified operation only
    string interval -- show failcounts for the specified operation interval only
    """
    report_items = []
    if interval is not None and operation is None:
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionIsMissing(
                    "interval", "operation"
                )
            )
        )
    if interval is not None:
        report_items.extend(
            ValueTimeInterval("interval").validate({"interval": interval})
        )
    if report_items:
        raise LibraryError(*report_items)

    interval_ms = (
        None if interval is None else timeout_to_seconds(interval) * 1000
    )

    all_failcounts = cib_status.get_resources_failcounts(
        get_status(env.get_cib())
    )
    return cib_status.filter_resources_failcounts(
        all_failcounts,
        resource=resource,
        node=node,
        operation=operation,
        interval=interval_ms,
    )


def move(env, resource_id, node=None, master=False, lifetime=None, wait=False):
    """
    Create a constraint to move a resource

    LibraryEnvironment env
    string resource_id -- id of a resource to be moved
    string node -- node to move the resource to, ban on the current node if None
    bool master -- limit the constraint to the Master role
    string lifetime -- lifespan of the constraint, forever if None
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    return _Move().run(
        env, resource_id, node=node, master=master, lifetime=lifetime, wait=wait
    )


def ban(env, resource_id, node=None, master=False, lifetime=None, wait=False):
    """
    Create a constraint to keep a resource of a node

    LibraryEnvironment env
    string resource_id -- id of a resource to be banned
    string node -- node to ban the resource on, ban on the current node if None
    bool master -- limit the constraint to the Master role
    string lifetime -- lifespan of the constraint, forever if None
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    return _Ban().run(
        env, resource_id, node=node, master=master, lifetime=lifetime, wait=wait
    )


class _MoveBanTemplate:
    def _validate(self, resource_el, master):
        raise NotImplementedError()

    def _run_action(self, runner, resource_id, node, master, lifetime):
        raise NotImplementedError()

    def _report_action_stopped_resource(self, resource_id):
        raise NotImplementedError()

    def _report_action_pcmk_error(self, resource_id, stdout, stderr):
        raise NotImplementedError()

    def _report_action_pcmk_success(self, resource_id, stdout, stderr):
        raise NotImplementedError()

    def _report_wait_result(
        self,
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        raise NotImplementedError()

    @staticmethod
    def _running_on_nodes(resource_state):
        if resource_state:
            return frozenset(
                resource_state.get("Master", [])
                + resource_state.get("Started", [])
            )
        return frozenset()

    def run(
        self,
        env,
        resource_id,
        node=None,
        master=False,
        lifetime=None,
        wait=False,
    ):
        # validate
        env.ensure_wait_satisfiable(wait)  # raises on error

        resource_el, report_list = resource.common.find_one_resource(
            get_resources(env.get_cib()), resource_id
        )
        if resource_el is not None:
            report_list.extend(self._validate(resource_el, master))
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        # get current status for wait processing
        if wait is not False:
            resource_running_on_before = get_resource_state(
                env.get_cluster_state(), resource_id
            )

        # run the action
        stdout, stderr, retval = self._run_action(
            env.cmd_runner(),
            resource_id,
            node=node,
            master=master,
            lifetime=lifetime,
        )
        if retval != 0:
            if (
                f"Resource '{resource_id}' not moved: active in 0 locations"
                in stderr
            ):
                raise LibraryError(
                    self._report_action_stopped_resource(resource_id)
                )
            raise LibraryError(
                self._report_action_pcmk_error(resource_id, stdout, stderr)
            )
        env.report_processor.report(
            self._report_action_pcmk_success(resource_id, stdout, stderr)
        )

        # process wait
        if wait is not False:
            wait_for_idle(env.cmd_runner(), env.get_wait_timeout(wait))
            resource_running_on_after = get_resource_state(
                env.get_cluster_state(), resource_id
            )
            if env.report_processor.report(
                self._report_wait_result(
                    resource_id,
                    node,
                    resource_running_on_before,
                    resource_running_on_after,
                )
            ).has_errors:
                raise LibraryError()


class _Move(_MoveBanTemplate):
    def _validate(self, resource_el, master):
        return resource.common.validate_move(resource_el, master)

    def _run_action(self, runner, resource_id, node, master, lifetime):
        return resource_move(
            runner, resource_id, node=node, master=master, lifetime=lifetime
        )

    def _report_action_stopped_resource(self, resource_id):
        return ReportItem.error(
            reports.messages.CannotMoveResourceStoppedNoNodeSpecified(
                resource_id
            )
        )

    def _report_action_pcmk_error(self, resource_id, stdout, stderr):
        return ReportItem.error(
            reports.messages.ResourceMovePcmkError(resource_id, stdout, stderr)
        )

    def _report_action_pcmk_success(self, resource_id, stdout, stderr):
        return ReportItem.info(
            reports.messages.ResourceMovePcmkSuccess(
                resource_id,
                stdout,
                stderr,
            )
        )

    def _report_wait_result(
        self,
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        allowed_nodes = frozenset([node] if node else [])
        running_on_nodes = self._running_on_nodes(resource_running_on_after)

        severity = reports.item.ReportItemSeverity.info()
        if resource_running_on_before and (  # running resource moved
            not running_on_nodes
            or (allowed_nodes and allowed_nodes.isdisjoint(running_on_nodes))
            or (resource_running_on_before == resource_running_on_after)
        ):
            severity = reports.item.ReportItemSeverity.error()
        if not resource_running_on_after:
            return ReportItem(
                severity,
                reports.messages.ResourceDoesNotRun(resource_id),
            )
        return ReportItem(
            severity,
            reports.messages.ResourceRunningOnNodes(
                resource_id,
                resource_running_on_after,
            ),
        )


class _Ban(_MoveBanTemplate):
    def _validate(self, resource_el, master):
        return resource.common.validate_ban(resource_el, master)

    def _run_action(self, runner, resource_id, node, master, lifetime):
        return resource_ban(
            runner, resource_id, node=node, master=master, lifetime=lifetime
        )

    def _report_action_stopped_resource(self, resource_id):
        return ReportItem.error(
            reports.messages.CannotBanResourceStoppedNoNodeSpecified(
                resource_id,
            )
        )

    def _report_action_pcmk_error(self, resource_id, stdout, stderr):
        return ReportItem.error(
            reports.messages.ResourceBanPcmkError(resource_id, stdout, stderr)
        )

    def _report_action_pcmk_success(
        self,
        resource_id: str,
        stdout: str,
        stderr: str,
    ) -> ReportItem:
        return ReportItem.info(
            reports.messages.ResourceBanPcmkSuccess(resource_id, stdout, stderr)
        )

    def _report_wait_result(
        self,
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        running_on_nodes = self._running_on_nodes(resource_running_on_after)
        if node:
            banned_nodes = frozenset([node])
        else:
            banned_nodes = self._running_on_nodes(resource_running_on_before)

        severity = reports.item.ReportItemSeverity.info()
        if not banned_nodes.isdisjoint(running_on_nodes) or (
            resource_running_on_before and not running_on_nodes
        ):
            severity = reports.item.ReportItemSeverity.error()
        if not resource_running_on_after:
            return ReportItem(
                severity,
                reports.messages.ResourceDoesNotRun(resource_id),
            )
        return ReportItem(
            severity,
            reports.messages.ResourceRunningOnNodes(
                resource_id,
                resource_running_on_after,
            ),
        )


def unmove_unban(
    env, resource_id, node=None, master=False, expired=False, wait=False
):
    """
    Remove all constraints created by move and ban

    LibraryEnvironment env
    string resource_id -- id of a resource to be unmoved/unbanned
    string node -- node to limit unmoving/unbanning to, all nodes if None
    bool master -- only remove constraints for Master role
    bool expired -- only remove constrains which have already expired
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    # validate
    env.ensure_wait_satisfiable(wait)  # raises on error

    resource_el, report_list = resource.common.find_one_resource(
        get_resources(env.get_cib()), resource_id
    )
    if resource_el is not None:
        report_list.extend(
            resource.common.validate_unmove_unban(resource_el, master)
        )
    if expired and not has_resource_unmove_unban_expired_support(
        env.cmd_runner()
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.ResourceUnmoveUnbanPcmkExpiredNotSupported()
            )
        )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    # run the action
    stdout, stderr, retval = resource_unmove_unban(
        env.cmd_runner(), resource_id, node=node, master=master, expired=expired
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceUnmoveUnbanPcmkError(
                    resource_id, stdout, stderr
                )
            )
        )
    env.report_processor.report(
        ReportItem.info(
            reports.messages.ResourceUnmoveUnbanPcmkSuccess(
                resource_id, stdout, stderr
            )
        )
    )

    # process wait
    if wait is not False:
        wait_for_idle(env.cmd_runner(), env.get_wait_timeout(wait))
        if env.report_processor.report(
            info_resource_state(env.get_cluster_state(), resource_id)
        ).has_errors:
            raise LibraryError()


def get_resource_relations_tree(
    env: LibraryEnvironment,
    resource_id: str,
) -> Mapping[str, Any]:
    """
    Return a dict representing tree-like structure of resources and their
    relations.

    env -- library environment
    resource_id -- id of a resource which should be the root of the relation
        tree
    """
    cib = env.get_cib()

    dummy_resource_el, report_list = resource.common.find_one_resource(
        get_resources(cib), resource_id
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    (
        resources_dict,
        relations_dict,
    ) = resource.relations.ResourceRelationsFetcher(cib).get_relations(
        resource_id
    )
    return dto.to_dict(
        resource.relations.ResourceRelationTreeBuilder(
            resources_dict, relations_dict
        )
        .get_tree(resource_id)
        .to_dto()
    )


def _find_resources_expand_tags(
    cib: _Element,
    resource_or_tag_ids: Iterable[str],
    additional_search: Optional[Callable[[_Element], List[_Element]]] = None,
) -> Tuple[List[_Element], ReportItemList]:
    rsc_or_tag_el_list, report_list = resource.common.find_resources(
        cib,
        resource_or_tag_ids,
        resource_tags=resource.common.ALL_RESOURCE_XML_TAGS + [TAG_TAG],
    )

    resource_set = set()
    for el in rsc_or_tag_el_list:
        resource_set.update(
            expand_tag(
                el, only_expand_types=resource.common.ALL_RESOURCE_XML_TAGS
            )
        )
    if not additional_search:
        return list(resource_set), report_list

    final_set = set()
    for el in resource_set:
        final_set.update(additional_search(el))
    return list(final_set), report_list


def get_required_cib_version_for_primitive(
    op_list: Iterable[Mapping[str, str]]
) -> Optional[Version]:
    for op in op_list:
        if op.get("on-fail", "") == "demote":
            return Version(3, 4, 0)
    return None
