from unittest import TestCase
from lxml import etree

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import create_patcher
from pcs_test.tools.xml import etree_to_str

from pcs.common import report_codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity as severity
from pcs.lib.pacemaker.state import ClusterState

from pcs.lib.cib import fencing_topology as lib


patch_lib = create_patcher("pcs.lib.cib.fencing_topology")

# pylint: disable=too-few-public-methods, anomalous-backslash-in-string
# pylint: disable=protected-access, no-self-use


class CibMixin:
    @staticmethod
    def get_cib():
        return etree.fromstring("""
            <cib><configuration>
            <fencing-topology>
                <fencing-level
                    id="fl1" index="1" devices="d1,d2" target="nodeA"
                />
                <fencing-level
                    id="fl2" index="2" devices="d3" target="nodeA"
                />
                <fencing-level
                    id="fl3" index="1" devices="d2,d1" target="nodeB"
                />
                <fencing-level
                    id="fl4" index="2" devices="d3" target="nodeB"
                />
                <fencing-level
                    id="fl5" index="1" devices="d3,d4" target-pattern="node\\d+"
                />
                <fencing-level
                    id="fl6" index="2" devices="d1" target-pattern="node\\d+"
                />
                <fencing-level
                    id="fl7" index="3" devices="d3,d4"
                    target-attribute="fencing" target-value="improved"
                />
                <fencing-level
                    id="fl8" index="4" devices="d5"
                    target-attribute="fencing" target-value="improved"
                />
                <fencing-level
                    id="fl9" index="3" devices="dR" target-pattern="node-R.*"
                />
                <fencing-level
                    id="fl10" index="4" devices="dR-special"
                    target-attribute="fencing" target-value="remote-special"
                />
            </fencing-topology>
            </configuration></cib>
        """)


class StatusNodesMixin:
    def get_status(self):
        return ClusterState("""
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
                    <node name="nodeA" id="1" online="true" standby="false"
                        standby_onfail="false" maintenance="false"
                        pending="false" unclean="false" shutdown="false"
                        expected_up="true" is_dc="true" resources_running="0"
                        type="member"
                    />
                    <node name="nodeB" id="2" online="true" standby="false"
                        standby_onfail="false" maintenance="false"
                        pending="false" unclean="false" shutdown="false"
                        expected_up="true" is_dc="false" resources_running="0"
                        type="member"
                    />
                </nodes>
            </crm_mon>
        """).node_section.nodes


@patch_lib("_append_level_element")
@patch_lib("_validate_level_target_devices_does_not_exist")
@patch_lib("_validate_devices")
@patch_lib("_validate_target")
@patch_lib("_validate_level", return_value="valid_level")
class AddLevel(TestCase):
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()

    def assert_validators_called(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        dupl_called=True
    ):
        mock_val_level.assert_called_once_with(self.reporter, "level")
        mock_val_target.assert_called_once_with(
            self.reporter, "cluster_status_nodes", "target_type",
            "target_value", "force_node"
        )
        mock_val_devices.assert_called_once_with(
            self.reporter, "resources_el", "devices", "force_device"
        )
        if dupl_called:
            mock_val_dupl.assert_called_once_with(
                self.reporter, "topology_el", "level", "target_type",
                "target_value", "devices"
            )
        else:
            mock_val_dupl.assert_not_called()

    def assert_called_invalid(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append, dupl_called=True
    ):
        self.assertRaises(
            LibraryError,
            lambda: lib.add_level(
                self.reporter, "topology_el", "resources_el", "level",
                "target_type", "target_value", "devices",
                "cluster_status_nodes", "force_device", "force_node"
            )
        )
        self.assert_validators_called(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
            dupl_called
        )
        mock_append.assert_not_called()

    def test_success(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append
    ):
        lib.add_level(
            self.reporter, "topology_el", "resources_el", "level",
            "target_type", "target_value", "devices", "cluster_status_nodes",
            "force_device", "force_node"
        )
        self.assert_validators_called(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl
        )
        mock_append.assert_called_once_with(
            "topology_el", "valid_level", "target_type", "target_value",
            "devices"
        )

    def test_invalid_level(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append
    ):
        mock_val_level.side_effect = lambda reporter, level: reporter.append(
            reports.invalid_option_value("level", level, "a positive integer")
        )
        self.assert_called_invalid(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
            mock_append, dupl_called=False
        )

    def test_invalid_target(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append
    ):
        mock_val_target.side_effect = (
            lambda reporter, status_nodes, target_type, target_value, force:
                reporter.append(
                    reports.node_not_found(target_value)
                )
        )
        self.assert_called_invalid(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
            mock_append, dupl_called=False
        )

    def test_invalid_devices(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append
    ):
        mock_val_devices.side_effect = (
            lambda reporter, resources, devices, force:
                reporter.append(
                    reports.stonith_resources_do_not_exist(["device"])
                )
        )
        self.assert_called_invalid(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
            mock_append, dupl_called=False
        )

    def test_already_exists(
        self, mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
        mock_append
    ):
        mock_val_dupl.side_effect = (
            lambda reporter, tree, level, target_type, target_value, devices:
                reporter.append(
                    reports.fencing_level_already_exists(
                        level, target_type, target_value, devices
                    )
                )
        )
        self.assert_called_invalid(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl,
            mock_append, dupl_called=True
        )


class RemoveAllLevels(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_success(self):
        lib.remove_all_levels(self.tree)
        assert_xml_equal(
            "<fencing-topology />",
            etree_to_str(self.tree)
        )


class RemoveLevelsByParams(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")
        self.reporter = MockLibraryReportProcessor()

    def get_remaining_ids(self):
        self.assertTrue(
            self.cib.find("configuration/fencing-topology") is not None
        )
        return [el.get("id") for el in self.tree.findall("fencing-level")]

    def test_level(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, level=2
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl3", "fl5", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_target_node(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, target_type=TARGET_TYPE_NODE,
            target_value="nodeA"
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_target_pattern(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, target_type=TARGET_TYPE_REGEXP,
            target_value=r"node\d+"
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl4", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_target_attrib(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, target_type=TARGET_TYPE_ATTRIBUTE,
            target_value=("fencing", "improved")
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_one_device(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, devices=["d3"]
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl3", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_more_devices(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, devices=["d2", "d1"]
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_combination(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, 2, TARGET_TYPE_NODE, "nodeB", ["d3"]
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"]
        )
        assert_report_item_list_equal(self.reporter.report_item_list, [])

    def test_invalid_target(self):
        assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.reporter, self.tree, target_type="bad_target",
                target_value="nodeA"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_TYPE,
                {
                    "option_name": "target",
                    "allowed_types": [
                        "node",
                        "regular expression",
                        "attribute_name=value"
                    ]
                },
                None
            ),
        )
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9",
                "fl10"
            ]
        )

    def test_no_such_level(self):
        assert_raise_library_error(
            lambda: lib.remove_levels_by_params(
                self.reporter, self.tree, 9, TARGET_TYPE_NODE, "nodeB", ["d3"]
            ),
            (
                severity.ERROR,
                report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                {
                    "devices": ["d3", ],
                    "target_type": TARGET_TYPE_NODE,
                    "target_value": "nodeB",
                    "level": 9,
                },
                None
            ),
        )
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9",
                "fl10"
            ]
        )

    def test_no_such_level_ignore_missing(self):
        lib.remove_levels_by_params(
            self.reporter, self.tree, 9, TARGET_TYPE_NODE, "nodeB", ["d3"], True
        )
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9",
                "fl10"
            ]
        )

class RemoveDeviceFromAllLevels(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_success(self):
        lib.remove_device_from_all_levels(self.tree, "d3")
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl1" index="1" devices="d1,d2" target="nodeA"
                />
                <fencing-level
                    id="fl3" index="1" devices="d2,d1" target="nodeB"
                />
                <fencing-level
                    id="fl5" index="1" devices="d4" target-pattern="node\\d+"
                />
                <fencing-level
                    id="fl6" index="2" devices="d1" target-pattern="node\\d+"
                />
                <fencing-level
                    id="fl7" index="3" devices="d4"
                    target-attribute="fencing" target-value="improved"
                />
                <fencing-level
                    id="fl8" index="4" devices="d5"
                    target-attribute="fencing" target-value="improved"
                />
                <fencing-level
                    id="fl9" index="3" devices="dR" target-pattern="node-R.*"
                />
                <fencing-level
                    id="fl10" index="4" devices="dR-special"
                    target-attribute="fencing" target-value="remote-special"
                />
            </fencing-topology>
            """,
            etree_to_str(self.tree)
        )

    def test_no_such_device(self):
        original_xml = etree_to_str(self.tree)
        lib.remove_device_from_all_levels(self.tree, "dX")
        assert_xml_equal(original_xml, etree_to_str(self.tree))


class Export(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_empty(self):
        self.assertEqual(
            lib.export(etree.fromstring("<fencing-topology />")),
            []
        )

    def test_success(self):
        self.assertEqual(
            lib.export(self.tree),
            [
                {
                    "level": "1",
                    "target_type": "node",
                    "target_value": "nodeA",
                    "devices": ["d1", "d2"],
                },
                {
                    "level": "2",
                    "target_type": "node",
                    "target_value": "nodeA",
                    "devices": ["d3"],
                },
                {
                    "level": "1",
                    "target_type": "node",
                    "target_value": "nodeB",
                    "devices": ["d2", "d1"],
                },
                {
                    "level": "2",
                    "target_type": "node",
                    "target_value": "nodeB",
                    "devices": ["d3"],
                },
                {
                    "level": "1",
                    "target_type": "regexp",
                    "target_value": r"node\d+",
                    "devices": ["d3", "d4"],
                },
                {
                    "level": "2",
                    "target_type": "regexp",
                    "target_value": r"node\d+",
                    "devices": ["d1"],
                },
                {
                    "level": "3",
                    "target_type": "attribute",
                    "target_value": ("fencing", "improved"),
                    "devices": ["d3", "d4"],
                },
                {
                    "level": "4",
                    "target_type": "attribute",
                    "target_value": ("fencing", "improved"),
                    "devices": ["d5"],
                },
                {
                    "level": "3",
                    "target_type": "regexp",
                    "target_value": "node-R.*",
                    "devices": ["dR"],
                },
                {
                    "level": "4",
                    "target_type": "attribute",
                    "target_value": ("fencing", "remote-special"),
                    "devices": ["dR-special"],
                }
            ]
        )


class Verify(TestCase, CibMixin, StatusNodesMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def fixture_resource(self, tree, name):
        el = etree.SubElement(tree, "primitive", id=name, type="fence_dummy")
        el.set("class", "stonith")

    def test_empty(self):
        resources = etree.fromstring("<resources />")
        topology = etree.fromstring("<fencing-topology />")
        reporter = MockLibraryReportProcessor()

        lib.verify(reporter, topology, resources, self.get_status())

        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_success(self):
        resources = etree.fromstring("<resources />")
        for name in ["d1", "d2", "d3", "d4", "d5", "dR", "dR-special"]:
            self.fixture_resource(resources, name)
        reporter = MockLibraryReportProcessor()

        lib.verify(reporter, self.tree, resources, self.get_status())

        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_failures(self):
        resources = etree.fromstring("<resources />")
        reporter = MockLibraryReportProcessor()

        lib.verify(reporter, self.tree, resources, [])

        report = [
            (
                severity.ERROR,
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                {
                    "stonith_ids": [
                        "d1", "d2", "d3", "d4", "d5", "dR", "dR-special"
                    ],
                },
                None
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "nodeA",
                },
                None
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "nodeB",
                },
                None
            ),
        ]
        assert_report_item_list_equal(reporter.report_item_list, report)


class ValidateLevel(TestCase):
    def test_success(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_level(reporter, 1)
        lib._validate_level(reporter, "1")
        lib._validate_level(reporter, 9)
        lib._validate_level(reporter, "9")
        lib._validate_level(reporter, "05")
        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_invalid(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_level(reporter, "")
        lib._validate_level(reporter, 0)
        lib._validate_level(reporter, "0")
        lib._validate_level(reporter, -1)
        lib._validate_level(reporter, "-1")
        lib._validate_level(reporter, "1abc")
        report_list = []
        for value in ["", 0, "0", -1, "-1", "1abc"]:
            report_list.append((
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": value,
                    "option_name": "level",
                    "allowed_values": "a positive integer",
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
                None
            ))
        assert_report_item_list_equal(reporter.report_item_list, report_list)


@patch_lib("_validate_target_valuewise")
@patch_lib("_validate_target_typewise")
class ValidateTarget(TestCase):
    def test_delegate(self, validate_type, validate_value):
        lib._validate_target("reporter", "status", "type", "value", "force")
        validate_type.assert_called_once_with("reporter", "type")
        validate_value.assert_called_once_with(
            "reporter", "status", "type", "value", "force"
        )


class ValidateTargetTypewise(TestCase):
    def test_success(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_typewise(reporter, TARGET_TYPE_NODE)
        lib._validate_target_typewise(reporter, TARGET_TYPE_ATTRIBUTE)
        lib._validate_target_typewise(reporter, TARGET_TYPE_REGEXP)
        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_empty(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_typewise(reporter, "")
        report = [(
            severity.ERROR,
            report_codes.INVALID_OPTION_TYPE,
            {
                "option_name": "target",
                "allowed_types": [
                    "node",
                    "regular expression",
                    "attribute_name=value"
                ],
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_invalid(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_typewise(reporter, "bad_target")
        report = [(
            severity.ERROR,
            report_codes.INVALID_OPTION_TYPE,
            {
                "option_name": "target",
                "allowed_types": [
                    "node",
                    "regular expression",
                    "attribute_name=value"
                ],
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)


class ValidateTargetValuewise(TestCase, StatusNodesMixin):
    def setUp(self):
        self.state = self.get_status()

    def test_node_valid(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_valuewise(
            reporter, self.state, TARGET_TYPE_NODE, "nodeA"
        )
        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_node_empty(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_valuewise(
            reporter, self.state, TARGET_TYPE_NODE, ""
        )
        report = [(
            severity.ERROR,
            report_codes.NODE_NOT_FOUND,
            {
                "node": "",
            },
            report_codes.FORCE_NODE_DOES_NOT_EXIST
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_node_invalid(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_valuewise(
            reporter, self.state, TARGET_TYPE_NODE, "rh7-x"
        )
        report = [(
            severity.ERROR,
            report_codes.NODE_NOT_FOUND,
            {
                "node": "rh7-x",
            },
            report_codes.FORCE_NODE_DOES_NOT_EXIST
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_node_invalid_force(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_valuewise(
            reporter, self.state, TARGET_TYPE_NODE, "rh7-x", force_node=True
        )
        report = [(
            severity.WARNING,
            report_codes.NODE_NOT_FOUND,
            {
                "node": "rh7-x",
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_node_invalid_not_forceable(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_target_valuewise(
            reporter, self.state, TARGET_TYPE_NODE, "rh7-x", allow_force=False
        )
        report = [(
            severity.ERROR,
            report_codes.NODE_NOT_FOUND,
            {
                "node": "rh7-x",
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)


class ValidateDevices(TestCase):
    def setUp(self):
        self.resources_el = etree.fromstring("""
            <resources>
                <primitive id="dummy"
                    class="ocf" provider="pacemaker" type="Stateful"
                 />
                <primitive id="stonith1" class="stonith" type="fence_xvm" />
                <primitive id="stonith2" class="stonith" type="fence_apc" />
            </resources>
        """)

    def test_success(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_devices(
            reporter, self.resources_el, ["stonith1"]
        )
        lib._validate_devices(
            reporter, self.resources_el, ["stonith1", "stonith2"]
        )
        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_empty(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_devices(reporter, self.resources_el, [])
        report = [(
            severity.ERROR,
            report_codes.REQUIRED_OPTIONS_ARE_MISSING,
            {
                "option_type": None,
                "option_names": ["stonith devices"],
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_invalid(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_devices(reporter, self.resources_el, ["dummy", "fenceX"])
        report = [(
            severity.ERROR,
            report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
            {
                "stonith_ids": ["dummy", "fenceX"],
            },
            report_codes.FORCE_STONITH_RESOURCE_DOES_NOT_EXIST
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_invalid_forced(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_devices(
            reporter, self.resources_el, ["dummy", "fenceX"], force_device=True
        )
        report = [(
            severity.WARNING,
            report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
            {
                "stonith_ids": ["dummy", "fenceX"],
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)

    def test_node_invalid_not_forceable(self):
        reporter = MockLibraryReportProcessor()
        lib._validate_devices(
            reporter, self.resources_el, ["dummy", "fenceX"], allow_force=False
        )
        report = [(
            severity.ERROR,
            report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
            {
                "stonith_ids": ["dummy", "fenceX"],
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)


@patch_lib("_find_level_elements")
class ValidateLevelTargetDevicesDoesNotExist(TestCase):
    def test_success(self, mock_find):
        mock_find.return_value = []
        reporter = MockLibraryReportProcessor()

        lib._validate_level_target_devices_does_not_exist(
            reporter, "tree", "level", "target_type", "target_value",
            ["devices"]
        )

        mock_find.assert_called_once_with(
            "tree", "level", "target_type", "target_value", ["devices"]
        )
        assert_report_item_list_equal(reporter.report_item_list, [])

    def test_error(self, mock_find):
        mock_find.return_value = ["element"]
        reporter = MockLibraryReportProcessor()

        lib._validate_level_target_devices_does_not_exist(
            reporter, "tree", "level", "target_type", "target_value",
            ["devices"]
        )

        mock_find.assert_called_once_with(
            "tree", "level", "target_type", "target_value", ["devices"]
        )
        report = [(
            severity.ERROR,
            report_codes.CIB_FENCING_LEVEL_ALREADY_EXISTS,
            {
                "devices": ["devices"],
                "target_type": "target_type",
                "target_value": "target_value",
                "level": "level",
            },
            None
        )]
        assert_report_item_list_equal(reporter.report_item_list, report)


class AppendLevelElement(TestCase):
    def setUp(self):
        self.tree = etree.fromstring("<fencing-topology />")

    def test_node_name(self):
        lib._append_level_element(
            self.tree, 1, TARGET_TYPE_NODE, "node1", ["d1"]
        )
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl-node1-1"
                    devices="d1" index="1" target="node1"
                />
            </fencing-topology>
            """,
            etree_to_str(self.tree)
        )

    def test_node_pattern(self):
        lib._append_level_element(
            self.tree, "2", TARGET_TYPE_REGEXP, r"node-\d+", ["d1", "d2"]
        )
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl-node-d-2"
                    devices="d1,d2" index="2" target-pattern="node-\\d+"
                />
            </fencing-topology>
            """,
            etree_to_str(self.tree)
        )

    def test_node_attribute(self):
        lib._append_level_element(
            self.tree, 3, TARGET_TYPE_ATTRIBUTE, ("name%@x", "val%@x"), ["d1"],
        )
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl-namex-3"
                    devices="d1"
                    index="3"
                    target-attribute="name%@x" target-value="val%@x"
                />
            </fencing-topology>
            """,
            etree_to_str(self.tree)
        )


class FindLevelElements(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def get_ids(self, elements):
        return [el.get("id") for el in elements]

    def test_no_filter(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(self.tree)),
            [
                "fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9",
                "fl10"
            ]
        )

    def test_no_such_level(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, level=2, target_type=TARGET_TYPE_NODE,
                target_value="nodeB", devices=["d5"]
            )),
            []
        )

    def test_level(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, level=1
            )),
            ["fl1", "fl3", "fl5"]
        )

    def test_target_node(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, target_type=TARGET_TYPE_NODE, target_value="nodeB"
            )),
            ["fl3", "fl4"]
        )

    def test_target_pattern(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, target_type=TARGET_TYPE_REGEXP,
                target_value="node-R.*"
            )),
            ["fl9"]
        )

    def test_target_attribute(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, target_type=TARGET_TYPE_ATTRIBUTE,
                target_value=("fencing", "improved")
            )),
            ["fl7", "fl8"]
        )

    def test_devices(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, devices=["d3"]
            )),
            ["fl2", "fl4"]
        )

        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, devices=["d1", "d2"]
            )),
            ["fl1"]
        )

    def test_combination(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(
                self.tree, 2, TARGET_TYPE_NODE, "nodeB", ["d3"]
            )),
            ["fl4"]
        )
