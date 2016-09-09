from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

import base64
import os.path

from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import get_test_resource

from pcs import settings
from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.errors import ReportItemSeverity as severity, LibraryError
from pcs.lib.external import (
    CommandRunner,
    NodeCommunicator,
    NodeCommunicationException,
)

import pcs.lib.corosync.qdevice_net as lib


_qnetd_cert_dir = "/etc/corosync/qnetd/nssdb"
_qnetd_cert_tool = "/usr/bin/corosync-qnetd-certutil"
_qnetd_tool = "/usr/bin/corosync-qnetd-tool"
_client_cert_dir = "/etc/corosync/qdevice/net/nssdb"
_client_cert_tool = "/usr/sbin/corosync-qdevice-net-certutil"

def cert_to_url(cert):
    return base64.b64encode(cert).decode("utf-8").replace("=", "%3D")

class CertificateTestCase(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.mock_tmpfile = mock.MagicMock()
        self.mock_tmpfile.name = "tmpfile path"

@mock.patch("pcs.lib.corosync.qdevice_net.external.is_dir_nonempty")
class QdeviceSetupTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = False
        self.mock_runner.run.return_value = ("initialized", "", 0)

        lib.qdevice_setup(self.mock_runner)

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.run.assert_called_once_with([_qnetd_cert_tool, "-i"])

    def test_cert_db_exists(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = True

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_ALREADY_INITIALIZED,
                {"model": "net"}
            )
        )

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.run.assert_not_called()

    def test_init_tool_fail(self, mock_is_dir_nonempty):
        mock_is_dir_nonempty.return_value = False
        self.mock_runner.run.return_value = ("stdout", "test error", 1)

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "test error\nstdout",
                }
            )
        )

        mock_is_dir_nonempty.assert_called_once_with(_qnetd_cert_dir)
        self.mock_runner.run.assert_called_once_with([_qnetd_cert_tool, "-i"])


@mock.patch("pcs.lib.corosync.qdevice_net.shutil.rmtree")
@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_initialized")
class QdeviceDestroyTest(TestCase):
    def test_success(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        lib.qdevice_destroy()
        mock_rmtree.assert_called_once_with(_qnetd_cert_dir)

    def test_not_initialized(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = False
        lib.qdevice_destroy()
        mock_rmtree.assert_not_called()

    def test_cert_dir_rm_error(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        mock_rmtree.side_effect = EnvironmentError("test errno", "test message")
        assert_raise_library_error(
            lib.qdevice_destroy,
            (
                severity.ERROR,
                report_codes.QDEVICE_DESTROY_ERROR,
                {
                    "model": "net",
                    "reason": "test message",
                }
            )
        )
        mock_rmtree.assert_called_once_with(_qnetd_cert_dir)


class QdeviceStatusGenericTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_generic_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-s"])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_generic_text(self.mock_runner, True)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-s", "-v"])

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 1)
        assert_raise_library_error(
            lambda: lib.qdevice_status_generic_text(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_GET_STATUS_ERROR,
                {
                    "model": "net",
                    "reason": "status error\nsome info",
                }
            )
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-s"])


class QdeviceStatusClusterTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l"])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, verbose=True)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l", "-v"])

    def test_success_cluster(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, "cluster")
        )
        self.mock_runner.run.assert_called_once_with([
            _qnetd_tool, "-l", "-c", "cluster"
        ])

    def test_success_cluster_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, "cluster", True)
        )
        self.mock_runner.run.assert_called_once_with([
            _qnetd_tool, "-l", "-v", "-c", "cluster"
        ])

    def test_error(self):
        self.mock_runner.run.return_value = ("some info", "status error", 1)
        assert_raise_library_error(
            lambda: lib.qdevice_status_cluster_text(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_GET_STATUS_ERROR,
                {
                    "model": "net",
                    "reason": "status error\nsome info",
                }
            )
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l"])


class QdeviceConnectedClustersTest(TestCase):
    def test_empty_status(self):
        status = ""
        self.assertEqual(
            [],
            lib.qdevice_connected_clusters(status)
        )

    def test_one_cluster(self):
        status = """\
Cluster "rhel72":
    Algorithm:          LMS
    Tie-breaker:        Node with lowest node ID
    Node ID 2:
        Client address:         ::ffff:192.168.122.122:59738
        Configured node list:   1, 2
        Membership node list:   1, 2
        Vote:                   ACK (ACK)
    Node ID 1:
        Client address:         ::ffff:192.168.122.121:43420
        Configured node list:   1, 2
        Membership node list:   1, 2
        Vote:                   ACK (ACK)
"""
        self.assertEqual(
            ["rhel72"],
            lib.qdevice_connected_clusters(status)
        )

    def test_more_clusters(self):
        status = """\
Cluster "rhel72":
Cluster "rhel73":
"""
        self.assertEqual(
            ["rhel72", "rhel73"],
            lib.qdevice_connected_clusters(status)
        )

    def test_invalid_status(self):
        status = """\
Cluster:
    Cluster "rhel72":
"""
        self.assertEqual(
            [],
            lib.qdevice_connected_clusters(status)
        )


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
@mock.patch("pcs.lib.corosync.qdevice_net._store_to_tmpfile")
class QdeviceSignCertificateRequestTest(CertificateTestCase):
    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized",
        lambda: True
    )
    def test_success(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.qdevice_sign_certificate_request(
            self.mock_runner,
            "certificate request",
            "clusterName"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_sign_error
        )
        self.mock_runner.run.assert_called_once_with([
            _qnetd_cert_tool,
            "-s", "-c", self.mock_tmpfile.name, "-n", "clusterName"
        ])
        mock_get_cert.assert_called_once_with(
            "tool output",
            reports.qdevice_certificate_sign_error
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized",
        lambda: False
    )
    def test_not_initialized(self, mock_tmp_store, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner,
                "certificate request",
                "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                }
            )
        )
        mock_tmp_store.assert_not_called()
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized",
        lambda: True
    )
    def test_input_write_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner,
                "certificate request",
                "clusterName"
            )
        )

        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized",
        lambda: True
    )
    def test_sign_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner,
                "certificate request",
                "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_SIGN_ERROR,
                {
                    "reason": "tool output error\nstdout",
                }
            )
        )

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_sign_error
        )
        self.mock_runner.run.assert_called_once_with([
            _qnetd_cert_tool,
            "-s", "-c", self.mock_tmpfile.name, "-n", "clusterName"
        ])
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized",
        lambda: True
    )
    def test_output_read_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner,
                "certificate request",
                "clusterName"
            )
        )

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_sign_error
        )
        self.mock_runner.run.assert_called_once_with([
            _qnetd_cert_tool,
            "-s", "-c", self.mock_tmpfile.name, "-n", "clusterName"
        ])
        mock_get_cert.assert_called_once_with(
            "tool output",
            reports.qdevice_certificate_sign_error
        )


@mock.patch("pcs.lib.corosync.qdevice_net.shutil.rmtree")
@mock.patch("pcs.lib.corosync.qdevice_net.client_initialized")
class ClientDestroyTest(TestCase):
    def test_success(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        lib.client_destroy()
        mock_rmtree.assert_called_once_with(_client_cert_dir)

    def test_not_initialized(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = False
        lib.client_destroy()
        mock_rmtree.assert_not_called()

    def test_cert_dir_rm_error(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        mock_rmtree.side_effect = EnvironmentError("test errno", "test message")
        assert_raise_library_error(
            lib.client_destroy,
            (
                severity.ERROR,
                report_codes.QDEVICE_DESTROY_ERROR,
                {
                    "model": "net",
                    "reason": "test message",
                }
            )
        )
        mock_rmtree.assert_called_once_with(_client_cert_dir)


class ClientSetupTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.original_path = settings.corosync_qdevice_net_client_certs_dir
        settings.corosync_qdevice_net_client_certs_dir = get_test_resource(
            "qdevice-certs"
        )
        self.ca_file_path = os.path.join(
            settings.corosync_qdevice_net_client_certs_dir,
            settings.corosync_qdevice_net_client_ca_file_name
        )

    def tearDown(self):
        settings.corosync_qdevice_net_client_certs_dir = self.original_path

    @mock.patch("pcs.lib.corosync.qdevice_net.client_destroy")
    def test_success(self, mock_destroy):
        self.mock_runner.run.return_value = ("tool output", "", 0)

        lib.client_setup(self.mock_runner, "certificate data".encode("utf-8"))

        self.assertEqual(
            "certificate data".encode("utf-8"),
            open(self.ca_file_path, "rb").read()
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-i", "-c", self.ca_file_path
        ])
        mock_destroy.assert_called_once_with()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_destroy")
    def test_init_error(self, mock_destroy):
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_setup(
                self.mock_runner,
                "certificate data".encode("utf-8")
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "tool output error\nstdout",
                }
            )
        )

        self.assertEqual(
            "certificate data".encode("utf-8"),
            open(self.ca_file_path, "rb").read()
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-i", "-c", self.ca_file_path
        ])
        mock_destroy.assert_called_once_with()


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
class ClientGenerateCertificateRequestTest(CertificateTestCase):
    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_success(self, mock_get_cert):
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.client_generate_certificate_request(
            self.mock_runner,
            "clusterName"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-r", "-n", "clusterName"
        ])
        self.assertEqual(1, len(mock_get_cert.mock_calls))
        self.assertEqual(
            "tool output",
            mock_get_cert.call_args[0][0]
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: False
    )
    def test_not_initialized(self, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.client_generate_certificate_request(
                self.mock_runner,
                "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                }
            )
        )
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_tool_error(self, mock_get_cert):
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_generate_certificate_request(
                self.mock_runner,
                "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "tool output error\nstdout",
                }
            )
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-r", "-n", "clusterName"
        ])
        mock_get_cert.assert_not_called()


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
@mock.patch("pcs.lib.corosync.qdevice_net._store_to_tmpfile")
class ClientCertRequestToPk12Test(CertificateTestCase):
    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_success(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.client_cert_request_to_pk12(
            self.mock_runner,
            "certificate request"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-M", "-c", self.mock_tmpfile.name
        ])
        mock_get_cert.assert_called_once_with(
            "tool output",
            reports.qdevice_certificate_import_error
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: False
    )
    def test_not_initialized(self, mock_tmp_store, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner,
                "certificate request"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                }
            )
        )
        mock_tmp_store.assert_not_called()
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_input_write_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner,
                "certificate request"
            )
        )

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_transform_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner,
                "certificate request"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "tool output error\nstdout",
                }
            )
        )

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-M", "-c", self.mock_tmpfile.name
        ])
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_output_read_error(self, mock_tmp_store, mock_get_cert):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner,
                "certificate request"
            )
        )

        mock_tmp_store.assert_called_once_with(
            "certificate request",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-M", "-c", self.mock_tmpfile.name
        ])
        mock_get_cert.assert_called_once_with(
            "tool output",
            reports.qdevice_certificate_import_error
        )


@mock.patch("pcs.lib.corosync.qdevice_net._store_to_tmpfile")
class ClientImportCertificateAndKeyTest(CertificateTestCase):
    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_success(self, mock_tmp_store):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("tool output", "", 0)

        lib.client_import_certificate_and_key(
            self.mock_runner,
            "pk12 certificate"
        )

        mock_tmp_store.assert_called_once_with(
            "pk12 certificate",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-m", "-c", self.mock_tmpfile.name
        ])

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: False
    )
    def test_not_initialized(self, mock_tmp_store):
        assert_raise_library_error(
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner,
                "pk12 certificate"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                }
            )
        )

        mock_tmp_store.assert_not_called()
        self.mock_runner.run.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_input_write_error(self, mock_tmp_store):
        mock_tmp_store.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner,
                "pk12 certificate"
            )
        )

        mock_tmp_store.assert_called_once_with(
            "pk12 certificate",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized",
        lambda: True
    )
    def test_import_error(self, mock_tmp_store):
        mock_tmp_store.return_value = self.mock_tmpfile
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner,
                "pk12 certificate"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "tool output error\nstdout",
                }
            )
        )

        mock_tmp_store.assert_called_once_with(
            "pk12 certificate",
            reports.qdevice_certificate_import_error
        )
        mock_tmp_store.assert_called_once_with(
            "pk12 certificate",
            reports.qdevice_certificate_import_error
        )
        self.mock_runner.run.assert_called_once_with([
            _client_cert_tool, "-m", "-c", self.mock_tmpfile.name
        ])


class RemoteQdeviceGetCaCertificate(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        expected_result = "abcd".encode("utf-8")
        mock_communicator.call_host.return_value = base64.b64encode(
            expected_result
        )

        result = lib.remote_qdevice_get_ca_certificate(
            mock_communicator,
            "qdevice host"
        )
        self.assertEqual(result, expected_result)

        mock_communicator.call_host.assert_called_once_with(
            "qdevice host",
            "remote/qdevice_net_get_ca_certificate",
            None
        )

    def test_decode_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_host.return_value = "error"

        assert_raise_library_error(
            lambda: lib.remote_qdevice_get_ca_certificate(
                mock_communicator,
                "qdevice host"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {
                    "node": "qdevice host",
                }
            )
        )

    def test_comunication_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_host.side_effect = NodeCommunicationException(
            "qdevice host", "command", "reason"
        )

        self.assertRaises(
            NodeCommunicationException,
            lambda: lib.remote_qdevice_get_ca_certificate(
                mock_communicator,
                "qdevice host"
            )
        )


class RemoteClientSetupTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = "node address"
        ca_cert = "CA certificate".encode("utf-8")

        lib.remote_client_setup(mock_communicator, node, ca_cert)

        mock_communicator.call_node.assert_called_once_with(
            node,
            "remote/qdevice_net_client_init_certificate_storage",
            "ca_certificate={0}".format(
                cert_to_url(ca_cert)
            )
        )

    def test_comunication_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_node.side_effect = NodeCommunicationException(
            "node address", "command", "reason"
        )

        self.assertRaises(
            NodeCommunicationException,
            lambda: lib.remote_client_setup(
                mock_communicator,
                "node address",
                "ca cert".encode("utf-8")
            )
        )


class RemoteSignCertificateRequestTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        cert_request = "request".encode("utf-8")
        expected_result = "abcd".encode("utf-8")
        host = "qdevice host"
        cluster_name = "ClusterName"
        mock_communicator.call_host.return_value = base64.b64encode(
            expected_result
        )

        result = lib.remote_sign_certificate_request(
            mock_communicator,
            host,
            cert_request,
            cluster_name
        )
        self.assertEqual(result, expected_result)

        mock_communicator.call_host.assert_called_once_with(
            host,
            "remote/qdevice_net_sign_node_certificate",
            "certificate_request={0}&cluster_name={1}".format(
                cert_to_url(cert_request),
                cluster_name
            )
        )

    def test_decode_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_host.return_value = "error"

        assert_raise_library_error(
            lambda: lib.remote_sign_certificate_request(
                mock_communicator,
                "qdevice host",
                "cert request".encode("utf-8"),
                "cluster name"
            ),
            (
                severity.ERROR,
                report_codes.INVALID_RESPONSE_FORMAT,
                {
                    "node": "qdevice host",
                }
            )
        )

    def test_comunication_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_host.side_effect = NodeCommunicationException(
            "qdevice host", "command", "reason"
        )

        self.assertRaises(
            NodeCommunicationException,
            lambda: lib.remote_sign_certificate_request(
                mock_communicator,
                "qdevice host",
                "cert request".encode("utf-8"),
                "cluster name"
            )
        )


class RemoteClientImportCertificateAndKeyTest(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = "node address"
        pk12_cert = "pk12 certificate".encode("utf-8")

        lib.remote_client_import_certificate_and_key(
            mock_communicator,
            node,
            pk12_cert
        )

        mock_communicator.call_node.assert_called_once_with(
            node,
            "remote/qdevice_net_client_import_certificate",
            "certificate={0}".format(
                cert_to_url(pk12_cert)
            )
        )

    def test_comunication_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_node.side_effect = NodeCommunicationException(
            "node address", "command", "reason"
        )

        self.assertRaises(
            NodeCommunicationException,
            lambda: lib.remote_client_import_certificate_and_key(
                mock_communicator,
                "node address",
                "pk12 cert".encode("utf-8")
            )
        )


class RemoteClientDestroy(TestCase):
    def test_success(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        node = "node address"

        lib.remote_client_destroy(mock_communicator, node)

        mock_communicator.call_node.assert_called_once_with(
            node,
            "remote/qdevice_net_client_destroy",
            None
        )

    def test_comunication_error(self):
        mock_communicator = mock.MagicMock(spec_set=NodeCommunicator)
        mock_communicator.call_node.side_effect = NodeCommunicationException(
            "node address", "command", "reason"
        )

        self.assertRaises(
            NodeCommunicationException,
            lambda: lib.remote_client_destroy(mock_communicator, "node address")
        )


class GetOutputCertificateTest(TestCase):
    def setUp(self):
        self.file_path = get_test_resource("qdevice-certs/qnetd-cacert.crt")
        self.file_data = open(self.file_path, "rb").read()

    def test_success(self):
        cert_tool_output = """
some line
Certificate stored in {0}
some other line
        """.format(self.file_path)
        report_func = mock.MagicMock()

        self.assertEqual(
            self.file_data,
            lib._get_output_certificate(cert_tool_output, report_func)
        )
        report_func.assert_not_called()

    def test_success_request(self):
        cert_tool_output = """
some line
Certificate request stored in {0}
some other line
        """.format(self.file_path)
        report_func = mock.MagicMock()

        self.assertEqual(
            self.file_data,
            lib._get_output_certificate(cert_tool_output, report_func)
        )
        report_func.assert_not_called()

    def test_message_not_found(self):
        cert_tool_output = "some rubbish output"
        report_func = reports.qdevice_certificate_import_error

        assert_raise_library_error(
            lambda: lib._get_output_certificate(
                cert_tool_output,
                report_func
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": cert_tool_output,
                }
            )
        )

    def test_cannot_read_file(self):
        cert_tool_output = """
some line
Certificate request stored in {0}.bad
some other line
        """.format(self.file_path)
        report_func = reports.qdevice_certificate_import_error

        assert_raise_library_error(
            lambda: lib._get_output_certificate(
                cert_tool_output,
                report_func
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "{0}.bad: No such file or directory".format(
                        self.file_path
                    ),
                }
            )
        )

