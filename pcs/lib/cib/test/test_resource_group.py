from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib.resource import group
from pcs.lib.errors import ReportItemSeverity as severities
from pcs.test.tools.assertions import assert_raise_library_error, assert_xml_equal
from pcs.test.tools.pcs_unittest import TestCase, mock


class FindGroupElement(TestCase):
    def test_returns_none_if_id_do_not_exists(self):
        self.assertIsNone(group.find_group_by_id(
            etree.fromstring("<resources/>"),
            "a"
        ))

    def test_returns_element_if_group_found(self):
        tree = etree.Element("resources")
        group_element = etree.SubElement(tree, "group", {"id": "a"})
        self.assertEqual(
            group_element,
            group.find_group_by_id(tree, "a")
        )

    def test_raises_when_id_belongs_to_unexpected_element(self):
        assert_raise_library_error(
            lambda: group.find_group_by_id(
                etree.fromstring('<resources><primitive id="a"/></resources>'),
                "a"
            ),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "a",
                    "expected_types": ["group"],
                    "current_type": "primitive",
                },
            ),
        )

class GetResource(TestCase):
    def test_returns_resource_when_is_in_group(self):
        group_element = etree.Element("group", {"id": "g"})
        resource_element = etree.SubElement(
            group_element,
            "primitive",
            {"id":"r"}
        )
        self.assertEqual(
            resource_element,
            group.get_resource(group_element, "r")
        )

    def test_raises_when_resource_not_in_group(self):
        assert_raise_library_error(
            lambda:
                group.get_resource(etree.fromstring('<group id="g"/>'), "r")
            ,
            (
                severities.ERROR,
                report_codes.RESOURCE_NOT_FOUND_IN_GROUP,
                {
                    "resource_id": "r",
                    "group_id": "g",
                },
            ),
        )

@mock.patch("pcs.lib.cib.resource.group.find_group_by_id")
class ProvideGroup(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            '<cib><resources><group id="g"/></resources></cib>'
        )
        self.group_element = self.cib.find('.//group')
        self.resources_section = self.cib.find('.//resources')


    def test_search_in_whole_tree(self, find_group_by_id):
        def find_group(whole_tree, id):
            self.assertEqual(self.cib, whole_tree.find('.'))
            return self.group_element

        find_group_by_id.side_effect = find_group

        self.assertEqual(
            self.group_element,
            group.provide_group(self.resources_section, "g")
        )

    def test_create_group_when_not_exists(self, find_group_by_id):
        find_group_by_id.return_value = None
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
                report_codes.RESOURCE_CANNOT_BE_NEXT_TO_ITSELF_IN_GROUP,
                {
                    "group_id": "g",
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
                report_codes.RESOURCE_NOT_FOUND_IN_GROUP,
                {
                    "resource_id": "r",
                    "group_id": "g",
                },
            ),
        )
