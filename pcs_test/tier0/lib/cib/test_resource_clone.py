from unittest import (
    TestCase,
)

from lxml import etree

from pcs.common.tools import Version
from pcs.lib.cib.resource import clone
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str


def fixture_resource_meta_stateful(
    meta_nvpairs="",
    use_legacy_roles=False,
    is_grouped=False,
):
    clone_el_tag = "clone"
    role_promoted = "Promoted"
    role_unpromoted = "Unpromoted"
    meta_attributes_xml = ""

    if use_legacy_roles:
        clone_el_tag = "master"
        role_promoted = "Master"
        role_unpromoted = "Slave"
        if meta_nvpairs:
            meta_attributes_xml = f"""
                <meta_attributes id="custom-clone-meta_attributes">
                    {meta_nvpairs}
                </meta_attributes>
            """
    else:
        meta_attributes_xml = f"""
            <meta_attributes id="custom-clone-meta_attributes">
                {meta_nvpairs}
                <nvpair id="custom-clone-meta_attributes-promotable"
                    name="promotable" value="true"
                />
            </meta_attributes>
        """

    group_start = group_end = ""
    if is_grouped:
        group_start = """<group id="G">"""
        group_end = "</group>"

    return f"""
        <{clone_el_tag} id="custom-clone">
            {group_start}
                <primitive id="A" class="ocf" type="Stateful"
                    provider="pacemaker"
                >
                    <operations>
                        <op name="demote" interval="0s" timeout="10s"
                            id="A-demote-interval-0s"
                        />
                        <op name="monitor" interval="10s" timeout="20s"
                            role="{role_promoted}" id="A-monitor-interval-10s"
                        />
                        <op name="monitor" interval="11s" timeout="20s"
                            role="{role_unpromoted}" id="A-monitor-interval-11s"
                        />
                        <op name="notify" interval="0s" timeout="5s"
                            id="A-notify-interval-0s"
                        />
                        <op name="promote" interval="0s" timeout="10s"
                            id="A-promote-interval-0s"
                        />
                        <op name="reload-agent" interval="0s" timeout="10s"
                            id="A-reload-agent-interval-0s"
                        />
                        <op name="start" interval="0s" timeout="20s"
                            id="A-start-interval-0s"
                        />
                        <op name="stop" interval="0s" timeout="20s"
                            id="A-stop-interval-0s"
                        />
                    </operations>
                </primitive>
            {group_end}
            {meta_attributes_xml}
        </{clone_el_tag}>
    """


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

    def test_group(self):
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


class GetInnerPrimitiveResources(TestCase):
    def assert_inner_resource(self, resource_id_list, xml):
        self.assertListEqual(
            resource_id_list,
            [
                inner_el.get("id", "")
                for inner_el in clone.get_inner_primitives(
                    etree.fromstring(xml)
                )
            ],
        )

    def test_primitive(self):
        self.assert_inner_resource(
            ["A"],
            """
                <clone id="A-clone">
                    <meta_attributes />
                    <primitive id="A" />
                    <meta_attributes />
                </clone>
            """,
        )

    def test_group_single(self):
        self.assert_inner_resource(
            ["A"],
            """
                <clone id="custom-clone">
                    <meta_attributes />
                    <group>
                        <primitive id="A" />
                    </group>
                    <meta_attributes />
                </clone>
            """,
        )

    def test_group_multiple(self):
        self.assert_inner_resource(
            ["A", "B", "C"],
            """
                <clone id="custom-clone">
                    <meta_attributes />
                    <group>
                        <primitive id="A" />
                        <primitive id="B" />
                        <primitive id="C" />
                    </group>
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
            "0CloneId",
            [fixture.report_invalid_id("0CloneId", "0")],
        )

    def test_clone_id_exist(self):
        self.assert_validate_clone_id(
            "CloneId-meta_attributes",
            [fixture.report_id_already_exist("CloneId-meta_attributes")],
        )


class ConvertLegacyPromotableElement(TestCase):
    _EXISTING_NVPAIR = (
        '<nvpair id="custom-clone-priority" name="priority" value="2" />'
    )

    def test_update_primitive(self):
        legacy_el_str = fixture_resource_meta_stateful(
            use_legacy_roles=True,
        )
        legacy_el = etree.fromstring(legacy_el_str)
        clone.convert_master_to_promotable(
            IdProvider(legacy_el), Version(3, 7), legacy_el
        )
        assert_xml_equal(
            etree_to_str(legacy_el),
            fixture_resource_meta_stateful(),
        )

    def test_update_primitive_with_existing_meta(self):
        legacy_el_str = fixture_resource_meta_stateful(
            meta_nvpairs=self._EXISTING_NVPAIR,
            use_legacy_roles=True,
        )
        legacy_el = etree.fromstring(legacy_el_str)
        clone.convert_master_to_promotable(
            IdProvider(legacy_el), Version(3, 7), legacy_el
        )
        assert_xml_equal(
            etree_to_str(legacy_el),
            fixture_resource_meta_stateful(meta_nvpairs=self._EXISTING_NVPAIR),
        )

    def test_update_group(self):
        legacy_el_str = fixture_resource_meta_stateful(
            use_legacy_roles=True,
            is_grouped=True,
        )
        legacy_el = etree.fromstring(legacy_el_str)
        clone.convert_master_to_promotable(
            IdProvider(legacy_el), Version(3, 7), legacy_el
        )
        assert_xml_equal(
            etree_to_str(legacy_el),
            fixture_resource_meta_stateful(is_grouped=True),
        )

    def test_update_group_with_existing_meta(self):
        legacy_el_str = fixture_resource_meta_stateful(
            meta_nvpairs=self._EXISTING_NVPAIR,
            use_legacy_roles=True,
            is_grouped=True,
        )
        legacy_el = etree.fromstring(legacy_el_str)
        clone.convert_master_to_promotable(
            IdProvider(legacy_el), Version(3, 7), legacy_el
        )
        assert_xml_equal(
            etree_to_str(legacy_el),
            fixture_resource_meta_stateful(
                meta_nvpairs=self._EXISTING_NVPAIR,
                is_grouped=True,
            ),
        )
