import logging
from contextlib import contextmanager
from functools import partial
from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import reports
from pcs.common.pacemaker.node import CibNodeDto, CibNodeListDto
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.common.types import CibRuleInEffectStatus
from pcs.lib.cib.tools import IdProvider
from pcs.lib.commands import node as lib
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import (
    MockLibraryReportProcessor,
    RuleInEffectEvalMock,
)
from pcs_test.tools.misc import create_patcher
from pcs_test.tools.nodes_dto import FIXTURE_NODES_CONFIG_XML, get_nodes_dto

mocked_cib = etree.fromstring("<cib />")

patch_env = partial(mock.patch.object, LibraryEnvironment)
patch_command = create_patcher("pcs.lib.commands.node")

create_env = partial(
    LibraryEnvironment,
    mock.MagicMock(logging.Logger),
    MockLibraryReportProcessor(),
)


def fixture_node(order_num):
    node = mock.MagicMock(attrs=mock.MagicMock())
    node.attrs.name = "node-{0}".format(order_num)
    return node


class StandbyMaintenancePassParameters(TestCase):
    def setUp(self):
        self.lib_env = "lib_env"
        self.nodes = "nodes"
        self.wait = "wait"
        self.standby_on = {"standby": "on"}
        self.standby_off = {"standby": ""}
        self.maintenance_on = {"maintenance": "on"}
        self.maintenance_off = {"maintenance": ""}


@patch_command("_set_instance_attrs_local_node")
class StandbyMaintenancePassParametersLocal(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_local(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_on, self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_local(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_off, self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_local(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_on, self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_local(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_off, self.wait
        )


@patch_command("_set_instance_attrs_node_list")
class StandbyMaintenancePassParametersList(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_list(self.lib_env, True, self.nodes, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_on, self.nodes, self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_list(self.lib_env, False, self.nodes, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_off, self.nodes, self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_list(
            self.lib_env, True, self.nodes, self.wait
        )
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_on, self.nodes, self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_list(
            self.lib_env, False, self.nodes, self.wait
        )
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_off, self.nodes, self.wait
        )


@patch_command("_set_instance_attrs_all_nodes")
class StandbyMaintenancePassParametersAll(StandbyMaintenancePassParameters):
    def test_standby(self, mock_doer):
        lib.standby_unstandby_all(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_on, self.wait
        )

    def test_unstandby(self, mock_doer):
        lib.standby_unstandby_all(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.standby_off, self.wait
        )

    def test_maintenance(self, mock_doer):
        lib.maintenance_unmaintenance_all(self.lib_env, True, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_on, self.wait
        )

    def test_unmaintenance(self, mock_doer):
        lib.maintenance_unmaintenance_all(self.lib_env, False, self.wait)
        mock_doer.assert_called_once_with(
            self.lib_env, self.maintenance_off, self.wait
        )


class SetInstanceAttrsBase(TestCase):
    node_count = 2

    def setUp(self):
        self.cluster_nodes = [fixture_node(i) for i in range(self.node_count)]
        self.cib = etree.fromstring("<cib />")

        self.launch = {"pre": False, "post": False}

        @contextmanager
        def cib_runner_nodes_contextmanager(env, wait):
            del env, wait
            self.launch["pre"] = True
            yield (self.cib, "mock_runner", self.cluster_nodes)
            self.launch["post"] = True

        patcher = patch_command("cib_runner_nodes")
        self.addCleanup(patcher.stop)
        patcher.start().side_effect = cib_runner_nodes_contextmanager

    def assert_context_manager_launched(self, pre=False, post=False):
        self.assertEqual(self.launch, {"pre": pre, "post": post})

    def assert_call_with_provider(self, call, cib, node, attrs, nodes):
        self.assertEqual(call[0][0], cib)
        self.assertTrue(isinstance(call[0][1], IdProvider))
        self.assertEqual(call[0][2], node)
        self.assertEqual(call[0][3], attrs)
        self.assertEqual(call[1]["state_nodes"], nodes)


@patch_command("update_node_instance_attrs")
@patch_command("get_local_node_name")
class SetInstanceAttrsLocal(SetInstanceAttrsBase):
    # pylint: disable=protected-access
    node_count = 2

    def test_not_possible_with_cib_file(self, mock_name, mock_attrs):
        assert_raise_library_error(
            lambda: lib._set_instance_attrs_local_node(
                create_env(cib_data="<cib />"), "attrs", "wait"
            ),
            (
                severity.ERROR,
                report_codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE,
                {},
            ),
        )
        self.assert_context_manager_launched(pre=False, post=False)
        mock_name.assert_not_called()
        mock_attrs.assert_not_called()

    def test_success(self, mock_name, mock_attrs):
        mock_name.return_value = "node-1"

        lib._set_instance_attrs_local_node(create_env(), "attrs", False)

        self.assert_context_manager_launched(pre=True, post=True)
        mock_name.assert_called_once_with("mock_runner")
        mock_attrs_calls = mock_attrs.call_args_list
        self.assertEqual(len(mock_attrs_calls), 1)
        self.assert_call_with_provider(
            mock_attrs_calls[0], self.cib, "node-1", "attrs", self.cluster_nodes
        )


@patch_command("update_node_instance_attrs")
class SetInstanceAttrsAll(SetInstanceAttrsBase):
    # pylint: disable=protected-access
    node_count = 2

    def test_success(self, mock_attrs):
        lib._set_instance_attrs_all_nodes(create_env(), "attrs", False)

        mock_attrs_calls = mock_attrs.call_args_list
        self.assertEqual(2, len(mock_attrs_calls))
        self.assert_call_with_provider(
            mock_attrs_calls[0], self.cib, "node-0", "attrs", self.cluster_nodes
        )
        self.assert_call_with_provider(
            mock_attrs_calls[1], self.cib, "node-1", "attrs", self.cluster_nodes
        )


@patch_command("update_node_instance_attrs")
class SetInstanceAttrsList(SetInstanceAttrsBase):
    # pylint: disable=protected-access
    node_count = 4

    def test_success(self, mock_attrs):
        lib._set_instance_attrs_node_list(
            create_env(), "attrs", ["node-1", "node-2"], False
        )

        self.assert_context_manager_launched(pre=True, post=True)
        mock_attrs_calls = mock_attrs.call_args_list
        self.assertEqual(2, len(mock_attrs_calls))
        self.assert_call_with_provider(
            mock_attrs_calls[0], self.cib, "node-1", "attrs", self.cluster_nodes
        )
        self.assert_call_with_provider(
            mock_attrs_calls[1], self.cib, "node-2", "attrs", self.cluster_nodes
        )

    def test_bad_node(self, mock_attrs):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib._set_instance_attrs_node_list(
                create_env(), "attrs", ["node-1", "node-9"], False
            ),
            (
                severity.ERROR,
                report_codes.NODE_NOT_FOUND,
                {
                    "node": "node-9",
                    "searched_types": [],
                },
            ),
        )
        mock_attrs.assert_not_called()


@patch_env("push_cib")
class CibRunnerNodes(TestCase):
    def setUp(self):
        self.env = create_env()

    @patch_env("get_cib", lambda self: "mocked cib")
    @patch_env("cmd_runner", lambda self: "mocked cmd_runner")
    @patch_env("ensure_wait_satisfiable")
    @patch_command("ClusterState")
    @patch_env("get_cluster_state")
    def test_wire_together_all_expected_dependencies(
        self,
        get_cluster_state,
        cluster_state,
        ensure_wait_satisfiable,
        push_cib,
    ):
        cluster_state.return_value = mock.MagicMock(
            node_section=mock.MagicMock(nodes="nodes")
        )
        get_cluster_state.return_value = "mock get_cluster_state"
        wait = 10
        ensure_wait_satisfiable.return_value = wait

        with lib.cib_runner_nodes(self.env, wait) as (cib, runner, nodes):
            self.assertEqual(cib, "mocked cib")
            self.assertEqual(runner, "mocked cmd_runner")
            self.assertEqual(nodes, "nodes")
            ensure_wait_satisfiable.assert_called_once_with(wait)
            get_cluster_state.assert_called_once_with()
            cluster_state.assert_called_once_with("mock get_cluster_state")

        push_cib.assert_called_once_with(wait_timeout=wait)

    @patch_env("ensure_wait_satisfiable", mock.Mock(side_effect=LibraryError))
    def test_raises_when_wait_is_not_satisfiable(self, push_cib):
        def run():
            # pylint: disable=unused-variable
            with lib.cib_runner_nodes(self.env, "wait") as (cib, runner, nodes):
                pass

        self.assertRaises(LibraryError, run)
        push_cib.assert_not_called()


class GetConfigDto(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def command(self, evaluate_expired=False):
        return lib.get_config_dto(
            self.env_assist.get_env(),
            evaluate_expired=evaluate_expired,
        )

    def test_no_node_config(self):
        self.config.runner.cib.load()
        self.assertEqual(self.command(), CibNodeListDto(nodes=[]))

    def test_nodes_without_attributes(self):
        self.config.runner.cib.load(filename="cib-empty-withnodes.xml")
        self.assertEqual(
            self.command(),
            CibNodeListDto(
                nodes=[
                    CibNodeDto(
                        id="1",
                        uname="rh7-1",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[],
                        utilization=[],
                    ),
                    CibNodeDto(
                        id="2",
                        uname="rh7-2",
                        description=None,
                        score=None,
                        type=None,
                        instance_attributes=[],
                        utilization=[],
                    ),
                ]
            ),
        )

    @mock.patch("pcs.lib.cib.rule.in_effect.has_rule_in_effect_status_tool")
    def test_nodes_config_without_rule_evaluation(self, mock_has_rule_tool):
        mock_has_rule_tool.side_effect = AssertionError(
            "has_rule_in_effect_status_tool should not be called"
        )
        self.config.runner.cib.load(nodes=FIXTURE_NODES_CONFIG_XML)
        self.assertEqual(
            self.command(),
            get_nodes_dto(RuleInEffectEvalMock({})),
        )

    @mock.patch("pcs.lib.commands.node.get_rule_evaluator")
    def test_nodes_config_with_rule_evaluation(self, mock_get_rule_evaluator):
        self.config.runner.cib.load(nodes=FIXTURE_NODES_CONFIG_XML)
        rule_evaluator = RuleInEffectEvalMock(
            {
                "nodes-1-rule": CibRuleInEffectStatus.EXPIRED,
                "nodes-1-2-rule": CibRuleInEffectStatus.IN_EFFECT,
                "nodes-2-utilization-rule": CibRuleInEffectStatus.IN_EFFECT,
            }
        )
        mock_get_rule_evaluator.return_value = rule_evaluator
        self.assertEqual(
            self.command(evaluate_expired=True),
            get_nodes_dto(rule_evaluator),
        )
        mock_get_rule_evaluator.assert_called_once()

    def test_cib_error(self):
        self.config.runner.cib.load(returncode=1, stderr="error")
        self.env_assist.assert_raise_library_error(
            self.command,
            reports=[
                fixture.error(reports.codes.CIB_LOAD_ERROR, reason="error")
            ],
            expected_in_processor=False,
        )
        self.env_assist.assert_reports([])
