from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
import logging

from pcs.test.tools.pcs_mock import mock

from pcs.lib.env import LibraryEnvironment

class LibraryEnvironmentTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)

    def test_logger(self):
        env = LibraryEnvironment(self.mock_logger)
        self.assertEqual(self.mock_logger, env.logger)

    def test_user_set(self):
        user = "testuser"
        env = LibraryEnvironment(self.mock_logger, user_login=user)
        self.assertEqual(user, env.user_login)

    def test_user_not_set(self):
        env = LibraryEnvironment(self.mock_logger)
        self.assertEqual(None, env.user_login)

    def test_usergroups_set(self):
        groups = ["some", "group"]
        env = LibraryEnvironment(self.mock_logger, user_groups=groups)
        self.assertEqual(groups, env.user_groups)

    def test_usergroups_not_set(self):
        env = LibraryEnvironment(self.mock_logger)
        self.assertEqual([], env.user_groups)

    @mock.patch("pcs.lib.env.is_cman_cluster")
    def test_is_cman_cluster(self, mock_is_cman):
        mock_is_cman.return_value = True
        env = LibraryEnvironment(self.mock_logger)
        self.assertTrue(env.is_cman_cluster)
        self.assertTrue(env.is_cman_cluster)
        self.assertEqual(1, mock_is_cman.call_count)

    @mock.patch("pcs.lib.env.replace_cib_configuration_xml")
    @mock.patch("pcs.lib.env.get_cib_xml")
    def test_cib_set(self, mock_get_cib, mock_push_cib):
        cib_data = "test cib data"
        new_cib_data = "new test cib data"
        env = LibraryEnvironment(self.mock_logger, cib_data=cib_data)

        self.assertFalse(env.is_cib_live)

        self.assertEqual(cib_data, env.get_cib_xml())
        self.assertEqual(0, mock_get_cib.call_count)

        env.push_cib_xml(new_cib_data)
        self.assertEqual(0, mock_push_cib.call_count)

        self.assertEqual(new_cib_data, env.get_cib_xml())
        self.assertEqual(0, mock_get_cib.call_count)

    @mock.patch("pcs.lib.env.replace_cib_configuration_xml")
    @mock.patch("pcs.lib.env.get_cib_xml")
    def test_cib_not_set(self, mock_get_cib, mock_push_cib):
        cib_data = "test cib data"
        new_cib_data = "new test cib data"
        mock_get_cib.return_value = cib_data
        env = LibraryEnvironment(self.mock_logger)

        self.assertTrue(env.is_cib_live)

        self.assertEqual(cib_data, env.get_cib_xml())
        self.assertEqual(1, mock_get_cib.call_count)

        env.push_cib_xml(new_cib_data)
        self.assertEqual(1, mock_push_cib.call_count)

    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_corosync_conf_set(self, mock_get_corosync):
        corosync_data = "test corosync data"
        new_corosync_data = "new test corosync data"
        env = LibraryEnvironment(
            self.mock_logger,
            corosync_conf_data=corosync_data
        )

        self.assertFalse(env.is_corosync_conf_live)

        self.assertEqual(corosync_data, env.get_corosync_conf())
        self.assertEqual(0, mock_get_corosync.call_count)

        env.push_corosync_conf(new_corosync_data)

        self.assertEqual(new_corosync_data, env.get_corosync_conf())
        self.assertEqual(0, mock_get_corosync.call_count)

    @mock.patch("pcs.lib.env.get_local_corosync_conf")
    def test_corosync_conf_not_set(self, mock_get_corosync):
        corosync_data = "test corosync data"
        new_corosync_data = "new test corosync data"
        mock_get_corosync.return_value = corosync_data
        env = LibraryEnvironment(self.mock_logger)

        self.assertTrue(env.is_corosync_conf_live)

        self.assertEqual(corosync_data, env.get_corosync_conf())
        self.assertEqual(1, mock_get_corosync.call_count)

        self.assertRaises(
            NotImplementedError,
            env.push_corosync_conf,
            new_corosync_data
        )

    @mock.patch("pcs.lib.env.CommandRunner")
    def test_cmd_runner_no_options(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        env = LibraryEnvironment(self.mock_logger)
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(self.mock_logger, {})

    @mock.patch("pcs.lib.env.CommandRunner")
    def test_cmd_runner_all_options(self, mock_runner):
        expected_runner = mock.MagicMock()
        mock_runner.return_value = expected_runner
        user = "testuser"
        env = LibraryEnvironment(self.mock_logger, user_login=user)
        runner = env.cmd_runner()
        self.assertEqual(expected_runner, runner)
        mock_runner.assert_called_once_with(
            self.mock_logger,
            {"CIB_user": user}
        )

    @mock.patch("pcs.lib.env.NodeCommunicator")
    def test_node_communicator_no_options(self, mock_comm):
        expected_comm = mock.MagicMock()
        mock_comm.return_value = expected_comm
        env = LibraryEnvironment(self.mock_logger)
        comm = env.node_communicator()
        self.assertEqual(expected_comm, comm)
        mock_comm.assert_called_once_with(self.mock_logger, {}, None, [])

    @mock.patch("pcs.lib.env.NodeCommunicator")
    def test_node_communicator_all_options(self, mock_comm):
        expected_comm = mock.MagicMock()
        mock_comm.return_value = expected_comm
        user = "testuser"
        groups = ["some", "group"]
        tokens = {"node": "token"}
        env = LibraryEnvironment(
            self.mock_logger,
            user_login=user,
            user_groups=groups,
            auth_tokens_getter=lambda:tokens
        )
        comm = env.node_communicator()
        self.assertEqual(expected_comm, comm)
        mock_comm.assert_called_once_with(
            self.mock_logger,
            tokens,
            user,
            groups
        )
