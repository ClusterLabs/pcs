from unittest import mock, TestCase
from lxml import etree

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)

from pcs.common import report_codes
from pcs.lib.cib.resource import group
from pcs.lib.errors import ReportItemSeverity as severities


class IsGroup(TestCase):
    def test_is_group(self):
        self.assertTrue(group.is_group(etree.fromstring("<group/>")))
        self.assertFalse(group.is_group(etree.fromstring("<clone/>")))
        self.assertFalse(group.is_group(etree.fromstring("<master/>")))


@mock.patch("pcs.lib.cib.resource.group.find_element_by_tag_and_id")
class ProvideGroup(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            '<cib><resources><group id="g"/></resources></cib>'
        )
        self.group_element = self.cib.find('.//group')
        self.resources_section = self.cib.find('.//resources')

    def test_search_in_whole_tree(self, find_element_by_tag_and_id):
        def find_group(*args, **kwargs):
            # pylint: disable=unused-argument
            return self.group_element

        find_element_by_tag_and_id.side_effect = find_group

        self.assertEqual(
            self.group_element,
            group.provide_group(self.resources_section, "g")
        )

    def test_create_group_when_not_exists(self, find_element_by_tag_and_id):
        find_element_by_tag_and_id.return_value = None
        group_element = group.provide_group(self.resources_section, "g2")
        self.assertEqual('group', group_element.tag)
        self.assertEqual('g2', group_element.attrib["id"])

class PlaceResource(TestCase):
    def setUp(self):
        self.group_element = etree.fromstring("""
            <group id="g">
                <primitive id="a"/>
                <primitive id="b"/>
            </group>
        """)
        self.primitive_element = etree.Element("primitive", {"id": "c"})

    def assert_final_order(
        self, id_list=None, adjacent_resource_id=None, put_after_adjacent=False
    ):
        group.place_resource(
            self.group_element,
            self.primitive_element,
            adjacent_resource_id,
            put_after_adjacent
        )
        assert_xml_equal(
            etree.tostring(self.group_element).decode(),
            """
                <group id="g">
                    <primitive id="{0}"/>
                    <primitive id="{1}"/>
                    <primitive id="{2}"/>
                </group>
            """.format(*id_list)
        )

    def test_append_at_the_end_when_adjacent_is_not_specified(self):
        self.assert_final_order(["a", "b", "c"])

    def test_insert_before_adjacent(self):
        self.assert_final_order(["c", "a", "b"], "a")

    def test_insert_after_adjacent(self):
        self.assert_final_order(["a", "c", "b"], "a", put_after_adjacent=True)

    def test_insert_after_adjacent_which_is_last(self):
        self.assert_final_order(["a", "b", "c"], "b", put_after_adjacent=True)

    def test_refuse_to_put_next_to_the_same_resource_id(self):
        assert_raise_library_error(
            lambda: group.place_resource(
                self.group_element,
                self.primitive_element,
                adjacent_resource_id="c",
            ),
            (
                severities.ERROR,
                report_codes.CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF,
                {
                    "resource_id": "c",
                },
            ),
        )

    def test_raises_when_adjacent_resource_not_in_group(self):
        assert_raise_library_error(
            lambda: group.place_resource(
                self.group_element,
                self.primitive_element,
                adjacent_resource_id="r",
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "r",
                    "expected_types": ["primitive"],
                    "context_type": "group",
                    "context_id": "g",
                },
                None
            ),
        )


class GetInnerResource(TestCase):
    def assert_inner_resource(self, resource_id, xml):
        self.assertEqual(
            resource_id,
            [
                element.attrib.get("id", "")
                for element in group.get_inner_resources(etree.fromstring(xml))
            ]
        )

    def test_one(self):
        self.assert_inner_resource(
            ["A"],
            """
                <group id="G">
                    <meta_attributes />
                    <primitive id="A" />
                    <meta_attributes />
                </group>
            """
        )

    def test_more(self):
        self.assert_inner_resource(
            ["A", "C", "B"],
            """
                <group id="G">
                    <meta_attributes />
                    <primitive id="A" />
                    <primitive id="C" />
                    <primitive id="B" />
                    <meta_attributes />
                </group>
            """
        )
