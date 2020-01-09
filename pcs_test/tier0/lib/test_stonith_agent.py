from unittest import mock, TestCase
from lxml import etree

from pcs_test.tools.assertions import assert_report_item_list_equal

from pcs.common import report_codes
from pcs.common.reports import ReportItemSeverity as severity
from pcs.lib import resource_agent as lib_ra
from pcs.lib.external import CommandRunner


class ValidateParameters(TestCase):
    def setUp(self):
        self.agent = lib_ra.StonithAgent(
            mock.MagicMock(spec_set=CommandRunner),
            "fence_dummy"
        )
        self.metadata = etree.XML("""
            <resource-agent>
                <parameters>
                    <parameter name="test_param" required="0">
                        <longdesc>Long description</longdesc>
                        <shortdesc>short description</shortdesc>
                        <content type="string" default="default_value" />
                    </parameter>
                    <parameter name="required_param" required="1">
                        <content type="boolean" />
                    </parameter>
                    <parameter name="action">
                        <content type="string" default="reboot" />
                        <shortdesc>Fencing action</shortdesc>
                    </parameter>
                </parameters>
            </resource-agent>
        """)
        patcher = mock.patch.object(lib_ra.StonithAgent, "_get_metadata")
        self.addCleanup(patcher.stop)
        self.get_metadata = patcher.start()
        self.get_metadata.return_value = self.metadata

        patcher_fenced = mock.patch.object(
            lib_ra.FencedMetadata, "_get_metadata"
        )
        self.addCleanup(patcher_fenced.stop)
        self.get_fenced_metadata = patcher_fenced.start()
        self.get_fenced_metadata.return_value = etree.XML("""
            <resource-agent>
                <parameters />
            </resource-agent>
        """)
        self.report_error = (
            severity.ERROR,
            report_codes.DEPRECATED_OPTION,
            {
                "option_name": "action",
                "option_type": "stonith",
                "replaced_by": [
                    "pcmk_off_action",
                    "pcmk_reboot_action"
                ],
            },
            report_codes.FORCE_OPTIONS
        )
        self.report_warning = (
            severity.WARNING,
            report_codes.DEPRECATED_OPTION,
            {
                "option_name": "action",
                "option_type": "stonith",
                "replaced_by": [
                    "pcmk_off_action",
                    "pcmk_reboot_action"
                ],
            },
            None
        )


class ValidateParametersCreate(ValidateParameters):
    def test_action_is_deprecated(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_create({
                "action": "reboot",
                "required_param": "value",
            }),
            [
                self.report_error,
            ],
        )

    def test_action_is_deprecated_forced(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_create({
                "action": "reboot",
                "required_param": "value",
            }, force=True),
            [
                self.report_warning,
            ],
        )

    def test_action_not_reported_deprecated_when_empty(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_create({
                "action": "",
                "required_param": "value",
            }),
            [
            ],
        )


class ValidateParametersUpdate(ValidateParameters):
    def test_action_is_deprecated(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_update(
                {
                    "required_param": "value",
                },
                {
                    "action": "reboot",
                }
            ),
            [
                self.report_error,
            ],
        )

    def test_action_not_reported_when_not_updated(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_update(
                {
                    "required_param": "value",
                    "action": "reboot",
                },
                {
                    "required_param": "value2",
                }
            ),
            [
            ],
        )

    def test_action_is_deprecated_when_set_already(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_update(
                {
                    "required_param": "value",
                    "action": "off",
                },
                {
                    "action": "reboot",
                }
            ),
            [
                self.report_error,
            ],
        )

    def test_action_is_deprecated_forced(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_update(
                {
                    "required_param": "value",
                },
                {
                    "action": "reboot",
                },
                force=True
            ),
            [
                self.report_warning,
            ],
        )

    def test_action_not_reported_deprecated_when_empty(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters_update(
                {
                    "required_param": "value",
                    "action": "reboot",
                },
                {
                    "action": "",
                },
            ),
            [
            ],
        )


@mock.patch.object(lib_ra.StonithAgent, "get_actions")
class StonithAgentMetadataGetCibDefaultActions(TestCase):
    fixture_actions = [
        {"name": "custom1", "timeout": "40s"},
        {"name": "custom2", "interval": "25s", "timeout": "60s"},
        {"name": "meta-data"},
        {"name": "monitor", "interval": "10s", "timeout": "30s"},
        {"name": "start", "interval": "40s"},
        {"name": "status", "interval": "15s", "timeout": "20s"},
        {"name": "validate-all"},
    ]

    def setUp(self):
        self.agent = lib_ra.StonithAgent(
            mock.MagicMock(spec_set=CommandRunner),
            "fence_dummy"
        )

    def test_select_only_actions_for_cib(self, get_actions):
        get_actions.return_value = self.fixture_actions
        self.assertEqual(
            [
                {"name": "monitor", "interval": "10s", "timeout": "30s"}
            ],
            self.agent.get_cib_default_actions()
        )

    def test_select_only_necessary_actions_for_cib(self, get_actions):
        get_actions.return_value = self.fixture_actions
        self.assertEqual(
            [
                {"name": "monitor", "interval": "10s", "timeout": "30s"}
            ],
            self.agent.get_cib_default_actions(necessary_only=True)
        )
