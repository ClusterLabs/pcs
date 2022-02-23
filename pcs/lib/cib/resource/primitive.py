from typing import (
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.cib.nvpair import (
    INSTANCE_ATTRIBUTES_TAG,
    append_new_instance_attributes,
    append_new_meta_attributes,
    get_nvset_as_dict,
    get_value,
)
from pcs.lib.cib.resource.agent import get_default_operations
from pcs.lib.cib.resource.operations import create_operations
from pcs.lib.cib.resource.operations import prepare as prepare_operations
from pcs.lib.cib.resource.types import ResourceOperationIn
from pcs.lib.cib.tools import (
    IdProvider,
    are_new_role_names_supported,
    does_id_exist,
    find_element_by_tag_and_id,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.resource_agent import (
    ResourceAgentFacade,
    ResourceAgentMetadata,
    ResourceAgentName,
)
from pcs.lib.resource_agent.const import STONITH_ACTION_REPLACED_BY

TAG = "primitive"


def is_primitive(resource_el):
    return resource_el.tag == TAG


def _find_primitives_by_agent(
    resources_section: _Element, agent_name: ResourceAgentName
) -> List[_Element]:
    """
    Returns list of primitive resource elements which are using same resource
    agent as specified by resource_agent_obj.

    resources_section -- element <resources/> from CIB
    agent_name -- name of an agent resources of which should be returned
    """
    return cast(
        List[_Element],
        resources_section.xpath(
            ".//primitive[@class=$class_ and @type=$type_ {provider_part}]".format(
                provider_part=" and @provider=$provider_"
                if agent_name.provider
                else "",
            ),
            class_=agent_name.standard,
            provider_=agent_name.provider or "",
            type_=agent_name.type,
        ),
    )


def create(
    report_processor: reports.ReportProcessor,
    resources_section: _Element,
    id_provider: IdProvider,
    resource_id: str,
    resource_agent_facade: ResourceAgentFacade,
    raw_operation_list: Optional[Iterable[ResourceOperationIn]] = None,
    meta_attributes: Optional[Mapping[str, str]] = None,
    instance_attributes: Optional[Mapping[str, str]] = None,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    resource_type: str = "resource",
    # TODO remove this arg
    do_not_report_instance_attribute_server_exists: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Prepare all parts of primitive resource and append it into cib.

    report_processor -- a tool for warning/info/error reporting
    resources_section -- a place where the new resource will be appended
    id_provider -- elements' ids generator
    resource_id -- id of the new resource
    resource_agent_facade -- resource agent
    raw_operation_list -- specifies operations of the resource
    meta_attributes -- specifies meta attributes of the resource
    instance_attributes -- specifies instance attributes of the resource
    allow_invalid_operation -- flag for skipping validation of operations
    allow_invalid_instance_attributes -- flag for skipping validation of
        instance_attributes
    use_default_operations -- flag for completion operations with default
        actions specified in resource agent
    resource_type -- describes the resource for reports
    do_not_report_instance_attribute_server_exists -- dirty fix due to
        suboptimal architecture, TODO: fix the architecture and remove the param
    """
    if raw_operation_list is None:
        raw_operation_list = []
    if meta_attributes is None:
        meta_attributes = {}
    if instance_attributes is None:
        instance_attributes = {}

    filtered_raw_operation_list = []
    for op in raw_operation_list:
        filtered_raw_operation_list.append(
            {name: "" if value is None else value for name, value in op.items()}
        )

    if does_id_exist(resources_section, resource_id):
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.IdAlreadyExists(resource_id)
            )
        )
    validate_id(resource_id, "{0} name".format(resource_type))

    agent_metadata = resource_agent_facade.metadata

    operation_list = prepare_operations(
        report_processor,
        filtered_raw_operation_list,
        get_default_operations(
            agent_metadata, necessary_only=not use_default_operations
        ),
        [operation.name for operation in agent_metadata.actions],
        are_new_role_names_supported(resources_section),
        allow_invalid=allow_invalid_operation,
    )

    report_items = validate_resource_instance_attributes_create(
        resource_agent_facade,
        instance_attributes,
        resources_section,
        force=allow_invalid_instance_attributes,
    )
    # TODO remove this "if", see pcs.lib.cib.remote_node.create for details
    if do_not_report_instance_attribute_server_exists:
        for report_item in report_items:
            if isinstance(report_item.message, reports.messages.InvalidOptions):
                report_msg = cast(
                    reports.messages.InvalidOptions, report_item.message
                )
                report_item.message = reports.messages.InvalidOptions(
                    report_msg.option_names,
                    sorted(
                        [
                            value
                            for value in report_msg.allowed
                            if value != "server"
                        ]
                    ),
                    report_msg.option_type,
                    report_msg.allowed_patterns,
                )
    report_processor.report_list(report_items)

    if report_processor.has_errors:
        raise LibraryError()

    return append_new(
        resources_section,
        id_provider,
        resource_id,
        agent_metadata.name.standard,
        agent_metadata.name.provider,
        agent_metadata.name.type,
        instance_attributes=instance_attributes,
        meta_attributes=meta_attributes,
        operation_list=operation_list,
    )


def append_new(
    resources_section,
    id_provider,
    resource_id,
    standard,
    provider,
    agent_type,
    instance_attributes=None,
    meta_attributes=None,
    operation_list=None,
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
            primitive_element, instance_attributes, id_provider
        )

    if meta_attributes:
        append_new_meta_attributes(
            primitive_element, meta_attributes, id_provider
        )

    create_operations(
        primitive_element, id_provider, operation_list if operation_list else []
    )

    return primitive_element


def _validate_unique_instance_attributes(
    resource_agent: ResourceAgentMetadata,
    instance_attributes: Mapping[str, str],
    resources_section: _Element,
    resource_id: Optional[str] = None,
    force: bool = False,
) -> reports.ReportItemList:
    if not resource_agent.unique_parameter_groups:
        return []

    report_list = []
    same_agent_resources = _find_primitives_by_agent(
        resources_section, resource_agent.name
    )

    for (
        group_name,
        group_attrs,
    ) in resource_agent.unique_parameter_groups.items():
        new_group_values_map = {
            name: instance_attributes.get(name, "") for name in group_attrs
        }
        if not any(new_group_values_map.values()):
            continue

        conflicting_resources: Set[str] = set()
        for primitive in same_agent_resources:
            if primitive.attrib["id"] == resource_id:
                continue
            existing_group_values_map = {
                name: get_value(INSTANCE_ATTRIBUTES_TAG, primitive, name, "")
                for name in group_attrs
            }
            if new_group_values_map == existing_group_values_map:
                conflicting_resources.add(str(primitive.attrib["id"]))

        if conflicting_resources:
            if len(new_group_values_map) == 1:
                message: reports.item.ReportItemMessage = (
                    reports.messages.ResourceInstanceAttrValueNotUnique(
                        *new_group_values_map.popitem(),
                        resource_agent.name.full_name,
                        sorted(conflicting_resources),
                    )
                )
            else:
                message = (
                    reports.messages.ResourceInstanceAttrGroupValueNotUnique(
                        group_name,
                        new_group_values_map,
                        resource_agent.name.full_name,
                        sorted(conflicting_resources),
                    )
                )
            report_list.append(
                reports.ReportItem(
                    reports.item.get_severity(reports.codes.FORCE, force),
                    message,
                )
            )
    return report_list


def validate_resource_instance_attributes_create(
    resource_agent: ResourceAgentFacade,
    instance_attributes: Mapping[str, str],
    resources_section: _Element,
    force: bool = False,
) -> reports.ReportItemList:
    report_items: reports.ReportItemList = []
    report_items += validate.ValidatorAll(
        [validate.ValueNotEmpty(name, None) for name in instance_attributes]
    ).validate(instance_attributes)
    if resource_agent.metadata.agent_exists:
        report_items += validate.ValidatorAll(
            resource_agent.get_validators_allowed_parameters(force)
            + resource_agent.get_validators_required_parameters(force)
        ).validate(instance_attributes)
        report_items += validate.ValidatorAll(
            resource_agent.get_validators_deprecated_parameters()
        ).validate(
            {
                name: value
                for name, value in instance_attributes.items()
                # we create a custom report for stonith parameter "action"
                if not (
                    resource_agent.metadata.name.is_stonith and name == "action"
                )
            }
        )

    if resource_agent.metadata.name.is_stonith:
        report_items += _validate_stonith_action(instance_attributes, force)

    if resource_agent.metadata.agent_exists:
        report_items += _validate_unique_instance_attributes(
            resource_agent.metadata,
            instance_attributes,
            resources_section,
            force=force,
        )
    return report_items


def validate_resource_instance_attributes_update(
    resource_agent: ResourceAgentFacade,
    instance_attributes: Mapping[str, str],
    resource_id: str,
    resources_section: _Element,
    force: bool = False,
) -> reports.ReportItemList:
    # TODO This function currently accepts the updated resource as a string and
    # finds the corresponding xml element by itself. This is needed as the
    # function is called from old pcs code which uses dom while pcs.lib uses
    # lxml. Once resource update command is moved to pcs.lib, this function
    # will be fixed to accept the updated resource as an element instead of a
    # string.
    report_items: reports.ReportItemList = []
    current_instance_attrs = get_nvset_as_dict(
        INSTANCE_ATTRIBUTES_TAG,
        find_element_by_tag_and_id(TAG, resources_section, resource_id),
    )

    if resource_agent.metadata.agent_exists:
        report_items += validate.ValidatorAll(
            resource_agent.get_validators_allowed_parameters(force)
        ).validate(
            # Do not report unknown parameters already set in the CIB. It would
            # be confusing to report an error in an option not actually created
            # now.
            {
                name: value
                for name, value in instance_attributes.items()
                if name not in current_instance_attrs
            }
        )
        report_items += validate.ValidatorAll(
            resource_agent.get_validators_deprecated_parameters()
        ).validate(
            {
                name: value
                for name, value in instance_attributes.items()
                # Allow removing deprecated parameters
                if value != ""
                # we create a custom report for stonith parameter "action"
                and not (
                    resource_agent.metadata.name.is_stonith and name == "action"
                )
            }
        )

        # Check that required parameters have not been removed. This is
        # complicated by two facts:
        # * parameters may by deprecated by other parameters, setting one
        #   required parameter from such group is enough
        # * we only want to report errors related to attributes to be updated
        final_attrs = dict(current_instance_attrs)
        for name, value in instance_attributes.items():
            if value == "":
                final_attrs.pop(name, None)
            else:
                final_attrs[name] = value
        report_items += validate.ValidatorAll(
            # Limit validation only to parameters entered now in an update
            # command. We don't want to report missing parameters not mentioned
            # in a command now, that would be confusing to users.
            resource_agent.get_validators_required_parameters(
                force, only_parameters=instance_attributes.keys()
            )
        ).validate(final_attrs)

    if resource_agent.metadata.name.is_stonith:
        report_items += _validate_stonith_action(instance_attributes, force)

    if resource_agent.metadata.agent_exists:
        report_items += _validate_unique_instance_attributes(
            resource_agent.metadata,
            instance_attributes,
            resources_section,
            resource_id=resource_id,
            force=force,
        )
    return report_items


def _validate_stonith_action(
    instance_attributes: Mapping[str, str], force: bool = False
) -> reports.ReportItemList:
    if instance_attributes.get("action"):
        return [
            reports.ReportItem(
                reports.item.get_severity(reports.codes.FORCE, force),
                reports.messages.DeprecatedOption(
                    "action", sorted(STONITH_ACTION_REPLACED_BY), "stonith"
                ),
            )
        ]
    return []
