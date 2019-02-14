from unittest import TestCase

from lxml import etree

from pcs.common import report_codes
from pcs.lib.cib.resource import relation
from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs.test.tools.xml import etree_to_str


def _resource(cib, id_):
    return cib.find(f".//*[@id='{id_}']")

def _resources(cib, *ids):
    return [_resource(cib, id_) for id_ in ids]

class ValidateMoveResourcesToGroup(TestCase):
    def setUp(self):
        self.cib = etree.fromstring("""
            <resources>
                <group id="G">
                    <primitive id="RG1" />
                    <primitive id="RG2" />
                </group>
                <primitive id="R1" />
                <primitive id="R2" />
                <primitive id="R3" />
                <clone id="RC1-clone">
                    <primitive id="RC1" />
                </clone>
                <bundle id="RB1-bundle">
                    <primitive id="RB1" />
                </bundle>
            </resources>
        """)
        self.group = self.cib.find(".//group")

    def _resource(self, id_):
        return _resource(self.cib, id_)

    def _resources(self, *ids):
        return _resources(self.cib, *ids)

    def test_no_resources_specified(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self.group,
                []
            ),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_NO_RESOURCES
                ),
            ]
        )

    def test_group_is_not_group(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self._resource("RC1-clone"),
                self._resources("R1")
            ),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="RC1-clone",
                    expected_types=["group"],
                    current_type="clone",
                ),
            ]
        )

    def test_resources_are_not_primitives(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("RC1-clone", "R1", "RB1-bundle")
            ),
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
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("RC1", "R1", "RB1")
            ),
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
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("RG2", "R1", "RG1")
            ),
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
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("RG2", "R1"),
                adjacent_resource=self._resource("RG1")
            ),
            [
            ]
        )

    def test_adjacent_resource_not_in_the_group(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("R1"),
                adjacent_resource=self._resource("R2")
            ),
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

    def test_adjacent_resource_to_be_grouped(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("RG1"),
                adjacent_resource=self._resource("RG1")
            ),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF,
                    resource_id="RG1",
                    group_id="G",
                ),
            ]
        )

    def test_resources_specified_twice(self):
        assert_report_item_list_equal(
            relation.validate_move_resources_to_group(
                self.group,
                self._resources("R3", "R2", "R1", "R2", "R1"),
            ),
            [
                fixture.error(
                    report_codes.CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE,
                    resource_list=["R1", "R2"],
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
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
        relation.move_resources_to_group(
            _resource(cib, "G"),
            _resources(cib, "R1"),
        )
        assert_xml_equal(cib_after, etree_to_str(cib))

    def test_move_last_from_cloned_group(self):
        self._assert_move_last_from_cloned_group("clone")

    def test_move_last_from_mastered_group(self):
        self._assert_move_last_from_cloned_group("master")
