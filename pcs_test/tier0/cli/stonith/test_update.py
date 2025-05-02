from unittest import mock

from pcs.cli.stonith import command

from pcs_test.tier0.cli.resource.test_update import ResourceMeta
from pcs_test.tools.misc import dict_to_modifiers

RESOURCE_ID = "resource-id"


class StonithMeta(ResourceMeta):
    command = staticmethod(command.meta)

    def setUp(self):
        super().setUp()
        self.lib.resource.is_any_resource_except_stonith = mock.Mock()
        self.lib.resource.is_any_resource_except_stonith.return_value = False

        mock_get_resource_status_msg_patcher = mock.patch(
            "pcs.cli.stonith.command.get_resource_status_msg"
        )
        self.addCleanup(mock_get_resource_status_msg_patcher.stop)
        self.mock_get_resource_status_msg = (
            mock_get_resource_status_msg_patcher.start()
        )

    def _assert_no_wait_or_stonith(self):
        self.lib.resource.is_any_resource_except_stonith.assert_called_once_with(
            [RESOURCE_ID]
        )
        self.wait_for_pcmk_idle.assert_not_called()
        self.mock_get_resource_status_msg.assert_not_called()

    @mock.patch("pcs.cli.stonith.common.deprecation_warning")
    def test_stonith_deprecation(self, mock_warning):
        self.lib.resource.is_any_resource_except_stonith.return_value = True
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        mock_warning.assert_called_once_with(
            "Ability of this command to accept resources is deprecated and "
            "will be removed in a future release. Please use 'pcs resource "
            "meta' instead."
        )
        self._assert_no_wait_or_stonith()

    @mock.patch("pcs.cli.stonith.command.print")
    def test_with_wait_zero(self, _):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({"wait": "0"}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        self.lib.resource.is_any_resource_except_stonith.assert_called_once_with(
            [RESOURCE_ID]
        )
        self.wait_for_pcmk_idle.assert_called_once_with(0)
