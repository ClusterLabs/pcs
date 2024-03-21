from collections import namedtuple
from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib import tag as lib
from pcs.lib.cib.tools import (
    IdProvider,
    get_constraints,
    get_resources,
    get_tags,
)
from pcs.lib.xml_tools import etree_to_str

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)

TagWithRefs = namedtuple("TagWithRefs", ["tag_id", "idref_list"])

FIXTURE_ONE_TAG = """
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
"""

FIXTURE_TWO_TAGS = """
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
"""


FIXTURE_OBJ_REFS = """
    <tags>
        <tag id="tag-A">
            <obj_ref id="ref1"/>
            <obj_ref id="ref2"/>
            <obj_ref id="ref3"/>
        </tag>
        <tag id="tag-B">
            <obj_ref id="common"/>
            <obj_ref id="ref4"/>
            <obj_ref id="ref5"/>
        </tag>
        <tag id="tag-C">
            <obj_ref id="common"/>
            <obj_ref id="ref4"/>
        </tag>
    </tags>
    """


def get_elements_by_ids(parent, id_list):
    element_list = []
    for _id in id_list:
        found_elements_list = parent.findall(
            f'.//*[@id="{_id}"]',
        )
        if found_elements_list:
            element_list.extend(found_elements_list)
    return element_list


def fixture_unexpected_element_reports(id_list, expected_types=None):
    return [
        fixture.report_unexpected_element(
            _id,
            ValidateCommonTestData.id_to_context_type_map[_id],
            expected_types=(
                [
                    "bundle",
                    "clone",
                    "group",
                    "master",
                    "primitive",
                ]
                if expected_types is None
                else expected_types
            ),
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
        self.cib = etree.fromstring("<cib><configuration/></cib>")

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
    tag_id = "tag_id"
    resource_ids = ["id-01", "id-02", "id-03"]
    nonresource_ids = ["no1", "no2"]
    nonexistent_ids = ["nonexistent1", "nonexistent2"]
    nonexistent_tags = ["nonexistent_tag1", "nonexistent_tag2"]
    existent_tags = ["first_tag", "second_tag"]
    id_to_context_type_map = {
        "no1": "rsc_location",
        "no2": "resources",
        "nonexistent1": "resources",
        "nonexistent2": "resources",
        "#invalid-tag-id": "resources",
        "tag_id": "resources",
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
            [lib.tag_element_to_dict(element) for element in element_list],
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
                fixture.report_invalid_id(tag_id, "#", id_description="id"),
                fixture.error(reports.codes.TAG_CANNOT_CONTAIN_ITSELF),
                *fixture_unexpected_element_reports(
                    2 * self.nonresource_ids[:1]
                ),
                *fixture_id_not_found_reports(2 * self.nonresource_ids[1:]),
                *fixture_id_not_found_reports([tag_id]),
                fixture.error(
                    reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                    duplicate_ids_list=self.nonresource_ids,
                    add_or_not_remove=True,
                ),
            ],
        )


class ValidateTagIdTest(ValidateCommonTestData):
    # pylint: disable=protected-access
    def test_tag_id_is_valid(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("new-tag-id", self.id_provider),
            [],
        )

    def test_tag_id_is_empty(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("", self.id_provider),
            [
                fixture.error(
                    reports.codes.INVALID_ID_IS_EMPTY,
                    id_description="id",
                )
            ],
        )

    def test_tag_id_invalid_first_character(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("0tagid", self.id_provider),
            [fixture.report_invalid_id("0tagid", "0")],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("-tagid", self.id_provider),
            [fixture.report_invalid_id("-tagid", "-")],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("átagid", self.id_provider),
            [fixture.report_invalid_id("átagid", "á")],
        )

    def test_tag_id_invalid_character(self):
        assert_report_item_list_equal(
            lib._validate_tag_id("tag,id", self.id_provider),
            [fixture.report_invalid_id("tag,id", ",")],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("tagid>", self.id_provider),
            [fixture.report_invalid_id("tagid>", ">")],
        )
        assert_report_item_list_equal(
            lib._validate_tag_id("taígid", self.id_provider),
            [fixture.report_invalid_id("taígid", "í")],
        )

    def test_tag_id_already_exists(self):
        for tag_id in ["id-01", "id-02"]:
            assert_report_item_list_equal(
                lib._validate_tag_id(tag_id, self.id_provider),
                [fixture.error(reports.codes.ID_ALREADY_EXISTS, id=tag_id)],
            )


class ValidateTagIdNotInIdrefList(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.idref_list = ["id1", "id2", "id3"]

    def test_tag_contains_itself(self):
        assert_report_item_list_equal(
            lib._validate_tag_id_not_in_idref_list(
                self.idref_list[0],
                self.idref_list,
            ),
            [fixture.error(reports.codes.TAG_CANNOT_CONTAIN_ITSELF)],
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
    # pylint: disable=protected-access
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
            lib._validate_add_remove_duplicate_reference_ids(["id1", "id2"]),
            [],
        )

    def test_duplicates(self):
        # pylint: disable=no-self-use
        for input_ids, output_ids in self.duplicated_ids_input_output:
            assert_report_item_list_equal(
                lib._validate_add_remove_duplicate_reference_ids(input_ids),
                [
                    fixture.error(
                        reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                        duplicate_ids_list=output_ids,
                        add_or_not_remove=True,
                    )
                ],
            )


class ValidateTagCreateIdrefListNotEmpty(TestCase):
    # pylint: disable=protected-access
    def test_empty_list(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib._validate_tag_create_idref_list_not_empty([]),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_CREATE_EMPTY_TAG_NO_IDS_SPECIFIED,
                )
            ],
        )

    def test_not_empty_list(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib._validate_tag_create_idref_list_not_empty(["id"]),
            [],
        )


class ValidateReferenceIdsAreResources(ValidateCommonTestData):
    # pylint: disable=protected-access
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
            [],
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
            fixture_unexpected_element_reports(self.nonresource_ids[:1])
            + fixture_id_not_found_reports(self.nonresource_ids[1:]),
        )

    def test_mixed_ids(self):
        assert_report_item_list_equal(
            lib._validate_reference_ids_are_resources(
                get_resources(self.test_tree),
                self.resource_ids + self.nonresource_ids + self.nonexistent_ids,
            ),
            fixture_unexpected_element_reports(self.nonresource_ids[:1])
            + fixture_id_not_found_reports(self.nonresource_ids[1:])
            + fixture_id_not_found_reports(self.nonexistent_ids),
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
                self.nonresource_ids[:1], expected_types=["tag"]
            )
            + [
                fixture.report_not_found(
                    self.nonresource_ids[1],
                    context_type="tags",
                    expected_types=["tag"],
                )
            ],
        )
        self.assertEqual(element_list, [])


class LibraryRemoveTag(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(FIXTURE_TWO_TAGS)

    def test_remove_empty_list(self):
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
    }
    constraint_template = """
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
            </constraints>
          </configuration>
          <status/>
        </cib>
        """
    tree_each_tag_has_one_constraint = etree.fromstring(
        constraint_template.format(tags=constraint_tags)
    )
    tree_tag_has_multiple_constraints = etree.fromstring(
        constraint_template.format(tags=["multitag"] * len(constraint_tags))
    )


class ValidateRemoveTag(ValidateCommonConstraintsTestData):
    def test_success_non_empty_list_for_remove(self):
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
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAGS_NO_TAGS_SPECIFIED
                )
            ],
        )

    def test_fail_tag_referenced_in_constraint(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_each_tag_has_one_constraint),
                ["tag-location"],
            ),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                    tag_id="tag-location",
                    constraint_id_list=["location"],
                )
            ],
        )

    def test_fail_tag_referenced_in_multiple_constraint(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib.validate_remove_tag(
                get_constraints(self.tree_tag_has_multiple_constraints),
                ["multitag"],
            ),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                    tag_id="multitag",
                    constraint_id_list=sorted(
                        set(self.tag2constraint_id.values()),
                    ),
                )
            ],
        )


class FindConstraintsReferencingTag(ValidateCommonConstraintsTestData):
    @staticmethod
    def call_find_constraints_referencing_tag(tree, tag_id):
        return lib.find_constraints_referencing_tag(
            get_constraints(tree),
            tag_id,
        )

    def assert_constraint_id(self, tag_id):
        one_constraint_list = self.call_find_constraints_referencing_tag(
            self.tree_each_tag_has_one_constraint,
            tag_id,
        )
        self.assertEqual(len(one_constraint_list), 1)
        self.assertEqual(
            one_constraint_list[0].get("id"),
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


class ValidateAddRemoveDuplicateReferenceIds(ValidateCommonTestData):
    # pylint: disable=protected-access
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

    def test_add_no_duplicates(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib._validate_add_remove_duplicate_reference_ids(["id1", "id2"]),
            [],
        )

    def test_remove_no_duplicates(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            lib._validate_add_remove_duplicate_reference_ids(
                ["id1", "id2"],
                False,
            ),
            [],
        )

    def test_add_duplicates(self):
        for input_ids, output_ids in self.duplicated_ids_input_output:
            with self.subTest(input_ids=input_ids, output_ids=output_ids):
                assert_report_item_list_equal(
                    lib._validate_add_remove_duplicate_reference_ids(input_ids),
                    [
                        fixture.error(
                            reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                            duplicate_ids_list=output_ids,
                            add_or_not_remove=True,
                        )
                    ],
                )

    def test_remove_duplicates(self):
        for input_ids, output_ids in self.duplicated_ids_input_output:
            with self.subTest(input_ids=input_ids, output_ids=output_ids):
                assert_report_item_list_equal(
                    lib._validate_add_remove_duplicate_reference_ids(
                        input_ids,
                        False,
                    ),
                    [
                        fixture.error(
                            reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                            duplicate_ids_list=output_ids,
                            add_or_not_remove=False,
                        )
                    ],
                )


class LibraryRemoveObjRef(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(FIXTURE_OBJ_REFS)

    def test_remove_empty_list(self):
        lib.remove_obj_ref([])
        assert_xml_equal(FIXTURE_OBJ_REFS, etree_to_str(self.cib))

    def test_remove_refs_from_a_tag_without_removing_tag(self):
        lib.remove_obj_ref(get_elements_by_ids(self.cib, ["ref1", "ref2"]))
        assert_xml_equal(
            """
            <tags>
                <tag id="tag-A">
                    <obj_ref id="ref3"/>
                </tag>
                <tag id="tag-B">
                    <obj_ref id="common"/>
                    <obj_ref id="ref4"/>
                    <obj_ref id="ref5"/>
                </tag>
                <tag id="tag-C">
                    <obj_ref id="common"/>
                    <obj_ref id="ref4"/>
                </tag>
            </tags>
            """,
            etree_to_str(self.cib),
        )

    def test_remove_refs_from_a_tag_with_removing_tag(self):
        lib.remove_obj_ref(
            get_elements_by_ids(self.cib, ["ref1", "ref2", "ref3"])
        )
        assert_xml_equal(
            """
            <tags>
                <tag id="tag-B">
                    <obj_ref id="common"/>
                    <obj_ref id="ref4"/>
                    <obj_ref id="ref5"/>
                </tag>
                <tag id="tag-C">
                    <obj_ref id="common"/>
                    <obj_ref id="ref4"/>
                </tag>
            </tags>
            """,
            etree_to_str(self.cib),
        )

    def test_remove_refs_from_multiple_tags_without_removing_tag(self):
        lib.remove_obj_ref(get_elements_by_ids(self.cib, ["ref4", "ref5"]))
        assert_xml_equal(
            """
            <tags>
                <tag id="tag-A">
                    <obj_ref id="ref1"/>
                    <obj_ref id="ref2"/>
                    <obj_ref id="ref3"/>
                </tag>
                <tag id="tag-B">
                    <obj_ref id="common"/>
                </tag>
                <tag id="tag-C">
                    <obj_ref id="common"/>
                </tag>
            </tags>
            """,
            etree_to_str(self.cib),
        )

    def test_remove_refs_from_multiple_tags_with_removing_tags(self):
        lib.remove_obj_ref(get_elements_by_ids(self.cib, ["common", "ref4"]))
        assert_xml_equal(
            """
            <tags>
                <tag id="tag-A">
                    <obj_ref id="ref1"/>
                    <obj_ref id="ref2"/>
                    <obj_ref id="ref3"/>
                </tag>
                <tag id="tag-B">
                    <obj_ref id="ref5"/>
                </tag>
            </tags>
            """,
            etree_to_str(self.cib),
        )


class LibraryAddObjRef(TestCase):
    def setUp(self):
        self.tag_el = etree.fromstring(
            """
            <tag>
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
                <obj_ref id="e3"/>
            </tag>
            """
        )
        self.new_list = [etree.Element("obj_ref", id=_id) for _id in "ab"]
        self.existing_list = get_elements_by_ids(
            self.tag_el,
            ["e1", "e2", "e3"],
        )

    def test_add_new_ids(self):
        lib.add_obj_ref(
            self.tag_el,
            self.new_list,
            None,
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
                <obj_ref id="e3"/>
                <obj_ref id="a"/>
                <obj_ref id="b"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_add_new_ids_before_adjacent(self):
        lib.add_obj_ref(
            self.tag_el,
            self.new_list,
            self.existing_list[0],
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="a"/>
                <obj_ref id="b"/>
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
                <obj_ref id="e3"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_add_new_ids_after_adjacent(self):
        lib.add_obj_ref(
            self.tag_el,
            self.new_list,
            self.existing_list[1],
            put_after_adjacent=True,
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
                <obj_ref id="a"/>
                <obj_ref id="b"/>
                <obj_ref id="e3"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_move_existing_ids_before(self):
        lib.add_obj_ref(
            self.tag_el,
            self.existing_list[2:0:-1],
            self.existing_list[0],
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="e3"/>
                <obj_ref id="e2"/>
                <obj_ref id="e1"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_move_existing_ids_after(self):
        lib.add_obj_ref(
            self.tag_el,
            self.existing_list[2::-2],
            self.existing_list[1],
            put_after_adjacent=True,
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="e2"/>
                <obj_ref id="e3"/>
                <obj_ref id="e1"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_move_both_new_and_existing_before(self):
        el_list = [
            self.new_list[1],
            self.existing_list[0],
            self.new_list[0],
            self.existing_list[2],
        ]
        lib.add_obj_ref(self.tag_el, el_list, self.existing_list[1])
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="b"/>
                <obj_ref id="e1"/>
                <obj_ref id="a"/>
                <obj_ref id="e3"/>
                <obj_ref id="e2"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )

    def test_move_both_new_and_existing_after(self):
        el_list = [
            self.new_list[1],
            self.new_list[0],
            self.existing_list[0],
            self.existing_list[1],
        ]
        lib.add_obj_ref(
            self.tag_el,
            el_list,
            self.existing_list[2],
            put_after_adjacent=True,
        )
        assert_xml_equal(
            """
            <tag>
                <obj_ref id="e3"/>
                <obj_ref id="b"/>
                <obj_ref id="a"/>
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
            </tag>
            """,
            etree_to_str(self.tag_el),
        )


class ValidateTagUpdateByIds(TestCase):
    OBJ_REF_EXPECTED_TYPES = ["bundle", "clone", "group", "master", "primitive"]
    test_cib = etree.fromstring(
        """
        <cib>
          <configuration>
            <resources>
              <primitive id="e1"/>
              <primitive id="e2"/>
              <primitive id="e3"/>
              <primitive id="new1"/>
            </resources>
            <tags>
              <tag id="tag">
                <obj_ref id="e1"/>
                <obj_ref id="e2"/>
                <obj_ref id="e3"/>
              </tag>
            </tags>
            <rsc_defaults>
                <meta_attributes id="other_id" />
            </rsc_defaults>
          </configuration>
          <status>
            <node_state id="status_id"/>
          </status>
        </cib>
        """
    )

    def _validate(self, tag, to_add, to_remove, adjacent=None):
        return lib.ValidateTagUpdateByIds(
            tag,
            to_add,
            to_remove,
            adjacent_idref=adjacent,
        ).validate(get_resources(self.test_cib), get_tags(self.test_cib))

    def test_tag_id_not_a_tag(self):
        assert_report_item_list_equal(
            self._validate("new1", ["new1"], ["none"], adjacent="none"),
            [fixture.report_unexpected_element("new1", "primitive", ["tag"])],
        )

    def test_not_existing_tag(self):
        assert_report_item_list_equal(
            self._validate("none_tag", ["e1"], []),
            [
                fixture.report_not_found(
                    "none_tag",
                    context_type="tags",
                    expected_types=["tag"],
                ),
            ],
        )

    def test_not_existing_tag_and_no_ids(self):
        assert_report_item_list_equal(
            self._validate("none_tag", [], []),
            [
                fixture.report_not_found(
                    "none_tag",
                    context_type="tags",
                    expected_types=["tag"],
                ),
                fixture.error(
                    reports.codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED,
                ),
            ],
        )

    def test_not_existing_tag_id_and_bad_add_ids(self):
        assert_report_item_list_equal(
            self._validate("none_tag", ["none", "status_id", "other_id"], []),
            [
                fixture.report_not_found(
                    "none_tag",
                    context_type="tags",
                    expected_types=["tag"],
                ),
                fixture.report_not_found(
                    "none",
                    context_type="resources",
                    expected_types=self.OBJ_REF_EXPECTED_TYPES,
                ),
                fixture.report_not_found(
                    "status_id",
                    context_type="resources",
                    expected_types=self.OBJ_REF_EXPECTED_TYPES,
                ),
                fixture.report_unexpected_element(
                    "other_id", "meta_attributes", self.OBJ_REF_EXPECTED_TYPES
                ),
            ],
        )

    def test_existing_tag_and_no_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", [], []),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED,
                ),
            ],
        )

    def test_existing_tag_and_no_ids_with_not_existing_adjacent(self):
        assert_report_item_list_equal(
            self._validate("tag", [], [], adjacent="none"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED,
                ),
                fixture.error(
                    reports.codes.TAG_CANNOT_SPECIFY_ADJACENT_ID_WITHOUT_IDS_TO_ADD,
                    adjacent_id="none",
                ),
                fixture.error(
                    reports.codes.TAG_ADJACENT_REFERENCE_ID_NOT_IN_THE_TAG,
                    adjacent_id="none",
                    tag_id="tag",
                ),
            ],
        )

    def test_existing_tag_and_no_ids_with_existing_adjacent(self):
        assert_report_item_list_equal(
            self._validate("tag", [], [], adjacent="e1"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED,
                ),
                fixture.error(
                    reports.codes.TAG_CANNOT_SPECIFY_ADJACENT_ID_WITHOUT_IDS_TO_ADD,
                    adjacent_id="e1",
                ),
            ],
        )

    def test_existing_tag_and_no_add_ids_with_existing_adjacent(self):
        assert_report_item_list_equal(
            self._validate("tag", [], ["e2"], adjacent="e1"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_SPECIFY_ADJACENT_ID_WITHOUT_IDS_TO_ADD,
                    adjacent_id="e1",
                ),
            ],
        )

    def test_add_ids_errors(self):
        assert_report_item_list_equal(
            self._validate(
                "tag",
                [
                    "new1",
                    "new1",
                    "none",
                    "none",
                    "other_id",
                    "other_id",
                    "e1",
                    "e1",
                    "status_id",
                    "status_id",
                    "e2",
                    "e2",
                ],
                [],
            ),
            [
                fixture.error(
                    reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                    duplicate_ids_list=[
                        "e1",
                        "e2",
                        "new1",
                        "none",
                        "other_id",
                        "status_id",
                    ],
                    add_or_not_remove=True,
                ),
                fixture.report_not_found(
                    "none",
                    context_type="resources",
                    expected_types=self.OBJ_REF_EXPECTED_TYPES,
                ),
                fixture.report_unexpected_element(
                    "other_id", "meta_attributes", self.OBJ_REF_EXPECTED_TYPES
                ),
                fixture.report_not_found(
                    "status_id",
                    context_type="resources",
                    expected_types=self.OBJ_REF_EXPECTED_TYPES,
                ),
                fixture.error(
                    reports.codes.TAG_CANNOT_ADD_REFERENCE_IDS_ALREADY_IN_THE_TAG,
                    idref_list=["e1", "e2"],
                    tag_id="tag",
                ),
            ],
        )

    def test_non_existing_adjacent_in_add_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", ["new1", "e1"], [], adjacent="e1"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_PUT_ID_NEXT_TO_ITSELF,
                    adjacent_id="e1",
                ),
            ],
        )

    def test_existing_adjacent_in_add_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", ["new1", "e1"], [], adjacent="new1"),
            [
                fixture.error(
                    reports.codes.TAG_ADJACENT_REFERENCE_ID_NOT_IN_THE_TAG,
                    adjacent_id="new1",
                    tag_id="tag",
                ),
            ],
        )

    def test_adjacent_in_remove_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", ["e2"], ["e1"], adjacent="e1"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_ADJACENT_ID,
                    adjacent_id="e1",
                ),
            ],
        )

    def test_remove_ids_errors(self):
        assert_report_item_list_equal(
            self._validate(
                "tag",
                [],
                [
                    "e1",
                    "e1",
                    "e2",
                    "e2",
                    "none",
                    "none",
                    "none1",
                    "none1",
                ],
            ),
            [
                fixture.error(
                    reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                    duplicate_ids_list=["e1", "e2", "none", "none1"],
                    add_or_not_remove=False,
                ),
                fixture.error(
                    reports.codes.TAG_IDS_NOT_IN_THE_TAG,
                    tag_id="tag",
                    id_list=["none", "none1"],
                ),
            ],
        )

    def test_remove_all_without_add(self):
        assert_report_item_list_equal(
            self._validate("tag", [], ["e1", "e2", "e3"]),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_REFERENCES_WITHOUT_REMOVING_TAG,
                    tag_id="tag",
                ),
            ],
        )

    def test_remove_all_and_add_new_one(self):
        assert_report_item_list_equal(
            self._validate("tag", ["new1"], ["e1", "e2", "e3"]),
            [],
        )

    def test_remove_all_and_add_missing_id(self):
        assert_report_item_list_equal(
            self._validate("tag", ["none"], ["e1", "e2", "e3"]),
            [
                fixture.report_not_found(
                    "none",
                    context_type="resources",
                    expected_types=self.OBJ_REF_EXPECTED_TYPES,
                ),
            ],
        )

    def test_add_and_remove_the_same_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", ["new1"], ["new1"]),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_ADD_AND_REMOVE_IDS_AT_THE_SAME_TIME,
                    idref_list=["new1"],
                ),
                fixture.error(
                    reports.codes.TAG_IDS_NOT_IN_THE_TAG,
                    tag_id="tag",
                    id_list=["new1"],
                ),
            ],
        )

    def test_move_and_remove_the_same_ids(self):
        assert_report_item_list_equal(
            self._validate("tag", ["e1", "e2"], ["e2", "e1"], adjacent="e3"),
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_ADD_AND_REMOVE_IDS_AT_THE_SAME_TIME,
                    idref_list=["e1", "e2"],
                ),
            ],
        )


class ExpandTag(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
                <configuration>
                    <resources>
                        <primitive id="R1"/>
                        <clone id="C">
                            <primitive id="RC"/>
                        </clone>
                        <primitive id="R2"/>
                    </resources>
                    <tags>
                        <tag id="tag1">
                            <obj_ref id="R1"/>
                            <obj_ref id="C"/>
                        </tag>
                        <tag id="tag2">
                            <obj_ref id="R2"/>
                        </tag>
                    </tags>
                </configuration>
            </cib>
        """
        )

    @staticmethod
    def get_ids(elements):
        return [el.get("id") for el in elements]

    def test_no_tag(self):
        el_list = lib.expand_tag(self.cib.xpath(".//primitive[@id='R1']")[0])
        self.assertEqual(self.get_ids(el_list), ["R1"])

    def test_expand_all_types(self):
        el_list = lib.expand_tag(self.cib.xpath(".//tag[@id='tag1']")[0])
        self.assertEqual(self.get_ids(el_list), ["R1", "C"])

    def test_expand_selected_types(self):
        el_list = lib.expand_tag(
            self.cib.xpath(".//tag[@id='tag1']")[0], ["clone"]
        )
        self.assertEqual(self.get_ids(el_list), ["C"])
