from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports
from pcs.lib.cib.resource import primitive
from pcs.lib.node import NodeAddresses
from pcs.lib.resource_agent import find_valid_resource_agent_by_name

def find_node_list(resources_section):
    return [
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

def find_node_resources(resources_section, node_identifier):
    """
    Return list of resource elements that match to node_identifier

    etree.Element resources_section is a researched element
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
    host_list = resource_element.xpath("""
        ./instance_attributes
        /nvpair[
            @name="server"
            and
            string-length(@value) > 0
        ]
        /@value
    """)
    return host_list[0] if host_list else None

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
            "ocf:pacemaker:remote",
        ),
        raw_operation_list,
        meta_attributes,
        instance_attributes,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
    )
