from contextlib import contextmanager
from functools import partial

from pcs.common import report_codes
from pcs.common.tools import Version
from pcs.lib import reports
from pcs.lib.cib import (
    resource,
    status as cib_status,
)
from pcs.lib.cib.tools import (
    find_element_by_tag_and_id,
    get_resources,
    get_status,
    IdProvider,
)
from pcs.lib.env_tools import get_existing_nodes_names_addrs
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    timeout_to_seconds,
    validate_id,
)
from pcs.lib.pacemaker.state import (
    ensure_resource_state,
    info_resource_state,
    is_resource_managed,
    ResourceNotFound,
)
from pcs.lib.resource_agent import(
    find_valid_resource_agent_by_name as get_agent
)
from pcs.lib.validate import value_time_interval

@contextmanager
def resource_environment(
    env,
    wait=False,
    wait_for_resource_ids=None,
    resource_state_reporter=info_resource_state,
    required_cib_version=None
):
    env.ensure_wait_satisfiable(wait)
    yield get_resources(env.get_cib(required_cib_version))
    env.push_cib(wait=wait)
    if wait is not False and wait_for_resource_ids:
        state = env.get_cluster_state()
        env.report_processor.process_list([
            resource_state_reporter(state, res_id)
            for res_id in wait_for_resource_ids
        ])

def _ensure_disabled_after_wait(disabled_after_wait):
    def inner(state, resource_id):
        return ensure_resource_state(
            not disabled_after_wait,
            state,
            resource_id
        )
    return inner

def _validate_remote_connection(
    resource_agent, existing_nodes_addrs, resource_id, instance_attributes,
    allow_not_suitable_command
):
    if resource_agent.get_name() != resource.remote_node.AGENT_NAME.full_name:
        return []

    report_list = []
    report_list.append(
        reports.get_problem_creator(
            report_codes.FORCE_NOT_SUITABLE_COMMAND,
            allow_not_suitable_command
        )(reports.use_command_node_add_remote)
    )

    report_list.extend(
        resource.remote_node.validate_host_not_conflicts(
            existing_nodes_addrs,
            resource_id,
            instance_attributes
        )
    )
    return report_list

def _validate_guest_change(
    tree, existing_nodes_names, existing_nodes_addrs, meta_attributes,
    allow_not_suitable_command, detect_remove=False
):
    if not resource.guest_node.is_node_name_in_options(meta_attributes):
        return []

    node_name = resource.guest_node.get_node_name_from_options(meta_attributes)

    report_list = []
    create_report = reports.use_command_node_add_guest
    if (
        detect_remove
        and
        not resource.guest_node.get_guest_option_value(meta_attributes)
    ):
        create_report = reports.use_command_node_remove_guest

    report_list.append(
        reports.get_problem_creator(
            report_codes.FORCE_NOT_SUITABLE_COMMAND,
            allow_not_suitable_command
        )(create_report)
    )

    report_list.extend(
        resource.guest_node.validate_conflicts(
            tree,
            existing_nodes_names,
            existing_nodes_addrs,
            node_name,
            meta_attributes
        )
    )

    return report_list

def _get_nodes_to_validate_against(env, tree):
    if not env.is_corosync_conf_live and env.is_cib_live:
        raise LibraryError(
            reports.live_environment_required(["COROSYNC_CONF"])
        )

    if not env.is_cib_live and env.is_corosync_conf_live:
        #we do not try to get corosync.conf from live cluster when cib is not
        #taken from live cluster
        return get_existing_nodes_names_addrs(cib=tree)

    return get_existing_nodes_names_addrs(env.get_corosync_conf(), cib=tree)


def _check_special_cases(
    env, resource_agent, resources_section, resource_id, meta_attributes,
    instance_attributes, allow_not_suitable_command
):
    if(
        resource_agent.get_name() != resource.remote_node.AGENT_NAME.full_name
        and
        not resource.guest_node.is_node_name_in_options(meta_attributes)
    ):
        #if no special case happens we won't take care about corosync.conf that
        #is needed for getting nodes to validate against
        return

    existing_nodes_names, existing_nodes_addrs = _get_nodes_to_validate_against(
        env,
        resources_section
    )

    report_list = []
    report_list.extend(_validate_remote_connection(
        resource_agent,
        existing_nodes_addrs,
        resource_id,
        instance_attributes,
        allow_not_suitable_command,
    ))
    report_list.extend(_validate_guest_change(
        resources_section,
        existing_nodes_names,
        existing_nodes_addrs,
        meta_attributes,
        allow_not_suitable_command,
    ))

    env.report_processor.process_list(report_list)

_find_bundle = partial(find_element_by_tag_and_id, resource.bundle.TAG)

def _get_required_cib_version_for_container(container_type, container_options):
    if container_type == "podman":
        return Version(3, 2, 0)

    if "promoted-max" in container_options:
        return Version(3, 0, 0)

    if container_type == "rkt":
        return Version(2, 10, 0)

    return Version(2, 8, 0)

def create(
    env, resource_id, resource_agent_name,
    operation_list, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create resource in a cib.

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operation_list contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    bool allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
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
            or
            resource.common.are_meta_disabled(meta_attributes)
        )
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command
        )

        primitive_element = resource.primitive.create(
            env.report_processor, resources_section, id_provider,
            resource_id, resource_agent,
            operation_list, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)

def create_as_clone(
    env, resource_id, resource_agent_name,
    operation_list, meta_attributes, instance_attributes, clone_meta_options,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create resource in a clone

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operation_list contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    dict clone_meta_options contains attributes for clone/meta_attributes
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    bool allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
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
            or
            resource.common.are_meta_disabled(meta_attributes)
            or
            resource.common.is_clone_deactivated_by_meta(clone_meta_options)
        )
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command
        )

        primitive_element = resource.primitive.create(
            env.report_processor, resources_section, id_provider,
            resource_id, resource_agent,
            operation_list, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        clone_element = resource.clone.append_new(
            resources_section,
            id_provider,
            primitive_element,
            clone_meta_options,
        )
        if ensure_disabled:
            resource.common.disable(clone_element, id_provider)

def create_in_group(
    env, resource_id, resource_agent_name, group_id,
    operation_list, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    adjacent_resource_id=None,
    put_after_adjacent=False,
    wait=False,
    allow_not_suitable_command=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create resource in a cib and put it into defined group

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    string group_id is identificator for group to put primitive resource inside
    list of dict operation_list contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    string adjacent_resource_id identify neighbor of a newly created resource
    bool put_after_adjacent is flag to put a newly create resource befor/after
        adjacent resource
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    bool allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
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
            or
            resource.common.are_meta_disabled(meta_attributes)
        )
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command
        )

        primitive_element = resource.primitive.create(
            env.report_processor, resources_section, id_provider,
            resource_id, resource_agent,
            operation_list, meta_attributes, instance_attributes,
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
    env, resource_id, resource_agent_name,
    operation_list, meta_attributes, instance_attributes,
    bundle_id,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
    allow_not_accessible_resource=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create a new resource in a cib and put it into an existing bundle

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operation_list contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    string bundle_id is id of an existing bundle to put the created resource in
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    bool allow_not_suitable_command -- flag for FORCE_NOT_SUITABLE_COMMAND
    bool allow_not_accessible_resource -- flag for
        FORCE_RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE
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
            or
            resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=Version(2, 8, 0)
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command
        )

        primitive_element = resource.primitive.create(
            env.report_processor, resources_section, id_provider,
            resource_id, resource_agent,
            operation_list, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)

        bundle_el = _find_bundle(resources_section, bundle_id)
        if not resource.bundle.is_pcmk_remote_accessible(bundle_el):
            env.report_processor.process(
                reports.get_problem_creator(
                    report_codes.FORCE_RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
                    allow_not_accessible_resource
                )(
                    reports.resource_in_bundle_not_accessible,
                    bundle_id,
                    resource_id
                )
            )
        resource.bundle.add_resource(bundle_el, primitive_element)

def bundle_create(
    env, bundle_id, container_type, container_options=None,
    network_options=None, port_map=None, storage_map=None, meta_attributes=None,
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
            or
            resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=_get_required_cib_version_for_container(
            container_type,
            container_options
        ),
    ) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        env.report_processor.process_list(
            resource.bundle.validate_new(
                id_provider,
                bundle_id,
                container_type,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options
            )
        )
        bundle_element = resource.bundle.append_new(
            resources_section,
            id_provider,
            bundle_id,
            container_type,
            container_options,
            network_options,
            port_map,
            storage_map,
            meta_attributes
        )
        if ensure_disabled:
            resource.common.disable(bundle_element, id_provider)

def bundle_reset(
    env, bundle_id, container_type, container_options=None,
    network_options=None, port_map=None, storage_map=None, meta_attributes=None,
    force_options=False,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Remove configuration of bundle bundle_id and create new one into it.

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the bundle to reset
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
            or
            resource.common.are_meta_disabled(meta_attributes)
        ),
        required_cib_version=_get_required_cib_version_for_container(
            container_type,
            container_options
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        env.report_processor.process_list(
            resource.bundle.validate_reset(
                id_provider,
                container_type,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options
            )
        )

        bundle_element = _find_bundle(resources_section, bundle_id)
        resource.bundle.reset(
            bundle_element,
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


def bundle_update(
    env, bundle_id, container_options=None, network_options=None,
    port_map_add=None, port_map_remove=None, storage_map_add=None,
    storage_map_remove=None, meta_attributes=None,
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

    required_cib_version = Version(2, 8, 0)
    if "promoted-max" in container_options:
        required_cib_version = Version(3, 0, 0)
    with resource_environment(
        env,
        wait,
        [bundle_id],
        required_cib_version=required_cib_version
    ) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        bundle_element = _find_bundle(resources_section, bundle_id)
        env.report_processor.process_list(
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
                force_options
            )
        )
        resource.bundle.update(
            id_provider,
            bundle_element,
            container_options,
            network_options,
            port_map_add,
            port_map_remove,
            storage_map_add,
            storage_map_remove,
            meta_attributes
        )

def disable(env, resource_ids, wait):
    """
    Disallow specified resource to be started by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to be disabled
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    with resource_environment(
        env, wait, resource_ids, _ensure_disabled_after_wait(True)
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids
        )
        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                resource.common.disable,
                id_provider,
                env.get_cluster_state()
            )
        )

def enable(env, resource_ids, wait):
    """
    Allow specified resource to be started by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to be enabled
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    with resource_environment(
        env, wait, resource_ids, _ensure_disabled_after_wait(False)
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_enable
        )
        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                resource.common.enable,
                id_provider,
                env.get_cluster_state()
            )
        )

def _resource_list_enable_disable(
    resource_el_list, func, id_provider, cluster_state
):
    report_list = []
    for resource_el in resource_el_list:
        res_id = resource_el.attrib["id"]
        try:
            if not is_resource_managed(cluster_state, res_id):
                report_list.append(reports.resource_is_unmanaged(res_id))
            func(resource_el, id_provider)
        except ResourceNotFound:
            report_list.append(
                reports.id_not_found(
                    res_id,
                    ["primitive", "clone", "group", "bundle", "master"]
               )
            )
    return report_list

def unmanage(env, resource_ids, with_monitor=False):
    """
    Set specified resources not to be managed by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to become unmanaged
    bool with_monitor -- disable resources' monitor operations
    """
    with resource_environment(env) as resources_section:
        id_provider = IdProvider(resources_section)
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_unmanage
        )
        primitives = []

        for resource_el in resource_el_list:
            resource.common.unmanage(resource_el, id_provider)
            if with_monitor:
                primitives.extend(
                    resource.common.find_primitives(resource_el)
                )

        for resource_el in set(primitives):
            for op in resource.operations.get_resource_operations(
                resource_el,
                ["monitor"]
            ):
                resource.operations.disable(op)

def manage(env, resource_ids, with_monitor=False):
    """
    Set specified resource to be managed by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to become managed
    bool with_monitor -- enable resources' monitor operations
    """
    with resource_environment(env) as resources_section:
        id_provider = IdProvider(resources_section)
        report_list = []
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_manage
        )
        primitives = []

        for resource_el in resource_el_list:
            resource.common.manage(resource_el, id_provider)
            primitives.extend(
                resource.common.find_primitives(resource_el)
            )

        for resource_el in sorted(
            set(primitives),
            key=lambda element: element.get("id", "")
        ):
            op_list = resource.operations.get_resource_operations(
                resource_el,
                ["monitor"]
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
                        reports.resource_managed_no_monitor_enabled(
                            resource_el.get("id", "")
                        )
                    )

        env.report_processor.process_list(report_list)

def group_add(
    env, group_id, resource_id_list, adjacent_resource_id=None,
    put_after_adjacent=True, wait=False
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

        validator = resource.relation.ValidateMoveResourcesToGroupByIds(
            group_id,
            resource_id_list,
            adjacent_resource_id=adjacent_resource_id
        )
        # raise on error
        env.report_processor.process_list(
            validator.validate(resources_section, id_provider)
        )

        # If we get no group element from the validator and there were no
        # errors, then the element does not exist and we can create it.
        group_element = validator.group_element()
        if group_element is None:
            group_element = resource.group.append_new(
                resources_section, group_id
            )

        resource.relation.move_resources_to_group(
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
            reports.prerequisite_option_is_missing("interval", "operation")
        )
    if interval is not None:
        report_items.extend(
            value_time_interval("interval")({"interval": interval})
        )
    if report_items:
        raise LibraryError(*report_items)

    interval_ms = (
        None if interval is None
        else timeout_to_seconds(interval) * 1000
    )

    all_failcounts = cib_status.get_resources_failcounts(
        get_status(env.get_cib())
    )
    return cib_status.filter_resources_failcounts(
        all_failcounts,
        resource=resource,
        node=node,
        operation=operation,
        interval=interval_ms
    )

def _find_resources_or_raise(
    context_element, resource_ids, additional_search=None, resource_tags=None
):
    report_list = []
    resource_el_list = resource.common.find_resources_and_report(
        context_element,
        resource_ids,
        report_list,
        additional_search=additional_search,
        resource_tags=resource_tags,
    )
    if report_list:
        raise LibraryError(*report_list)
    return resource_el_list
