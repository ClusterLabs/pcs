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
        self.lib.env = mock.Mock(spec_set=["report_processor"])
        self.lib.remote_node = mock.Mock(
            spec_set=["get_resource_ids", "node_remove_remote"]
        )
        self.lib.cluster = mock.Mock(spec_set=["wait_for_pcmk_idle"])
        self.lib.resource = mock.Mock(spec_set=["stop"])

        self.report_processor_patcher = mock.patch(
            "pcs.cli.cluster.command.NodeRemoveRemoteReportProcessor",
            new_callable=mock.Mock,
            spec_set=["reports", "already_reported_to_console"],
        )
        self.report_processor = self.report_processor_patcher.start()
        self.report_processor.reports = mock.PropertyMock(return_value=[])
        self.report_processor.already_reported_to_console = mock.PropertyMock(
            return_value=False
        )
        # https://docs.python.org/3/library/unittest.mock.html#unittest.mock.PropertyMock
        # We need to attach PropertyMocks to the mock type objects
        type(
            self.report_processor.return_value
        ).reports = self.report_processor.reports
        type(
            self.report_processor.return_value
        ).already_reported_to_console = (
            self.report_processor.already_reported_to_console
        )

    def tearDown(self):
        self.report_processor_patcher.stop()

    def _call_cmd(self, argv, modifiers=None):
        command.node_remove_remote(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def assert_lib_calls(self, expected_calls):
        self.lib.assert_has_calls(expected_calls)
        self.assertEqual(len(self.lib.mock_calls), len(expected_calls))

    def test_no_args(self, mock_process_library_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.assert_lib_calls([])
        self.report_processor.assert_not_called()
        self.report_processor.reports.assert_not_called()
        self.report_processor.already_reported_to_console.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_too_many_args(self, mock_process_library_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["A", "B"])
        self.assertIsNone(cm.exception.message)
        self.assert_lib_calls([])
        self.report_processor.assert_not_called()
        self.report_processor.reports.assert_not_called()
        self.report_processor.already_reported_to_console.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_success_should_print_reports(self, mock_process_library_reports):
        self.report_processor.reports.return_value = [INFO_REPORT]
        self.report_processor.already_reported_to_console.return_value = False
        self._call_cmd(["A"])

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )

    def test_success_reports_already_reported(
        self, mock_process_library_reports
    ):
        self.report_processor.already_reported_to_console.return_value = True
        self._call_cmd(["A"])

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_not_called()

    def test_success_with_debug(self, mock_process_library_reports):
        self.report_processor.reports.return_value = [INFO_REPORT]
        self.report_processor.already_reported_to_console.return_value = False
        self._call_cmd(["A"], {"debug": True})

        self.report_processor.assert_called_once_with(True)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=True
        )

    def test_skip_offline(self, mock_process_library_reports):
        self.report_processor.reports.return_value = [INFO_REPORT]
        self.report_processor.already_reported_to_console.return_value = False
        self._call_cmd(["A"], {"skip-offline": True})

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(
                    "A", [reports.codes.SKIP_OFFLINE_NODES]
                )
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )

    def test_dont_stop_me_now(self, mock_process_library_reports):
        self._call_cmd(["A"], {"no-stop": True})

        self.report_processor.assert_not_called()
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_not_called()

    def test_no_stop_all_force_flags(self, mock_process_library_reports):
        self._call_cmd(
            ["A"], {"force": True, "no-stop": True, "skip-offline": True}
        )

        self.report_processor.assert_not_called()
        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(
                    "A", [reports.codes.FORCE, reports.codes.SKIP_OFFLINE_NODES]
                )
            ]
        )
        mock_process_library_reports.assert_not_called()

    def test_remove_not_stopped(self, mock_process_library_reports):
        node_identifier = "A"
        resource_ids = ["B"]
        force_flags = []
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.report_processor.reports.return_value = [
            UNSTOPPED_RESOURCES_ERROR_REPORT
        ]
        self.lib.remote_node.get_resource_ids.return_value = resource_ids

        self._call_cmd([node_identifier])

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(node_identifier, []),
                mock.call.remote_node.get_resource_ids(node_identifier),
                mock.call.resource.stop(resource_ids, force_flags),
                mock.call.cluster.wait_for_pcmk_idle(None),
                mock.call.remote_node.node_remove_remote(
                    node_identifier, force_flags
                ),
            ]
        )
        mock_process_library_reports.assert_not_called()

    def test_remove_more_errors_should_print_reports(
        self, mock_process_library_reports
    ):
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.report_processor.reports.return_value = [
            UNSTOPPED_RESOURCES_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(LibraryError, lambda: self._call_cmd(["A"]))

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_called_once_with(
            [NODE_NOT_FOUND_ERROR_REPORT],
            include_debug=False,
            exit_on_error=False,
        )

    def test_remove_more_errors_reports_already_reported(
        self, mock_process_library_reports
    ):
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.report_processor.already_reported_to_console.return_value = True

        self.assertRaises(LibraryError, lambda: self._call_cmd(["A"]))

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_not_called()

    def test_remove_more_errors_debug(self, mock_process_library_reports):
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.report_processor.reports.return_value = [
            UNSTOPPED_RESOURCES_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError, lambda: self._call_cmd(["A"], {"debug": True})
        )

        self.report_processor.assert_called_once_with(True)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
        mock_process_library_reports.assert_called_once_with(
            [NODE_NOT_FOUND_ERROR_REPORT],
            include_debug=True,
            exit_on_error=False,
        )

    def test_mutually_exclusive_options(self, mock_process_library_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            command.node_remove_remote(
                self.lib,
                ["R1"],
                InputModifiers({"-f": "foo", "--no-stop": True}),
            )
        self.assertEqual(
            cm.exception.message, "Only one of '--no-stop', '-f' can be used"
        )
        self.assert_lib_calls([])
        mock_process_library_reports.assert_not_called()


@mock.patch("pcs.cli.cluster.command.process_library_reports")
class NodeRemoveRemote(NodeRemoveRemoteBase, TestCase):
    @mock.patch("pcs.cli.cluster.command.deprecation_warning")
    def test_remove_force(
        self, mock_deprecation_warning, mock_process_library_reports
    ):
        self._call_cmd(["A"], {"force": True})

        mock_deprecation_warning.assert_called_once()
        self.report_processor.assert_not_called()
        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(
                    "A", [reports.codes.FORCE]
                )
            ]
        )
        mock_process_library_reports.assert_not_called()


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

    def test_remove_force_forceable_error(self, mock_process_library_reports):
        node_identifier = "A"
        resource_ids = ["B"]
        force_flags = [reports.codes.FORCE]
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.lib.remote_node.get_resource_ids.return_value = resource_ids
        self.report_processor.reports.return_value = [FORCEABLE_ERROR_REPORT]

        self._call_cmd([node_identifier], {"force": True})

        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(node_identifier, []),
                mock.call.remote_node.get_resource_ids(node_identifier),
                mock.call.resource.stop(resource_ids, force_flags),
                mock.call.cluster.wait_for_pcmk_idle(None),
                mock.call.remote_node.node_remove_remote(
                    node_identifier, force_flags
                ),
            ]
        )
        mock_process_library_reports.assert_not_called()

    def test_remove_force_more_errors_not_forceable(
        self, mock_process_library_reports
    ):
        self.lib.remote_node.node_remove_remote.side_effect = [
            LibraryError(),
            None,
        ]
        self.report_processor.reports.return_value = [
            FORCEABLE_ERROR_REPORT,
            NODE_NOT_FOUND_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError, lambda: self._call_cmd(["A"], {"force": True})
        )
        self.report_processor.assert_called_once_with(False)
        self.assert_lib_calls(
            [mock.call.remote_node.node_remove_remote("A", [])]
        )
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

    def test_remove_with_force_and_skip_offline(
        self, mock_process_library_reports
    ):
        self.report_processor.reports.return_value = [INFO_REPORT]
        self._call_cmd(["A"], {"force": True, "skip-offline": True})

        self.assert_lib_calls(
            [
                mock.call.remote_node.node_remove_remote(
                    "A", [reports.codes.SKIP_OFFLINE_NODES]
                )
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )


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
