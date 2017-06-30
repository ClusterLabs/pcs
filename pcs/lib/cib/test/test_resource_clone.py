from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree

from pcs.lib.cib.resource import clone
from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.assertions import assert_xml_equal

class AppendNewCommon(TestCase):
    def setUp(self):
        self.cib = etree.fromstring("""
            <cib>
                <resources>
                    <primitive id="R"/>
                </resources>
            </cib>
        """)
        self.resources = self.cib.find(".//resources")
        self.primitive = self.cib.find(".//primitive")

    def assert_clone_effect(self, options, xml):
        clone.append_new(
            clone.TAG_CLONE,
            self.resources,
            self.primitive,
            options
        )
        assert_xml_equal(etree.tostring(self.cib).decode(), xml)

    def test_add_without_options(self):
        self.assert_clone_effect({}, """
            <cib>
                <resources>
                    <clone id="R-clone">
                        <primitive id="R"/>
                    </clone>
                </resources>
            </cib>
        """)

    def test_add_with_options(self):
        self.assert_clone_effect({"a": "b"}, """
            <cib>
                <resources>
                    <clone id="R-clone">
                        <primitive id="R"/>
                        <meta_attributes id="R-clone-meta_attributes">
                            <nvpair id="R-clone-meta_attributes-a"
                                name="a" value="b"
                            />
                        </meta_attributes>
                    </clone>
                </resources>
            </cib>
        """)


class IsAnyClone(TestCase):
    def test_is_clone(self):
        self.assertTrue(clone.is_clone(etree.fromstring("<clone/>")))
        self.assertFalse(clone.is_clone(etree.fromstring("<master/>")))
        self.assertFalse(clone.is_clone(etree.fromstring("<group/>")))

    def test_is_master(self):
        self.assertTrue(clone.is_master(etree.fromstring("<master/>")))
        self.assertFalse(clone.is_master(etree.fromstring("<clone/>")))
        self.assertFalse(clone.is_master(etree.fromstring("<group/>")))

    def test_is_any_clone(self):
        self.assertTrue(clone.is_any_clone(etree.fromstring("<clone/>")))
        self.assertTrue(clone.is_any_clone(etree.fromstring("<master/>")))
        self.assertFalse(clone.is_any_clone(etree.fromstring("<group/>")))


class GetInnerResource(TestCase):
    def assert_inner_resource(self, resource_id, xml):
        self.assertEqual(
            resource_id,
            clone.get_inner_resource(etree.fromstring(xml)).get("id", "")
        )

    def test_primitive(self):
        self.assert_inner_resource(
            "A",
            """
                <clone id="A-clone">
                    <meta_attributes />
                    <primitive id="A" />
                    <meta_attributes />
                </clone>
            """
        )

    def test_group(self):
        self.assert_inner_resource(
            "A",
            """
                <clone id="A-clone">
                    <meta_attributes />
                    <group id="A" />
                    <meta_attributes />
                </clone>
            """
        )
