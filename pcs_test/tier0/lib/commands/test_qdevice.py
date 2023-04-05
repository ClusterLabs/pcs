import base64
import logging
import os.path
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.commands.qdevice as lib
from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.common.services.errors import (
    DisableServiceError,
    EnableServiceError,
    StartServiceError,
    StopServiceError,
)
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import KillServicesError

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


class QdeviceTestCase(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        mock.patch(
            "pcs.lib.env.get_service_manager", spec=ServiceManagerInterface
        ).start()
        self.addCleanup(mock.patch.stopall)
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


class QdeviceBadModelTest(QdeviceTestCase):
    @staticmethod
    def base_test(func):
        assert_raise_library_error(
            func,
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "bad model",
                    "allowed_values": ["net"],
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

    def test_setup(self):
        self.base_test(
            lambda: lib.qdevice_setup(self.lib_env, "bad model", False, False)
        )

    def test_destroy(self):
        self.base_test(lambda: lib.qdevice_destroy(self.lib_env, "bad model"))

    def test_status_text(self):
        self.base_test(
            lambda: lib.qdevice_status_text(self.lib_env, "bad model")
        )

    def test_enable(self):
        self.base_test(lambda: lib.qdevice_enable(self.lib_env, "bad model"))

    def test_disable(self):
        self.base_test(lambda: lib.qdevice_disable(self.lib_env, "bad model"))

    def test_start(self):
        self.base_test(lambda: lib.qdevice_start(self.lib_env, "bad model"))

    def test_stop(self):
        self.base_test(lambda: lib.qdevice_stop(self.lib_env, "bad model"))

    def test_kill(self):
        self.base_test(lambda: lib.qdevice_kill(self.lib_env, "bad model"))


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_setup")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class QdeviceNetSetupTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success(self, mock_net_setup):
        lib.qdevice_setup(self.lib_env, "net", False, False)

        mock_net_setup.assert_called_once_with("mock_runner")
        self.assertEqual(self.lib_env.service_manager.method_calls, [])
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    },
                )
            ],
        )

    def test_start_enable_success(self, mock_net_setup):
        lib.qdevice_setup(self.lib_env, "net", True, True)

        mock_net_setup.assert_called_once_with("mock_runner")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.enable("corosync-qnetd"),
                mock.call.start("corosync-qnetd"),
            ],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_ENABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )

    def test_init_failed(self, mock_net_setup):
        mock_net_setup.side_effect = LibraryError("mock_report_item")
        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_setup(self.lib_env, "net", False, False),
        )
        mock_net_setup.assert_called_once_with("mock_runner")
        self.assertEqual(self.lib_env.service_manager.method_calls, [])
        assert_report_item_list_equal(self.mock_reporter.report_item_list, [])

    def test_enable_failed(self, mock_net_setup):
        self.lib_env.service_manager.enable.side_effect = EnableServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.lib_env, "net", True, True),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_ENABLE,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )

        mock_net_setup.assert_called_once_with("mock_runner")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.enable("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    },
                )
            ],
        )

    def test_start_failed(self, mock_net_setup):
        self.lib_env.service_manager.start.side_effect = StartServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.lib_env, "net", True, True),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_START,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )

        mock_net_setup.assert_called_once_with("mock_runner")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.enable("corosync-qnetd"),
                mock.call.start("corosync-qnetd"),
            ],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_ENABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
            ],
        )


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_status_cluster_text")
@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_destroy")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class QdeviceNetDestroyTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success_not_used(self, mock_net_destroy, mock_status):
        mock_status.return_value = ""

        lib.qdevice_destroy(self.lib_env, "net")

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.stop("corosync-qnetd"),
                mock.call.disable("corosync-qnetd"),
            ],
        )
        mock_net_destroy.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_DISABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_DESTROY_SUCCESS,
                    {
                        "model": "net",
                    },
                ),
            ],
        )

    def test_success_used_forced(self, mock_net_destroy, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        lib.qdevice_destroy(self.lib_env, "net", proceed_if_used=True)

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.stop("corosync-qnetd"),
                mock.call.disable("corosync-qnetd"),
            ],
        )
        mock_net_destroy.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.QDEVICE_USED_BY_CLUSTERS,
                    {
                        "clusters": ["a_cluster"],
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_DISABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_DESTROY_SUCCESS,
                    {
                        "model": "net",
                    },
                ),
            ],
        )

    def test_used_not_forced(self, mock_net_destroy, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net")
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.ERROR,
                    report_codes.QDEVICE_USED_BY_CLUSTERS,
                    {
                        "clusters": ["a_cluster"],
                    },
                    report_codes.FORCE,
                ),
            ],
        )

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [],
        )
        mock_net_destroy.assert_not_called()

    def test_stop_failed(self, mock_net_destroy, mock_status):
        mock_status.return_value = ""
        self.lib_env.service_manager.stop.side_effect = StopServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_STOP,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.stop("corosync-qnetd")],
        )
        mock_net_destroy.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                )
            ],
        )

    def test_disable_failed(self, mock_net_destroy, mock_status):
        mock_status.return_value = ""
        self.lib_env.service_manager.disable.side_effect = DisableServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_DISABLE,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.stop("corosync-qnetd"),
                mock.call.disable("corosync-qnetd"),
            ],
        )
        mock_net_destroy.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )

    def test_destroy_failed(self, mock_net_destroy, mock_status):
        mock_status.return_value = ""
        mock_net_destroy.side_effect = LibraryError("mock_report_item")

        self.assertRaises(
            LibraryError, lambda: lib.qdevice_destroy(self.lib_env, "net")
        )

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [
                mock.call.stop("corosync-qnetd"),
                mock.call.disable("corosync-qnetd"),
            ],
        )
        mock_net_destroy.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_DISABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_status_cluster_text")
@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_status_generic_text")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class TestQdeviceNetStatusTextTest(QdeviceTestCase):
    def test_success(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEqual(
            lib.qdevice_status_text(self.lib_env, "net"),
            "generic status info\ncluster status info\n",
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with("mock_runner", None, False)

    def test_success_verbose(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEqual(
            lib.qdevice_status_text(self.lib_env, "net", verbose=True),
            "generic status info\ncluster status info\n",
        )

        mock_status_generic.assert_called_once_with("mock_runner", True)
        mock_status_cluster.assert_called_once_with("mock_runner", None, True)

    def test_success_cluster(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEqual(
            lib.qdevice_status_text(self.lib_env, "net", cluster="name"),
            "generic status info\ncluster status info\n",
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with(
            "mock_runner", "name", False
        )

    def test_error_generic_status(
        self, mock_status_generic, mock_status_cluster
    ):
        mock_status_generic.side_effect = LibraryError("mock_report_item")
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertRaises(
            LibraryError, lambda: lib.qdevice_status_text(self.lib_env, "net")
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_not_called()

    def test_error_cluster_status(
        self, mock_status_generic, mock_status_cluster
    ):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.side_effect = LibraryError("mock_report_item")

        self.assertRaises(
            LibraryError, lambda: lib.qdevice_status_text(self.lib_env, "net")
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with("mock_runner", None, False)


class QdeviceNetEnableTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success(self):
        lib.qdevice_enable(self.lib_env, "net")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.enable("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_ENABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                )
            ],
        )

    def test_failed(self):
        self.lib_env.service_manager.enable.side_effect = EnableServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_enable(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_ENABLE,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.enable("corosync-qnetd")],
        )


class QdeviceNetDisableTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success(self):
        lib.qdevice_disable(self.lib_env, "net")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.disable("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_DISABLE,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                )
            ],
        )

    def test_failed(self):
        self.lib_env.service_manager.disable.side_effect = DisableServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_disable(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_DISABLE,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.disable("corosync-qnetd")],
        )


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_initialized")
class QdeviceNetStartTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success(self, mock_qdevice_initialized):
        mock_qdevice_initialized.return_value = True
        lib.qdevice_start(self.lib_env, "net")
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.start("corosync-qnetd")],
        )
        mock_qdevice_initialized.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )

    def test_failed(self, mock_qdevice_initialized):
        self.lib_env.service_manager.start.side_effect = StartServiceError(
            "test service", "test error"
        )
        mock_qdevice_initialized.return_value = True

        assert_raise_library_error(
            lambda: lib.qdevice_start(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_START,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.start("corosync-qnetd")],
        )
        mock_qdevice_initialized.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_START,
                        "service": "quorum device",
                        "instance": "",
                    },
                )
            ],
        )

    def test_qdevice_not_initialized(self, mock_qdevice_initialized):
        mock_qdevice_initialized.return_value = False

        assert_raise_library_error(
            lambda: lib.qdevice_start(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                },
            ),
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [],
        )
        mock_qdevice_initialized.assert_called_once_with()


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_status_cluster_text")
class QdeviceNetStopTest(QdeviceTestCase):
    # pylint: disable=no-member
    def test_success_not_used(self, mock_status):
        mock_status.return_value = ""

        lib.qdevice_stop(self.lib_env, "net", proceed_if_used=False)

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.stop("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )

    def test_success_used_forced(self, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        lib.qdevice_stop(self.lib_env, "net", proceed_if_used=True)

        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.stop("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.QDEVICE_USED_BY_CLUSTERS,
                    {
                        "clusters": ["a_cluster"],
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                ),
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                ),
            ],
        )

    def test_used_not_forced(self, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        assert_raise_library_error(
            lambda: lib.qdevice_stop(self.lib_env, "net", proceed_if_used=False)
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.ERROR,
                    report_codes.QDEVICE_USED_BY_CLUSTERS,
                    {
                        "clusters": ["a_cluster"],
                    },
                    report_codes.FORCE,
                ),
            ],
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [],
        )

    def test_failed(self, mock_status):
        mock_status.return_value = ""
        self.lib_env.service_manager.stop.side_effect = StopServiceError(
            "test service", "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_stop(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_STOP,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )
        self.assertEqual(
            self.lib_env.service_manager.method_calls,
            [mock.call.stop("corosync-qnetd")],
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_STARTED,
                    {
                        "action": reports.const.SERVICE_ACTION_STOP,
                        "service": "quorum device",
                        "instance": "",
                    },
                )
            ],
        )


@mock.patch("pcs.lib.external.kill_services")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class QdeviceNetKillTest(QdeviceTestCase):
    def test_success(self, mock_net_kill):
        lib.qdevice_kill(self.lib_env, "net")
        mock_net_kill.assert_called_once_with("mock_runner", ["corosync-qnetd"])
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    {
                        "action": reports.const.SERVICE_ACTION_KILL,
                        "service": "quorum device",
                        "node": "",
                        "instance": "",
                    },
                )
            ],
        )

    def test_failed(self, mock_net_kill):
        mock_net_kill.side_effect = KillServicesError(
            ["test service"], "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_kill(self.lib_env, "net"),
            (
                severity.ERROR,
                reports.codes.SERVICE_ACTION_FAILED,
                {
                    "action": reports.const.SERVICE_ACTION_KILL,
                    "service": "test service",
                    "reason": "test error",
                    "node": "",
                    "instance": "",
                },
            ),
        )
        mock_net_kill.assert_called_once_with("mock_runner", ["corosync-qnetd"])


class QdeviceNetGetCaCertificate(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)
        self.path = os.path.join(
            settings.corosync_qdevice_net_server_certs_dir,
            settings.corosync_qdevice_net_server_ca_file_name,
        )

    def test_success(self):
        ca_cert_data = b"ca cert data"
        self.config.raw_file.read(
            file_type_codes.COROSYNC_QNETD_CA_CERT, self.path, ca_cert_data
        )
        result = lib.qdevice_net_get_ca_certificate(self.env_assist.get_env())
        self.assertEqual(result, base64.b64encode(ca_cert_data).decode())

    def test_read_error(self):
        self.config.raw_file.read(
            file_type_codes.COROSYNC_QNETD_CA_CERT,
            self.path,
            exception_msg="an error",
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.qdevice_net_get_ca_certificate(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_QNETD_CA_CERT,
                    operation=RawFileError.ACTION_READ,
                    reason="an error",
                    file_path=self.path,
                )
            ]
        )


@mock.patch(
    "pcs.lib.commands.qdevice.qdevice_net.qdevice_sign_certificate_request"
)
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class QdeviceNetSignCertificateRequestTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "certificate request".encode()
        qdevice_func_output = "signed certificate".encode()
        mock_qdevice_func.return_value = qdevice_func_output
        cluster_name = "clusterName"

        self.assertEqual(
            base64.b64encode(qdevice_func_output).decode(),
            lib.qdevice_net_sign_certificate_request(
                self.lib_env, base64.b64encode(qdevice_func_input), cluster_name
            ),
        )

        mock_qdevice_func.assert_called_once_with(
            "mock_runner", qdevice_func_input, cluster_name
        )

    def test_bad_input(self, mock_qdevice_func):
        qdevice_func_input = "certificate request".encode("utf-8")
        cluster_name = "clusterName"

        assert_raise_library_error(
            lambda: lib.qdevice_net_sign_certificate_request(
                self.lib_env, qdevice_func_input, cluster_name
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "qnetd certificate request",
                    "option_value": qdevice_func_input,
                    "allowed_values": ["base64 encoded certificate"],
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

        mock_qdevice_func.assert_not_called()


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.client_setup")
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class ClientNetSetupTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "CA certificate".encode("utf-8")

        lib.client_net_setup(self.lib_env, base64.b64encode(qdevice_func_input))

        mock_qdevice_func.assert_called_once_with(
            "mock_runner", qdevice_func_input
        )

    def test_bad_input(self, mock_qdevice_func):
        qdevice_func_input = "CA certificate".encode("utf-8")

        assert_raise_library_error(
            lambda: lib.client_net_setup(self.lib_env, qdevice_func_input),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "qnetd CA certificate",
                    "option_value": qdevice_func_input,
                    "allowed_values": ["base64 encoded certificate"],
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

        mock_qdevice_func.assert_not_called()


@mock.patch(
    "pcs.lib.commands.qdevice.qdevice_net.client_import_certificate_and_key"
)
@mock.patch.object(LibraryEnvironment, "cmd_runner", lambda self: "mock_runner")
class ClientNetImportCertificateTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "client certificate".encode("utf-8")

        lib.client_net_import_certificate(
            self.lib_env, base64.b64encode(qdevice_func_input)
        )

        mock_qdevice_func.assert_called_once_with(
            "mock_runner", qdevice_func_input
        )

    def test_bad_input(self, mock_qdevice_func):
        qdevice_func_input = "client certificate".encode("utf-8")

        assert_raise_library_error(
            lambda: lib.client_net_import_certificate(
                self.lib_env, qdevice_func_input
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "qnetd client certificate",
                    "option_value": qdevice_func_input,
                    "allowed_values": ["base64 encoded certificate"],
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
            ),
        )

        mock_qdevice_func.assert_not_called()


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.client_destroy")
class ClientNetDestroyTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        lib.client_net_destroy(self.lib_env)
        mock_qdevice_func.assert_called_once_with()
