from unittest import TestCase

from pcs.lib.cib.resource import agent
from pcs.lib.resource_agent import AgentMetadataDto, AgentActionDto


class GetDefaultOperationInterval(TestCase):
    def test_return_0s_on_name_different_from_monitor(self):
        self.assertEqual("0s", agent.get_default_operation_interval("start"))

    def test_return_60s_on_monitor(self):
        self.assertEqual("60s", agent.get_default_operation_interval("monitor"))


class CompleteOperationsOptions(TestCase):
    def test_add_intervals_everywhere_is_missing(self):
        self.assertEqual(
            agent.complete_operations_options(
                [
                    {"name": "monitor", "interval": "20s"},
                    {"name": "start"},
                ]
            ),
            [
                {"name": "monitor", "interval": "20s"},
                {"name": "start", "interval": "0s"},
            ],
        )


class GetDefaultOperations(TestCase):
    fixture_actions = [
        AgentActionDto("custom1", "40s", None, None, None, None, None, None),
        AgentActionDto("custom2", "60s", "25s", None, None, None, None, None),
        AgentActionDto("meta-data", None, None, None, None, None, None, None),
        AgentActionDto("monitor", "30s", "10s", None, None, None, None, None),
        AgentActionDto("start", None, "40s", None, None, None, None, None),
        AgentActionDto("status", "20s", "15s", None, None, None, None, None),
        AgentActionDto(
            "validate-all", None, None, None, None, None, None, None
        ),
    ]
    fixture_actions_meta_only = [
        AgentActionDto("meta-data", None, None, None, None, None, None, None)
    ]
    maxDiff = None

    @staticmethod
    def fixture_agent(actions):
        return AgentMetadataDto(
            "ocf:pacemaker:Dummy",
            "ocf",
            "pacemaker",
            "Dummy",
            "",
            "",
            [],
            actions,
        )

    @staticmethod
    def fixture_stonith_agent(actions):
        return AgentMetadataDto(
            "fence_test", "stonith", None, "fence_test", "", "", [], actions
        )

    def test_select_only_actions_for_cib(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions)
            ),
            [
                {
                    "automatic": None,
                    "interval": None,
                    "name": "custom1",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "40s",
                },
                {
                    "automatic": None,
                    "interval": "25s",
                    "name": "custom2",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "60s",
                },
                {
                    "automatic": None,
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "30s",
                },
                {
                    "automatic": None,
                    "interval": "40s",
                    "name": "start",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": None,
                },
            ],
        )

    def test_select_only_actions_for_cib_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions)
            ),
            [
                {
                    "automatic": None,
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "30s",
                }
            ],
        )

    def test_select_only_necessary_actions_for_cib(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions), necessary_only=True
            ),
            [
                {
                    "automatic": None,
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "30s",
                }
            ],
        )

    def test_select_only_necessary_actions_for_cib_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions),
                necessary_only=True,
            ),
            [
                {
                    "automatic": None,
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "30s",
                }
            ],
        )

    def test_complete_monitor(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions_meta_only),
                necessary_only=True,
            ),
            [
                {
                    "automatic": None,
                    "interval": None,
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": None,
                }
            ],
        )

    def test_complete_monitor_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions_meta_only),
                necessary_only=True,
            ),
            [
                {
                    "automatic": None,
                    "interval": None,
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "on_target": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": None,
                }
            ],
        )


class ActionToOperation(TestCase):
    def test_remove_depth_with_0(self):
        self.assertEqual(
            agent.action_to_operation(
                {"name": "monitor", "timeout": "20", "depth": "0"}
            ),
            {"name": "monitor", "timeout": "20", "depth": "0"},
        )

    def test_transform_depth_to_ocf_check_level(self):
        self.assertEqual(
            agent.action_to_operation(
                {"name": "monitor", "timeout": "20", "depth": "1"}
            ),
            {"name": "monitor", "timeout": "20", "OCF_CHECK_LEVEL": "1"},
        )
