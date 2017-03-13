from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from contextlib import contextmanager
from functools import partial

from pcs.lib import reports
from pcs.lib.cib import resource
from pcs.lib.cib.resource.common import (
    are_meta_disabled,
    disable as disable_resource,
    disable_meta,
    enable as enable_resource,
    find_resources_to_enable,
    is_clone_deactivated_by_meta,
)
from pcs.lib.cib.resource.clone import ALL_TAGS as TAGS_CLONE
from pcs.lib.cib.resource.group import TAG as TAG_GROUP
from pcs.lib.cib.resource.primitive import TAG as TAG_PRIMITIVE
from pcs.lib.cib.tools import (
    find_element_by_tag_and_id,
    get_resources,
)
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
def resource_environment(env, resource_ids, wait, disabled_after_wait):
    env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    yield get_resources(cib)
    env.push_cib(cib, wait)
    if wait is not False:
        state = env.get_cluster_state()
        env.report_processor.process_list([
            ensure_resource_state( not disabled_after_wait, state, res_id)
            for res_id in resource_ids
        ])

def create(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
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
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(
        env, [resource_id], wait,
        ensure_disabled or are_meta_disabled(meta_attributes),
    ) as resources_section:
        resource.primitive.create(
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            ensure_disabled,
        )

def _create_as_clone_common(
    tag, env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes, clone_meta_options,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
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
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(env, [resource_id], wait, (
        ensure_disabled
        or
        are_meta_disabled(meta_attributes)
        or
        is_clone_deactivated_by_meta(clone_meta_options)
    )) as resources_section:
        primitive_element = resource.primitive.create(
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )

        if ensure_disabled:
            clone_meta_options = disable_meta(clone_meta_options)

        resource.clone.append_new(
            tag,
            resources_section,
            primitive_element,
            clone_meta_options,
        )

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
    """
    resource_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        resource_agent_name,
        allow_absent_agent,
    )
    with resource_environment(
        env, [resource_id], wait,
        ensure_disabled or are_meta_disabled(meta_attributes),
    ) as resources_section:
        primitive_element = resource.primitive.create(
            env.report_processor, resources_section,
            resource_id, resource_agent,
            operations, meta_attributes, instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            ensure_disabled,
        )
        validate_id(group_id, "group name")
        resource.group.place_resource(
            resource.group.provide_group(resources_section, group_id),
            primitive_element,
            adjacent_resource_id,
            put_after_adjacent,
        )

create_as_clone = partial(_create_as_clone_common, resource.clone.TAG_CLONE)
create_as_master = partial(_create_as_clone_common, resource.clone.TAG_MASTER)

def disable(env, resource_ids, wait):
    """
    Disable specified resources in the CIB.
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to be disabled
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    with resource_environment(
        env, resource_ids, wait, True
    ) as resources_section:
        report_list = []
        resource_el_list = []
        for res_id in resource_ids:
            try:
                resource_el_list.append(
                    _find_any_resource(resources_section, res_id)
                )
            except LibraryError as e:
                report_list.extend(e.args)
        env.report_processor.process_list(report_list)

        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                disable_resource,
                env.get_cluster_state()
            )
        )

def enable(env, resource_ids, wait):
    """
    Enable specified resource in the CIB.
    LibraryEnvironment env --
    strings resource_ids -- ids of the resources to be enabled
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    with resource_environment(
        env, resource_ids, wait, False
    ) as resources_section:
        report_list = []
        resource_el_list = []
        for res_id in resource_ids:
            try:
                resource_el_list.extend(
                    find_resources_to_enable(
                        _find_any_resource(resources_section, res_id)
                    )
                )
            except LibraryError as e:
                report_list.extend(e.args)
        env.report_processor.process_list(report_list)

        env.report_processor.process_list(
            _resource_list_enable_disable(
                resource_el_list,
                enable_resource,
                env.get_cluster_state()
            )
        )

_find_any_resource = partial(
    find_element_by_tag_and_id,
    TAGS_CLONE + [TAG_GROUP, TAG_PRIMITIVE],
    id_description="resource/clone/master/group"
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
                    id_description="resource/clone/master/group"
               )
            )
    return report_list
