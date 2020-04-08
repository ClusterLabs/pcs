from unittest import TestCase

from lxml import etree

from pcs.lib.cib import stonith


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
            (resources.findall("primitive[@id='S1']"), [], [],),
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
