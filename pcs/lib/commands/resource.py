from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib import resource
from pcs.lib.cib.resource.common import disable_meta
from pcs.lib.cib.tools import get_resources
from pcs.lib.pacemaker.values import validate_id


def create(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    master=False
):
    cib = env.get_cib()
    resources_section = get_resources(cib)
    resource.primitive.create(
        env.report_processor, env.cmd_runner(), resources_section,
        resource_id, resource_agent_name,
        operations, meta_attributes, instance_attributes,
        allow_absent_agent,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
        ensure_disabled,
        master=master
    )
    env.push_cib(cib)

def create_as_master(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes, master_meta_options,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    master=False
):
    meta_attributes = {}
    cib = env.get_cib()
    resources_section = get_resources(cib)
    primitive_element = resource.primitive.create(
        env.report_processor, env.cmd_runner(), resources_section,
        resource_id, resource_agent_name,
        operations, meta_attributes, instance_attributes,
        allow_absent_agent,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
        master=True
    )

    if ensure_disabled:
        master_meta_options = disable_meta(master_meta_options)

    resource.clone.append_new_master(
        resources_section,
        primitive_element,
        master_meta_options,
    )
    env.push_cib(cib)

def create_as_clone(
    env, resource_id, resource_agent_name,
    operations, meta_attributes, instance_attributes, clone_options,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    master=False,
):
    cib = env.get_cib()
    resources_section = get_resources(cib)
    primitive_element = resource.primitive.create(
        env.report_processor, env.cmd_runner(), resources_section,
        resource_id, resource_agent_name,
        operations, meta_attributes, instance_attributes,
        allow_absent_agent,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
        ensure_disabled,
        master=master
    )
    resource.clone.append_new_clone(
        resources_section,
        primitive_element,
        clone_options,
    )
    env.push_cib(cib)

def create_in_group(
    env, resource_id, resource_agent_name, group_id,
    operations, meta_attributes, instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    master=False,
    adjacent_resource_id=None,
    put_after_adjacent=False,
):
    cib = env.get_cib()
    resources_section = get_resources(cib)
    primitive_element = resource.primitive.create(
        env.report_processor, env.cmd_runner(), resources_section,
        resource_id, resource_agent_name,
        operations, meta_attributes, instance_attributes,
        allow_absent_agent,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
        ensure_disabled,
        master=master
    )
    validate_id(group_id, "group name")
    resource.group.place_resource(
        resource.group.provide_group(resources_section, group_id),
        primitive_element,
        adjacent_resource_id,
        put_after_adjacent,
    )

    env.push_cib(cib)
