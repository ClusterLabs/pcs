from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json
from unittest import TestCase

from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib.errors import (
    ReportItemSeverity as Severities,
    ReportItem,
    LibraryError,
)
from pcs.lib.node import NodeAddresses
from pcs.lib.external import (
    NodeCommunicator,
    NodeCommunicationException,
    NodeConnectionException,
)
import pcs.lib.sbd as lib_sbd


class TestException(Exception):
    pass


class RunParallelAndRaiseLibErrorOnFailureTest(TestCase):
    def test_no_report_items(self):
        # test that no exception has been raised
        lib_sbd._run_parallel_and_raise_lib_error_on_failure(
            lambda: [],
            [([], {}) for _ in range(5)]
        )

    def test_failures(self):
        def report_item_generator(i):
            if i == 1:
                raise NodeConnectionException("node", "command", "reason")
            elif i == 2:
                raise LibraryError(
                    ReportItem.error(
                        report_codes.COMMON_ERROR,
                        "another report"
                    ),
                    ReportItem.info(
                        report_codes.COMMON_INFO,
                        "just info"
                    )
                )

        assert_raise_library_error(
            lambda: lib_sbd._run_parallel_and_raise_lib_error_on_failure(
                report_item_generator,
                [([i], {}) for i in range(5)]
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": "node",
                    "command": "command",
                    "reason": "reason"
                }
            ),
            (
                Severities.ERROR,
                report_codes.COMMON_ERROR,
                {}
            ),
            (
                Severities.INFO,
                report_codes.COMMON_INFO,
                {}
            )
        )


class CheckSbdTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.check_sbd(mock_communicator, node, "/dev/watchdog")
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/check_sbd", "watchdog=%2Fdev%2Fwatchdog"
        )


@mock.patch("pcs.lib.sbd.check_sbd")
class CheckSbdOnNodeTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_rep = MockLibraryReportProcessor()
        self.node = NodeAddresses("node1")

    def test_success(self, mock_check_sbd):
        mock_check_sbd.return_value = json.dumps({
            "sbd": {
                "installed": True
            },
            "watchdog": {
                "exist": True
            }
        })
        # if no exception was raised, it's fine
        lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SBD_CHECK_SUCCESS,
                {"node": self.node.label}
            )]
        )

    def test_unable_to_connect(self, mock_check_sbd):
        mock_check_sbd.side_effect = NodeConnectionException(
            self.node.label, "command", "reason"
        )
        self.assertRaises(
            NodeCommunicationException,
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))

    def test_data_parsing_error(self, mock_check_sbd):
        mock_check_sbd.return_value = "invalid JSON"
        assert_raise_library_error(
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": self.node.label}
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))

    def test_sbd_not_installed(self, mock_check_sbd):
        mock_check_sbd.return_value = json.dumps({
            "sbd": {
                "installed": False
            },
            "watchdog": {
                "exist": True
            }
        })
        assert_raise_library_error(
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            ),
            (
                Severities.ERROR,
                report_codes.SBD_NOT_INSTALLED,
                {"node": self.node.label}
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))

    def test_watchdog_does_not_exist(self, mock_check_sbd):
        mock_check_sbd.return_value = json.dumps({
            "sbd": {
                "installed": True
            },
            "watchdog": {
                "exist": False
            }
        })
        assert_raise_library_error(
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            ),
            (
                Severities.ERROR,
                report_codes.WATCHDOG_NOT_FOUND,
                {"node": self.node.label}
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))

    def test_watchdog_does_not_exist_and_sbd_not_installed(
            self, mock_check_sbd
    ):
        mock_check_sbd.return_value = json.dumps({
            "sbd": {
                "installed": False
            },
            "watchdog": {
                "exist": False
            }
        })
        assert_raise_library_error(
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            ),
            (
                Severities.ERROR,
                report_codes.WATCHDOG_NOT_FOUND,
                {"node": self.node.label}
            ),
            (
                Severities.ERROR,
                report_codes.SBD_NOT_INSTALLED,
                {"node": self.node.label}
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))

    def test_invalid_response_format(self, mock_check_sbd):
        mock_check_sbd.return_value = json.dumps({
            "not_sbd": {
                "installed": False
            },
            "watchdog": {
                "exist": False
            }
        })
        assert_raise_library_error(
            lambda: lib_sbd.check_sbd_on_node(
                self.mock_rep, self.mock_com, self.node, "watchdog"
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": self.node.label}
            )
        )
        mock_check_sbd.assert_called_once_with(
            self.mock_com, self.node, "watchdog"
        )
        self.assertEqual(0, len(self.mock_rep.report_item_list))


@mock.patch("pcs.lib.sbd._run_parallel_and_raise_lib_error_on_failure")
class CheckSbdOnAllNodesTest(TestCase):
    def test_success(self, mock_func):
        mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        mock_rep = MockLibraryReportProcessor()
        node_list = [NodeAddresses("node" + str(i)) for i in range(2)]
        data = {
            node_list[0]: "/dev/watchdog1",
            node_list[1]: "/dev/watchdog2"
        }
        lib_sbd.check_sbd_on_all_nodes(mock_rep, mock_com, data)
        items = sorted(data.items())
        mock_func.assert_called_once_with(
            lib_sbd.check_sbd_on_node,
            [
                ([mock_rep, mock_com, node, watchdog], {})
                for node, watchdog in items
            ]
        )


class SetSbdConfigTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        cfg = """# This file has been generated by pcs.
SBD_OPTS="-n node1"
SBD_WATCHDOG_DEV=/dev/watchdog
SBD_WATCHDOG_TIMEOUT=0
"""
        lib_sbd.set_sbd_config(mock_communicator, node, cfg)
        cfg_url_encoded = "%23+This+file+has+been+generated+by+" \
            "pcs.%0ASBD_OPTS%3D%22-n+node1%22%0ASBD_WATCHDOG_DEV%3D%2Fdev%2" \
            "Fwatchdog%0ASBD_WATCHDOG_TIMEOUT%3D0%0A"
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/set_sbd_config", "config=" + cfg_url_encoded
        )


@mock.patch("pcs.lib.sbd.set_sbd_config")
class SetSbdConfigOnNodeTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_rep = MockLibraryReportProcessor()
        self.node = NodeAddresses("node1")

    def test_success(self, mock_set_sbd_cfg):
        cfg_in = {
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_WATCHDOG_TIMEOUT": "0"
        }
        cfg_out = """# This file has been generated by pcs.
SBD_OPTS="-n node1"
SBD_WATCHDOG_DEV=/dev/watchdog
SBD_WATCHDOG_TIMEOUT=0
"""
        lib_sbd.set_sbd_config_on_node(
            self.mock_rep, self.mock_com, self.node, cfg_in
        )
        mock_set_sbd_cfg.assert_called_once_with(
            self.mock_com, self.node, cfg_out
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SBD_CONFIG_ACCEPTED_BY_NODE,
                {"node": self.node.label}
            )]
        )


@mock.patch("pcs.lib.sbd._run_parallel_and_raise_lib_error_on_failure")
class SetSbdConfigOnAllNodesTest(TestCase):
    def test_success(self, mock_func):
        mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        mock_rep = MockLibraryReportProcessor()
        node_list = [NodeAddresses("node" + str(i)) for i in range(5)]
        config = {
            "opt1": "val1",
            "opt2": "val2"
        }
        lib_sbd.set_sbd_config_on_all_nodes(
            mock_rep, mock_com, node_list, config
        )
        mock_func.assert_called_once_with(
            lib_sbd.set_sbd_config_on_node,
            [([mock_rep, mock_com, node, config], {}) for node in node_list]
        )


class EnableSbdServiceTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.enable_sbd_service(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/sbd_enable", None
        )


class EnableSbdServiceOnNodeTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_rep = MockLibraryReportProcessor()
        self.node = NodeAddresses("node1")

    @mock.patch("pcs.lib.sbd.enable_sbd_service")
    def test_success(self, mock_enable_sbd):
        lib_sbd.enable_sbd_service_on_node(
            self.mock_rep, self.mock_com, self.node
        )
        mock_enable_sbd.assert_called_once_with(self.mock_com, self.node)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_ENABLE_SUCCESS,
                {
                    "service": "sbd",
                    "node": self.node.label
                }
            )]
        )


@mock.patch("pcs.lib.sbd._run_parallel_and_raise_lib_error_on_failure")
class EnableSbdServiceOnAllNodes(TestCase):
    def test_success(self, mock_func):
        mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        mock_rep = MockLibraryReportProcessor()
        node_list = [NodeAddresses("node" + str(i)) for i in range(5)]
        lib_sbd.enable_sbd_service_on_all_nodes(mock_rep, mock_com, node_list)
        mock_func.assert_called_once_with(
            lib_sbd.enable_sbd_service_on_node,
            [([mock_rep, mock_com, node], {}) for node in node_list]
        )


class DisableSbdServiceTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.disable_sbd_service(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/sbd_disable", None
        )


class DisableSbdServiceOnNodeTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_rep = MockLibraryReportProcessor()
        self.node = NodeAddresses("node1")

    @mock.patch("pcs.lib.sbd.disable_sbd_service")
    def test_success(self, mock_disable_sbd):
        lib_sbd.disable_sbd_service_on_node(
            self.mock_rep, self.mock_com, self.node
        )
        mock_disable_sbd.assert_called_once_with(self.mock_com, self.node)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.SERVICE_DISABLE_SUCCESS,
                {
                    "service": "sbd",
                    "node": self.node.label
                }
            )]
        )


@mock.patch("pcs.lib.sbd._run_parallel_and_raise_lib_error_on_failure")
class DisableSbdServiceOnAllNodes(TestCase):
    def test_success(self, mock_func):
        mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        mock_rep = MockLibraryReportProcessor()
        node_list = [NodeAddresses("node" + str(i)) for i in range(5)]
        lib_sbd.disable_sbd_service_on_all_nodes(mock_rep, mock_com, node_list)
        mock_func.assert_called_once_with(
            lib_sbd.disable_sbd_service_on_node,
            [([mock_rep, mock_com, node], {}) for node in node_list]
        )


class SetStonithWatchdogTimeoutToZeroTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.set_stonith_watchdog_timeout_to_zero(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/set_stonith_watchdog_timeout_to_zero", None
        )


@mock.patch("pcs.lib.sbd.set_stonith_watchdog_timeout_to_zero")
class SetStonithWatchdogTimeoutToZeroOnAllNodesTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.node_list = [NodeAddresses("node" + str(i)) for i in range(5)]

    def test_success(self, mock_func):
        lib_sbd.set_stonith_watchdog_timeout_to_zero_on_all_nodes(
            self.mock_com, self.node_list
        )
        func_calls = [mock.call(self.mock_com, node) for node in self.node_list]
        self.assertEqual(mock_func.call_count, len(func_calls))
        mock_func.assert_has_calls(func_calls)

    def test_communication_error(self, mock_func):
        def raiser(_, node):
            if node == self.node_list[1]:
                raise NodeConnectionException(
                    self.node_list[1], "command", "reason"
                )
            elif node == self.node_list[4]:
                raise NodeCommunicationException(
                    self.node_list[4], "command", "reason"
                )

        mock_func.side_effect = raiser
        assert_raise_library_error(
            lambda: lib_sbd.set_stonith_watchdog_timeout_to_zero_on_all_nodes(
                self.mock_com, self.node_list
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": self.node_list[1],
                    "command": "command",
                    "reason": "reason"
                }
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {
                    "node": self.node_list[4],
                    "command": "command",
                    "reason": "reason"
                }
            )
        )
        func_calls = [mock.call(self.mock_com, node) for node in self.node_list]
        self.assertEqual(mock_func.call_count, len(func_calls))
        mock_func.assert_has_calls(func_calls)


class RemoveStonithWatchdogTimeoutTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.remove_stonith_watchdog_timeout(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/remove_stonith_watchdog_timeout", None
        )


@mock.patch("pcs.lib.sbd.remove_stonith_watchdog_timeout")
class RemoveStonithWatchdogTimeoutOnAllNodesTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.node_list = [NodeAddresses("node" + str(i)) for i in range(5)]

    def test_success(self, mock_func):
        lib_sbd.remove_stonith_watchdog_timeout_on_all_nodes(
            self.mock_com, self.node_list
        )
        func_calls = [mock.call(self.mock_com, node) for node in self.node_list]
        self.assertEqual(mock_func.call_count, len(func_calls))
        mock_func.assert_has_calls(func_calls)

    def test_communication_error(self, mock_func):
        def raiser(_, node):
            if node == self.node_list[1]:
                raise NodeConnectionException(
                    self.node_list[1], "command", "reason"
                )
            elif node == self.node_list[4]:
                raise NodeCommunicationException(
                    self.node_list[4], "command", "reason"
                )

        mock_func.side_effect = raiser
        assert_raise_library_error(
            lambda: lib_sbd.remove_stonith_watchdog_timeout_on_all_nodes(
                self.mock_com, self.node_list
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": self.node_list[1],
                    "command": "command",
                    "reason": "reason"
                }
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {
                    "node": self.node_list[4],
                    "command": "command",
                    "reason": "reason"
                }
            )
        )
        func_calls = [mock.call(self.mock_com, node) for node in self.node_list]
        self.assertEqual(mock_func.call_count, len(func_calls))
        mock_func.assert_has_calls(func_calls)


class GetSbdConfigTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = NodeAddresses("node1")
        lib_sbd.get_sbd_config(mock_communicator, node)
        mock_communicator.call_node.assert_called_once_with(
            node, "remote/get_sbd_config", None
        )


@mock.patch("pcs.lib.external.is_service_enabled")
class IsSbdEnabledTest(TestCase):
    def test_success(self, mock_is_service_enabled):
        mock_obj = mock.MagicMock()
        mock_is_service_enabled.return_value = True
        self.assertTrue(lib_sbd.is_sbd_enabled(mock_obj))
