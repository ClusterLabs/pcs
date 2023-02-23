from unittest import (
    TestCase,
    mock,
)

from pcs.cli.cluster_property import command as cluster_property
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.reports import codes as report_codes

from pcs_test.tools.misc import dict_to_modifiers


class TestSetProperty(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.Mock(spec_set=["set_properties"])
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.set_property(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.cluster_property.set_properties.assert_not_called()

    def test_empty_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["", ""])
        self.assertEqual(cm.exception.message, "missing value of '' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_option_missing_value(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a=1", "b"])
        self.assertEqual(cm.exception.message, "missing value of 'b' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_value_missing_option_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["=1", "b=2"])
        self.assertEqual(cm.exception.message, "missing key in '=1' option")
        self.cluster_property.set_properties.assert_not_called()

    def test_option_multiple_values(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a=1", "a=2", "b=2", "b="])
        self.assertEqual(
            cm.exception.message,
            "duplicate option 'a' with different values '1' and '2'",
        )
        self.cluster_property.set_properties.assert_not_called()

    def test_multiple_args(self):
        self._call_cmd(["a=1", "b=2", "c="])
        self.cluster_property.set_properties.assert_called_once_with(
            {"a": "1", "b": "2", "c": ""}, set()
        )

    def test_multiple_args_with_force(self):
        self._call_cmd(["a=1", "b=2", "c="], {"force": True})
        self.cluster_property.set_properties.assert_called_once_with(
            {"a": "1", "b": "2", "c": ""}, set([report_codes.FORCE])
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"all": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--all' is not supported in this command",
        )
        self.cluster_property.assert_not_called()


class TestUnsetProperty(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster_property"])
        self.cluster_property = mock.Mock(spec_set=["set_properties"])
        self.lib.cluster_property = self.cluster_property

    def _call_cmd(self, argv, modifiers=None):
        cluster_property.unset_property(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.cluster_property.set_properties.assert_not_called()

    def test_args(self):
        self._call_cmd(["a=1", "=b", ""])
        self.cluster_property.set_properties.assert_called_once_with(
            {"a=1": "", "=b": "", "": ""}, set()
        )

    def test_args_with_force(self):
        self._call_cmd(["a=1", "=b", ""], {"force": True})
        self.cluster_property.set_properties.assert_called_once_with(
            {"a=1": "", "=b": "", "": ""}, set([report_codes.FORCE])
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([], {"defaults": True})
        self.assertEqual(
            cm.exception.message,
            "Specified option '--defaults' is not supported in this command",
        )
        self.cluster_property.assert_not_called()

    def test_duplicate_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["a", "a", "b", "b", "c"])
        self.assertEqual(
            cm.exception.message,
            "duplicate arguments: 'a', 'b'",
        )
        self.cluster_property.assert_not_called()
