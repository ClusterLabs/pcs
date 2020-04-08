from unittest import mock, TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.common.file import RawFileError
from pcs.lib.commands import pcsd


class SynchronizeSslCertificates(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.pcsd_ssl_cert = "pcsd ssl cert"
        self.pcsd_ssl_key = "pcsd ssl key"
        self.node_names = [
            "rh7-1",
            "rh7-2",
        ]  # It matches nodes in corosync.conf
        (self.config.corosync_conf.load().env.set_known_nodes(self.node_names))

    def test_success(self):
        (
            self.config.fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
            .http.host.send_pcsd_cert(
                cert=self.pcsd_ssl_cert,
                key=self.pcsd_ssl_key,
                node_labels=self.node_names,
            )
        )

        pcsd.synchronize_ssl_certificate(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=self.node_names,
                )
            ]
            + [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS, node=node,
                )
                for node in self.node_names
            ]
        )

    def test_some_node_names_missing(self):
        nodes = ["rh7-2"]
        (
            self.config.corosync_conf.load(
                filename="corosync-some-node-names.conf",
                instead="corosync_conf.load",
            )
            .fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
            .http.host.send_pcsd_cert(
                cert=self.pcsd_ssl_cert,
                key=self.pcsd_ssl_key,
                node_labels=nodes,
            )
        )

        pcsd.synchronize_ssl_certificate(self.env_assist.get_env())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=nodes,
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
            ]
            + [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS, node=node,
                )
                for node in nodes
            ]
        )

    def test_all_node_names_missing(self):
        (
            self.config.corosync_conf.load(
                filename="corosync-no-node-names.conf",
                instead="corosync_conf.load",
            )
            .fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: pcsd.synchronize_ssl_certificate(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=False,
                ),
                fixture.error(report_codes.COROSYNC_CONFIG_NO_NODES_DEFINED,),
            ]
        )

    def test_fail_communication(self):
        error = "an error"
        (
            self.config.fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
            .http.host.send_pcsd_cert(
                cert=self.pcsd_ssl_cert,
                key=self.pcsd_ssl_key,
                communication_list=[
                    {
                        "label": self.node_names[0],
                        "response_code": 400,
                        "output": error,
                    }
                ]
                + [dict(label=node) for node in self.node_names[1:]],
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: pcsd.synchronize_ssl_certificate(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=self.node_names,
                )
            ]
            + [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS, node=node,
                )
                for node in self.node_names[1:]
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_names[0],
                    command="remote/set_certs",
                    reason=error,
                )
            ]
        )

    def test_fail_all_nodes_unknown(self):
        (
            self.config.env.set_known_nodes([])
            .fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: pcsd.synchronize_ssl_certificate(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=self.node_names,
                ),
                fixture.error(report_codes.NONE_HOST_FOUND),
            ]
        )

    def test_fail_some_nodes_unknown(self):
        (
            self.config.env.set_known_nodes(self.node_names[1:])
            .fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: pcsd.synchronize_ssl_certificate(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=[self.node_names[0]],
                ),
            ]
        )

    def test_some_nodes_unknown_forced(self):
        (
            self.config.env.set_known_nodes(self.node_names[1:])
            .fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=self.pcsd_ssl_cert)(),
                name="fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=self.pcsd_ssl_key)(),
                name="fs.open.pcsd_ssl_key",
            )
            .http.host.send_pcsd_cert(
                cert=self.pcsd_ssl_cert,
                key=self.pcsd_ssl_key,
                node_labels=self.node_names[1:],
            )
        )

        pcsd.synchronize_ssl_certificate(
            self.env_assist.get_env(), skip_offline=True
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND, host_list=[self.node_names[0]]
                ),
            ]
            + [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=self.node_names[1:],
                )
            ]
            + [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS, node=node,
                )
                for node in self.node_names[1:]
            ]
        )

    def test_fail_reading_files(self):
        (
            self.config.fs.open(
                settings.pcsd_cert_location,
                name="fs.open.pcsd_ssl_cert",
                side_effect=EnvironmentError(1, "error cert"),
            ).fs.open(
                settings.pcsd_key_location,
                name="fs.open.pcsd_ssl_key",
                side_effect=EnvironmentError(1, "error key"),
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: pcsd.synchronize_ssl_certificate(self.env_assist.get_env()),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_type_code="PCSD_SSL_CERT",
                    file_path=settings.pcsd_cert_location,
                    reason="error cert",
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_type_code="PCSD_SSL_KEY",
                    file_path=settings.pcsd_key_location,
                    reason="error key",
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )
