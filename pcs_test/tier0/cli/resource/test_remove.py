from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.resource import resource_remove_cmd

from pcs_test.tools.misc import dict_to_modifiers
from pcs_test.tools.resources_dto import ALL_RESOURCES


@mock.patch("pcs.resource.deprecation_warning")
class RemoveResource(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cib", "resource"])
        self.lib.cib = mock.Mock(spec_set=["remove_elements"])
        self.cib = self.lib.cib
        self.lib.resource = mock.Mock(spec_set=["get_configured_resources"])
        self.resource = self.lib.resource
        self.resource.get_configured_resources.return_value = ALL_RESOURCES

    def _call_cmd(self, argv, modifiers=None):
        resource_remove_cmd(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self, mock_deprecation_warning):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.resource.get_configured_resources.assert_not_called()
        self.cib.remove_elements.assert_not_called()
        mock_deprecation_warning.assert_not_called()

    def test_remove_one(self, mock_deprecation_warning):
        self._call_cmd(["R1"])
        self.resource.get_configured_resources.assert_called_once_with()
        self.cib.remove_elements.assert_called_once_with({"R1"}, set())
        mock_deprecation_warning.assert_not_called()

    def test_remove_multiple(self, mock_deprecation_warning):
        self._call_cmd(["R1", "R2", "R3"])
        self.resource.get_configured_resources.assert_called_once_with()
        self.cib.remove_elements.assert_called_once_with(
            {"R1", "R2", "R3"}, set()
        )
        mock_deprecation_warning.assert_not_called()

    def test_duplicate_args(self, mock_deprecation_warning):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["R1", "R1", "R2", "R3", "R2"])
        self.assertEqual(
            cm.exception.message, "duplicate arguments: 'R1', 'R2'"
        )
        self.resource.get_configured_resources.assert_not_called()
        self.cib.remove_elements.assert_not_called()
        mock_deprecation_warning.assert_not_called()

    def test_not_resource_id(self, mock_deprecation_warning):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["nonexistent"])
        self.assertEqual(
            cm.exception.message, "Unable to find resource: 'nonexistent'"
        )
        self.resource.get_configured_resources.assert_called_once_with()
        self.cib.remove_elements.assert_not_called()
        mock_deprecation_warning.assert_not_called()

    def test_stonith_id(self, mock_deprecation_warning):
        self._call_cmd(["S1"])
        self.resource.get_configured_resources.assert_called_once_with()
        self.cib.remove_elements.assert_called_once_with({"S1"}, set())
        mock_deprecation_warning.assert_called_once_with(
            "Ability of this command to accept stonith resources is deprecated "
            "and will be removed in a future release. Please use "
            "'pcs stonith remove' instead."
        )

    def test_multiple_stonith_ids(self, mock_deprecation_warning):
        self._call_cmd(["S1", "R1", "R2", "R3", "S2"])
        self.resource.get_configured_resources.assert_called_once_with()
        self.cib.remove_elements.assert_called_once_with(
            {"R1", "R2", "R3", "S1", "S2"}, set()
        )
        mock_deprecation_warning.assert_called_once_with(
            "Ability of this command to accept stonith resources is deprecated "
            "and will be removed in a future release. Please use "
            "'pcs stonith remove' instead."
        )
