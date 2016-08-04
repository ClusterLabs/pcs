from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from lxml import etree

import pcs.lib.booth.resource as booth_resource
from pcs.test.tools.pcs_mock import mock


def fixture_resources_with_booth(booth_config_file_path):
    return etree.fromstring('''
        <resources>
            <primitive type="booth-site">
                <instance_attributes>
                    <nvpair name="config" value="{0}"/>
                </instance_attributes>
            </primitive>
        </resources>
    '''.format(booth_config_file_path))

def fixture_booth_element(id, booth_config_file_path):
    return etree.fromstring('''
        <primitive id="{0}" type="booth-site">
            <instance_attributes>
                <nvpair name="config" value="{1}"/>
            </instance_attributes>
        </primitive>
    '''.format(id, booth_config_file_path))

def fixture_ip_element(id, ip=""):
    return etree.fromstring('''
        <primitive id="{0}" type="IPaddr2">
            <instance_attributes id="{0}-ia">
            <nvpair
                id="booth-booth-{0}-ia-ip"
                name="ip"
                value="192.168.122.31"
            />
          </instance_attributes>
        </primitive>
    '''.format(id, ip))

class CreateResourceIdTest(TestCase):
    @mock.patch("pcs.lib.booth.resource.find_unique_id")
    def test_return_new_uinq_id(self, mock_find_unique_id):
        resources_section = etree.fromstring('''<resources/>''')
        mock_find_unique_id.side_effect = (
            lambda resources_section, id: "{0}-n".format(id)
        )
        self.assertEqual(
            "booth-some-name-ip-n",
            booth_resource.create_resource_id(
                resources_section, "some-name", "ip"
            )
        )

class FindBoothResourceElementsTest(TestCase):
    def test_returns_empty_list_when_no_matching_booth_element(self):
        self.assertEqual([], booth_resource.find_for_config(
            fixture_resources_with_booth("/ANOTHER/PATH/TO/CONF"),
            "/PATH/TO/CONF"
        ))


    def test_returns_all_found_resource_elements(self):
        resources = etree.fromstring('<resources/>')
        first = fixture_booth_element("first", "/PATH/TO/CONF")
        second = fixture_booth_element("second", "/ANOTHER/PATH/TO/CONF")
        third = fixture_booth_element("third", "/PATH/TO/CONF")
        for element in [first, second,third]:
            resources.append(element)

        self.assertEqual(
            [first, third],
            booth_resource.find_for_config(
                resources,
                "/PATH/TO/CONF"
            )
        )

class RemoveFromClusterTest(TestCase):
    def call(self, resources_section, remove_multiple=False):
        mock_resource_remove = mock.Mock()
        num_of_removed_booth_resources = booth_resource.get_remover(
            mock_resource_remove
        )(
            resources_section,
            "/PATH/TO/CONF",
            remove_multiple,
        )
        return (
            mock_resource_remove,
            num_of_removed_booth_resources
        )

    def fixture_resources_including_two_booths(self):
        resources_section = etree.fromstring('<resources/>')
        first = fixture_booth_element("first", "/PATH/TO/CONF")
        second = fixture_booth_element("second", "/PATH/TO/CONF")
        resources_section.append(first)
        resources_section.append(second)
        return resources_section

    def test_raises_when_booth_resource_not_found(self):
        self.assertRaises(
            booth_resource.BoothNotFoundInCib,
            lambda: self.call(etree.fromstring('<resources/>')),
        )

    def test_raises_when_more_booth_resources_found(self):
        resources_section = self.fixture_resources_including_two_booths()
        self.assertRaises(
            booth_resource.BoothMultipleOccurenceFoundInCib,
            lambda: self.call(resources_section),
        )

    def test_returns_number_of_removed_elements(self):
        resources_section = self.fixture_resources_including_two_booths()
        mock_resource_remove, num_of_removed_booth_resources = self.call(
            resources_section,
            remove_multiple=True
        )
        self.assertEqual(num_of_removed_booth_resources, 2)
        self.assertEqual(
            mock_resource_remove.mock_calls, [
                mock.call('first'),
                mock.call('second'),
            ]
        )

    def test_remove_ip_when_is_only_booth_sibling_in_group(self):
        resources_section = etree.fromstring('''
            <resources>
                <group>
                    <primitive id="ip" type="IPaddr2"/>
                    <primitive id="booth" type="booth-site">
                        <instance_attributes>
                            <nvpair name="config" value="/PATH/TO/CONF"/>
                        </instance_attributes>
                    </primitive>
                </group>
            </resources>
        ''')

        mock_resource_remove, _ = self.call(
            resources_section,
            remove_multiple=True
        )
        self.assertEqual(
            mock_resource_remove.mock_calls, [
                mock.call('ip'),
                mock.call('booth'),
            ]
        )


class FindBindedIpTest(TestCase):
    def fixture_resource_section(self, ip_element_list):
        resources_section = etree.fromstring('<resources/>')
        group = etree.SubElement(resources_section, "group")
        group.append(fixture_booth_element("booth1", "/PATH/TO/CONF"))
        for ip_element in ip_element_list:
            group.append(ip_element)
        return resources_section


    def test_returns_None_when_no_ip(self):
        self.assertEqual(
            None,
            booth_resource.find_binded_single_ip(
                self.fixture_resource_section([]),
                "/PATH/TO/CONF",
            )
        )

    def test_returns_ip_when_correctly_found(self):
        self.assertEqual(
            "192.168.122.31",
            booth_resource.find_binded_single_ip(
                self.fixture_resource_section([
                    fixture_ip_element("ip1", "192.168.122.31"),
                ]),
                "/PATH/TO/CONF",
            )
        )

    def test_returns_None_when_more_ip(self):
        self.assertEqual(
            None,
            booth_resource.find_binded_single_ip(
                self.fixture_resource_section([
                    fixture_ip_element("ip1", "192.168.122.31"),
                    fixture_ip_element("ip2", "192.168.122.32"),
                ]),
                "/PATH/TO/CONF",
            )
        )
