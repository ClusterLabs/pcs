from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import list as ra_list
from pcs.lib.resource_agent.error import (
    AgentNameGuessFoundMoreThanOne,
    AgentNameGuessFoundNone,
)
from pcs.lib.resource_agent.types import (
    ResourceAgentName,
    StandardProviderTuple,
)

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class ListResourceAgentsStandards(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def assert_runner(self):
        self.mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--list-standards"]
        )

    def test_success(self):
        agents = [
            "",
            "service  ",
            "systemd",
            "  nagios  ",
            "ocf",
            "  lsb",
            "  service",
            "",
            "stonith",
            "",
        ]
        # retval is number of standards found
        self.mock_runner.run.return_value = (
            "\n".join(agents) + "\n",
            "",
            len(agents),
        )

        self.assertEqual(
            ra_list.list_resource_agents_standards(self.mock_runner),
            ["lsb", "nagios", "ocf", "service", "stonith", "systemd"],
        )
        self.assert_runner()

    def test_empty(self):
        self.mock_runner.run.return_value = ("", "", 0)
        self.assertEqual(
            ra_list.list_resource_agents_standards(self.mock_runner), []
        )
        self.assert_runner()

    def test_error(self):
        self.mock_runner.run.return_value = ("lsb", "error", 1)
        self.assertEqual(
            ra_list.list_resource_agents_standards(self.mock_runner), ["lsb"]
        )
        self.assert_runner()


class ListResourceAgentsOcfProviders(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def assert_runner(self):
        self.mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--list-ocf-providers"]
        )

    def test_success_filter_whitespace(self):
        providers = [
            "",
            "heartbeat",
            "  pacemaker",
            " openstack",
            "pacemaker ",
            " booth ",
        ]
        # retval is number of providers found
        self.mock_runner.run.return_value = (
            "\n".join(providers) + "\n",
            "",
            len(providers),
        )

        self.assertEqual(
            ra_list.list_resource_agents_ocf_providers(self.mock_runner),
            ["booth", "heartbeat", "openstack", "pacemaker"],
        )
        self.assert_runner()

    def test_empty(self):
        self.mock_runner.run.return_value = ("", "", 0)
        self.assertEqual(
            ra_list.list_resource_agents_ocf_providers(self.mock_runner), []
        )
        self.assert_runner()

    def test_error(self):
        self.mock_runner.run.return_value = ("booth", "error", 1)
        self.assertEqual(
            ra_list.list_resource_agents_ocf_providers(self.mock_runner),
            ["booth"],
        )
        self.assert_runner()


class ListResourceAgentsStandardsAndProviders(TestCase):
    def test_success(self):
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.side_effect = [
            (
                "\n".join(
                    [
                        "nagios ",
                        "ocf",
                        " service",
                        "lsb  ",
                        " ocf",
                        "stonith",
                        "systemd",
                        "",
                    ]
                ),
                "",
                0,
            ),
            (
                "\n".join(
                    [
                        "heartbeat",
                        "openstack",
                        "pacemaker",
                        "booth ",
                        " pacemaker",
                        "",
                    ]
                ),
                "",
                0,
            ),
        ]

        self.assertEqual(
            ra_list.list_resource_agents_standards_and_providers(mock_runner),
            [
                StandardProviderTuple("lsb"),
                StandardProviderTuple("nagios"),
                StandardProviderTuple("ocf", "booth"),
                StandardProviderTuple("ocf", "heartbeat"),
                StandardProviderTuple("ocf", "openstack"),
                StandardProviderTuple("ocf", "pacemaker"),
                StandardProviderTuple("service"),
                StandardProviderTuple("stonith"),
                StandardProviderTuple("systemd"),
            ],
        )

        self.assertEqual(2, len(mock_runner.run.mock_calls))
        mock_runner.run.assert_has_calls(
            [
                mock.call([settings.crm_resource_exec, "--list-standards"]),
                mock.call([settings.crm_resource_exec, "--list-ocf-providers"]),
            ]
        )


class ListResourceAgents(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def assert_runner(self, standard_provider):
        self.mock_runner.run.assert_called_once_with(
            [settings.crm_resource_exec, "--list-agents", standard_provider]
        )

    def test_success_standard(self):
        self.mock_runner.run.return_value = (
            "\n".join(
                [
                    "docker",
                    "Dummy",
                    "dhcpd",
                    "Dummy",
                    "ethmonitor",
                    "",
                ]
            ),
            "",
            0,
        )

        self.assertEqual(
            ra_list.list_resource_agents(
                self.mock_runner, StandardProviderTuple("ocf")
            ),
            [
                "dhcpd",
                "docker",
                "Dummy",
                "ethmonitor",
            ],
        )
        self.assert_runner("ocf")

    def test_success_standard_provider(self):
        self.mock_runner.run.return_value = (
            "\n".join(
                [
                    "ping",
                    "SystemHealth",
                    "SysInfo",
                    "HealthCPU",
                    "Dummy",
                    "",
                ]
            ),
            "",
            0,
        )

        self.assertEqual(
            ra_list.list_resource_agents(
                self.mock_runner, StandardProviderTuple("ocf", "pacemaker")
            ),
            [
                "Dummy",
                "HealthCPU",
                "ping",
                "SysInfo",
                "SystemHealth",
            ],
        )
        self.assert_runner("ocf:pacemaker")

    def test_bad_standard(self):
        self.mock_runner.run.return_value = (
            "",
            "No agents found for standard=nonsense, provider=*",
            1,
        )
        self.assertEqual(
            ra_list.list_resource_agents(
                self.mock_runner, StandardProviderTuple("nonsense")
            ),
            [],
        )
        self.assert_runner("nonsense")

    def test_filter_hidden_agents(self):
        self.mock_runner.run.return_value = (
            "\n".join(
                [
                    "fence_na",
                    "fence_wti",
                    "fence_scsi",
                    "fence_vmware_helper",
                    "fence_nss_wrapper",
                    "fence_node",
                    "fence_vmware_soap",
                    "fence_virt",
                    "fence_pcmk",
                    "fence_sanlockd",
                    "fence_xvm",
                    "fence_ack_manual",
                    "fence_legacy",
                    "fence_check",
                    "fence_tool",
                    "fence_kdump_send",
                    "fence_virtd",
                    "",
                ]
            ),
            "",
            0,
        )

        self.assertEqual(
            ra_list.list_resource_agents(
                self.mock_runner, StandardProviderTuple("stonith")
            ),
            [
                "fence_scsi",
                "fence_virt",
                "fence_vmware_soap",
                "fence_wti",
                "fence_xvm",
            ],
        )
        self.assert_runner("stonith")


class FindOneResourceAgentByType(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _fixture_success_calls(self):
        self.config.runner.pcmk.list_agents_standards(
            "\n".join(["service", "ocf"])
        )
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["Delay", "Dummy"]),
            name="runner.pcmk.list_agents_ocf_providers.heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["Dummy", "Stateful"]),
            name="runner.pcmk.list_agents_ocf_providers.pacemaker",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "service",
            "\n".join(["sshd", "nonvalid:dummy"]),
            name="runner.pcmk.list_agents_ocf_providers.service",
        )

    def test_found_one_agent(self):
        self._fixture_success_calls()
        env = self.env_assist.get_env()
        self.assertEqual(
            ra_list.find_one_resource_agent_by_type(
                env.cmd_runner(), env.report_processor, "delay"
            ),
            ResourceAgentName("ocf", "heartbeat", "Delay"),
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.AGENT_NAME_GUESSED,
                    entered_name="delay",
                    guessed_name="ocf:heartbeat:Delay",
                )
            ]
        )

    def test_found_more_agents(self):
        self._fixture_success_calls()
        env = self.env_assist.get_env()
        with self.assertRaises(AgentNameGuessFoundMoreThanOne) as cm:
            ra_list.find_one_resource_agent_by_type(
                env.cmd_runner(), env.report_processor, "dummy"
            )
        self.assertEqual(cm.exception.agent_name, "dummy")
        self.assertEqual(
            cm.exception.names_found,
            ["ocf:heartbeat:Dummy", "ocf:pacemaker:Dummy"],
        )

    def test_found_no_agents(self):
        self._fixture_success_calls()
        env = self.env_assist.get_env()
        with self.assertRaises(AgentNameGuessFoundNone) as cm:
            ra_list.find_one_resource_agent_by_type(
                env.cmd_runner(), env.report_processor, "missing"
            )
        self.assertEqual(cm.exception.agent_name, "missing")
