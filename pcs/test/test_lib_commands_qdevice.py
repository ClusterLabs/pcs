from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
import base64
import logging

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor

from pcs.common import report_codes
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError, ReportItemSeverity as severity
from pcs.lib.external import (
    DisableServiceError,
    EnableServiceError,
    StartServiceError,
    StopServiceError,
    KillServicesError,
)

import pcs.lib.commands.qdevice as lib


class QdeviceTestCase(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()
        self.lib_env = LibraryEnvironment(self.mock_logger, self.mock_reporter)


@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: True)
class QdeviceDisabledOnCmanTest(QdeviceTestCase):
    def base_test(self, func):
        assert_raise_library_error(
            func,
            (
                severity.ERROR,
                report_codes.CMAN_UNSUPPORTED_COMMAND,
                {}
            )
        )

    def test_setup(self):
        self.base_test(
            lambda: lib.qdevice_setup(self.lib_env, "bad model", False, False)
        )

    def test_destroy(self):
        self.base_test(
            lambda: lib.qdevice_destroy(self.lib_env, "bad model")
        )

    def test_status_text(self):
        self.base_test(
            lambda: lib.qdevice_status_text(self.lib_env, "bad model")
        )

    def test_enable(self):
        self.base_test(
            lambda: lib.qdevice_enable(self.lib_env, "bad model")
        )

    def test_disable(self):
        self.base_test(
            lambda: lib.qdevice_disable(self.lib_env, "bad model")
        )

    def test_start(self):
        self.base_test(
            lambda: lib.qdevice_start(self.lib_env, "bad model")
        )

    def test_stop(self):
        self.base_test(
            lambda: lib.qdevice_stop(self.lib_env, "bad model")
        )

    def test_kill(self):
        self.base_test(
            lambda: lib.qdevice_kill(self.lib_env, "bad model")
        )

    def test_qdevice_net_sign_certificate_request(self):
        self.base_test(
            lambda: lib.qdevice_net_sign_certificate_request(
                self.lib_env,
                "certificate request",
                "cluster name"
            )
        )

    def test_client_net_setup(self):
        self.base_test(
            lambda: lib.client_net_setup(self.lib_env, "ca certificate")
        )

    def test_client_net_import_certificate(self):
        self.base_test(
            lambda: lib.client_net_import_certificate(self.lib_env, "cert")
        )

    def test_client_net_destroy(self):
        self.base_test(
            lambda: lib.client_net_destroy(self.lib_env)
        )


@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
class QdeviceBadModelTest(QdeviceTestCase):
    def base_test(self, func):
        assert_raise_library_error(
            func,
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "model",
                    "option_value": "bad model",
                    "allowed_values": ["net"],
                }
            )
        )

    def test_setup(self):
        self.base_test(
            lambda: lib.qdevice_setup(self.lib_env, "bad model", False, False)
        )

    def test_destroy(self):
        self.base_test(
            lambda: lib.qdevice_destroy(self.lib_env, "bad model")
        )

    def test_status_text(self):
        self.base_test(
            lambda: lib.qdevice_status_text(self.lib_env, "bad model")
        )

    def test_enable(self):
        self.base_test(
            lambda: lib.qdevice_enable(self.lib_env, "bad model")
        )

    def test_disable(self):
        self.base_test(
            lambda: lib.qdevice_disable(self.lib_env, "bad model")
        )

    def test_start(self):
        self.base_test(
            lambda: lib.qdevice_start(self.lib_env, "bad model")
        )

    def test_stop(self):
        self.base_test(
            lambda: lib.qdevice_stop(self.lib_env, "bad model")
        )

    def test_kill(self):
        self.base_test(
            lambda: lib.qdevice_kill(self.lib_env, "bad model")
        )


@mock.patch("pcs.lib.external.start_service")
@mock.patch("pcs.lib.external.enable_service")
@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_setup")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetSetupTest(QdeviceTestCase):
    def test_success(self, mock_net_setup, mock_net_enable, mock_net_start):
        lib.qdevice_setup(self.lib_env, "net", False, False)

        mock_net_setup.assert_called_once_with("mock_runner")
        mock_net_enable.assert_not_called()
        mock_net_start.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    }
                )
            ]
        )

    def test_start_enable_success(
        self, mock_net_setup, mock_net_enable, mock_net_start
    ):
        lib.qdevice_setup(self.lib_env, "net", True, True)

        mock_net_setup.assert_called_once_with("mock_runner")
        mock_net_enable.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_start.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_init_failed(
        self, mock_net_setup, mock_net_enable, mock_net_start
    ):
        mock_net_setup.side_effect = LibraryError("mock_report_item")
        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_setup(self.lib_env, "net", False, False)
        )
        mock_net_setup.assert_called_once_with("mock_runner")
        mock_net_enable.assert_not_called()
        mock_net_start.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            []
        )

    def test_enable_failed(
        self, mock_net_setup, mock_net_enable, mock_net_start
    ):
        mock_net_enable.side_effect = EnableServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.lib_env, "net", True, True),
            (
                severity.ERROR,
                report_codes.SERVICE_ENABLE_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )

        mock_net_setup.assert_called_once_with("mock_runner")
        mock_net_enable.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_start.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    }
                )
            ]
        )

    def test_start_failed(
        self, mock_net_setup, mock_net_enable, mock_net_start
    ):
        mock_net_start.side_effect = StartServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.lib_env, "net", True, True),
            (
                severity.ERROR,
                report_codes.SERVICE_START_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )

        mock_net_setup.assert_called_once_with("mock_runner")
        mock_net_enable.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_start.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.QDEVICE_INITIALIZATION_SUCCESS,
                    {
                        "model": "net",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_status_cluster_text")
@mock.patch("pcs.lib.external.stop_service")
@mock.patch("pcs.lib.external.disable_service")
@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_destroy")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetDestroyTest(QdeviceTestCase):
    def test_success_not_used(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = ""

        lib.qdevice_destroy(self.lib_env, "net")

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
        )
        mock_net_destroy.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_DESTROY_SUCCESS,
                    {
                        "model": "net",
                    }
                )
            ]
        )

    def test_success_used_forced(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        lib.qdevice_destroy(self.lib_env, "net", proceed_if_used=True)

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
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
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.QDEVICE_DESTROY_SUCCESS,
                    {
                        "model": "net",
                    }
                )
            ]
        )

    def test_used_not_forced(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.QDEVICE_USED_BY_CLUSTERS,
                {
                    "clusters": ["a_cluster"],
                },
                report_codes.FORCE_QDEVICE_USED
            ),
        )

        mock_net_stop.assert_not_called()
        mock_net_disable.assert_not_called()
        mock_net_destroy.assert_not_called()

    def test_stop_failed(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = ""
        mock_net_stop.side_effect = StopServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_STOP_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_disable.assert_not_called()
        mock_net_destroy.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_disable_failed(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = ""
        mock_net_disable.side_effect = DisableServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_destroy(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_DISABLE_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
        )
        mock_net_destroy.assert_not_called()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_destroy_failed(
        self, mock_net_destroy, mock_net_disable, mock_net_stop, mock_status
    ):
        mock_status.return_value = ""
        mock_net_destroy.side_effect = LibraryError("mock_report_item")

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_destroy(self.lib_env, "net")
        )

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
        )
        mock_net_destroy.assert_called_once_with()
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_status_cluster_text")
@mock.patch("pcs.lib.commands.qdevice.qdevice_net.qdevice_status_generic_text")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class TestQdeviceNetStatusTextTest(QdeviceTestCase):
    def test_success(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEquals(
            lib.qdevice_status_text(self.lib_env, "net"),
             "generic status info\ncluster status info\n"
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with("mock_runner", None, False)

    def test_success_verbose(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEquals(
            lib.qdevice_status_text(self.lib_env, "net", verbose=True),
             "generic status info\ncluster status info\n"
        )

        mock_status_generic.assert_called_once_with("mock_runner", True)
        mock_status_cluster.assert_called_once_with("mock_runner", None, True)

    def test_success_cluster(self, mock_status_generic, mock_status_cluster):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertEquals(
            lib.qdevice_status_text(self.lib_env, "net", cluster="name"),
             "generic status info\ncluster status info\n"
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with("mock_runner", "name", False)

    def test_error_generic_status(
        self, mock_status_generic, mock_status_cluster
    ):
        mock_status_generic.side_effect = LibraryError("mock_report_item")
        mock_status_cluster.return_value = "cluster status info\n"

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_status_text(self.lib_env, "net")
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_not_called()

    def test_error_cluster_status(
        self, mock_status_generic, mock_status_cluster
    ):
        mock_status_generic.return_value = "generic status info\n"
        mock_status_cluster.side_effect = LibraryError("mock_report_item")

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_status_text(self.lib_env, "net")
        )

        mock_status_generic.assert_called_once_with("mock_runner", False)
        mock_status_cluster.assert_called_once_with("mock_runner", None, False)


@mock.patch("pcs.lib.external.enable_service")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetEnableTest(QdeviceTestCase):
    def test_success(self, mock_net_enable):
        lib.qdevice_enable(self.lib_env, "net")
        mock_net_enable.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_ENABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_failed(self, mock_net_enable):
        mock_net_enable.side_effect = EnableServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_enable(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_ENABLE_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )
        mock_net_enable.assert_called_once_with("mock_runner", "corosync-qnetd")


@mock.patch("pcs.lib.external.disable_service")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetDisableTest(QdeviceTestCase):
    def test_success(self, mock_net_disable):
        lib.qdevice_disable(self.lib_env, "net")
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_failed(self, mock_net_disable):
        mock_net_disable.side_effect = DisableServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_disable(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_DISABLE_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )
        mock_net_disable.assert_called_once_with(
            "mock_runner",
            "corosync-qnetd"
        )


@mock.patch("pcs.lib.external.start_service")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetStartTest(QdeviceTestCase):
    def test_success(self, mock_net_start):
        lib.qdevice_start(self.lib_env, "net")
        mock_net_start.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_START_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_failed(self, mock_net_start):
        mock_net_start.side_effect = StartServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_start(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_START_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )
        mock_net_start.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_START_STARTED,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_status_cluster_text")
@mock.patch("pcs.lib.external.stop_service")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetStopTest(QdeviceTestCase):
    def test_success_not_used(self, mock_net_stop, mock_status):
        mock_status.return_value = ""

        lib.qdevice_stop(self.lib_env, "net", proceed_if_used=False)

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_success_used_forced(self, mock_net_stop, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        lib.qdevice_stop(self.lib_env, "net", proceed_if_used=True)

        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.QDEVICE_USED_BY_CLUSTERS,
                    {
                        "clusters": ["a_cluster"],
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                ),
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_SUCCESS,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )

    def test_used_not_forced(self, mock_net_stop, mock_status):
        mock_status.return_value = 'Cluster "a_cluster":\n'

        assert_raise_library_error(
            lambda: lib.qdevice_stop(
                self.lib_env,
                "net",
                proceed_if_used=False
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_USED_BY_CLUSTERS,
                {
                    "clusters": ["a_cluster"],
                },
                report_codes.FORCE_QDEVICE_USED
            ),
        )
        mock_net_stop.assert_not_called()

    def test_failed(self, mock_net_stop, mock_status):
        mock_status.return_value = ""
        mock_net_stop.side_effect = StopServiceError(
            "test service",
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_stop(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_STOP_ERROR,
                {
                    "service": "test service",
                    "reason": "test error",
                }
            )
        )
        mock_net_stop.assert_called_once_with("mock_runner", "corosync-qnetd")
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_STOP_STARTED,
                    {
                        "service": "quorum device",
                    }
                )
            ]
        )


@mock.patch("pcs.lib.external.kill_services")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetKillTest(QdeviceTestCase):
    def test_success(self, mock_net_kill):
        lib.qdevice_kill(self.lib_env, "net")
        mock_net_kill.assert_called_once_with(
            "mock_runner",
            ["corosync-qnetd"]
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.INFO,
                    report_codes.SERVICE_KILL_SUCCESS,
                    {
                        "services": ["quorum device"],
                    }
                )
            ]
        )

    def test_failed(self, mock_net_kill):
        mock_net_kill.side_effect = KillServicesError(
            ["test service"],
            "test error"
        )

        assert_raise_library_error(
            lambda: lib.qdevice_kill(self.lib_env, "net"),
            (
                severity.ERROR,
                report_codes.SERVICE_KILL_ERROR,
                {
                    "services": ["test service"],
                    "reason": "test error",
                }
            )
        )
        mock_net_kill.assert_called_once_with(
            "mock_runner",
            ["corosync-qnetd"]
        )


@mock.patch(
    "pcs.lib.commands.qdevice.qdevice_net.qdevice_sign_certificate_request"
)
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class QdeviceNetSignCertificateRequestTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "certificate request".encode("utf-8")
        qdevice_func_output = "signed certificate".encode("utf-8")
        mock_qdevice_func.return_value = qdevice_func_output
        cluster_name = "clusterName"

        self.assertEqual(
            base64.b64encode(qdevice_func_output),
            lib.qdevice_net_sign_certificate_request(
                self.lib_env,
                base64.b64encode(qdevice_func_input),
                cluster_name
            )
        )

        mock_qdevice_func.assert_called_once_with(
            "mock_runner",
            qdevice_func_input,
            cluster_name
        )

    def test_bad_input(self, mock_qdevice_func):
        qdevice_func_input = "certificate request".encode("utf-8")
        cluster_name = "clusterName"

        assert_raise_library_error(
            lambda: lib.qdevice_net_sign_certificate_request(
                self.lib_env,
                qdevice_func_input,
                cluster_name
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "qnetd certificate request",
                    "option_value": qdevice_func_input,
                    "allowed_values": ["base64 encoded certificate"],
                }
            )
        )

        mock_qdevice_func.assert_not_called()


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.client_setup")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class ClientNetSetupTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "CA certificate".encode("utf-8")

        lib.client_net_setup(self.lib_env, base64.b64encode(qdevice_func_input))

        mock_qdevice_func.assert_called_once_with(
            "mock_runner",
            qdevice_func_input
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
                }
            )
        )

        mock_qdevice_func.assert_not_called()


@mock.patch(
    "pcs.lib.commands.qdevice.qdevice_net.client_import_certificate_and_key"
)
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
@mock.patch.object(
    LibraryEnvironment,
    "cmd_runner",
    lambda self: "mock_runner"
)
class ClientNetImportCertificateTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        qdevice_func_input = "client certificate".encode("utf-8")

        lib.client_net_import_certificate(
            self.lib_env,
            base64.b64encode(qdevice_func_input)
        )

        mock_qdevice_func.assert_called_once_with(
            "mock_runner",
            qdevice_func_input
        )

    def test_bad_input(self, mock_qdevice_func):
        qdevice_func_input = "client certificate".encode("utf-8")

        assert_raise_library_error(
            lambda: lib.client_net_import_certificate(
                self.lib_env,
                qdevice_func_input
            ),
            (
                severity.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_name": "qnetd client certificate",
                    "option_value": qdevice_func_input,
                    "allowed_values": ["base64 encoded certificate"],
                }
            )
        )

        mock_qdevice_func.assert_not_called()


@mock.patch("pcs.lib.commands.qdevice.qdevice_net.client_destroy")
@mock.patch("pcs.lib.env.is_cman_cluster", lambda self: False)
class ClientNetDestroyTest(QdeviceTestCase):
    def test_success(self, mock_qdevice_func):
        lib.client_net_destroy(self.lib_env)
        mock_qdevice_func.assert_called_once_with()

