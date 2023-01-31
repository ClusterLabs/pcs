from typing import Mapping

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.common.types import StringCollection
from pcs.lib import validate
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.cib.nvpair import (
    arrange_first_meta_attributes,
    get_meta_attribute_value,
    has_meta_attribute,
)
from pcs.lib.cib.tools import does_id_exist

# TODO pcs currently does not care about multiple meta_attributes and here
# we don't care as well
GUEST_OPTIONS = [
    "remote-port",
    "remote-addr",
    "remote-connect-timeout",
]


def validate_conflicts(
    tree: _Element,
    existing_nodes_names: StringCollection,
    existing_nodes_addrs: StringCollection,
    node_name: str,
    options: Mapping[str, str],
) -> reports.ReportItemList:
    report_list = []
    if (
        does_id_exist(tree, node_name)
        or node_name in existing_nodes_names
        or ("remote-addr" not in options and node_name in existing_nodes_addrs)
    ):
        report_list.append(
            ReportItem.error(reports.messages.IdAlreadyExists(node_name))
        )

    if (
        "remote-addr" in options
        and options["remote-addr"] in existing_nodes_addrs
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.IdAlreadyExists(options["remote-addr"])
            )
        )
    return report_list


def is_node_name_in_options(options):
    return "remote-node" in options


def get_guest_option_value(options, default=None):
    """
    Commandline options: no options
    """
    return options.get("remote-node", default)


def validate_set_as_guest(
    tree, existing_nodes_names, existing_nodes_addrs, node_name, options
):
    validator_list = [
        validate.NamesIn(GUEST_OPTIONS, option_type="guest"),
        validate.ValueTimeInterval("remote-connect-timeout"),
        validate.ValuePortNumber("remote-port"),
    ]
    return (
        validate.ValidatorAll(validator_list).validate(options)
        + validate.ValueNotEmpty("node name", None).validate(
            {"node name": node_name.strip()}
        )
        + validate_conflicts(
            tree, existing_nodes_names, existing_nodes_addrs, node_name, options
        )
    )


def is_guest_node(resource_element):
    """
    Return True if resource_element is already set as guest node.

    etree.Element resource_element is a search element
    """
    return has_meta_attribute(resource_element, "remote-node")


def validate_is_not_guest(resource_element):
    """
    etree.Element resource_element
    """
    if not is_guest_node(resource_element):
        return []

    return [
        ReportItem.error(
            reports.messages.ResourceIsGuestNodeAlready(
                resource_element.attrib["id"]
            )
        )
    ]


def set_as_guest(
    resource_element,
    id_provider,
    node,
    addr=None,
    port=None,
    connect_timeout=None,
):
    """
    Set resource as guest node.

    etree.Element resource_element

    """
    meta_options = {"remote-node": str(node)}
    if addr:
        meta_options["remote-addr"] = str(addr)
    if port:
        meta_options["remote-port"] = str(port)
    if connect_timeout:
        meta_options["remote-connect-timeout"] = str(connect_timeout)

    arrange_first_meta_attributes(resource_element, meta_options, id_provider)


def unset_guest(resource_element):
    """
    Unset resource as guest node.

    etree.Element resource_element
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    guest_nvpair_list = resource_element.xpath(
        "./meta_attributes/nvpair[{0}]".format(
            " or ".join(
                [
                    '@name="{0}"'.format(option)
                    for option in (GUEST_OPTIONS + ["remote-node"])
                ]
            )
        )
    )
    for nvpair in guest_nvpair_list:
        meta_attributes = nvpair.getparent()
        meta_attributes.remove(nvpair)


def get_node_name_from_options(meta_options, default=None):
    """
    Return node_name from meta options.
    dict meta_options
    """
    return meta_options.get("remote-node", default)


def get_node_name_from_resource(resource_element):
    """
    Return the node name from a remote node resource, None for other resources

    etree.Element resource_element
    """
    return get_meta_attribute_value(resource_element, "remote-node")


def find_node_list(tree):
    """
    Return list of guest nodes from the specified element tree

    etree.Element tree -- an element to search guest nodes in
    """
    node_list = []
    for meta_attrs in tree.xpath(
        """
            .//primitive
                /meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                ]
        """
    ):
        host = None
        name = None
        for nvpair in meta_attrs:
            if nvpair.attrib.get("name", "") == "remote-addr":
                host = nvpair.attrib["value"]
            if nvpair.attrib.get("name", "") == "remote-node":
                name = nvpair.attrib["value"]
                if host is None:
                    host = name
        if name:
            # The name is never empty as we only loop through elements with
            # non-empty names. It's just we loop through nvpairs instead of
            # reading the name directly.
            node_list.append(PacemakerNode(name, host))
    return node_list


def find_node_resources(resources_section, node_identifier):
    """
    Return list of etree.Element primitives that are guest nodes.

    etree.Element resources_section is a researched element
    string node_identifier could be id of resource, node name or node address
    """
    resources = resources_section.xpath(
        """
        .//primitive[
            (
                @id=$node_id
                and
                meta_attributes[
                    nvpair[
                        @name="remote-node"
                        and
                        string-length(@value) > 0
                    ]
                ]
            )
            or
            meta_attributes[
                nvpair[
                    @name="remote-node"
                    and
                    string-length(@value) > 0
                ]
                and
                nvpair[
                    (
                        @name="remote-addr"
                        or
                        @name="remote-node"
                    )
                    and
                    @value=$node_id
                ]
            ]
        ]
    """,
        node_id=node_identifier,
    )
    return resources
