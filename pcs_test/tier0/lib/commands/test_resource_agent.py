# coding=utf-8
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.reports import codes as report_codes

from pcs.lib.commands import resource_agent as lib
from pcs.lib.resource_agent import ResourceAgentName


class ListStandards(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        standards = ["service", "lsb", "ocf", "systemd", "lsb", "nagios"]
        self.config.runner.pcmk.list_agents_standards("\n".join(standards))
        self.assertEqual(
            lib.list_standards(self.env_assist.get_env()),
            sorted(set(standards)),
        )


class ListOcfProviders(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        providers = ["pacemaker", "booth", "openstack", "booth", "heartbeat"]
        self.config.runner.pcmk.list_agents_ocf_providers("\n".join(providers))
        self.assertEqual(
            lib.list_ocf_providers(self.env_assist.get_env()),
            sorted(set(providers)),
        )


class ListAgentsForStandardAndProvider(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def _assert_standard_provider_specified(self, standard):
        agents = ["Delay", "Stateful", "Delay", "Dummy"]
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker", "\n".join(agents)
        )
        self.assertEqual(
            lib.list_agents_for_standard_and_provider(
                self.env_assist.get_env(), standard
            ),
            sorted(set(agents)),
        )

    def test_standard_provider_specified_1(self):
        self._assert_standard_provider_specified("ocf:pacemaker")

    def test_standard_provider_specified_2(self):
        self._assert_standard_provider_specified("ocf:pacemaker:")

    def test_standard_provider_not_specified(self):
        agents_pacemaker = ["Delay", "Dummy", "Stateful"]
        agents_heartbeat = ["Delay"]
        agents_service = ["corosync", "pacemaker", "pcsd"]
        self.config.runner.pcmk.list_agents_standards(
            "\n".join(["service", "stonith", "ocf"])
        )
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(agents_heartbeat),
            name="runner.pcmk.list_agents_ocf_providers.heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(agents_pacemaker),
            name="runner.pcmk.list_agents_ocf_providers.pacemaker",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "service",
            "\n".join(agents_service),
            name="runner.pcmk.list_agents_ocf_providers.service",
        )
        self.assertEqual(
            lib.list_agents_for_standard_and_provider(
                self.env_assist.get_env()
            ),
            sorted(
                agents_pacemaker + agents_heartbeat + agents_service,
                key=str.lower,
            ),
        )


class ListAgents(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.env_assist, self.config = get_env_tools(test_case=self)

        self.config.runner.pcmk.list_agents_standards(
            "\n".join(["service", "ocf"])
        )
        self.config.runner.pcmk.list_agents_ocf_providers("\n".join(["test"]))
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:test",
            "\n".join(["Stateful", "Delay"]),
            name="runner.pcmk.list_agents_ocf_providers.ocf_test",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "service",
            "\n".join(["corosync", "pacemaker_remote"]),
            name="runner.pcmk.list_agents_ocf_providers.service",
        )

    @staticmethod
    def _fixture_agent_struct(name):
        return {
            "name": name.full_name,
            "standard": name.standard,
            "provider": name.provider,
            "type": name.type,
            "shortdesc": None,
            "longdesc": None,
            "parameters": [],
            "actions": [],
            "default_actions": [],
        }

    @staticmethod
    def _fixture_agent_metadata(name):
        return f"""
            <resource-agent name="{name}">
                <shortdesc>short {name}</shortdesc>
                <longdesc>long {name}</longdesc>
                <parameters>
                </parameters>
                <actions>
                </actions>
            </resource-agent>
            """

    def test_list_all(self):
        self.assertEqual(
            lib.list_agents(self.env_assist.get_env(), False, None),
            [
                self._fixture_agent_struct(
                    ResourceAgentName("ocf", "test", "Delay")
                ),
                self._fixture_agent_struct(
                    ResourceAgentName("ocf", "test", "Stateful")
                ),
                self._fixture_agent_struct(
                    ResourceAgentName("service", None, "corosync")
                ),
                self._fixture_agent_struct(
                    ResourceAgentName("service", None, "pacemaker_remote")
                ),
            ],
        )

    def test_search(self):
        self.assertEqual(
            lib.list_agents(self.env_assist.get_env(), False, "te"),
            [
                self._fixture_agent_struct(
                    ResourceAgentName("ocf", "test", "Delay")
                ),
                self._fixture_agent_struct(
                    ResourceAgentName("ocf", "test", "Stateful")
                ),
                self._fixture_agent_struct(
                    ResourceAgentName("service", None, "pacemaker_remote")
                ),
            ],
        )

    def test_describe(self):
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:test:Delay",
            stdout=self._fixture_agent_metadata("ocf:test:Delay"),
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.delay",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="ocf:test:Stateful",
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.stateful",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="service:corosync",
            stdout=self._fixture_agent_metadata("service:corosync"),
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.corosync",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="service:pacemaker_remote",
            stdout=self._fixture_agent_metadata("service:pacemaker_remote"),
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.pacemaker_remote",
        )

        agent_stub = {
            "parameters": [],
            "actions": [],
            "default_actions": [
                {
                    "interval": "60s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "automatic": False,
                    "on_target": False,
                    "role": None,
                    "start-delay": None,
                    "timeout": None,
                }
            ],
        }
        self.assertEqual(
            lib.list_agents(self.env_assist.get_env(), True, None),
            [
                dict(
                    name="ocf:test:Delay",
                    standard="ocf",
                    provider="test",
                    type="Delay",
                    shortdesc="short ocf:test:Delay",
                    longdesc="long ocf:test:Delay",
                    **agent_stub,
                ),
                dict(
                    name="service:corosync",
                    standard="service",
                    provider=None,
                    type="corosync",
                    shortdesc="short service:corosync",
                    longdesc="long service:corosync",
                    **agent_stub,
                ),
                dict(
                    name="service:pacemaker_remote",
                    standard="service",
                    provider=None,
                    type="pacemaker_remote",
                    shortdesc="short service:pacemaker_remote",
                    longdesc="long service:pacemaker_remote",
                    **agent_stub,
                ),
            ],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="ocf:test:Stateful",
                    reason=(
                        "Agent ocf:test:Stateful not found or does not support "
                        "meta-data: Invalid argument (22)\nMetadata query for "
                        "ocf:test:Stateful failed: Input/output error"
                    ),
                )
            ]
        )


class DescribeAgent(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.env_assist, self.config = get_env_tools(test_case=self)

        self.trace_parameters = [
            {
                "advanced": True,
                "default": "0",
                "deprecated": False,
                "deprecated_by": [],
                "deprecated_desc": None,
                "enum_values": None,
                "longdesc": "Set to 1 to turn on resource agent tracing"
                " (expect large output) The trace output will be "
                "saved to trace_file, if set, or by default to "
                "$HA_VARRUN/ra_trace/<type>/<id>.<action>."
                "<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/db."
                "start.2012-11-27.08:37:08",
                "name": "trace_ra",
                "required": False,
                "shortdesc": "Set to 1 to turn on resource agent "
                "tracing (expect large output)",
                "type": "integer",
                "unique_group": None,
                "reloadable": False,
            },
            {
                "advanced": True,
                "default": "",
                "deprecated": False,
                "deprecated_by": [],
                "deprecated_desc": None,
                "enum_values": None,
                "longdesc": (
                    "Path to a file to store resource agent tracing log"
                ),
                "name": "trace_file",
                "required": False,
                "shortdesc": (
                    "Path to a file to store resource agent tracing log"
                ),
                "type": "string",
                "unique_group": None,
                "reloadable": False,
            },
        ]

    def test_full_name_and_utf8_success(self):
        full_name = "ocf:heartbeat:Dummy"
        self.config.runner.pcmk.load_agent(
            agent_filename="resource_agent_ocf_heartbeat_dummy_utf8.xml",
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.assertEqual(
            lib.describe_agent(self.env_assist.get_env(), full_name),
            {
                "name": full_name,
                "standard": "ocf",
                "provider": "heartbeat",
                "type": "Dummy",
                "shortdesc": "Example stateless resource agent: ®",
                "longdesc": "This is a Dummy Resource Agent for testing utf-8"
                " in metadata: ®",
                "parameters": [
                    {
                        "advanced": False,
                        "default": "/var/run/resource-agents/Dummy-®.state",
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "enum_values": None,
                        "longdesc": (
                            "Location to store the resource state in: ®"
                        ),
                        "name": "state-®",
                        "required": False,
                        "shortdesc": "State file: ®",
                        "type": "string",
                        "unique_group": "_pcs_unique_group_state-®",
                        "reloadable": True,
                    },
                ]
                + self.trace_parameters,
                "actions": [
                    {
                        "name": "start",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "stop",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "monitor",
                        "interval": "10",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "meta-data",
                        "timeout": "5",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "validate-all",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "custom-®",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                ],
                "default_actions": [
                    {
                        "name": "start",
                        "interval": "0s",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "stop",
                        "interval": "0s",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "monitor",
                        "interval": "10",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                    {
                        "name": "custom-®",
                        "interval": "0s",
                        "timeout": "20",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                    },
                ],
            },
        )

    def test_guess_success(self):
        self.config.runner.pcmk.list_agents_standards(
            "\n".join(["service", "ocf"])
        )
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers.heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["agent1"]),
            name="runner.pcmk.list_agents_ocf_providers.pacemaker",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "service",
            "\n".join(["agent1"]),
            name="runner.pcmk.list_agents_ocf_providers.service",
        )
        self.config.runner.pcmk.load_agent(
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.assertEqual(
            lib.describe_agent(self.env_assist.get_env(), "dummy"),
            {
                "name": "ocf:heartbeat:Dummy",
                "standard": "ocf",
                "provider": "heartbeat",
                "type": "Dummy",
                "shortdesc": "Example stateless resource agent",
                "longdesc": (
                    "This is a Dummy Resource Agent. It does absolutely nothing "
                    "except \nkeep track of whether its running or not.\nIts "
                    "purpose in life is for testing and to serve as a template "
                    "for RA writers.\n\nNB: Please pay attention to the timeouts "
                    "specified in the actions\nsection below. They should be "
                    "meaningful for the kind of resource\nthe agent manages. "
                    "They should be the minimum advised timeouts,\nbut they "
                    "shouldn't/cannot cover _all_ possible resource\ninstances. "
                    "So, try to be neither overly generous nor too stingy,\nbut "
                    "moderate. The minimum timeouts should never be below 10 seconds."
                ),
                "parameters": [
                    {
                        "name": "state",
                        "shortdesc": "State file",
                        "longdesc": "Location to store the resource state in.",
                        "type": "string",
                        "default": "/var/run/resource-agents/Dummy-undef.state",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": "_pcs_unique_group_state",
                        "reloadable": True,
                    },
                    {
                        "name": "fake",
                        "shortdesc": (
                            "Fake attribute that can be changed to cause a reload"
                        ),
                        "longdesc": (
                            "Fake attribute that can be changed to cause a reload"
                        ),
                        "type": "string",
                        "default": "dummy",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                ]
                + self.trace_parameters,
                "actions": [
                    {
                        "name": "start",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "stop",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "monitor",
                        "timeout": "20",
                        "interval": "10",
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "reload",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "migrate_to",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "migrate_from",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "meta-data",
                        "timeout": "5",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                    {
                        "name": "validate-all",
                        "timeout": "20",
                        "automatic": False,
                        "interval": None,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                    },
                ],
                "default_actions": [
                    {
                        "name": "start",
                        "timeout": "20",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "stop",
                        "timeout": "20",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "monitor",
                        "timeout": "20",
                        "interval": "10",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "reload",
                        "timeout": "20",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_to",
                        "timeout": "20",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "migrate_from",
                        "timeout": "20",
                        "interval": "0s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                ],
            },
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.AGENT_NAME_GUESSED,
                    entered_name="dummy",
                    guessed_name="ocf:heartbeat:Dummy",
                )
            ]
        )

    def test_agent_ambiguos(self):
        self.config.runner.pcmk.list_agents_standards("\n".join(["ocf"]))
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat", "pacemaker"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_heartbeat",
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:pacemaker",
            "\n".join(["agent1", "Dummy", "agent2"]),
            name="runner.pcmk.list_agents_ocf_providers_pacemaker",
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.describe_agent(self.env_assist.get_env(), "dummy")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.AGENT_NAME_GUESS_FOUND_MORE_THAN_ONE,
                    agent="dummy",
                    possible_agents=[
                        "ocf:heartbeat:Dummy",
                        "ocf:pacemaker:Dummy",
                    ],
                )
            ],
        )

    def test_agent_not_found(self):
        self.config.runner.pcmk.list_agents_standards("\n".join(["ocf"]))
        self.config.runner.pcmk.list_agents_ocf_providers(
            "\n".join(["heartbeat"])
        )
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "ocf:heartbeat", "\n".join(["Dummy"])
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.describe_agent(self.env_assist.get_env(), "agent")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.AGENT_NAME_GUESS_FOUND_NONE,
                    agent="agent",
                )
            ],
        )

    def test_metadata_load_error(self):
        self.config.runner.pcmk.load_agent(
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.describe_agent(
                self.env_assist.get_env(), "ocf:heartbeat:Dummy"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="ocf:heartbeat:Dummy",
                    reason=(
                        "Agent ocf:heartbeat:Dummy not found or does not support "
                        "meta-data: Invalid argument (22)\nMetadata query for "
                        "ocf:heartbeat:Dummy failed: Input/output error"
                    ),
                )
            ],
        )

    def test_invalid_name(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.describe_agent(
                self.env_assist.get_env(), "ocf:heartbeat:Something:else"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_RESOURCE_AGENT_NAME,
                    name="ocf:heartbeat:Something:else",
                )
            ],
        )
