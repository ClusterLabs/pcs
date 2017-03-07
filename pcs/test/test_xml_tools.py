from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import xml_tools as lib
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.pcs_unittest import TestCase

class GetSubElementTest(TestCase):
    def setUp(self):
        self.root = etree.Element("root")
        self.sub = etree.SubElement(self.root, "sub_element")

    def test_sub_element_exists(self):
        self.assertEqual(
            self.sub, lib.get_sub_element(self.root, "sub_element")
        )

    def test_new_no_id(self):
        assert_xml_equal(
            '<new_element/>',
            etree.tostring(
                lib.get_sub_element(self.root, "new_element")
            ).decode()
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_with_id(self):
        assert_xml_equal(
            '<new_element id="new_id"/>',
            etree.tostring(
                lib.get_sub_element(self.root, "new_element", "new_id")
            ).decode()
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element id="new_id"/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_first(self):
        lib.get_sub_element(self.root, "new_element", "new_id", 0)
        assert_xml_equal(
            """
            <root>
                <new_element id="new_id"/>
                <sub_element/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_last(self):
        lib.get_sub_element(self.root, "new_element", "new_id", None)
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element id="new_id"/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )


class EtreeElementAttributesToDictTest(TestCase):
    def setUp(self):
        self.el = etree.Element(
            "test_element",
            {
                "id": "test_id",
                "description": "some description",
                "attribute": "value",
            }
        )

    def test_only_existing(self):
        self.assertEqual(
            {
                "id": "test_id",
                "attribute": "value",
            },
            lib.etree_element_attibutes_to_dict(self.el, ["id", "attribute"])
        )

    def test_only_not_existing(self):
        self.assertEqual(
            {
                "_id": None,
                "not_existing": None,
            },
            lib.etree_element_attibutes_to_dict(
                self.el, ["_id", "not_existing"]
            )
        )

    def test_mix(self):
        self.assertEqual(
            {
                "id": "test_id",
                "attribute": "value",
                "not_existing": None,
            },
            lib.etree_element_attibutes_to_dict(
                self.el, ["id", "not_existing", "attribute"]
            )
        )
