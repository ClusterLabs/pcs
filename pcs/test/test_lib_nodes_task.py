from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock

from pcs.common import report_codes
from pcs.lib.external import NodeCommunicator, NodeAuthenticationException
from pcs.lib.node import NodeAddresses, NodeAddressesList
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.nodes_task as lib


class DistributeCorosyncConfTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.mock_communicator = "mock node communicator"

    @mock.patch("pcs.lib.nodes_task.corosync_live")
    def test_success(self, mock_corosync_live):
        conf_text = "test conf text"
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        mock_corosync_live.set_remote_corosync_conf = mock.MagicMock()

        lib.distribute_corosync_conf(
            self.mock_communicator,
            self.mock_reporter,
            node_addrs_list,
            conf_text
        )

        corosync_live_calls = [
            mock.call.set_remote_corosync_conf(
                "mock node communicator", node_addrs_list[0], conf_text
            ),
            mock.call.set_remote_corosync_conf(
                "mock node communicator", node_addrs_list[1], conf_text
            ),
        ]
        self.assertEqual(
            len(corosync_live_calls),
            len(mock_corosync_live.mock_calls)
        )
        mock_corosync_live.set_remote_corosync_conf.assert_has_calls(
            corosync_live_calls,
            any_order=True
        )

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    {"node": nodes[0]}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    {"node": nodes[1]}
                ),
            ]
        )

    @mock.patch("pcs.lib.nodes_task.corosync_live")
    def test_one_node_down(self, mock_corosync_live):
        conf_text = "test conf text"
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        mock_corosync_live.set_remote_corosync_conf = mock.MagicMock()
        def raiser(comm, node, conf):
            if node.ring0 == nodes[1]:
                raise NodeAuthenticationException(
                    nodes[1], "command", "HTTP error: 401"
                )
        mock_corosync_live.set_remote_corosync_conf.side_effect = raiser

        assert_raise_library_error(
            lambda: lib.distribute_corosync_conf(
                self.mock_communicator,
                self.mock_reporter,
                node_addrs_list,
                conf_text
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
                report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                {
                    "node": nodes[1],
                },
                report_codes.SKIP_OFFLINE_NODES
            )
        )

        corosync_live_calls = [
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[0], conf_text
            ),
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[1], conf_text
            ),
        ]
        self.assertEqual(
            len(corosync_live_calls),
            len(mock_corosync_live.mock_calls)
        )
        mock_corosync_live.set_remote_corosync_conf.assert_has_calls([
            mock.call("mock node communicator", node_addrs_list[0], conf_text),
            mock.call("mock node communicator", node_addrs_list[1], conf_text),
        ], any_order=True)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    {"node": nodes[0]}
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
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    {
                        "node": nodes[1],
                    },
                    report_codes.SKIP_OFFLINE_NODES
                )
            ]
        )

    @mock.patch("pcs.lib.nodes_task.corosync_live")
    def test_one_node_down_forced(self, mock_corosync_live):
        conf_text = "test conf text"
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        mock_corosync_live.set_remote_corosync_conf = mock.MagicMock()
        def raiser(comm, node, conf):
            if node.ring0 == nodes[1]:
                raise NodeAuthenticationException(
                    nodes[1], "command", "HTTP error: 401"
                )
        mock_corosync_live.set_remote_corosync_conf.side_effect = raiser

        lib.distribute_corosync_conf(
            self.mock_communicator,
            self.mock_reporter,
            node_addrs_list,
            conf_text,
            skip_offline_nodes=True
        )

        corosync_live_calls = [
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[0], conf_text
            ),
            mock.call.set_remote_corosync_conf(
                "mock node communicator", nodes[1], conf_text
            ),
        ]
        self.assertEqual(
            len(corosync_live_calls),
            len(mock_corosync_live.mock_calls)
        )
        mock_corosync_live.set_remote_corosync_conf.assert_has_calls([
            mock.call("mock node communicator", node_addrs_list[0], conf_text),
            mock.call("mock node communicator", node_addrs_list[1], conf_text),
        ], any_order=True)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
                    {}
                ),
                (
                    severity.INFO,
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    {"node": nodes[0]}
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
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    {
                        "node": nodes[1],
                    }
                ),
            ]
        )

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
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        self.mock_communicator.call_node.side_effect = [
            '{"corosync": false}',
            '{"corosync": true}',
        ]

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
                    "node": nodes[1],
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


@mock.patch("pcs.lib.nodes_task.qdevice_client.remote_client_stop")
@mock.patch("pcs.lib.nodes_task.qdevice_client.remote_client_start")
class QdeviceReloadOnNodesTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()
        self.mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)

    def test_success(self, mock_remote_start, mock_remote_stop):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )

        lib.qdevice_reload_on_nodes(
            self.mock_communicator,
            self.mock_reporter,
            node_addrs_list
        )

        node_calls = [
            mock.call(
                self.mock_reporter, self.mock_communicator, node_addrs_list[0]
            ),
            mock.call(
                self.mock_reporter, self.mock_communicator, node_addrs_list[1]
            ),
        ]
        self.assertEqual(len(node_calls), len(mock_remote_stop.mock_calls))
        self.assertEqual(len(node_calls), len(mock_remote_start.mock_calls))
        mock_remote_stop.assert_has_calls(node_calls, any_order=True)
        mock_remote_start.assert_has_calls(node_calls, any_order=True)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CLIENT_RELOAD_STARTED,
                    {}
                ),
            ]
        )

    def test_fail_doesnt_prevent_start(
        self, mock_remote_start, mock_remote_stop
    ):
        nodes = ["node1", "node2"]
        node_addrs_list = NodeAddressesList(
            [NodeAddresses(addr) for addr in nodes]
        )
        def raiser(reporter, communicator, node):
            if node.ring0 == nodes[1]:
                raise NodeAuthenticationException(
                    node.label, "command", "HTTP error: 401"
                )
        mock_remote_stop.side_effect = raiser

        assert_raise_library_error(
            lambda: lib.qdevice_reload_on_nodes(
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
            )
        )

        node_calls = [
            mock.call(
                self.mock_reporter, self.mock_communicator, node_addrs_list[0]
            ),
            mock.call(
                self.mock_reporter, self.mock_communicator, node_addrs_list[1]
            ),
        ]
        self.assertEqual(len(node_calls), len(mock_remote_stop.mock_calls))
        self.assertEqual(len(node_calls), len(mock_remote_start.mock_calls))
        mock_remote_stop.assert_has_calls(node_calls, any_order=True)
        mock_remote_start.assert_has_calls(node_calls, any_order=True)

        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_CLIENT_RELOAD_STARTED,
                    {}
                ),
                # why the same error twice?
                # 1. Tested piece of code calls a function which puts an error
                # into the reporter. The reporter raises an exception. The
                # exception is caught in the tested piece of code, stored, and
                # later put to reporter again.
                # 2. Mock reporter remembers everything that goes through it
                # and by the machanism described in 1 the error goes througt it
                # twice.
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
                    report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                    {
                        "node": nodes[1],
                        "command": "command",
                        "reason" : "HTTP error: 401",
                    },
                    report_codes.SKIP_OFFLINE_NODES
                ),
            ]
        )


class NodeCheckAuthTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib.node_check_auth(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/check_auth", "check_auth_only=1"
        )
