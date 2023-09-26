from unittest import TestCase

from pcs.common import reports
from pcs.lib.commands import tag as cmd_tag

from pcs_test.tier0.lib.commands.tag.tag_common import (
    fixture_constraints_for_tags,
    fixture_resources_for_ids,
    fixture_tags_xml,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

TAG_DEFINITIONS = [
    ("tag1", ("i1", "i2")),
    ("tag2", ("j1", "j2")),
    ("tag3", ("k1", "k2")),
]


class TestTagRemove(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_tags_element_is_kept(self):
        self.config.runner.cib.load(
            tags=fixture_tags_xml(TAG_DEFINITIONS[0:1]),
        )
        self.config.env.push_cib(tags="<tags/>")
        cmd_tag.remove(self.env_assist.get_env(), ["tag1"])

    def test_remove_tags_others_are_kept(self):
        self.config.runner.cib.load(
            tags=fixture_tags_xml(TAG_DEFINITIONS),
        )
        self.config.env.push_cib(
            tags=fixture_tags_xml(TAG_DEFINITIONS[2:3]),
        )
        cmd_tag.remove(self.env_assist.get_env(), ["tag1", "tag2"])

    def test_remove_all_tags(self):
        self.config.runner.cib.load(tags=fixture_tags_xml(TAG_DEFINITIONS))
        self.config.env.push_cib(tags="<tags/>")
        cmd_tag.remove(self.env_assist.get_env(), ["tag1", "tag2", "tag3"])

    def test_nonexistent_tag_ids(self):
        self.config.runner.cib.load(tags=fixture_tags_xml(TAG_DEFINITIONS))
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.remove(
                self.env_assist.get_env(),
                ["nonexistent_tag1", "nonexistent_tag2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    _id, expected_types=["tag"], context_type="tags"
                )
                for _id in ["nonexistent_tag1", "nonexistent_tag2"]
            ]
        )

    def test_not_tag_ids(self):
        self.config.runner.cib.load(
            resources=fixture_resources_for_ids(),
            tags=fixture_tags_xml(TAG_DEFINITIONS),
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.remove(self.env_assist.get_env(), ["id1", "id2"])
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    _id,
                    "primitive",
                    expected_types=["tag"],
                )
                for _id in ["id1", "id2"]
            ]
        )

    def test_mixed_ids(self):
        self.config.runner.cib.load(
            resources=fixture_resources_for_ids(),
            tags=fixture_tags_xml(TAG_DEFINITIONS),
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.remove(
                self.env_assist.get_env(),
                ["tag1", "nonexistent_tag1", "id1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    "nonexistent_tag1",
                    expected_types=["tag"],
                    context_type="tags",
                ),
                fixture.report_unexpected_element(
                    "id1",
                    "primitive",
                    expected_types=["tag"],
                ),
            ]
        )

    def test_tag_referenced_in_constraint(self):
        self.config.runner.cib.load(
            constraints=fixture_constraints_for_tags(
                tag[0] for tag in TAG_DEFINITIONS
            ),
            tags=fixture_tags_xml(TAG_DEFINITIONS),
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.remove(
                self.env_assist.get_env(),
                ["tag1"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                    tag_id="tag1",
                    constraint_id_list=["location-tag1"],
                ),
            ]
        )

    def test_multiple_tags_referenced_in_constraints(self):
        self.config.runner.cib.load(
            constraints=fixture_constraints_for_tags(
                tag[0] for tag in TAG_DEFINITIONS
            ),
            tags=fixture_tags_xml(TAG_DEFINITIONS),
        )
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.remove(
                self.env_assist.get_env(),
                ["tag1", "tag2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                    tag_id="tag1",
                    constraint_id_list=["location-tag1"],
                ),
                fixture.error(
                    reports.codes.TAG_CANNOT_REMOVE_TAG_REFERENCED_IN_CONSTRAINTS,
                    tag_id="tag2",
                    constraint_id_list=["location-tag2"],
                ),
            ]
        )
