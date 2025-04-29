from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.cib.resource import guest_node
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.misc import create_setup_patch_mixin

SetupPatchMixin = create_setup_patch_mixin(guest_node)


class ValidateUpdatingGuestAttributes(TestCase):
    def setUp(self):
        self.validate_conflicts_mock = mock.patch(
            "pcs.lib.cib.resource.guest_node.validate_conflicts"
        )
        self.validate_conflicts_mock.return_value = []
        self.validate_conflicts_mock.start()
        self.cib = etree.fromstring("<cib />")

    def tearDown(self):
        self.validate_conflicts_mock.stop()

    def test_no_existing_no_new(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib, [], [], {}, {}, []
            ),
            [],
        )

    def test_no_existing_add_addr(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib, [], [], {"node-addr": "192.168.1.100"}, {}, []
            ),
            [],
        )

    def test_fake_guest_conn_update(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "is_managed": "true",
                    "remote-node": "remote1",
                },
                {
                    "is_managed": "false",
                    "remote-node": "remote1",
                },
                force_flags=[],
            ),
            [],
        )

    def test_existing_guest_add_other(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "is-managed": "false",
                },
                {
                    "remote-node": "remote-1",
                },
                force_flags=[],
            ),
            [],
        )

    def test_existing_guest_update_all(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "remote-2",
                },
                {
                    "remote-node": "remote-1",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE,
                    force_code=report_codes.FORCE,
                )
            ],
        )

    def test_existing_guest_update_all_force(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "remote-2",
                },
                {
                    "remote-node": "remote-1",
                },
                force_flags=[report_codes.FORCE],
            ),
            [fixture.warn(report_codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE)],
        )

    def test_existing_guest_update_addr(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-addr": "192.168.1.100",
                },
                {
                    "remote-node": "remote-1",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE,
                    force_code=report_codes.FORCE,
                )
            ],
        )

    def test_existing_guest_update_addr_force(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-addr": "192.168.1.100",
                },
                {
                    "remote-node": "remote-1",
                },
                force_flags=[report_codes.FORCE],
            ),
            [fixture.warn(report_codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE)],
        )

    def test_existing_guest_update_some(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-addr": "192.168.1.100",
                },
                {
                    "remote-node": "remote-1",
                    "remote-addr": "10.0.0.10",
                    "remote-connect-timeout": "30s",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_REMOVE_AND_ADD_GUEST_NODE,
                    force_code=report_codes.FORCE,
                )
            ],
        )

    def test_remote_addr_exists_add_remote_node(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "remote-1",
                },
                {
                    "remote-addr": "192.168.1.100",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_NODE_ADD_GUEST,
                    force_code=report_codes.FORCE,
                ),
            ],
        )

    def test_remote_addr_exists_add_remote_node_force(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "remote-1",
                },
                {
                    "remote-addr": "192.168.1.100",
                },
                force_flags=[report_codes.FORCE],
            ),
            [
                fixture.warn(report_codes.USE_COMMAND_NODE_ADD_GUEST),
            ],
        )

    def test_remote_addr_exists_update_and_add_remote_node(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "remote-1",
                    "remote-addr": "10.0.0.10",
                },
                {
                    "remote-addr": "192.168.1.100",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_NODE_ADD_GUEST,
                    force_code=report_codes.FORCE,
                ),
            ],
        )

    def test_existing_guest_remove_guest_some(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-addr": "",
                },
                {
                    "remote-node": "remote-1",
                    "remote-addr": "10.0.0.10",
                    "remote-connect-timeout": "30s",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id=None,
                    force_code=report_codes.FORCE,
                )
            ],
        )

    def test_existing_guest_remove_guest_some_force(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-addr": "",
                },
                {
                    "remote-node": "remote-1",
                    "remote-addr": "10.0.0.10",
                    "remote-connect-timeout": "30s",
                },
                force_flags=[report_codes.FORCE],
            ),
            [
                fixture.warn(
                    report_codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id=None,
                )
            ],
        )

    def test_existing_guest_remove_guest_all(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-node": "",
                    "remote-addr": "",
                    "remote_port": "",
                    "remote-connect-timeout": "",
                },
                {
                    "remote-node": "remote-1",
                    "remote-addr": "10.0.0.10",
                    "remote_port": "50000",
                    "remote-connect-timeout": "30s",
                },
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.USE_COMMAND_NODE_REMOVE_GUEST,
                    resource_id=None,
                    force_code=report_codes.FORCE,
                )
            ],
        )

    def test_invalid_remote_port(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-port": "808080",
                },
                {},
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="remote-port",
                    option_value="808080",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_remove_remote_port(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-port": "",
                },
                {
                    "remote-port": "50000",
                },
                force_flags=[],
            ),
            [],
        )

    def test_invalid_remote_timeout(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-connect-timeout": "abc",
                },
                {},
                force_flags=[],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="remote-connect-timeout",
                    option_value="abc",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_remove_remote_timeout(self):
        assert_report_item_list_equal(
            guest_node.validate_updating_guest_attributes(
                self.cib,
                [],
                [],
                {
                    "remote-connect-timeout": "",
                },
                {
                    "remote-connect-timeout": "30s",
                },
                force_flags=[],
            ),
            [],
        )


class ValidateHostConflicts(TestCase):
    @staticmethod
    def validate(node_name, options):
        tree = etree.fromstring(
            """
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
        """
        )
        existing_nodes_names = ["R1", "B", "GUEST_CONFLICT", "some"]
        existing_nodes_addrs = [
            "RING0",
            "RING1",
            "REMOTE_CONFLICT",
            "GUEST_CONFLICT",
            "GUEST_ADDR_CONFLICT",
        ]
        return guest_node.validate_conflicts(
            tree, existing_nodes_names, existing_nodes_addrs, node_name, options
        )

    def assert_node_name_already_exists_error(
        self, report_node_name, node_name, options=None
    ):
        assert_report_item_list_equal(
            self.validate(node_name, options if options else {}),
            [
                fixture.error(
                    report_codes.GUEST_NODE_NAME_ALREADY_EXISTS,
                    node_name=report_node_name,
                )
            ],
        )

    def assert_remote_addr_already_exists_error(self, node_name, options):
        assert_report_item_list_equal(
            self.validate(node_name, options),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=[options["remote-addr"]],
                )
            ],
        )

    def test_report_conflict_with_id(self):
        self.assert_node_name_already_exists_error("CONFLICT", "CONFLICT")

    def test_report_conflict_guest_node(self):
        self.assert_node_name_already_exists_error(
            "GUEST_CONFLICT", "GUEST_CONFLICT"
        )

    def test_report_conflict_guest_addr(self):
        self.assert_node_name_already_exists_error(
            "GUEST_ADDR_CONFLICT",
            "GUEST_ADDR_CONFLICT",
        )

    def test_report_conflict_guest_addr_by_addr(self):
        self.assert_node_name_already_exists_error(
            "GUEST_ADDR_CONFLICT",
            "GUEST_ADDR_CONFLICT",
        )

    def test_no_conflict_guest_node_when_addr_is_different(self):
        self.assertEqual(
            [],
            self.validate(
                "GUEST_ADDR_CONFLICT",
                {
                    "remote-addr": "different",
                },
            ),
        )

    def test_report_conflict_remote_node(self):
        self.assert_node_name_already_exists_error(
            "REMOTE_CONFLICT", "REMOTE_CONFLICT"
        )

    def test_no_conflict_remote_node_when_addr_is_different(self):
        self.assertEqual(
            [],
            self.validate(
                "REMOTE_CONFLICT",
                {
                    "remote-addr": "different",
                },
            ),
        )

    def test_report_conflict_remote_node_by_addr(self):
        self.assert_remote_addr_already_exists_error(
            "REMOTE_CONFLICT",
            {
                "remote-addr": "REMOTE_CONFLICT",
            },
        )


class ValidateOptions(TestCase):
    @staticmethod
    def validate(options, name="some_name"):
        return guest_node.validate_set_as_guest(
            etree.fromstring("<cib/>"),
            ["EXISTING-HOST-NAME"],
            ["EXISTING-HOST-RING0", "EXISTING-HOST-RING0"],
            name,
            options,
        )

    def test_no_report_on_valid(self):
        self.assertEqual([], self.validate({}, "node1"))

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
                    None,
                ),
            ],
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
                        "allowed_values": (
                            "time interval (e.g. 1, 2s, 3m, 4h, ...)"
                        ),
                        "cannot_be_empty": False,
                        "forbidden_characters": None,
                    },
                    None,
                ),
            ],
        )

    def test_report_invalid_node_name(self):
        assert_report_item_list_equal(
            self.validate({}, "EXISTING-HOST-NAME"),
            [
                fixture.error(
                    report_codes.GUEST_NODE_NAME_ALREADY_EXISTS,
                    node_name="EXISTING-HOST-NAME",
                )
            ],
        )


class ValidateIsNotGuest(TestCase):
    # guest_node.is_guest_node is tested here as well
    def test_no_report_on_non_guest(self):
        self.assertEqual(
            [],
            guest_node.validate_is_not_guest(etree.fromstring("<primitive/>")),
        )

    def test_report_when_is_guest(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            guest_node.validate_is_not_guest(
                etree.fromstring(
                    """
                <primitive id="resource_id">
                    <meta_attributes>
                        <nvpair name="remote-node" value="node1" />
                    </meta_attributes>
                </primitive>
            """
                )
            ),
            [
                (
                    severities.ERROR,
                    report_codes.RESOURCE_IS_GUEST_NODE_ALREADY,
                    {
                        "resource_id": "resource_id",
                    },
                    None,
                ),
            ],
        )


class SetAsGuest(TestCase):
    def test_set_guest_meta_correctly(self):
        # pylint: disable=no-self-use
        resource_element = etree.fromstring('<primitive id="A"/>')
        guest_node.set_as_guest(
            resource_element,
            IdProvider(resource_element),
            "node1",
            connect_timeout="10",
        )
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
            """,
        )


class UnsetGuest(TestCase):
    def test_unset_all_guest_attributes(self):
        # pylint: disable=no-self-use
        resource_element = etree.fromstring(
            """
            <primitive id="A">
                <meta_attributes id="B">
                    <nvpair id="C" name="remote-node" value="node1"/>
                    <nvpair id="D" name="remote-port" value="2222"/>
                    <nvpair id="E" name="remote-addr" value="node3"/>
                    <nvpair id="F" name="remote-connect-timeout" value="10"/>
                    <nvpair id="G" name="a" value="b"/>
                </meta_attributes>
            </primitive>
        """
        )
        guest_node.unset_guest(resource_element)
        assert_xml_equal(
            etree.tostring(resource_element).decode(),
            """
                <primitive id="A">
                    <meta_attributes id="B">
                        <nvpair id="G" name="a" value="b"/>
                    </meta_attributes>
                </primitive>
            """,
        )

    def test_unset_all_guest_attributes_and_empty_meta_tag(self):
        # pylint: disable=no-self-use
        resource_element = etree.fromstring(
            """
            <primitive id="A">
                <meta_attributes id="B">
                    <nvpair id="C" name="remote-node" value="node1"/>
                    <nvpair id="D" name="remote-port" value="2222"/>
                    <nvpair id="E" name="remote-addr" value="node3"/>
                    <nvpair id="F" name="remote-connect-timeout" value="10"/>
                </meta_attributes>
            </primitive>
        """
        )
        guest_node.unset_guest(resource_element)
        assert_xml_equal(
            etree.tostring(resource_element).decode(),
            """
            <primitive id="A">
                <meta_attributes id="B" />
            </primitive>
            """,
        )


class FindNodeList(TestCase, SetupPatchMixin):
    def assert_nodes_equals(self, xml, expected_nodes):
        self.assertEqual(
            expected_nodes, guest_node.find_node_list(etree.fromstring(xml))
        )

    def test_get_no_nodes_when_no_primitives(self):
        self.assert_nodes_equals("<resources/>", [])

    def test_get_no_nodes_when_no_meta_remote_node(self):
        self.assert_nodes_equals(
            """
            <resources>
                <primitive>
                    <meta_attributes>
                        <nvpair name="remote-addr" value="G1"/>
                    </meta_attributes>
                </primitive>
            </resources>
            """,
            [],
        )

    def test_get_multiple_nodes(self):
        self.assert_nodes_equals(
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
                PacemakerNode("G1", "G1addr"),
                PacemakerNode("G2", "G2"),
            ],
        )


class GetNodeNameFromResource(TestCase):
    def assert_find_name(self, name, xml):
        self.assertEqual(
            name, guest_node.get_node_name_from_resource(etree.fromstring(xml))
        )

    def test_return_name_ignore_remote_addr(self):
        self.assert_find_name(
            "NODE",
            """
            <primitive>
                <meta_attributes>
                    <nvpair name="remote-node" value="NODE" />
                    <nvpair name="remote-addr" value="HOST" />
                </meta_attributes>
            </primitive>
        """,
        )

    def test_return_name_from_remote_node(self):
        self.assert_find_name(
            "HOST",
            """
            <primitive>
                <meta_attributes>
                    <nvpair name="remote-node" value="HOST" />
                </meta_attributes>
            </primitive>
        """,
        )

    def test_return_none(self):
        self.assert_find_name(
            None,
            """
            <primitive>
                <meta_attributes>
                    <nvpair name="any" value="HOST" />
                </meta_attributes>
            </primitive>
        """,
        )


class FindNodeResources(TestCase):
    def assert_return_resources(
        self, identifier, resources_section_xml=None, found=True
    ):
        if resources_section_xml is None:
            resources_section_xml = """
                <resources>
                    <primitive id="RESOURCE_ID">
                        <meta_attributes>
                            <nvpair name="remote-node" value="NODE_NAME" />
                            <nvpair name="remote-addr" value="NODE_HOST" />
                        </meta_attributes>
                    </primitive>
                </resources>
            """
        resources_section = etree.fromstring(resources_section_xml)
        resources = guest_node.find_node_resources(
            resources_section, identifier
        )
        if not found:
            self.assertEqual([], resources)
        else:
            self.assertTrue(resources)
            self.assertEqual("RESOURCE_ID", resources[0].attrib["id"])

    def test_return_resources_by_resource_id(self):
        self.assert_return_resources("RESOURCE_ID")

    def test_return_resources_by_node_name(self):
        self.assert_return_resources("NODE_NAME")

    def test_return_resources_by_node_host(self):
        self.assert_return_resources("NODE_HOST")

    def test_no_result_when_no_guest_nodes(self):
        self.assert_return_resources(
            "RESOURCE_ID",
            '<resources><primitive id="RESOURCE_ID"/></resources>',
            found=False,
        )

    def test_remote_node_meta_is_enough_1(self):
        self.assert_return_resources(
            "RESOURCE_ID",
            """
                <resources>
                    <primitive id="RESOURCE_ID">
                        <meta_attributes>
                            <nvpair name="remote-node" value="NODE_NAME" />
                        </meta_attributes>
                    </primitive>
                </resources>
            """,
        )

    def test_remote_node_meta_is_enough_2(self):
        self.assert_return_resources(
            "NODE_NAME",
            """
                <resources>
                    <primitive id="RESOURCE_ID">
                        <meta_attributes>
                            <nvpair name="remote-node" value="NODE_NAME" />
                        </meta_attributes>
                    </primitive>
                </resources>
            """,
        )

    def test_remote_addr_is_not_enough_1(self):
        self.assert_return_resources(
            "RESOURCE_ID",
            """
                <resources>
                    <primitive id="RESOURCE_ID">
                        <meta_attributes>
                            <nvpair name="remote-addr" value="NODE_HOST" />
                        </meta_attributes>
                    </primitive>
                </resources>
            """,
            found=False,
        )

    def test_remote_addr_is_not_enough_2(self):
        self.assert_return_resources(
            "NODE_NAME",
            """
                <resources>
                    <primitive id="RESOURCE_ID">
                        <meta_attributes>
                            <nvpair name="remote-addr" value="NODE_HOST" />
                        </meta_attributes>
                    </primitive>
                </resources>
            """,
            found=False,
        )
