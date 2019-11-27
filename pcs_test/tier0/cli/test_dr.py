from textwrap import dedent
from unittest import mock, TestCase

from pcs_test.tools.misc import dict_to_modifiers

from pcs.cli import dr
from pcs.cli.common.errors import CmdLineInputError


@mock.patch("pcs.cli.dr.print")
class Config(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["dr"])
        self.lib.dr = mock.Mock(spec_set=["get_config"])

    def _call_cmd(self, argv=None):
        dr.config(self.lib, argv or [], dict_to_modifiers({}))

    def test_argv(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["x"])
        self.assertIsNone(cm.exception.message)
        mock_print.assert_not_called()

    def test_success(self, mock_print):
        self.lib.dr.get_config.return_value = {
            "local_site": {
                "node_list": [],
                "site_role": "RECOVERY",
            },
            "remote_site_list": [
                {
                    "node_list": [
                        {"name": "nodeA2"},
                        {"name": "nodeA1"},
                    ],
                    "site_role": "PRIMARY",
                },
                {
                    "node_list": [
                        {"name": "nodeB1"},
                    ],
                    "site_role": "RECOVERY",
                }
            ],
        }
        self._call_cmd([])
        self.lib.dr.get_config.assert_called_once_with()
        mock_print.assert_called_once_with(dedent("""\
            Local site:
              Role: Recovery
            Remote site:
              Role: Primary
              Nodes:
                nodeA1
                nodeA2
            Remote site:
              Role: Recovery
              Nodes:
                nodeB1"""))

    @mock.patch("pcs.cli.common.console_report.sys.stderr.write")
    def test_invalid_response(self, mock_stderr, mock_print):
        self.lib.dr.get_config.return_value = [
            "wrong response",
            {"x": "y"},
        ]
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd([])
        self.assertEqual(cm.exception.code, 1)
        self.lib.dr.get_config.assert_called_once_with()
        mock_print.assert_not_called()
        mock_stderr.assert_called_once_with(
            "Error: Unable to communicate with pcsd, received response:\n"
                "['wrong response', {'x': 'y'}]\n"
        )


class SetRecoverySite(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["dr"])
        self.dr = mock.Mock(spec_set=["set_recovery_site"])
        self.lib.dr = self.dr

    def call_cmd(self, argv):
        dr.set_recovery_site(self.lib, argv, dict_to_modifiers({}))

    def test_no_node(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_multiple_nodes(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node1", "node2"])
        self.assertIsNone(cm.exception.message)

    def test_success(self):
        node = "node"
        self.call_cmd([node])
        self.dr.set_recovery_site.assert_called_once_with(node)


@mock.patch("pcs.cli.dr.print")
class Status(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["dr"])
        self.lib.dr = mock.Mock(spec_set=["status_all_sites_plaintext"])

    def _call_cmd(self, argv, modifiers=None):
        dr.status(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def _fixture_response(self, local_success=True, remote_success=True):
        self.lib.dr.status_all_sites_plaintext.return_value = [
            {
                "local_site": True,
                "site_role": "PRIMARY",
                "status_plaintext": (
                    "local cluster\nstatus" if local_success
                    else "this should never be displayed"
                ),
                "status_successfully_obtained": local_success,
            },
            {
                "local_site": False,
                "site_role": "RECOVERY",
                "status_plaintext": (
                    "remote cluster\nstatus" if remote_success
                    else "this should never be displayed"
                ),
                "status_successfully_obtained": remote_success,
            },
        ]

    @staticmethod
    def _fixture_print():
        return dedent("""\
            --- Local cluster - Primary site ---
            local cluster
            status


            --- Remote cluster - Recovery site ---
            remote cluster
            status"""
        )

    def test_argv(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["x"])
        self.assertIsNone(cm.exception.message)
        mock_print.assert_not_called()

    def test_success(self, mock_print):
        self._fixture_response()
        self._call_cmd([])
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=False
        )
        mock_print.assert_called_once_with(self._fixture_print())

    def test_success_full(self, mock_print):
        self._fixture_response()
        self._call_cmd([], {"full": True})
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=True
        )
        mock_print.assert_called_once_with(self._fixture_print())

    def test_success_hide_inactive(self, mock_print):
        self._fixture_response()
        self._call_cmd([], {"hide-inactive": True})
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=True, verbose=False
        )
        mock_print.assert_called_once_with(self._fixture_print())

    def test_success_all_flags(self, mock_print):
        self._fixture_response()
        self._call_cmd([], {"full": True, "hide-inactive": True})
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=True, verbose=True
        )
        mock_print.assert_called_once_with(self._fixture_print())

    @mock.patch("pcs.cli.common.console_report.sys.stderr.write")
    def test_error_local(self, mock_stderr, mock_print):
        self._fixture_response(local_success=False)
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd([])
        self.assertEqual(cm.exception.code, 1)
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=False
        )
        mock_print.assert_called_once_with(dedent("""\
            --- Local cluster - Primary site ---
            Error: Unable to get status of the cluster from any node

            --- Remote cluster - Recovery site ---
            remote cluster
            status"""
        ))
        mock_stderr.assert_called_once_with(
            "Error: Unable to get status of all sites\n"
        )

    @mock.patch("pcs.cli.common.console_report.sys.stderr.write")
    def test_error_remote(self, mock_stderr, mock_print):
        self._fixture_response(remote_success=False)
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd([])
        self.assertEqual(cm.exception.code, 1)
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=False
        )
        mock_print.assert_called_once_with(dedent("""\
            --- Local cluster - Primary site ---
            local cluster
            status


            --- Remote cluster - Recovery site ---
            Error: Unable to get status of the cluster from any node"""
        ))
        mock_stderr.assert_called_once_with(
            "Error: Unable to get status of all sites\n"
        )

    @mock.patch("pcs.cli.common.console_report.sys.stderr.write")
    def test_error_both(self, mock_stderr, mock_print):
        self._fixture_response(local_success=False, remote_success=False)
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd([])
        self.assertEqual(cm.exception.code, 1)
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=False
        )
        mock_print.assert_called_once_with(dedent("""\
            --- Local cluster - Primary site ---
            Error: Unable to get status of the cluster from any node

            --- Remote cluster - Recovery site ---
            Error: Unable to get status of the cluster from any node"""
        ))
        mock_stderr.assert_called_once_with(
            "Error: Unable to get status of all sites\n"
        )

    @mock.patch("pcs.cli.common.console_report.sys.stderr.write")
    def test_invalid_response(self, mock_stderr, mock_print):
        self.lib.dr.status_all_sites_plaintext.return_value = [
            "wrong response",
            {"x": "y"},
        ]
        with self.assertRaises(SystemExit) as cm:
            self._call_cmd([])
        self.assertEqual(cm.exception.code, 1)
        self.lib.dr.status_all_sites_plaintext.assert_called_once_with(
            hide_inactive_resources=False, verbose=False
        )
        mock_print.assert_not_called()
        mock_stderr.assert_called_once_with(
            "Error: Unable to communicate with pcsd, received response:\n"
                "['wrong response', {'x': 'y'}]\n"
        )
