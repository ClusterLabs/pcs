from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import tag as cmd_tag

from pcs_test.tier0.lib.commands.tag.tag_common import (
    fixture_resources_for_reference_ids,
    fixture_tags_xml,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


# This class does not focusing on validation testing, there are validator tests
# for that in pcs_test.tier0.lib.cib.test_tag
class TestTagUpdate(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources=fixture_resources_for_reference_ids(
                ["e1", "e2", "e3", "a", "b"]
            ),
            tags=fixture_tags_xml([("t", ["e1", "e2", "e3"])]),
        )

    def test_add_ids(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "e3", "a", "b"])]),
        )
        cmd_tag.update(self.env_assist.get_env(), "t", ["a", "b"], [])

    def test_add_ids_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b", "e1", "e2", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["a", "b"],
            [],
            adjacent_idref="e1",
        )

    def test_add_ids_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "b", "a", "e2", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["b", "a"],
            [],
            adjacent_idref="e1",
            put_after_adjacent=True,
        )

    def test_remove_ids(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2"])]),
        )
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
            self.env_assist.get_env(),
            "t",
            ["a", "b"],
            ["e1", "e3"],
            adjacent_idref="e2",
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
            adjacent_idref="e2",
            put_after_adjacent=True,
        )

    def test_move_existing_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "e3", "e1"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["e2", "e3"],
            [],
            adjacent_idref="e1",
        )

    def test_move_existing_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "e3", "e1"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["e1"],
            [],
            adjacent_idref="e3",
            put_after_adjacent=True,
        )

    def test_move_new_and_existing_before(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e2", "a", "e3", "b", "e1"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["e2", "a", "e3", "b"],
            [],
            adjacent_idref="e1",
        )

    def test_move_new_and_existing_after(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "b", "a", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["b", "a", "e3"],
            [],
            adjacent_idref="e2",
            put_after_adjacent=True,
        )

    def test_move_new_and_existing_before_and_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b", "e2", "e3"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["a", "b"],
            ["e1"],
            adjacent_idref="e2",
        )

    def test_move_new_and_existing_after_and_remove(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["e1", "e2", "b", "a"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["b", "a"],
            ["e3"],
            adjacent_idref="e2",
            put_after_adjacent=True,
        )

    def test_remove_all_existing_but_add_new_ones(self):
        self.config.env.push_cib(
            tags=fixture_tags_xml([("t", ["a", "b"])]),
        )
        cmd_tag.update(
            self.env_assist.get_env(),
            "t",
            ["a", "b"],
            ["e1", "e2", "e3"],
        )
        self.env_assist.assert_reports([])

    def test_raises_exception_in_case_of_report(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.update(
                self.env_assist.get_env(),
                "t",
                [],
                ["e1", "e2", "e3"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_REFERENCES_WITHOUT_REMOVING_TAG,
                    tag_id="t",
                )
            ]
        )
