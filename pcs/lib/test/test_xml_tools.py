from unittest import TestCase
from lxml import etree

from pcs.lib import xml_tools as lib
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.xml import etree_to_str

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
            etree_to_str(
                lib.get_sub_element(self.root, "new_element")
            )
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element/>
            </root>
            """,
            etree_to_str(self.root)
        )

    def test_new_with_id(self):
        assert_xml_equal(
            '<new_element id="new_id"/>',
            etree_to_str(
                lib.get_sub_element(self.root, "new_element", "new_id")
            )
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element id="new_id"/>
            </root>
            """,
            etree_to_str(self.root)
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
            etree_to_str(self.root)
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
            etree_to_str(self.root)
        )

    def test_new_not_append(self):
        subelement = lib.get_sub_element(
            self.root, "new_element", "new_id", append_if_missing=False
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
            </root>
            """,
            etree_to_str(self.root)
        )
        assert_xml_equal(
            """<new_element id="new_id" />""",
            etree_to_str(subelement)
        )

class UpdateAttributeRemoveEmpty(TestCase):
    def setUp(self):
        self.el = etree.Element(
            "test_element",
            {
                "a": "A",
                "b": "B",
            }
        )

    def assert_xml_equal(self, expected):
        assert_xml_equal(expected, etree_to_str(self.el))

    def test_set_new_attr(self):
        lib.update_attribute_remove_empty(self.el, "c", "C")
        self.assert_xml_equal('<test_element a="A" b="B" c="C" />')

    def test_change_existing_attr(self):
        lib.update_attribute_remove_empty(self.el, "b", "b1")
        self.assert_xml_equal('<test_element a="A" b="b1" />')

    def test_remove_existing_attr(self):
        lib.update_attribute_remove_empty(self.el, "b", "")
        self.assert_xml_equal('<test_element a="A" />')

    def test_zero_does_not_remove(self):
        lib.update_attribute_remove_empty(self.el, "b", "0")
        self.assert_xml_equal('<test_element a="A" b="0" />')

    def test_remove_missing_attr(self):
        lib.update_attribute_remove_empty(self.el, "c", "")
        self.assert_xml_equal('<test_element a="A" b="B" />')

    def test_more(self):
        lib.update_attributes_remove_empty(self.el, {
            "a": "X",
            "b": "",
            "c": "C",
            "d": "",
        })
        self.assert_xml_equal('<test_element a="X" c="C" />')


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

class RemoveWhenPointless(TestCase):
    def assert_count_tags_after_call(self, count, tag, **kwargs):
        tree = etree.fromstring(
            """
            <root>
                <empty />
                <with-subelement>
                    <subelement/>
                </with-subelement>
                <with-attr some="attribute"/>
                <with-only-id id="1"/>
            </root>
            """
        )
        xpath = ".//{0}".format(tag)
        lib.remove_when_pointless(tree.find(xpath), **kwargs)
        self.assertEqual(len(tree.xpath(xpath)), count)

    def assert_remove(self, tag, **kwargs):
        self.assert_count_tags_after_call(0, tag, **kwargs)

    def assert_keep(self, tag, **kwargs):
        self.assert_count_tags_after_call(1, tag, **kwargs)

    def test_remove_empty(self):
        self.assert_remove("empty")

    def test_keep_with_subelement(self):
        self.assert_keep("with-subelement")

    def test_keep_when_attr(self):
        self.assert_keep("with-attr")

    def test_remove_when_attr_not_important(self):
        self.assert_remove("with-attr", attribs_important=False)

    def test_remove_when_only_id(self):
        self.assert_remove("with-only-id")


class AppendWhenUseful(TestCase):
    def setUp(self):
        self.tree_str = """
            <root>
                <parent-A>
                    <element-A1 />
                    <element-A2 attr="test" />
                </parent-A>
                <parent-B>
                    <element-B1 attr="test"/>
                    <element-B2 />
                </parent-B>
            </root>
        """
        self.tree = etree.fromstring(self.tree_str)
        self.parent = self.tree.find(".//parent-A")

    def test_already_appended(self):
        element = self.tree.find(".//element-A2")
        lib.append_when_useful(self.parent, element)
        assert_xml_equal(
            self.tree_str,
            etree_to_str(self.tree)
        )

    def test_different_parent_useful(self):
        element = self.tree.find(".//element-B1")
        lib.append_when_useful(self.parent, element)
        assert_xml_equal(
            """
                <root>
                    <parent-A>
                        <element-A1 />
                        <element-A2 attr="test" />
                        <element-B1 attr="test"/>
                    </parent-A>
                    <parent-B>
                        <element-B2 />
                    </parent-B>
                </root>
            """,
            etree_to_str(self.tree)
        )

    def test_different_parent_not_useful(self):
        element = self.tree.find(".//element-B2")
        lib.append_when_useful(self.parent, element)
        assert_xml_equal(
            self.tree_str,
            etree_to_str(self.tree)
        )

    def test_index(self):
        element = etree.Element("new", attr="test")
        lib.append_when_useful(self.parent, element, index=1)
        assert_xml_equal(
            """
                <root>
                    <parent-A>
                        <element-A1 />
                        <new attr="test" />
                        <element-A2 attr="test" />
                    </parent-A>
                    <parent-B>
                        <element-B1 attr="test"/>
                        <element-B2 />
                    </parent-B>
                </root>
            """,
            etree_to_str(self.tree)
        )

    def test_not_useful(self):
        element = etree.Element("new")
        lib.append_when_useful(self.parent, element)
        assert_xml_equal(
            self.tree_str,
            etree_to_str(self.tree)
        )

    def test_not_useful_with_attributes(self):
        element = etree.Element("new", attr="test")
        lib.append_when_useful(self.parent, element, attribs_important=False)
        assert_xml_equal(
            self.tree_str,
            etree_to_str(self.tree)
        )
