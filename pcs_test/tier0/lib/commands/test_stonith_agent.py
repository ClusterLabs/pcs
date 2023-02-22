from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import stonith_agent as lib

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    start_tag_error_text,
)
from pcs_test.tools.command_env import get_env_tools

_fixture_fenced_xml = """
    <?xml version="1.0"?><!DOCTYPE resource-agent SYSTEM "ra-api-1.dtd">
    <resource-agent name="pacemaker-fenced">
        <version>1.0</version>
        <parameters>
            <parameter name="fenced-param">
                <shortdesc>testing fenced parameter</shortdesc>
                <longdesc>with a longdesc</longdesc>
            </parameter>
        </parameters>
    </resource-agent>
"""


def _fixture_parameter(name, shortdesc, longdesc=None):
    return {
        "advanced": False,
        "default": None,
        "deprecated": False,
        "deprecated_by": [],
        "deprecated_desc": None,
        "enum_values": None,
        "longdesc": longdesc,
        "name": name,
        "reloadable": False,
        "required": False,
        "shortdesc": shortdesc,
        "type": "string",
        "unique_group": None,
    }


_fixture_fenced_parsed = [
    _fixture_parameter(
        "fenced-param",
        "testing fenced parameter",
        "testing fenced parameter.\nwith a longdesc",
    )
]


class ListAgents(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.config.runner.pcmk.list_agents_for_standard_and_provider(
            "stonith", "\n".join(["fence_apc", "fence_xvm", "fence_dummy"])
        )

    @staticmethod
    def _fixture_agent_struct(name):
        return {
            "name": f"stonith:{name}",
            "standard": "stonith",
            "provider": None,
            "type": name,
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
                    <parameter name="own-param">
                        <shortdesc>testing own parameter</shortdesc>
                    </parameter>
                </parameters>
                <actions>
                </actions>
            </resource-agent>
            """

    def test_list_all(self):
        self.assertEqual(
            lib.list_agents(self.env_assist.get_env(), False, None),
            [
                self._fixture_agent_struct("fence_apc"),
                self._fixture_agent_struct("fence_dummy"),
                self._fixture_agent_struct("fence_xvm"),
            ],
        )

    def test_search(self):
        self.assertEqual(
            lib.list_agents(self.env_assist.get_env(), False, "M"),
            [
                self._fixture_agent_struct("fence_dummy"),
                self._fixture_agent_struct("fence_xvm"),
            ],
        )

    def test_describe(self):
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_apc",
            stdout=self._fixture_agent_metadata("stonith:fence_apc"),
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.fence_apc",
        )
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout=_fixture_fenced_xml
        )
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_dummy",
            agent_is_missing=True,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.fence_dummy",
        )
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_xvm",
            stdout=self._fixture_agent_metadata("stonith:fence_xvm"),
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.fence_xvm",
        )
        agent_stub = {
            "parameters": [
                _fixture_parameter("own-param", "testing own parameter")
            ]
            + _fixture_fenced_parsed,
            "actions": [],
            "default_actions": [
                {
                    "name": "monitor",
                    "interval": "60s",
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
                    name="stonith:fence_apc",
                    standard="stonith",
                    provider=None,
                    type="fence_apc",
                    shortdesc="short stonith:fence_apc",
                    longdesc="long stonith:fence_apc",
                    **agent_stub,
                ),
                dict(
                    name="stonith:fence_xvm",
                    standard="stonith",
                    provider=None,
                    type="fence_xvm",
                    shortdesc="short stonith:fence_xvm",
                    longdesc="long stonith:fence_xvm",
                    **agent_stub,
                ),
            ],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="stonith:fence_dummy",
                    reason=(
                        "Agent stonith:fence_dummy not found or does not support "
                        "meta-data: Invalid argument (22)\nMetadata query for "
                        "stonith:fence_dummy failed: Input/output error"
                    ),
                )
            ]
        )


class DescribeAgent(TestCase):
    def setUp(self):
        self.maxDiff = None
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_dummy",
            stdout="""
                <resource-agent name="fence_dummy">
                    <shortdesc>short desc</shortdesc>
                    <longdesc>long desc</longdesc>
                    <parameters>
                        <parameter name="own-param">
                            <shortdesc>testing own parameter</shortdesc>
                        </parameter>
                    </parameters>
                    <actions>
                    </actions>
                </resource-agent>
            """,
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
            name="runner.pcmk.load_agent.fence_apc",
        )
        self.config.runner.pcmk.load_fake_agent_metadata(
            stdout=_fixture_fenced_xml
        )

        self.assertEqual(
            lib.describe_agent(self.env_assist.get_env(), "fence_dummy"),
            {
                "name": "stonith:fence_dummy",
                "standard": "stonith",
                "provider": None,
                "type": "fence_dummy",
                "shortdesc": "short desc",
                "longdesc": "long desc",
                "parameters": [
                    _fixture_parameter("own-param", "testing own parameter")
                ]
                + _fixture_fenced_parsed,
                "actions": [],
                "default_actions": [
                    {
                        "name": "monitor",
                        "interval": "60s",
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                        "role": None,
                        "start-delay": None,
                        "timeout": None,
                    }
                ],
            },
        )

    def test_fail(self):
        self.config.runner.pcmk.load_agent(
            agent_name="stonith:fence_dummy",
            stdout="this is not a proper metadata xml",
            env={"PATH": "/usr/sbin:/bin:/usr/bin"},
        )

        assert_raise_library_error(
            lambda: lib.describe_agent(self.env_assist.get_env(), "fence_dummy")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.UNABLE_TO_GET_AGENT_METADATA,
                    agent="stonith:fence_dummy",
                    reason=start_tag_error_text(),
                ),
            ]
        )

    def test_invalid_name(self):
        assert_raise_library_error(
            lambda: lib.describe_agent(
                self.env_assist.get_env(), "stonith:fence_dummy"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_STONITH_AGENT_NAME,
                    name="stonith:fence_dummy",
                )
            ]
        )
