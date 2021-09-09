from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib import stonith

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


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
            </resources>
        """
        )
        stonith1 = resources.find("primitive[@id='S1']")
        stonith2 = resources.find("primitive[@id='S2']")
        stonith3 = resources.find("primitive[@id='S3']")
        stonith4 = resources.find("primitive[@id='S4']")
        self.assertEqual(
            stonith.get_misconfigured_resources(resources),
            (
                [stonith1, stonith2, stonith3, stonith4],
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
                    supported_stonith_types=["fence_scsi"],
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
