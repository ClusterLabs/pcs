from unittest import TestCase

from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str

from pcs.common.reports import codes as report_codes
from pcs.lib.cib.resource import hierarchy
from pcs.lib.cib.tools import IdProvider


def _resource(cib, id_):
    return cib.find(f".//*[@id='{id_}']")

def _resources(cib, *ids):
    return [_resource(cib, id_) for id_ in ids]

class ValidateMoveResourcesToGroupMixin():
    def setUp(self):
        # pylint does not know this mixin goes to TestCase
        # pylint: disable=invalid-name
        self.cib = etree.fromstring("""
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
        """)

    def test_no_resources_specified(self):
        assert_report_item_list_equal(
            self._validate("G", []),
            [
                fixture.error(report_codes.CANNOT_GROUP_RESOURCE_NO_RESOURCES),
            ]
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
            ]
        )

    def test_resources_are_not_primitives(self):
        assert_report_item_list_equal(
            self._validate("G", ["RC1-clone", "R1", "RB1-bundle"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1-clone",
                    resource_type="clone",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1-bundle",
                    resource_type="bundle",
                ),
            ]
        )

    def test_resources_are_in_clones_etc(self):
        assert_report_item_list_equal(
            self._validate("G", ["RC1", "R1", "RB1"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1",
                    resource_type="clone",
                ),
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1",
                    resource_type="bundle",
                ),
            ]
        )

    def test_resources_already_in_the_group(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG2", "R1", "RG1"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP,
                    resource_list=["RG1", "RG2"],
                    group_id="G",
                ),
            ]
        )

    def test_allow_moving_resources_in_a_group_if_adjacent(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG2", "R1"], "RG1"),
            [
            ]
        )

    def test_adjacent_resource_not_in_the_group(self):
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "R2"),
            [
                fixture.error(
                    report_codes
                        .CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP
                    ,
                    adjacent_resource_id="R2",
                    group_id="G",
                ),
            ]
        )

    def test_adjacent_resource_in_another_group(self):
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "RGX"),
            [
                fixture.error(
                    report_codes
                        .CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP
                    ,
                    adjacent_resource_id="RGX",
                    group_id="G",
                ),
            ]
        )

    def test_adjacent_resource_to_be_grouped(self):
        assert_report_item_list_equal(
            self._validate("G", ["RG1"], "RG1"),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF,
                    resource_id="RG1",
                ),
            ]
        )

    def test_resources_specified_twice(self):
        assert_report_item_list_equal(
            self._validate("G", ["R3", "R2", "R1", "R2", "R1"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE,
                    resource_list=["R1", "R2"],
                ),
            ]
        )


class ValidateMoveResourcesToGroupByElements(
    ValidateMoveResourcesToGroupMixin, TestCase
):
    def _resource(self, id_):
        return _resource(self.cib, id_)

    def _resources(self, ids):
        return _resources(self.cib, *ids)

    def _validate(self, group, resources, adjacent=None):
        return hierarchy.ValidateMoveResourcesToGroupByElements(
            self._resource(group),
            self._resources(resources),
            self._resource(adjacent) if adjacent else None,
        ).validate()

    def test_resources_are_not_resources(self):
        # The validator expects to get resource elements. So this report is
        # not the best, but at least the validator detects the problem.
        # Validation using IDs provides better reporting in this case.
        assert_report_item_list_equal(
            self._validate("G", ["RB1-meta_attributes"]),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1-meta_attributes",
                    resource_type="meta_attributes",
                ),
            ]
        )


class ValidateMoveResourcesToGroupByIds(
    ValidateMoveResourcesToGroupMixin, TestCase
):
    def _resource(self, id_):
        # this is for inheritance
        # pylint: disable=no-self-use
        return id_

    def _resources(self, ids):
        # this is for inheritance
        # pylint: disable=no-self-use
        return ids

    def _validate(self, group, resources, adjacent=None):
        return hierarchy.ValidateMoveResourcesToGroupByIds(
            self._resource(group),
            self._resources(resources),
            self._resource(adjacent) if adjacent else None,
        ).validate(
            self.cib,
            IdProvider(self.cib),
        )

    def test_new_group_not_valid_id(self):
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
            ]
        )

    def test_missing_resources_specified(self):
        assert_report_item_list_equal(
            self._validate("G", ["RX1", "RX2"]),
            [
                fixture.report_not_found("RX1", context_type="resources"),
                fixture.report_not_found("RX2", context_type="resources"),
            ]
        )

    def test_resources_are_not_resources(self):
        assert_report_item_list_equal(
            self._validate("G", ["RB1-meta_attributes"]),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="RB1-meta_attributes",
                    expected_types=[
                        "bundle", "clone", "group", "master", "primitive",
                    ],
                    current_type="meta_attributes",
                ),
            ]
        )

    def test_adjacent_resource_new_group(self):
        assert_report_item_list_equal(
            self._validate("G-new", ["R1"], "R2"),
            [
                fixture.error(
                    report_codes
                        .CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_FOR_NEW_GROUP
                    ,
                    adjacent_resource_id="R2",
                    group_id="G-new",
                ),
            ]
        )

    def test_adjacent_resource_doesnt_exist(self):
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "RX"),
            [
                fixture.error(
                    report_codes
                        .CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP
                    ,
                    adjacent_resource_id="RX",
                    group_id="G",
                ),
            ]
        )




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
            _resource(cib, "G"),
            _resources(cib, "R3", "R1")
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
            adjacent_resource=_resource(cib, "RG1")
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
            adjacent_resource=_resource(cib, "RG3")
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
            put_after_adjacent=False
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
            put_after_adjacent=False
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
