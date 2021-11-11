from unittest import TestCase
from lxml import etree

from pcs.lib.cib.resource import group


class IsGroup(TestCase):
    def test_is_group(self):
        self.assertTrue(group.is_group(etree.fromstring("<group/>")))
        self.assertFalse(group.is_group(etree.fromstring("<clone/>")))
        self.assertFalse(group.is_group(etree.fromstring("<master/>")))


class GetInnerResource(TestCase):
    def assert_inner_resource(self, resource_id, xml):
        self.assertEqual(
            resource_id,
            [
                element.attrib.get("id", "")
                for element in group.get_inner_resources(etree.fromstring(xml))
            ],
        )

    def test_one(self):
        self.assert_inner_resource(
            ["A"],
            """
                <group id="G">
                    <meta_attributes />
                    <primitive id="A" />
                    <meta_attributes />
                </group>
            """,
        )

    def test_more(self):
        self.assert_inner_resource(
            ["A", "C", "B"],
            """
                <group id="G">
                    <meta_attributes />
                    <primitive id="A" />
                    <primitive id="C" />
                    <primitive id="B" />
                    <meta_attributes />
                </group>
            """,
        )
