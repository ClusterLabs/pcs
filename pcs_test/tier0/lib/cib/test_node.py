from unittest import mock, TestCase
from lxml import etree

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str

from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.tools import IdProvider
from pcs.lib.pacemaker.state import ClusterState

from pcs.lib.cib import node

# pylint: disable=protected-access


@mock.patch("pcs.lib.cib.node._ensure_node_exists")
class UpdateNodeInstanceAttrs(TestCase):
    def setUp(self):
        self.node1 = etree.fromstring(
            """
            <node id="1" uname="rh73-node1"/>
        """
        )
        self.node2 = etree.fromstring(
            """
            <node id="2" uname="rh73-node2">
                <instance_attributes id="nodes-2">
                    <nvpair name="a" value="A" />
                    <nvpair name="b" value="B" />
                    <nvpair name="c" value="C" />
                </instance_attributes>
            </node>
        """
        )
        self.node3 = etree.fromstring(
            """
            <node id="3" uname="rh73-node3" >
                <instance_attributes id="nodes-3-a">
                    <nvpair name="a" value="A" />
                </instance_attributes>
                <instance_attributes id="nodes-3-b">
                    <nvpair name="b" value="B" />
                </instance_attributes>
            </node>
        """
        )
        self.cib = etree.fromstring(
            self.compile_cib(self.node1, self.node2, self.node3)
        )
        self.state = "node state list"
        self.id_provider = IdProvider(self.cib)

    @staticmethod
    def compile_cib(*node_list):
        parts = ["<cib><configuration><nodes>"]
        parts += [
            node if isinstance(node, str) else etree_to_str(node)
            for node in node_list
        ]
        parts.append("</nodes></configuration></cib>")
        return "".join(parts)

    def test_empty_node(self, mock_get_node):
        mock_get_node.return_value = self.node1
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node1",
            {"x": "X"},
            state_nodes=self.state,
        )
        assert_xml_equal(
            etree_to_str(self.node1),
            """
                <node id="1" uname="rh73-node1">
                    <instance_attributes id="nodes-1">
                        <nvpair id="nodes-1-x" name="x" value="X" />
                    </instance_attributes>
                </node>
            """,
        )

    def test_existing_attrs(self, mock_get_node):
        mock_get_node.return_value = self.node2
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node2",
            {"a": "", "b": "b", "x": "X"},
            state_nodes=self.state,
        )
        assert_xml_equal(
            etree_to_str(self.node2),
            """
                <node id="2" uname="rh73-node2">
                    <instance_attributes id="nodes-2">
                        <nvpair name="b" value="b" />
                        <nvpair name="c" value="C" />
                        <nvpair id="nodes-2-x" name="x" value="X" />
                    </instance_attributes>
                </node>
            """,
        )

    def test_multiple_attrs_sets(self, mock_get_node):
        mock_get_node.return_value = self.node3
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node3",
            {"x": "X"},
            state_nodes=self.state,
        )
        assert_xml_equal(
            etree_to_str(self.node3),
            """
                <node id="3" uname="rh73-node3" >
                    <instance_attributes id="nodes-3-a">
                        <nvpair name="a" value="A" />
                        <nvpair id="nodes-3-a-x" name="x" value="X" />
                    </instance_attributes>
                    <instance_attributes id="nodes-3-b">
                        <nvpair name="b" value="B" />
                    </instance_attributes>
                </node>
            """,
        )

    def test_keep_empty_nvset_and_node(self, mock_get_node):
        mock_get_node.return_value = self.node2
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node2",
            {"a": "", "b": "", "c": ""},
            state_nodes=self.state,
        )
        assert_xml_equal(
            self.compile_cib(
                self.node1,
                """
                    <node id="2" uname="rh73-node2">
                        <instance_attributes id="nodes-2" />
                    </node>
                """,
                self.node3,
            ),
            self.compile_cib(self.node1, self.node2, self.node3),
        )

    def test_dont_create_empty_nvset_if_deleting(self, mock_get_node):
        mock_get_node.return_value = self.node1
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node1",
            {"x": ""},
            state_nodes=self.state,
        )
        assert_xml_equal(
            etree_to_str(self.node1), """<node id="1" uname="rh73-node1" />"""
        )

    def test_dont_create_empty_nvset_if_no_attrs(self, mock_get_node):
        mock_get_node.return_value = self.node1
        node.update_node_instance_attrs(
            self.cib, self.id_provider, "rh73-node1", {}, state_nodes=self.state
        )
        assert_xml_equal(
            etree_to_str(self.node1), """<node id="1" uname="rh73-node1" />"""
        )

    def test_dont_create_empty_node_if_deleting(self, mock_get_node):
        node4 = etree.fromstring("""<node id="4" />""")
        mock_get_node.return_value = node4
        node.update_node_instance_attrs(
            self.cib,
            self.id_provider,
            "rh73-node4",
            {"x": ""},
            state_nodes=self.state,
        )
        assert_xml_equal(
            etree_to_str(self.cib),
            self.compile_cib(self.node1, self.node2, self.node3),
        )


class EnsureNodeExists(TestCase):
    def setUp(self):
        self.node1 = etree.fromstring(
            """
            <node id="1" uname="name-test1" type="member" />
        """
        )
        self.node2 = etree.fromstring(
            """
            <node id="2" uname="name-test2" type="member" />
        """
        )
        self.nodes = etree.Element("nodes")
        self.nodes.append(self.node1)

        self.state = ClusterState(
            """
            <crm_mon version="2.0.3">
                <summary>
                    <stack type="corosync" />
                    <current_dc present="true" />
                    <last_update time="Wed Nov  6 13:45:41 2019" />
                    <last_change time="Wed Nov  6 10:42:54 2019"
                        user="hacluster" client="crmd" origin="node1"
                    />
                    <nodes_configured number="2" />
                    <resources_configured number="0" disabled="0" blocked="0" />
                    <cluster_options stonith-enabled="true"
                        symmetric-cluster="true" no-quorum-policy="stop"
                        maintenance-mode="false"
                    />
                </summary>
                <nodes>
                    <node name="name-test1" id="1" online="true" standby="false"
                        standby_onfail="false" maintenance="false"
                        pending="false" unclean="false" shutdown="false"
                        expected_up="true" is_dc="true" resources_running="0"
                        type="member"
                    />
                    <node name="name-test2" id="2" online="true" standby="false"
                        standby_onfail="false" maintenance="false"
                        pending="false" unclean="false" shutdown="false"
                        expected_up="true" is_dc="false" resources_running="0"
                        type="member"
                    />
                </nodes>
            </crm_mon>
        """
        ).node_section.nodes

    def test_node_already_exists(self):
        assert_xml_equal(
            etree_to_str(node._ensure_node_exists(self.nodes, "name-test1")),
            etree_to_str(self.node1),
        )

    def test_node_missing_no_state(self):
        assert_raise_library_error(
            lambda: node._ensure_node_exists(self.nodes, "name-missing"),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "name-missing", "searched_types": []},
                None,
            ),
        )

    def test_node_missing_not_in_state(self):
        assert_raise_library_error(
            lambda: node._ensure_node_exists(
                self.nodes, "name-missing", self.state
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "name-missing", "searched_types": []},
                None,
            ),
        )

    def test_node_missing_and_gets_created(self):
        assert_xml_equal(
            etree_to_str(
                node._ensure_node_exists(self.nodes, "name-test2", self.state)
            ),
            etree_to_str(self.node2),
        )


class GetNodeByUname(TestCase):
    def setUp(self):
        self.node1 = etree.fromstring(
            """
            <node id="id-test1" uname="name-test1" />
        """
        )
        self.node2 = etree.fromstring(
            """
            <node id="id-test2" uname="name-test2" />
        """
        )
        self.nodes = etree.Element("nodes")
        self.nodes.append(self.node1)
        self.nodes.append(self.node2)

    def test_found(self):
        assert_xml_equal(
            etree_to_str(node._get_node_by_uname(self.nodes, "name-test1")),
            """<node id="id-test1" uname="name-test1" />""",
        )

    def test_not_found(self):
        self.assertTrue(node._get_node_by_uname(self.nodes, "id-test1") is None)


class CreateNode(TestCase):
    def setUp(self):
        self.nodes = etree.Element("nodes")

    def test_minimal(self):
        new_node = node._create_node("id-test", "name-test")
        self.nodes.append(new_node)
        assert_xml_equal(
            """
            <nodes>
                <node id="id-test" uname="name-test" />
            </nodes>
            """,
            etree_to_str(self.nodes),
        )

    def test_with_type(self):
        new_node = node._create_node("id-test", "name-test", "type-test")
        self.nodes.append(new_node)
        assert_xml_equal(
            """
            <nodes>
                <node id="id-test" uname="name-test" type="type-test" />
            </nodes>
            """,
            etree_to_str(self.nodes),
        )
