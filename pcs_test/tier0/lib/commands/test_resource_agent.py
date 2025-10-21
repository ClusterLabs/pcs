# coding=utf-8
from unittest import TestCase

from pcs.common import const
from pcs.common.interface.dto import from_dict
from pcs.common.pacemaker.resource.operations import (
    CibResourceOperationDto,
    ListCibResourceOperationDto,
)
from pcs.common.reports import codes as report_codes
from pcs.common.resource_agent.dto import (
    ListResourceAgentNameDto,
    ResourceAgentActionDto,
    ResourceAgentMetadataDto,
    ResourceAgentNameDto,
    ResourceAgentParameterDto,
)
from pcs.lib.commands import resource_agent as lib
from pcs.lib.resource_agent import ResourceAgentName
from pcs.lib.resource_agent import const as ra_const

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.metadata_dto import get_fixture_meta_attributes_dto


def _operation_fixture(name, interval="", role=None, timeout=None):
    return CibResourceOperationDto(
        id="",
        name=name,
        interval=interval,
        description=None,
        start_delay=None,
        interval_origin=None,
        timeout=timeout,
        enabled=None,
        record_pending=None,
        role=role,
        on_fail=None,
        meta_attributes=[],
        instance_attributes=[],
    )


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


class ActionToOperation(TestCase):
    # pylint: disable=protected-access
    @staticmethod
    def _action_dict(action):
        all_keys = {
            "name": "",
            "timeout": None,
            "interval": None,
            "role": None,
            "start-delay": None,
            "OCF_CHECK_LEVEL": None,
            "automatic": False,
            "on_target": False,
        }
        all_keys.update(action)
        return all_keys

    @staticmethod
    def _action_dto(action):
        all_keys = {
            "name": "",
            "timeout": None,
            "interval": None,
            "role": None,
            "start-delay": None,
            "depth": None,
            "automatic": False,
            "on_target": False,
        }
        all_keys.update(action)
        return from_dict(ResourceAgentActionDto, all_keys)

    def test_remove_depth_with_0(self):
        self.assertEqual(
            lib._action_to_operation(
                self._action_dto(
                    {"name": "monitor", "timeout": "20", "depth": "0"},
                )
            ),
            self._action_dict({"name": "monitor", "timeout": "20"}),
        )

    def test_transform_depth_to_ocf_check_level(self):
        self.assertEqual(
            lib._action_to_operation(
                self._action_dto(
                    {"name": "monitor", "timeout": "20", "depth": "1"},
                )
            ),
            self._action_dict(
                {"name": "monitor", "timeout": "20", "OCF_CHECK_LEVEL": "1"}
            ),
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

    def test_agent_ambiguous(self):
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


class GetAgentMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        standard = "ocf"
        provider = "heartbeat"
        agent_type = "Dummy"
        self.name = ResourceAgentName(standard, provider, agent_type)
        self.agent_metadata = ResourceAgentMetadataDto(
            name=ResourceAgentNameDto(
                standard=standard,
                provider=provider,
                type=agent_type,
            ),
            shortdesc="Example stateless resource agent: ®",
            longdesc=(
                "This is a Dummy Resource Agent for testing utf-8"
                " in metadata: ®"
            ),
            parameters=[
                ResourceAgentParameterDto(
                    name="state-®",
                    shortdesc="State file: ®",
                    longdesc="Location to store the resource state in: ®",
                    type="string",
                    default="/var/run/resource-agents/Dummy-®.state",
                    enum_values=None,
                    required=False,
                    advanced=False,
                    deprecated=False,
                    deprecated_by=[],
                    deprecated_desc=None,
                    unique_group="_pcs_unique_group_state-®",
                    reloadable=True,
                ),
                ResourceAgentParameterDto(
                    name="trace_ra",
                    shortdesc=(
                        "Set to 1 to turn on resource agent "
                        "tracing (expect large output)"
                    ),
                    longdesc=(
                        "Set to 1 to turn on resource agent tracing"
                        " (expect large output) The trace output will be "
                        "saved to trace_file, if set, or by default to "
                        "$HA_VARRUN/ra_trace/<type>/<id>.<action>."
                        "<timestamp> e.g. $HA_VARRUN/ra_trace/oracle/db."
                        "start.2012-11-27.08:37:08"
                    ),
                    type="integer",
                    default="0",
                    enum_values=None,
                    required=False,
                    advanced=True,
                    deprecated=False,
                    deprecated_by=[],
                    deprecated_desc=None,
                    unique_group=None,
                    reloadable=False,
                ),
                ResourceAgentParameterDto(
                    name="trace_file",
                    shortdesc="Path to a file to store resource agent tracing log",
                    longdesc="Path to a file to store resource agent tracing log",
                    type="string",
                    default="",
                    enum_values=None,
                    required=False,
                    advanced=True,
                    deprecated=False,
                    deprecated_by=[],
                    deprecated_desc=None,
                    unique_group=None,
                    reloadable=False,
                ),
            ],
            actions=[
                ResourceAgentActionDto(
                    name="start",
                    timeout="20",
                    interval=None,
                    role=None,
                    start_delay=None,
                    depth=None,
                    automatic=False,
                    on_target=False,
                ),
                ResourceAgentActionDto(
                    name="stop",
                    timeout="20",
                    interval=None,
                    role=None,
                    start_delay=None,
                    depth=None,
                    automatic=False,
                    on_target=False,
                ),
                ResourceAgentActionDto(
                    name="monitor",
                    timeout="20",
                    interval="10",
                    role=None,
                    start_delay=None,
                    depth="0",
                    automatic=False,
                    on_target=False,
                ),
                ResourceAgentActionDto(
                    name="meta-data",
                    timeout="5",
                    interval=None,
                    role=None,
                    start_delay=None,
                    depth=None,
                    automatic=False,
                    on_target=False,
                ),
                ResourceAgentActionDto(
                    name="validate-all",
                    timeout="20",
                    interval=None,
                    role=None,
                    start_delay=None,
                    depth=None,
                    automatic=False,
                    on_target=False,
                ),
                ResourceAgentActionDto(
                    name="custom-®",
                    timeout="20",
                    interval=None,
                    role=None,
                    start_delay=None,
                    depth=None,
                    automatic=False,
                    on_target=False,
                ),
            ],
        )

    def test_full_name(self):
        self.config.runner.pcmk.load_agent(
            agent_name=self.name.full_name,
            agent_filename="resource_agent_ocf_heartbeat_dummy_utf8.xml",
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.assertEqual(
            lib.get_agent_metadata(self.env_assist.get_env(), self.name),
            self.agent_metadata,
        )

    def test_agent_not_found(self):
        err_msg = "error message"
        self.config.runner.pcmk.load_agent(
            agent_name=self.name.full_name,
            agent_is_missing=True,
            stderr=err_msg,
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_agent_metadata(self.env_assist.get_env(), self.name)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent=self.name.full_name,
                    reason=err_msg,
                )
            ],
        )

    def test_metadata_load_error(self):
        self.config.runner.pcmk.load_agent(
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_agent_metadata(self.env_assist.get_env(), self.name)
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent=self.name.full_name,
                    reason=(
                        f"Agent {self.name.full_name} not found or does not "
                        "support meta-data: Invalid argument (22)\nMetadata "
                        f"query for {self.name.full_name} failed: Input/output "
                        "error"
                    ),
                )
            ],
        )


class GetAgentsList(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
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
        self.assertEqual(
            lib.get_agents_list(self.env_assist.get_env()),
            ListResourceAgentNameDto(
                names=[
                    ResourceAgentNameDto(
                        standard="ocf",
                        provider="test",
                        type="Delay",
                    ),
                    ResourceAgentNameDto(
                        standard="ocf",
                        provider="test",
                        type="Stateful",
                    ),
                    ResourceAgentNameDto(
                        standard="service",
                        provider=None,
                        type="corosync",
                    ),
                    ResourceAgentNameDto(
                        standard="service",
                        provider=None,
                        type="pacemaker_remote",
                    ),
                ]
            ),
        )


class GetAgentDefaultOperations(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_resource(self):
        agent_name = ResourceAgentName("ocf", "pacemaker", "Stateful")
        self.config.runner.pcmk.load_agent(
            agent_name=agent_name.full_name,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.assertEqual(
            lib.get_agent_default_operations(
                self.env_assist.get_env(), agent_name.to_dto()
            ),
            ListCibResourceOperationDto(
                operations=[
                    _operation_fixture("start", "0s", timeout="20s"),
                    _operation_fixture("stop", "0s", timeout="20s"),
                    _operation_fixture(
                        "monitor",
                        "10s",
                        timeout="20s",
                        role=const.PCMK_ROLE_PROMOTED,
                    ),
                    _operation_fixture(
                        "monitor",
                        "11s",
                        timeout="20s",
                        role=const.PCMK_ROLE_UNPROMOTED,
                    ),
                    _operation_fixture("promote", "0s", timeout="10s"),
                    _operation_fixture("demote", "0s", timeout="10s"),
                    _operation_fixture("notify", "0s", timeout="5s"),
                    _operation_fixture("reload-agent", "0s", timeout="10s"),
                ]
            ),
        )

    def test_resource_only_necessary(self):
        agent_name = ResourceAgentName("ocf", "pacemaker", "Stateful")
        self.config.runner.pcmk.load_agent(
            agent_name=agent_name.full_name,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.assertEqual(
            lib.get_agent_default_operations(
                self.env_assist.get_env(),
                agent_name.to_dto(),
                necessary_only=True,
            ),
            ListCibResourceOperationDto(
                operations=[
                    _operation_fixture(
                        "monitor",
                        "10s",
                        timeout="20s",
                        role=const.PCMK_ROLE_PROMOTED,
                    ),
                    _operation_fixture(
                        "monitor",
                        "11s",
                        timeout="20s",
                        role=const.PCMK_ROLE_UNPROMOTED,
                    ),
                ]
            ),
        )

    def _test_stonith(self, necessary_only):
        agent_name = ResourceAgentName("stonith", None, "fence_unfencing")
        self.config.runner.pcmk.load_agent(
            agent_name=agent_name.full_name,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )
        self.config.runner.pcmk.load_fake_agent_metadata()
        self.assertEqual(
            lib.get_agent_default_operations(
                self.env_assist.get_env(),
                agent_name.to_dto(),
                necessary_only=necessary_only,
            ),
            ListCibResourceOperationDto(
                operations=[
                    _operation_fixture("monitor", interval="60s"),
                ]
            ),
        )

    def test_stonith(self):
        self._test_stonith(False)

    def test_stonith_only_necessary(self):
        self._test_stonith(True)


class GetMetaAttributesMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.maxDiff = None

    def _test_success(self, resource_type):
        self.config.runner.pcmk.load_crm_resource_metadata()
        self.assertEqual(
            lib.get_meta_attributes_metadata(
                self.env_assist.get_env(), resource_type
            ).parameters,
            get_fixture_meta_attributes_dto(
                agent_name=resource_type
            ).parameters,
        )

    def test_success_primitive_meta(self):
        self._test_success(resource_type=ra_const.PRIMITIVE_META)

    def test_success_stonith_meta(self):
        self._test_success(resource_type=ra_const.STONITH_META)

    def test_metadata_load_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_meta_attributes_metadata(
                self.env_assist.get_env(), "unknown"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="unknown",
                    reason="Unknown agent",
                )
            ]
        )
