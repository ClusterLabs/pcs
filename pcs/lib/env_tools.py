from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib.resource import remote_node, guest_node
from pcs.lib.xml_tools import get_root
from pcs.lib.node import NodeAddressesList


def get_nodes(corosync_conf=None, tree=None):
    return NodeAddressesList(
        (
            corosync_conf.get_nodes() if corosync_conf
            else NodeAddressesList([])
        )
        +
        (
            get_nodes_remote(tree) if tree is not None
            else NodeAddressesList([])
        )
        +
        (
            get_nodes_guest(tree) if tree is not None
            else NodeAddressesList([])
        )
    )

def get_nodes_remote(tree):
    return NodeAddressesList(remote_node.find_node_list(get_root(tree)))

def get_nodes_guest(tree):
    return NodeAddressesList(guest_node.find_node_list(get_root(tree)))
