from unittest import mock, TestCase

from pcs_test.tools.misc import dict_to_modifiers

from pcs.cli import dr
from pcs.cli.common.errors import CmdLineInputError

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
