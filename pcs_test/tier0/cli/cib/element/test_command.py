from unittest import TestCase, mock

from pcs.cli.cib.element import command
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.misc import dict_to_modifiers


class Description(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cib"])
        self.lib.cib = mock.Mock(spec_set=["set_description"])

    def _call_cmd(self, argv=None):
        command.description(self.lib, argv or [], dict_to_modifiers({}))

    def test_success_set(self):
        self._call_cmd(["a", "description"])
        self.lib.cib.set_description.assert_called_once_with("a", "description")

    def test_bad_number_of_args(self):
        bad_args = [
            [],
            ["a"],
            ["a", "b", "c"],
        ]
        for argv in bad_args:
            with self.subTest(argv=argv):
                with self.assertRaises(CmdLineInputError) as cm:
                    self._call_cmd(argv)
                self.assertIsNone(cm.exception.message)
                self.lib.cib.set_description.assert_not_called()
