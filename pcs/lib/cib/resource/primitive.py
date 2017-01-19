from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.nvpair import (
    append_new_instance_attributes,
    append_new_meta_attributes,
)
from pcs.lib.cib.resource.common import disable_meta
from pcs.lib.cib.resource.operations import(
    prepare as prepare_operations,
    create_operations,
)
from pcs.lib.cib.tools import does_id_exist
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id


TAG = "primitive"

def create(
    report_processor, resources_section, resource_id, resource_agent,
    raw_operation_list, meta_attributes, instance_attributes,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
):
    """
    Prepare all parts of primitive resource and push it to cib.

    report_processor is a tool for warning/info/error reporting
    etree.Element resources_section is place where new element will be appended
    string resource_id is id of new resource
    lib.resource_agent.CrmAgent resource_agent
    list of dict raw_operation_list specifies operations of resource
    dict meta_attributes specifies meta attributes of resource
    dict instance_attributes specifies instance attributes of resource
    bool allow_invalid_operation is flag for skipping validation of operations
    bool allow_invalid_instance_attributes is flag for skipping validation of
        instance_attributes
    bool use_default_operations is flag for completion operations with default
        actions specified in resource agent
    bool ensure_disabled is flag for completion meta_attributes with attribute
        causing disabling resource
    """
    if does_id_exist(resources_section, resource_id):
        raise LibraryError(reports.id_already_exists(resource_id))
    validate_id(resource_id, "resource name")

    operation_list = prepare_operations(
        report_processor,
        raw_operation_list,
        resource_agent.get_cib_default_actions(
            necessary_only=not use_default_operations
        ),
        [operation["name"] for operation in resource_agent.get_actions()],
        allow_invalid=allow_invalid_operation,
    )

    if ensure_disabled:
        meta_attributes = disable_meta(meta_attributes)

    report_processor.process_list(
        resource_agent.validate_parameters(
            instance_attributes,
            parameters_type="resource option",
            allow_invalid=allow_invalid_instance_attributes,
        )
    )

    return append_new(
        resources_section,
        resource_id,
        resource_agent.get_standard(),
        resource_agent.get_type(),
        resource_agent.get_provider(),
        instance_attributes=instance_attributes,
        meta_attributes=meta_attributes,
        operation_list=operation_list
    )

def append_new(
    resources_section, resource_id, standard, agent_type,
    provider=None,
    instance_attributes=None,
    meta_attributes=None,
    operation_list=None
):
    """
    Append a new primitive element to the resources_section.

    etree.Element resources_section is place where new element will be appended
    string resource_id is id of new resource
    string standard is a standard of resource agent (e.g. ocf)
    string agent_type is a type of resource agent (e.g. IPaddr2)
    string provider is a provider of resource agent (e.g. heartbeat)
    dict instance_attributes will be nvpairs inside instance_attributes element
    dict meta_attributes will be nvpairs inside meta_attributes element
    list operation_list contains dicts representing operations
        (e.g. [{"name": "monitor"}, {"name": "start"}])
    """
    attributes = {
        "id": resource_id,
        "class": standard,
        "type": agent_type,
    }
    if provider:
        attributes["provider"] = provider
    primitive_element = etree.SubElement(
        resources_section,
        "primitive",
        attributes
    )

    if instance_attributes:
        append_new_instance_attributes(
            primitive_element,
            instance_attributes
        )

    if meta_attributes:
        append_new_meta_attributes(primitive_element, meta_attributes)

    create_operations(
        primitive_element,
        operation_list if operation_list else []
    )

    return primitive_element
