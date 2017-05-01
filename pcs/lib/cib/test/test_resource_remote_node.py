from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib.resource import remote_node
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.lib.node import NodeAddresses
from pcs.test.tools.assertions import assert_report_item_list_equal
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

    def test_return_host_from_resource_id(self):
        self.assertEqual(
            "R",
            remote_node.get_host(etree.fromstring("""
                <primitive class="ocf" id="R" provider="pacemaker"
                    type="remote"
                />
            """))
        )

class ValidateHostNotAmbiguous(TestCase):
    def test_no_report_when_no_server_in_instance_attributes(self):
        self.assertEqual(
            remote_node.validate_host_not_ambiguous({}, "HOST"),
            [],
        )

    def test_no_report_when_host_eq_server_in_instance_attributes(self):
        self.assertEqual(
            remote_node.validate_host_not_ambiguous({"server": "HOST"}, "HOST"),
            [],
        )

    def test_report_on_unambiguous(self):
        assert_report_item_list_equal(
            remote_node.validate_host_not_ambiguous({"server": "NEXT"}, "HOST"),
            [
                (
                    severities.ERROR,
                    report_codes.AMBIGUOUS_HOST_SPECIFICATION,
                    {
                        "host_list": ["HOST", "NEXT"]
                    }
                )
            ]
        )

class ValidatePcmkRemoteHostNotUsed(TestCase):
    def validate_options(self, options):
        nodes = [
            NodeAddresses("RING0", "RING1", name="R1"),
            NodeAddresses("HOST", name="R1"),
        ]

        assert_report_item_list_equal(
            remote_node.validate_pcmk_remote_host_not_used("server", nodes)
                (options)
            ,
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": options["server"]
                    }
                )
            ]
        )

    def test_report_when_conflict_with_existing(self):
        self.validate_options({"server": "HOST"})

    def test_report_when_conflict_with_ring1(self):
        self.validate_options({"server": "RING1"})

class Validate(TestCase):
    def validate(self, instance_attributes, node_name="NODE-NAME"):
        nodes = [
            NodeAddresses("RING0", "RING1", name="R"),
        ]
        return remote_node.validate_parts(nodes, node_name, instance_attributes)

    def test_report_required_server(self):
        assert_report_item_list_equal(
            self.validate(instance_attributes={}),
            [
                (
                    severities.ERROR,
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    {
                        "option_type": "remote node",
                        "option_names": ["server"],
                    },
                    None
                )
            ]
        )

    def test_report_conflict_node_name(self):
        assert_report_item_list_equal(
            self.validate(
                instance_attributes={"server": "host"},
                node_name="R",
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
