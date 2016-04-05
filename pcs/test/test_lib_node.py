from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

import pcs.lib.node as lib

class NodeAddressesTest(TestCase):
    def test_properties_all(self):
        ring0 = "test_ring0"
        ring1 = "test_ring1"
        name = "test_name"
        id = "test_id"
        node = lib.NodeAddresses(ring0, ring1, name, id)
        self.assertEqual(ring0, node.ring0)
        self.assertEqual(ring1, node.ring1)
        self.assertEqual(name, node.label)
        self.assertEqual(id, node.id)

    def test_properties_required(self):
        ring0 = "test_ring0"
        node = lib.NodeAddresses(ring0)
        self.assertEqual(ring0, node.ring0)
        self.assertEqual(None, node.ring1)
        self.assertEqual(ring0, node.label)
        self.assertEqual(None, node.id)


class NodeAddressesListTest(TestCase):
    def test_empty(self):
        nodes = lib.NodeAddressesList()
        self.assertEqual(0, len(nodes))
        self.assertEqual([], list(nodes))
        self.assertRaises(IndexError, lambda: nodes[0])

    def test_append(self):
        node1 = lib.NodeAddresses("node1")
        node2 = lib.NodeAddresses("node2")
        nodes = lib.NodeAddressesList()

        nodes.append(node1)
        self.assertEqual(1, len(nodes))
        self.assertEqual([node1], list(nodes))
        self.assertEqual(node1, nodes[0])

        nodes.append(node2)
        self.assertEqual(2, len(nodes))
        self.assertEqual([node1, node2], list(nodes))
        self.assertEqual(node1, nodes[0])
        self.assertEqual(node2, nodes[1])

    def test_create_from_empty_list(self):
        nodes = lib.NodeAddressesList([])
        self.assertEqual(0, len(nodes))
        self.assertEqual([], list(nodes))
        self.assertRaises(IndexError, lambda: nodes[0])

    def test_create_from_list(self):
        node1 = lib.NodeAddresses("node1")
        node2 = lib.NodeAddresses("node2")
        nodes = lib.NodeAddressesList([node1, node2])
        self.assertEqual(2, len(nodes))
        self.assertEqual([node1, node2], list(nodes))
        self.assertEqual(node1, nodes[0])
        self.assertEqual(node2, nodes[1])

    def test_create_from_node_list(self):
        node1 = lib.NodeAddresses("node1")
        node2 = lib.NodeAddresses("node2")
        node3 = lib.NodeAddresses("node3")
        nodes_source = lib.NodeAddressesList([node1, node2])
        nodes = lib.NodeAddressesList(nodes_source)
        nodes_source.append(node3)

        self.assertEqual(2, len(nodes))
        self.assertEqual([node1, node2], list(nodes))
        self.assertEqual(node1, nodes[0])
        self.assertEqual(node2, nodes[1])
