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
    get_resources,
    get_tags,
    IdProvider,
)


# pylint: disable=protected-access

TagWithRefs = namedtuple("TagWithRefs", ["tag_id", "idref_list"])

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

    fixture_one_tag = """
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
        self.assert_cib_equal(self.fixture_one_tag)

    def test_create_tag_if_tags_exists(self):
        self.cib = etree.fromstring(self.fixture_one_tag)
        self.call_create_tag(self.tag_sets[1])
        self.assert_cib_equal(FIXTURE_TWO_TAGS)


class ValidateCommonTestData(TestCase):
    resource_ids = ["id-01", "id-02", "id-03"]
    nonresource_ids = ["no1", "no2"]
    nonexistent_ids = ["nonexisten1", "nonexisten2"]
    nonexistent_tags = ["nonexistent_tag1", "nonexistent_tag2"]
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
              <primitive id="{}"/>
              <group id="G">
                <primitive id="{}"/>
              </group>
              <clone id="C">
                <primitive id="{}"/>
              </clone>
            </resources>
            <constraints>
              <rsc_location id="{}"/>
            </constraints>
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
          <status>
            <node_state id="{}"/>
          </status>
        </cib>
        """.format(*resource_ids, *nonresource_ids)
    )
    id_provider = IdProvider(get_tags(test_tree))


class LibraryGetListOfTags(ValidateCommonTestData):
    expected_dicts = [
        {
            "tag_id": "first_tag",
            "idref_list": ["idref1", "idref2"],
        },
        {
            "tag_id": "second_tag",
            "idref_list": ["ref1", "ref2", "ref3"],
        },
    ]

    def test_get_all_tags(self):
        self.assertEqual(
            lib.get_list_of_tags(get_tags(self.test_tree), []),
            self.expected_dicts,
        )

    def test_get_specified_tag(self):
        self.assertEqual(
            lib.get_list_of_tags(get_tags(self.test_tree), ["second_tag"]),
            self.expected_dicts[1:2],
        )

    def test_get_specified_tags(self):
        self.assertEqual(
            lib.get_list_of_tags(
                get_tags(self.test_tree),
                ["second_tag", "first_tag"],
            ),
            self.expected_dicts,
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


class ValidateTagIdsExist(ValidateCommonTestData):
    def test_ids_exist(self):
        assert_report_item_list_equal(
            lib.validate_tag_ids_exist(
                get_tags(self.test_tree),
                ["first_tag", "second_tag"],
            ),
            [],
        )

    def test_ids_does_not_exist(self):
        assert_report_item_list_equal(
            lib.validate_tag_ids_exist(
                get_tags(self.test_tree),
                self.nonexistent_tags,
            ),
            fixture_id_not_found_reports(
                self.nonexistent_tags,
                expected_types=["tag"],
            ),
        )

    def test_mixed_ids(self):
        assert_report_item_list_equal(
            lib.validate_tag_ids_exist(
                get_tags(self.test_tree),
                ["first_tag"] + self.nonexistent_tags,
            ),
            fixture_id_not_found_reports(
                self.nonexistent_tags,
                expected_types=["tag"],
            ),
        )

    def test_not_tag_ids(self):
        assert_report_item_list_equal(
            lib.validate_tag_ids_exist(
                get_tags(self.test_tree),
                self.nonresource_ids,
            ),
            fixture_unexpected_element_reports(
                self.nonresource_ids,
                expected_types=["tag"],
            ),
        )
