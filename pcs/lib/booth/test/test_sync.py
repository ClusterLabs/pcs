from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase

import json
import base64
try:
    # python 2
    from urlparse import parse_qs as url_decode
except ImportError:
    # python 3
    from urllib.parse import parse_qs as url_decode

from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.assertions import (
    assert_report_item_list_equal,
    assert_raise_library_error,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib.node import NodeAddresses, NodeAddressesList
from pcs.lib.errors import ReportItemSeverity as Severities
from pcs.lib.external import NodeCommunicator, NodeConnectionException
import pcs.lib.booth.sync as lib


def to_b64(string):
    return base64.b64encode(string.encode("utf-8")).decode("utf-8")


class SetConfigOnNodeTest(TestCase):
    def setUp(self):
        self.mock_com = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_rep = MockLibraryReportProcessor()
        self.node = NodeAddresses("node")

    def test_with_authfile(self):
        lib._set_config_on_node(
            self.mock_com,
            self.mock_rep,
            self.node,
            "cfg_name",
            "cfg",
            authfile="/abs/path/my-key.key",
            authfile_data="test key".encode("utf-8")
        )
        self.assertEqual(1, self.mock_com.call_node.call_count)
        self.assertEqual(self.node, self.mock_com.call_node.call_args[0][0])
        self.assertEqual(
            "remote/booth_set_config", self.mock_com.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_com.call_node.call_args[0][2])
        self.assertTrue("data_json" in data)
        self.assertEqual(
            {
                "config": {
                    "name": "cfg_name.conf",
                    "data": "cfg"
                },
                "authfile": {
                    "name": "my-key.key",
                    "data": to_b64("test key")
                }
            },
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                {
                    "node": self.node.label,
                    "name": "cfg_name",
                    "name_list": ["cfg_name"]
                }
            )]
        )

    def test_authfile_data_None(self):
        lib._set_config_on_node(
            self.mock_com, self.mock_rep, self.node, "cfg_name", "cfg",
            authfile="key.key"
        )
        self.assertEqual(1, self.mock_com.call_node.call_count)
        self.assertEqual(self.node, self.mock_com.call_node.call_args[0][0])
        self.assertEqual(
            "remote/booth_set_config", self.mock_com.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_com.call_node.call_args[0][2])
        self.assertTrue("data_json" in data)
        self.assertEqual(
            {
                "config": {
                    "name": "cfg_name.conf",
                    "data": "cfg"
                }
            },
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                {
                    "node": self.node.label,
                    "name": "cfg_name",
                    "name_list": ["cfg_name"]
                }
            )]
        )

    def test_authfile_only_data(self):
        lib._set_config_on_node(
            self.mock_com, self.mock_rep, self.node, "cfg_name", "cfg",
            authfile_data="key".encode("utf-8")
        )
        self.assertEqual(1, self.mock_com.call_node.call_count)
        self.assertEqual(self.node, self.mock_com.call_node.call_args[0][0])
        self.assertEqual(
            "remote/booth_set_config", self.mock_com.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_com.call_node.call_args[0][2])
        self.assertTrue("data_json" in data)
        self.assertEqual(
            {
                "config": {
                    "name": "cfg_name.conf",
                    "data": "cfg"
                }
            },
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                {
                    "node": self.node.label,
                    "name": "cfg_name",
                    "name_list": ["cfg_name"]
                }
            )]
        )

    def test_without_authfile(self):
        lib._set_config_on_node(
            self.mock_com, self.mock_rep, self.node, "cfg_name", "cfg"
        )
        self.assertEqual(1, self.mock_com.call_node.call_count)
        self.assertEqual(self.node, self.mock_com.call_node.call_args[0][0])
        self.assertEqual(
            "remote/booth_set_config", self.mock_com.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_com.call_node.call_args[0][2])
        self.assertTrue("data_json" in data)
        self.assertEqual(
            {
                "config": {
                    "name": "cfg_name.conf",
                    "data": "cfg"
                }
            },
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_rep.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                {
                    "node": self.node.label,
                    "name": "cfg_name",
                    "name_list": ["cfg_name"]
                }
            )]
        )


@mock.patch("pcs.lib.booth.sync.parallel_nodes_communication_helper")
class SyncConfigInCluster(TestCase):
    def setUp(self):
        self.mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_reporter = MockLibraryReportProcessor()
        self.node_list = NodeAddressesList(
            [NodeAddresses("node" + str(i) for i in range(5))]
        )

    def test_without_authfile(self, mock_parallel):
        lib.send_config_to_all_nodes(
            self.mock_communicator,
            self.mock_reporter,
            self.node_list,
            "cfg_name",
            "config data"
        )
        mock_parallel.assert_called_once_with(
            lib._set_config_on_node,
            [
                (
                    [
                        self.mock_communicator,
                        self.mock_reporter,
                        node,
                        "cfg_name",
                        "config data",
                        None,
                        None
                    ],
                    {}
                )
                for node in self.node_list
            ],
            self.mock_reporter,
            False
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_DISTRIBUTING_CONFIG,
                {"name": "cfg_name"}
            )]
        )

    def test_skip_offline(self, mock_parallel):
        lib.send_config_to_all_nodes(
            self.mock_communicator,
            self.mock_reporter,
            self.node_list,
            "cfg_name",
            "config data",
            skip_offline=True
        )
        mock_parallel.assert_called_once_with(
            lib._set_config_on_node,
            [
                (
                    [
                        self.mock_communicator,
                        self.mock_reporter,
                        node,
                        "cfg_name",
                        "config data",
                        None,
                        None
                    ],
                    {}
                )
                for node in self.node_list
                ],
            self.mock_reporter,
            True
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_DISTRIBUTING_CONFIG,
                {"name": "cfg_name"}
            )]
        )

    def test_with_authfile(self, mock_parallel):
        lib.send_config_to_all_nodes(
            self.mock_communicator,
            self.mock_reporter,
            self.node_list,
            "cfg_name",
            "config data",
            authfile="/my/auth/file.key",
            authfile_data="authfile data".encode("utf-8")
        )
        mock_parallel.assert_called_once_with(
            lib._set_config_on_node,
            [
                (
                    [
                        self.mock_communicator,
                        self.mock_reporter,
                        node,
                        "cfg_name",
                        "config data",
                        "/my/auth/file.key",
                        "authfile data".encode("utf-8")
                    ],
                    {}
                )
                for node in self.node_list
                ],
            self.mock_reporter,
            False
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [(
                Severities.INFO,
                report_codes.BOOTH_DISTRIBUTING_CONFIG,
                {"name": "cfg_name"}
            )]
        )


@mock.patch("pcs.lib.booth.configuration.read_configs")
@mock.patch("pcs.lib.booth.configuration.read_authfiles_from_configs")
class SendAllConfigToNodeTest(TestCase):
    def setUp(self):
        self.mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        self.mock_reporter = MockLibraryReportProcessor()
        self.node = NodeAddresses("node")

    def test_success(self, mock_read_authfiles, mock_read_configs):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = """
        {
            "existing": [],
            "failed": {},
            "saved": ["name1.conf", "name2.conf", "file1.key", "file2.key"]
        }
        """
        lib.send_all_config_to_node(
            self.mock_communicator, self.mock_reporter, self.node
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVING_ON_NODE,
                    {"node": self.node.label}
                ),
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                    {
                        "node": self.node.label,
                        "name": "name1.conf, name2.conf, file1.key, file2.key",
                        "name_list": [
                            "name1.conf", "name2.conf", "file1.key", "file2.key"
                        ]
                    }
                )
            ]
        )

    def test_do_not_rewrite_existing(
        self, mock_read_authfiles, mock_read_configs
    ):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = """
        {
            "existing": ["name1.conf", "file1.key"],
            "failed": {},
            "saved": ["name2.conf", "file2.key"]
        }
        """
        assert_raise_library_error(
            lambda: lib.send_all_config_to_node(
                self.mock_communicator, self.mock_reporter, self.node
            ),
            (
                Severities.ERROR,
                report_codes.FILE_ALREADY_EXISTS,
                {
                    "file_role": None,
                    "file_path": "name1.conf",
                    "node": self.node.label
                },
                report_codes.FORCE_FILE_OVERWRITE
            ),
            (
                Severities.ERROR,
                report_codes.FILE_ALREADY_EXISTS,
                {
                    "file_role": None,
                    "file_path": "file1.key",
                    "node": self.node.label
                },
                report_codes.FORCE_FILE_OVERWRITE
            )
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVING_ON_NODE,
                    {"node": self.node.label}
                ),
                (
                    Severities.ERROR,
                    report_codes.FILE_ALREADY_EXISTS,
                    {
                        "file_role": None,
                        "file_path": "name1.conf",
                        "node": self.node.label
                    },
                    report_codes.FORCE_FILE_OVERWRITE
                ),
                (
                    Severities.ERROR,
                    report_codes.FILE_ALREADY_EXISTS,
                    {
                        "file_role": None,
                        "file_path": "file1.key",
                        "node": self.node.label
                    },
                    report_codes.FORCE_FILE_OVERWRITE
                )
            ]
        )

    def test_rewrite_existing(self, mock_read_authfiles, mock_read_configs):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = """
        {
            "existing": ["name1.conf", "file1.key"],
            "failed": {},
            "saved": ["name2.conf", "file2.key"]
        }
        """
        lib.send_all_config_to_node(
            self.mock_communicator,
            self.mock_reporter,
            self.node,
            rewrite_existing=True
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertTrue("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVING_ON_NODE,
                    {"node": self.node.label}
                ),
                (
                    Severities.WARNING,
                    report_codes.FILE_ALREADY_EXISTS,
                    {
                        "file_role": None,
                        "file_path": "name1.conf",
                        "node": self.node.label
                    }
                ),
                (
                    Severities.WARNING,
                    report_codes.FILE_ALREADY_EXISTS,
                    {
                        "file_role": None,
                        "file_path": "file1.key",
                        "node": self.node.label
                    }
                ),
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
                    {
                        "node": self.node.label,
                        "name": "name2.conf, file2.key",
                        "name_list": ["name2.conf", "file2.key"]
                    }
                )
            ]
        )

    def test_write_failure(self, mock_read_authfiles, mock_read_configs):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = """
        {
            "existing": [],
            "failed": {
                "name1.conf": "Error message",
                "file1.key": "Another error message"
            },
            "saved": ["name2.conf", "file2.key"]
        }
        """
        assert_raise_library_error(
            lambda: lib.send_all_config_to_node(
                self.mock_communicator, self.mock_reporter, self.node
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_WRITE_ERROR,
                {
                    "node": self.node.label,
                    "name": "name1.conf",
                    "reason": "Error message"
                }
            ),
            (
                Severities.ERROR,
                report_codes.BOOTH_CONFIG_WRITE_ERROR,
                {
                    "node": self.node.label,
                    "name": "file1.key",
                    "reason": "Another error message"
                }
            )
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    Severities.INFO,
                    report_codes.BOOTH_CONFIGS_SAVING_ON_NODE,
                    {"node": self.node.label}
                ),
                (
                    Severities.ERROR,
                    report_codes.BOOTH_CONFIG_WRITE_ERROR,
                    {
                        "node": self.node.label,
                        "name": "name1.conf",
                        "reason": "Error message"
                    }
                ),
                (
                    Severities.ERROR,
                    report_codes.BOOTH_CONFIG_WRITE_ERROR,
                    {
                        "node": self.node.label,
                        "name": "file1.key",
                        "reason": "Another error message"
                    }
                )
            ]
        )

    def test_communication_failure(
        self, mock_read_authfiles, mock_read_configs
    ):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.side_effect = NodeConnectionException(
            self.node.label, "command", "reason"
        )
        assert_raise_library_error(
            lambda: lib.send_all_config_to_node(
                self.mock_communicator, self.mock_reporter, self.node
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": self.node.label,
                    "command": "command",
                    "reason": "reason"
                }
            )
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )

    def test_wrong_response_format(
        self, mock_read_authfiles, mock_read_configs
    ):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = """
            {
                "existing_files": [],
                "failed": {
                    "name1.conf": "Error message",
                    "file1.key": "Another error message"
                },
                "saved": ["name2.conf", "file2.key"]
            }
        """
        assert_raise_library_error(
            lambda: lib.send_all_config_to_node(
                self.mock_communicator, self.mock_reporter, self.node
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": self.node.label}
            )
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )

    def test_response_not_json(self, mock_read_authfiles, mock_read_configs):
        mock_read_configs.return_value = {
            "name1.conf": "config1",
            "name2.conf": "config2"
        }
        mock_read_authfiles.return_value = {
            "file1.key": "some key".encode("utf-8"),
            "file2.key": "another key".encode("utf-8")
        }
        self.mock_communicator.call_node.return_value = "not json"
        assert_raise_library_error(
            lambda: lib.send_all_config_to_node(
                self.mock_communicator, self.mock_reporter, self.node
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": self.node.label}
            )
        )
        mock_read_configs.assert_called_once_with(self.mock_reporter, False)
        mock_read_authfiles.assert_called_once_with(
            self.mock_reporter, ["config1", "config2"]
        )
        self.assertEqual(1, self.mock_communicator.call_node.call_count)
        self.assertEqual(
            self.node, self.mock_communicator.call_node.call_args[0][0]
        )
        self.assertEqual(
            "remote/booth_save_files",
            self.mock_communicator.call_node.call_args[0][1]
        )
        data = url_decode(self.mock_communicator.call_node.call_args[0][2])
        self.assertFalse("rewrite_existing" in data)
        self.assertTrue("data_json" in data)
        self.assertEqual(
            [
                {
                    "name": "name1.conf",
                    "data": "config1",
                    "base64": False
                },
                {
                    "name": "name2.conf",
                    "data": "config2",
                    "base64": False
                },
                {
                    "name": "file1.key",
                    "data": to_b64("some key"),
                    "base64": True
                },
                {
                    "name": "file2.key",
                    "data": to_b64("another key"),
                    "base64": True
                }
            ],
            json.loads(data["data_json"][0])
        )


class PullConfigFromNodeTest(TestCase):
    def setUp(self):
        self.mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        self.node = NodeAddresses("node")

    def test_success(self):
        self.mock_communicator.call_node.return_value = "{}"
        self.assertEqual(
            {}, lib.pull_config_from_node(
                self.mock_communicator, self.node, "booth"
            )
        )
        self.mock_communicator.call_node.assert_called_once_with(
            self.node, "remote/booth_get_config", "name=booth"
        )

    def test_not_json(self):
        self.mock_communicator.call_node.return_value = "not json"
        assert_raise_library_error(
            lambda: lib.pull_config_from_node(
                self.mock_communicator, self.node, "booth"
            ),
            (
                Severities.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {"node": self.node.label}
            )
        )

    def test_communication_failure(self):
        self.mock_communicator.call_node.side_effect = NodeConnectionException(
            self.node.label, "command", "reason"
        )
        assert_raise_library_error(
            lambda: lib.pull_config_from_node(
                self.mock_communicator, self.node, "booth"
            ),
            (
                Severities.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": self.node.label,
                    "command": "command",
                    "reason": "reason"
                }
            )
        )
