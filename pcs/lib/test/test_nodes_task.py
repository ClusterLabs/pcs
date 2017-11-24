from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json

from pcs.test.tools.pcs_unittest import TestCase, skip

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.misc import create_patcher

from pcs.common import report_codes
from pcs.lib.external import NodeCommunicator, NodeAuthenticationException
from pcs.lib.node import NodeAddresses, NodeAddressesList
from pcs.lib.errors import ReportItemSeverity as severity

# import pcs.lib.nodes_task as lib
lib = mock.Mock()
lib.__name__ = "nodes_task"

patch_nodes_task = create_patcher(lib)

@skip("TODO: rewrite for pcs.lib.communication.corosync.CheckCorosyncOffline")
class CheckCorosyncOfflineTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.mock_communicator = mock.MagicMock(NodeCommunicator)

    def test_success(self):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        self.mock_communicator.call_node.return_value = '{"corosync": false}'

        lib.check_corosync_offline_on_nodes(
            self.mock_communicator,
            self.mock_reporter,
            node_addrs_list
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                    {"node": nodes[0]}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
                    {"node": nodes[1]}
                ),
            ]
        )

    def test_one_node_running(self):
        node_responses = {
            "node1": '{"corosync": false}',
            "node2": '{"corosync": true}',
        }
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in node_responses.keys()]
        )

        self.mock_communicator.call_node.side_effect = (
            lambda node, request, data: node_responses[node.label]
        )


        assert_raise_library_error(
            lambda: lib.check_corosync_offline_on_nodes(
                self.mock_communicator,
                self.mock_reporter,
                node_addrs_list
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_RUNNING_ON_NODE,
                {
                    "node": "node2",
                }
            )
        )

    def test_json_error(self):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        self.mock_communicator.call_node.side_effect = [
            '{}', # missing key
            '{', # not valid json
        ]

        assert_raise_library_error(
            lambda: lib.check_corosync_offline_on_nodes(
                self.mock_communicator,
                self.mock_reporter,
                node_addrs_list
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                {
                    "node": nodes[0],
                },
                report_codes.SKIP_OFFLINE_NODES
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                {
                    "node": nodes[1],
                },
                report_codes.SKIP_OFFLINE_NODES
            )
        )

    def test_node_down(self):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        def side_effect(node, request, data):
            if node.ring0 == nodes[1]:
                raise NodeAuthenticationException(
                    nodes[1], "command", "HTTP error: 401"
                )
            return '{"corosync": false}'
        self.mock_communicator.call_node.side_effect = side_effect

        assert_raise_library_error(
            lambda: lib.check_corosync_offline_on_nodes(
                self.mock_communicator,
                self.mock_reporter,
                node_addrs_list
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                {
                    "node": nodes[1],
                    "command": "command",
                    "reason" : "HTTP error: 401",
                },
                report_codes.SKIP_OFFLINE_NODES
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                {
                    "node": nodes[1],
                },
                report_codes.SKIP_OFFLINE_NODES
            )
        )

    def test_errors_forced(self):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        def side_effect(node, request, data):
            if node.ring0 == nodes[1]:
                raise NodeAuthenticationException(
                    nodes[1], "command", "HTTP error: 401"
                )
            return '{' # invalid json
        self.mock_communicator.call_node.side_effect = side_effect

        lib.check_corosync_offline_on_nodes(
            self.mock_communicator,
            self.mock_reporter,
            node_addrs_list,
            skip_offline_nodes=True
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED,
                    {}
                ),
                (
                    severity.WARNING,
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    {
                        "node": nodes[0],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                    {
                        "node": nodes[1],
                        "command": "command",
                        "reason" : "HTTP error: 401",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    {
                        "node": nodes[1],
                    }
                )
            ]
        )

@skip("TODO: rewrite for pcs.lib.communication.nodes.GetOnlineTargets")
class NodeCheckAuthTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib.node_check_auth(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/check_auth", "check_auth_only=1"
        )


def fixture_invalid_response_format(node_label):
    return (
        severity.ERROR,
        report_codes.INVALID_RESPONSE_FORMAT,
        {
            "node": node_label
        },
        None
    )

def assert_call_cause_reports(call, expected_report_items):
    report_items = []
    call(report_items)
    assert_report_item_list_equal(report_items, expected_report_items)

@skip("TODO: rewrite for pcs.lib.communication.nodes.PrecheckNewNode")
class CheckCanAddNodeToCluster(TestCase):
    def setUp(self):
        self.node = NodeAddresses("node1")
        self.node_communicator = mock.MagicMock(spec_set=NodeCommunicator)

    def assert_result_causes_invalid_format(self, result):
        self.node_communicator.call_node = mock.Mock(
            return_value=json.dumps(result)
        )
        assert_call_cause_reports(
            self.make_call,
            [fixture_invalid_response_format(self.node.label)],
        )

    def make_call(self, report_items):
        lib.check_can_add_node_to_cluster(
            self.node_communicator,
            self.node,
            report_items,
            check_response=(
                lambda availability_info, report_items, node_label: None
            )
        )

    def test_report_no_dict_in_json_response(self):
        self.assert_result_causes_invalid_format("bad answer")

class OnNodeTest(TestCase):
    def setUp(self):
        self.reporter = MockLibraryReportProcessor()
        self.node = NodeAddresses("node1")
        self.node_communicator = mock.MagicMock(spec_set=NodeCommunicator)

    def set_call_result(self, result):
        self.node_communicator.call_node = mock.Mock(
            return_value=json.dumps(result)
        )

@skip(
    "TODO: rewrite for pcs.lib.communication.nodes.RunActionBase and it's "
    "descendants"
)
class RunActionOnNode(OnNodeTest):
    def make_call(self):
        return lib.run_actions_on_node(
            self.node_communicator,
            "remote/run_action",
            "actions",
            self.reporter,
            self.node,
            {"action": {"type": "any_mock_type"}}
        )

    def test_return_node_action_result(self):
        self.set_call_result({
            "actions": {
                "action": {
                    "code": "some_code",
                    "message": "some_message",
                }
            }
        })
        result = self.make_call()["action"]
        self.assertEqual(result.code, "some_code")
        self.assertEqual(result.message, "some_message")
