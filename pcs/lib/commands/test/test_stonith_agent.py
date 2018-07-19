import logging
from lxml import etree
from unittest import mock, TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    start_tag_error_text,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib import resource_agent as lib_ra
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.external import CommandRunner

from pcs.lib.commands import stonith_agent as lib


@mock.patch(
    "pcs.lib.resource_agent.list_stonith_agents",
    lambda runner: [
        "fence_apc",
        "fence_dummy",
        "fence_xvm",
    ]
)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class TestListAgents(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


    def tearDown(self):
        lib_ra.StonithAgent._fenced_metadata = None


    def test_list_all(self):
        self.assertEqual(
            lib.list_agents(self.lib_env, False, None),
            [
                {
                    "name": "fence_apc",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "fence_dummy",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "fence_xvm",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


    def test_search(self):
        self.assertEqual(
            lib.list_agents(self.lib_env, False, "M"),
            [
                {
                    "name": "fence_dummy",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "fence_xvm",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


    @mock.patch.object(lib_ra.Agent, "_get_metadata", autospec=True)
    def test_describe(self, mock_metadata):
        self.maxDiff = None
        def mock_metadata_func(self):
            if self.get_name() == "ocf:test:Stateful":
                raise lib_ra.UnableToGetAgentMetadata(
                    self.get_name(),
                    "test exception"
                )
            return etree.XML("""
                <resource-agent>
                    <shortdesc>short {name}</shortdesc>
                    <longdesc>long {name}</longdesc>
                    <parameters>
                    </parameters>
                    <actions>
                    </actions>
                </resource-agent>
            """.format(name=self.get_name()))
        mock_metadata.side_effect = mock_metadata_func

        # Stateful is missing as it does not provide valid metadata - see above
        self.assertEqual(
            lib.list_agents(self.lib_env, True, None),
            [
                {
                    "name": "fence_apc",
                    "shortdesc": "short fence_apc",
                    "longdesc": "long fence_apc",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "fence_dummy",
                    "shortdesc": "short fence_dummy",
                    "longdesc": "long fence_dummy",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "fence_xvm",
                    "shortdesc": "short fence_xvm",
                    "longdesc": "long fence_xvm",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


@mock.patch.object(lib_ra.StonithAgent, "_load_metadata", autospec=True)
@mock.patch.object(lib_ra.FencedMetadata, "get_parameters", lambda self: [])
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class TestDescribeAgent(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)
        self.metadata = """
            <resource-agent>
                <shortdesc>short desc</shortdesc>
                <longdesc>long desc</longdesc>
                <parameters>
                </parameters>
                <actions>
                </actions>
            </resource-agent>
        """
        self.description = {
            "name": "fence_dummy",
            "shortdesc": "short desc",
            "longdesc": "long desc",
            "parameters": [],
            "actions": [],
            "default_actions": [{"name": "monitor", "interval": "60s"}],
        }


    def tearDown(self):
        lib_ra.StonithAgent._fenced_metadata = None


    def test_success(self, mock_metadata):
        mock_metadata.return_value = self.metadata

        self.assertEqual(
            lib.describe_agent(self.lib_env, "fence_dummy"),
            self.description
        )

        self.assertEqual(len(mock_metadata.mock_calls), 1)


    def test_fail(self, mock_metadata):
        mock_metadata.return_value = "invalid xml"

        assert_raise_library_error(
            lambda: lib.describe_agent(self.lib_env, "fence_dummy"),
            (
                severity.ERROR,
                report_codes.UNABLE_TO_GET_AGENT_METADATA,
                {
                    "agent": "fence_dummy",
                    "reason": start_tag_error_text(),
                }
            )
        )

        self.assertEqual(len(mock_metadata.mock_calls), 1)


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

    def test_action_is_deprecated(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters({
                "action": "reboot",
                "required_param": "value",
            }),
            [
                (
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
                ),
            ],
        )

    def test_action_is_deprecated_forced(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters({
                "action": "reboot",
                "required_param": "value",
            }, allow_invalid=True),
            [
                (
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
                ),
            ],
        )

    def test_action_not_reported_deprecated_when_empty(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters({
                "action": "",
                "required_param": "value",
            }),
            [
            ],
        )

    def test_required_not_specified_on_update(self):
        assert_report_item_list_equal(
            self.agent.validate_parameters({
                "test_param": "value",
            }, update=True),
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
