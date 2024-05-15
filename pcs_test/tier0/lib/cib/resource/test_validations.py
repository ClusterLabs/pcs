from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib.resource import validations

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


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
                <primitive id="S1" class="stonith" />
                <primitive id="S2" class="stonith" />
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
        return validations.validate_move_resources_to_group(
            _resource(self.cib, group),
            _resources(self.cib, *resources),
            _resource(self.cib, adjacent) if adjacent else None,
        )

    def test_no_resources_specified(self):
        assert_report_item_list_equal(
            self._validate("G", []),
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                ),
            ],
        )

    def test_group_is_not_group(self):
        assert_report_item_list_equal(
            self._validate("RB1-meta_attributes", ["R1"]),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
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
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1-clone",
                    resource_type="clone",
                    parent_id=None,
                    parent_type=None,
                ),
                fixture.error(
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RB1-bundle",
                    resource_type="bundle",
                    parent_id=None,
                    parent_type=None,
                ),
            ],
        )

    def test_resources_are_stonith_resources(self):
        assert_report_item_list_equal(
            self._validate("G", ["S1", "S2"]),
            [
                fixture.error(
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="S1",
                    resource_type="stonith",
                    parent_id=None,
                    parent_type=None,
                ),
                fixture.error(
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="S2",
                    resource_type="stonith",
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
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
                    resource_id="RC1",
                    resource_type="primitive",
                    parent_id="RC1-clone",
                    parent_type="clone",
                ),
                fixture.error(
                    reports.codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
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
                    reports.codes.ADD_REMOVE_CANNOT_ADD_ITEMS_ALREADY_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "R2"),
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="R2",
                ),
            ],
        )

    def test_adjacent_resource_in_another_group(self):
        assert_report_item_list_equal(
            self._validate("G", ["R1"], "RGX"),
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
                    reports.codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
                    reports.codes.ADD_REMOVE_ITEMS_DUPLICATION,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
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
                    reports.codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G",
                    adjacent_item_id="RG1",
                ),
            ],
        )

    def test_adjacent_same_as_moved_new_group(self):
        empty_group_element = etree.fromstring('<group id="G-new" />')
        assert_report_item_list_equal(
            validations.validate_move_resources_to_group(
                empty_group_element,
                _resources(self.cib, "RG1"),
                _resource(self.cib, "RG1"),
            ),
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_CANNOT_PUT_ITEM_NEXT_TO_ITSELF,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
                    container_id="G-new",
                    adjacent_item_id="RG1",
                ),
                fixture.error(
                    reports.codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
                    reports.codes.INVALID_ID_BAD_CHAR,
                    id="1Gr:oup",
                    id_description="group name",
                    is_first_char=True,
                    invalid_character="1",
                ),
                fixture.error(
                    reports.codes.INVALID_ID_BAD_CHAR,
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
            validations.validate_move_resources_to_group(
                empty_group_element,
                _resources(self.cib, "RG1"),
                _resource(self.cib, "RG2"),
            ),
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ADJACENT_ITEM_NOT_IN_THE_CONTAINER,
                    container_type=reports.const.ADD_REMOVE_CONTAINER_TYPE_GROUP,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_RESOURCE,
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
                    reports.codes.ID_NOT_FOUND,
                    id="RX",
                    expected_types=["primitive"],
                    context_type="resources",
                    context_id="",
                ),
            ],
        )
        """


class ValidateMoveBanClearMixin:
    # pylint: disable=too-many-public-methods
    @staticmethod
    def _fixture_bundle():
        return etree.fromstring(
            """
            <bundle id="R-bundle">
                <primitive id="R" />
            </bundle>
            """
        )

    @staticmethod
    def _fixture_clone(promotable=False):
        return etree.fromstring(
            f"""
            <clone id="R-clone">
                <primitive id="R" />
                <meta_attributes>
                    <nvpair name="promotable" value="{'true' if promotable else 'false'}" />
                </meta_attributes>
            </clone>
            """
        )

    @staticmethod
    def _fixture_group_clone(promotable=False):
        return etree.fromstring(
            f"""
            <clone id="G-clone">
                <group id="G">
                    <primitive id="R" />
                </group>
                <meta_attributes>
                    <nvpair name="promotable" value="{'true' if promotable else 'false'}" />
                </meta_attributes>
            </clone>
            """
        )

    @staticmethod
    def _fixture_master():
        return etree.fromstring(
            """
            <master id="R-master">
                <primitive id="R" />
            </master>
            """
        )

    @staticmethod
    def _fixture_group_master():
        return etree.fromstring(
            """
            <master id="G-master">
                <group id="G">
                    <primitive id="R" />
                </group>
            </master>
            """
        )

    def test_promoted_true_promotable_clone(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(self.validate(element, True), [])

    def test_promoted_false_promotable_clone(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(self.validate(element, False), [])

    def test_promoted_true_clone(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element, True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R-clone",
                    promotable_id="",
                ),
            ],
        )

    def test_promoted_false_clone(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(self.validate(element, False), [])

    def test_promoted_true_master(self):
        element = self._fixture_master()
        assert_report_item_list_equal(self.validate(element, True), [])

    def test_promoted_false_master(self):
        element = self._fixture_master()
        assert_report_item_list_equal(self.validate(element, False), [])

    def test_promoted_true_promotable_clone_resource(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="R-clone",
                ),
            ],
        )

    def test_promoted_false_promotable_clone_resource(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False), []
        )

    def test_promoted_true_promotable_clone_group(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="G",
                    promotable_id="G-clone",
                ),
            ],
        )

    def test_promoted_false_promotable_clone_group(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), False), []
        )

    def test_promoted_true_promotable_clone_group_resource(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="G-clone",
                ),
            ],
        )

    def test_promoted_false_promotable_clone_group_resource(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), False), []
        )

    def test_promoted_true_clone_resource(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="",
                ),
            ],
        )

    def test_promoted_false_clone_resource(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False), []
        )

    def test_promoted_true_clone_group(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="G",
                    promotable_id="",
                ),
            ],
        )

    def test_promoted_false_clone_group(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), False), []
        )

    def test_promoted_true_clone_group_resource(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="",
                ),
            ],
        )

    def test_promoted_false_clone_group_resource(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), False), []
        )

    def test_promoted_true_master_resource(self):
        element = self._fixture_master()
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="R-master",
                ),
            ],
        )

    def test_promoted_true_master_group(self):
        element = self._fixture_group_master()
        assert_report_item_list_equal(
            self.validate(element.find("./group"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="G",
                    promotable_id="G-master",
                ),
            ],
        )

    def test_promoted_true_master_group_resource(self):
        element = self._fixture_group_master()
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), True),
            [
                fixture.error(
                    self.report_code_bad_promoted,
                    resource_id="R",
                    promotable_id="G-master",
                ),
            ],
        )


class ValidateMove(ValidateMoveBanClearMixin, TestCase):
    validate = staticmethod(validations.validate_move)
    report_code_bad_promoted = (
        reports.codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )

    def test_promoted_false_promotable_clone(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(
            self.validate(element, False),
            [],
        )

    def test_promoted_true_promotable_clone(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(
            self.validate(element, True),
            [],
        )

    def test_promoted_true_clone(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element, True),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE,
                    resource_id="R-clone",
                    promotable_id="",
                ),
            ],
        )

    def test_promoted_false_clone(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element, False),
            [],
        )

    def test_promoted_false_master(self):
        element = self._fixture_master()
        assert_report_item_list_equal(
            self.validate(element, False),
            [],
        )

    def test_promoted_true_master(self):
        element = self._fixture_master()
        assert_report_item_list_equal(
            self.validate(element, True),
            [],
        )

    def test_promoted_false_promotable_clone_resource(self):
        element = self._fixture_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_INNER,
                    resource_id="R",
                    promotable_id="R-clone",
                ),
            ],
        )

    def test_promoted_false_promotable_clone_group(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_INNER,
                    resource_id="G",
                    promotable_id="G-clone",
                ),
            ],
        )

    def test_promoted_false_promotable_clone_group_resource(self):
        element = self._fixture_group_clone(True)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_INNER,
                    resource_id="R",
                    promotable_id="G-clone",
                ),
            ],
        )

    def test_promoted_true_clone_resource(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), True),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="R",
                    clone_id="R-clone",
                ),
            ],
        )

    def test_promoted_false_clone_resource(self):
        element = self._fixture_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="R",
                    clone_id="R-clone",
                ),
            ],
        )

    def test_promoted_true_clone_group(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), True),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="G",
                    clone_id="G-clone",
                ),
            ],
        )

    def test_promoted_false_clone_group(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="G",
                    clone_id="G-clone",
                ),
            ],
        )

    def test_promoted_true_clone_group_resource(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), True),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="R",
                    clone_id="G-clone",
                ),
            ],
        )

    def test_promoted_false_clone_group_resource(self):
        element = self._fixture_group_clone(False)
        assert_report_item_list_equal(
            self.validate(element.find("./group/primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_CLONE_INNER,
                    resource_id="R",
                    clone_id="G-clone",
                ),
            ],
        )

    def test_bundle(self):
        element = self._fixture_bundle()
        assert_report_item_list_equal(
            self.validate(element, False),
            [],
        )

    def test_bundle_resource(self):
        element = self._fixture_bundle()
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_MOVE_RESOURCE_BUNDLE_INNER,
                    resource_id="R",
                    bundle_id="R-bundle",
                ),
            ],
        )


class ValidateBan(ValidateMoveBanClearMixin, TestCase):
    validate = staticmethod(validations.validate_ban)
    report_code_bad_promoted = (
        reports.codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )

    def test_bundle_resource(self):
        element = self._fixture_bundle()
        assert_report_item_list_equal(
            self.validate(element.find("./primitive"), False),
            [
                fixture.error(
                    reports.codes.CANNOT_BAN_RESOURCE_BUNDLE_INNER,
                    resource_id="R",
                    bundle_id="R-bundle",
                ),
            ],
        )


class ValidateUnmoveUnban(ValidateMoveBanClearMixin, TestCase):
    validate = staticmethod(validations.validate_unmove_unban)
    report_code_bad_promoted = (
        reports.codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
    )
