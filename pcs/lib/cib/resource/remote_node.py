from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.cib.resource import primitive
from pcs.lib.node import(
    NodeAddresses,
    node_addresses_contain_host,
    node_addresses_contain_name,
)
from pcs.lib.resource_agent import(
    find_valid_resource_agent_by_name,
    ResourceAgentName,
)

AGENT_NAME = ResourceAgentName("ocf", "pacemaker", "remote")

def get_agent(report_processor, cmd_runner):
    return find_valid_resource_agent_by_name(
        report_processor,
        cmd_runner,
        AGENT_NAME.full_name,
    )

_IS_REMOTE_AGENT_XPATH_SNIPPET = """
    @class="{0}" and @provider="{1}" and @type="{2}"
""".format(AGENT_NAME.standard, AGENT_NAME.provider, AGENT_NAME.type)

_HAS_SERVER_XPATH_SNIPPET = """
    instance_attributes/nvpair[
        @name="server"
        and
        string-length(@value) > 0
    ]
"""



def find_node_list(resources_section):
    node_list = [
        NodeAddresses(
            nvpair.attrib["value"],
            name=nvpair.getparent().getparent().attrib["id"]
        )
        for nvpair in resources_section.xpath(
            ".//primitive[{is_remote}]/{has_server}"
            .format(
                is_remote=_IS_REMOTE_AGENT_XPATH_SNIPPET,
                has_server=_HAS_SERVER_XPATH_SNIPPET,
            )
        )
    ]

    node_list.extend([
        NodeAddresses(primitive.attrib["id"], name=primitive.attrib["id"])
        for primitive in resources_section.xpath(
            ".//primitive[{is_remote} and not({has_server})]"
            .format(
                is_remote=_IS_REMOTE_AGENT_XPATH_SNIPPET,
                has_server=_HAS_SERVER_XPATH_SNIPPET,
            )
        )
    ])

    return node_list

def find_node_resources(resources_section, node_identifier):
    """
    Return list of resource elements that match to node_identifier

    etree.Element resources_section is a search element
    string node_identifier could be id of the resource or its instance attribute
        "server"
    """
    return resources_section.xpath(
        """
            .//primitive[
                {is_remote} and (
                    @id="{identifier}"
                    or
                    instance_attributes/nvpair[
                        @name="server"
                        and
                        @value="{identifier}"
                    ]
                )
            ]
        """
        .format(
            is_remote=_IS_REMOTE_AGENT_XPATH_SNIPPET,
            identifier=node_identifier
        )
    )

def get_host(resource_element):
    """
    Return first host from resource element if is there. Return None if host is
    not there.

    etree.Element resource_element
    """
    if not (
        resource_element.attrib["class"] == AGENT_NAME.standard
        and
        resource_element.attrib["provider"] == AGENT_NAME.provider
        and
        resource_element.attrib["type"] == AGENT_NAME.type
    ):
        return None


    host_list = resource_element.xpath(
        "./{has_server}/@value".format(has_server=_HAS_SERVER_XPATH_SNIPPET)
    )
    if host_list:
        return host_list[0]
    return resource_element.attrib["id"]

def _validate_server_not_used(agent, option_dict):
    if "server" in option_dict:
        return [reports.invalid_option(
            ["server"],
            sorted([
                attr["name"] for attr in agent.get_parameters()
                if attr["name"] != "server"
            ]),
            "resource",
        )]
    return []


def validate_host_not_conflicts(nodes, node_name, instance_attributes):
    host = instance_attributes.get("server", node_name)
    if node_addresses_contain_host(nodes, host):
        return [reports.id_already_exists(host)]
    return []

def validate_create(
    nodes, resource_agent, host, node_name, instance_attributes
):
    """
    validate inputs for create

    list of NodeAddresses nodes -- nodes already used
    string node_name -- name of future node
    dict instance_attributes -- data for future resource instance attributes
    """
    report_list = _validate_server_not_used(resource_agent, instance_attributes)

    if node_addresses_contain_host(nodes, host):
        report_list.append(reports.id_already_exists(host))

    if node_addresses_contain_name(nodes, node_name):
        report_list.append(reports.id_already_exists(node_name))

    return report_list

def prepare_instance_atributes(instance_attributes, host):
    enriched_instance_attributes = instance_attributes.copy()
    enriched_instance_attributes["server"] = host
    return enriched_instance_attributes

def create(
    report_processor, resource_agent, resources_section, host, node_name,
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
    all_instance_attributes = instance_attributes.copy()
    all_instance_attributes.update({"server": host})
    try:
        return primitive.create(
            report_processor,
            resources_section,
            node_name,
            resource_agent,
            raw_operation_list,
            meta_attributes,
            all_instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
    except LibraryError as e:
        for report in e.args:
            if report.code == report_codes.INVALID_OPTION:
                report.info["allowed"] = [
                    value for value in report.info["allowed"]
                    if value != "server"
                ]
        raise e
