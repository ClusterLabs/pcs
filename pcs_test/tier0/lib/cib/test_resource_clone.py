from unittest import TestCase
from lxml import etree

from pcs_test.tools.assertions import assert_xml_equal

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

    def assert_clone_effect(self, options, xml):
        clone.append_new(
            self.resources, IdProvider(self.resources), self.primitive, options
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


class IsAnyClone(TestCase):
    def test_is_clone(self):
        self.assertTrue(clone.is_clone(etree.fromstring("<clone/>")))
        self.assertFalse(clone.is_clone(etree.fromstring("<main/>")))
        self.assertFalse(clone.is_clone(etree.fromstring("<group/>")))

    def test_is_main(self):
        self.assertTrue(clone.is_main(etree.fromstring("<main/>")))
        self.assertFalse(clone.is_main(etree.fromstring("<clone/>")))
        self.assertFalse(clone.is_main(etree.fromstring("<group/>")))

    def test_is_any_clone(self):
        self.assertTrue(clone.is_any_clone(etree.fromstring("<clone/>")))
        self.assertTrue(clone.is_any_clone(etree.fromstring("<main/>")))
        self.assertFalse(clone.is_any_clone(etree.fromstring("<group/>")))


class IsPromotableClone(TestCase):
    def my_assert(self, result, xml):
        self.assertEqual(
            result, clone.is_promotable_clone(etree.fromstring(xml))
        )

    def test_main(self):
        self.my_assert(False, "<main />")

    def test_main_with_promotable(self):
        self.my_assert(
            False,
            """
                <main>
                    <meta_attributes>
                        <nvpair name="promotable" value="true" />
                    </meta_attributes>
                </main>
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
                <main id="C-main">
                    <primitive id="C" />
                </main>
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
                <main id="F-main">
                    <group id="F">
                        <primitive id="F1" />
                        <primitive id="F2" />
                    </group>
                </main>
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

    def test_main(self):
        self.my_assert("C-main", None)
        self.my_assert("F-main", None)

    def test_primitive_in_main(self):
        self.my_assert("C", "C-main")

    def test_grop(self):
        self.my_assert("D", None)

    def test_primitive_in_group(self):
        self.my_assert("D1", None)

    def test_group_in_clone(self):
        self.my_assert("E", "E-clone")

    def test_primitive_in_group_in_clone(self):
        self.my_assert("E1", "E-clone")

    def test_group_in_main(self):
        self.my_assert("F", "F-main")

    def test_primitive_in_group_in_main(self):
        self.my_assert("F1", "F-main")

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
