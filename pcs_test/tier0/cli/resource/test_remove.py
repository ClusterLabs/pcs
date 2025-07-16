from unittest import (
    TestCase,
    mock,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.resource import command
from pcs.common import reports
from pcs.lib.errors import LibraryError

from pcs_test.tools.misc import dict_to_modifiers
from pcs_test.tools.resources_dto import ALL_RESOURCES

CANNOT_STOP_RESOURCES_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.CannotRemoveResourcesNotStopped(["R1"])
)
NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.NoStonithMeansWouldBeLeft()
)
FORCEABLE_ERROR_REPORT = reports.ReportItem.error(
    reports.messages.NoStonithMeansWouldBeLeft(), force_code=reports.codes.FORCE
)
INFO_REPORT = reports.ReportItem.info(
    reports.messages.CibRemoveDependantElements({})
)


class RemoveResourceBase:
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cib", "cluster", "env", "resource"])

        self.lib.env = mock.Mock(spec_set=["report_processor"])
        self.lib.cib = mock.Mock(spec_set=["remove_elements"])
        self.lib.cluster = mock.Mock(spec_set=["wait_for_pcmk_idle"])
        self.lib.resource = mock.Mock(
            spec_set=["stop", "get_configured_resources"]
        )
        self.lib.resource.get_configured_resources.return_value = ALL_RESOURCES

    def _call_cmd(self, argv, modifiers=None):
        command.remove(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def assert_lib_calls(self, expected_calls):
        self.lib.assert_has_calls(expected_calls)
        self.assertEqual(len(self.lib.mock_calls), len(expected_calls))

    def test_no_args(self, mock_process_lib_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd([])
        self.assertIsNone(cm.exception.message)
        self.assert_lib_calls([])
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()

    def test_duplicate_args(self, mock_process_lib_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["R1", "R1", "R2", "R3", "R2"])
        self.assertEqual(
            cm.exception.message, "duplicate arguments: 'R1', 'R2'"
        )
        self.assert_lib_calls([])
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()

    def test_not_resource_id(self, mock_process_lib_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["nonexistent"])

        self.assertEqual(
            cm.exception.message, "Unable to find resource: 'nonexistent'"
        )
        self.assert_lib_calls([mock.call.resource.get_configured_resources()])
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()

    def test_stonith_id(self, mock_process_lib_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["S1"])

        self.assertEqual(
            cm.exception.message,
            (
                "This command cannot remove stonith resource: 'S1'. "
                "Use 'pcs stonith remove' instead."
            ),
        )
        self.assert_lib_calls([mock.call.resource.get_configured_resources()])
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()

    def test_multiple_stonith_ids(self, mock_process_lib_reports, mock_reports):
        with self.assertRaises(CmdLineInputError) as cm:
            self._call_cmd(["S1", "R1", "R2", "R3", "S2"])

        self.assertEqual(
            cm.exception.message,
            (
                "This command cannot remove stonith resources: 'S1', 'S2'. "
                "Use 'pcs stonith remove' instead."
            ),
        )
        self.assert_lib_calls([mock.call.resource.get_configured_resources()])
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()

    def test_remove_one(self, mock_process_library_reports, mock_reports):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["R1"])

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}),
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=False
        )

    def test_remove_one_with_debug(
        self, mock_process_library_reports, mock_reports
    ):
        mock_reports.return_value = [INFO_REPORT]
        self._call_cmd(["R1"], {"debug": True})

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}),
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [INFO_REPORT], include_debug=True
        )

    def test_remove_multiple(self, mock_process_library_reports, mock_reports):
        mock_reports.return_value = []
        self._call_cmd(["R1", "R2", "R3"])

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1", "R2", "R3"}),
            ]
        )
        mock_process_library_reports.assert_not_called()

    def test_dont_stop_me_now(self, mock_process_library_reports, mock_reports):
        self._call_cmd(["R1"], {"no-stop": True})

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}, set()),
            ]
        )
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_force_dont_stop_me_now(
        self, mock_process_library_reports, mock_reports
    ):
        self._call_cmd(["R1"], {"force": True, "no-stop": True})

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}, {reports.codes.FORCE}),
            ]
        )
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()

    def test_remove_not_stopped(
        self, mock_process_library_reports, mock_reports
    ):
        self.lib.cib.remove_elements.side_effect = [LibraryError(), None]
        mock_reports.return_value = [CANNOT_STOP_RESOURCES_ERROR_REPORT]

        self._call_cmd(["R1"])

        resource_ids = {"R1"}
        force_flags = set()
        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements(resource_ids),
                mock.call.resource.stop(resource_ids, force_flags),
                mock.call.cluster.wait_for_pcmk_idle(None),
                mock.call.cib.remove_elements(resource_ids, force_flags),
            ]
        )
        mock_process_library_reports.assert_not_called()

    def test_remove_more_errors(
        self, mock_process_library_reports, mock_reports
    ):
        self.lib.cib.remove_elements.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT,
            CANNOT_STOP_RESOURCES_ERROR_REPORT,
        ]

        self.assertRaises(LibraryError, lambda: self._call_cmd(["R1"]))

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}),
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT],
            include_debug=False,
            exit_on_error=False,
        )

    def test_remove_more_errors_debug(
        self, mock_process_library_reports, mock_reports
    ):
        self.lib.cib.remove_elements.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT,
            CANNOT_STOP_RESOURCES_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError, lambda: self._call_cmd(["R1"], {"debug": True})
        )

        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}),
            ]
        )
        mock_process_library_reports.assert_called_once_with(
            [NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT],
            include_debug=True,
            exit_on_error=False,
        )

    def test_mutually_exclusive_options(
        self, mock_process_library_reports, mock_reports
    ):
        with self.assertRaises(CmdLineInputError) as cm:
            command.remove(
                self.lib,
                ["R1"],
                InputModifiers({"-f": "foo", "--no-stop": True}),
            )

        self.assert_lib_calls([])
        self.assertEqual(
            cm.exception.message, "Only one of '--no-stop', '-f' can be used"
        )
        mock_reports.assert_not_called()
        mock_process_library_reports.assert_not_called()


@mock.patch(
    "pcs.common.reports.processor.ReportProcessorInMemory.reports",
    new_callable=mock.PropertyMock,
)
@mock.patch("pcs.cli.resource.command.process_library_reports")
class RemoveResource(RemoveResourceBase, TestCase):
    @mock.patch("pcs.cli.resource.command.deprecation_warning")
    def test_remove_force(
        self, mock_deprecation_warning, mock_process_lib_reports, mock_reports
    ):
        self._call_cmd(["R1"], {"force": True})

        mock_deprecation_warning.assert_called_once()
        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}, {reports.codes.FORCE}),
            ]
        )
        mock_reports.assert_not_called()
        mock_process_lib_reports.assert_not_called()


@mock.patch(
    "pcs.common.reports.processor.ReportProcessorInMemory.reports",
    new_callable=mock.PropertyMock,
)
@mock.patch("pcs.cli.resource.command.process_library_reports")
class RemoveResourceFuture(RemoveResourceBase, TestCase):
    def _call_cmd(self, argv, modifiers=None):
        default_modifiers = {"future": True}
        command.remove(
            self.lib,
            argv,
            dict_to_modifiers(
                modifiers | default_modifiers
                if modifiers
                else default_modifiers
            ),
        )

    def test_remove_force_more_errors_forceable(
        self, mock_process_lib_reports, mock_reports
    ):
        self.lib.cib.remove_elements.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            FORCEABLE_ERROR_REPORT,
            CANNOT_STOP_RESOURCES_ERROR_REPORT,
        ]

        self._call_cmd(["R1"], {"force": True})

        resource_ids = {"R1"}
        force_codes = {reports.codes.FORCE}
        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements(resource_ids),
                mock.call.resource.stop(resource_ids, force_codes),
                mock.call.cluster.wait_for_pcmk_idle(None),
                mock.call.cib.remove_elements(resource_ids, force_codes),
            ]
        )
        mock_process_lib_reports.assert_not_called()

    def test_remove_force_more_errors_not_forceable(
        self, mock_process_lib_reports, mock_reports
    ):
        self.lib.cib.remove_elements.side_effect = [LibraryError(), None]
        mock_reports.return_value = [
            FORCEABLE_ERROR_REPORT,
            NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT,
            CANNOT_STOP_RESOURCES_ERROR_REPORT,
        ]

        self.assertRaises(
            LibraryError,
            lambda: self._call_cmd(["R1"], {"force": True}),
        )
        self.assert_lib_calls(
            [
                mock.call.resource.get_configured_resources(),
                mock.call.cib.remove_elements({"R1"}),
            ]
        )
        mock_process_lib_reports.assert_called_once_with(
            [
                reports.item.ReportItem.warning(
                    reports.messages.NoStonithMeansWouldBeLeft()
                ),
                NO_STONITH_WOULD_BE_LEFT_ERROR_REPORT,
            ],
            include_debug=False,
            exit_on_error=False,
        )
