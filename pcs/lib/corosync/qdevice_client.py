from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


def remote_client_enable(node_communicator, node):
    node_communicator.call_node(node, "remote/qdevice_client_enable", "")

def remote_client_disable(node_communicator, node):
    node_communicator.call_node(node, "remote/qdevice_client_disable", "")
