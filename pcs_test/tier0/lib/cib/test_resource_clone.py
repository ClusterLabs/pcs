from unittest import TestCase
from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)

from pcs.lib.cib.resource import clone
from pcs.lib.cib.tools import IdProvider


class AppendNewCommon(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
                <resources>
                    <primitive id="R"/>
                </resources>
            </cib>
        """
        )
        self.resources = self.cib.find(".//resources")
        self.primitive = self.cib.find(".//primitive")

    def assert_clone_effect(self, options, xml, clone_id=None):
        clone.append_new(
            self.resources,
            IdProvider(self.resources),
            self.primitive,
            options,
            clone_id=clone_id,
        )
        assert_xml_equal(etree.tostring(self.cib).decode(), xml)

    def test_add_without_options(self):
        self.assert_clone_effect(
            {},
            """
            <cib>
                <resources>
                    <clone id="R-clone">
                        <primitive id="R"/>
                    </clone>
                </resources>
            </cib>
        """,
        )

    def test_add_with_options(self):
        self.assert_clone_effect(
            {"a": "b"},
            """
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
        """,
        )

    def test_add_without_options_and_with_custom_id(self):
        self.assert_clone_effect(
            {},
            """
            <cib>
                <resources>
                    <clone id="MyCustomCloneId">
                        <primitive id="R"/>
                    </clone>
                </resources>
            </cib>
            """,
            clone_id="MyCustomCloneId",
        )

    def test_add_with_options_and_with_custom_id(self):
        self.assert_clone_effect(
            {"a": "b"},
            """
            <cib>
                <resources>
                    <clone id="MyCustomCloneId">
                        <primitive id="R"/>
                        <meta_attributes id="MyCustomCloneId-meta_attributes">
                            <nvpair id="MyCustomCloneId-meta_attributes-a"
                                name="a" value="b"
                            />
                        </meta_attributes>
                    </clone>
                </resources>
            </cib>
            """,
            clone_id="MyCustomCloneId",
        )


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


class IsPromotableClone(TestCase):
    def my_assert(self, result, xml):
        self.assertEqual(
            result, clone.is_promotable_clone(etree.fromstring(xml))
        )

    def test_master(self):
        self.my_assert(False, "<master />")

    def test_master_with_promotable(self):
        self.my_assert(
            False,
            """
                <master>
                    <meta_attributes>
                        <nvpair name="promotable" value="true" />
                    </meta_attributes>
                </master>
            """,
        )

    def test_clone(self):
        self.my_assert(False, "<clone />")

    def test_clone_with_promotable(self):
        self.my_assert(
            True,
            """
                <clone>
                    <meta_attributes>
                        <nvpair name="promotable" value="true" />
                    </meta_attributes>
                </clone>
            """,
        )

    def test_clone_with_promotable_false(self):
        self.my_assert(
            False,
            """
                <clone>
                    <meta_attributes>
                        <nvpair name="promotable" value="false" />
                    </meta_attributes>
                </clone>
            """,
        )

    def test_clone_with_promotable_in_resource(self):
        self.my_assert(
            False,
            """
                <clone>
                    <primitive>
                        <meta_attributes>
                            <nvpair name="promotable" value="true" />
                        </meta_attributes>
                    </primitive>
                </clone>
            """,
        )


class GetParentAnyClone(TestCase):
    cib = etree.fromstring(
        """
        <cib>
            <resources>
                <primitive id="A" />
                <clone id="B-clone">
                    <primitive id="B" />
                </clone>
                <master id="C-master">
                    <primitive id="C" />
                </master>
                <group id="D">
                    <primitive id="D1" />
                    <primitive id="D2" />
                </group>
                <clone id="E-clone">
                    <group id="E">
                        <primitive id="E1" />
                        <primitive id="E2" />
                    </group>
                </clone>
                <master id="F-master">
                    <group id="F">
                        <primitive id="F1" />
                        <primitive id="F2" />
                    </group>
                </master>
                <bundle id="G-bundle" />
                <bundle id="H-bundle">
                    <primitive id="H" />
                </bundle>
            </resources>
        </cib>
    """
    )

    def my_assert(self, id_in, id_out):
        element_in = self.cib.find(f'.//*[@id="{id_in}"]')
        actual_out = clone.get_parent_any_clone(element_in)
        if id_out is None:
            self.assertIsNone(actual_out)
            return
        if actual_out is None:
            self.assertIsNone(id_out)
            return
        self.assertEqual(id_out, actual_out.get("id"))

    def test_primitive(self):
        self.my_assert("A", None)

    def test_clone(self):
        self.my_assert("B-clone", None)
        self.my_assert("E-clone", None)

    def test_primitive_in_clone(self):
        self.my_assert("B", "B-clone")

    def test_master(self):
        self.my_assert("C-master", None)
        self.my_assert("F-master", None)

    def test_primitive_in_master(self):
        self.my_assert("C", "C-master")

    def test_grop(self):
        self.my_assert("D", None)

    def test_primitive_in_group(self):
        self.my_assert("D1", None)

    def test_group_in_clone(self):
        self.my_assert("E", "E-clone")

    def test_primitive_in_group_in_clone(self):
        self.my_assert("E1", "E-clone")

    def test_group_in_master(self):
        self.my_assert("F", "F-master")

    def test_primitive_in_group_in_master(self):
        self.my_assert("F1", "F-master")

    def test_bundle(self):
        self.my_assert("G-bundle", None)
        self.my_assert("H-bundle", None)

    def test_primitive_in_bundle(self):
        self.my_assert("H", None)


class GetInnerResource(TestCase):
    def assert_inner_resource(self, resource_id, xml):
        self.assertEqual(
            resource_id,
            clone.get_inner_resource(etree.fromstring(xml)).get("id", ""),
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
            """,
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
            """,
        )


class ValidateCloneId(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
                <resources>
                    <clone id="CloneId">
                        <meta_attributes id="CloneId-meta_attributes"/>
                    </clone>
                </resources>
            </cib>
            """
        )
        self.resources = self.cib.find(".//resources")
        self.id_provider = IdProvider(self.resources)

    def assert_validate_clone_id(self, clone_id, expected_report_item_list):
        assert_report_item_list_equal(
            clone.validate_clone_id(clone_id, self.id_provider),
            expected_report_item_list,
        )

    def test_valid_id(self):
        self.assert_validate_clone_id("UniqueCloneId", [])

    def test_invalid_id_character(self):
        self.assert_validate_clone_id(
            "0CloneId", [fixture.report_invalid_id("0CloneId", "0")],
        )

    def test_clone_id_exist(self):
        self.assert_validate_clone_id(
            "CloneId-meta_attributes",
            [fixture.report_id_already_exist("CloneId-meta_attributes")],
        )
