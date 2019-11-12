from unittest import mock, TestCase

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.tag import command
from pcs_test.tools.misc import dict_to_modifiers

class TagCreate(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["tag"])
        self.tag = mock.Mock(spec_set=["create"])
        self.lib.tag = self.tag

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            command.tag_create(self.lib, [], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.tag.create.assert_not_called()

    def test_not_enough_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            command.tag_create(self.lib, ["arg1"], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.tag.create.assert_not_called()

    def test_minimum_args(self):
        command.tag_create(self.lib, ["arg1", "arg2"], dict_to_modifiers({}))
        self.tag.create.assert_called_once_with("arg1", ["arg2"])

    def test_empty_args(self):
        command.tag_create(self.lib, ["", ""], dict_to_modifiers({}))
        self.tag.create.assert_called_once_with("", [""])

    def test_multiple_args(self):
        command.tag_create(
            self.lib,
            ["tagid", "id1", "id2"],
            dict_to_modifiers({}),
        )
        self.tag.create.assert_called_once_with("tagid", ["id1", "id2"])
