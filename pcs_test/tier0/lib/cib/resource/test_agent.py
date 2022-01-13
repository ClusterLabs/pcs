from unittest import TestCase

from pcs.common.pacemaker.resource.operations import CibResourceOperationDto
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

    @staticmethod
    def op_fixture(name, interval, timeout):
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
            role=None,
            on_fail=None,
            meta_attributes=[],
            instance_attributes=[],
        )

    def test_select_only_actions_for_cib(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions)
            ),
            [
                self.op_fixture("custom1", "0s", "40s"),
                self.op_fixture("custom2", "25s", "60s"),
                self.op_fixture("monitor", "10s", "30s"),
                self.op_fixture("start", "40s", None),
            ],
        )

    def test_select_only_actions_for_cib_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions)
            ),
            [self.op_fixture("monitor", "10s", "30s")],
        )

    def test_select_only_necessary_actions_for_cib(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions), necessary_only=True
            ),
            [self.op_fixture("monitor", "10s", "30s")],
        )

    def test_select_only_necessary_actions_for_cib_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions),
                necessary_only=True,
            ),
            [self.op_fixture("monitor", "10s", "30s")],
        )

    def test_complete_monitor(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_agent(self.fixture_actions_meta_only),
                necessary_only=True,
            ),
            [self.op_fixture("monitor", "60s", None)],
        )

    def test_complete_monitor_stonith(self):
        self.assertEqual(
            agent.get_default_operations(
                self.fixture_stonith_agent(self.fixture_actions_meta_only),
                necessary_only=True,
            ),
            [self.op_fixture("monitor", "60s", None)],
        )
