from typing import (
    Iterable,
    Mapping,
    Optional,
    cast,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.types import StringCollection
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.cib.resource import primitive
from pcs.lib.cib.resource.types import ResourceOperationIn
from pcs.lib.cib.tools import IdProvider
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import (
    ResourceAgentFacade,
    ResourceAgentMetadata,
    ResourceAgentName,
)

AGENT_NAME = ResourceAgentName("ocf", "pacemaker", "remote")


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


def find_node_list(tree):
    """
    Return list of remote nodes from the specified element tree

    etree.Element tree -- an element to search remote nodes in
    """
    node_list = [
        PacemakerNode(
            nvpair.getparent().getparent().attrib["id"], nvpair.attrib["value"]
        )
        for nvpair in tree.xpath(
            ".//primitive[{is_remote}]/{has_server}".format(
                is_remote=_IS_REMOTE_AGENT_XPATH_SNIPPET,
                has_server=_HAS_SERVER_XPATH_SNIPPET,
            )
        )
    ]

    node_list.extend(
        [
            PacemakerNode(primitive.attrib["id"], primitive.attrib["id"])
            for primitive in tree.xpath(
                ".//primitive[{is_remote} and not({has_server})]".format(
                    is_remote=_IS_REMOTE_AGENT_XPATH_SNIPPET,
                    has_server=_HAS_SERVER_XPATH_SNIPPET,
                )
            )
        ]
    )

    return node_list


def find_node_resources(
    resources_section: _Element, node_identifier: str
) -> list[_Element]:
    """
    Return list of resource elements that match to node_identifier

    resources_section -- search element
    node_identifier -- could be id of the resource or its instance attribute
        "server"
    """
    return cast(
        list[_Element],
        resources_section.xpath(
            f"""
            .//primitive[
                {_IS_REMOTE_AGENT_XPATH_SNIPPET} and (
                    @id=$identifier
                    or
                    instance_attributes/nvpair[
                        @name="server"
                        and
                        @value=$identifier
                    ]
                )
            ]
        """,
            identifier=node_identifier,
        ),
    )


def get_node_name_from_resource(resource_element):
    """
    Return the node name from a remote node resource, None for other resources

    etree.Element resource_element
    """
    if not (
        resource_element.attrib.get("class", "") == AGENT_NAME.standard
        and resource_element.attrib.get("provider", "") == AGENT_NAME.provider
        and resource_element.attrib.get("type", "") == AGENT_NAME.type
    ):
        return None
    return resource_element.attrib["id"]


def _validate_server_not_used(
    agent: ResourceAgentMetadata, option_dict: Mapping[str, str]
) -> reports.ReportItemList:
    if "server" in option_dict:
        return [
            reports.ReportItem.error(
                reports.messages.InvalidOptions(
                    ["server"],
                    sorted(
                        [
                            attr.name
                            for attr in agent.parameters
                            if attr.name != "server"
                        ]
                    ),
                    "resource",
                ),
            )
        ]
    return []


def validate_host_not_conflicts(
    existing_nodes_addrs: StringCollection,
    node_name: str,
    instance_attributes: Mapping[str, str],
) -> reports.ReportItemList:
    host = instance_attributes.get("server", node_name)
    if host in existing_nodes_addrs:
        return [
            reports.ReportItem.error(reports.messages.IdAlreadyExists(host))
        ]
    return []


def validate_create(
    existing_nodes_names: StringCollection,
    existing_nodes_addrs: StringCollection,
    resource_agent: ResourceAgentMetadata,
    new_node_name: str,
    new_node_addr: str,
    instance_attributes: Mapping[str, str],
) -> reports.ReportItemList:
    """
    validate inputs for create

    existing_nodes_names -- node names already in use
    existing_nodes_addrs -- node addresses already in use
    ResourceAgent resource_agent -- pacemaker_remote resource agent
    new_node_name -- the name of the future node
    new_node_addr -- the address of the future node
    instance_attributes -- data for the future resource instance attributes
    """
    report_list = _validate_server_not_used(resource_agent, instance_attributes)

    addr_is_used = False
    if new_node_addr in existing_nodes_addrs:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdAlreadyExists(new_node_addr)
            )
        )
        addr_is_used = True

    if (
        not addr_is_used or new_node_addr != new_node_name
    ) and new_node_name in existing_nodes_names:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.IdAlreadyExists(new_node_name)
            )
        )

    return report_list


def _prepare_instance_attributes(
    instance_attributes: Optional[Mapping[str, str]],
    host: str,
) -> Mapping[str, str]:
    enriched_instance_attributes = (
        dict(instance_attributes) if instance_attributes else {}
    )
    enriched_instance_attributes["server"] = host
    return enriched_instance_attributes


def create(
    report_processor: reports.ReportProcessor,
    cmd_runner: CommandRunner,
    resource_agent_facade: ResourceAgentFacade,
    resources_section: _Element,
    id_provider: IdProvider,
    host: str,
    node_name: str,
    raw_operation_list: Optional[Iterable[ResourceOperationIn]] = None,
    meta_attributes: Optional[Mapping[str, str]] = None,
    instance_attributes: Optional[Mapping[str, str]] = None,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    """
    Prepare all parts of remote resource and append it into the cib.

    report_processor -- tool for warning/info/error reporting
    resources_section -- place where new element will be appended
    node_name -- name of the remote node and id of new resource as well
    raw_operation_list -- specifies operations of resource
    meta_attributes -- specifies meta attributes of resource
    instance_attributes -- specifies instance attributes of resource
    allow_invalid_operation -- flag for skipping validation of operations
    allow_invalid_instance_attributes -- flag for skipping validation of
        instance_attributes
    use_default_operations -- flag for completion operations with default
        actions specified in resource agent
    """
    all_instance_attributes = _prepare_instance_attributes(
        instance_attributes, host
    )
    return primitive.create(
        report_processor,
        cmd_runner,
        resources_section,
        id_provider,
        node_name,
        resource_agent_facade,
        raw_operation_list,
        meta_attributes,
        all_instance_attributes,
        allow_invalid_operation,
        allow_invalid_instance_attributes,
        use_default_operations,
        # TODO remove this dirty fix
        # This is for passing info from the top (here) through another library
        # command (primitive.create) to instance attributes validator in
        # resource_agent. We handle the "server" attribute ourselves in this
        # command so we want to make sure it is not reported as an allowed
        # option.
        # How to fix:
        # 1) do not call one lib command from another
        # 2) split validation and cib modification in primitive.create
        # 3) call the validation from here and handle the results or config
        #    the validator before / when running it
        do_not_report_instance_attribute_server_exists=True,
        enable_agent_self_validation=False,
    )
