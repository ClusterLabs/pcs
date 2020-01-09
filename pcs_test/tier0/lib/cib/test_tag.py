from collections import namedtuple
from unittest import TestCase

from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)

from pcs.common import report_codes
from pcs.lib.xml_tools import (
    etree_to_str,
)
from pcs.lib.cib import tag as lib
from pcs.lib.cib.tools import (
    get_constraints,
    get_resources,
    get_tags,
    IdProvider,
)

# pylint: disable=protected-access

TagWithRefs = namedtuple("TagWithRefs", ["tag_id", "idref_list"])

FIXTURE_ONE_TAG = ("""
    <cib>
        <configuration>
            <tags>
                <tag id="first_tag">
                    <obj_ref id="idref1"/>
                    <obj_ref id="idref2"/>
                </tag>
            </tags>
        </configuration>
    </cib>
""")

FIXTURE_TWO_TAGS = ("""
    <cib>
        <configuration>
            <tags>
                <tag id="first_tag">
                    <obj_ref id="idref1"/>
                    <obj_ref id="idref2"/>
                </tag>
                <tag id="second_tag">
                    <obj_ref id="ref1"/>
                    <obj_ref id="ref2"/>
                    <obj_ref id="ref3"/>
                </tag>
            </tags>
        </configuration>
    </cib>
""")

def fixture_unexpected_element_reports(id_list, expected_types=None):
    return [
        fixture.report_unexpected_element(
            _id,
            ValidateCommonTestData.id_to_context_type_map[_id],
            expected_types=[
                'clone',
                'master',
                'group',
                'primitive',
                'bundle',
            ] if expected_types is None else expected_types
        )
        for _id in id_list
    ]


def fixture_id_not_found_reports(id_list, expected_types=None):
    return [
        fixture.report_not_found(
            _id,
            context_type=ValidateCommonTestData.id_to_context_type_map[_id],
            expected_types=expected_types,
        )
        for _id in id_list
    ]


class LibraryTagTest(TestCase):
    tag_sets = [
        TagWithRefs("first_tag", ["idref1", "idref2"]),
        TagWithRefs("second_tag", ["ref1", "ref2", "ref3"]),
    ]

    def setUp(self):
        self.cib = etree.fromstring('<cib><configuration/></cib>')

    def call_create_tag(self, tag_with_refs):
        lib.create_tag(
            get_tags(self.cib),
            tag_with_refs.tag_id,
            tag_with_refs.idref_list,
        )

    def assert_cib_equal(self, expected_cib):
        assert_xml_equal(expected_cib, etree_to_str(self.cib))

    def test_create_tag_if_no_tags(self):
        self.call_create_tag(self.tag_sets[0])
        self.assert_cib_equal(FIXTURE_ONE_TAG)

    def test_create_tag_if_tags_exists(self):
        self.cib = etree.fromstring(FIXTURE_ONE_TAG)
        self.call_create_tag(self.tag_sets[1])
        self.assert_cib_equal(FIXTURE_TWO_TAGS)


class ValidateCommonTestData(TestCase):
    resource_ids = ["id-01", "id-02", "id-03"]
    nonresource_ids = ["no1", "no2"]
    nonexistent_ids = ["nonexisten1", "nonexisten2"]
    nonexistent_tags = ["nonexistent_tag1", "nonexistent_tag2"]
    existent_tags = ["first_tag", "second_tag"]
    id_to_context_type_map = {
        "no1": "rsc_location",
        "no2": "node_state",
        "nonexisten1": "resources",
        "nonexisten2": "resources",
        "#invalid-tag-id": "resources",
        "nonexistent_tag1": "tags",
        "nonexistent_tag2": "tags",
    }
    test_tree = etree.fromstring(
        """
        <cib>
          <configuration>
            <resources>
              <primitive id="{resource_ids[0]}"/>
              <group id="G">
                <primitive id="{resource_ids[1]}"/>
              </group>
              <clone id="C">
                <primitive id="{resource_ids[2]}"/>
              </clone>
            </resources>
            <constraints>
              <rsc_location id="{nonresource_ids[0]}"/>
            </constraints>
            <tags>
              <tag id="{tags[0]}">
                <obj_ref id="idref1"/>
                <obj_ref id="idref2"/>
              </tag>
              <tag id="{tags[1]}">
                <obj_ref id="ref1"/>
                <obj_ref id="ref2"/>
                <obj_ref id="ref3"/>
              </tag>
            </tags>
          </configuration>
          <status>
            <node_state id="{nonresource_ids[1]}"/>
          </status>
        </cib>
        """.format(
            resource_ids=resource_ids,
            tags=existent_tags,
            nonresource_ids=nonresource_ids,
        )
    )
    tags_section = get_tags(test_tree)
    resources_section = get_resources(test_tree)
    id_provider = IdProvider(tags_section)

    def get_tag_elements(self, id_list):
        return [
            element
            for element in self.tags_section.findall("tag")
            if element.get("id", default="") in id_list
        ]


class AllTagElementsToDict(ValidateCommonTestData):
    def test_success(self):
        element_list = lib.get_list_of_tag_elements(get_tags(self.test_tree))
        self.assertEqual(
            [
                lib.tag_element_to_dict(element)
                for element in element_list
            ],
            [
                {
                    "tag_id": "first_tag",
                    "idref_list": ["idref1", "idref2"],
                },
                {
                    "tag_id": "second_tag",
                    "idref_list": ["ref1", "ref2", "ref3"],
                },
            ],
        )


class ValidateCreateTag(ValidateCommonTestData):
    def test_validation_success(self):
        assert_report_item_list_equal(
            lib.validate_create_tag(
                get_resources(self.test_tree),
                "new-tag",
                self.resource_ids,
                self.id_provider,
            ),
            [],
        )

    def test_validation_failure_all_kinds_reports(self):
        tag_id = "#invalid-tag-id"
        idref_list = 2 * self.nonresource_ids
        idref_list.append(tag_id)
        assert_report_item_list_equal(
            lib.validate_create_tag(
                get_resources(self.test_tree),
                tag_id,
                idref_list,
                self.id_provider,
            ),
            [
                fixture.report_invalid_id(tag_id, '#'),
                fixture.error(report_codes.TAG_CANNOT_CONTAIN_ITSELF),
                *fixture_unexpected_element_reports(2 * self.nonresource_ids),
                *fixture_id_not_found_reports([tag_id]),
                fixture.error(
                    report_codes.TAG_IDS_DUPLICATION,
                    duplicate_ids_list=self.nonresource_ids,
                ),
            ],
        )

class ValidateTagIdTest(ValidateCommonTestData):
    def test_tag_id_is_valid(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("new-tag-id", self.id_provider),
            [],
        )

    def test_tag_id_is_empty(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("", self.id_provider),
            [fixture.error(report_codes.EMPTY_ID, id="")],
        )

    def test_tag_id_invalid_first_character(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("0tagid", self.id_provider),
            [fixture.report_invalid_id("0tagid", '0')],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("-tagid", self.id_provider),
            [fixture.report_invalid_id("-tagid", '-')],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("átagid", self.id_provider),
            [fixture.report_invalid_id("átagid", 'á')],
        )

    def test_tag_id_invalid_character(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("tag,id", self.id_provider),
            [fixture.report_invalid_id("tag,id", ',')],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("tagid>", self.id_provider),
            [fixture.report_invalid_id("tagid>", '>')],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("taígid", self.id_provider),
            [fixture.report_invalid_id("taígid", 'í')],
        )

    def test_tag_id_already_exists(self):
        for tag_id in ["id-01", "id-02"]:
            assert_report_item_list_equal(
                lib._validate_tag_id(tag_id, self.id_provider),
                [
                    fixture.error(report_codes.ID_ALREADY_EXISTS, id=tag_id)
                ],
            )


class ValidateTagIdNotInIdrefList(TestCase):
    def setUp(self):
        self.idref_list = ["id1", "id2", "id3"]

    def test_tag_contains_itself(self):
        assert_report_item_list_equal(
            lib._validate_tag_id_not_in_idref_list(
                self.idref_list[0],
                self.idref_list,
            ),
            [fixture.error(report_codes.TAG_CANNOT_CONTAIN_ITSELF)],
        )

    def test_tag_does_not_contain_itself(self):
        assert_report_item_list_equal(
            lib._validate_tag_id_not_in_idref_list(
                "tag-not-in-list",
                self.idref_list,
            ),
            [],
        )


class ValidateDuplicateReferenceIds(ValidateCommonTestData):
    duplicated_ids_input_output = (
        (
            ["id1", "id1"],
            ["id1"],
        ),
        (
            ["id1", "id2", "id2"],
            ["id2"],
        ),
        (
            ["id1", "id2", "id3", "id1", "id4", "id4"],
            ["id1", "id4"],
        ),
    )

    def test_no_duplicates(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib._validate_duplicate_reference_ids(["id1", "id2"]),
            [],
        )

    def test_duplicates(self):
        # pylint: disable=no-self-use
        for input_ids, output_ids in self.duplicated_ids_input_output:
            assert_report_item_list_equal(
                lib._validate_duplicate_reference_ids(input_ids),
                [fixture.error(
                    report_codes.TAG_IDS_DUPLICATION,
                    duplicate_ids_list=output_ids,
                )],
            )


class ValidateReferenceAreResources(ValidateCommonTestData):
    def test_ids_exist(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.resource_ids,
            ),
            [],
        )

    def test_no_ids_empty_list(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                [],
            ),
            [fixture.error(
                report_codes.TAG_CANNOT_CREATE_EMPTY_TAG_NO_IDS_SPECIFIED,
            )],
        )

    def test_id_does_not_exist(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.nonexistent_ids[0:1],
            ),
            fixture_id_not_found_reports(self.nonexistent_ids[0:1]),
        )

    def test_multiple_id_does_not_exist(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.nonexistent_ids,
            ),
            fixture_id_not_found_reports(self.nonexistent_ids),
        )

    def test_id_is_not_a_resource(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.nonresource_ids[0:1],
            ),
            fixture_unexpected_element_reports(self.nonresource_ids[0:1]),
        )

    def test_ids_are_not_resources(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.nonresource_ids,
            ),
            fixture_unexpected_element_reports(self.nonresource_ids),
        )

    def test_mixed_ids(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.resource_ids + self.nonresource_ids + self.nonexistent_ids,
            ),
            fixture_id_not_found_reports(self.nonexistent_ids)
            +
            fixture_unexpected_element_reports(self.nonresource_ids),
        )


class FindTagElementsByIdsTest(ValidateCommonTestData):
    def call_find_elements_by_ids(self, id_list):
        return lib.find_tag_elements_by_ids(
            self.tags_section,
            id_list,
        )

    def test_ids_exist(self):
        element_list, report_list = self.call_find_elements_by_ids(
            self.existent_tags,
        )
        assert_report_item_list_equal(
            report_list,
            [],
        )
        self.assertEqual(
            element_list,
            self.get_tag_elements(self.existent_tags),
        )

    def test_ids_does_not_exist(self):
        element_list, report_list = self.call_find_elements_by_ids(
            self.nonexistent_tags,
        )
        assert_report_item_list_equal(
            report_list,
            fixture_id_not_found_reports(
                self.nonexistent_tags,
                expected_types=["tag"],
            ),
        )
        self.assertEqual(element_list, [])

    def test_mixed_ids(self):
        element_list, report_list = self.call_find_elements_by_ids(
            self.existent_tags[0:1] + self.nonexistent_tags,
        )
        assert_report_item_list_equal(
            report_list,
            fixture_id_not_found_reports(
                self.nonexistent_tags,
                expected_types=["tag"],
            ),
        )
        self.assertEqual(
            element_list,
            self.get_tag_elements(self.existent_tags[0:1]),
        )

    def test_not_tag_ids(self):
        element_list, report_list = self.call_find_elements_by_ids(
            self.nonresource_ids,
        )
        assert_report_item_list_equal(
            report_list,
            fixture_unexpected_element_reports(
                self.nonresource_ids,
                expected_types=["tag"],
            ),
        )
        self.assertEqual(element_list, [])


class LibraryRemoveTag(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(FIXTURE_TWO_TAGS)

    def test_remove_emtpy_list(self):
        lib.remove_tag([])
        assert_xml_equal(FIXTURE_TWO_TAGS, etree_to_str(self.cib))

    def test_remove_a_tag(self):
        lib.remove_tag(
            elem
            for elem in get_tags(self.cib)
            if elem.get("id") == "second_tag"
        )
        assert_xml_equal(FIXTURE_ONE_TAG, etree_to_str(self.cib))

    def test_remove_more_tags(self):
        lib.remove_tag(elem for elem in get_tags(self.cib))
        assert_xml_equal(
            "<cib><configuration><tags/></configuration></cib>",
            etree_to_str(self.cib),
        )


class ValidateCommonConstraintsTestData(TestCase):
    constraint_tags = [
        "tag-colocation",
        "tag-colocation-with",
        "tag-location",
        "tag-order-first",
        "tag-order-then",
        "tag-ticket",
        "tag-colocation-set",
        "tag-location-set",
        "tag-order-set",
        "tag-ticket-set",
        "tag-colocation-idref",
        "tag-location-idref",
        "tag-order-idref",
        "tag-ticket-idref",
        "tag-rule",
    ]
    tag2constraint_id = {
        "tag-colocation": "colocation",
        "tag-colocation-with": "colocation",
        "tag-location": "location",
        "tag-order-first": "order",
        "tag-order-then": "order",
        "tag-ticket": "ticket",
        "tag-colocation-set": "colocation-set",
        "tag-location-set": "location-set",
        "tag-order-set": "order-set",
        "tag-ticket-set": "ticket-set",
        "tag-colocation-idref": "colocation-set-idref",
        "tag-location-idref": "location-set-idref",
        "tag-order-idref": "order-set-idref",
        "tag-ticket-idref": "ticket-set-idref",
        "tag-rule": "location-rule",
    }
    constraint_template = (
        """
        <cib>
          <configuration>
            <resources/>
            <constraints>

              <rsc_colocation id="colocation"
                rsc="{tags[0]}"
                with-rsc="{tags[1]}"/>
              <rsc_location id="location" rsc="{tags[2]}"/>
              <rsc_order id="order" first="{tags[3]}" then="{tags[4]}"/>
              <rsc_ticket id="ticket" rsc="{tags[5]}"/>

              <rsc_colocation id="colocation-set">
                <resource_set id="in-colocation-set">
                  <resource_ref id="{tags[6]}"/>
                  <resource_ref id="dummy"/>
                </resource_set>
              </rsc_colocation>
              <rsc_location id="location-set">
                <resource_set id="in-location-set">
                  <resource_ref id="{tags[7]}"/>
                  <resource_ref id="dummy"/>
                </resource_set>
              </rsc_location>
              <rsc_order id="order-set">
                <resource_set id="in-order-set">
                  <resource_ref id="{tags[8]}"/>
                  <resource_ref id="dummy"/>
                </resource_set>
              </rsc_order>
              <rsc_ticket id="ticket-set">
                <resource_set id="in-ticket-set">
                  <resource_ref id="{tags[9]}"/>
                  <resource_ref id="dummy"/>
                </resource_set>
              </rsc_ticket>

              <rsc_colocation id="colocation-set-idref">
                <resource_set id-ref="{tags[10]}"/>
              </rsc_colocation>
              <rsc_location id="location-set-idref">
                <resource_set id-ref="{tags[11]}"/>
              </rsc_location>
              <rsc_order id="order-set-idref">
                <resource_set id-ref="{tags[12]}"/>
              </rsc_order>
              <rsc_ticket id="ticket-set-idref">
                <resource_set id-ref="{tags[13]}"/>
              </rsc_ticket>

              <rsc_location id="location-rule">
                <rule id-ref="{tags[14]}"/>
              </rsc_location>

            </constraints>
          </configuration>
          <status/>
        </cib>
        """
    )
    tree_each_tag_has_one_constraint = etree.fromstring(
        constraint_template.format(tags=constraint_tags)
    )
    tree_tag_has_multiple_constraints = etree.fromstring(
        constraint_template.format(tags=["multitag"] * len(constraint_tags))
    )


class ValidateRemoveTag(ValidateCommonConstraintsTestData):
    def test_sucess_non_empty_list_for_remove(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_each_tag_has_one_constraint),
                ["not-referenced-tag"],
            ),
            [],
        )

    def test_fail_empty_list_for_remove(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_each_tag_has_one_constraint),
                [],
            ),
            [fixture.error(
                report_codes.TAG_CANNOT_REMOVE_TAGS_NO_TAGS_SPECIFIED
            )],
        )

    def test_fail_tag_referenced_in_constraint(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_each_tag_has_one_constraint),
                ["tag-location"],
            ),
            [fixture.error(
                report_codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                tag_id="tag-location",
                constraint_id_list=["location"],
            )],
        )

    def test_fail_tag_referenced_in_multiple_constraint(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_tag_has_multiple_constraints),
                ["multitag"],
            ),
            [fixture.error(
                report_codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                tag_id="multitag",
                constraint_id_list=sorted(
                    set(self.tag2constraint_id.values()),
                )
            )],
        )


class FindConstraintsReferencingTag(ValidateCommonConstraintsTestData):
    @staticmethod
    def call_find_constraints_referencing_tag(tree, tag_id):
        return lib.find_constraints_referencing_tag(
            get_constraints(tree),
            tag_id,
        )

    def assert_constraint_id(self, tag_id):
        self.assertEqual(
            self.call_find_constraints_referencing_tag(
                self.tree_each_tag_has_one_constraint,
                tag_id,
            )[0].get("id"),
            self.tag2constraint_id[tag_id],
        )

    def test_multiple_constraints(self):
        constraint_list = self.call_find_constraints_referencing_tag(
            self.tree_tag_has_multiple_constraints,
            "multitag",
        )
        constraint_id_set = set(self.tag2constraint_id.values())
        self.assertEqual(
            len(constraint_list),
            len(constraint_id_set),
        )
        for constraint in constraint_list:
            self.assertIn(constraint.get("id"), constraint_id_set)

    def test_colocation(self):
        self.assert_constraint_id("tag-colocation")

    def test_colocation_with(self):
        self.assert_constraint_id("tag-colocation-with")

    def test_location(self):
        self.assert_constraint_id("tag-location")

    def test_order_first(self):
        self.assert_constraint_id("tag-order-first")

    def test_order_then(self):
        self.assert_constraint_id("tag-order-then")

    def test_ticket(self):
        self.assert_constraint_id("tag-ticket")

    def test_colocation_set(self):
        self.assert_constraint_id("tag-colocation-set")

    def test_location_set(self):
        self.assert_constraint_id("tag-location-set")

    def test_order_set(self):
        self.assert_constraint_id("tag-order-set")

    def test_ticket_set(self):
        self.assert_constraint_id("tag-ticket-set")

    def test_colocation_idref(self):
        self.assert_constraint_id("tag-colocation-idref")

    def test_location_idref(self):
        self.assert_constraint_id("tag-location-idref")

    def test_order_idref(self):
        self.assert_constraint_id("tag-order-idref")

    def test_ticket_idref(self):
        self.assert_constraint_id("tag-ticket-idref")

    def test_rule(self):
        self.assert_constraint_id("tag-rule")
