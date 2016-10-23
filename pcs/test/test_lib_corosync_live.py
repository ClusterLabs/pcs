from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

import os.path

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock

from pcs import settings
from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.lib.node import NodeAddresses
from pcs.lib.external import CommandRunner, NodeCommunicator

from pcs.lib.corosync import live as lib


class GetLocalCorosyncConfTest(TestCase):
    def test_success(self):
        path = rc("corosync.conf")
        settings.corosync_conf_file = path
        self.assertEqual(
            lib.get_local_corosync_conf(),
            open(path).read()
        )

    def test_error(self):
        path = rc("corosync.conf.nonexistent")
        settings.corosync_conf_file = path
        assert_raise_library_error(
            lib.get_local_corosync_conf,
            (
                severity.ERROR,
                report_codes.UNABLE_TO_READ_COROSYNC_CONFIG,
                {
                    "path": path,
                    "reason": "No such file or directory",
                }
            )
        )


class GetLocalClusterConfTest(TestCase):
    def test_success(self):
        path = rc("cluster.conf")
        settings.cluster_conf_file = path
        self.assertEqual(
            lib.get_local_cluster_conf(),
            open(path).read()
        )

    def test_error(self):
        path = rc("cluster.conf.nonexistent")
        settings.cluster_conf_file = path
        assert_raise_library_error(
            lib.get_local_cluster_conf,
            (
                severity.ERROR,
                report_codes.CLUSTER_CONF_READ_ERROR,
                {
                    "path": path,
                    "reason": "No such file or directory",
                }
            )
        )


class SetRemoteCorosyncConfTest(TestCase):
    def test_success(self):
        config = "test {\nconfig: data\n}\n"
        node = NodeAddresses("node1")
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_node.return_value = "dummy return"

        lib.set_remote_corosync_conf(mock_communicator, node, config)

        mock_communicator.call_node.assert_called_once_with(
            node,
            "remote/set_corosync_conf",
            "corosync_conf=test+%7B%0Aconfig%3A+data%0A%7D%0A"
        )


class ReloadConfigTest(TestCase):
    def path(self, name):
        return os.path.join(settings.corosync_binaries, name)

    def test_success(self):
        cmd_retval = 0
        cmd_stdout = "cmd output"
        cmd_stderr = ""
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        lib.reload_config(mock_runner)

        mock_runner.run.assert_called_once_with([
            self.path("corosync-cfgtool"), "-R"
        ])

    def test_error(self):
        cmd_retval = 1
        cmd_stdout = "cmd output"
        cmd_stderr = "cmd error"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        assert_raise_library_error(
            lambda: lib.reload_config(mock_runner),
            (
                severity.ERROR,
                report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                {
                    "reason": "\n".join([cmd_stderr, cmd_stdout]),
                }
            )
        )

        mock_runner.run.assert_called_once_with([
            self.path("corosync-cfgtool"), "-R"
        ])


class GetQuorumStatusTextTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.quorum_tool = "/usr/sbin/corosync-quorumtool"

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.get_quorum_status_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([
            self.quorum_tool, "-p"
        ])

    def test_success_with_retval_1(self):
        self.mock_runner.run.return_value = ("status info", "", 1)
        self.assertEqual(
            "status info",
            lib.get_quorum_status_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([
            self.quorum_tool, "-p"
        ])

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 2)
        assert_raise_library_error(
            lambda: lib.get_quorum_status_text(self.mock_runner),
            (
                severity.ERROR,
                report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
                {
                    "reason": "status error",
                }
            )
        )
        self.mock_runner.run.assert_called_once_with([
            self.quorum_tool, "-p"
        ])


class SetExpectedVotesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def path(self, name):
        return os.path.join(settings.corosync_binaries, name)

    def test_success(self):
        cmd_retval = 0
        cmd_stdout = "cmd output"
        cmd_stderr = ""
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        lib.set_expected_votes(mock_runner, 3)

        mock_runner.run.assert_called_once_with([
            self.path("corosync-quorumtool"), "-e", "3"
        ])

    def test_error(self):
        cmd_retval = 1
        cmd_stdout = "cmd output"
        cmd_stderr = "cmd stderr"
        mock_runner = mock.MagicMock(spec_set=CommandRunner)
        mock_runner.run.return_value = (cmd_stdout, cmd_stderr, cmd_retval)

        assert_raise_library_error(
            lambda: lib.set_expected_votes(mock_runner, 3),
            (
                severity.ERROR,
                report_codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR,
                {
                    "reason": cmd_stderr,
                }
            )
        )

        mock_runner.run.assert_called_once_with([
            self.path("corosync-quorumtool"), "-e", "3"
        ])

