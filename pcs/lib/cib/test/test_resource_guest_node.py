from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib.resource import guest_node
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import(
    assert_xml_equal,
    assert_report_item_list_equal,
)
from pcs.test.tools.misc import create_setup_patch_mixin
from pcs.test.tools.pcs_unittest import TestCase
from pcs.lib.node import NodeAddresses


SetupPatchMixin = create_setup_patch_mixin(guest_node)

class ValidateHostConflicts(TestCase):
    def validate(self, node_name, options):
        tree = etree.fromstring("""
            <cib>
                <configuration>
                    <resources>
                        <primitive id="CONFLICT"/>
                        <primitive id="A">
                            <meta_attributes>
                                <nvpair name="remote-node"
                                    value="GUEST_CONFLICT"
                                />
                            </meta_attributes>
                        </primitive>
                        <primitive id="B" class="ocf" provider="pacemaker"
                            type="remote"
                        >
                            <instance_attributes>
                                <nvpair name="server" value="REMOTE_CONFLICT"/>
                            </instance_attributes>
                        </primitive>
                        <primitive id="C">
                            <meta_attributes>
                                <nvpair name="remote-node" value="some"/>
                                <nvpair name="remote-addr"
                                    value="GUEST_ADDR_CONFLICT"
                                />
                            </meta_attributes>
                        </primitive>
                    </resources>
                </configuration>
            </cib>
        """)
        nodes = [
            NodeAddresses("RING0", "RING1", name="R1"),
            NodeAddresses("REMOTE_CONFLICT", name="B"),
            NodeAddresses("GUEST_CONFLICT", name="GUEST_CONFLICT"),
            NodeAddresses("GUEST_ADDR_CONFLICT", name="some"),
        ]
        return guest_node.validate_conflicts(tree, nodes, node_name, options)

    def assert_already_exists_error(
        self, conflict_name, node_name, options=None
    ):
        assert_report_item_list_equal(
            self.validate(node_name, options if options else {}),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": conflict_name,
                    },
                    None
                ),
            ]
        )


    def test_report_conflict_with_id(self):
        self.assert_already_exists_error("CONFLICT", "CONFLICT")

    def test_report_conflict_guest_node(self):
        self.assert_already_exists_error("GUEST_CONFLICT", "GUEST_CONFLICT")

    def test_report_conflict_guest_addr(self):
        self.assert_already_exists_error(
            "GUEST_ADDR_CONFLICT",
            "GUEST_ADDR_CONFLICT",
        )

    def test_report_conflict_guest_addr_by_addr(self):
        self.assert_already_exists_error(
            "GUEST_ADDR_CONFLICT",
            "GUEST_ADDR_CONFLICT",
        )

    def test_no_conflict_guest_node_whe_addr_is_different(self):
        self.assertEqual([], self.validate("GUEST_ADDR_CONFLICT", {
            "remote-addr": "different",
        }))

    def test_report_conflict_remote_node(self):
        self.assert_already_exists_error("REMOTE_CONFLICT", "REMOTE_CONFLICT")

    def test_no_conflict_remote_node_whe_addr_is_different(self):
        self.assertEqual([], self.validate("REMOTE_CONFLICT", {
            "remote-addr": "different",
        }))

    def test_report_conflict_remote_node_by_addr(self):
        self.assert_already_exists_error("REMOTE_CONFLICT", "different", {
            "remote-addr": "REMOTE_CONFLICT",
        })

class ValidateOptions(TestCase):
    def validate(self, options, name="some_name"):
        return guest_node.validate_set_as_guest(
            etree.fromstring('<cib/>'),
            [NodeAddresses(
                "EXISTING-HOST-RING0",
                "EXISTING-HOST-RING0",
                name="EXISTING-HOST-NAME"
            )],
            name,
            options
        )

    def test_no_report_on_valid(self):
        self.assertEqual(
            [],
            self.validate({}, "node1")
        )

    def test_report_invalid_option(self):
        assert_report_item_list_equal(
            self.validate({"invalid": "invalid"}, "node1"),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_type": "guest",
                        "option_names": ["invalid"],
                        "allowed": sorted(guest_node.GUEST_OPTIONS),
                        "allowed_patterns": [],
                    },
                    None
                ),
            ]
        )

    def test_report_invalid_interval(self):
        assert_report_item_list_equal(
            self.validate({"remote-connect-timeout": "invalid"}, "node1"),
            [
                (
                    severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "remote-connect-timeout",
                        "option_value": "invalid",
                    },
                    None
                ),
            ]
        )

    def test_report_invalid_node_name(self):
        assert_report_item_list_equal(
            self.validate({}, "EXISTING-HOST-NAME"),
            [
                (
                    severities.ERROR,
                    report_codes.ID_ALREADY_EXISTS,
                    {
                        "id": "EXISTING-HOST-NAME",
                    },
                    None
                ),
            ]
        )


class ValidateInNotGuest(TestCase):
    #guest_node.is_guest_node is tested here as well
    def test_no_report_on_non_guest(self):
        self.assertEqual(
            [],
            guest_node.validate_is_not_guest(etree.fromstring("<primitive/>"))
        )

    def test_report_when_is_guest(self):
        assert_report_item_list_equal(
            guest_node.validate_is_not_guest(etree.fromstring("""
                <primitive id="resource_id">
                    <meta_attributes>
                        <nvpair name="remote-node" value="node1" />
                    </meta_attributes>
                </primitive>
            """)),
            [
                (
                    severities.ERROR,
                    report_codes.RESOURCE_IS_GUEST_NODE_ALREADY,
                    {
                        "resource_id": "resource_id",
                    },
                    None
                ),
            ]
        )

class SetAsGuest(TestCase):
    def test_set_guest_meta_correctly(self):
        resource_element = etree.fromstring('<primitive id="A"/>')
        guest_node.set_as_guest(resource_element, "node1", connect_timeout="10")
        assert_xml_equal(
            etree.tostring(resource_element).decode(),
            """
                <primitive id="A">
                    <meta_attributes id="A-meta_attributes">
                        <nvpair id="A-meta_attributes-remote-connect-timeout"
                            name="remote-connect-timeout" value="10"
                        />
                        <nvpair id="A-meta_attributes-remote-node"
                            name="remote-node" value="node1"
                        />
                    </meta_attributes>
                </primitive>
            """
        )

class UnsetGuest(TestCase):
    def test_unset_all_guest_attributes(self):
        resource_element = etree.fromstring("""
            <primitive id="A">
                <meta_attributes id="B">
                    <nvpair id="C" name="remote-node" value="node1"/>
                    <nvpair id="D" name="remote-port" value="2222"/>
                    <nvpair id="E" name="remote-addr" value="node3"/>
                    <nvpair id="F" name="remote-connect-timeout" value="10"/>
                    <nvpair id="G" name="a" value="b"/>
                </meta_attributes>
            </primitive>
        """)
        guest_node.unset_guest(resource_element)
        assert_xml_equal(
            etree.tostring(resource_element).decode(),
            """
                <primitive id="A">
                    <meta_attributes id="B">
                        <nvpair id="G" name="a" value="b"/>
                    </meta_attributes>
                </primitive>
            """
        )

    def test_unset_all_guest_attributes_and_empty_meta_tag(self):
        resource_element = etree.fromstring("""
            <primitive id="A">
                <meta_attributes id="B">
                    <nvpair id="C" name="remote-node" value="node1"/>
                    <nvpair id="D" name="remote-port" value="2222"/>
                    <nvpair id="E" name="remote-addr" value="node3"/>
                    <nvpair id="F" name="remote-connect-timeout" value="10"/>
                </meta_attributes>
            </primitive>
        """)
        guest_node.unset_guest(resource_element)
        assert_xml_equal(
            etree.tostring(resource_element).decode(),
            '<primitive id="A"/>'
        )


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
                etree.tostring(call[1][0]).decode()
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

class GetHost(TestCase):
    def assert_find_host(self, host, xml):
        self.assertEqual(host, guest_node.get_host(etree.fromstring(xml)))

    def test_return_host_from_remote_addr(self):
        self.assert_find_host("HOST", """
            <primitive>
                <meta_attributes>
                    <nvpair name="remote-node" value="NODE" />
                    <nvpair name="remote-addr" value="HOST" />
                </meta_attributes>
            </primitive>
        """)

    def test_return_host_from_remote_node(self):
        self.assert_find_host("HOST", """
            <primitive>
                <meta_attributes>
                    <nvpair name="remote-node" value="HOST" />
                </meta_attributes>
            </primitive>
        """)

    def test_return_none(self):
        self.assert_find_host(None, """
            <primitive>
                <meta_attributes>
                    <nvpair name="any" value="HOST" />
                </meta_attributes>
            </primitive>
        """)

class FindNodeResources(TestCase):
    def assert_return_resources(self, identifier):
        resources_section = etree.fromstring("""
            <resources>
                <primitive id="RESOURCE_ID">
                    <meta_attributes>
                        <nvpair name="remote-node" value="NODE_NAME" />
                        <nvpair name="remote-addr" value="NODE_HOST" />
                    </meta_attributes>
                </primitive>
            </resources>
        """)
        self.assertEquals(
            "RESOURCE_ID",
            guest_node.find_node_resources(resources_section, identifier)[0]
                .attrib["id"]
        )

    def test_return_resources_by_resource_id(self):
        self.assert_return_resources("RESOURCE_ID")

    def test_return_resources_by_node_name(self):
        self.assert_return_resources("NODE_NAME")

    def test_return_resources_by_node_host(self):
        self.assert_return_resources("NODE_HOST")

    def test_no_result_when_no_guest_nodes(self):
        resources_section = etree.fromstring(
            '<resources><primitive id="RESOURCE_ID"/></resources>'
        )
        self.assertEquals([], guest_node.find_node_resources(
            resources_section,
            "RESOURCE_ID"
        ))
