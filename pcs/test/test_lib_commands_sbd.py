from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import logging

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib.errors import (
    ReportItemSeverity as Severities,
    LibraryError,
    ReportItem,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.node import (
    NodeAddresses,
    NodeAddressesList,
)
from pcs.lib.external import (
    NodeCommunicator,
    NodeConnectionException,
    CommandRunner,
)
import pcs.lib.commands.sbd as cmd_sbd


def _assert_equal_list_of_dictionaries_without_order(expected, actual):
    for item in actual:
        if item not in expected:
            raise AssertionError("Given but not expected: {0}".format(item))
    for item in expected:
        if item not in actual:
            raise AssertionError("Expected but not given: {0}".format(item))


class CommandSbdTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_log = mock.MagicMock(spec_set=logging.Logger)
        self.mock_env.logger = self.mock_log
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_env.node_communicator.return_value = self.mock_com
        self.mock_run = mock.MagicMock(spec_set=CommandRunner)
        self.mock_env.cmd_runner.return_value = self.mock_run
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env.report_processor = self.mock_rep

        self.node_list = NodeAddressesList(
            [NodeAddresses("node" + str(i)) for i in range(3)]
        )


class ValidateSbdOptionsTest(TestCase):
    def setUp(self):
        self.allowed_sbd_options = sorted([
            "SBD_DELAY_START", "SBD_STARTMODE", "SBD_WATCHDOG_TIMEOUT"
        ])

    def test_all_ok(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean"
        }
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_unknown_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value"
        }
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_UNKNOWN",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "another_unknown_option",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    report_codes.FORCE_OPTIONS
                )
            ]
        )

    def test_unknown_options_forced(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_UNKNOWN": "",
            "another_unknown_option": "some value"
        }
        # just make sure there is no exception raised
        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config, allow_unknown_opts=True),
            [
                (
                    Severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_UNKNOWN",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "another_unknown_option",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                )
            ]
        )


    def test_unsupported_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_OPTS": "  "
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_WATCHDOG_DEV",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_OPTS",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                )
            ]
        )

    def test_invalid_and_unsupported_options(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_UNKNOWN": "",
            "SBD_OPTS": "  "
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_WATCHDOG_DEV",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_OPTS",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_UNKNOWN",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    report_codes.FORCE_OPTIONS
                )
            ]
        )

    def test_invalid_and_unsupported_options_forced(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_WATCHDOG_TIMEOUT": "5",
            "SBD_STARTMODE": "clean",
            "SBD_WATCHDOG_DEV": "/dev/watchdog",
            "SBD_UNKNOWN": "",
            "SBD_OPTS": "  ",
            "SBD_PACEMAKER": "false",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config, allow_unknown_opts=True),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_WATCHDOG_DEV",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_OPTS",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.WARNING,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_UNKNOWN",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                ),
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION,
                    {
                        "option_name": "SBD_PACEMAKER",
                        "option_type": None,
                        "allowed": self.allowed_sbd_options,
                    },
                    None
                )
            ]
        )

    def test_watchdog_timeout_is_not_present(self):
        config = {
            "SBD_DELAY_START": "yes",
            "SBD_STARTMODE": "clean"
        }
        self.assertEqual([], cmd_sbd._validate_sbd_options(config))

    def test_watchdog_timeout_is_nonnegative_int(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": "-1",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": "-1",
                        "allowed_values": "nonnegative integer",
                    },
                    None
                )
            ]
        )

    def test_watchdog_timeout_is_not_int(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": "not int",
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": "not int",
                        "allowed_values": "nonnegative integer",
                    },
                    None
                )
            ]
        )

    def test_watchdog_timeout_is_none(self):
        config = {
            "SBD_WATCHDOG_TIMEOUT": None,
        }

        assert_report_item_list_equal(
            cmd_sbd._validate_sbd_options(config),
            [
                (
                    Severities.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "SBD_WATCHDOG_TIMEOUT",
                        "option_value": None,
                        "allowed_values": "nonnegative integer",
                    },
                    None
                )
            ]
        )


class GetFullWatchdogListTest(TestCase):
    def setUp(self):
        self.node_list = NodeAddressesList(
            [NodeAddresses("node" + str(i)) for i in range(5)]
        )

    def test_full(self):
        watchdog_dict = {
            self.node_list[1].label: "/dev/watchdog1",
            self.node_list[2].label: "/dev/watchdog2"
        }
        expected = {
            self.node_list[0]: "/dev/default",
            self.node_list[1]: "/dev/watchdog1",
            self.node_list[2]: "/dev/watchdog2",
            self.node_list[3]: "/dev/default",
            self.node_list[4]: "/dev/default",
        }
        self.assertEqual(
            cmd_sbd._get_full_watchdog_list(
                self.node_list, "/dev/default", watchdog_dict
            ),
            expected
        )

    def test_unknown_nodes(self):
        watchdog_dict = {
            self.node_list[1].label: "/dev/watchdog1",
            self.node_list[2].label: "/dev/watchdog2",
            "unknown_node": "/dev/watchdog0",
            "another_unknown_node": "/dev/watchdog"
        }
        assert_raise_library_error(
            lambda: cmd_sbd._get_full_watchdog_list(
                self.node_list, "/dev/dog", watchdog_dict
            ),
            (
                Severities.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "unknown_node"}
            ),
            (
                Severities.ERROR,
                report_codes.NODE_NOT_FOUND,
                {"node": "another_unknown_node"}
            )
        )

    def test_invalid_watchdogs(self):
        watchdog_dict = {
            self.node_list[1].label: "",
            self.node_list[2].label: None,
            self.node_list[3].label: "not/abs/path",
            self.node_list[4].label: "/dev/watchdog"

        }
        assert_raise_library_error(
            lambda: cmd_sbd._get_full_watchdog_list(
                self.node_list, "/dev/dog", watchdog_dict
            ),
            (
                Severities.ERROR,
                report_codes.WATCHDOG_INVALID,
                {"watchdog": ""}
            ),
            (
                Severities.ERROR,
                report_codes.WATCHDOG_INVALID,
                {"watchdog": None}
            ),
            (
                Severities.ERROR,
                report_codes.WATCHDOG_INVALID,
                {"watchdog": "not/abs/path"}
            )
        )


@mock.patch("pcs.lib.commands.sbd._get_cluster_nodes")
@mock.patch("pcs.lib.sbd.check_sbd")
class GetClusterSbdStatusTest(CommandSbdTest):
    def test_success(self, mock_check_sbd, mock_get_nodes):
        def ret_val(communicator, node, empty_str):
            self.assertEqual(communicator, self.mock_com)
            self.assertEqual(empty_str, "")
            if node.label == "node0":
                return """{
                    "sbd": {
                        "installed": true,
                        "enabled": true,
                        "running": false
                    }
                }"""
            elif node.label == "node1":
                return """{
                    "sbd": {
                        "installed": false,
                        "enabled": false,
                        "running": false
                    }
                }"""
            elif node.label == "node2":
                return """{
                    "sbd": {
                        "installed": true,
                        "enabled": false,
                        "running": false
                    }
                }"""
            else:
                raise AssertionError(
                    "Unexpected call: node={node}, node.label={label}".format(
                        node=str(node), label=node.label
                    )
                )

        mock_check_sbd.side_effect = ret_val
        self.mock_env.is_cman_cluster = False
        mock_get_nodes.return_value = self.node_list
        expected = [
            {
                "node": self.node_list.find_by_label("node0"),
                "status": {
                    "installed": True,
                    "enabled": True,
                    "running": False
                }
            },
            {
                "node": self.node_list.find_by_label("node1"),
                "status": {
                    "installed": False,
                    "enabled": False,
                    "running": False
                }
            },
            {
                "node": self.node_list.find_by_label("node2"),
                "status": {
                    "installed": True,
                    "enabled": False,
                    "running": False
                }
            }
        ]
        _assert_equal_list_of_dictionaries_without_order(
            expected, cmd_sbd.get_cluster_sbd_status(self.mock_env)
        )
        mock_get_nodes.assert_called_once_with(self.mock_env)
        self.assertEqual(3, mock_check_sbd.call_count)
        self.assertEqual(self.mock_log.warning.call_count, 0)

    def test_failures(self, mock_check_sbd, mock_get_nodes):
        def ret_val(communicator, node, empty_str):
            self.assertEqual(communicator, self.mock_com)
            self.assertEqual(empty_str, "")
            if node.label == "node0":
                return """{
                    "not_sbd": {
                        "installed": true,
                        "enabled": true,
                        "running": false
                    }
                }"""
            elif node.label == "node1":
                raise NodeConnectionException(node.label, "command", "reason")
            elif node.label == "node2":
                return "invalid_json"
            else:
                raise AssertionError(
                    "Unexpected call: node={node}, node.label={label}".format(
                        node=str(node), label=node.label
                    )
                )

        mock_check_sbd.side_effect = ret_val
        self.mock_env.is_cman_cluster = False
        mock_get_nodes.return_value = self.node_list
        all_none = {
            "installed": None,
            "enabled": None,
            "running": None
        }
        expected = [
            {
                "node": self.node_list.find_by_label("node0"),
                "status": all_none
            },
            {
                "node": self.node_list.find_by_label("node1"),
                "status": all_none
            },
            {
                "node": self.node_list.find_by_label("node2"),
                "status": all_none
            }
        ]

        _assert_equal_list_of_dictionaries_without_order(
            expected, cmd_sbd.get_cluster_sbd_status(self.mock_env)
        )
        mock_get_nodes.assert_called_once_with(self.mock_env)
        self.assertEqual(3, mock_check_sbd.call_count)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.WARNING,
                    report_codes.UNABLE_TO_GET_SBD_STATUS,
                    {"node": "node0"}
                ),
                (
                    Severities.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    {
                        "node": "node1",
                        "reason": "reason",
                        "command": "command",
                    }
                ),
                (
                    Severities.WARNING,
                    report_codes.UNABLE_TO_GET_SBD_STATUS,
                    {"node": "node1"}
                ),
                (
                    Severities.WARNING,
                    report_codes.UNABLE_TO_GET_SBD_STATUS,
                    {"node": "node2"}
                )
            ]
        )

@mock.patch("pcs.lib.commands.sbd._get_cluster_nodes")
@mock.patch("pcs.lib.sbd.get_sbd_config")
class GetClusterSbdConfigTest(CommandSbdTest):
    def test_success(self, mock_sbd_cfg, mock_get_nodes):
        this = self

        def ret_val(communicator, node):
            this.assertEqual(communicator, this.mock_com)
            if node.label == "node0":
                return """\
# comment
SBD_TEST=true
ANOTHER_OPT=1
"""
            elif node.label == "node1":
                return """\
OPTION=   value

"""
            elif node.label == "node2":
                return """\

# just comment

"""
            else:
                raise AssertionError(
                    "Unexpected call: node={node}, node.label={label}".format(
                        node=str(node), label=node.label
                    )
                )

        mock_sbd_cfg.side_effect = ret_val
        self.mock_env.is_cman_cluster = False
        mock_get_nodes.return_value = self.node_list
        expected = [
            {
                "node": self.node_list.find_by_label("node0"),
                "config": {
                    "SBD_TEST": "true",
                    "ANOTHER_OPT": "1"
                }
            },
            {
                "node": self.node_list.find_by_label("node1"),
                "config": {"OPTION": "value"}
            },
            {
                "node": self.node_list.find_by_label("node2"),
                "config": {}
            }
        ]

        _assert_equal_list_of_dictionaries_without_order(
            expected, cmd_sbd.get_cluster_sbd_config(self.mock_env)
        )
        mock_get_nodes.assert_called_once_with(self.mock_env)
        self.assertEqual(3, mock_sbd_cfg.call_count)
        self.assertEqual(self.mock_log.warning.call_count, 0)

    def test_few_failures(self, mock_sbd_cfg, mock_get_nodes):
        def ret_val(communicator, node):
            self.assertEqual(communicator, self.mock_com)
            if node.label == "node0":
                return """\
            # comment
            SBD_TEST=true
            ANOTHER_OPT=1
            """
            elif node.label == "node1":
                return """\
invalid value

            """
            elif node.label == "node2":
                raise NodeConnectionException(node.label, "command", "reason")
            else:
                raise AssertionError(
                    "Unexpected call: node={node}, node.label={label}".format(
                        node=str(node), label=node.label
                    )
                )

        mock_sbd_cfg.side_effect = ret_val
        self.mock_env.is_cman_cluster = False
        mock_get_nodes.return_value = self.node_list
        expected = [
            {
                "node": self.node_list.find_by_label("node0"),
                "config": {
                    "SBD_TEST": "true",
                    "ANOTHER_OPT": "1"
                }
            },
            {
                "node": self.node_list.find_by_label("node1"),
                "config": {}
            },
            {
                "node": self.node_list.find_by_label("node2"),
                "config": None
            }
        ]

        _assert_equal_list_of_dictionaries_without_order(
            expected, cmd_sbd.get_cluster_sbd_config(self.mock_env)
        )
        mock_get_nodes.assert_called_once_with(self.mock_env)
        self.assertEqual(3, mock_sbd_cfg.call_count)
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [
                (
                    Severities.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    {
                        "node": "node2",
                        "reason": "reason",
                        "command": "command",
                    }
                ),
                (
                    Severities.WARNING,
                    report_codes.UNABLE_TO_GET_SBD_CONFIG,
                    {"node": "node2"}
                ),
            ]
        )


@mock.patch("pcs.lib.sbd.get_local_sbd_config")
class GetLocalSbdConfigTest(TestCase):
    def setUp(self):
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)

    def test_success(self, mock_config):
        self.mock_env.is_cman_cluster = False
        mock_config.return_value = """
# This file has been generated by pcs.
SBD_OPTS="-n node1"
SBD_WATCHDOG_DEV=/dev/watchdog
SBD_WATCHDOG_TIMEOUT=0
"""

        self.assertEqual(
            {
                "SBD_OPTS": '"-n node1"',
                "SBD_WATCHDOG_DEV": "/dev/watchdog",
                "SBD_WATCHDOG_TIMEOUT": "0"
            },
            cmd_sbd.get_local_sbd_config(self.mock_env)
        )
        self.assertEqual(1, mock_config.call_count)

    def test_file_error(self, mock_config):
        self.mock_env.is_cman_cluster = False
        mock_config.side_effect = LibraryError(ReportItem.error(
            report_codes.UNABLE_TO_GET_SBD_CONFIG,
        ))
        assert_raise_library_error(
            lambda: cmd_sbd.get_local_sbd_config(self.mock_env),
            (
                Severities.ERROR,
                report_codes.UNABLE_TO_GET_SBD_CONFIG,
                {}
            )
        )
