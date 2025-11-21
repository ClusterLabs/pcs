from unittest import TestCase, mock

from pcs.common import reports
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .fixtures import fixture_crm_config_properties


class TestGetProperties(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, evaluate_expired=False):
        return cluster_property.get_properties(
            self.env_assist.get_env(),
            evaluate_expired=evaluate_expired,
        )

    def test_no_properties_configured(self):
        self.config.runner.cib.load()
        self.assertEqual(self.command(), ListCibNvsetDto(nvsets=[]))

    def test_empty_cluster_property_set(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )

    def test_cluster_property_set_with_properties(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [("set_id", {"prop1": "val1", "prop2": "val2"})],
                score_list=[100],
            )
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(
                        id="set_id",
                        options={"score": "100"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id-prop1", name="prop1", value="val1"
                            ),
                            CibNvpairDto(
                                id="set_id-prop2", name="prop2", value="val2"
                            ),
                        ],
                    )
                ]
            ),
        )

    def test_more_cluster_property_sets(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties(
                [
                    ("set_id", {"prop1": "val1", "prop2": "val2"}),
                    ("set_id2", {"prop3": "val3", "prop4": "val4"}),
                ],
                score_list=[100, 200],
            )
        )
        self.assertEqual(
            self.command(),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(
                        id="set_id",
                        options={"score": "100"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id-prop1", name="prop1", value="val1"
                            ),
                            CibNvpairDto(
                                id="set_id-prop2", name="prop2", value="val2"
                            ),
                        ],
                    ),
                    CibNvsetDto(
                        id="set_id2",
                        options={"score": "200"},
                        rule=None,
                        nvpairs=[
                            CibNvpairDto(
                                id="set_id2-prop3", name="prop3", value="val3"
                            ),
                            CibNvpairDto(
                                id="set_id2-prop4", name="prop4", value="val4"
                            ),
                        ],
                    ),
                ]
            ),
        )

    def test_cib_error(self):
        self.config.runner.cib.load(returncode=1, stderr="error")
        self.env_assist.assert_raise_library_error(
            self.command,
            reports=[
                fixture.error(reports.codes.CIB_LOAD_ERROR, reason="error")
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])

    @mock.patch(
        "pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool",
        lambda: True,
    )
    def test_evaluate_expired_but_no_set_rule(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(evaluate_expired=True),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )

    @mock.patch(
        "pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool",
        lambda: False,
    )
    def test_evaluate_expired_no_status_tool(self):
        self.config.runner.cib.load(
            crm_config=fixture_crm_config_properties([("set_id", {})])
        )
        self.assertEqual(
            self.command(evaluate_expired=True),
            ListCibNvsetDto(
                nvsets=[
                    CibNvsetDto(id="set_id", options={}, rule=None, nvpairs=[])
                ]
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RULE_IN_EFFECT_STATUS_DETECTION_NOT_SUPPORTED,
                )
            ]
        )
