from unittest import (
    TestCase,
    mock,
)

from pcs.cli.cluster import command
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.reports import codes as report_codes

from pcs_test.tools.misc import dict_to_modifiers


class ParseNodeAddRemote(TestCase):
    # pylint: disable=protected-access
    def test_deal_with_explicit_address(self):
        self.assertEqual(
            command._node_add_remote_separate_name_and_addr(
                ["name", "address", "a=b"]
            ),
            ("name", "address", ["a=b"]),
        )

    def test_deal_with_implicit_address(self):
        self.assertEqual(
            command._node_add_remote_separate_name_and_addr(["name", "a=b"]),
            ("name", None, ["a=b"]),
        )


class NodeRemoveRemote(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["remote_node"])
        self.remote_node = mock.Mock(spec_set=["node_remove_remote"])
        self.lib.remote_node = self.remote_node

    def _call_cmd(self, argv, modifiers=None):
        command.node_remove_remote(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.remote_node.node_remove_remote.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["A", "B"])
        self.assertIsNone(cm.exception.message)
        self.remote_node.node_remove_remote.assert_not_called()

    def test_success(self):
        self._call_cmd(["A"])
        self.remote_node.node_remove_remote.assert_called_once_with("A", [])

    def test_skip_offline(self):
        self._call_cmd(["A"], {"skip-offline": True})
        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [report_codes.SKIP_OFFLINE_NODES]
        )

    def test_force(self):
        self._call_cmd(["A"], {"force": True})
        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [report_codes.FORCE]
        )

    def test_all_flags(self):
        self._call_cmd(["A"], {"skip-offline": True, "force": True})
        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES]
        )


class ClusterRename(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.lib.cluster = mock.Mock(spec_set=["rename"])

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            command.cluster_rename(self.lib, [], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.lib.cluster.rename.assert_not_called()

    def test_too_many_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            command.cluster_rename(self.lib, ["A", "B"], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.lib.cluster.rename.assert_not_called()

    def test_success(self):
        command.cluster_rename(self.lib, ["A"], dict_to_modifiers({}))
        self.lib.cluster.rename.assert_called_once_with("A", [])

    def test_force(self):
        command.cluster_rename(
            self.lib, ["A"], dict_to_modifiers({"force": True})
        )
        self.lib.cluster.rename.assert_called_once_with(
            "A", [report_codes.FORCE]
        )

    def test_skip_offline(self):
        command.cluster_rename(
            self.lib, ["A"], dict_to_modifiers({"skip-offline": True})
        )
        self.lib.cluster.rename.assert_called_once_with(
            "A", [report_codes.SKIP_OFFLINE_NODES]
        )

    def test_all_flags(self):
        command.cluster_rename(
            self.lib,
            ["A"],
            dict_to_modifiers({"force": True, "skip-offline": True}),
        )
        self.lib.cluster.rename.assert_called_once_with(
            "A", [report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES]
        )
