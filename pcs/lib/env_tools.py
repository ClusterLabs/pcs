from pcs.lib.cib.resource import remote_node, guest_node
from pcs.lib.xml_tools import get_root


def get_existing_nodes_names(corosync_conf=None, cib=None):
    return __get_nodes_names(*__get_nodes(corosync_conf, cib))

def get_existing_nodes_names_addrs(corosync_conf=None, cib=None):
    corosync_nodes, remote_and_guest_nodes = __get_nodes(corosync_conf, cib)
    return (
        __get_nodes_names(corosync_nodes, remote_and_guest_nodes),
        __get_nodes_addrs(corosync_nodes, remote_and_guest_nodes),
    )

def __get_nodes(corosync_conf=None, cib=None):
    corosync_nodes = corosync_conf.get_nodes() if corosync_conf else []
    remote_and_guest_nodes = []
    if cib is not None:
        cib_root = get_root(cib)
        remote_and_guest_nodes = (
            remote_node.find_node_list(cib_root)
            +
            guest_node.find_node_list(cib_root)
        )
    return corosync_nodes, remote_and_guest_nodes

def __get_nodes_names(corosync_nodes, remote_and_guest_nodes):
    return (
        [node.name for node in corosync_nodes if node.name]
        +
        [node.name for node in remote_and_guest_nodes]
    )

def __get_nodes_addrs(corosync_nodes, remote_and_guest_nodes):
    nodes_addrs = [node.addr for node in remote_and_guest_nodes]
    for node in corosync_nodes:
        nodes_addrs += node.addrs_plain
    return nodes_addrs
