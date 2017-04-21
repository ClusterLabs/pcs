from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.resource import remote_node
from pcs.test.tools.pcs_unittest import TestCase


class FindNodeList(TestCase):
    def assert_nodes_equals(self, xml, expected_nodes):
        self.assertEquals(
            expected_nodes,
            [
                (node.ring0, node.name)
                for node in remote_node.find_node_list(etree.fromstring(xml))
            ]
        )
    def test_find_multiple_nodes(self):
        self.assert_nodes_equals(
            """
            <resources>
                <primitive class="ocf" id="R1"
                    provider="pacemaker" type="remote"
                >
                    <instance_attributes>
                        <nvpair name="server" value="H1"/>
                    </instance_attributes>
                </primitive>
                <primitive class="ocf" id="R2"
                    provider="pacemaker" type="remote"
                >
                    <instance_attributes id="first-attribs">
                        <nvpair name="server" value="H2"/>
                    </instance_attributes>
                </primitive>
            </resources>
            """,
            [
                ("H1", "R1"),
                ("H2", "R2"),
            ]
        )

    def test_find_no_nodes(self):
        self.assert_nodes_equals(
            """
            <resources>
                <primitive class="ocf" id="D" provider="heartbeat" type="dummy">
                    <meta_attributes>
                        <nvpair name="server" value="H1"/>
                    </meta_attributes>
                </primitive>
                <primitive class="ocf" id="R1"
                    provider="pacemaker" type="remote"
                />
            </resources>
            """,
            []
        )
