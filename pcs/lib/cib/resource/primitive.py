from lxml import etree

from pcs.common import report_codes
from pcs.common.reports import ReportProcessor
from pcs.lib import reports
from pcs.lib.cib.nvpair import (
    append_new_instance_attributes,
    append_new_meta_attributes,
    get_value,
    get_nvset_as_dict,
)
from pcs.lib.cib.resource.operations import(
    prepare as prepare_operations,
    create_operations,
)
from pcs.lib.cib.tools import does_id_exist, find_element_by_tag_and_id
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id


TAG = "primitive"

def is_primitive(resource_el):
    return resource_el.tag == TAG


def find_primitives_by_agent(resources_section, resource_agent_obj):
    """
    Returns list of primitive resource elements which are using same resource
    agent as specified by resource_agent_obj.

    resources_section etree.Element -- element <resources/> from CIB
    resource_agent_obj pcs.lib.resource_agent.CrmAgent -- agent of which
        resources should be returned
    """
    provider = resource_agent_obj.get_provider()
    return resources_section.xpath(
        ".//primitive[@class='{_class}' and @type='{_type}'{_provider}]".format(
            _class=resource_agent_obj.get_standard(),
            _type=resource_agent_obj.get_type(),
            _provider=f" and @provider='{provider}'" if provider else "",
        )
    )


def create(
    report_processor: ReportProcessor,
    resources_section,
    id_provider,
    resource_id,
    resource_agent,
    raw_operation_list=None,
    meta_attributes=None,
    instance_attributes=None,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    resource_type="resource",
    do_not_report_instance_attribute_server_exists=False # TODO remove this arg
):
    # pylint: disable=too-many-arguments
    """
    Prepare all parts of primitive resource and append it into cib.

    report_processor is a tool for warning/info/error reporting
    etree.Element resources_section is place where new element will be appended
    IdProvider id_provider -- elements' ids generator
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
    string resource_type -- describes the resource for reports
    bool do_not_report_instance_attribute_server_exists -- dirty fix due to
        suboptimal architecture, TODO: fix the architecture and remove the param
    """
    if raw_operation_list is None:
        raw_operation_list = []
    if meta_attributes is None:
        meta_attributes = {}
    if instance_attributes is None:
        instance_attributes = {}

    if does_id_exist(resources_section, resource_id):
        raise LibraryError(reports.id_already_exists(resource_id))
    validate_id(resource_id, "{0} name".format(resource_type))

    operation_list = prepare_operations(
        report_processor,
        raw_operation_list,
        resource_agent.get_cib_default_actions(
            necessary_only=not use_default_operations
        ),
        [operation["name"] for operation in resource_agent.get_actions()],
        allow_invalid=allow_invalid_operation,
    )

    if report_processor.report_list(
        validate_resource_instance_attributes_create(
            resource_agent,
            instance_attributes,
            resources_section,
            force=allow_invalid_instance_attributes,
            do_not_report_instance_attribute_server_exists=(
                do_not_report_instance_attribute_server_exists
            )
        )
    ).has_errors:
        raise LibraryError()

    return append_new(
        resources_section,
        id_provider,
        resource_id,
        resource_agent.get_standard(),
        resource_agent.get_provider(),
        resource_agent.get_type(),
        instance_attributes=instance_attributes,
        meta_attributes=meta_attributes,
        operation_list=operation_list
    )

def append_new(
    resources_section, id_provider, resource_id, standard, provider, agent_type,
    instance_attributes=None,
    meta_attributes=None,
    operation_list=None
):
    # pylint:disable=too-many-arguments
    """
    Append a new primitive element to the resources_section.

    etree.Element resources_section is place where new element will be appended
    IdProvider id_provider -- elements' ids generator
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
    primitive_element = etree.SubElement(resources_section, TAG, attributes)

    if instance_attributes:
        append_new_instance_attributes(
            primitive_element,
            instance_attributes,
            id_provider
        )

    if meta_attributes:
        append_new_meta_attributes(
            primitive_element,
            meta_attributes,
            id_provider
        )

    create_operations(
        primitive_element,
        id_provider,
        operation_list if operation_list else []
    )

    return primitive_element


def validate_unique_instance_attributes(
    resource_agent, instance_attributes, resources_section,
    resource_id=None, force=False
):
    report_list = []
    report_creator = reports.get_problem_creator(
        report_codes.FORCE_OPTIONS, force
    )
    ra_unique_attributes = [
        param["name"]
        for param in resource_agent.get_parameters()
        if param["unique"]
    ]
    same_agent_resources = find_primitives_by_agent(
        resources_section, resource_agent
    )
    for attr in ra_unique_attributes:
        if attr not in instance_attributes:
            continue
        conflicting_resources = {
            primitive.get("id")
            for primitive in same_agent_resources
            if (
                primitive.get("id") != resource_id
                and
                instance_attributes[attr] == get_value(
                    "instance_attributes", primitive, attr
                )
            )
        }
        if conflicting_resources:
            report_list.append(
                report_creator(
                    reports.resource_instance_attr_value_not_unique,
                    attr,
                    instance_attributes[attr],
                    resource_agent.get_name(),
                    list(conflicting_resources),
                )
            )
    return report_list


def validate_resource_instance_attributes_create(
    resource_agent, instance_attributes, resources_section, force=False,
    do_not_report_instance_attribute_server_exists=False
):
    return (
        resource_agent.validate_parameters_create(
            instance_attributes, force=force,
            do_not_report_instance_attribute_server_exists=(
                do_not_report_instance_attribute_server_exists
            )
        )
        +
        validate_unique_instance_attributes(
            resource_agent, instance_attributes, resources_section, force=force
        )
    )


def validate_resource_instance_attributes_update(
    resource_agent, instance_attributes, resource_id, resources_section,
    force=False
):
    return (
        resource_agent.validate_parameters_update(
            get_nvset_as_dict(
                "instance_attributes",
                find_element_by_tag_and_id(
                    "primitive", resources_section, resource_id
                )
            ),
            instance_attributes,
            force=force,
        )
        +
        validate_unique_instance_attributes(
            resource_agent, instance_attributes, resources_section,
            resource_id=resource_id, force=force,
        )
    )
