from unittest import TestCase

from lxml import etree

from pcs.lib.cib import nvpair
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools.assertions import assert_xml_equal
from pcs_test.tools.xml import etree_to_str


class AppendNewNvpair(TestCase):
    def test_append_new_nvpair_to_given_element(self):
        # pylint: disable=no-self-use
        nvset_element = etree.fromstring('<nvset id="a"/>')
        id_provider = IdProvider(nvset_element)
        # pylint: disable=protected-access
        nvpair._append_new_nvpair(nvset_element, "b", "c", id_provider)
        assert_xml_equal(
            etree_to_str(nvset_element),
            """
            <nvset id="a">
                <nvpair id="a-b" name="b" value="c"></nvpair>
            </nvset>
            """,
        )

    def test_with_id_provider(self):
        # pylint: disable=no-self-use
        nvset_element = etree.fromstring('<nvset id="a"/>')
        provider = IdProvider(nvset_element)
        provider.book_ids("a-b")
        # pylint: disable=protected-access
        nvpair._append_new_nvpair(nvset_element, "b", "c", provider)
        assert_xml_equal(
            etree_to_str(nvset_element),
            """
            <nvset id="a">
                <nvpair id="a-b-1" name="b" value="c"></nvpair>
            </nvset>
            """,
        )


class UpdateNvsetTest(TestCase):
    def test_updates_nvset(self):
        # pylint: disable=no-self-use
        nvset_element = etree.fromstring(
            """
            <instance_attributes id="iattrs">
                <nvpair id="iattrs-a" name="a" value="b"/>
                <nvpair id="iattrs-c" name="c" value="d"/>
                <nvpair id="iattrs-e" name="e" value="f"/>
            </instance_attributes>
        """
        )
        id_provider = IdProvider(nvset_element)
        nvpair.update_nvset(
            nvset_element,
            {
                "a": "B",
                "c": "",
                "g": "h",
            },
            id_provider,
        )
        assert_xml_equal(
            """
            <instance_attributes id="iattrs">
                <nvpair id="iattrs-a" name="a" value="B"/>
                <nvpair id="iattrs-e" name="e" value="f"/>
                <nvpair id="iattrs-g" name="g" value="h"/>
            </instance_attributes>
            """,
            etree_to_str(nvset_element),
        )

    def test_empty_value_has_no_effect(self):
        # pylint: disable=no-self-use
        xml = """
            <instance_attributes id="iattrs">
                <nvpair id="iattrs-b" name="a" value="b"/>
                <nvpair id="iattrs-d" name="c" value="d"/>
                <nvpair id="iattrs-f" name="e" value="f"/>
            </instance_attributes>
        """
        nvset_element = etree.fromstring(xml)
        id_provider = IdProvider(nvset_element)
        nvpair.update_nvset(nvset_element, {}, id_provider)
        assert_xml_equal(xml, etree_to_str(nvset_element))

    def test_keep_empty_nvset(self):
        # pylint: disable=no-self-use
        xml_pre = """
            <resource>
                <instance_attributes id="iattrs">
                    <nvpair id="iattrs-a" name="a" value="b"/>
                </instance_attributes>
            </resource>
        """
        xml_post = """
            <resource>
                <instance_attributes id="iattrs" />
            </resource>
        """
        xml = etree.fromstring(xml_pre)
        nvset_element = xml.find("instance_attributes")
        id_provider = IdProvider(nvset_element)
        nvpair.update_nvset(nvset_element, {"a": ""}, id_provider)
        assert_xml_equal(xml_post, etree_to_str(xml))


class SetNvpairInNvsetTest(TestCase):
    def setUp(self):
        self.nvset = etree.Element("nvset", id="nvset")
        etree.SubElement(
            self.nvset, "nvpair", id="nvset-attr", name="attr", value="1"
        )
        etree.SubElement(
            self.nvset, "nvpair", id="nvset-attr2", name="attr2", value="2"
        )
        etree.SubElement(
            self.nvset, "notnvpair", id="nvset-test", name="test", value="0"
        )
        self.id_provider = IdProvider(self.nvset)

    def test_update(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr", "10", self.id_provider)
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="10"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree_to_str(self.nvset),
        )

    def test_add(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "test", "0", self.id_provider)
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
                <nvpair id="nvset-test-1" name="test" value="0"/>
            </nvset>
            """,
            etree_to_str(self.nvset),
        )

    def test_remove(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr2", "", self.id_provider)
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree_to_str(self.nvset),
        )

    def test_remove_not_existing(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr3", "", self.id_provider)
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree_to_str(self.nvset),
        )


class AppendNewNvsetTest(TestCase):
    def test_append_new_nvset_to_given_element(self):
        # pylint: disable=no-self-use
        context_element = etree.fromstring('<context id="a"/>')
        id_provider = IdProvider(context_element)
        nvpair.append_new_nvset(
            "instance_attributes",
            context_element,
            {
                "a": "b",
                "c": "d",
            },
            id_provider,
        )
        assert_xml_equal(
            """
                <context id="a">
                    <instance_attributes id="a-instance_attributes">
                        <nvpair
                            id="a-instance_attributes-a" name="a" value="b"
                        />
                        <nvpair
                            id="a-instance_attributes-c" name="c" value="d"
                        />
                    </instance_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_with_id_provider_booked_ids(self):
        # pylint: disable=no-self-use
        context_element = etree.fromstring('<context id="a"/>')
        provider = IdProvider(context_element)
        provider.book_ids("a-instance_attributes", "a-instance_attributes-1-a")
        nvpair.append_new_nvset(
            "instance_attributes",
            context_element,
            {
                "a": "b",
                "c": "d",
            },
            provider,
        )
        assert_xml_equal(
            """
                <context id="a">
                    <instance_attributes id="a-instance_attributes-1">
                        <nvpair
                            id="a-instance_attributes-1-a-1" name="a" value="b"
                        />
                        <nvpair
                            id="a-instance_attributes-1-c" name="c" value="d"
                        />
                    </instance_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )


class ArrangeFirstNvsetTest(TestCase):
    def setUp(self):
        self.root = etree.Element("root", id="root")
        self.nvset = etree.SubElement(self.root, "nvset", id="nvset")
        etree.SubElement(
            self.nvset, "nvpair", id="nvset-attr", name="attr", value="1"
        )
        etree.SubElement(
            self.nvset, "nvpair", id="nvset-attr2", name="attr2", value="2"
        )
        etree.SubElement(
            self.nvset, "notnvpair", id="nvset-test", name="test", value="0"
        )
        self.id_provider = IdProvider(self.nvset)

    def test_empty_value_has_no_effect(self):
        nvpair.arrange_first_nvset("nvset", self.root, {}, self.id_provider)
        assert_xml_equal(
            """
                <nvset id="nvset">
                    <nvpair id="nvset-attr" name="attr" value="1"/>
                    <nvpair id="nvset-attr2" name="attr2" value="2"/>
                    <notnvpair id="nvset-test" name="test" value="0"/>
                </nvset>
            """,
            etree_to_str(self.nvset),
        )

    def test_update_existing_nvset(self):
        nvpair.arrange_first_nvset(
            "nvset",
            self.root,
            {"attr": "10", "new_one": "20", "test": "0", "attr2": ""},
            self.id_provider,
        )
        assert_xml_equal(
            """
                <nvset id="nvset">
                    <nvpair id="nvset-attr" name="attr" value="10"/>
                    <notnvpair id="nvset-test" name="test" value="0"/>
                    <nvpair id="nvset-new_one" name="new_one" value="20"/>
                    <nvpair id="nvset-test-1" name="test" value="0"/>
                </nvset>
            """,
            etree_to_str(self.nvset),
        )

    def test_create_new_nvset_if_does_not_exist(self):
        root = etree.Element("root", id="root")
        nvpair.arrange_first_nvset(
            "nvset",
            root,
            {"attr": "10", "new_one": "20", "test": "0", "attr2": ""},
            self.id_provider,
        )

        assert_xml_equal(
            """
            <root id="root">
                <nvset id="root-nvset">
                    <nvpair id="root-nvset-attr" name="attr" value="10"/>
                    <nvpair id="root-nvset-new_one" name="new_one" value="20"/>
                    <nvpair id="root-nvset-test" name="test" value="0"/>
                </nvset>
            </root>
            """,
            etree_to_str(root),
        )


class GetNvsetTest(TestCase):
    def test_success(self):
        nvset = etree.XML(
            """
            <nvset>
                <nvpair id="nvset-name1" name="name1" value="value1"/>
                <nvpair id="nvset-name2" name="name2" value="value2"/>
                <nvpair id="nvset-name3" name="name3"/>
            </nvset>
            """
        )
        self.assertEqual(
            [
                {"id": "nvset-name1", "name": "name1", "value": "value1"},
                {"id": "nvset-name2", "name": "name2", "value": "value2"},
                {"id": "nvset-name3", "name": "name3", "value": None},
            ],
            nvpair.get_nvset(nvset),
        )


class GetValue(TestCase):
    def assert_find_value(self, tag_name, name, value, xml, default=None):
        self.assertEqual(
            value,
            nvpair.get_value(tag_name, etree.fromstring(xml), name, default),
        )

    def test_return_value_when_name_exists(self):
        self.assert_find_value(
            "meta_attributes",
            "SOME-NAME",
            "some-value",
            """
                <context>
                    <meta_attributes>
                        <nvpair name="SOME-NAME" value="some-value" />
                        <nvpair name="OTHER-NAME" value="other-value" />
                    </meta_attributes>
                </context>
            """,
        )

    def test_return_none_when_name_not_exists(self):
        self.assert_find_value(
            "instance_attributes",
            "SOME-NAME",
            value=None,
            xml="""
                <context>
                    <instance_attributes>
                        <nvpair name="another-name" value="some-value" />
                    </instance_attributes>
                </context>
            """,
        )

    def test_return_default_when_name_not_exists(self):
        self.assert_find_value(
            "instance_attributes",
            "SOME-NAME",
            value="DEFAULT",
            xml="""
                <context>
                    <instance_attributes>
                        <nvpair name="another-name" value="some-value" />
                    </instance_attributes>
                </context>
            """,
            default="DEFAULT",
        )

    def test_return_none_when_no_nvpair(self):
        self.assert_find_value(
            "instance_attributes",
            "SOME-NAME",
            value=None,
            xml="""
                <context>
                    <instance_attributes />
                </context>
            """,
        )

    def test_return_none_when_no_nvset(self):
        self.assert_find_value(
            "instance_attributes",
            "SOME-NAME",
            value=None,
            xml="""
                <context>
                </context>
            """,
        )


class GetNvsetAsDictTest(TestCase):
    def test_no_element(self):
        resource_element = etree.fromstring("<primitive/>")
        self.assertEqual(
            {},
            nvpair.get_nvset_as_dict("meta_attributes", resource_element),
        )

    def test_empty(self):
        resource_element = etree.fromstring(
            """
            <primitive>
                <meta_attributes/>
            </primitive>
        """
        )
        self.assertEqual(
            {},
            nvpair.get_nvset_as_dict("meta_attributes", resource_element),
        )

    def test_non_empty(self):
        resource_element = etree.fromstring(
            """
            <primitive>
                <meta_attributes>
                    <nvpair id="a" name="attr_name" value="value"/>
                    <nvpair id="b" name="other_name" value="other-value"/>
                </meta_attributes>
            </primitive>
        """
        )
        self.assertEqual(
            dict(
                attr_name="value",
                other_name="other-value",
            ),
            nvpair.get_nvset_as_dict("meta_attributes", resource_element),
        )

    def test_multiple_nvsets(self):
        resource_element = etree.fromstring(
            """
            <primitive>
                <meta_attributes>
                    <nvpair id="a" name="attr_name" value="value"/>
                    <nvpair id="b" name="other_name" value="other-value"/>
                </meta_attributes>
                <meta_attributes>
                    <nvpair id="a" name="attr_name2" value="value2"/>
                    <nvpair id="b" name="other_name2" value="other-value2"/>
                </meta_attributes>
            </primitive>
        """
        )
        self.assertEqual(
            dict(
                attr_name="value",
                other_name="other-value",
            ),
            nvpair.get_nvset_as_dict("meta_attributes", resource_element),
        )


class HasMetaAttribute(TestCase):
    def test_return_false_if_does_not_have_such_attribute(self):
        resource_element = etree.fromstring("""<primitive/>""")
        self.assertFalse(
            nvpair.has_meta_attribute(resource_element, "attr_name")
        )

    def test_return_true_if_such_meta_attribute_exists(self):
        resource_element = etree.fromstring(
            """
            <primitive>
                <meta_attributes>
                    <nvpair id="a" name="attr_name" value="value"/>
                    <nvpair id="b" name="other_name" value="other-value"/>
                </meta_attributes>
            </primitive>
        """
        )
        self.assertTrue(
            nvpair.has_meta_attribute(resource_element, "attr_name")
        )

    def test_return_false_if_meta_attribute_exists_but_in_nested_element(self):
        resource_element = etree.fromstring(
            """
            <group>
                <primitive>
                    <meta_attributes>
                        <nvpair id="a" name="attr_name" value="value"/>
                    </meta_attributes>
                </primitive>
            </group>
        """
        )
        self.assertFalse(
            nvpair.has_meta_attribute(resource_element, "attr_name")
        )
