from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs import settings
from pcs.common import reports
from pcs.common.fencing_topology import (
    TARGET_TYPE_ATTRIBUTE,
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
)
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.common.reports.item import ReportItem
from pcs.lib.cib import fencing_topology as lib
from pcs.lib.cib.tools import ElementNotFound
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ClusterState

from pcs_test.tools import (
    fixture,
    fixture_crm_mon,
)
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import create_patcher
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import etree_to_str

patch_lib = create_patcher("pcs.lib.cib.fencing_topology")

# pylint: disable=protected-access

FIXTURE_NON_UNIQUE_DEVICES = """
    <fencing-topology>
        <fencing-level
            id="fl1" index="1" devices="d1,d1" target="nodeA"
        />
        <fencing-level
            id="fl2" index="2" devices="d1,d2,d1,d3" target="nodeA"
        />
    </fencing-topology>
"""


class CibMixin:
    @staticmethod
    def get_cib():
        return etree.fromstring(
            """
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
        """
        )


class StatusNodesMixin:
    def get_status(self):
        # pylint: disable=no-self-use
        with open(rc("crm_mon.minimal.xml")) as crm_mon_file:
            crm_mon_xml = crm_mon_file.read()
        return ClusterState(
            fixture_crm_mon.complete_state(
                crm_mon_xml,
                nodes_xml="""
                <nodes>
                    <node name="nodeA" id="1" is_dc="true" />
                    <node name="nodeB" id="2" />
                </nodes>
            """,
            )
        ).node_section.nodes


@patch_lib("_append_level_element")
@patch_lib("_validate_level_target_devices_does_not_exist", return_value=[])
@patch_lib("_validate_devices", return_value=[])
@patch_lib("_validate_target", return_value=[])
@patch_lib("_validate_level", return_value=[])
class AddLevel(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()
        self.topology_el = "a topology element"
        self.resources_el = "a resources element"
        self.level = "a level"
        self.target_type = "a target type"
        self.target_value = "a target value"
        self.devices = ["device1", "device2"]
        self.cluster_status_nodes = "a status"
        self.force_device = "a force for a device"
        self.force_node = "a force for a node"

    def assert_validators_called(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        dupl_called=True,
    ):
        mock_val_level.assert_called_once_with(self.level)
        mock_val_target.assert_called_once_with(
            self.cluster_status_nodes,
            self.target_type,
            self.target_value,
            self.force_node,
        )
        mock_val_devices.assert_called_once_with(
            self.resources_el, self.devices, self.force_device
        )
        if dupl_called:
            mock_val_dupl.assert_called_once_with(
                self.topology_el,
                self.level,
                self.target_type,
                self.target_value,
                self.devices,
            )
        else:
            mock_val_dupl.assert_not_called()

    def assert_called_invalid(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
        dupl_called=True,
        report_list=None,
    ):
        report_list = report_list or []
        with self.assertRaises(LibraryError):
            lib.add_level(
                self.reporter,
                self.topology_el,
                self.resources_el,
                self.level,
                self.target_type,
                self.target_value,
                self.devices,
                self.cluster_status_nodes,
                self.force_device,
                self.force_node,
            )
        assert_report_item_list_equal(
            self.reporter.report_item_list, report_list
        )
        self.assert_validators_called(
            mock_val_level,
            mock_val_target,
            mock_val_devices,
            mock_val_dupl,
            dupl_called,
        )
        mock_append.assert_not_called()

    def test_success(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
    ):
        self.level = 1
        lib.add_level(
            self.reporter,
            self.topology_el,
            self.resources_el,
            self.level,
            self.target_type,
            self.target_value,
            self.devices,
            self.cluster_status_nodes,
            self.force_device,
            self.force_node,
        )
        self.assert_validators_called(
            mock_val_level, mock_val_target, mock_val_devices, mock_val_dupl
        )
        mock_append.assert_called_once_with(
            self.topology_el,
            self.level,
            self.target_type,
            self.target_value,
            self.devices,
        )

    def test_invalid_level(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
    ):
        mock_val_level.return_value = [
            reports.item.ReportItem.error(
                reports.messages.InvalidOptionValue("level", self.level, "1..9")
            )
        ]
        report_list = [
            fixture.error(
                report_codes.INVALID_OPTION_VALUE,
                option_value=self.level,
                option_name="level",
                allowed_values="1..9",
                cannot_be_empty=False,
                forbidden_characters=None,
            ),
        ]
        self.assert_called_invalid(
            mock_val_level,
            mock_val_target,
            mock_val_devices,
            mock_val_dupl,
            mock_append,
            dupl_called=False,
            report_list=report_list,
        )

    def test_invalid_target(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
    ):
        mock_val_target.return_value = [
            ReportItem.error(reports.messages.NodeNotFound(self.target_value))
        ]
        report_list = [
            fixture.error(
                report_codes.NODE_NOT_FOUND,
                node=self.target_value,
                searched_types=[],
            ),
        ]
        self.assert_called_invalid(
            mock_val_level,
            mock_val_target,
            mock_val_devices,
            mock_val_dupl,
            mock_append,
            dupl_called=False,
            report_list=report_list,
        )

    def test_invalid_devices(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
    ):
        mock_val_devices.return_value = [
            ReportItem.error(
                reports.messages.StonithResourcesDoNotExist(self.devices)
            )
        ]
        report_list = [
            fixture.error(
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                stonith_ids=self.devices,
            ),
        ]
        self.assert_called_invalid(
            mock_val_level,
            mock_val_target,
            mock_val_devices,
            mock_val_dupl,
            mock_append,
            dupl_called=False,
            report_list=report_list,
        )

    def test_already_exists(
        self,
        mock_val_level,
        mock_val_target,
        mock_val_devices,
        mock_val_dupl,
        mock_append,
    ):
        mock_val_dupl.return_value = [
            reports.item.ReportItem.error(
                reports.messages.CibFencingLevelAlreadyExists(
                    self.level,
                    self.target_type,
                    self.target_value,
                    self.devices,
                )
            )
        ]
        report_list = [
            fixture.error(
                report_codes.CIB_FENCING_LEVEL_ALREADY_EXISTS,
                level=self.level,
                target_type=self.target_type,
                target_value=self.target_value,
                devices=self.devices,
            ),
        ]
        self.assert_called_invalid(
            mock_val_level,
            mock_val_target,
            mock_val_devices,
            mock_val_dupl,
            mock_append,
            dupl_called=True,
            report_list=report_list,
        )


class RemoveAllLevels(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_success(self):
        lib.remove_all_levels(self.tree)
        assert_xml_equal("<fencing-topology />", etree_to_str(self.tree))


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
        report_list = lib.remove_levels_by_params(self.tree, level=2)
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl3", "fl5", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_target_node(self):
        report_list = lib.remove_levels_by_params(
            self.tree, target_type=TARGET_TYPE_NODE, target_value="nodeA"
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl3", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_target_pattern(self):
        report_list = lib.remove_levels_by_params(
            self.tree, target_type=TARGET_TYPE_REGEXP, target_value=r"node\d+"
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl4", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_target_attrib(self):
        report_list = lib.remove_levels_by_params(
            self.tree,
            target_type=TARGET_TYPE_ATTRIBUTE,
            target_value=("fencing", "improved"),
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl4", "fl5", "fl6", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_one_device(self):
        report_list = lib.remove_levels_by_params(self.tree, devices=["d3"])
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl3", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_more_devices(self):
        report_list = lib.remove_levels_by_params(
            self.tree, devices=["d2", "d1"]
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl4", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_combination(self):
        report_list = lib.remove_levels_by_params(
            self.tree, 2, TARGET_TYPE_NODE, "nodeB", ["d3"]
        )
        self.assertEqual(
            self.get_remaining_ids(),
            ["fl1", "fl2", "fl3", "fl5", "fl6", "fl7", "fl8", "fl9", "fl10"],
        )
        assert_report_item_list_equal(report_list, [])

    def test_invalid_target(self):
        report_list = lib.remove_levels_by_params(
            self.tree, target_type="bad_target", target_value="nodeA"
        )
        assert_report_item_list_equal(
            report_list,
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_TYPE,
                    {
                        "option_name": "target",
                        "allowed_types": [
                            "node",
                            "regular expression",
                            "attribute_name=value",
                        ],
                    },
                    None,
                ),
            ],
        )
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1",
                "fl2",
                "fl3",
                "fl4",
                "fl5",
                "fl6",
                "fl7",
                "fl8",
                "fl9",
                "fl10",
            ],
        )

    def test_no_such_level(self):
        report_list = lib.remove_levels_by_params(
            self.tree, 9, TARGET_TYPE_NODE, "nodeB", ["d3"]
        )
        assert_report_item_list_equal(
            report_list,
            [
                (
                    severity.ERROR,
                    report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
                    {
                        "devices": [
                            "d3",
                        ],
                        "target_type": TARGET_TYPE_NODE,
                        "target_value": "nodeB",
                        "level": 9,
                    },
                    None,
                ),
            ],
        )
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1",
                "fl2",
                "fl3",
                "fl4",
                "fl5",
                "fl6",
                "fl7",
                "fl8",
                "fl9",
                "fl10",
            ],
        )

    def test_no_such_level_ignore_missing(self):
        report_list = lib.remove_levels_by_params(
            self.tree, 9, TARGET_TYPE_NODE, "nodeB", ["d3"], True
        )
        assert_report_item_list_equal(report_list, [])
        self.assertEqual(
            self.get_remaining_ids(),
            [
                "fl1",
                "fl2",
                "fl3",
                "fl4",
                "fl5",
                "fl6",
                "fl7",
                "fl8",
                "fl9",
                "fl10",
            ],
        )


class RemoveDeviceFromAllLevelsDontRemoveElement(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_success(self):
        elements = lib.remove_device_from_all_levels_dont_remove_elements(
            self.tree, "d3"
        )
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl1" index="1" devices="d1,d2" target="nodeA"
                />
                <fencing-level
                    id="fl2" index="2" devices="" target="nodeA"
                />
                <fencing-level
                    id="fl3" index="1" devices="d2,d1" target="nodeB"
                />
                <fencing-level
                    id="fl4" index="2" devices="" target="nodeB"
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
            etree_to_str(self.tree),
        )
        self.assertEqual(
            [
                self.tree.find(".//fencing-level[@id='fl2']"),
                self.tree.find(".//fencing-level[@id='fl4']"),
                self.tree.find(".//fencing-level[@id='fl5']"),
                self.tree.find(".//fencing-level[@id='fl7']"),
            ],
            elements,
        )

    def test_non_unique_device_ids(self):
        tree = etree.fromstring(FIXTURE_NON_UNIQUE_DEVICES)
        elements = lib.remove_device_from_all_levels_dont_remove_elements(
            tree, "d1"
        )
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl1" index="1" devices="" target="nodeA"
                />
                <fencing-level
                    id="fl2" index="2" devices="d2,d3" target="nodeA"
                />
            </fencing-topology>
            """,
            etree_to_str(tree),
        )
        self.assertEqual(
            [
                tree.find(".//fencing-level[@id='fl1']"),
                tree.find(".//fencing-level[@id='fl2']"),
            ],
            elements,
        )

    def test_no_such_device(self):
        original_xml = etree_to_str(self.tree)
        elements = lib.remove_device_from_all_levels_dont_remove_elements(
            self.tree, "dX"
        )
        assert_xml_equal(original_xml, etree_to_str(self.tree))
        self.assertEqual([], elements)


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
            etree_to_str(self.tree),
        )

    def test_non_unique_device_ids(self):
        # pylint: disable=no-self-use
        tree = etree.fromstring(FIXTURE_NON_UNIQUE_DEVICES)
        lib.remove_device_from_all_levels(tree, "d1")
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl2" index="2" devices="d2,d3" target="nodeA"
                />
            </fencing-topology>
            """,
            etree_to_str(tree),
        )

    def test_no_such_device(self):
        original_xml = etree_to_str(self.tree)
        lib.remove_device_from_all_levels(self.tree, "dX")
        assert_xml_equal(original_xml, etree_to_str(self.tree))


class RemoveDeviceFromOneLevel(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_keep_fencing_level(self):
        lib.remove_device_from_one_level(self.tree, "fl1", "d1")
        assert_xml_equal(
            """
            <fencing-topology>
                <fencing-level
                    id="fl1" index="1" devices="d2" target="nodeA"
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
            """,
            etree_to_str(self.tree),
        )

    def test_remove_fencing_level(self):
        lib.remove_device_from_one_level(self.tree, "fl2", "d3")
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
            """,
            etree_to_str(self.tree),
        )

    def test_nonexistent_level(self):
        with self.assertRaises(ElementNotFound):
            lib.remove_device_from_one_level(self.tree, "nonexistent", "d1")


class Export(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def test_empty(self):
        self.assertEqual(
            lib.export(etree.fromstring("<fencing-topology />")), []
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
                },
            ],
        )


class Verify(TestCase, CibMixin, StatusNodesMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def fixture_resource(self, tree, name):
        # pylint: disable=no-self-use
        el = etree.SubElement(tree, "primitive", id=name, type="fence_dummy")
        el.set("class", "stonith")

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_empty(self):
        resources = etree.fromstring("<resources />")
        topology = etree.fromstring("<fencing-topology />")

        report_list = lib.verify(topology, resources, self.get_status())

        assert_report_item_list_equal(report_list, [])

    @mock.patch.object(
        settings,
        "pacemaker_api_result_schema",
        rc("pcmk_api_rng/api-result.rng"),
    )
    def test_success(self):
        resources = etree.fromstring("<resources />")
        for name in ["d1", "d2", "d3", "d4", "d5", "dR", "dR-special"]:
            self.fixture_resource(resources, name)

        report_list = lib.verify(self.tree, resources, self.get_status())

        assert_report_item_list_equal(report_list, [])

    def test_failures(self):
        resources = etree.fromstring("<resources />")

        report_list = lib.verify(self.tree, resources, [])

        report = [
            (
                severity.ERROR,
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                {
                    "stonith_ids": [
                        "d1",
                        "d2",
                        "d3",
                        "d4",
                        "d5",
                        "dR",
                        "dR-special",
                    ],
                },
                None,
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "nodeA",
                    "searched_types": [],
                },
                None,
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "nodeB",
                    "searched_types": [],
                },
                None,
            ),
        ]
        assert_report_item_list_equal(report_list, report)


class ValidateLevel(TestCase):
    def test_success(self):
        level_list = [1, "1", 9, "9", "05"]
        for level in level_list:
            with self.subTest(level=level):
                report_list = lib._validate_level(level)
                assert_report_item_list_equal(report_list, [])

    def test_invalid(self):
        level_list = ["", 0, "0", -1, "-1", "1abc", "10"]
        for level in level_list:
            with self.subTest(level=level):
                report_list = lib._validate_level(level)
                assert_report_item_list_equal(
                    report_list,
                    [
                        fixture.error(
                            report_codes.INVALID_OPTION_VALUE,
                            option_value=level,
                            option_name="level",
                            allowed_values="1..9",
                            cannot_be_empty=False,
                            forbidden_characters=None,
                        ),
                    ],
                )


@patch_lib("_validate_target_valuewise")
@patch_lib("_validate_target_typewise")
class ValidateTarget(TestCase):
    def test_delegate(self, validate_type, validate_value):
        # pylint: disable=no-self-use
        lib._validate_target("status", "type", "value", "force")
        validate_type.assert_called_once_with("type")
        validate_value.assert_called_once_with(
            "status", "type", "value", "force"
        )


class ValidateTargetTypewise(TestCase):
    def test_success(self):
        # pylint: disable=no-self-use
        report_list = []
        report_list.extend(lib._validate_target_typewise(TARGET_TYPE_NODE))
        report_list.extend(lib._validate_target_typewise(TARGET_TYPE_ATTRIBUTE))
        report_list.extend(lib._validate_target_typewise(TARGET_TYPE_REGEXP))
        assert_report_item_list_equal(report_list, [])

    def test_empty(self):
        # pylint: disable=no-self-use
        report_list = lib._validate_target_typewise("")
        report = [
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_TYPE,
                {
                    "option_name": "target",
                    "allowed_types": [
                        "node",
                        "regular expression",
                        "attribute_name=value",
                    ],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_invalid(self):
        # pylint: disable=no-self-use
        report_list = lib._validate_target_typewise("bad_target")
        report = [
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_TYPE,
                {
                    "option_name": "target",
                    "allowed_types": [
                        "node",
                        "regular expression",
                        "attribute_name=value",
                    ],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)


@mock.patch.object(
    settings, "pacemaker_api_result_schema", rc("pcmk_api_rng/api-result.rng")
)
class ValidateTargetValuewise(TestCase, StatusNodesMixin):
    def test_node_valid(self):
        state = self.get_status()
        assert_report_item_list_equal(
            lib._validate_target_valuewise(state, TARGET_TYPE_NODE, "nodeA"),
            [],
        )

    def test_node_empty(self):
        state = self.get_status()
        report_list = lib._validate_target_valuewise(
            state, TARGET_TYPE_NODE, ""
        )
        report = [
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "",
                    "searched_types": [],
                },
                report_codes.FORCE,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_node_invalid(self):
        state = self.get_status()
        report_list = lib._validate_target_valuewise(
            state, TARGET_TYPE_NODE, "rh7-x"
        )
        report = [
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "rh7-x",
                    "searched_types": [],
                },
                report_codes.FORCE,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_node_invalid_force(self):
        state = self.get_status()
        report_list = lib._validate_target_valuewise(
            state, TARGET_TYPE_NODE, "rh7-x", force_node=True
        )
        report = [
            (
                severity.WARNING,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "rh7-x",
                    "searched_types": [],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_node_invalid_not_forceable(self):
        state = self.get_status()
        report_list = lib._validate_target_valuewise(
            state, TARGET_TYPE_NODE, "rh7-x", allow_force=False
        )
        report = [
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "rh7-x",
                    "searched_types": [],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)


class ValidateDevices(TestCase):
    def setUp(self):
        self.resources_el = etree.fromstring(
            """
            <resources>
                <primitive id="dummy"
                    class="ocf" provider="pacemaker" type="Stateful"
                 />
                <primitive id="stonith1" class="stonith" type="fence_xvm" />
                <primitive id="stonith2" class="stonith" type="fence_apc" />
            </resources>
        """
        )

    def test_success(self):
        report_list = []
        report_list.extend(
            lib._validate_devices(self.resources_el, ["stonith1"])
        )
        report_list.extend(
            lib._validate_devices(self.resources_el, ["stonith1", "stonith2"])
        )
        assert_report_item_list_equal(report_list, [])

    def test_empty(self):
        report_list = lib._validate_devices(self.resources_el, [])
        report = [
            (
                severity.ERROR,
                report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                {
                    "option_type": None,
                    "option_names": ["stonith devices"],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_invalid(self):
        report_list = lib._validate_devices(
            self.resources_el, ["dummy", "fenceX"]
        )
        report = [
            (
                severity.ERROR,
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                {
                    "stonith_ids": ["dummy", "fenceX"],
                },
                report_codes.FORCE,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_invalid_forced(self):
        report_list = lib._validate_devices(
            self.resources_el, ["dummy", "fenceX"], force_device=True
        )
        report = [
            (
                severity.WARNING,
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                {
                    "stonith_ids": ["dummy", "fenceX"],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)

    def test_node_invalid_not_forceable(self):
        report_list = lib._validate_devices(
            self.resources_el, ["dummy", "fenceX"], allow_force=False
        )
        report = [
            (
                severity.ERROR,
                report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
                {
                    "stonith_ids": ["dummy", "fenceX"],
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)


@patch_lib("_find_level_elements")
class ValidateLevelTargetDevicesDoesNotExist(TestCase):
    def test_success(self, mock_find):
        # pylint: disable=no-self-use
        mock_find.return_value = []

        report_list = lib._validate_level_target_devices_does_not_exist(
            "tree", "level", "target_type", "target_value", ["devices"]
        )

        mock_find.assert_called_once_with(
            "tree", "level", "target_type", "target_value", ["devices"]
        )
        assert_report_item_list_equal(report_list, [])

    def test_error(self, mock_find):
        # pylint: disable=no-self-use
        mock_find.return_value = ["element"]

        report_list = lib._validate_level_target_devices_does_not_exist(
            "tree", "level", "target_type", "target_value", ["devices"]
        )

        mock_find.assert_called_once_with(
            "tree", "level", "target_type", "target_value", ["devices"]
        )
        report = [
            (
                severity.ERROR,
                report_codes.CIB_FENCING_LEVEL_ALREADY_EXISTS,
                {
                    "devices": ["devices"],
                    "target_type": "target_type",
                    "target_value": "target_value",
                    "level": "level",
                },
                None,
            )
        ]
        assert_report_item_list_equal(report_list, report)


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
            etree_to_str(self.tree),
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
            etree_to_str(self.tree),
        )

    def test_node_attribute(self):
        lib._append_level_element(
            self.tree,
            3,
            TARGET_TYPE_ATTRIBUTE,
            ("name%@x", "val%@x"),
            ["d1"],
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
            etree_to_str(self.tree),
        )


class FindLevelElements(TestCase, CibMixin):
    def setUp(self):
        self.cib = self.get_cib()
        self.tree = self.cib.find("configuration/fencing-topology")

    def get_ids(self, elements):
        # pylint: disable=no-self-use
        return [el.get("id") for el in elements]

    def test_no_filter(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(self.tree)),
            [
                "fl1",
                "fl2",
                "fl3",
                "fl4",
                "fl5",
                "fl6",
                "fl7",
                "fl8",
                "fl9",
                "fl10",
            ],
        )

    def test_no_such_level(self):
        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(
                    self.tree,
                    level=2,
                    target_type=TARGET_TYPE_NODE,
                    target_value="nodeB",
                    devices=["d5"],
                )
            ),
            [],
        )

    def test_level(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(self.tree, level=1)),
            ["fl1", "fl3", "fl5"],
        )

    def test_target_node(self):
        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(
                    self.tree,
                    target_type=TARGET_TYPE_NODE,
                    target_value="nodeB",
                )
            ),
            ["fl3", "fl4"],
        )

    def test_target_pattern(self):
        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(
                    self.tree,
                    target_type=TARGET_TYPE_REGEXP,
                    target_value="node-R.*",
                )
            ),
            ["fl9"],
        )

    def test_target_attribute(self):
        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(
                    self.tree,
                    target_type=TARGET_TYPE_ATTRIBUTE,
                    target_value=("fencing", "improved"),
                )
            ),
            ["fl7", "fl8"],
        )

    def test_devices(self):
        self.assertEqual(
            self.get_ids(lib._find_level_elements(self.tree, devices=["d3"])),
            ["fl2", "fl4"],
        )

        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(self.tree, devices=["d1", "d2"])
            ),
            ["fl1"],
        )

    def test_combination(self):
        self.assertEqual(
            self.get_ids(
                lib._find_level_elements(
                    self.tree, 2, TARGET_TYPE_NODE, "nodeB", ["d3"]
                )
            ),
            ["fl4"],
        )
