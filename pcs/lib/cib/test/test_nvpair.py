from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

from lxml import etree

from pcs.lib.cib import nvpair
from pcs.test.tools.assertions import assert_xml_equal


class UpdateNvpairTest(TestCase):
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
        assert_xml_equal(
            "<nvpair id='nvset-attr' name='attr' value='10'/>",
            etree.tostring(
                nvpair.update_nvpair(self.nvset, self.nvset, "attr", "10")
            ).decode()
        )
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
        assert_xml_equal(
            "<nvpair id='nvset-test-1' name='test' value='0'/>",
            etree.tostring(
                nvpair.update_nvpair(self.nvset, self.nvset, "test", "0")
            ).decode()
        )
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
        assert_xml_equal(
            "<nvpair id='nvset-attr2' name='attr2' value='2'/>",
            etree.tostring(
                nvpair.update_nvpair(self.nvset, self.nvset, "attr2", "")
            ).decode()
        )
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
        self.assertTrue(
            nvpair.update_nvpair(self.nvset, self.nvset, "attr3", "") is None
        )
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


class UpdateNvsetTest(TestCase):
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

    def test_None(self):
        self.assertTrue(
            nvpair.update_nvset("nvset", self.root, self.root, None) is None
        )

    def test_empty(self):
        self.assertTrue(
            nvpair.update_nvset("nvset", self.root, self.root, {}) is None
        )

    def test_existing(self):
        self.assertEqual(
            self.nvset,
            nvpair.update_nvset("nvset", self.root, self.root, {
                "attr": "10",
                "new_one": "20",
                "test": "0",
                "attr2": ""
            })
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
            etree.tostring(self.nvset).decode()
        )

    def test_new(self):
        root = etree.Element("root", id="root")
        assert_xml_equal(
            """
            <nvset id="root-nvset">
                <nvpair id="root-nvset-attr" name="attr" value="10"/>
                <nvpair id="root-nvset-new_one" name="new_one" value="20"/>
                <nvpair id="root-nvset-test" name="test" value="0"/>
            </nvset>
            """,
            etree.tostring(nvpair.update_nvset("nvset", root, root, {
                "attr": "10",
                "new_one": "20",
                "test": "0",
                "attr2": ""
            })).decode()
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
