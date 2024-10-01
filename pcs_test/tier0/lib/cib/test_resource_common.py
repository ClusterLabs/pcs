from unittest import TestCase

from lxml import etree

from pcs.lib.cib.resource import common
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str

fixture_cib = etree.fromstring(
    """
    <cib>
        <configuration>
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
                <group id="I">
                    <primitive id="I1" />
                </group>
                <clone id="J-clone">
                    <group id="J">
                        <primitive id="J1" />
                    </group>
                </clone>
                <master id="K-master">
                    <group id="K">
                        <primitive id="K1" />
                    </group>
                </master>
            </resources>
        </configuration>
    </cib>
    """
)


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


class FindOneOrMoreResources(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <resources>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
                <primitive id="R1x" />
                <primitive id="R2x" />
            </resources>
        """
        )

        def searcher(resource_element):
            return [
                resource_element.getparent().find(
                    ".//*[@id='{0}x']".format(resource_element.get("id"))
                )
            ]

        self.additional_search = searcher

    def test_one_existing(self):
        resource, report_list = common.find_one_resource(self.cib, "R1")
        self.assertEqual("R1", resource.attrib.get("id"))
        assert_report_item_list_equal(report_list, [])

    def test_one_nonexistent(self):
        resource, report_list = common.find_one_resource(self.cib, "R-missing")
        self.assertIsNone(resource)
        assert_report_item_list_equal(
            report_list,
            [
                fixture.report_not_found("R-missing", context_type="resources"),
            ],
        )

    def test_more_existing(self):
        resource_list, report_list = common.find_resources(
            self.cib, ["R1", "R2"]
        )
        self.assertEqual(
            ["R1", "R2"],
            [resource.attrib.get("id") for resource in resource_list],
        )
        assert_report_item_list_equal(report_list, [])

    def test_more_some_missing(self):
        resource_list, report_list = common.find_resources(
            self.cib, ["R1", "R2", "RY1", "RY2"]
        )
        self.assertEqual(
            ["R1", "R2"],
            [resource.attrib.get("id") for resource in resource_list],
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.report_not_found("RY1", context_type="resources"),
                fixture.report_not_found("RY2", context_type="resources"),
            ],
        )


class FindResourcesMixin:
    _iterable_type = list

    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            self._iterable_type(output_resource_ids),
            self._iterable_type(
                [
                    element.get("id", "")
                    for element in self._tested_fn(
                        fixture_cib.find(
                            './/*[@id="{0}"]'.format(input_resource_id)
                        )
                    )
                ]
            ),
        )

    def test_group(self):
        self.assert_find_resources("D", ["D1", "D2"])

    def test_group_in_clone(self):
        self.assert_find_resources("E", ["E1", "E2"])

    def test_group_in_master(self):
        self.assert_find_resources("F", ["F1", "F2"])

    def test_cloned_primitive(self):
        self.assert_find_resources("B-clone", ["B"])

    def test_mastered_primitive(self):
        self.assert_find_resources("C-master", ["C"])

    def test_bundle_empty(self):
        self.assert_find_resources("G-bundle", [])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", ["H"])

    def test_primitive(self):
        raise NotImplementedError()

    def test_primitive_in_clone(self):
        raise NotImplementedError()

    def test_primitive_in_master(self):
        raise NotImplementedError()

    def test_primitive_in_group(self):
        raise NotImplementedError()

    def test_primitive_in_bundle(self):
        raise NotImplementedError()

    def test_cloned_group(self):
        raise NotImplementedError()

    def test_mastered_group(self):
        raise NotImplementedError()


class FindPrimitives(TestCase, FindResourcesMixin):
    _tested_fn = staticmethod(common.find_primitives)

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

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E1", "E2"])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F1", "F2"])


class GetAllInnerResources(TestCase, FindResourcesMixin):
    _iterable_type = set
    _tested_fn = staticmethod(common.get_all_inner_resources)

    def test_primitive(self):
        self.assert_find_resources("A", set())

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", set())

    def test_primitive_in_master(self):
        self.assert_find_resources("C", set())

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", set())
        self.assert_find_resources("D2", set())
        self.assert_find_resources("E1", set())
        self.assert_find_resources("E2", set())
        self.assert_find_resources("F1", set())
        self.assert_find_resources("F2", set())

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", set())

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", {"E", "E1", "E2"})

    def test_mastered_group(self):
        self.assert_find_resources("F-master", {"F", "F1", "F2"})


class GetInnerResources(TestCase, FindResourcesMixin):
    _tested_fn = staticmethod(common.get_inner_resources)

    def test_primitive(self):
        self.assert_find_resources("A", [])

    def test_primitive_in_clone(self):
        self.assert_find_resources("B", [])

    def test_primitive_in_master(self):
        self.assert_find_resources("C", [])

    def test_primitive_in_group(self):
        self.assert_find_resources("D1", [])
        self.assert_find_resources("D2", [])
        self.assert_find_resources("E1", [])
        self.assert_find_resources("E2", [])
        self.assert_find_resources("F1", [])
        self.assert_find_resources("F2", [])

    def test_primitive_in_bundle(self):
        self.assert_find_resources("H", [])

    def test_mastered_group(self):
        self.assert_find_resources("F-master", ["F"])

    def test_cloned_group(self):
        self.assert_find_resources("E-clone", ["E"])


class IsWrapperResource(TestCase):
    def assert_is_wrapper(self, res_id, is_wrapper):
        self.assertEqual(
            is_wrapper,
            common.is_wrapper_resource(
                fixture_cib.find('.//*[@id="{0}"]'.format(res_id))
            ),
        )

    def test_primitive(self):
        self.assert_is_wrapper("A", False)

    def test_primitive_in_clone(self):
        self.assert_is_wrapper("B", False)

    def test_primitive_in_master(self):
        self.assert_is_wrapper("C", False)

    def test_primitive_in_group(self):
        self.assert_is_wrapper("D1", False)
        self.assert_is_wrapper("D2", False)
        self.assert_is_wrapper("E1", False)
        self.assert_is_wrapper("E2", False)
        self.assert_is_wrapper("F1", False)
        self.assert_is_wrapper("F2", False)

    def test_primitive_in_bundle(self):
        self.assert_is_wrapper("H", False)

    def test_cloned_group(self):
        self.assert_is_wrapper("E-clone", True)

    def test_mastered_group(self):
        self.assert_is_wrapper("F-master", True)

    def test_group(self):
        self.assert_is_wrapper("D", True)

    def test_group_in_clone(self):
        self.assert_is_wrapper("E", True)

    def test_group_in_master(self):
        self.assert_is_wrapper("F", True)

    def test_cloned_primitive(self):
        self.assert_is_wrapper("B-clone", True)

    def test_mastered_primitive(self):
        self.assert_is_wrapper("C-master", True)

    def test_bundle_empty(self):
        self.assert_is_wrapper("G-bundle", True)

    def test_bundle_with_primitive(self):
        self.assert_is_wrapper("H-bundle", True)


class GetParentResource(TestCase):
    def assert_parent_resource(self, input_resource_id, output_resource_id):
        res_el = common.get_parent_resource(
            fixture_cib.find('.//*[@id="{0}"]'.format(input_resource_id))
        )
        self.assertEqual(
            output_resource_id, res_el.get("id") if res_el is not None else None
        )

    def test_primitive(self):
        self.assert_parent_resource("A", None)

    def test_primitive_in_clone(self):
        self.assert_parent_resource("B", "B-clone")

    def test_primitive_in_master(self):
        self.assert_parent_resource("C", "C-master")

    def test_primitive_in_group(self):
        self.assert_parent_resource("D1", "D")
        self.assert_parent_resource("D2", "D")
        self.assert_parent_resource("E1", "E")
        self.assert_parent_resource("E2", "E")
        self.assert_parent_resource("F1", "F")
        self.assert_parent_resource("F2", "F")

    def test_primitive_in_bundle(self):
        self.assert_parent_resource("H", "H-bundle")

    def test_cloned_group(self):
        self.assert_parent_resource("E-clone", None)

    def test_mastered_group(self):
        self.assert_parent_resource("F-master", None)

    def test_group(self):
        self.assert_parent_resource("D", None)

    def test_group_in_clone(self):
        self.assert_parent_resource("E", "E-clone")

    def test_group_in_master(self):
        self.assert_parent_resource("F", "F-master")

    def test_cloned_primitive(self):
        self.assert_parent_resource("B-clone", None)

    def test_mastered_primitive(self):
        self.assert_parent_resource("C-master", None)

    def test_bundle_empty(self):
        self.assert_parent_resource("G-bundle", None)

    def test_bundle_with_primitive(self):
        self.assert_parent_resource("H-bundle", None)


class FindResourcesToEnable(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in common.find_resources_to_enable(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ],
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
        self.assert_find_resources("H", ["H", "H-bundle"])

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
        self.assert_find_resources("G-bundle", ["G-bundle"])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", ["H-bundle", "H"])


class Enable(TestCase):
    @staticmethod
    def assert_enabled(pre, post):
        resource = etree.fromstring(pre)
        common.enable(resource, IdProvider(resource))
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
                    <meta_attributes />
                </resource>
            """,
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
            """,
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
                    <meta_attributes id="meta1" />
                    <meta_attributes id="meta2">
                        <nvpair name="target-role" value="something" />
                    </meta_attributes>
                </resource>
            """,
        )


class Disable(TestCase):
    @staticmethod
    def assert_disabled(pre, post):
        resource = etree.fromstring(pre)
        common.disable(resource, IdProvider(resource))
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
            """,
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
            """,
        )


class FindResourcesToManage(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in common.find_resources_to_manage(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ],
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
        self.assert_find_resources("H", ["H", "H-bundle"])

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
        self.assert_find_resources("G-bundle", ["G-bundle"])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", ["H-bundle", "H"])


class FindResourcesToUnmanage(TestCase):
    def assert_find_resources(self, input_resource_id, output_resource_ids):
        self.assertEqual(
            output_resource_ids,
            [
                element.get("id", "")
                for element in common.find_resources_to_unmanage(
                    fixture_cib.find(
                        './/*[@id="{0}"]'.format(input_resource_id)
                    )
                )
            ],
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
        self.assert_find_resources("G-bundle", ["G-bundle"])

    def test_bundle_with_primitive(self):
        self.assert_find_resources("H-bundle", ["H-bundle", "H"])


class Manage(TestCase):
    @staticmethod
    def assert_managed(pre, post):
        resource = etree.fromstring(pre)
        common.manage(resource, IdProvider(resource))
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
                    <meta_attributes />
                </resource>
            """,
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
            """,
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
                    <meta_attributes id="meta1" />
                    <meta_attributes id="meta2">
                        <nvpair name="is-managed" value="something" />
                    </meta_attributes>
                </resource>
            """,
        )


class Unmanage(TestCase):
    @staticmethod
    def assert_unmanaged(pre, post):
        resource = etree.fromstring(pre)
        common.unmanage(resource, IdProvider(resource))
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
            """,
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
            """,
        )
