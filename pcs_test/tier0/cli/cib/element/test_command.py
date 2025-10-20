from unittest import TestCase, mock

from pcs.cli.cib.element import command
from pcs.cli.common.errors import CmdLineInputError

from pcs_test.tools.misc import dict_to_modifiers


class Description(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cib"])
        self.lib.cib = mock.Mock(
            spec_set=["element_description_get", "element_description_set"]
        )

    def _call_cmd(self, argv=None):
        command.description(self.lib, argv or [], dict_to_modifiers({}))

    def test_success_set(self):
        self._call_cmd(["a", "description"])
        self.lib.cib.element_description_set.assert_called_once_with(
            "a", "description"
        )
        self.lib.cib.element_description_get.assert_not_called()

    @mock.patch("pcs.cli.cib.element.command.print")
    def test_success_get(self, mock_print):
        self.lib.cib.element_description_get.return_value = "AAA"
        self._call_cmd(["a"])
        self.lib.cib.element_description_set.assert_not_called()
        self.lib.cib.element_description_get.assert_called_once_with("a")
        mock_print.assert_called_once_with("AAA")

    @mock.patch("pcs.cli.cib.element.command.print")
    def test_success_get_no_description(self, mock_print):
        self.lib.cib.element_description_get.return_value = ""
        self._call_cmd(["a"])
        self.lib.cib.element_description_set.assert_not_called()
        self.lib.cib.element_description_get.assert_called_once_with("a")
        mock_print.assert_not_called()

    def test_bad_number_of_args(self):
        bad_args = [
            [],
            ["a", "b", "c"],
        ]
        for argv in bad_args:
            with self.subTest(argv=argv):
                with self.assertRaises(CmdLineInputError) as cm:
                    self._call_cmd(argv)
                self.assertIsNone(cm.exception.message)
                self.lib.cib.element_description_set.assert_not_called()
                self.lib.cib.element_description_get.assert_not_called()
