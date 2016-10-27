from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging
from lxml import etree

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.common import report_codes
from pcs.lib import resource_agent as lib_ra
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import ReportItemSeverity as severity

from pcs.lib.commands import resource_agent as lib


@mock.patch("pcs.lib.resource_agent.list_resource_agents_standards")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class TestListStandards(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


    def test_success(self, mock_list_standards):
        standards = [
            "lsb",
            "nagios",
            "ocf",
            "service",
            "systemd",
        ]
        mock_list_standards.return_value = standards

        self.assertEqual(
            lib.list_standards(self.lib_env),
            standards
        )

        mock_list_standards.assert_called_once_with("mock_runner")


@mock.patch("pcs.lib.resource_agent.list_resource_agents_ocf_providers")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class TestListOcfProviders(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


    def test_success(self, mock_list_providers):
        providers = [
            "booth",
            "heartbeat",
            "openstack",
            "pacemaker",
        ]
        mock_list_providers.return_value = providers

        self.assertEqual(
            lib.list_ocf_providers(self.lib_env),
            providers
        )

        mock_list_providers.assert_called_once_with("mock_runner")


@mock.patch("pcs.lib.resource_agent.list_resource_agents_standards")
@mock.patch("pcs.lib.resource_agent.list_resource_agents")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class TestListAgentsForStandardAndProvider(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


    def test_standard_specified(self, mock_list_agents, mock_list_standards):
        agents = [
            "Delay",
            "Dummy",
            "Stateful",
        ]
        mock_list_agents.return_value = agents

        self.assertEqual(
            lib.list_agents_for_standard_and_provider(self.lib_env, "ocf:test"),
            agents
        )

        mock_list_agents.assert_called_once_with("mock_runner", "ocf:test")
        mock_list_standards.assert_not_called()


    def test_standard_not_specified(
        self, mock_list_agents, mock_list_standards
    ):
        agents_ocf = [
            "Delay",
            "Dummy",
            "Stateful",
        ]
        agents_service = [
            "corosync",
            "pacemaker",
            "pcsd",
        ]
        mock_list_standards.return_value = ["ocf:test", "service"]
        mock_list_agents.side_effect = [agents_ocf, agents_service]

        self.assertEqual(
            lib.list_agents_for_standard_and_provider(self.lib_env),
            sorted(agents_ocf + agents_service, key=lambda x: x.lower())
        )

        mock_list_standards.assert_called_once_with("mock_runner")
        self.assertEqual(2, len(mock_list_agents.mock_calls))
        mock_list_agents.assert_has_calls([
            mock.call("mock_runner", "ocf:test"),
            mock.call("mock_runner", "service"),
        ])


@mock.patch(
    "pcs.lib.resource_agent.list_resource_agents_standards_and_providers",
    lambda runner: ["service", "ocf:test"]
)
@mock.patch(
    "pcs.lib.resource_agent.list_resource_agents",
    lambda runner, standard: {
        "ocf:test": [
            "Stateful",
            "Delay",
        ],
        "service": [
            "corosync",
            "pacemaker_remote",
        ],
    }.get(standard, [])
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


    def test_list_all(self):
        self.assertEqual(
            lib.list_agents(self.lib_env, False, None),
            [
                {
                    "name": "ocf:test:Delay",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "ocf:test:Stateful",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "service:corosync",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "service:pacemaker_remote",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


    def test_search(self):
        self.assertEqual(
            lib.list_agents(self.lib_env, False, "te"),
            [
                {
                    "name": "ocf:test:Delay",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "ocf:test:Stateful",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "service:pacemaker_remote",
                    "shortdesc": "",
                    "longdesc": "",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


    @mock.patch.object(lib_ra.Agent, "_get_metadata", autospec=True)
    def test_describe(self, mock_metadata):
        def mock_metadata_func(self):
            if self._full_agent_name == "ocf:test:Stateful":
                raise lib_ra.UnableToGetAgentMetadata(
                    self._full_agent_name,
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
            """.format(name=self._full_agent_name))
        mock_metadata.side_effect = mock_metadata_func

        # Stateful is missing as it does not provide valid metadata - see above
        self.assertEqual(
            lib.list_agents(self.lib_env, True, None),
            [
                {
                    "name": "ocf:test:Delay",
                    "shortdesc": "short ocf:test:Delay",
                    "longdesc": "long ocf:test:Delay",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "service:corosync",
                    "shortdesc": "short service:corosync",
                    "longdesc": "long service:corosync",
                    "parameters": [],
                    "actions": [],
                },
                {
                    "name": "service:pacemaker_remote",
                    "shortdesc": "short service:pacemaker_remote",
                    "longdesc": "long service:pacemaker_remote",
                    "parameters": [],
                    "actions": [],
                },
            ]
        )


@mock.patch.object(lib_ra.ResourceAgent, "_load_metadata", autospec=True)
@mock.patch("pcs.lib.resource_agent.guess_exactly_one_resource_agent_full_name")
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
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
            "name": "ocf:test:Dummy",
            "shortdesc": "short desc",
            "longdesc": "long desc",
            "parameters": [],
            "actions": [],
        }


    def test_full_name_success(self, mock_guess, mock_metadata):
        mock_metadata.return_value = self.metadata

        self.assertEqual(
            lib.describe_agent(self.lib_env, "ocf:test:Dummy"),
            self.description
        )

        self.assertEqual(len(mock_metadata.mock_calls), 1)
        mock_guess.assert_not_called()


    def test_guess_success(self, mock_guess, mock_metadata):
        mock_metadata.return_value = self.metadata
        mock_guess.return_value = lib_ra.ResourceAgent(
            self.lib_env.cmd_runner(),
            "ocf:test:Dummy"
        )

        self.assertEqual(
            lib.describe_agent(self.lib_env, "dummy"),
            self.description
        )

        self.assertEqual(len(mock_metadata.mock_calls), 1)
        mock_guess.assert_called_once_with("mock_runner", "dummy")


    def test_full_name_fail(self, mock_guess, mock_metadata):
        mock_metadata.return_value = "invalid xml"

        assert_raise_library_error(
            lambda: lib.describe_agent(self.lib_env, "ocf:test:Dummy"),
            (
                severity.ERROR,
                report_codes.UNABLE_TO_GET_AGENT_METADATA,
                {
                    "agent": "ocf:test:Dummy",
                    "reason": "Start tag expected, '<' not found, line 1, column 1",
                }
            )
        )

        self.assertEqual(len(mock_metadata.mock_calls), 1)
        mock_guess.assert_not_called()
