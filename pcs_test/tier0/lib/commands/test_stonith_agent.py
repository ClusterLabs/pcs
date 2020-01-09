import logging
from unittest import mock, TestCase
from lxml import etree

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    start_tag_error_text,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.common.reports import ReportItemSeverity as severity
from pcs.lib import resource_agent as lib_ra
from pcs.lib.env import LibraryEnvironment

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
        # pylint: disable=protected-access
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
        # pylint: disable=protected-access
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
