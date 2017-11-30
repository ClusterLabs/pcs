from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib.resource import remote_node
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.lib.node import NodeAddresses
from pcs.test.tools.assertions import assert_report_item_list_equal
from pcs.test.tools.pcs_unittest import TestCase, mock


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
            </resources>
            """,
            []
        )

    def test_find_nodes_without_server(self):
        self.assert_nodes_equals(
            """
            <resources>
                <primitive class="ocf" id="R1"
                    provider="pacemaker" type="remote"
                >
                </primitive>
            </resources>
            """,
            [
                ("R1", "R1"),
            ]
        )

    def test_find_nodes_with_empty_server(self):
        #it does not work, but the node "R1" is visible as remote node in the
        #status
        self.assert_nodes_equals(
            """
            <resources>
                <primitive class="ocf" id="R1"
                    provider="pacemaker" type="remote"
                >
                    <instance_attributes id="first-attribs">
                        <nvpair name="server" value=""/>
                    </instance_attributes>
                </primitive>
            </resources>
            """,
            [
                ("R1", "R1"),
            ]
        )


class FindNodeResources(TestCase):
    def assert_resources_equals(self, node_identifier, xml, resource_id_list):
        self.assertEqual(
            resource_id_list,
            [
                resource_element.attrib["id"]
                for resource_element in remote_node.find_node_resources(
                    etree.fromstring(xml),
                    node_identifier
                )
            ]
        )

    def test_find_all_resources(self):
        self.assert_resources_equals(
            "HOST",
            """<resources>
                <primitive class="ocf" id="R1"
                    provider="pacemaker" type="remote"
                >
                    <instance_attributes>
                        <nvpair name="server" value="HOST"/>
                    </instance_attributes>
                </primitive>
                <primitive class="ocf" id="R2"
                    provider="pacemaker" type="remote"
                >
                    <instance_attributes id="first-attribs">
                        <nvpair name="server" value="HOST"/>
                    </instance_attributes>
                </primitive>
            </resources>""",
            ["R1", "R2"]
        )

    def test_find_by_resource_id(self):
        self.assert_resources_equals(
            "HOST",
            """<resources>
                <primitive class="ocf" id="HOST"
                    provider="pacemaker" type="remote"
                />
            </resources>""",
            ["HOST"]
        )

    def test_ignore_non_remote_primitives(self):
        self.assert_resources_equals(
            "HOST",
            """<resources>
                <primitive class="ocf" id="HOST"
                    provider="heartbeat" type="Dummy"
                />
            </resources>""",
            []
        )


class GetHost(TestCase):
    def test_return_host_when_there(self):
        self.assertEqual(
            "HOST",
            remote_node.get_host(etree.fromstring("""
                <primitive class="ocf" id="R" provider="pacemaker" type="remote"
                >
                    <instance_attributes>
                        <nvpair name="server" value="HOST"/>
                    </instance_attributes>
                </primitive>
            """))
        )

    def test_return_none_when_host_not_found(self):
        self.assertIsNone(remote_node.get_host(etree.fromstring("""
            <primitive class="ocf" id="R" provider="heartbeat" type="dummy"/>
        """)))

    def test_return_none_when_primitive_is_without_agent(self):
        case_list = [
            '<primitive id="R"/>',
            '<primitive id="R" class="ocf"/>',
            '<primitive id="R" class="ocf" provider="pacemaker"/>',
        ]
        for case in case_list:
            self.assertIsNone(
                remote_node.get_host(etree.fromstring(case)),
                "for '{0}' is not returned None".format(case)
            )

    def test_return_host_from_resource_id(self):
        self.assertEqual(
            "R",
            remote_node.get_host(etree.fromstring("""
                <primitive class="ocf" id="R" provider="pacemaker"
                    type="remote"
                />
            """))
        )

class Validate(TestCase):
    def validate(
        self, instance_attributes=None, node_name="NODE-NAME", host="node-host"
    ):
        nodes = [
            NodeAddresses("RING0", "RING1", name="R"),
        ]
        resource_agent = mock.MagicMock()
        return remote_node.validate_create(
            nodes,
            resource_agent,
            host,
            node_name,
            instance_attributes if instance_attributes else {},
        )

    def test_report_conflict_node_name(self):
        assert_report_item_list_equal(
            self.validate(
                node_name="R",
                host="host",
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": "R",
                    },
                    None
                )
            ]
        )

    def test_report_conflict_node_host(self):
        assert_report_item_list_equal(
            self.validate(
                host="RING0",
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": "RING0",
                    },
                    None
                )
            ]
        )

    def test_report_conflict_node_host_ring1(self):
        assert_report_item_list_equal(
            self.validate(
                host="RING1",
            ),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": "RING1",
                    },
                    None
                )
            ]
        )

    def test_report_used_disallowed_server(self):
        assert_report_item_list_equal(
            self.validate(
                instance_attributes={"server": "A"}
            ),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        'option_type': 'resource',
                        'option_names': ['server'],
                        'allowed': [],
                        "allowed_patterns": [],
                    },
                    None
                )
            ]
        )
