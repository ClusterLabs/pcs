from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.node import NodeAddresses
from pcs.lib.pacemaker.env import PacemakerEnv
from pcs.test.tools.pcs_unittest import TestCase, mock


class GetNodesTest(TestCase):
    def setUp(self):
        self.set_cib("<cib><resources /></cib>")

    @property
    def env(self):
        report_processor = mock.MagicMock()
        return PacemakerEnv(
            report_processor,
            env_data={},
            get_cib=lambda: self.cib
        )

    def set_cib(self, xml):
        self.cib = etree.fromstring(xml)

class GetRemoteNodes(GetNodesTest):
    def test_get_all_remote_nodes(self):
        self.set_cib("""
            <cib>
                <resources>
                    <primitive class="ocf" id="remote-1" provider="pacemaker"
                        type="remote"
                    >
                        <instance_attributes id="first-attribs">
                            <nvpair id="server1" name="server" value="host-1"/>
                        </instance_attributes>
                    </primitive>
                    <primitive class="ocf" id="remote-2" provider="pacemaker"
                        type="remote"
                    >
                        <instance_attributes id="first-attribs">
                            <nvpair id="server1" name="server" value="host-2"/>
                        </instance_attributes>
                    </primitive>
                </resources>
            </cib>
        """)
        self.assertEqual(
            [
                NodeAddresses("host-1", name="remote-1"),
                NodeAddresses("host-2", name="remote-2"),
            ],
            self.env.remote_nodes
        )

    def test_get_no_remote_nodes_when_not_in_cib(self):
        self.assertEqual([], self.env.remote_nodes)

class GetGuestNodes(GetNodesTest):
    def test_get_all_guest_nodes(self):
        self.set_cib("""
            <cib>
                <resources>
                    <primitive class="ocf" id="R1" provider="heartbeat"
                        type="VirtualDomain"
                    >
                        <meta_attributes id="meta1">
                            <nvpair id="rnode-1" name="remote-node" value="G1"/>
                        </meta_attributes>
                    </primitive>
                    <primitive class="ocf" id="R2" provider="heartbeat"
                        type="VirtualDomain"
                    >
                        <meta_attributes id="meta2">
                            <nvpair id="rnode-2" name="remote-node" value="G2"/>
                        </meta_attributes>
                    </primitive>
                </resources>
            </cib>
        """)
        self.assertEqual(
            [
                NodeAddresses("G1", name="R1"),
                NodeAddresses("G2", name="R2"),
            ],
            self.env.guest_nodes
        )

    def test_get_no_guest_nodes_when_not_in_cib(self):
        self.assertEqual([], self.env.guest_nodes)
