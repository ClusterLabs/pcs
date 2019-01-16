from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.cib.nvpair import update_nvset
from pcs.lib.cib.tools import get_nodes, find_unique_id
from pcs.lib.errors import LibraryError


def update_node_instance_attrs(cib, node_name, attrs, state_nodes=None):
    """
    Update nvpairs in instance_attributes for a node specified by its name.

    Automatically creates instance_attributes element if needed. If the node has
    more than one instance_attributes element, the first one is modified. If the
    node is missing in the CIB, it is automatically created if its state is
    provided in state_nodes.

    etree cib -- cib
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
    only_removing = True
    for value in attrs.values():
        if value != "":
            only_removing = False
            break

    nodes_section = get_nodes(cib)
    node_el = _get_node_by_uname(nodes_section, node_name)

    # Do not create new node if we are only removing values from it.
    if node_el is None and only_removing:
        return

    node_el = _ensure_node_exists(get_nodes(cib), node_name, state_nodes)
    # If no instance_attributes id is specified, crm_attribute modifies the
    # first one found. So we just mimic this behavior here.
    attrs_el = node_el.find("./instance_attributes")
    if attrs_el is None:
        # Do not create new nvset if we are only removing values from it.
        if only_removing:
            return
        attrs_el = etree.SubElement(
            node_el,
            "instance_attributes",
            id=find_unique_id(cib, "nodes-{0}".format(node_el.get("id")))
        )
    update_nvset(attrs_el, attrs)

def _ensure_node_exists(tree, node_name, state_nodes=None):
    """
    Make sure node with specified name exists in the tree.

    If the node doesn't exist, raise LibraryError. If state_nodes is provided
    and contains state of a node with the specified name, create the node in
    the tree. Return existing or created node element.

    etree tree -- node parent element
    string name -- node name
    iterable state_nodes -- optional list of node state objects
    """
    node_el = _get_node_by_uname(tree, node_name)
    if node_el is None and state_nodes:
        for node_state in state_nodes:
            if node_state.attrs.name == node_name:
                node_el = _create_node(
                    tree,
                    node_state.attrs.id,
                    node_state.attrs.name,
                    node_state.attrs.type
                )
                break
    if node_el is None:
        raise LibraryError(reports.node_not_found(node_name))
    return node_el

def _get_node_by_uname(tree, uname):
    """
    Return a node element with specified uname in the tree or None if not found

    etree tree -- node parent element
    string uname -- node name
    """
    return tree.find("./node[@uname='{0}']".format(uname))

def _create_node(tree, node_id, uname, node_type=None):
    """
    Create new node element as a direct child of the tree element

    etree tree -- node parent element
    string node_id -- node id
    string uname -- node name
    string node_type -- optional node type (normal, member, ping, remote)
    """
    node = etree.SubElement(tree, "node", id=node_id, uname=uname)
    if node_type:
        node.set("type", node_type)
    return node

