from unittest import TestCase

from pcs_test.tier0.lib.commands.tag.tag_common import (
    fixture_resources_for_ids,
    fixture_tags_xml,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.lib.commands import tag as cmd_tag

class TestTagConfig(TestCase):
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
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            filename="cib-empty.xml",
            append={
                ".//configuration": fixture_tags_xml([
                    ("tag1", ("i1", "i2")),
                    ("tag2", ("j1", "j2")),
                 ]),
            },
            resources=fixture_resources_for_ids(),
        )

    def test_success_no_args(self):
        self.assertEqual(
            cmd_tag.config(self.env_assist.get_env(), []),
            self.tag_dicts_list,
        )

    def test_tag_id_does_not_exist(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.config(
                self.env_assist.get_env(),
                [
                    "nonexistent_tag1",
                    "tag2",
                    "nonexistent_tag2",
                ]
            )
        )
        self.env_assist.assert_reports([
            fixture.report_not_found(
                _id,
                expected_types=["tag"],
                context_type="tags"
            )
            for _id in ["nonexistent_tag1", "nonexistent_tag2"]
        ])

    def test_not_a_tag_id(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_tag.config(self.env_assist.get_env(), ["id1"])
        )
        self.env_assist.assert_reports([
            fixture.report_unexpected_element(
                "id1",
                "primitive",
                expected_types=["tag"],
            ),
        ])
