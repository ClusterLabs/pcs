from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import tag as cmd_tag
from pcs_test.tier0.lib.commands.tag.tag_common import (
    fixture_resouces_for_reference_ids,
    fixture_tags_xml,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class TestTagUpdate(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources=fixture_resouces_for_reference_ids(
                ["e1", "e2", "e3", "a", "b"]
            ),
            tags=fixture_tags_xml([("t", ["e1", "e2", "e3"])]),
        )

    def test_add_one_id(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "e3", "a"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a"], [])

    def test_add_more_ids(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "e3", "a", "b"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a", "b"], ())

    def test_add_one_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "e1", "e2", "e3"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a"], [], "e1")

    def test_add_more_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b", "e1", "e2", "e3"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a", "b"], [], "e1")

    def test_add_one_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "a", "e3"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a"], [], "e2", True)

    def test_add_more_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "b", "a", "e2", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["b", "a"], [], "e1", True,
        )

    def test_remove_one(self):
        self.config.env.push_cib(tags=fixture_tags_xml([("t", ["e1", "e3"])]),)
        cmd_tag.update(self.env_assist.get_env(), "t", [], ["e2"])

    def test_remove_more(self):
        self.config.env.push_cib(tags=fixture_tags_xml([("t", ["e2"])]),)
        cmd_tag.update(self.env_assist.get_env(), "t", [], ["e1", "e3"])

    def test_combination_add_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "a", "b"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a", "b"], ["e1", "e3"])

    def test_combination_add_before_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b", "e2"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["a", "b"], ["e1", "e3"], "e2",
        )

    def test_combination_add_after_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "a", "b"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["a", "b"],
            ["e1", "e3"],
            "e2",
            True,
        )

    def test_move_existing_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "e3", "e1"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["e2", "e3"], [], "e1")

    def test_move_existing_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "e3", "e1"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["e1"], [], "e3", True)

    def test_move_new_and_existing_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "a", "e3", "b", "e1"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["e2", "a", "e3", "b"], [], "e1",
        )

    def test_move_new_and_existing_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "b", "a", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["b", "a", "e3"], [], "e2", True,
        )

    def test_move_new_and_existing_before_and_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b", "e2", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["a", "b"], ["e1"], "e2",
        )

    def test_move_new_and_existing_after_and_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "b", "a"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["b", "a"], ["e3"], "e2", True,
        )

    def test_tag_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "nonexistent_tag", ["a"], ["e1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    "nonexistent_tag",
                    expected_types=["tag"],
                    context_type="tags",
                ),
            ]
        )

    def test_tag_id_belongs_to_unexpected_type(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "a", ["b"], ["e1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "a", "primitive", expected_types=["tag"],
                ),
            ]
        )

    def test_add_remove_ids_not_specified(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(self.env_assist.get_env(), "t", [], [],)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_UPDATE_TAG_NO_IDS_SPECIFIED
                ),
            ]
        )

    def test_cannot_add_tag_id_to_itself(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(self.env_assist.get_env(), "t", ["t"], [],)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(reports.codes.TAG_CANNOT_CONTAIN_ITSELF),
                fixture.report_unexpected_element(
                    "t",
                    "tag",
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                    ],
                ),
            ]
        )

    def test_add_ids_are_not_resources(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["x", "y"], [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    _id,
                    expected_types=[
                        "bundle",
                        "clone",
                        "group",
                        "master",
                        "primitive",
                    ],
                    context_type="resources",
                )
                for _id in ["x", "y"]
            ]
        )

    def test_add_remove_duplicate_ids(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(),
                "t",
                ["a", "a", "a", "b", "b", "b"],
                ["e1", "e1", "e2", "e2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                    duplicate_ids_list=["a", "b"],
                    add_or_not_remove=True,
                ),
                fixture.error(
                    reports.codes.TAG_ADD_REMOVE_IDS_DUPLICATION,
                    duplicate_ids_list=["e1", "e2"],
                    add_or_not_remove=False,
                ),
            ]
        )

    def test_add_remove_have_intersection(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["a", "b"], ["a", "b"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    # pylint: disable=line-too-long
                    reports.codes.TAG_CANNOT_ADD_AND_REMOVE_THE_SAME_IDS_AT_ONCE,
                    idref_list=["a", "b"],
                ),
            ]
        )

    def test_adjacent_id_in_add_ids(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["e1", "e2"], [], "e2"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_PUT_ID_NEXT_TO_ITSELF, idref="e2",
                ),
            ]
        )

    def test_adjacent_id_in_remove_ids(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["a"], ["e3"], "e3"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_ADJACENT_ID, idref="e3",
                ),
            ]
        )

    def test_adjacent_id_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["a"], [], "b"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_ADJACENT_REFERENCE_ID_NOT_IN_THE_TAG,
                    adjacent_idref="b",
                    tag_id="t",
                ),
            ]
        )

    def test_add_ids_already_in_tag(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", ["a", "e1", "e2"], [],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    # pylint: disable=line-too-long
                    reports.codes.TAG_CANNOT_ADD_REFERENCE_IDS_ALREADY_IN_THE_TAG,
                    idref_list=["e1", "e2"],
                    tag_id="t",
                ),
            ]
        )

    def test_remove_ids_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", [], ["x", "y"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    _id,
                    expected_types=["obj_ref"],
                    context_type="tag",
                    context_id="t",
                )
                for _id in ["x", "y"]
            ]
        )

    def test_remove_ids_belongs_to_unexpected_type(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", [], ["a", "b"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    _id, "primitive", expected_types=["obj_ref"],
                )
                for _id in ["a", "b"]
            ]
        )

    def test_removed_ids_leaves_empty_tag(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(), "t", [], ["e1", "e2", "e3"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    # pylint: disable=line-too-long
                    reports.codes.TAG_CANNOT_REMOVE_REFERENCES_WITHOUT_REMOVING_TAG,
                )
            ]
        )

    def test_remove_all_existing_but_add_new_ones(self):
        self.config.env.push_cib(tags=fixture_tags_xml([("t", ["a", "b"])]),)
        cmd_tag.update(
            self.env_assist.get_env(), "t", ["a", "b"], ["e1", "e2", "e3"],
        )
