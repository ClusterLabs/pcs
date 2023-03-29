from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import const
from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.commands.constraint import common as constraint

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.constraints_dto import get_all_constraints
from pcs_test.tools.custom_mock import (
    MockLibraryReportProcessor,
    RuleInEffectEvalMock,
)


def fixture_cib_and_constraints():
    cib = etree.Element(
        "cib",
        {"validate-with": f"pacemaker-{const.PCMK_NEW_ROLES_CIB_VERSION}"},
    )
    config_section = etree.SubElement(cib, "configuration")
    resources_section = etree.SubElement(config_section, "resources")
    for _id in ("A", "B", "E", "F"):
        etree.SubElement(resources_section, "primitive").attrib["id"] = _id
    constraint_section = etree.SubElement(config_section, "constraints")
    return cib, constraint_section


def fixture_env(cib):
    env = mock.MagicMock()
    env.get_cib = mock.Mock()
    env.get_cib.return_value = cib
    env.push_cib = mock.Mock()
    env.report_processor = MockLibraryReportProcessor()
    return env


class CreateWithSetTest(TestCase):
    def setUp(self):
        self.cib, self.constraint_section = fixture_cib_and_constraints()
        self.env = fixture_env(self.cib)
        self.role = const.PCMK_ROLE_PROMOTED_LEGACY
        self.independent_cib = etree.XML(etree.tostring(self.cib))

    def create(self, duplication_allowed=False):
        constraint.create_with_set(
            "rsc_some",
            lambda cib, options, resource_set_list: options,
            self.env,
            [
                {"ids": ["A", "B"], "options": {"role": self.role}},
                {"ids": ["E", "F"], "options": {"action": "start"}},
            ],
            {"id": "some_id", "symmetrical": "true"},
            duplication_alowed=duplication_allowed,
        )

    def test_put_new_constraint_to_constraint_section(self):
        self.create()
        self.env.push_cib.assert_called_once_with()
        self.independent_cib.find(".//constraints").append(
            etree.XML(
                f"""
            <rsc_some id="some_id" symmetrical="true">
                  <resource_set id="some_id_set" role="{const.PCMK_ROLE_PROMOTED_PRIMARY}">
                      <resource_ref id="A"></resource_ref>
                      <resource_ref id="B"></resource_ref>
                  </resource_set>
                  <resource_set action="start" id="some_id_set-1">
                      <resource_ref id="E"></resource_ref>
                      <resource_ref id="F"></resource_ref>
                  </resource_set>
            </rsc_some>
        """
            )
        )
        assert_xml_equal(
            etree.tostring(self.independent_cib).decode(),
            etree.tostring(self.cib).decode(),
        )
        self.env.report_processor.assert_reports(
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=self.role,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
                )
            ]
        )

    def test_refuse_duplicate(self):
        self.create()
        self.env.push_cib.assert_called_once_with()
        assert_raise_library_error(self.create)
        self.env.report_processor.assert_reports(
            [
                (
                    severities.ERROR,
                    report_codes.DUPLICATE_CONSTRAINTS_EXIST,
                    {
                        "constraint_ids": ["some_id"],
                    },
                    report_codes.FORCE,
                ),
                (
                    severities.INFO,
                    report_codes.DUPLICATE_CONSTRAINTS_LIST,
                    {
                        "constraint_type": "rsc_some",
                        "constraint_info_list": [
                            {
                                "options": {
                                    "symmetrical": "true",
                                    "id": "some_id",
                                },
                                "resource_sets": [
                                    {
                                        "ids": ["A", "B"],
                                        "options": {
                                            "role": const.PCMK_ROLE_PROMOTED_PRIMARY,
                                            "id": "some_id_set",
                                        },
                                    },
                                    {
                                        "ids": ["E", "F"],
                                        "options": {
                                            "action": "start",
                                            "id": "some_id_set-1",
                                        },
                                    },
                                ],
                            }
                        ],
                    },
                ),
            ]
            + [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=self.role,
                    replaced_by=const.PCMK_ROLE_PROMOTED,
                )
                for _ in range(2)
            ]
        )

    def test_put_duplicate_constraint_when_duplication_allowed(self):
        self.create()
        self.create(duplication_allowed=True)
        expected_calls = [
            mock.call(),
            mock.call(),
        ]
        self.assertEqual(self.env.push_cib.call_count, len(expected_calls))
        self.env.push_cib.assert_has_calls(expected_calls)

        constraint_section = self.independent_cib.find(".//constraints")
        constraint_section.append(
            etree.XML(
                f"""
            <rsc_some id="some_id" symmetrical="true">
                <resource_set id="some_id_set" role="{const.PCMK_ROLE_PROMOTED_PRIMARY}">
                    <resource_ref id="A"></resource_ref>
                    <resource_ref id="B"></resource_ref>
                </resource_set>
                <resource_set action="start" id="some_id_set-1">
                    <resource_ref id="E"></resource_ref>
                    <resource_ref id="F"></resource_ref>
                </resource_set>
            </rsc_some>
        """
            )
        )
        constraint_section.append(
            etree.XML(
                f"""
            <rsc_some id="some_id" symmetrical="true">
                <resource_set id="some_id_set-2" role="{const.PCMK_ROLE_PROMOTED_PRIMARY}">
                    <resource_ref id="A"></resource_ref>
                    <resource_ref id="B"></resource_ref>
                </resource_set>
                <resource_set action="start" id="some_id_set-3">
                    <resource_ref id="E"></resource_ref>
                    <resource_ref id="F"></resource_ref>
                </resource_set>
            </rsc_some>
        """
            )
        )
        assert_xml_equal(
            etree.tostring(self.independent_cib).decode(),
            etree.tostring(self.cib).decode(),
        )


class GetConfig(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    @mock.patch("pcs.lib.commands.constraint.common.get_rule_evaluator")
    def test_success(self, get_rule_evaluator_mock):
        rule_evaluator = RuleInEffectEvalMock(
            {
                "loc_constr_with_expired_rule-rule": CibRuleInEffectStatus.EXPIRED,
                "loc_constr_with_not_expired_rule": CibRuleInEffectStatus.IN_EFFECT,
            }
        )
        self.config.runner.cib.load(filename="cib-all.xml")
        get_rule_evaluator_mock.return_value = rule_evaluator
        self.assertEqual(
            get_all_constraints(rule_evaluator),
            constraint.get_config(
                self.env_assist.get_env(), evaluate_rules=True
            ),
        )
        get_rule_evaluator_mock.assert_called_once()

    @mock.patch("pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool")
    def test_no_rule_evaluation(self, has_rule_tool_mock):
        has_rule_tool_mock.side_effect = AssertionError(
            "has_rule_in_effect_status_tool should not be called"
        )
        self.config.runner.cib.load(filename="cib-all.xml")
        self.assertEqual(
            get_all_constraints(RuleInEffectEvalMock({})),
            constraint.get_config(
                self.env_assist.get_env(), evaluate_rules=False
            ),
        )
