from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.resource import guest_node
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.misc import create_setup_patch_mixin
from pcs.test.tools.pcs_unittest import TestCase


SetupPatchMixin = create_setup_patch_mixin(guest_node)

class FindNodeList(TestCase, SetupPatchMixin):
    def assert_find_meta_attributes(self, xml, meta_attributes_xml_list):
        get_node = self.setup_patch("get_node", return_value=None)

        self.assertEquals(
            [None] * len(meta_attributes_xml_list),
            guest_node.find_node_list(etree.fromstring(xml))
        )

        for i, call in enumerate(get_node.mock_calls):
            assert_xml_equal(
                meta_attributes_xml_list[i],
                etree.tostring(call[1][0])
            )

    def test_get_no_nodes_when_no_primitives(self):
        self.assert_find_meta_attributes("<resources/>", [])

    def test_get_no_nodes_when_no_meta_remote_node(self):
        self.assert_find_meta_attributes(
            """
            <resources>
                <primitive>
                    <meta_attributes>
                        <nvpair name="remote-addr" value="G1"/>
                    </meta_attributes>
                </primitive>
            </resources>
            """,
            []
        )

    def test_get_multiple_nodes(self):
        self.assert_find_meta_attributes(
            """
            <resources>
                <primitive>
                    <meta_attributes>
                        <nvpair name="remote-node" value="G1"/>
                        <nvpair name="remote-addr" value="G1addr"/>
                    </meta_attributes>
                </primitive>
                <primitive>
                    <meta_attributes>
                        <nvpair name="remote-node" value="G2"/>
                    </meta_attributes>
                </primitive>
            </resources>
            """,
            [
                """
                <meta_attributes>
                    <nvpair name="remote-node" value="G1"/>
                    <nvpair name="remote-addr" value="G1addr"/>
                </meta_attributes>
                """,
                """
                <meta_attributes>
                    <nvpair name="remote-node" value="G2"/>
                </meta_attributes>
                """,
            ]
        )

class GetNode(TestCase):
    def assert_node(self, xml, expected_node):
        node = guest_node.get_node(etree.fromstring(xml))
        self.assertEquals(expected_node, (node.ring0, node.name))

    def test_return_none_when_is_not_guest_node(self):
        self.assertIsNone(guest_node.get_node(etree.fromstring(
            """
            <meta_attributes>
                <nvpair name="remote-addr" value="G1"/>
            </meta_attributes>
            """
        )))

    def test_return_same_host_and_name_when_remote_node_only(self):
        self.assert_node(
            """
            <meta_attributes>
                <nvpair name="remote-node" value="G1"/>
            </meta_attributes>
            """,
            ("G1", "G1")
        )

    def test_return_different_host_and_name_when_remote_addr_there(self):
        self.assert_node(
            """
            <meta_attributes>
                <nvpair name="remote-node" value="G1"/>
                <nvpair name="remote-addr" value="G1addr"/>
            </meta_attributes>
            """,
            ("G1addr", "G1")
        )
