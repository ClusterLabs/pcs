from collections import namedtuple
from typing import Set

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.nvpair import update_nvset
from pcs.lib.cib.tools import get_nodes
from pcs.lib.errors import LibraryError
from pcs.lib.xml_tools import (
    append_when_useful,
    get_root,
)


class PacemakerNode(namedtuple("PacemakerNode", "name addr")):
    """
    A class for transporting a node name and address for purposes of network
    communication and checking if node name / address is in use.
    """

    __slots__ = ()


def update_node_instance_attrs(
    cib, id_provider, node_name, attrs, state_nodes=None
):
    """
    Update nvpairs in instance_attributes for a node specified by its name.

    Automatically creates instance_attributes element if needed. If the node has
    more than one instance_attributes element, the first one is modified. If the
    node is missing in the CIB, it is automatically created if its state is
    provided in state_nodes.

    etree cib -- cib
    IdProvider id_provider -- elements' ids generator
    string node_name -- name of the node to be updated
    dict attrs -- attrs to update, e.g. {'A': 'a', 'B': ''}
    iterable state_nodes -- optional list of node state objects
    """
    # Do not ever remove the nvset element or the node element, even if they
    # are empty. There may be ACLs set in pacemaker which allow "write" for
    # nvpairs (adding, changing and removing) but not nvsets. In such a case,
    # removing the nvset would cause the whole change to be rejected by
    # pacemaker with a "permission denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514

    if not attrs:
        return

    cib_nodes = get_nodes(cib)
    node_el = _ensure_node_exists(cib_nodes, node_name, state_nodes)
    # If no instance_attributes id is specified, crm_attribute modifies the
    # first one found. So we just mimic this behavior here.
    attrs_el = node_el.find("./instance_attributes")
    if attrs_el is None:
        attrs_el = etree.Element(
            "instance_attributes",
            id=id_provider.allocate_id("nodes-{0}".format(node_el.get("id"))),
        )
    update_nvset(attrs_el, attrs, id_provider)
    append_when_useful(node_el, attrs_el)
    append_when_useful(cib_nodes, node_el)


def get_node_names(cib: _Element) -> Set[str]:
    return {
        str(node.attrib["uname"])
        for node in get_nodes(get_root(cib)).iterfind("./node")
    }


def _ensure_node_exists(tree, node_name, state_nodes=None):
    """
    Make sure node with specified name exists

    If the node doesn't exist, raise LibraryError. If state_nodes is provided
    and contains state of a node with the specified name, create the node.
    Return existing or created node element.

    etree tree -- node parent element
    string name -- node name
    iterable state_nodes -- optional list of node state objects
    """
    node_el = _get_node_by_uname(tree, node_name)
    if node_el is None and state_nodes:
        for node_state in state_nodes:
            if node_state.attrs.name == node_name:
                node_el = _create_node(
                    node_state.attrs.id,
                    node_state.attrs.name,
                    node_state.attrs.type,
                )
                break
    if node_el is None:
        raise LibraryError(
            ReportItem.error(reports.messages.NodeNotFound(node_name))
        )
    return node_el


def _get_node_by_uname(tree, uname):
    """
    Return a node element with specified uname in the tree or None if not found

    etree tree -- node parent element
    string uname -- node name
    """
    nodes = tree.xpath("./node[@uname=$uname]", uname=uname)
    return nodes[0] if nodes else None


def _create_node(node_id, uname, node_type=None):
    """
    Create new node element

    string node_id -- node id
    string uname -- node name
    string node_type -- optional node type (member, ping, remote)
    """
    node = etree.Element("node", id=node_id, uname=uname)
    if node_type:
        node.set("type", node_type)
    return node
