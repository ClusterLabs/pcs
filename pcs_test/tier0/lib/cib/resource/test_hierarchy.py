from unittest import TestCase

from lxml import etree

from pcs.common.reports import codes as report_codes
from pcs.common.reports.const import (
    ADD_REMOVE_CONTAINER_TYPE_GROUP,
    ADD_REMOVE_ITEM_TYPE_RESOURCE,
)
from pcs.lib.cib.resource import hierarchy

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str


def _resource(cib, id_):
    return cib.find(f".//*[@id='{id_}']")


def _resources(cib, *ids):
    return [_resource(cib, id_) for id_ in ids]


class ValidateMoveResourcesToGroup(TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                </group>
                <group id="GX">
                    <primitive id="RGX" />
                </group>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
                <clone id="RC1-clone">
                    <primitive id="RC1" />
                </clone>
                <bundle id="RB1-bundle">
                    <primitive id="RB1">
                        <meta_attributes id="RB1-meta_attributes" />
                    </primitive>
                </bundle>
            </resources>
        """
        )

    def _validate(self, group, resources, adjacent=None):
        return hierarchy.validate_move_resources_to_group(
            _resource(self.cib, group),
            _resources(self.cib, *resources),
            _resource(self.cib, adjacent) if adjacent else None,
        )

    def test_no_resources_specified(self):
        assert_report_item_list_equal(
            self._validate("G", []),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                ),
            ],
        )

    def test_group_is_not_group(self):
        assert_report_item_list_equal(
            self._validate("RB1-meta_attributes", ["R1"]),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="RB1-meta_attributes",
                    expected_types=["group"],
                    current_type="meta_attributes",
                ),
            ],
        )

    def test_resources_are_not_primitives(self):
        assert_report_item_list_equal(
            self._validate("G", ["RC1-clone", "R1", "RB1-bundle"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1-clone",
                    resource_type="clone",
                    parent_id=None,
                    parent_type=None,
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1-bundle",
                    resource_type="bundle",
                    parent_id=None,
                    parent_type=None,
                ),
            ],
        )

    def test_resources_are_in_clones_etc(self):
        assert_report_item_list_equal(
            self._validate("G", ["RC1", "R1", "RB1"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1",
                    resource_type="primitive",
                    parent_id="RC1-clone",
                    parent_type="clone",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1",
                    resource_type="primitive",
                    parent_id="RB1-bundle",
                    parent_type="bundle",
                ),
            ],
        )

    def test_resources_already_in_the_group(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG2", "R1", "RG1"]),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_CANNOT_ADD_ITEMS_ALREADY_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    item_list=["RG1", "RG2"],
                ),
            ],
        )

    def test_allow_moving_resources_in_a_group_if_adjacent(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG2", "R1"], "RG1"), []
        )

    def test_adjacent_resource_not_in_the_group(self):
        # pylint: disable=line-too-long
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "R2"),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="R2",
                ),
            ],
        )

    def test_adjacent_resource_in_another_group(self):
        # pylint: disable=line-too-long
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "RGX"),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="RGX",
                ),
            ],
        )

    def test_adjacent_resource_to_be_grouped(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG1"], "RG1"),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="RG1",
                ),
            ],
        )

    def test_resources_specified_twice(self):
        assert_report_item_list_equal(
            self._validate("G", ["R3", "R2", "R1", "R2", "R1"]),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ITEMS_DUPLICATION,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    duplicate_items_list=["R1", "R2"],
                ),
            ],
        )

    def test_resources_are_not_resources(self):
        assert_report_item_list_equal(
            self._validate("G", ["RB1-meta_attributes"]),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="RB1-meta_attributes",
                    expected_types=["primitive"],
                    current_type="meta_attributes",
                ),
            ],
        )

    def test_adjacent_same_as_moved(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG1", "RG2"], "RG1"),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="RG1",
                ),
            ],
        )

    def test_adjacent_same_as_moved_new_group(self):
        empty_group_element = etree.fromstring('<group id="G-new" />')
        assert_report_item_list_equal(
            hierarchy.validate_move_resources_to_group(
                empty_group_element,
                _resources(self.cib, "RG1"),
                _resource(self.cib, "RG1"),
            ),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G-new",
                    adjacent_item_id="RG1",
                ),
                fixture.error(
                    report_codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G-new",
                    adjacent_item_id="RG1",
                ),
            ],
        )

    def test_new_group_not_valid_id(self):
        # TODO: This can no longer be tested here
        """
        assert_report_item_list_equal(
            self._validate("1Gr:oup", ["R1"]),
            [
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="1Gr:oup",
                    id_description="group name",
                    is_first_char=True,
                    invalid_character="1",
                ),
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="1Gr:oup",
                    id_description="group name",
                    is_first_char=False,
                    invalid_character=":",
                ),
            ],
        )
        """

    def test_adjacent_resource_new_group(self):
        empty_group_element = etree.fromstring('<group id="G-new" />')
        assert_report_item_list_equal(
            hierarchy.validate_move_resources_to_group(
                empty_group_element,
                _resources(self.cib, "RG1"),
                _resource(self.cib, "RG2"),
            ),
            [
                fixture.error(
                    report_codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G-new",
                    adjacent_item_id="RG2",
                ),
            ],
        )

    def test_adjacent_resource_doesnt_exist(self):
        # TODO: This can no longer be tested here
        """

        assert_report_item_list_equal(
            self._validate("G", "RX"),
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    id="RX",
                    expected_types=["primitive"],
                    context_type="resources",
                    context_id="",
                ),
            ],
        )
        """


class MoveResourcesToGroup(TestCase):
    cib_resources = """
        <resources>
            <group id="G">
                <primitive id="RG1" />
                <primitive id="RG2" />
                <primitive id="RG3" />
            </group>
            <primitive id="R1" />
            <primitive id="R2" />
            <primitive id="R3" />
        </resources>
    """

    def test_no_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"), _resources(cib, "R3", "R1")
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_after_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_after_adjacent_last(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG3" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG2"),
            adjacent_resource=_resource(cib, "RG3"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_before_adjacent(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG2"),
            put_after_adjacent=False,
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_before_adjacent_first(self):
        cib_before = self.cib_resources
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="R3" />
                    <primitive id="R1" />
                    <primitive id="RG3" />
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R2" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R3", "R1", "RG3"),
            adjacent_resource=_resource(cib, "RG1"),
            put_after_adjacent=False,
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_from_another_group(self):
        # pylint: disable=no-self-use
        cib_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                    <primitive id="R2" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R2" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R2"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_last_from_group(self):
        # pylint: disable=no-self-use
        cib_before = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <group id="X">
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def _assert_move_last_from_cloned_group(self, clone_type):
        # pylint: disable=no-self-use
        cib_before = f"""
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                </group>
                <{clone_type} id="X-{clone_type}">
                    <group id="X">
                        <primitive id="R1" />
                    </group>
                </{clone_type}>
                <primitive id="R3" />
            </resources>
        """
        cib_after = """
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                    <primitive id="RG3" />
                    <primitive id="R1" />
                </group>
                <primitive id="R3" />
            </resources>
        """
        cib = etree.fromstring(cib_before)
        hierarchy.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_last_from_cloned_group(self):
        self._assert_move_last_from_cloned_group("clone")

    def test_move_last_from_mastered_group(self):
        self._assert_move_last_from_cloned_group("master")
