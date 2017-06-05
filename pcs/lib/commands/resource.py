from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from contextlib import contextmanager
from functools import partial

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.cib import resource
from pcs.lib.cib.resource import operations, remote_node, guest_node
from pcs.lib.cib.tools import (
    find_element_by_tag_and_id,
    get_resources,
    IdProvider,
)
from pcs.lib.env_tools import get_nodes
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.pacemaker.state import (
    ensure_resource_state,
    is_resource_managed,
    ResourceNotFound,
)
from pcs.lib.resource_agent import(
    find_valid_resource_agent_by_name as get_agent
)

@contextmanager
def resource_environment(
    env, wait=False, wait_for_resource_ids=None, disabled_after_wait=False,
    required_cib_version=None
):
    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib(required_cib_version)
    yield get_resources(cib)
    env.push_cib(cib, wait)
    if wait is not False and wait_for_resource_ids:
        state = env.get_cluster_state()
        env.report_processor.process_list([
            ensure_resource_state(not disabled_after_wait, state, res_id)
            for res_id in wait_for_resource_ids
        ])

def _validate_remote_connection(
    resource_agent, nodes_to_validate_against, resource_id, instance_attributes,
    allow_not_suitable_command
):
    if resource_agent.get_name() != remote_node.AGENT_NAME.full_name:
        return []

    report_list = []
    report_list.append(
        reports.get_problem_creator(
            report_codes.FORCE_NOT_SUITABLE_COMMAND,
            allow_not_suitable_command
        )(reports.use_command_node_add_remote)
    )

    report_list.extend(
        remote_node.validate_host_not_conflicts(
            nodes_to_validate_against,
            resource_id,
            instance_attributes
        )
    )
    return report_list

def _validate_guest_change(
    tree, nodes_to_validate_against, meta_attributes,
    allow_not_suitable_command, detect_remove=False
):
    if not guest_node.is_node_name_in_options(meta_attributes):
        return []

    node_name = guest_node.get_node_name_from_options(meta_attributes)

    report_list = []
    create_report = reports.use_command_node_add_guest
    if detect_remove and not guest_node.get_guest_option_value(meta_attributes):
        create_report = reports.use_command_node_remove_guest

    report_list.append(
        reports.get_problem_creator(
            report_codes.FORCE_NOT_SUITABLE_COMMAND,
            allow_not_suitable_command
        )(create_report)
    )

    report_list.extend(
        guest_node.validate_conflicts(
            tree,
            nodes_to_validate_against,
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
        return get_nodes(tree=tree)

    return get_nodes(env.get_corosync_conf(), tree)


def _check_special_cases(
    env, resource_agent, resources_section, resource_id, meta_attributes,
    instance_attributes, allow_not_suitable_command
):
    if(
        resource_agent.get_name() != remote_node.AGENT_NAME.full_name
        and
        not guest_node.is_node_name_in_options(meta_attributes)
    ):
        #if no special case happens we won't take care about corosync.conf that
        #is needed for getting nodes to validate against
        return

    nodes_to_validate_against = _get_nodes_to_validate_against(
        env,
        resources_section
    )

    report_list = []
    report_list.extend(_validate_remote_connection(
        resource_agent,
        nodes_to_validate_against,
        resource_id,
        instance_attributes,
        allow_not_suitable_command,
    ))
    report_list.extend(_validate_guest_change(
        resources_section,
        nodes_to_validate_against,
        meta_attributes,
        allow_not_suitable_command,
    ))

    env.report_processor.process_list(report_list)

def create(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
):
    """
    Create resource in a cib.

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operations contains attributes for each entered operation
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
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
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
        ensure_disabled or resource.common.are_meta_disabled(meta_attributes),
    ) as resources_section:
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
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element)

def _create_as_clone_common(
    tag, env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes, clone_meta_options,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
):
    """
    Create resource in some kind of clone (clone or master).

    Currently the only difference between commands "create_as_clone" and
    "create_as_master" is in tag. So the commands create_as_clone and
    create_as_master are created by passing tag with partial.

    string tag is any clone tag. Currently it can be "clone" or "master".
    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operations contains attributes for each entered operation
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
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
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
        (
            ensure_disabled
            or
            resource.common.are_meta_disabled(meta_attributes)
            or
            resource.common.is_clone_deactivated_by_meta(clone_meta_options)
        )
    ) as resources_section:
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
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        clone_element = resource.clone.append_new(
            tag,
            resources_section,
            primitive_element,
            clone_meta_options,
        )
        if ensure_disabled:
            resource.common.disable(clone_element)

def create_in_group(
    env, resource_id, resource_agent_name, group_id,
    operations, meta_attributes, instance_attributes,
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
    """
    Create resource in a cib and put it into defined group

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    string group_id is identificator for group to put primitive resource inside
    list of dict operations contains attributes for each entered operation
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
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
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
        ensure_disabled or resource.common.are_meta_disabled(meta_attributes),
    ) as resources_section:
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
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element)
        validate_id(group_id, "group name")
        resource.group.place_resource(
            resource.group.provide_group(resources_section, group_id),
            primitive_element,
            adjacent_resource_id,
            put_after_adjacent,
        )

create_as_clone = partial(_create_as_clone_common, resource.clone.TAG_CLONE)
create_as_master = partial(_create_as_clone_common, resource.clone.TAG_MASTER)

def create_into_bundle(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes,
    bundle_id,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
    allow_not_suitable_command=False,
):
    """
    Create a new resource in a cib and put it into an existing bundle

    LibraryEnvironment env provides all for communication with externals
    string resource_id is identifier of resource
    string resource_agent_name contains name for the identification of agent
    list of dict operations contains attributes for each entered operation
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
    mixed wait is flag for controlling waiting for pacemaker iddle mechanism
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
        disabled_after_wait=ensure_disabled,
        required_cib_version=(2, 8, 0)
    ) as resources_section:
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
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element)
        resource.bundle.add_resource(
            find_element_by_tag_and_id(
                "bundle", resources_section, bundle_id
            ),
            primitive_element
        )

def bundle_create(
    env, bundle_id, container_type, container_options=None,
    network_options=None, port_map=None, storage_map=None,
    force_options=False,
    wait=False,
):
    """
    Create a new bundle containing no resources

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the new bundle
    string container_type -- container engine name (docker, lxc...)
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- list of port mapping options
    list of dict storage_map -- list of storage mapping options
    bool force_options -- return warnings instead of forceable errors
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    container_options = container_options or {}
    network_options = network_options or {}
    port_map = port_map or []
    storage_map = storage_map or []

    with resource_environment(
        env,
        wait,
        [bundle_id],
        # bundles are always enabled, currently there is no way to disable them
        disabled_after_wait=False,
        required_cib_version=(2, 8, 0)
    ) as resources_section:
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
                force_options
            )
        )
        resource.bundle.append_new(
            resources_section,
            id_provider,
            bundle_id,
            container_type,
            container_options,
            network_options,
            port_map,
            storage_map
        )

def bundle_update(
    env, bundle_id, container_options=None, network_options=None,
    port_map_add=None, port_map_remove=None, storage_map_add=None,
    storage_map_remove=None,
    force_options=False,
    wait=False,
):
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
    bool force_options -- return warnings instead of forceable errors
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    container_options = container_options or {}
    network_options = network_options or {}
    port_map_add = port_map_add or []
    port_map_remove = port_map_remove or []
    storage_map_add = storage_map_add or []
    storage_map_remove = storage_map_remove or []

    with resource_environment(
        env,
        wait,
        [bundle_id],
        # bundles are always enabled, currently there is no way to disable them
        disabled_after_wait=False,
        required_cib_version=(2, 8, 0)
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        bundle_element = find_element_by_tag_and_id(
            resource.bundle.TAG,
            resources_section,
            bundle_id
        )
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
            storage_map_remove
        )

def disable(env, resource_ids, wait):
    """
    Disallow specified resource to be started by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to be disabled
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    with resource_environment(
        env, wait, resource_ids, True
    ) as resources_section:
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids
        )
        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                resource.common.disable,
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
        env, wait, resource_ids, False
    ) as resources_section:
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_enable
        )
        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                resource.common.enable,
                env.get_cluster_state()
            )
        )

def _resource_list_enable_disable(resource_el_list, func, cluster_state):
    report_list = []
    for resource_el in resource_el_list:
        res_id = resource_el.attrib["id"]
        try:
            if not is_resource_managed(cluster_state, res_id):
                report_list.append(reports.resource_is_unmanaged(res_id))
            func(resource_el)
        except ResourceNotFound:
            report_list.append(
                reports.id_not_found(
                    res_id,
                    id_description="resource/clone/master/group/bundle"
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
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_unmanage
        )
        primitives = []

        for resource_el in resource_el_list:
            resource.common.unmanage(resource_el)
            if with_monitor:
                primitives.extend(
                    resource.common.find_primitives(resource_el)
                )

        for resource_el in set(primitives):
            for op in operations.get_resource_operations(
                resource_el,
                ["monitor"]
            ):
                operations.disable(op)

def manage(env, resource_ids, with_monitor=False):
    """
    Set specified resource to be managed by the cluster
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to become managed
    bool with_monitor -- enable resources' monitor operations
    """
    with resource_environment(env) as resources_section:
        report_list = []
        resource_el_list = _find_resources_or_raise(
            resources_section,
            resource_ids,
            resource.common.find_resources_to_manage
        )
        primitives = []

        for resource_el in resource_el_list:
            resource.common.manage(resource_el)
            primitives.extend(
                resource.common.find_primitives(resource_el)
            )

        for resource_el in sorted(
            set(primitives),
            key=lambda element: element.get("id", "")
        ):
            op_list = operations.get_resource_operations(
                resource_el,
                ["monitor"]
            )
            if with_monitor:
                for op in op_list:
                    operations.enable(op)
            else:
                monitor_enabled = False
                for op in op_list:
                    if operations.is_enabled(op):
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

def _find_resources_or_raise(
    resources_section, resource_ids, additional_search=None
):
    if not additional_search:
        additional_search = lambda x: [x]
    report_list = []
    resource_el_list = []
    resource_tags = (
        resource.clone.ALL_TAGS
        +
        [resource.group.TAG, resource.primitive.TAG, resource.bundle.TAG]
    )
    for res_id in resource_ids:
        try:
            resource_el_list.extend(
                additional_search(
                    find_element_by_tag_and_id(
                        resource_tags,
                        resources_section,
                        res_id,
                        id_description="resource/clone/master/group/bundle"
                    )
                )
            )
        except LibraryError as e:
            report_list.extend(e.args)
    if report_list:
        raise LibraryError(*report_list)
    return resource_el_list
