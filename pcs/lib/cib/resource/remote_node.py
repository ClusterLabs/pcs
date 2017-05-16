from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports, validate
from pcs.lib.cib.resource import primitive
from pcs.lib.node import(
    NodeAddresses,
    node_addresses_contain_host,
    node_addresses_contain_name,
)
from pcs.lib.resource_agent import find_valid_resource_agent_by_name

AGENT_NAME = "ocf:pacemaker:remote"

def find_node_list(resources_section):
    node_list = [
        NodeAddresses(
            nvpair.attrib["value"],
            name=nvpair.getparent().getparent().attrib["id"]
        )
        for nvpair in resources_section.xpath("""
            .//primitive[
                @class="ocf"
                and
                @provider="pacemaker"
                and
                @type="remote"
            ]
            /instance_attributes
            /nvpair[@name="server" and string-length(@value) > 0]
        """)
    ]

    node_list.extend([
        NodeAddresses(primitive.attrib["id"], name=primitive.attrib["id"])
        for primitive in resources_section.xpath("""
            .//primitive[
                @class="ocf"
                and
                @provider="pacemaker"
                and
                @type="remote"
                and
                not(
                    instance_attributes/nvpair[
                        @name="server"
                        and
                        string-length(@value) > 0
                    ]
                )
            ]
        """)
    ])

    return node_list

def find_node_resources(resources_section, node_identifier):
    """
    Return list of resource elements that match to node_identifier

    etree.Element resources_section is a search element
    string node_identifier could be id of the resource or its instance attribute
        "server"
    """
    return resources_section.xpath("""
        .//primitive[
            @class="ocf"
            and
            @provider="pacemaker"
            and
            @type="remote"
            and (
                @id="{0}"
                or
                instance_attributes/nvpair[@name="server" and @value="{0}"]
            )
        ]
    """.format(node_identifier))

def get_host(resource_element):
    """
    Return first host from resource element if is there. Return None if host is
    not there.

    etree.Element resource_element
    """
    if not (
        resource_element.attrib["class"] == "ocf"
        and
        resource_element.attrib["provider"] == "pacemaker"
        and
        resource_element.attrib["type"] == "remote"
    ):
        return None


    host_list = resource_element.xpath("""
        ./instance_attributes/nvpair[
            @name="server"
            and
            string-length(@value) > 0
        ]
        /@value
    """)
    if host_list:
        return host_list[0]
    return resource_element.attrib["id"]

def validate_host_not_ambiguous(instance_attributes, host):
    if instance_attributes.get("server", host) != host:
        return [
            reports.ambiguous_host_specification(
                [
                    host,
                    instance_attributes["server"]
                ]
            )
        ]
    return []

def validate_pcmk_remote_host_not_used(option_name, nodes):
    def validate(option_dict):
        if(
            option_name in option_dict
            and
            node_addresses_contain_host(nodes, option_dict[option_name])
        ):
            return [reports.id_already_exists(option_dict[option_name])]
        return []
    return validate

def validate_host_not_conflicts(nodes, node_name, instance_attributes):
    host = instance_attributes.get("server", node_name)
    if node_addresses_contain_host(nodes, host):
        return [reports.id_already_exists(host)]
    return []

def validate_parts(nodes, node_name, instance_attributes):
    """
    validate inputs for create

    list of NodeAddresses nodes -- nodes already used
    string node_name -- name of future node
    dict instance_attributes -- data for future resource instance attributes
    """
    validator_list = [
        validate.is_required("server", "remote node"),
        validate_pcmk_remote_host_not_used("server", nodes)
    ]
    report_list = []
    report_list.extend(validate.run_collection_of_option_validators(
        instance_attributes,
        validator_list
    ))
    if node_addresses_contain_name(nodes, node_name):
        report_list.append(reports.id_already_exists(node_name))
    return report_list

def prepare_instance_atributes(instance_attributes, host):
    enriched_instance_attributes = instance_attributes.copy()
    enriched_instance_attributes["server"] = host
    return enriched_instance_attributes

def create(
    report_processor, cmd_runner, resources_section, node_name,
    raw_operation_list=None, meta_attributes=None,
    instance_attributes=None,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
):
    """
    Prepare all parts of remote resource and append it into the cib.

    report_processor is a tool for warning/info/error reporting
    cmd_runner is tool for launching external commands
    etree.Element resources_section is place where new element will be appended
    string node_name is name of the remote node and id of new resource as well
    list of dict raw_operation_list specifies operations of resource
    dict meta_attributes specifies meta attributes of resource
    dict instance_attributes specifies instance attributes of resource
    bool allow_invalid_operation is flag for skipping validation of operations
    bool allow_invalid_instance_attributes is flag for skipping validation of
        instance_attributes
    bool use_default_operations is flag for completion operations with default
        actions specified in resource agent
    """
    return primitive.create(
        report_processor,
        resources_section,
        node_name,
        find_valid_resource_agent_by_name(
            report_processor,
            cmd_runner,
            AGENT_NAME,
        ),
        raw_operation_list,
        meta_attributes,
        instance_attributes,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
    )
