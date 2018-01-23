from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json

from pcs.test.tools.pcs_unittest import TestCase, skip

from pcs.test.tools.assertions import (
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.misc import create_patcher

from pcs.common import report_codes
from pcs.lib.external import NodeCommunicator
from pcs.lib.node import NodeAddresses
from pcs.lib.errors import ReportItemSeverity as severity

# import pcs.lib.nodes_task as lib
lib = mock.Mock()
lib.__name__ = "nodes_task"

patch_nodes_task = create_patcher(lib)

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
