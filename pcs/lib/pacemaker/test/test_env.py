from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.pacemaker.env import PacemakerEnv
from pcs.test.tools.pcs_unittest import TestCase, mock



class GetRemoteNodes(TestCase):
    def setUp(self):
        self.set_cib("<cib><configuration><resources /></configuration></cib>")

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

    def assert_nodes_equals(self, actual_nodes, expected_nodes):
        self.assertEquals(
            expected_nodes,
            [(node.ring0, node.name) for node in actual_nodes]
        )
    def test_get_all_remote_nodes(self):
        self.set_cib("""
            <cib>
                <configuration>
                    <resources>
                        <primitive class="ocf" id="remote-1"
                            provider="pacemaker" type="remote"
                        >
                            <instance_attributes id="first-attribs">
                                <nvpair id="server1" name="server"
                                    value="host-1"
                                />
                            </instance_attributes>
                        </primitive>
                        <primitive class="ocf" id="remote-2"
                            provider="pacemaker" type="remote"
                        >
                            <instance_attributes id="first-attribs">
                                <nvpair id="server1" name="server"
                                    value="host-2"
                                />
                            </instance_attributes>
                        </primitive>
                    </resources>
                </configuration>
            </cib>
        """)
        self.assert_nodes_equals(self.env.remote_nodes, [
            ("host-1", "remote-1"),
            ("host-2", "remote-2"),
        ])

    def test_get_no_remote_nodes_when_not_in_cib(self):
        self.assert_nodes_equals(self.env.remote_nodes, [])
