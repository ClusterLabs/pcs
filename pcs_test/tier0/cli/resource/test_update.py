from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.resource import command
from pcs.common import reports

from pcs_test.tools.misc import dict_to_modifiers

RESOURCE_ID = "resource-id"


class ResourceMeta(TestCase):
    command = staticmethod(command.meta)

    def setUp(self):
        self.lib = mock.Mock(spec_set=["resource", "cluster"])

        self.lib.resource = mock.Mock(
            spec_set=[
                "update_meta",
                "is_any_stonith",
                "is_any_resource_except_stonith",
            ]
        )
        self.lib.resource.update_meta = self.update_meta = mock.Mock()

        mock_get_resource_status_msg_patcher = mock.patch(
            "pcs.cli.resource.command.get_resource_status_msg"
        )
        self.addCleanup(mock_get_resource_status_msg_patcher.stop)
        self.mock_get_resource_status_msg = (
            mock_get_resource_status_msg_patcher.start()
        )

        self.lib.resource.is_any_stonith = mock.Mock()
        self.lib.resource.is_any_stonith.return_value = False

        self.lib.cluster = mock.Mock(spec_set=["wait_for_pcmk_idle"])
        self.lib.cluster.wait_for_pcmk_idle = self.wait_for_pcmk_idle = (
            mock.Mock()
        )

    def _assert_no_wait_or_stonith(self):
        self.lib.resource.is_any_stonith.assert_called_once_with([RESOURCE_ID])
        self.wait_for_pcmk_idle.assert_not_called()
        self.mock_get_resource_status_msg.assert_not_called()

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.command(self.lib, [], dict_to_modifiers({}))
        self.assertIsNone(cm.exception.message)
        self.lib.resource.is_any_stonith.assert_not_called()
        self.update_meta.assert_not_called()
        self.wait_for_pcmk_idle.assert_not_called()

    def test_duplicate_attrs(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.command(
                self.lib,
                [RESOURCE_ID, "meta-attr1=value1", "meta-attr1=value2"],
                dict_to_modifiers({}),
            )
        self.assertEqual(
            cm.exception.message,
            "duplicate option 'meta-attr1' with different values 'value1' and "
            "'value2'",
        )
        self.update_meta.assert_not_called()
        self._assert_no_wait_or_stonith()

    def test_one_attr(self):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        self._assert_no_wait_or_stonith()

    @mock.patch("pcs.cli.resource.common.deprecation_warning")
    def test_stonith_deprecation(self, mock_warning):
        self.lib.resource.is_any_stonith.return_value = True
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        mock_warning.assert_called_once_with(
            "Ability of this command to accept stonith resources is deprecated "
            "and will be removed in a future release. Please use 'pcs stonith "
            "meta' instead."
        )
        self._assert_no_wait_or_stonith()

    def test_multiple_attrs(self):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1", "meta-attr2=value2"],
            dict_to_modifiers({}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1", "meta-attr2": "value2"}, []
        )
        self._assert_no_wait_or_stonith()

    @mock.patch("pcs.cli.resource.command.print")
    def test_with_wait_zero(self, _):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({"wait": "0"}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        self.lib.resource.is_any_stonith.assert_called_once_with([RESOURCE_ID])
        self.wait_for_pcmk_idle.assert_called_once_with(0)

    @mock.patch("pcs.cli.resource.command.print")
    @mock.patch("pcs.cli.stonith.command.print")
    def test_with_wait_timeout(self, _a, _b):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({"wait": "30"}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, []
        )
        self.wait_for_pcmk_idle.assert_called_once_with(30)
        self.mock_get_resource_status_msg.assert_called_once_with(
            mock.ANY, RESOURCE_ID
        )

    def test_with_force(self):
        self.command(
            self.lib,
            [RESOURCE_ID, "meta-attr1=value1"],
            dict_to_modifiers({"force": True}),
        )
        self.update_meta.assert_called_once_with(
            RESOURCE_ID, {"meta-attr1": "value1"}, [reports.codes.FORCE]
        )
        self.mock_get_resource_status_msg.assert_not_called()
        self._assert_no_wait_or_stonith()
