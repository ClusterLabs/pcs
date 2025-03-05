from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib.resource import stonith

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)


class IsStonithEnabled(TestCase):
    def test_not_set(self):
        crm_config = etree.fromstring("<crm_config />")
        self.assertTrue(stonith.is_stonith_enabled(crm_config))

    def test_set_to_enabled(self):
        crm_config = etree.fromstring(
            """
            <crm_config>
                <cluster_property_set>
                    <nvpair name="abc" value="false" />
                    <nvpair name="stonith-enabled" value="true" />
                </cluster_property_set>
            </crm_config>
        """
        )
        self.assertTrue(stonith.is_stonith_enabled(crm_config))

    def test_set_to_disabled(self):
        crm_config = etree.fromstring(
            """
            <crm_config>
                <cluster_property_set>
                    <nvpair name="abc" value="true" />
                    <nvpair name="stonith-enabled" value="false" />
                </cluster_property_set>
            </crm_config>
        """
        )
        self.assertFalse(stonith.is_stonith_enabled(crm_config))

    def test_multiple_values(self):
        crm_config = etree.fromstring(
            """
            <crm_config>
                <cluster_property_set>
                    <nvpair name="stonith-enabled" value="false" />
                    <nvpair name="stonith-enabled" value="true" />
                    <nvpair name="stonith-enabled" value="false" />
                </cluster_property_set>
            </crm_config>
        """
        )
        self.assertFalse(stonith.is_stonith_enabled(crm_config))

    def test_multiple_sections(self):
        crm_config = etree.fromstring(
            """
            <crm_config>
                <cluster_property_set>
                    <nvpair name="stonith-enabled" value="false" />
                    <nvpair name="stonith-enabled" value="true" />
                </cluster_property_set>
                <cluster_property_set>
                    <nvpair name="stonith-enabled" value="false" />
                </cluster_property_set>
            </crm_config>
        """
        )
        self.assertFalse(stonith.is_stonith_enabled(crm_config))


class GetAllResourcesBase(TestCase):
    resources = etree.fromstring(
        """
            <resources>
                <primitive id="R" class="ocf" provider="pacemaker" type="Dummy" />
                <primitive id="S1" class="stonith" type="fence_any" />
                <primitive id="S2" class="stonith" type="fence_sbd" />
                <group id="G1">
                    <primitive id="S3" class="stonith" type="fence_any" />
                    <primitive id="S4" class="stonith" type="fence_kdump" />
                </group>
                <clone id="C1">
                    <group id="G2">
                        <primitive id="S5" class="stonith" type="fence_any" />
                        <primitive id="S6" class="stonith" type="fence_watchdog" />
                    </group>
                </clone>
            </resources>
        """
    )


class GetAllResources(GetAllResourcesBase):
    def test_success(self):
        self.assertEqual(
            [
                el.attrib["id"]
                for el in stonith.get_all_resources(self.resources)
            ],
            ["S1", "S2", "S3", "S4", "S5", "S6"],
        )


class GetAllNodeIsolatingResources(GetAllResourcesBase):
    def test_success(self):
        self.assertEqual(
            [
                el.attrib["id"]
                for el in stonith.get_all_node_isolating_resources(
                    self.resources
                )
            ],
            ["S1", "S3", "S5"],
        )


class GetMisconfiguredResources(TestCase):
    def test_no_stonith(self):
        resources = etree.fromstring(
            """
            <resources>
                <primitive id="R" class="ocf" provider="pacemaker" type="Dummy">
                    <instance_attributes>
                        <nvpair name="action" value="value" />
                        <nvpair name="method" value="cycle" />
                    </instance_attributes>
                </primitive>
            </resources>
        """
        )
        self.assertEqual(
            stonith.get_misconfigured_resources(resources), ([], [], [])
        )

    def test_all_ok(self):
        resources = etree.fromstring(
            """
            <resources>
                <primitive id="S1" class="stonith" type="fence_something">
                    <instance_attributes>
                        <nvpair name="name" value="value" />
                    </instance_attributes>
                </primitive>
            </resources>
        """
        )
        self.assertEqual(
            stonith.get_misconfigured_resources(resources),
            (
                resources.findall("primitive[@id='S1']"),
                [],
                [],
            ),
        )

    def test_issues(self):
        resources = etree.fromstring(
            """
            <resources>
                <primitive id="S1" class="stonith" type="fence_something">
                    <instance_attributes>
                        <nvpair name="name" value="value" />
                        <nvpair name="method" value="onoff" />
                    </instance_attributes>
                </primitive>
                <primitive id="S2" class="stonith" type="fence_something">
                    <instance_attributes>
                        <nvpair name="action" value="value" />
                    </instance_attributes>
                </primitive>
                <primitive id="S3" class="stonith" type="fence_something">
                    <instance_attributes>
                        <nvpair name="method" value="cycle" />
                    </instance_attributes>
                </primitive>
                <primitive id="S4" class="stonith" type="fence_something">
                    <instance_attributes>
                        <nvpair name="action" value="value" />
                        <nvpair name="method" value="cycle" />
                    </instance_attributes>
                </primitive>
                <primitive id="S5" class="stonith" type="fence_sbd">
                    <instance_attributes>
                        <nvpair name="method" value="cycle" />
                    </instance_attributes>
                </primitive>
            </resources>
        """
        )
        stonith1 = resources.find("primitive[@id='S1']")
        stonith2 = resources.find("primitive[@id='S2']")
        stonith3 = resources.find("primitive[@id='S3']")
        stonith4 = resources.find("primitive[@id='S4']")
        stonith5 = resources.find("primitive[@id='S5']")
        self.assertEqual(
            stonith.get_misconfigured_resources(resources),
            (
                [stonith1, stonith2, stonith3, stonith4, stonith5],
                [stonith2, stonith4],
                [stonith3, stonith4],
            ),
        )


class ValidateStonithRestartlessUpdate(TestCase):
    RESOURCES = etree.fromstring(
        """
        <resources>
            <primitive id="supported" class="stonith" type="fence_scsi">
                <instance_attributes>
                    <nvpair name="devices" value="/dev/sda" />
                </instance_attributes>
            </primitive>
            <primitive id="empty" class="stonith" type="fence_scsi">
                <instance_attributes>
                    <nvpair id="empty-instance_attributes-devices"
                        name="devices" value="" />
                </instance_attributes>
            </primitive>
            <primitive id="no-devices" class="stonith" type="fence_scsi"/>
            <primitive id="unsupported_provider"
                class="stonith" provider="provider" type="fence_scsi"/>
            <primitive id="unsupported_type" class="stonith" type="fence_xvm"/>
            <primitive class="ocf" id="cp-01" provider="pacemaker" type="Dummy"/>
        </resources>
        """
    )

    def assert_unsupported_stonith_agent(self, resource_id, resource_type):
        stonith_el, report_list = stonith.validate_stonith_restartless_update(
            self.RESOURCES, resource_id
        )
        self.assertEqual(
            stonith_el,
            self.RESOURCES.find(f".//primitive[@id='{resource_id}']"),
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNSUPPORTED_AGENT,
                    resource_id=resource_id,
                    resource_type=resource_type,
                    supported_stonith_types=["fence_scsi", "fence_mpath"],
                )
            ],
        )

    def assert_no_devices(self, resource_id):
        stonith_el, report_list = stonith.validate_stonith_restartless_update(
            self.RESOURCES, resource_id
        )
        self.assertEqual(
            stonith_el,
            self.RESOURCES.find(f".//primitive[@id='{resource_id}']"),
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.STONITH_RESTARTLESS_UPDATE_UNABLE_TO_PERFORM,
                    reason=(
                        "no devices option configured for stonith device "
                        f"'{resource_id}'"
                    ),
                    reason_type="other",
                )
            ],
        )

    def test_supported(self):
        stonith_el, report_list = stonith.validate_stonith_restartless_update(
            self.RESOURCES, "supported"
        )
        self.assertEqual(
            stonith_el, self.RESOURCES.find(".//primitive[@id='supported']")
        )
        assert_report_item_list_equal(report_list, [])

    def test_nonexistent_id(self):
        stonith_el, report_list = stonith.validate_stonith_restartless_update(
            self.RESOURCES, "non-existent"
        )
        self.assertEqual(stonith_el, None)
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="non-existent",
                    expected_types=["primitive"],
                    context_type="resources",
                    context_id="",
                )
            ],
        )

    def test_not_a_resource_id(self):
        stonith_el, report_list = stonith.validate_stonith_restartless_update(
            self.RESOURCES, "empty-instance_attributes-devices"
        )
        self.assertEqual(stonith_el, None)
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="empty-instance_attributes-devices",
                    expected_types=["primitive"],
                    current_type="nvpair",
                )
            ],
        )

    def test_devices_empty(self):
        self.assert_no_devices("empty")

    def test_missing_devices_attr(self):
        self.assert_no_devices("no-devices")

    def test_unsupported_class(self):
        self.assert_unsupported_stonith_agent("cp-01", "Dummy")

    def test_unsupported_provider(self):
        self.assert_unsupported_stonith_agent(
            "unsupported_provider", "fence_scsi"
        )

    def test_unsupported_type(self):
        self.assert_unsupported_stonith_agent("unsupported_type", "fence_xvm")


def _fixture_stonith_el(host_map_value):
    if host_map_value is None:
        return etree.fromstring(
            '<primitive id="fence-mepath" class="stonith" type="fence_mpath" />'
        )
    return etree.fromstring(
        f"""
        <primitive id="fence-mepath" class="stonith" type="fence_mpath">
            <instance_attributes id="fence-mepath-instance_attributes">
                <nvpair id="fence-mepath-instance_attributes-pcmk_host_map"
                    name="pcmk_host_map" value="{host_map_value}" />
            </instance_attributes>
        </primitive>
        """
    )


class GetNodeKeyMapForMpath(TestCase):
    NODE_LABELS = ["rh9-1", "rh9-2", "rh9-3"]

    def assert_success(self, value, result_dict, node_labels=None):
        if node_labels is None:
            node_labels = self.NODE_LABELS
        self.assertEqual(
            stonith.get_node_key_map_for_mpath(
                _fixture_stonith_el(value), node_labels
            ),
            result_dict,
        )

    def assert_error(self, value, node_labels=None, missing_nodes=None):
        if node_labels is None:
            node_labels = self.NODE_LABELS
        if missing_nodes is None:
            missing_nodes = self.NODE_LABELS
        assert_raise_library_error(
            lambda: stonith.get_node_key_map_for_mpath(
                _fixture_stonith_el(value), node_labels
            ),
            fixture.error(
                reports.codes.STONITH_RESTARTLESS_UPDATE_MISSING_MPATH_KEYS,
                pcmk_host_map_value=value if value else None,
                missing_nodes=sorted(missing_nodes),
            ),
        )

    def test_invalid_part_skipped(self):
        self.assert_success(
            "  ;\trh9-1:1;rh9-2==22;rh9-3 :3;e",
            {"rh9-1": "1"},
            node_labels=self.NODE_LABELS[0:1],
        )

    def test_success_colon_sign_as_assignment_char(self):
        self.assert_success(
            "rh9-1:1;rh9-2:2;rh9-3:3",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_equal_sign_as_assignment_char(self):
        self.assert_success(
            "rh9-1=1;rh9-2=2;rh9-3=3",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_mixed_assignment_char(self):
        self.assert_success(
            "rh9-1:1;rh9-2=2;rh9-3:3",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_semicolon_as_separator(self):
        self.assert_success(
            "rh9-1:1;rh9-2:2;rh9-3:3;",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_space_as_separator(self):
        self.assert_success(
            "rh9-1:1 rh9-2:2 rh9-3:3 ",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_tab_as_separator(self):
        self.assert_success(
            "rh9-1:1\trh9-2:2\trh9-3:3\t",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
        )

    def test_success_mixed_separators(self):
        self.assert_success(
            "rh9-1:1;rh9-2:2 rh9-3:3\trh9-4:4",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3", "rh9-4": "4"},
            node_labels=self.NODE_LABELS + ["rh9-4"],
        )

    def test_success_more_keys_than_current_nodes(self):
        self.assert_success(
            "rh9-1:1;rh9-2:2;rh9-3:3",
            {"rh9-1": "1", "rh9-2": "2", "rh9-3": "3"},
            node_labels=self.NODE_LABELS[:-1],
        )

    def test_empty_nodes(self):
        self.assert_success(
            "rh9-1:1;rh9-2:2", {"rh9-1": "1", "rh9-2": "2"}, node_labels=[]
        )

    def test_missing_value(self):
        self.assert_error(None)

    def test_empty_value(self):
        self.assert_error("")

    def test_not_enough_keys_for_nodes_misconfiguration(self):
        self.assert_error("rh9-1:1;rh9-2;rh9-3:3", missing_nodes=["rh9-2"])

    def test_not_enough_keys_for_nodes_missing(self):
        self.assert_error("rh9-1:1", missing_nodes=["rh9-3", "rh9-2"])
