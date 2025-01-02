from unittest import (
    TestCase,
    mock,
)

from lxml import etree

import pcs.lib.booth.resource as booth_resource


def fixture_resources_with_booth(booth_config_file_path):
    return etree.fromstring(
        """
        <resources>
            <primitive type="booth-site">
                <instance_attributes>
                    <nvpair name="config" value="{0}"/>
                </instance_attributes>
            </primitive>
        </resources>
    """.format(booth_config_file_path)
    )


def fixture_booth_element(_id, booth_config_file_path):
    return etree.fromstring(
        """
        <primitive id="{0}" type="booth-site">
            <instance_attributes>
                <nvpair name="config" value="{1}"/>
            </instance_attributes>
        </primitive>
    """.format(_id, booth_config_file_path)
    )


def fixture_ip_element(_id, ip=""):
    return etree.fromstring(
        """
        <primitive id="{0}" type="IPaddr2">
            <instance_attributes id="{0}-ia">
            <nvpair
                id="booth-booth-{0}-ia-ip"
                name="ip"
                value="{1}"
            />
          </instance_attributes>
        </primitive>
    """.format(_id, ip)
    )


class CreateResourceIdTest(TestCase):
    @mock.patch("pcs.lib.booth.resource.find_unique_id")
    def test_return_new_uinq_id(self, mock_find_unique_id):
        resources_section = etree.fromstring("""<resources/>""")
        mock_find_unique_id.side_effect = lambda resources_section, _id: (
            "{0}-n".format(_id)
        )
        self.assertEqual(
            "booth-some-name-ip-n",
            booth_resource.create_resource_id(
                resources_section, "some-name", "ip"
            ),
        )


class FindBoothResourceElementsTest(TestCase):
    def test_returns_empty_list_when_no_matching_booth_element(self):
        self.assertEqual(
            [],
            booth_resource.find_for_config(
                fixture_resources_with_booth("/ANOTHER/PATH/TO/CONF"),
                "/PATH/TO/CONF",
            ),
        )

    def test_returns_all_found_resource_elements(self):
        resources = etree.fromstring("<resources/>")
        first = fixture_booth_element("first", "/PATH/TO/CONF")
        second = fixture_booth_element("second", "/ANOTHER/PATH/TO/CONF")
        third = fixture_booth_element("third", "/PATH/TO/CONF")
        for element in [first, second, third]:
            resources.append(element)

        self.assertEqual(
            [first, third],
            booth_resource.find_for_config(resources, "/PATH/TO/CONF"),
        )


class FindElementsToRemove(TestCase):
    @staticmethod
    def find_booth_resources(tree):
        return tree.xpath('.//primitive[@type="booth-site"]')

    def test_remove_ip_when_is_only_booth_sibling_in_group(self):
        group = etree.fromstring(
            """
            <group>
                <primitive id="ip" type="IPaddr2"/>
                <primitive id="booth" type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
            </group>
        """
        )

        elements = booth_resource.find_elements_to_remove(
            self.find_booth_resources(group)
        )
        self.assertEqual(
            [
                group.find("./primitive[@id='ip']"),
                group.find("./primitive[@id='booth']"),
            ],
            elements,
        )

    def test_remove_ip_when_group_is_disabled_1(self):
        group = etree.fromstring(
            """
            <group>
                <primitive id="ip" type="IPaddr2"/>
                <primitive id="booth" type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
                <meta_attributes>
                    <nvpair name="target-role" value="Stopped"/>
                </meta_attributes>
            </group>
        """
        )

        elements = booth_resource.find_elements_to_remove(
            self.find_booth_resources(group)
        )
        self.assertEqual(
            [
                group.find("./primitive[@id='ip']"),
                group.find("./primitive[@id='booth']"),
            ],
            elements,
        )

    def test_remove_ip_when_group_is_disabled_2(self):
        group = etree.fromstring(
            """
            <group>
                <meta_attributes>
                    <nvpair name="target-role" value="Stopped"/>
                </meta_attributes>
                <primitive id="ip" type="IPaddr2"/>
                <primitive id="booth" type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
            </group>
        """
        )

        elements = booth_resource.find_elements_to_remove(
            self.find_booth_resources(group)
        )
        self.assertEqual(
            [
                group.find("./primitive[@id='ip']"),
                group.find("./primitive[@id='booth']"),
            ],
            elements,
        )

    def test_dont_remove_ip_when_group_has_other_resources(self):
        group = etree.fromstring(
            """
            <group>
                <primitive id="ip" type="IPaddr2"/>
                <primitive id="booth" type="booth-site">
                    <instance_attributes>
                        <nvpair name="config" value="/PATH/TO/CONF"/>
                    </instance_attributes>
                </primitive>
                <primitive id="dummy" type="Dummy"/>
            </group>
        """
        )

        elements = booth_resource.find_elements_to_remove(
            self.find_booth_resources(group)
        )
        self.assertEqual([group.find("./primitive[@id='booth']")], elements)


class FindBoundIpTest(TestCase):
    @staticmethod
    def fixture_resource_section(ip_element_list):
        resources_section = etree.fromstring("<resources/>")
        group = etree.SubElement(resources_section, "group")
        group.append(fixture_booth_element("booth1", "/PATH/TO/CONF"))
        for ip_element in ip_element_list:
            group.append(ip_element)
        return resources_section

    def test_returns_none_when_no_ip(self):
        self.assertEqual(
            [],
            booth_resource.find_bound_ip(
                self.fixture_resource_section([]),
                "/PATH/TO/CONF",
            ),
        )

    def test_returns_ip_when_correctly_found(self):
        self.assertEqual(
            ["192.168.122.31"],
            booth_resource.find_bound_ip(
                self.fixture_resource_section(
                    [
                        fixture_ip_element("ip1", "192.168.122.31"),
                    ]
                ),
                "/PATH/TO/CONF",
            ),
        )

    def test_returns_none_when_more_ip(self):
        self.assertEqual(
            ["192.168.122.31", "192.168.122.32"],
            booth_resource.find_bound_ip(
                self.fixture_resource_section(
                    [
                        fixture_ip_element("ip1", "192.168.122.31"),
                        fixture_ip_element("ip2", "192.168.122.32"),
                    ]
                ),
                "/PATH/TO/CONF",
            ),
        )
