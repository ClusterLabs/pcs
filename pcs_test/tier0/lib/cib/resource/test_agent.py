from unittest import TestCase

from pcs.common.interface.dto import from_dict
from pcs.common.resource_agent_dto import ResourceAgentActionDto
from pcs.lib.cib.resource import agent
from pcs.lib.resource_agent import (
    ResourceAgentAction,
    ResourceAgentMetadata,
    ResourceAgentName,
)
from pcs.lib.resource_agent.const import OCF_1_0


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
        ResourceAgentAction(
            "custom1", "40s", None, None, None, None, False, False
        ),
        ResourceAgentAction(
            "custom2", "60s", "25s", None, None, None, False, False
        ),
        ResourceAgentAction(
            "meta-data", None, None, None, None, None, False, False
        ),
        ResourceAgentAction(
            "monitor", "30s", "10s", None, None, None, False, False
        ),
        ResourceAgentAction(
            "start", None, "40s", None, None, None, False, False
        ),
        ResourceAgentAction(
            "status", "20s", "15s", None, None, None, False, False
        ),
        ResourceAgentAction(
            "validate-all", None, None, None, None, None, False, False
        ),
    ]
    fixture_actions_meta_only = [
        ResourceAgentAction(
            "meta-data", None, None, None, None, None, False, False
        )
    ]
    maxDiff = None

    @staticmethod
    def fixture_agent(actions):
        return ResourceAgentMetadata(
            ResourceAgentName("ocf", "pacemaker", "Dummy"),
            agent_exists=True,
            ocf_version=OCF_1_0,
            shortdesc="",
            longdesc="",
            parameters=[],
            actions=actions,
        )

    @staticmethod
    def fixture_stonith_agent(actions):
        return ResourceAgentMetadata(
            ResourceAgentName("stonith", None, "fence_test"),
            agent_exists=True,
            ocf_version=OCF_1_0,
            shortdesc="",
            longdesc="",
            parameters=[],
            actions=actions,
        )

    def test_select_only_actions_for_cib(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions)
            ),
            [
                {
                    "interval": None,
                    "name": "custom1",
                    "OCF_CHECK_LEVEL": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "40s",
                },
                {
                    "interval": "25s",
                    "name": "custom2",
                    "OCF_CHECK_LEVEL": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "60s",
                },
                {
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": "30s",
                },
                {
                    "interval": "40s",
                    "name": "start",
                    "OCF_CHECK_LEVEL": None,
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
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
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
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
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
                    "interval": "10s",
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
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
                    "interval": None,
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
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
                    "interval": None,
                    "name": "monitor",
                    "OCF_CHECK_LEVEL": None,
                    "role": None,
                    "start-delay": None,
                    "timeout": None,
                }
            ],
        )


class ActionToOperation(TestCase):
    @staticmethod
    def _action_dict(action):
        all_keys = {
            "name": "",
            "timeout": None,
            "interval": None,
            "role": None,
            "start-delay": None,
            "OCF_CHECK_LEVEL": None,
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
            agent.action_to_operation(
                self._action_dto(
                    {"name": "monitor", "timeout": "20", "depth": "0"},
                )
            ),
            self._action_dict({"name": "monitor", "timeout": "20"}),
        )

    def test_transform_depth_to_ocf_check_level(self):
        self.assertEqual(
            agent.action_to_operation(
                self._action_dto(
                    {"name": "monitor", "timeout": "20", "depth": "1"},
                )
            ),
            self._action_dict(
                {"name": "monitor", "timeout": "20", "OCF_CHECK_LEVEL": "1"}
            ),
        )

    def test_remove_attributes_not_allowed_in_cib(self):
        self.assertEqual(
            agent.action_to_operation(
                self._action_dto(
                    {
                        "name": "monitor",
                        "on_target": True,
                        "automatic": False,
                    },
                )
            ),
            self._action_dict({"name": "monitor"}),
        )
