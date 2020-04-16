from textwrap import dedent
from unittest import mock, TestCase

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.tag import command
from pcs.lib.errors import LibraryError
from pcs_test.tools.misc import dict_to_modifiers


class TagCreate(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["tag"])
        self.tag = mock.Mock(spec_set=["create"])
        self.lib.tag = self.tag

    def _call_cmd(self, argv):
        command.tag_create(self.lib, argv, dict_to_modifiers({}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.tag.create.assert_not_called()

    def test_not_enough_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["arg1"])
        self.assertIsNone(cm.exception.message)
        self.tag.create.assert_not_called()

    def test_minimum_args(self):
        self._call_cmd(["arg1", "arg2"])
        self.tag.create.assert_called_once_with("arg1", ["arg2"])

    def test_empty_args(self):
        self._call_cmd(["", ""])
        self.tag.create.assert_called_once_with("", [""])

    def test_multiple_args(self):
        self._call_cmd(["tagid", "id1", "id2"])
        self.tag.create.assert_called_once_with("tagid", ["id1", "id2"])


@mock.patch("pcs.cli.tag.command.print")
class TagConfig(TestCase):
    tag_dicts = [
        {"tag_id": "tag1", "idref_list": ["i1", "i2", "i3"],},
        {"tag_id": "tag2", "idref_list": ["j1", "j2", "j3"],},
    ]

    def setUp(self):
        self.lib = mock.Mock(spec_set=["tag"])
        self.tag = mock.Mock(spec_set=["config"])
        self.lib.tag = self.tag

    def _call_cmd(self, argv):
        command.tag_config(self.lib, argv, dict_to_modifiers({}))

    def test_no_args_no_tags(self, mock_print):
        self.tag.config.return_value = []
        self._call_cmd([])
        self.tag.config.assert_called_once_with([])
        mock_print.assert_called_once_with(" No tags defined")

    def test_no_args_all_tags(self, mock_print):
        self.tag.config.return_value = self.tag_dicts
        self._call_cmd([])
        self.tag.config.assert_called_once_with([])
        mock_print.assert_called_once_with(
            dedent(
                """\
            tag1
              i1
              i2
              i3
            tag2
              j1
              j2
              j3"""
            )
        )

    def test_specified_tag(self, mock_print):
        self.tag.config.return_value = self.tag_dicts[1:2]
        self._call_cmd(["tag2"])
        self.tag.config.assert_called_once_with(["tag2"])
        mock_print.assert_called_once_with(
            dedent(
                """\
            tag2
              j1
              j2
              j3"""
            )
        )

    def test_specified_another_tag(self, mock_print):
        self.tag.config.return_value = self.tag_dicts[0:1]
        self._call_cmd(["tag1"])
        self.tag.config.assert_called_once_with(["tag1"])
        mock_print.assert_called_once_with(
            dedent(
                """\
            tag1
              i1
              i2
              i3"""
            )
        )

    def test_specified_more_tags_are_printed_in_given_order(self, mock_print):
        self.tag.config.return_value = self.tag_dicts[::-1]
        self._call_cmd(["tag2", "tag1"])
        self.tag.config.assert_called_once_with(["tag2", "tag1"])
        mock_print.assert_called_once_with(
            dedent(
                """\
            tag2
              j1
              j2
              j3
            tag1
              i1
              i2
              i3"""
            )
        )

    def test_no_print_on_exception(self, mock_print):
        self.tag.config.side_effect = LibraryError()
        with self.assertRaises(LibraryError):
            self._call_cmd(["something"])
        self.tag.config.assert_called_once_with(["something"])
        mock_print.assert_not_called()


class TagRemove(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["tag"])
        self.tag = mock.Mock(spec_set=["remove"])
        self.lib.tag = self.tag

    def _call_cmd(self, argv):
        command.tag_remove(self.lib, argv, dict_to_modifiers({}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.tag.remove.assert_not_called()

    def test_minimum_args(self):
        self._call_cmd(["arg1"])
        self.tag.remove.assert_called_once_with(["arg1"])

    def test_more_args(self):
        self._call_cmd(["arg1", "arg2"])
        self.tag.remove.assert_called_once_with(["arg1", "arg2"])
