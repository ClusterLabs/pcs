from unittest import (
    TestCase,
    mock,
)

from pcs import quorum
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.misc import dict_to_modifiers


class LocalQnetdCertsMixin:
    def _call_cmd(self, argv, modifiers=None):
        self.cli_command(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertEqual(
            cm.exception.message,
            "Expected arguments: <qnetd_host> <cluster_name>",
        )
        self.lib_command.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a", "b", "c"])
        self.assertEqual(
            cm.exception.message,
            "Expected arguments: <qnetd_host> <cluster_name>",
        )
        self.lib_command.assert_not_called()

    def test_empty_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["", ""])
        self.assertEqual(
            cm.exception.message,
            "Expected arguments: <qnetd_host> <cluster_name>",
        )
        self.lib_command.assert_not_called()


class CheckLocalQnetdCerts(LocalQnetdCertsMixin, TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["quorum"])
        self.lib.quorum = mock.Mock()
        self.lib_command = self.lib.quorum.device_net_certificate_check_local
        self.cli_command = quorum.check_local_qnetd_certs_cmd

    @mock.patch("pcs.quorum.print")
    def test_success_true(self, mock_print):
        self.lib_command.return_value = True
        self._call_cmd(["a", "b"])
        self.lib_command.assert_called_once_with("a", "b")
        mock_print.assert_called_once_with("certificate present")

    @mock.patch("pcs.quorum.print")
    def test_success_false(self, mock_print):
        self.lib_command.return_value = False
        self._call_cmd(["a", "b"])
        self.lib_command.assert_called_once_with("a", "b")
        mock_print.assert_called_once_with("certificate missing")


class SetupLocalQnetdCerts(LocalQnetdCertsMixin, TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["quorum"])
        self.lib.quorum = mock.Mock()
        self.lib_command = self.lib.quorum.device_net_certificate_setup_local
        self.cli_command = quorum.setup_local_qnetd_certs_cmd

    def test_success(self):
        self._call_cmd(["a", "b"])
        self.lib_command.assert_called_once_with("a", "b")
