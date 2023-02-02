import base64
import os.path
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.corosync.qdevice_net as lib
from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner

from pcs_test.tools.assertions import assert_raise_library_error
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_dir,
)

# pylint: disable=no-self-use

_qnetd_cert_tool = os.path.join(
    settings.corosync_qnet_binaries, "corosync-qnetd-certutil"
)
_qnetd_tool = os.path.join(
    settings.corosync_qnet_binaries, "corosync-qnetd-tool"
)
_client_cert_tool = os.path.join(
    settings.corosync_qdevice_binaries, "corosync-qdevice-net-certutil"
)


def cert_to_url(cert):
    return base64.b64encode(cert).decode("utf-8").replace("=", "%3D")


class CertificateTestCase(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.mock_tmpfile = mock.MagicMock()
        self.mock_tmpfile.name = "tmpfile path"


@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_initialized")
class QdeviceSetupTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self, mock_initialized):
        mock_initialized.return_value = False
        self.mock_runner.run.return_value = ("initialized", "", 0)

        lib.qdevice_setup(self.mock_runner)

        mock_initialized.assert_called_once_with()
        self.mock_runner.run.assert_called_once_with([_qnetd_cert_tool, "-i"])

    def test_cert_db_exists(self, mock_initialized):
        mock_initialized.return_value = True

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_ALREADY_INITIALIZED,
                {"model": "net"},
            ),
        )

        mock_initialized.assert_called_once_with()
        self.mock_runner.run.assert_not_called()

    def test_init_tool_fail(self, mock_initialized):
        mock_initialized.return_value = False
        self.mock_runner.run.return_value = ("stdout", "test error", 1)

        assert_raise_library_error(
            lambda: lib.qdevice_setup(self.mock_runner),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "test error\nstdout",
                },
            ),
        )

        mock_initialized.assert_called_once_with()
        self.mock_runner.run.assert_called_once_with([_qnetd_cert_tool, "-i"])


@mock.patch("pcs.lib.corosync.qdevice_net.shutil.rmtree")
@mock.patch("pcs.lib.corosync.qdevice_net.qdevice_initialized")
class QdeviceDestroyTest(TestCase):
    def test_success(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        lib.qdevice_destroy()
        mock_rmtree.assert_called_once_with(
            settings.corosync_qdevice_net_server_certs_dir
        )

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
                },
            ),
        )
        mock_rmtree.assert_called_once_with(
            settings.corosync_qdevice_net_server_certs_dir
        )


class QdeviceStatusGenericTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info", lib.qdevice_status_generic_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-s"])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_generic_text(self.mock_runner, True),
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
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-s"])


class QdeviceStatusClusterTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info", lib.qdevice_status_cluster_text(self.mock_runner)
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l"])

    def test_success_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, verbose=True),
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l", "-v"])

    def test_success_cluster(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, "cluster"),
        )
        self.mock_runner.run.assert_called_once_with(
            [_qnetd_tool, "-l", "-c", "cluster"]
        )

    def test_success_cluster_verbose(self):
        self.mock_runner.run.return_value = ("status info", "", 0)
        self.assertEqual(
            "status info",
            lib.qdevice_status_cluster_text(self.mock_runner, "cluster", True),
        )
        self.mock_runner.run.assert_called_once_with(
            [_qnetd_tool, "-l", "-v", "-c", "cluster"]
        )

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
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with([_qnetd_tool, "-l"])


class QdeviceConnectedClustersTest(TestCase):
    def test_empty_status(self):
        status = ""
        self.assertEqual([], lib.qdevice_connected_clusters(status))

    def test_one_cluster(self):
        status = dedent(
            """\
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
        )
        self.assertEqual(["rhel72"], lib.qdevice_connected_clusters(status))

    def test_more_clusters(self):
        status = dedent(
            """\
            Cluster "rhel72":
            Cluster "rhel73":
            """
        )
        self.assertEqual(
            ["rhel72", "rhel73"], lib.qdevice_connected_clusters(status)
        )

    def test_invalid_status(self):
        status = dedent(
            """\
            Cluster:
                Cluster "rhel72":
            """
        )
        self.assertEqual([], lib.qdevice_connected_clusters(status))


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
@mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
class QdeviceSignCertificateRequestTest(CertificateTestCase):
    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized", lambda: True
    )
    def test_success(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.qdevice_sign_certificate_request(
            self.mock_runner, "certificate request", "clusterName"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [
                _qnetd_cert_tool,
                "-s",
                "-c",
                self.mock_tmpfile.name,
                "-n",
                "clusterName",
            ]
        )
        self.assertEqual("tool output", mock_get_cert.call_args[0][0])
        self.assertEqual(
            reports.messages.QdeviceCertificateSignError("tool output"),
            mock_get_cert.call_args[0][1]("tool output"),
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized", lambda: False
    )
    def test_not_initialized(self, mock_get_tmp_file, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner, "certificate request", "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                },
            ),
        )
        mock_get_tmp_file.assert_not_called()
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized", lambda: True
    )
    def test_input_write_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner, "certificate request", "clusterName"
            ),
        )

        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized", lambda: True
    )
    def test_sign_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner, "certificate request", "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_SIGN_ERROR,
                {
                    "reason": "tool output error\nstdout",
                },
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [
                _qnetd_cert_tool,
                "-s",
                "-c",
                self.mock_tmpfile.name,
                "-n",
                "clusterName",
            ]
        )
        mock_get_cert.assert_not_called()

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.qdevice_initialized", lambda: True
    )
    def test_output_read_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.qdevice_sign_certificate_request(
                self.mock_runner, "certificate request", "clusterName"
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [
                _qnetd_cert_tool,
                "-s",
                "-c",
                self.mock_tmpfile.name,
                "-n",
                "clusterName",
            ]
        )
        self.assertEqual("tool output", mock_get_cert.call_args[0][0])
        self.assertEqual(
            reports.messages.QdeviceCertificateSignError("tool output"),
            mock_get_cert.call_args[0][1]("tool output"),
        )


@mock.patch("pcs.lib.corosync.qdevice_net.shutil.rmtree")
@mock.patch("pcs.lib.corosync.qdevice_net.client_initialized")
class ClientDestroyTest(TestCase):
    def test_success(self, mock_initialized, mock_rmtree):
        mock_initialized.return_value = True
        lib.client_destroy()
        mock_rmtree.assert_called_once_with(
            settings.corosync_qdevice_net_client_certs_dir
        )

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
                },
            ),
        )
        mock_rmtree.assert_called_once_with(
            settings.corosync_qdevice_net_client_certs_dir
        )


class ClientSetupTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.original_path = settings.corosync_qdevice_net_client_certs_dir
        self.cert_dir = get_tmp_dir("tier0_lib_corosync_qdevice_net")
        settings.corosync_qdevice_net_client_certs_dir = self.cert_dir.name
        self.ca_file_path = os.path.join(
            settings.corosync_qdevice_net_client_certs_dir,
            settings.corosync_qdevice_net_client_ca_file_name,
        )
        with open(self.ca_file_path, "w") as my_file:
            my_file.write("to be overwritten")

    def tearDown(self):
        settings.corosync_qdevice_net_client_certs_dir = self.original_path
        self.cert_dir.cleanup()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_destroy")
    def test_success(self, mock_destroy):
        self.mock_runner.run.return_value = ("tool output", "", 0)

        lib.client_setup(
            self.mock_runner, "qnetd CA certificate".encode("utf-8")
        )
        with open(self.ca_file_path, "rb") as a_file:
            self.assertEqual(
                "qnetd CA certificate".encode("utf-8"), a_file.read()
            )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-i", "-c", self.ca_file_path]
        )
        mock_destroy.assert_called_once_with()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_destroy")
    def test_init_error(self, mock_destroy):
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_setup(
                self.mock_runner, "qnetd CA certificate".encode("utf-8")
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "tool output error\nstdout",
                },
            ),
        )
        with open(self.ca_file_path, "rb") as a_file:
            file_content = a_file.read()

        self.assertEqual("qnetd CA certificate".encode("utf-8"), file_content)
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-i", "-c", self.ca_file_path]
        )
        mock_destroy.assert_called_once_with()


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
class ClientGenerateCertificateRequestTest(CertificateTestCase):
    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_success(self, mock_get_cert):
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.client_generate_certificate_request(
            self.mock_runner, "clusterName"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-r", "-n", "clusterName"]
        )
        self.assertEqual(1, len(mock_get_cert.mock_calls))
        self.assertEqual(
            "tool output",
            mock_get_cert.call_args[0][0],
        )
        self.assertEqual(
            reports.messages.QdeviceInitializationError("net", "tool output"),
            mock_get_cert.call_args[0][1]("tool output"),
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized", lambda: False
    )
    def test_not_initialized(self, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.client_generate_certificate_request(
                self.mock_runner, "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                },
            ),
        )
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_tool_error(self, mock_get_cert):
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_generate_certificate_request(
                self.mock_runner, "clusterName"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_INITIALIZATION_ERROR,
                {
                    "model": "net",
                    "reason": "tool output error\nstdout",
                },
            ),
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-r", "-n", "clusterName"]
        )
        mock_get_cert.assert_not_called()


@mock.patch("pcs.lib.corosync.qdevice_net._get_output_certificate")
@mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
class ClientCertRequestToPk12Test(CertificateTestCase):
    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_success(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.return_value = "new certificate".encode("utf-8")

        result = lib.client_cert_request_to_pk12(
            self.mock_runner, "certificate request"
        )
        self.assertEqual(result, mock_get_cert.return_value)

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-M", "-c", self.mock_tmpfile.name]
        )
        self.assertEqual("tool output", mock_get_cert.call_args[0][0])
        self.assertEqual(
            reports.messages.QdeviceCertificateImportError("tool output"),
            mock_get_cert.call_args[0][1]("tool output"),
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized", lambda: False
    )
    def test_not_initialized(self, mock_get_tmp_file, mock_get_cert):
        assert_raise_library_error(
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner, "certificate request"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                },
            ),
        )
        mock_get_tmp_file.assert_not_called()
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_input_write_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner, "certificate request"
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_not_called()
        mock_get_cert.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_transform_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner, "certificate request"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "tool output error\nstdout",
                },
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-M", "-c", self.mock_tmpfile.name]
        )
        mock_get_cert.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_output_read_error(self, mock_get_tmp_file, mock_get_cert):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("tool output", "", 0)
        mock_get_cert.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_cert_request_to_pk12(
                self.mock_runner, "certificate request"
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "certificate request", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-M", "-c", self.mock_tmpfile.name]
        )
        self.assertEqual("tool output", mock_get_cert.call_args[0][0])
        self.assertEqual(
            reports.messages.QdeviceCertificateImportError("tool output"),
            mock_get_cert.call_args[0][1]("tool output"),
        )


@mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
class ClientImportCertificateAndKeyTest(CertificateTestCase):
    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_success(self, mock_get_tmp_file):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("tool output", "", 0)

        lib.client_import_certificate_and_key(
            self.mock_runner, "pk12 certificate"
        )

        mock_get_tmp_file.assert_called_once_with(
            "pk12 certificate", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-m", "-c", self.mock_tmpfile.name]
        )

    @mock.patch(
        "pcs.lib.corosync.qdevice_net.client_initialized", lambda: False
    )
    def test_not_initialized(self, mock_get_tmp_file):
        assert_raise_library_error(
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner, "pk12 certificate"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_INITIALIZED,
                {
                    "model": "net",
                },
            ),
        )

        mock_get_tmp_file.assert_not_called()
        self.mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_input_write_error(self, mock_get_tmp_file):
        mock_get_tmp_file.return_value.__enter__.side_effect = LibraryError

        self.assertRaises(
            LibraryError,
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner, "pk12 certificate"
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "pk12 certificate", binary=True
        )
        self.mock_runner.run.assert_not_called()

    @mock.patch("pcs.lib.corosync.qdevice_net.client_initialized", lambda: True)
    def test_import_error(self, mock_get_tmp_file):
        mock_get_tmp_file.return_value.__enter__.return_value = (
            self.mock_tmpfile
        )
        self.mock_runner.run.return_value = ("stdout", "tool output error", 1)

        assert_raise_library_error(
            lambda: lib.client_import_certificate_and_key(
                self.mock_runner, "pk12 certificate"
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "tool output error\nstdout",
                },
            ),
        )

        mock_get_tmp_file.assert_called_once_with(
            "pk12 certificate", binary=True
        )
        self.mock_runner.run.assert_called_once_with(
            [_client_cert_tool, "-m", "-c", self.mock_tmpfile.name]
        )


class GetOutputCertificateTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.file_path = get_test_resource("qdevice-certs/qnetd-cacert.crt")
        with open(self.file_path, "rb") as a_file:
            self.file_data = a_file.read()

    def test_success(self):
        cert_tool_output = dedent(
            """
            some line
            Certificate stored in {0}
            some other line
            """.format(
                self.file_path
            )
        )
        report_func = mock.MagicMock()

        self.assertEqual(
            self.file_data,
            lib._get_output_certificate(cert_tool_output, report_func),
        )
        report_func.assert_not_called()

    def test_success_request(self):
        cert_tool_output = dedent(
            """
            some line
            Certificate request stored in {0}
            some other line
            """.format(
                self.file_path
            )
        )
        report_func = mock.MagicMock()

        self.assertEqual(
            self.file_data,
            lib._get_output_certificate(cert_tool_output, report_func),
        )
        report_func.assert_not_called()

    def test_message_not_found(self):
        cert_tool_output = "some rubbish output"
        report_item_message = reports.messages.QdeviceCertificateImportError

        assert_raise_library_error(
            lambda: lib._get_output_certificate(
                cert_tool_output,
                report_item_message,
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": cert_tool_output,
                },
            ),
        )

    def test_cannot_read_file(self):
        cert_tool_output = dedent(
            """
            some line
            Certificate request stored in {0}.bad
            some other line
            """.format(
                self.file_path
            )
        )
        report_item_message = reports.messages.QdeviceCertificateImportError

        assert_raise_library_error(
            lambda: lib._get_output_certificate(
                cert_tool_output,
                report_item_message,
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                {
                    "reason": "{0}.bad: No such file or directory".format(
                        self.file_path
                    ),
                },
            ),
        )
