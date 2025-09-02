from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs import settings
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.pacemaker import state
from pcs.lib.pacemaker.state import (
    ClusterState,
    _Attrs,
    _Children,
)

from pcs_test.tools.assertions import assert_report_item_equal
from pcs_test.tools.fixture_crm_mon import complete_state
from pcs_test.tools.misc import get_test_resource as rc


class AttrsTest(TestCase):
    def test_get_declared_attr(self):
        attrs = _Attrs("test", {"node-name": "node1"}, {"name": "node-name"})
        self.assertEqual("node1", attrs.name)

    def test_raises_on_undeclared_attribute(self):
        attrs = _Attrs("test", {"node-name": "node1"}, {})
        self.assertRaises(AttributeError, lambda: attrs.name)

    def test_raises_on_missing_required_attribute(self):
        attrs = _Attrs("test", {}, {"name": "node-name"})
        self.assertRaises(AttributeError, lambda: attrs.name)

    def test_attr_transformation_success(self):
        attrs = _Attrs("test", {"number": "7"}, {"count": ("number", int)})
        self.assertEqual(7, attrs.count)

    def test_attr_transformation_fail(self):
        attrs = _Attrs("test", {"number": "abc"}, {"count": ("number", int)})
        self.assertRaises(ValueError, lambda: attrs.count)


class ChildrenTest(TestCase):
    def setUp(self):
        self.dom = etree.fromstring(
            '<main><some name="0"/><any name="1"/><any name="2"/></main>'
        )

    def wrap(self, element):
        # pylint: disable=no-self-use
        return "{0}.{1}".format(element.tag, element.attrib["name"])

    def test_get_declared_section(self):
        children = _Children(
            "test", self.dom, {}, {"some_section": ("some", self.wrap)}
        )
        self.assertEqual("some.0", children.some_section)

    def test_get_declared_children(self):
        children = _Children("test", self.dom, {"anys": ("any", self.wrap)}, {})
        self.assertEqual(["any.1", "any.2"], children.anys)

    def test_raises_on_undeclared_children(self):
        children = _Children("test", self.dom, {}, {})
        self.assertRaises(AttributeError, lambda: children.some_section)


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_rng/api/api-result.rng")
)
class WorkWithClusterStatusNodesTest(TestCase):
    def test_can_get_node_names(self):
        with open(rc("crm_mon.minimal.xml")) as crm_mon_file:
            crm_mon_xml = crm_mon_file.read()
        state_dom = complete_state(
            crm_mon_xml,
            nodes_xml="""
                <nodes>
                    <node name="node1" id="1" />
                    <node name="node2" id="2" />
                </nodes>
            """,
        )
        self.assertEqual(
            ["node1", "node2"],
            [
                node.attrs.name
                for node in ClusterState(state_dom).node_section.nodes
            ],
        )

    def test_can_filter_out_remote_nodes(self):
        with open(rc("crm_mon.minimal.xml")) as crm_mon_file:
            crm_mon_xml = crm_mon_file.read()
        state_dom = complete_state(
            crm_mon_xml,
            nodes_xml="""
                <nodes>
                    <node name="node1" id="1" />
                    <node name="node2" id="2" type="remote" />
                </nodes>
            """,
        )
        self.assertEqual(
            ["node1"],
            [
                node.attrs.name
                for node in ClusterState(state_dom).node_section.nodes
                if node.attrs.type != "remote"
            ],
        )


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_rng/api/api-result.rng")
)
class WorkWithClusterStatusSummaryTest(TestCase):
    def test_nodes_count(self):
        with open(rc("crm_mon.minimal.xml")) as crm_mon_file:
            crm_mon_xml = crm_mon_file.read()
        self.assertEqual(
            0,
            ClusterState(complete_state(crm_mon_xml)).summary.nodes.attrs.count,
        )

    def test_resources_count(self):
        with open(rc("crm_mon.minimal.xml")) as crm_mon_file:
            crm_mon_xml = crm_mon_file.read()
        self.assertEqual(
            0,
            ClusterState(
                complete_state(crm_mon_xml)
            ).summary.resources.attrs.count,
        )


class GetPrimitiveRolesWithNodes(TestCase):
    def test_success(self):
        primitives_xml = [
            """
                <resource id="A" role="Started">
                    <node name="node1" id="1"/>
                </resource>
            """,
            """
                <resource id="A" role="Master">
                    <node name="node2" id="2"/>
                </resource>
            """,
            """
                <resource id="A" role="Slave">
                    <node name="node4" id="4"/>
                </resource>
            """,
            """
                <resource id="A" role="Unpromoted">
                    <node name="node3" id="3"/>
                </resource>
            """,
            """
                <resource id="A" role="Stopped">
                </resource>
            """,
            """
                <resource id="A" role="Started">
                    <node name="node5" id="5"/>
                </resource>
            """,
            """
                <resource id="A" role="Promoted">
                    <node name="node6" id="6"/>
                </resource>
            """,
        ]
        primitives = [etree.fromstring(xml) for xml in primitives_xml]

        self.assertEqual(
            # pylint: disable=protected-access
            state._get_primitive_roles_with_nodes(primitives),
            {
                "Started": ["node1", "node5"],
                "Promoted": ["node2", "node6"],
                "Unpromoted": ["node3", "node4"],
            },
        )

    def test_empty(self):
        # pylint: disable=protected-access
        self.assertEqual(state._get_primitive_roles_with_nodes([]), {})


class GetPrimitivesForStateCheck(TestCase):
    # pylint: disable=too-many-public-methods
    status_xml = etree.fromstring(
        """
        <resources>
            <resource id="R01" failed="false" />
            <resource id="R02" failed="true" />

            <group id="G1">
                <resource id="R03" failed="false" />
                <resource id="R04" failed="false" />
            </group>
            <group id="G2">
                <resource id="R05" failed="true" />
                <resource id="R06" failed="true" />
            </group>

            <clone id="R07-clone">
                <resource id="R07" failed="false" />
                <resource id="R07" failed="false" />
            </clone>
            <clone id="R08-clone">
                <resource id="R08" failed="true" />
                <resource id="R08" failed="false" />
            </clone>
            <clone id="R09-clone">
                <resource id="R09" failed="true" />
                <resource id="R09" failed="true" />
            </clone>

            <clone id="R10-clone">
                <resource id="R10:0" failed="false" />
                <resource id="R10:1" failed="false" />
            </clone>
            <clone id="R11-clone">
                <resource id="R11:0" failed="false" />
                <resource id="R11:1" failed="true" />
            </clone>
            <clone id="R12-clone">
                <resource id="R12:0" failed="true" />
                <resource id="R12:1" failed="true" />
            </clone>

            <clone id="G3-clone">
                <group id="G3:0">
                    <resource id="R13" failed="false" />
                    <resource id="R14" failed="false" />
                </group>
                <group id="G3:1">
                    <resource id="R13" failed="false" />
                    <resource id="R14" failed="false" />
                </group>
            </clone>
            <clone id="G4-clone">
                <group id="G4:0">
                    <resource id="R15" failed="true" />
                    <resource id="R16" failed="true" />
                </group>
                <group id="G4:1">
                    <resource id="R15" failed="false" />
                    <resource id="R16" failed="false" />
                </group>
            </clone>
            <clone id="G5-clone">
                <group id="G5:0">
                    <resource id="R17" failed="true" />
                    <resource id="R18" failed="true" />
                </group>
                <group id="G5:1">
                    <resource id="R17" failed="true" />
                    <resource id="R18" failed="true" />
                </group>
            </clone>

            <clone id="G6-clone" managed="true">
                <group id="G6:0">
                    <resource id="R19:0" failed="false" />
                    <resource id="R20:0" failed="false" />
                </group>
                <group id="G6:1">
                    <resource id="R19:1" failed="false" />
                    <resource id="R20:1" failed="false" />
                </group>
            </clone>
            <clone id="G7-clone" managed="true">
                <group id="G7:0">
                    <resource id="R21:0" failed="true" />
                    <resource id="R22:0" failed="true" />
                </group>
                <group id="G7:1">
                    <resource id="R21:1" failed="false" />
                    <resource id="R22:1" failed="false" />
                </group>
            </clone>
            <clone id="G8-clone" managed="true">
                <group id="G8:0">
                    <resource id="R23:0" failed="true" />
                    <resource id="R24:0" failed="true" />
                </group>
                <group id="G8:1">
                    <resource id="R23:1" failed="true" />
                    <resource id="R24:1" failed="true" />
                </group>
            </clone>
            <bundle id="B1" managed="true">
                <replica id="0">
                    <resource id="B1-R1" failed="false" />
                    <resource id="B1-R2" failed="false" />
                </replica>
            </bundle>
            <bundle id="B2" managed="true">
                <replica id="0">
                    <resource id="B2-R1" failed="true" />
                    <resource id="B2-R2" failed="false" />
                </replica>
                <replica id="1">
                    <resource id="B2-R1" failed="false" />
                    <resource id="B2-R2" failed="false" />
                </replica>
            </bundle>
        </resources>
    """
    )

    def setUp(self):
        self.status = etree.parse(rc("crm_mon.minimal.xml")).getroot()
        self.status.append(self.status_xml)
        for resource in self.status.xpath(".//resource"):
            resource.attrib.update(
                {
                    "resource_agent": "ocf::pacemaker:Stateful",
                    "role": "Started",
                    "active": "true",
                    "orphaned": "false",
                    "blocked": "false",
                    "managed": "true",
                    "failure_ignored": "false",
                    "nodes_running_on": "1",
                }
            )

    def assert_primitives(self, resource_id, primitive_ids, expected_running):
        self.assertEqual(
            [
                elem.attrib["id"]
                # pylint: disable=protected-access
                for elem in state._get_primitives_for_state_check(
                    self.status, resource_id, expected_running
                )
            ],
            primitive_ids,
        )

    def test_missing(self):
        self.assert_primitives("Rxx", [], True)
        self.assert_primitives("Rxx", [], False)

    def test_primitive(self):
        self.assert_primitives("R01", ["R01"], True)
        self.assert_primitives("R01", ["R01"], False)

    def test_primitive_failed(self):
        self.assert_primitives("R02", [], True)
        self.assert_primitives("R02", [], False)

    def test_group(self):
        self.assert_primitives("G1", ["R04"], True)
        self.assert_primitives("G1", ["R03"], False)

    def test_group_failed_primitive(self):
        self.assert_primitives("G2", [], True)
        self.assert_primitives("G2", [], False)

    def test_primitive_in_group(self):
        self.assert_primitives("R03", ["R03"], True)
        self.assert_primitives("R03", ["R03"], False)

    def test_primitive_in_group_failed(self):
        self.assert_primitives("R05", [], True)
        self.assert_primitives("R05", [], False)

    def test_clone(self):
        self.assert_primitives("R07-clone", ["R07", "R07"], True)
        self.assert_primitives("R07-clone", ["R07", "R07"], False)
        self.assert_primitives("R10-clone", ["R10:0", "R10:1"], True)
        self.assert_primitives("R10-clone", ["R10:0", "R10:1"], False)

    def test_clone_partially_failed(self):
        self.assert_primitives("R08-clone", ["R08"], True)
        self.assert_primitives("R08-clone", ["R08"], False)
        self.assert_primitives("R11-clone", ["R11:0"], True)
        self.assert_primitives("R11-clone", ["R11:0"], False)

    def test_clone_failed(self):
        self.assert_primitives("R09-clone", [], True)
        self.assert_primitives("R09-clone", [], False)
        self.assert_primitives("R12-clone", [], True)
        self.assert_primitives("R12-clone", [], False)

    def test_primitive_in_clone(self):
        self.assert_primitives("R07", ["R07", "R07"], True)
        self.assert_primitives("R07", ["R07", "R07"], False)
        self.assert_primitives("R10", ["R10:0", "R10:1"], True)
        self.assert_primitives("R10", ["R10:0", "R10:1"], False)

    def test_primitive_in_clone_partially_failed(self):
        self.assert_primitives("R08", ["R08"], True)
        self.assert_primitives("R08", ["R08"], False)
        self.assert_primitives("R11", ["R11:0"], True)
        self.assert_primitives("R11", ["R11:0"], False)

    def test_primitive_in_clone_failed(self):
        self.assert_primitives("R09", [], True)
        self.assert_primitives("R09", [], False)
        self.assert_primitives("R12", [], True)
        self.assert_primitives("R12", [], False)

    def test_clone_containing_group(self):
        self.assert_primitives("G3-clone", ["R14", "R14"], True)
        self.assert_primitives("G3-clone", ["R13", "R13"], False)
        self.assert_primitives("G6-clone", ["R20:0", "R20:1"], True)
        self.assert_primitives("G6-clone", ["R19:0", "R19:1"], False)

    def test_clone_containing_group_partially_failed(self):
        self.assert_primitives("G4-clone", ["R16"], True)
        self.assert_primitives("G4-clone", ["R15"], False)
        self.assert_primitives("G7-clone", ["R22:1"], True)
        self.assert_primitives("G7-clone", ["R21:1"], False)

    def test_clone_containing_group_failed(self):
        self.assert_primitives("G5-clone", [], True)
        self.assert_primitives("G5-clone", [], False)
        self.assert_primitives("G8-clone", [], True)
        self.assert_primitives("G8-clone", [], False)

    def test_group_in_clone_containing_group(self):
        self.assert_primitives("G3", ["R14", "R14"], True)
        self.assert_primitives("G3", ["R13", "R13"], False)
        self.assert_primitives("G6", ["R20:0", "R20:1"], True)
        self.assert_primitives("G6", ["R19:0", "R19:1"], False)

    def test_group_in_clone_containing_group_partially_failed(self):
        self.assert_primitives("G4", ["R16"], True)
        self.assert_primitives("G4", ["R15"], False)
        self.assert_primitives("G7", ["R22:1"], True)
        self.assert_primitives("G7", ["R21:1"], False)

    def test_group_in_clone_containing_group_failed(self):
        self.assert_primitives("G5", [], True)
        self.assert_primitives("G5", [], False)
        self.assert_primitives("G8", [], True)
        self.assert_primitives("G8", [], False)

    def test_primitive_in_clone_containing_group(self):
        self.assert_primitives("R14", ["R14", "R14"], True)
        self.assert_primitives("R14", ["R14", "R14"], False)
        self.assert_primitives("R20", ["R20:0", "R20:1"], True)
        self.assert_primitives("R20", ["R20:0", "R20:1"], False)

    def test_primitive_in_clone_containing_group_partially_failed(self):
        self.assert_primitives("R16", ["R16"], True)
        self.assert_primitives("R16", ["R16"], False)
        self.assert_primitives("R22", ["R22:1"], True)
        self.assert_primitives("R22", ["R22:1"], False)

    def test_primitive_in_clone_containing_group_failed(self):
        self.assert_primitives("R18", [], True)
        self.assert_primitives("R18", [], False)
        self.assert_primitives("R24", [], True)
        self.assert_primitives("R24", [], False)

    def test_bundle(self):
        self.assert_primitives("B1", ["B1-R1", "B1-R2"], True)
        self.assert_primitives("B1", ["B1-R1", "B1-R2"], False)
        self.assert_primitives("B2", ["B2-R2", "B2-R1", "B2-R2"], True)
        self.assert_primitives("B2", ["B2-R2", "B2-R1", "B2-R2"], False)

    def test_primitive_in_bundle(self):
        self.assert_primitives("B1-R1", ["B1-R1"], True)
        self.assert_primitives("B1-R1", ["B1-R1"], False)
        self.assert_primitives("B2-R1", ["B2-R1"], True)
        self.assert_primitives("B2-R1", ["B2-R1"], False)
        self.assert_primitives("B2-R2", ["B2-R2", "B2-R2"], True)
        self.assert_primitives("B2-R2", ["B2-R2", "B2-R2"], False)


class CommonResourceState(TestCase):
    resource_id = "R"

    def setUp(self):
        self.cluster_state = "state"

        patcher_primitives = mock.patch(
            "pcs.lib.pacemaker.state._get_primitives_for_state_check"
        )
        self.addCleanup(patcher_primitives.stop)
        self.get_primitives_for_state_check = patcher_primitives.start()

        patcher_roles = mock.patch(
            "pcs.lib.pacemaker.state._get_primitive_roles_with_nodes"
        )
        self.addCleanup(patcher_roles.stop)
        self.get_primitive_roles_with_nodes = patcher_roles.start()

    def fixture_running_state_info(self):
        # pylint: disable=no-self-use
        return {
            "Started": ["node1"],
            "Promoted": ["node2"],
            "Unpromoted": ["node3", "node4"],
        }

    def fixture_running_report(self, severity):
        return (
            severity,
            report_codes.RESOURCE_RUNNING_ON_NODES,
            {
                "resource_id": self.resource_id,
                "roles_with_nodes": self.fixture_running_state_info(),
            },
        )

    def fixture_not_running_report(self, severity):
        return (
            severity,
            report_codes.RESOURCE_DOES_NOT_RUN,
            {"resource_id": self.resource_id},
        )


class EnsureResourceState(CommonResourceState):
    def assert_running_info_transform(self, run_info, report, expected_running):
        self.get_primitives_for_state_check.return_value = ["elem1", "elem2"]
        self.get_primitive_roles_with_nodes.return_value = run_info
        assert_report_item_equal(
            state.ensure_resource_state(
                expected_running, self.cluster_state, self.resource_id
            ),
            report,
        )
        self.get_primitives_for_state_check.assert_called_once_with(
            self.cluster_state, self.resource_id, expected_running
        )
        self.get_primitive_roles_with_nodes.assert_called_once_with(
            ["elem1", "elem2"]
        )

    def test_report_info_running(self):
        self.assert_running_info_transform(
            self.fixture_running_state_info(),
            self.fixture_running_report(severities.INFO),
            expected_running=True,
        )

    def test_report_error_running(self):
        self.assert_running_info_transform(
            self.fixture_running_state_info(),
            self.fixture_running_report(severities.ERROR),
            expected_running=False,
        )

    def test_report_error_not_running(self):
        self.assert_running_info_transform(
            [],
            self.fixture_not_running_report(severities.ERROR),
            expected_running=True,
        )

    def test_report_info_not_running(self):
        self.assert_running_info_transform(
            [],
            self.fixture_not_running_report(severities.INFO),
            expected_running=False,
        )


class InfoResourceState(CommonResourceState):
    def assert_running_info_transform(self, run_info, report):
        self.get_primitives_for_state_check.return_value = ["elem1", "elem2"]
        self.get_primitive_roles_with_nodes.return_value = run_info
        assert_report_item_equal(
            state.info_resource_state(self.cluster_state, self.resource_id),
            report,
        )
        self.get_primitives_for_state_check.assert_called_once_with(
            self.cluster_state, self.resource_id, expected_running=True
        )
        self.get_primitive_roles_with_nodes.assert_called_once_with(
            ["elem1", "elem2"]
        )

    def test_report_info_running(self):
        self.assert_running_info_transform(
            self.fixture_running_state_info(),
            self.fixture_running_report(severities.INFO),
        )

    def test_report_info_not_running(self):
        self.assert_running_info_transform(
            [], self.fixture_not_running_report(severities.INFO)
        )


class IsResourceManaged(TestCase):
    status_xml = etree.fromstring(
        """
        <resources>
            <resource id="R01" managed="true" />
            <resource id="R02" managed="false" />

            <group id="G1">
                <resource id="R03" managed="true" />
                <resource id="R04" managed="true" />
            </group>
            <group id="G2">
                <resource id="R05" managed="false" />
                <resource id="R06" managed="true" />
            </group>
            <group id="G3">
                <resource id="R07" managed="true" />
                <resource id="R08" managed="false" />
            </group>
            <group id="G4">
                <resource id="R09" managed="false" />
                <resource id="R10" managed="false" />
            </group>

            <clone id="R11-clone" managed="true">
                <resource id="R11" managed="true" />
                <resource id="R11" managed="true" />
            </clone>
            <clone id="R12-clone" managed="true">
                <resource id="R12" managed="false" />
                <resource id="R12" managed="false" />
            </clone>
            <clone id="R13-clone" managed="false">
                <resource id="R13" managed="true" />
                <resource id="R13" managed="true" />
            </clone>
            <clone id="R14-clone" managed="false">
                <resource id="R14" managed="false" />
                <resource id="R14" managed="false" />
            </clone>

            <clone id="R15-clone" managed="true">
                <resource id="R15:0" managed="true" />
                <resource id="R15:1" managed="true" />
            </clone>
            <clone id="R16-clone" managed="true">
                <resource id="R16:0" managed="false" />
                <resource id="R16:1" managed="false" />
            </clone>
            <clone id="R17-clone" managed="false">
                <resource id="R17:0" managed="true" />
                <resource id="R17:1" managed="true" />
            </clone>
            <clone id="R18-clone" managed="false">
                <resource id="R18:0" managed="false" />
                <resource id="R18:1" managed="false" />
            </clone>

            <clone id="G5-clone" managed="true">
                <group id="G5:0">
                    <resource id="R19" managed="true" />
                    <resource id="R20" managed="true" />
                </group>
                <group id="G5:1">
                    <resource id="R19" managed="true" />
                    <resource id="R20" managed="true" />
                </group>
            </clone>
            <clone id="G6-clone" managed="false">
                <group id="G6:0">
                    <resource id="R21" managed="true" />
                    <resource id="R22" managed="true" />
                </group>
                <group id="G6:1">
                    <resource id="R21" managed="true" />
                    <resource id="R22" managed="true" />
                </group>
            </clone>
            <clone id="G7-clone" managed="true">
                <group id="G7:0">
                    <resource id="R23" managed="false" />
                    <resource id="R24" managed="true" />
                </group>
                <group id="G7:1">
                    <resource id="R23" managed="false" />
                    <resource id="R24" managed="true" />
                </group>
            </clone>
            <clone id="G8-clone" managed="true">
                <group id="G8:0">
                    <resource id="R25" managed="true" />
                    <resource id="R26" managed="false" />
                </group>
                <group id="G8:1">
                    <resource id="R25" managed="true" />
                    <resource id="R26" managed="false" />
                </group>
            </clone>
            <clone id="G9-clone" managed="false">
                <group id="G9:0">
                    <resource id="R27" managed="false" />
                    <resource id="R28" managed="false" />
                </group>
                <group id="G9:1">
                    <resource id="R27" managed="false" />
                    <resource id="R28" managed="false" />
                </group>
            </clone>

            <clone id="G10-clone" managed="true">
                <group id="G10:0">
                    <resource id="R29:0" managed="true" />
                    <resource id="R30:0" managed="true" />
                </group>
                <group id="G10:1">
                    <resource id="R29:1" managed="true" />
                    <resource id="R30:1" managed="true" />
                </group>
            </clone>
            <clone id="G11-clone" managed="false">
                <group id="G11:0">
                    <resource id="R31:0" managed="true" />
                    <resource id="R32:0" managed="true" />
                </group>
                <group id="G11:1">
                    <resource id="R31:1" managed="true" />
                    <resource id="R32:1" managed="true" />
                </group>
            </clone>
            <clone id="G12-clone" managed="true">
                <group id="G12:0">
                    <resource id="R33:0" managed="false" />
                    <resource id="R34:0" managed="true" />
                </group>
                <group id="G12:1">
                    <resource id="R33:1" managed="false" />
                    <resource id="R34:1" managed="true" />
                </group>
            </clone>
            <clone id="G13-clone" managed="true">
                <group id="G13:0">
                    <resource id="R35:0" managed="true" />
                    <resource id="R36:0" managed="false" />
                </group>
                <group id="G13:1">
                    <resource id="R35:1" managed="true" />
                    <resource id="R36:1" managed="false" />
                </group>
            </clone>
            <clone id="G14-clone" managed="false">
                <group id="G14:0">
                    <resource id="R37:0" managed="false" />
                    <resource id="R38:0" managed="false" />
                </group>
                <group id="G14:1">
                    <resource id="R37:1" managed="false" />
                    <resource id="R38:1" managed="false" />
                </group>
            </clone>

            <bundle id="B1" managed="true" />
            <bundle id="B2" managed="false" />

            <bundle id="B3" managed="true">
                <replica id="0">
                    <resource id="R39" managed="true" />
                    <resource id="R40" managed="true" />
                </replica>
                <replica id="1">
                    <resource id="R39" managed="true" />
                    <resource id="R40" managed="true" />
                </replica>
            </bundle>
            <bundle id="B4" managed="false">
                <replica id="0">
                    <resource id="R41" managed="true" />
                    <resource id="R42" managed="true" />
                </replica>
                <replica id="1">
                    <resource id="R41" managed="true" />
                    <resource id="R42" managed="true" />
                </replica>
            </bundle>
            <bundle id="B5" managed="true">
                <replica id="0">
                    <resource id="R43" managed="false" />
                    <resource id="R44" managed="true" />
                </replica>
                <replica id="1">
                    <resource id="R43" managed="false" />
                    <resource id="R44" managed="true" />
                </replica>
            </bundle>
            <bundle id="B6" managed="true">
                <replica id="0">
                    <resource id="R45" managed="true" />
                    <resource id="R46" managed="false" />
                </replica>
                <replica id="1">
                    <resource id="R45" managed="true" />
                    <resource id="R46" managed="false" />
                </replica>
            </bundle>
            <bundle id="B7" managed="false">
                <replica id="0">
                    <resource id="R47" managed="false" />
                    <resource id="R48" managed="false" />
                </replica>
                <replica id="1">
                    <resource id="R47" managed="false" />
                    <resource id="R48" managed="false" />
                </replica>
            </bundle>
        </resources>
    """
    )

    def setUp(self):
        self.status = etree.parse(rc("crm_mon.minimal.xml")).getroot()
        self.status.append(self.status_xml)
        for resource in self.status.xpath(".//resource"):
            resource.attrib.update(
                {
                    "resource_agent": "ocf::pacemaker:Stateful",
                    "role": "Started",
                    "active": "true",
                    "orphaned": "false",
                    "blocked": "false",
                    "failed": "false",
                    "failure_ignored": "false",
                    "nodes_running_on": "1",
                }
            )

    def assert_managed(self, resource, managed):
        self.assertEqual(
            managed, state.is_resource_managed(self.status, resource)
        )

    def test_missing(self):
        self.assertRaises(
            state.ResourceNotFound, self.assert_managed, "Rxx", True
        )

    def test_primitive(self):
        self.assert_managed("R01", True)
        self.assert_managed("R02", False)

    def test_group(self):
        self.assert_managed("G1", True)
        self.assert_managed("G2", False)
        self.assert_managed("G3", False)
        self.assert_managed("G4", False)

    def test_primitive_in_group(self):
        self.assert_managed("R03", True)
        self.assert_managed("R04", True)
        self.assert_managed("R05", False)
        self.assert_managed("R06", True)
        self.assert_managed("R07", True)
        self.assert_managed("R08", False)
        self.assert_managed("R09", False)
        self.assert_managed("R10", False)

    def test_clone(self):
        self.assert_managed("R11-clone", True)
        self.assert_managed("R12-clone", False)
        self.assert_managed("R13-clone", False)
        self.assert_managed("R14-clone", False)

        self.assert_managed("R15-clone", True)
        self.assert_managed("R16-clone", False)
        self.assert_managed("R17-clone", False)
        self.assert_managed("R18-clone", False)

    def test_primitive_in_clone(self):
        self.assert_managed("R11", True)
        self.assert_managed("R12", False)
        self.assert_managed("R13", False)
        self.assert_managed("R14", False)

    def test_primitive_in_unique_clone(self):
        self.assert_managed("R15", True)
        self.assert_managed("R16", False)
        self.assert_managed("R17", False)
        self.assert_managed("R18", False)

    def test_clone_containing_group(self):
        self.assert_managed("G5-clone", True)
        self.assert_managed("G6-clone", False)
        self.assert_managed("G7-clone", False)
        self.assert_managed("G8-clone", False)
        self.assert_managed("G9-clone", False)

        self.assert_managed("G10-clone", True)
        self.assert_managed("G11-clone", False)
        self.assert_managed("G12-clone", False)
        self.assert_managed("G13-clone", False)
        self.assert_managed("G14-clone", False)

    def test_group_in_clone(self):
        self.assert_managed("G5", True)
        self.assert_managed("G6", False)
        self.assert_managed("G7", False)
        self.assert_managed("G8", False)
        self.assert_managed("G9", False)

    def test_group_in_unique_clone(self):
        self.assert_managed("G10", True)
        self.assert_managed("G11", False)
        self.assert_managed("G12", False)
        self.assert_managed("G13", False)
        self.assert_managed("G14", False)

    def test_primitive_in_group_in_clone(self):
        self.assert_managed("R19", True)
        self.assert_managed("R20", True)
        self.assert_managed("R21", False)
        self.assert_managed("R22", False)
        self.assert_managed("R23", False)
        self.assert_managed("R24", True)
        self.assert_managed("R25", True)
        self.assert_managed("R26", False)
        self.assert_managed("R27", False)
        self.assert_managed("R28", False)

    def test_primitive_in_group_in_unique_clone(self):
        self.assert_managed("R29", True)
        self.assert_managed("R30", True)
        self.assert_managed("R31", False)
        self.assert_managed("R32", False)
        self.assert_managed("R33", False)
        self.assert_managed("R34", True)
        self.assert_managed("R35", True)
        self.assert_managed("R36", False)
        self.assert_managed("R37", False)
        self.assert_managed("R38", False)

    def test_bundle(self):
        self.assert_managed("B1", True)
        self.assert_managed("B2", False)
        self.assert_managed("B3", True)
        self.assert_managed("B4", False)
        self.assert_managed("B5", False)
        self.assert_managed("B6", False)
        self.assert_managed("B7", False)

    def test_primitive_in_bundle(self):
        self.assert_managed("R39", True)
        self.assert_managed("R40", True)
        self.assert_managed("R41", False)
        self.assert_managed("R42", False)
        self.assert_managed("R43", False)
        self.assert_managed("R44", True)
        self.assert_managed("R45", True)
        self.assert_managed("R46", False)
        self.assert_managed("R47", False)
        self.assert_managed("R48", False)
