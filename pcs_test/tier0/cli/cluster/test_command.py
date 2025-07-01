from unittest import (
    TestCase,
    mock,
)

from pcs.cli.cluster import command
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.lib.errors import LibraryError

from pcs_test.tools.misc import dict_to_modifiers

UNSTOPPED_RESOURCES_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.CannotRemoveResourcesNotStopped(["A"])
)
NODE_NOT_FOUND_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.NodeNotFound("A", ["remote"])
)
FORCEABLE_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.NodeNotFound("A", ["remote"]),
    force_code=reports.codes.FORCE,
)
INFO_REPORT = reports.ReportItem.info(
    reports.messages.CibRemoveDependantElements({})
)


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


class NodeRemoveRemoteBase:
    def setUp(self):
        self.lib = mock.Mock(
            spec_set=["cluster", "env", "remote_node", "resource"]
        )

        self.lib.remote_node = mock.Mock(
            spec_set=["get_resource_ids", "node_remove_remote"]
        )
        self.remote_node = self.lib.remote_node

        self.lib.cluster = mock.Mock(spec_set=["wait_for_pcmk_idle"])
        self.cluster = self.lib.cluster

        self.lib.resource = mock.Mock(spec_set=["stop"])
        self.resource = self.lib.resource

    def _call_cmd(self, argv, modifiers=None):
        command.node_remove_remote(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self, mock_process_library_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.remote_node.node_remove_remote.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_too_many_args(self, mock_process_library_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["A", "B"])
        self.assertIsNone(cm.exception.message)
        self.remote_node.node_remove_remote.assert_not_called()
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_success(self, mock_process_library_reports, mock_reports):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["A"])

        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_success_with_debug(
        self, mock_process_library_reports, mock_reports
    ):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["A"], {"debug": True})

        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=True
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_skip_offline(self, mock_process_library_reports, mock_reports):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["A"], {"skip-offline": True})

        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [reports.codes.SKIP_OFFLINE_NODES]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_dont_stop_me_now(self, mock_process_library_reports, mock_reports):
        self._call_cmd(["A"], {"no-stop": True})

        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_no_stop_all_force_flags(
        self, mock_process_library_reports, mock_reports
    ):
        self._call_cmd(
            ["A"], {"force": True, "no-stop": True, "skip-offline": True}
        )

        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [reports.codes.FORCE, reports.codes.SKIP_OFFLINE_NODES]
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_remove_not_stopped(
        self, mock_process_library_reports, mock_reports
    ):
        self.remote_node.node_remove_remote.side_effect = [LibraryError(), None]
        mock_reports.return_value = [UNSTOPPED_RESOURCES_ERROR_REPORT]
        self.remote_node.get_resource_ids.return_value = ["A"]

        self._call_cmd(["A"])
        self.remote_node.node_remove_remote.assert_has_calls(
            [mock.call("A", []), mock.call("A", [])]
        )
        self.assertEqual(self.remote_node.node_remove_remote.call_count, 2)
        self.remote_node.get_resource_ids.assert_called_once_with("A")
        self.resource.stop.assert_called_once_with(
            self.remote_node.get_resource_ids.return_value,
            [],
        )
        self.cluster.wait_for_pcmk_idle.assert_called_once_with(None)
        mock_process_library_reports.assert_not_called()

    def test_remove_more_errors(
        self, mock_process_library_reports, mock_reports
    ):
        self.remote_node.node_remove_remote.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            UNSTOPPED_RESOURCES_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(LibraryError, lambda: self._call_cmd(["A"]))

        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        mock_process_library_reports.assert_called_once_with(
            [NODE_NOT_FOUND_ERROR_REPORT],
            include_debug=False,
            exit_on_error=False,
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_remove_more_errors_debug(
        self, mock_process_library_reports, mock_reports
    ):
        self.remote_node.node_remove_remote.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            UNSTOPPED_RESOURCES_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError, lambda: self._call_cmd(["A"], {"debug": True})
        )

        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        mock_process_library_reports.assert_called_once_with(
            [NODE_NOT_FOUND_ERROR_REPORT],
            include_debug=True,
            exit_on_error=False,
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_mutually_exclusive_options(
        self, mock_process_library_reports, mock_reports
    ):
        with self.assertRaises(CmdLineInputError) as cm:
            command.node_remove_remote(
                self.lib,
                ["R1"],
                InputModifiers({"-f": "foo", "--no-stop": True}),
            )
        self.assertEqual(
            cm.exception.message, "Only one of '--no-stop', '-f' can be used"
        )
        self.remote_node.node_remove_remote.assert_not_called()
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    # future force skip-offline combo


@mock.patch(
    "pcs.common.reports.processor.ReportProcessorInMemory.reports",
    new_callable=mock.PropertyMock,
)
@mock.patch("pcs.cli.cluster.command.process_library_reports")
class NodeRemoveRemote(NodeRemoveRemoteBase, TestCase):
    @mock.patch("pcs.cli.cluster.command.deprecation_warning")
    def test_remove_force(
        self,
        mock_deprecation_warning,
        mock_process_library_reports,
        mock_reports,
    ):
        self._call_cmd(["A"], {"force": True})

        mock_deprecation_warning.assert_called_once()
        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [reports.codes.FORCE]
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()


@mock.patch(
    "pcs.common.reports.processor.ReportProcessorInMemory.reports",
    new_callable=mock.PropertyMock,
)
@mock.patch("pcs.cli.cluster.command.process_library_reports")
class NodeRemoveRemoteFuture(NodeRemoveRemoteBase, TestCase):
    def _call_cmd(self, argv, modifiers=None):
        default_modifiers = {"future": True}
        command.node_remove_remote(
            self.lib,
            argv,
            dict_to_modifiers(
                modifiers | default_modifiers
                if modifiers
                else default_modifiers
            ),
        )

    def test_remove_force_forceable_error(
        self, mock_process_library_reports, mock_reports
    ):
        self.remote_node.node_remove_remote.side_effect = [LibraryError(), None]
        mock_reports.return_value = [FORCEABLE_ERROR_REPORT]
        self.remote_node.get_resource_ids.return_value = ["A"]

        self._call_cmd("A", {"force": True})
        self.remote_node.node_remove_remote.assert_has_calls(
            [mock.call("A", []), mock.call("A", [reports.codes.FORCE])]
        )
        self.assertEqual(self.remote_node.node_remove_remote.call_count, 2)
        self.remote_node.get_resource_ids.assert_called_once_with("A")
        self.resource.stop.assert_called_once_with(
            self.remote_node.get_resource_ids.return_value,
            [reports.codes.FORCE],
        )
        self.cluster.wait_for_pcmk_idle.assert_called_once_with(None)
        mock_process_library_reports.assert_not_called()

    def test_remove_force_more_errors_not_forceable(
        self, mock_process_library_reports, mock_reports
    ):
        self.remote_node.node_remove_remote.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            FORCEABLE_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError, lambda: self._call_cmd("A", {"force": True})
        )
        self.remote_node.node_remove_remote.assert_called_once_with("A", [])
        mock_process_library_reports.assert_called_once_with(
            [
                reports.item.ReportItem.warning(
                    reports.messages.NodeNotFound("A", ["remote"])
                ),
                NODE_NOT_FOUND_ERROR_REPORT,
            ],
            include_debug=False,
            exit_on_error=False,
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()

    def test_remove_with_force_and_skip_offline(
        self, mock_process_library_reports, mock_reports
    ):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["A"], {"force": True, "skip-offline": True})

        self.remote_node.node_remove_remote.assert_called_once_with(
            "A", [reports.codes.SKIP_OFFLINE_NODES]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )
        self.remote_node.get_resource_ids.assert_not_called()
        self.resource.stop.assert_not_called()
        self.cluster.wait_for_pcmk_idle.assert_not_called()


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
