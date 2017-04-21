from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.resource import common
from pcs.test.tools.assertions import assert_xml_equal
from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.xml import etree_to_str


fixture_cib = etree.fromstring("""
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
""")


class AreMetaDisabled(TestCase):
    def test_detect_is_disabled(self):
        self.assertTrue(common.are_meta_disabled({"target-role": "Stopped"}))
        self.assertTrue(common.are_meta_disabled({"target-role": "stopped"}))

    def test_detect_is_not_disabled(self):
        self.assertFalse(common.are_meta_disabled({}))
        self.assertFalse(common.are_meta_disabled({"target-role": "any"}))


class IsCloneDeactivatedByMeta(TestCase):
    def assert_is_disabled(self, meta_attributes):
        self.assertTrue(common.is_clone_deactivated_by_meta(meta_attributes))

    def assert_is_not_disabled(self, meta_attributes):
        self.assertFalse(common.is_clone_deactivated_by_meta(meta_attributes))

    def test_detect_is_disabled(self):
        self.assert_is_disabled({"target-role": "Stopped"})
        self.assert_is_disabled({"target-role": "stopped"})
        self.assert_is_disabled({"clone-max": "0"})
        self.assert_is_disabled({"clone-max": "00"})
        self.assert_is_disabled({"clone-max": 0})
        self.assert_is_disabled({"clone-node-max": "0"})
        self.assert_is_disabled({"clone-node-max": "abc1"})

    def test_detect_is_not_disabled(self):
        self.assert_is_not_disabled({})
        self.assert_is_not_disabled({"target-role": "any"})
        self.assert_is_not_disabled({"clone-max": "1"})
        self.assert_is_not_disabled({"clone-max": "01"})
        self.assert_is_not_disabled({"clone-max": 1})
        self.assert_is_not_disabled({"clone-node-max": "1"})
        self.assert_is_not_disabled({"clone-node-max": 1})
        self.assert_is_not_disabled({"clone-node-max": "1abc"})
        self.assert_is_not_disabled({"clone-node-max": "1.1"})


class FindPrimitives(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in
                common.find_primitives(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ]
        )

    def test_primitive(self):
        self.assert_find_resources("A", ["A"])

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", ["B"])

    def test_primitive_in_master(self):
        self.assert_find_resources("C", ["C"])

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", ["D1"])
        self.assert_find_resources("D2", ["D2"])
        self.assert_find_resources("E1", ["E1"])
        self.assert_find_resources("E2", ["E2"])
        self.assert_find_resources("F1", ["F1"])
        self.assert_find_resources("F2", ["F2"])

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", ["H"])

    def test_group(self):
        self.assert_find_resources("D", ["D1", "D2"])

    def test_group_in_clone(self):
        self.assert_find_resources("E", ["E1", "E2"])

    def test_group_in_master(self):
        self.assert_find_resources("F", ["F1", "F2"])

    def test_cloned_primitive(self):
        self.assert_find_resources("B-clone", ["B"])

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E1", "E2"])

    def test_mastered_primitive(self):
        self.assert_find_resources("C-master", ["C"])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F1", "F2"])

    def test_bundle_empty(self):
        self.assert_find_resources("G-bundle", [])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", ["H"])


class FindResourcesToEnable(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in
                common.find_resources_to_enable(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ]
        )

    def test_primitive(self):
        self.assert_find_resources("A", ["A"])

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", ["B", "B-clone"])

    def test_primitive_in_master(self):
        self.assert_find_resources("C", ["C", "C-master"])

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", ["D1"])
        self.assert_find_resources("D2", ["D2"])
        self.assert_find_resources("E1", ["E1"])
        self.assert_find_resources("E2", ["E2"])
        self.assert_find_resources("F1", ["F1"])
        self.assert_find_resources("F2", ["F2"])

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", ["H"])

    def test_group(self):
        self.assert_find_resources("D", ["D"])

    def test_group_in_clone(self):
        self.assert_find_resources("E", ["E", "E-clone"])

    def test_group_in_master(self):
        self.assert_find_resources("F", ["F", "F-master"])

    def test_cloned_primitive(self):
        self.assert_find_resources("B-clone", ["B-clone", "B"])

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E-clone", "E"])

    def test_mastered_primitive(self):
        self.assert_find_resources("C-master", ["C-master", "C"])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F-master", "F"])

    def test_bundle_empty(self):
        self.assert_find_resources("G-bundle", [])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", [])


class Enable(TestCase):
    def assert_enabled(self, pre, post):
        resource = etree.fromstring(pre)
        common.enable(resource)
        assert_xml_equal(post, etree_to_str(resource))

    def test_disabled(self):
        self.assert_enabled(
            """
                <resource>
                    <meta_attributes>
                        <nvpair name="target-role" value="something" />
                    </meta_attributes>
                </resource>
            """,
            """
                <resource>
                </resource>
            """
        )

    def test_enabled(self):
        self.assert_enabled(
            """
                <resource>
                </resource>
            """,
            """
                <resource>
                </resource>
            """
        )

    def test_only_first_meta(self):
        # this captures the current behavior
        # once pcs supports more instance and meta attributes for each resource,
        # this test should be reconsidered
        self.assert_enabled(
            """
                <resource>
                    <meta_attributes id="meta1">
                        <nvpair name="target-role" value="something" />
                    </meta_attributes>
                    <meta_attributes id="meta2">
                        <nvpair name="target-role" value="something" />
                    </meta_attributes>
                </resource>
            """,
            """
                <resource>
                    <meta_attributes id="meta2">
                        <nvpair name="target-role" value="something" />
                    </meta_attributes>
                </resource>
            """
        )


class Disable(TestCase):
    def assert_disabled(self, pre, post):
        resource = etree.fromstring(pre)
        common.disable(resource)
        assert_xml_equal(post, etree_to_str(resource))

    def test_disabled(self):
        xml = """
            <resource id="R">
                <meta_attributes id="R-meta_attributes">
                    <nvpair id="R-meta_attributes-target-role"
                        name="target-role" value="Stopped" />
                </meta_attributes>
            </resource>
        """
        self.assert_disabled(xml, xml)

    def test_enabled(self):
        self.assert_disabled(
            """
                <resource id="R">
                </resource>
            """,
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                </resource>
            """
        )

    def test_only_first_meta(self):
        # this captures the current behavior
        # once pcs supports more instance and meta attributes for each resource,
        # this test should be reconsidered
        self.assert_disabled(
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                    </meta_attributes>
                    <meta_attributes id="R-meta_attributes-2">
                    </meta_attributes>
                </resource>
            """,
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-target-role"
                            name="target-role" value="Stopped" />
                    </meta_attributes>
                    <meta_attributes id="R-meta_attributes-2">
                    </meta_attributes>
                </resource>
            """
        )


class FindResourcesToManage(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in
                common.find_resources_to_manage(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ]
        )

    def test_primitive(self):
        self.assert_find_resources("A", ["A"])

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", ["B", "B-clone"])

    def test_primitive_in_master(self):
        self.assert_find_resources("C", ["C", "C-master"])

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", ["D1", "D"])
        self.assert_find_resources("D2", ["D2", "D"])
        self.assert_find_resources("E1", ["E1", "E-clone", "E"])
        self.assert_find_resources("E2", ["E2", "E-clone", "E"])
        self.assert_find_resources("F1", ["F1", "F-master", "F"])
        self.assert_find_resources("F2", ["F2", "F-master", "F"])

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", ["H"])

    def test_group(self):
        self.assert_find_resources("D", ["D", "D1", "D2"])

    def test_group_in_clone(self):
        self.assert_find_resources("E", ["E", "E-clone", "E1", "E2"])

    def test_group_in_master(self):
        self.assert_find_resources("F", ["F", "F-master", "F1", "F2"])

    def test_cloned_primitive(self):
        self.assert_find_resources("B-clone", ["B-clone", "B"])

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E-clone", "E", "E1", "E2"])

    def test_mastered_primitive(self):
        self.assert_find_resources("C-master", ["C-master", "C"])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F-master", "F", "F1", "F2"])

    def test_bundle_empty(self):
        self.assert_find_resources("G-bundle", [])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", [])


class FindResourcesToUnmanage(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in
                common.find_resources_to_unmanage(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ]
        )

    def test_primitive(self):
        self.assert_find_resources("A", ["A"])

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", ["B"])

    def test_primitive_in_master(self):
        self.assert_find_resources("C", ["C"])

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", ["D1"])
        self.assert_find_resources("D2", ["D2"])
        self.assert_find_resources("E1", ["E1"])
        self.assert_find_resources("E2", ["E2"])
        self.assert_find_resources("F1", ["F1"])
        self.assert_find_resources("F2", ["F2"])

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", ["H"])

    def test_group(self):
        self.assert_find_resources("D", ["D1", "D2"])

    def test_group_in_clone(self):
        self.assert_find_resources("E", ["E1", "E2"])

    def test_group_in_master(self):
        self.assert_find_resources("F", ["F1", "F2"])

    def test_cloned_primitive(self):
        self.assert_find_resources("B-clone", ["B"])

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E1", "E2"])

    def test_mastered_primitive(self):
        self.assert_find_resources("C-master", ["C"])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F1", "F2"])

    def test_bundle_empty(self):
        self.assert_find_resources("G-bundle", [])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", [])


class Manage(TestCase):
    def assert_managed(self, pre, post):
        resource = etree.fromstring(pre)
        common.manage(resource)
        assert_xml_equal(post, etree_to_str(resource))

    def test_unmanaged(self):
        self.assert_managed(
            """
                <resource>
                    <meta_attributes>
                        <nvpair name="is-managed" value="something" />
                    </meta_attributes>
                </resource>
            """,
            """
                <resource>
                </resource>
            """
        )

    def test_managed(self):
        self.assert_managed(
            """
                <resource>
                </resource>
            """,
            """
                <resource>
                </resource>
            """
        )

    def test_only_first_meta(self):
        # this captures the current behavior
        # once pcs supports more instance and meta attributes for each resource,
        # this test should be reconsidered
        self.assert_managed(
            """
                <resource>
                    <meta_attributes id="meta1">
                        <nvpair name="is-managed" value="something" />
                    </meta_attributes>
                    <meta_attributes id="meta2">
                        <nvpair name="is-managed" value="something" />
                    </meta_attributes>
                </resource>
            """,
            """
                <resource>
                    <meta_attributes id="meta2">
                        <nvpair name="is-managed" value="something" />
                    </meta_attributes>
                </resource>
            """
        )


class Unmanage(TestCase):
    def assert_unmanaged(self, pre, post):
        resource = etree.fromstring(pre)
        common.unmanage(resource)
        assert_xml_equal(post, etree_to_str(resource))

    def test_unmanaged(self):
        xml = """
            <resource id="R">
                <meta_attributes id="R-meta_attributes">
                    <nvpair id="R-meta_attributes-is-managed"
                        name="is-managed" value="false" />
                </meta_attributes>
            </resource>
        """
        self.assert_unmanaged(xml, xml)

    def test_managed(self):
        self.assert_unmanaged(
            """
                <resource id="R">
                </resource>
            """,
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                </resource>
            """
        )

    def test_only_first_meta(self):
        # this captures the current behavior
        # once pcs supports more instance and meta attributes for each resource,
        # this test should be reconsidered
        self.assert_unmanaged(
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                    </meta_attributes>
                    <meta_attributes id="R-meta_attributes-2">
                    </meta_attributes>
                </resource>
            """,
            """
                <resource id="R">
                    <meta_attributes id="R-meta_attributes">
                        <nvpair id="R-meta_attributes-is-managed"
                            name="is-managed" value="false" />
                    </meta_attributes>
                    <meta_attributes id="R-meta_attributes-2">
                    </meta_attributes>
                </resource>
            """
        )

class HasMetaAttribute(TestCase):
    def test_return_false_if_does_not_have_such_attribute(self):
        resource_element = etree.fromstring("""<primitive/>""")
        self.assertFalse(
            common.has_meta_attribute(resource_element, "attr_name")
        )

    def test_return_true_if_such_meta_attribute_exists(self):
        resource_element = etree.fromstring("""
            <primitive>
                <meta_attributes>
                    <nvpair id="a" name="attr_name" value="value"/>
                </meta_attributes>
            </primitive>
        """)
        self.assertTrue(
            common.has_meta_attribute(resource_element, "attr_name")
        )

    def test_return_false_if_meta_attribute_exists_but_in_nested_element(self):
        resource_element = etree.fromstring("""
            <group>
                <primitive>
                    <meta_attributes>
                        <nvpair id="a" name="attr_name" value="value"/>
                    </meta_attributes>
                </primitive>
            </group>
        """)
        self.assertFalse(
            common.has_meta_attribute(resource_element, "attr_name")
        )
