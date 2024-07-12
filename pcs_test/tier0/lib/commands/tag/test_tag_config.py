from unittest import TestCase

from pcs.common.pacemaker.tag import (
    CibTagDto,
    CibTagListDto,
)
from pcs.lib.commands import tag as cmd_tag

from pcs_test.tier0.lib.commands.tag.tag_common import (
    fixture_resources_for_ids,
    fixture_tags_xml,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class TestTagConfigBase(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            tags=fixture_tags_xml(
                [
                    ("tag1", ("i1", "i2")),
                    ("tag2", ("j1", "j2")),
                ]
            ),
            resources=fixture_resources_for_ids(),
        )

    def assert_not_found_reports(self):
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    _id, expected_types=["tag"], context_type="tags"
                )
                for _id in ["nonexistent_tag1", "nonexistent_tag2"]
            ]
        )

    def assert_unexpected_element_reports(self):
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "id1",
                    "primitive",
                    expected_types=["tag"],
                ),
            ]
        )


class TestTagConfig(TestTagConfigBase):
    tag_dicts_list = [
        {
            "tag_id": "tag1",
            "idref_list": ["i1", "i2"],
        },
        {
            "tag_id": "tag2",
            "idref_list": ["j1", "j2"],
        },
    ]

    def test_success_no_args(self):
        self.assertEqual(
            cmd_tag.config(self.env_assist.get_env(), []),
            self.tag_dicts_list,
        )

    def test_only_selected(self):
        self.assertEqual(
            cmd_tag.config(self.env_assist.get_env(), ["tag2"]),
            [self.tag_dicts_list[1]],
        )

    def test_tag_id_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.config(
                self.env_assist.get_env(),
                [
                    "nonexistent_tag1",
                    "tag2",
                    "nonexistent_tag2",
                ],
            )
        )
        self.assert_not_found_reports()

    def test_not_a_tag_id(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.config(self.env_assist.get_env(), ["id1"])
        )
        self.assert_unexpected_element_reports()


class GetTagConfigDto(TestTagConfigBase):
    tag_dto_list = [
        CibTagDto("tag1", ["i1", "i2"]),
        CibTagDto("tag2", ["j1", "j2"]),
    ]

    def test_success_no_args(self):
        self.assertEqual(
            cmd_tag.get_config_dto(self.env_assist.get_env(), []),
            CibTagListDto(self.tag_dto_list),
        )

    def test_success_only_selected(self):
        self.assertEqual(
            cmd_tag.get_config_dto(self.env_assist.get_env(), ["tag2"]),
            CibTagListDto([self.tag_dto_list[1]]),
        )

    def test_success_selected_order(self):
        self.assertEqual(
            cmd_tag.get_config_dto(self.env_assist.get_env(), ["tag2", "tag1"]),
            CibTagListDto(self.tag_dto_list[::-1]),
        )

    def test_tag_id_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.get_config_dto(
                self.env_assist.get_env(),
                [
                    "nonexistent_tag1",
                    "tag2",
                    "nonexistent_tag2",
                ],
            )
        )
        self.assert_not_found_reports()

    def test_not_a_tag_id(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.get_config_dto(self.env_assist.get_env(), ["id1"])
        )
        self.assert_unexpected_element_reports()
