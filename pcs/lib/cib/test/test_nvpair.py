from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib import nvpair
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.pcs_unittest import TestCase, mock


class UpdateNvsetTest(TestCase):
    @mock.patch(
        "pcs.lib.cib.nvpair.create_subelement_id",
        mock.Mock(return_value="4")
    )
    def test_updates_nvset(self):
        nvset_element = etree.fromstring("""
            <instance_attributes id="iattrs">
                <nvpair id="1" name="a" value="b"/>
                <nvpair id="2" name="c" value="d"/>
                <nvpair id="3" name="e" value="f"/>
            </instance_attributes>
        """)
        nvpair.update_nvset(nvset_element, {
            "a": "B",
            "c": "",
            "g": "h",
        })
        assert_xml_equal(
            """
            <instance_attributes id="iattrs">
                <nvpair id="1" name="a" value="B"/>
                <nvpair id="3" name="e" value="f"/>
                <nvpair id="4" name="g" value="h"/>
            </instance_attributes>
            """,
            etree.tostring(nvset_element).decode()
        )
    def test_empty_value_has_no_effect(self):
        xml = """
            <instance_attributes id="iattrs">
                <nvpair id="1" name="a" value="b"/>
                <nvpair id="2" name="c" value="d"/>
                <nvpair id="3" name="e" value="f"/>
            </instance_attributes>
        """
        nvset_element = etree.fromstring(xml)
        nvpair.update_nvset(nvset_element, {})
        assert_xml_equal(xml, etree.tostring(nvset_element).decode())

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

    def test_update(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr", "10")
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="10"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )

    def test_add(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "test", "0")
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
                <nvpair id="nvset-test-1" name="test" value="0"/>
            </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )

    def test_remove(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr2", "")
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )

    def test_remove_not_existing(self):
        nvpair.set_nvpair_in_nvset(self.nvset, "attr3", "")
        assert_xml_equal(
            """
            <nvset id="nvset">
                <nvpair id="nvset-attr" name="attr" value="1"/>
                <nvpair id="nvset-attr2" name="attr2" value="2"/>
                <notnvpair id="nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )


class ArrangeSomeNvsetTest(TestCase):
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

    def test_empty_value_has_no_effect(self):
        nvpair.arrange_first_nvset("nvset", self.root, {})
        assert_xml_equal(
            """
                <nvset id="nvset">
                    <nvpair id="nvset-attr" name="attr" value="1"/>
                    <nvpair id="nvset-attr2" name="attr2" value="2"/>
                    <notnvpair id="nvset-test" name="test" value="0"/>
                </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )

    def test_update_existing_nvset(self):
        nvpair.arrange_first_nvset("nvset", self.root, {
            "attr": "10",
            "new_one": "20",
            "test": "0",
            "attr2": ""
        })
        assert_xml_equal(
            """
                <nvset id="nvset">
                    <nvpair id="nvset-attr" name="attr" value="10"/>
                    <notnvpair id="nvset-test" name="test" value="0"/>
                    <nvpair id="nvset-new_one" name="new_one" value="20"/>
                    <nvpair id="nvset-test-1" name="test" value="0"/>
                </nvset>
            """,
            etree.tostring(self.nvset).decode()
        )

    def test_create_new_nvset_if_does_not_exist(self):
        root = etree.Element("root", id="root")
        nvpair.arrange_first_nvset("nvset", root, {
            "attr": "10",
            "new_one": "20",
            "test": "0",
            "attr2": ""
        })

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
            etree.tostring(root).decode()
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
                {
                    "id": "nvset-name1",
                    "name": "name1",
                    "value": "value1"
                },
                {
                    "id": "nvset-name2",
                    "name": "name2",
                    "value": "value2"
                },
                {
                    "id": "nvset-name3",
                    "name": "name3",
                    "value": ""
                }
            ],
            nvpair.get_nvset(nvset)
        )
