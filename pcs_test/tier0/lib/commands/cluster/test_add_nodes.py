# pylint: disable=too-many-lines
# pylint: disable=no-member
import base64
import json
import os.path
from functools import partial
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.file import RawFileError
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import patch_getaddrinfo

from .common import (
    CLUSTER_NAME,
    QDEVICE_HOST,
    corosync_conf_fixture,
    corosync_node_fixture,
    get_two_node,
    node_fixture,
)


def generate_nodes(existing_nodes_num, new_nodes_num):
    return (
        [f"node{i}" for i in range(1, existing_nodes_num + 1)],
        [
            f"node{i}"
            for i in range(
                existing_nodes_num + 1, existing_nodes_num + new_nodes_num + 1
            )
        ],
    )


class LocalConfig:
    def __init__(self, call_collection, wrap_helper, config):
        del wrap_helper, call_collection
        self.config = config
        self.expected_reports = []

    def set_expected_reports_list(self, expected_reports):
        self.expected_reports = expected_reports

    def setup_qdevice_part1(self, mock_get_tmp_file, new_nodes):
        cert = b"cert"
        ca_cert = b"ca_cert"
        cert_req_path = "cert_req_path"
        tmp_file_path = "tmp_file_path"
        tempfile_mock = mock.Mock(spec_set=["close", "name"])
        tempfile_mock.name = tmp_file_path
        mock_get_tmp_file.return_value.__enter__.return_value = tempfile_mock

        local_prefix = "local.setup_qdevice."
        (
            self.config.http.corosync.qdevice_net_get_ca_cert(
                ca_cert=ca_cert,
                node_labels=[QDEVICE_HOST],
                name=f"{local_prefix}http.corosync.qdevice_ca_cert",
            )
            .http.corosync.qdevice_net_client_setup(
                ca_cert=ca_cert,
                node_labels=new_nodes,
                name=f"{local_prefix}http.corosync.qdevice_client_setup",
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name=f"{local_prefix}fs.exists.corosync_certs_db",
            )
            .runner.corosync.qdevice_generate_cert(
                CLUSTER_NAME,
                cert_req_path=cert_req_path,
                name=f"{local_prefix}runner.corosync.qdevice_generate_cert",
            )
            .fs.open(
                cert_req_path,
                return_value=mock.mock_open(read_data=cert)(),
                mode="rb",
                name=f"{local_prefix}fs.open.cert_req_read",
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
                )
            ]
        )

    def setup_qdevice_part2(self, mock_get_tmp_file, new_nodes):
        cert = b"cert"
        tmp_file_path = "tmp_file_path"
        pk12_cert_path = "pk12_cert_path"
        pk12_cert = b"pk12_cert"
        tempfile_mock = mock.Mock(spec_set=["close", "name"])
        tempfile_mock.name = tmp_file_path
        mock_get_tmp_file.return_value.__enter__.return_value = tempfile_mock

        local_prefix = "local.setup_qdevice."
        (
            self.config.http.corosync.qdevice_net_sign_certificate(
                CLUSTER_NAME,
                cert=cert,
                signed_cert=b"signed cert",
                node_labels=[QDEVICE_HOST],
                name=f"{local_prefix}http.corosync.qdevice_sign_certificate",
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name=f"{local_prefix}fs.exists.corosync_certs_db2",
            )
            .runner.corosync.qdevice_get_pk12(
                cert_path=tmp_file_path,
                output_path=pk12_cert_path,
                name=f"{local_prefix}runner.corosync.qdevice_get_pk12",
            )
            .fs.open(
                pk12_cert_path,
                return_value=mock.mock_open(read_data=pk12_cert)(),
                mode="rb",
                name=f"{local_prefix}fs.open.pk12_cert_read",
            )
            .http.corosync.qdevice_net_client_import_cert_and_key(
                cert=pk12_cert,
                node_labels=new_nodes,
                name=(
                    f"{local_prefix}http.corosync"
                    ".qdevice_client_import_cert_and_key"
                ),
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in new_nodes
            ]
        )

    def setup_qdevice(self, mock_get_tmp_file, new_nodes):
        self.setup_qdevice_part1(mock_get_tmp_file, new_nodes)
        self.setup_qdevice_part2(mock_get_tmp_file, new_nodes)

    def distribute_and_reload_corosync_conf(
        self, corosync_conf_content, existing_nodes, new_nodes
    ):
        local_prefix = "local.distribute_and_reload_corosync_conf."
        (
            self.config.http.corosync.set_corosync_conf(
                corosync_conf_content,
                node_labels=existing_nodes + new_nodes,
                name=f"{local_prefix}http.corosync.set_corosync_conf",
            ).http.corosync.reload_corosync_conf(
                node_labels=existing_nodes[:1],
                name=f"{local_prefix}http.corosync.reload_corosync_conf",
            )
        )
        self.expected_reports.extend(
            [fixture.info(reports.codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in existing_nodes + new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node=existing_nodes[0],
                )
            ]
        )

    def atb_needed(self, node_labels):
        local_prefix = "local.atb_needed."
        (
            self.config.services.is_installed(
                "sbd",
                return_value=True,
                name=f"{local_prefix}services.is_installed.sbd",
            )
            .services.is_enabled(
                "sbd",
                return_value=True,
                name=f"{local_prefix}services.is_enabled.sbd",
            )
            .local.read_sbd_config(name_sufix="-atb_needed")
            .http.corosync.check_corosync_offline(
                node_labels=node_labels,
                name=f"{local_prefix}http.corosync.check_corosync_offline",
            )
        )
        self.expected_reports.extend(
            [
                fixture.warn(
                    reports.codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
                ),
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
            ]
            + [
                fixture.info(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=node,
                )
                for node in node_labels
            ]
        )

    def read_sbd_config(self, config_content="", name_sufix=""):
        local_prefix = "local.read_sbd_config."
        (
            self.config.fs.exists(
                settings.sbd_config,
                return_value=True,
                name=f"{local_prefix}fs.exists.sbd_config{name_sufix}",
            ).fs.open(
                settings.sbd_config,
                return_value=mock.mock_open(read_data=config_content)(),
                name=f"{local_prefix}fs.open.sbd_config_read{name_sufix}",
            )
        )

    def check_sbd(self, node_labels, with_devices=True):
        self.config.http.sbd.check_sbd(
            communication_list=_get_check_sbd_communication_list(
                node_labels,
                with_devices=with_devices,
            ),
            name="local.check_sbd.http.sbd_check_sbd",
        )
        self.expected_reports.extend(
            [fixture.info(reports.codes.SBD_CHECK_STARTED)]
            + [
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node=node)
                for node in node_labels
            ]
        )

    def disable_sbd(self, node_labels):
        self.config.http.sbd.disable_sbd(
            node_labels=node_labels,
            name="local.disable_sbd.http.sbd.disable_sbd",
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in node_labels
            ]
        )

    def setup_sbd(self, local_config, config_generator, node_labels):
        local_prefix = "local.setup_sbd."
        (
            self.config.fs.open(
                settings.sbd_config,
                return_value=mock.mock_open(read_data=local_config)(),
                name=f"{local_prefix}fs.open.sbd_config",
            )
            .http.sbd.set_sbd_config(
                config_generator=config_generator,
                node_labels=node_labels,
                name=f"{local_prefix}http.sbd.set_sbd_config",
            )
            .http.sbd.enable_sbd(node_labels=node_labels)
        )
        self.expected_reports.extend(
            [fixture.info(reports.codes.SBD_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.SBD_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in node_labels
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in node_labels
            ]
        )

    def setup_booth(self, node_labels):
        config_dir = settings.booth_config_dir
        config_file = "booth.conf"
        authfile = "booth.authfile"
        config_path = os.path.join(config_dir, config_file)
        authfile_path = os.path.join(config_dir, authfile)
        config_content = "authfile = {}\n".format(authfile_path)
        authfile_content = b"booth authfile"
        local_prefix = "local.setup_booth."
        (
            self.config.fs.isdir(
                settings.booth_config_dir,
                name=f"{local_prefix}fs.isdir.booth_config_dir",
            )
            .fs.listdir(
                settings.booth_config_dir,
                [config_file, "something", authfile],
                name=f"{local_prefix}fs.listdir.booth_config_dir",
            )
            .fs.isfile(
                config_path,
                name=f"{local_prefix}fs.isfile.booth_config_file",
            )
            .raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                config_path,
                content=config_content.encode("utf-8"),
                name=f"{local_prefix}raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                authfile_path,
                content=authfile_content,
                name=f"{local_prefix}raw_file.read.booth_authfile_read",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=config_file,
                        data=config_content,
                        is_authfile=False,
                    ),
                    dict(
                        name=authfile,
                        data=base64.b64encode(authfile_content).decode("utf-8"),
                        is_authfile=True,
                    ),
                ],
                saved=[config_file, authfile],
                node_labels=node_labels,
                name=f"{local_prefix}http.booth.save_files",
            )
        )
        self.expected_reports.extend(
            [fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[authfile, config_file],
                )
                for node in node_labels
            ]
        )

    def get_host_info(self, node_labels):
        self.config.http.host.get_host_info(
            node_labels=node_labels,
            output_data=dict(
                services={
                    service: dict(installed=True, enabled=False, running=False)
                    for service in ("corosync", "pacemaker", "pcsd")
                },
                cluster_configuration_exists=False,
            ),
            name="local.get_host_info.http.host.get_host_info",
        )

    def no_file_sync(self):
        local_prefix = "local.no_file_sync."
        (
            self.config.fs.isfile(
                settings.corosync_authkey_file,
                return_value=False,
                name=f"{local_prefix}fs.isfile.corosync_authkey",
            )
            .fs.isfile(
                settings.pacemaker_authkey_file,
                return_value=False,
                name=f"{local_prefix}fs.isfile.pacemaker_authkey",
            )
            .fs.isfile(
                settings.pcsd_dr_config_location,
                return_value=False,
                name=f"{local_prefix}fs.isfile.pcsd_disaster_recovery",
            )
            .fs.isfile(
                settings.pcsd_settings_conf_location,
                return_value=False,
                name=f"{local_prefix}fs.isfile.pcsd_settings",
            )
        )

    def files_sync(self, node_labels):
        corosync_authkey_content = b"corosync authfile"
        pcmk_authkey_content = b"pcmk authfile"
        pcs_disaster_recovery_content = b"disaster recovery config data"
        pcs_settings_content = "pcs_settings.conf data"
        file_list = [
            "corosync authkey",
            "pacemaker authkey",
            "disaster-recovery config",
            "pcs_settings.conf",
        ]
        local_prefix = "local.files_sync."
        (
            self.config.fs.isfile(
                settings.corosync_authkey_file,
                return_value=True,
                name=f"{local_prefix}fs.isfile.corosync_authkey",
            )
            .fs.open(
                settings.corosync_authkey_file,
                return_value=mock.mock_open(
                    read_data=corosync_authkey_content
                )(),
                mode="rb",
                name=f"{local_prefix}fs.open.corosync_authkey_read",
            )
            .fs.isfile(
                settings.pacemaker_authkey_file,
                return_value=True,
                name=f"{local_prefix}fs.isfile.pacemaker_authkey",
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                return_value=mock.mock_open(read_data=pcmk_authkey_content)(),
                mode="rb",
                name=f"{local_prefix}fs.open.pcmk_authkey_read",
            )
            .fs.isfile(
                settings.pcsd_dr_config_location,
                return_value=True,
                name=f"{local_prefix}fs.isfile.pcsd_disaster_recovery",
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                return_value=(
                    mock.mock_open(read_data=pcs_disaster_recovery_content)()
                ),
                mode="rb",
                name=f"{local_prefix}fs.open.pcsd_disaster_recovery_read",
            )
            .fs.isfile(
                settings.pcsd_settings_conf_location,
                return_value=True,
                name=f"{local_prefix}fs.isfile.pcsd_settings",
            )
            .fs.open(
                settings.pcsd_settings_conf_location,
                return_value=mock.mock_open(read_data=pcs_settings_content)(),
                name=f"{local_prefix}fs.open.pcsd_settings_conf_read",
            )
            .http.files.put_files(
                node_labels=node_labels,
                pcmk_authkey=pcmk_authkey_content,
                corosync_authkey=corosync_authkey_content,
                pcs_disaster_recovery_conf=pcs_disaster_recovery_content,
                pcs_settings_conf=pcs_settings_content,
                name=f"{local_prefix}http.files.put_files",
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.FILES_DISTRIBUTION_STARTED,
                    file_list=file_list,
                    node_list=node_labels,
                )
            ]
            + [
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=file,
                )
                for node in node_labels
                for file in file_list
            ]
        )

    def pcsd_ssl_cert_sync_disabled(self):
        local_prefix = "local.pcsd_ssl_cert_sync_disabled."
        (
            self.config.fs.isfile(
                settings.pcsd_config,
                name=f"{local_prefix}fs.isfile.pcsd_config",
            ).fs.open(
                settings.pcsd_config,
                # Tests for other cases are in SslCertSync class.
                mock.mock_open(
                    read_data="PCSD_SSL_CERT_SYNC_ENABLED=false\n"
                )(),
                name=f"{local_prefix}fs.open.pcsd_config",
            )
        )

    def pcsd_ssl_cert_sync_enabled(self):
        local_prefix = "local.pcsd_ssl_cert_sync_enabled."
        (
            self.config.fs.isfile(
                settings.pcsd_config,
                name=f"{local_prefix}fs.isfile.pcsd_config",
            ).fs.open(
                settings.pcsd_config,
                # Tests for other cases are in SslCertSync class.
                mock.mock_open(read_data="PCSD_SSL_CERT_SYNC_ENABLED=true\n")(),
                name=f"{local_prefix}fs.open.pcsd_config",
            )
        )

    def pcsd_ssl_cert_sync(self, node_labels):
        local_prefix = "local.pcsd_ssl_cert_sync."
        pcsd_ssl_cert = "pcsd ssl cert"
        pcsd_ssl_key = "pcsd ssl key"
        (
            self.config.fs.open(
                settings.pcsd_cert_location,
                mock.mock_open(read_data=pcsd_ssl_cert)(),
                name=f"{local_prefix}fs.open.pcsd_ssl_cert",
            )
            .fs.open(
                settings.pcsd_key_location,
                mock.mock_open(read_data=pcsd_ssl_key)(),
                name=f"{local_prefix}fs.open.pcsd_ssl_key",
            )
            .http.host.send_pcsd_cert(
                cert=pcsd_ssl_cert, key=pcsd_ssl_key, node_labels=node_labels
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=node_labels,
                )
            ]
            + [
                fixture.info(
                    reports.codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS,
                    node=node,
                )
                for node in node_labels
            ]
        )


get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})


class CheckLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options,
                )
            ],
            expected_in_processor=False,
        )

    def test_mock_corosync(self):
        self.config.env.set_corosync_conf_data(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )
        self.assert_live_required(["COROSYNC_CONF"])

    def test_mock_cib(self):
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required(["CIB"])

    def test_mock_cib_corosync(self):
        self.config.env.set_corosync_conf_data(
            corosync_conf_fixture(
                self.existing_corosync_nodes,
                get_two_node(len(self.existing_corosync_nodes)),
            )
        )
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required(["CIB", "COROSYNC_CONF"])


class AddNodesSuccessMinimal(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes = ()
        self.new_nodes = ()
        self.expected_reports = []

    def set_up(self, existing_nodes_num, new_nodes_num):
        self.existing_nodes, self.new_nodes = generate_nodes(
            existing_nodes_num, new_nodes_num
        )
        patch_getaddrinfo(self, self.new_nodes)
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.new_nodes + self.existing_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        is_sbd_installed_name = "_services.is_installed.sbd.False"
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    existing_corosync_nodes, get_two_node(existing_nodes_num)
                )
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .services.is_installed(
                "sbd", return_value=False, name=is_sbd_installed_name
            )
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, existing_nodes_num + 1
                        )
                    ],
                    get_two_node(existing_nodes_num + new_nodes_num),
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        if (existing_nodes_num + new_nodes_num) % 2 != 0:
            self.config.calls.remove(is_sbd_installed_name)

        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )

    def _test_minimal(self, existing, new):
        self.set_up(existing, new)
        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

        self.env_assist.assert_reports(self.expected_reports)

    def test_minimal_1_existing_1_new(self):
        self._test_minimal(1, 1)

    def test_minimal_1_existing_2_new(self):
        self._test_minimal(1, 2)

    def test_minimal_1_existing_3_new(self):
        self._test_minimal(1, 3)

    def test_minimal_2_existing_1_new(self):
        self._test_minimal(2, 1)

    def test_minimal_2_existing_2_new(self):
        self._test_minimal(2, 2)

    def test_minimal_2_existing_3_new(self):
        self._test_minimal(2, 3)

    def test_minimal_3_existing_1_new(self):
        self._test_minimal(3, 1)

    def test_minimal_3_existing_2_new(self):
        self._test_minimal(3, 2)

    def test_minimal_3_existing_3_new(self):
        self._test_minimal(3, 3)

    def _test_enable(self, existing, new):
        self.set_up(existing, new)
        self.config.http.host.enable_cluster(
            node_labels=self.new_nodes,
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            enable=True,
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.CLUSTER_ENABLE_STARTED,
                    host_name_list=sorted(self.new_nodes),
                )
            ]
            + [
                fixture.info(reports.codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in self.new_nodes
            ]
        )

    def test_enable_1_existing_1_new(self):
        self._test_enable(1, 1)

    def test_enable_1_existing_2_new(self):
        self._test_enable(1, 2)

    def test_enable_1_existing_3_new(self):
        self._test_enable(1, 3)

    def test_enable_2_existing_1_new(self):
        self._test_enable(2, 1)

    def test_enable_2_existing_2_new(self):
        self._test_enable(2, 2)

    def test_enable_2_existing_3_new(self):
        self._test_enable(2, 3)

    def test_enable_3_existing_1_new(self):
        self._test_enable(3, 1)

    def test_enable_3_existing_2_new(self):
        self._test_enable(3, 2)

    def test_enable_3_existing_3_new(self):
        self._test_enable(3, 3)

    def _test_start(self, existing, new):
        self.set_up(existing, new)
        self.config.http.host.start_cluster(node_labels=self.new_nodes)

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            start=True,
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_STARTED,
                    host_name_list=self.new_nodes,
                )
            ]
        )

    def test_start_1_existing_1_new(self):
        self._test_start(1, 1)

    def test_start_1_existing_2_new(self):
        self._test_start(1, 2)

    def test_start_1_existing_3_new(self):
        self._test_start(1, 3)

    def test_start_2_existing_1_new(self):
        self._test_start(2, 1)

    def test_start_2_existing_2_new(self):
        self._test_start(2, 2)

    def test_start_2_existing_3_new(self):
        self._test_start(2, 3)

    def test_start_3_existing_1_new(self):
        self._test_start(3, 1)

    def test_start_3_existing_2_new(self):
        self._test_start(3, 2)

    def test_start_3_existing_3_new(self):
        self._test_start(3, 3)

    def _test_start_wait(self, existing, new):
        self.set_up(existing, new)
        (
            self.config.http.host.start_cluster(
                node_labels=self.new_nodes
            ).http.host.check_pacemaker_started(self.new_nodes)
        )

        with mock.patch("time.sleep", lambda secs: None):
            cluster.add_nodes(
                self.env_assist.get_env(),
                # [{"name": "node4"}],
                [{"name": node} for node in self.new_nodes],
                start=True,
                wait=True,
            )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_STARTED,
                    host_name_list=sorted(self.new_nodes),
                ),
                fixture.info(
                    reports.codes.WAIT_FOR_NODE_STARTUP_STARTED,
                    node_name_list=self.new_nodes,
                ),
            ]
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_SUCCESS,
                    node=node,
                )
                for node in self.new_nodes
            ]
        )

    def test_start_wait_1_existing_1_new(self):
        self._test_start_wait(1, 1)

    def test_start_wait_1_existing_2_new(self):
        self._test_start_wait(1, 2)

    def test_start_wait_1_existing_3_new(self):
        self._test_start_wait(1, 3)

    def test_start_wait_2_existing_1_new(self):
        self._test_start_wait(2, 1)

    def test_start_wait_2_existing_2_new(self):
        self._test_start_wait(2, 2)

    def test_start_wait_2_existing_3_new(self):
        self._test_start_wait(2, 3)

    def test_start_wait_3_existing_1_new(self):
        self._test_start_wait(3, 1)

    def test_start_wait_3_existing_2_new(self):
        self._test_start_wait(3, 2)

    def test_start_wait_3_existing_3_new(self):
        self._test_start_wait(3, 3)

    def _test_enable_start(self, existing, new):
        self.set_up(existing, new)
        (
            self.config.http.host.enable_cluster(
                node_labels=self.new_nodes
            ).http.host.start_cluster(node_labels=self.new_nodes)
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            enable=True,
            start=True,
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.CLUSTER_ENABLE_STARTED,
                    host_name_list=sorted(self.new_nodes),
                )
            ]
            + [
                fixture.info(reports.codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in self.new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_STARTED,
                    host_name_list=sorted(self.new_nodes),
                )
            ]
        )

    def test_enable_start_1_existing_1_new(self):
        self._test_enable_start(1, 1)

    def test_enable_start_1_existing_2_new(self):
        self._test_enable_start(1, 2)

    def test_enable_start_1_existing_3_new(self):
        self._test_enable_start(1, 3)

    def test_enable_start_2_existing_1_new(self):
        self._test_enable_start(2, 1)

    def test_enable_start_2_existing_2_new(self):
        self._test_enable_start(2, 2)

    def test_enable_start_2_existing_3_new(self):
        self._test_enable_start(2, 3)

    def test_enable_start_3_existing_1_new(self):
        self._test_enable_start(3, 1)

    def test_enable_start_3_existing_2_new(self):
        self._test_enable_start(3, 2)

    def test_enable_start_3_existing_3_new(self):
        self._test_enable_start(3, 3)

    def _test_enable_start_wait(self, existing, new):
        self.set_up(existing, new)
        (
            self.config.http.host.enable_cluster(node_labels=self.new_nodes)
            .http.host.start_cluster(node_labels=self.new_nodes)
            .http.host.check_pacemaker_started(self.new_nodes)
        )
        with mock.patch("time.sleep", lambda secs: None):
            cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
                enable=True,
                start=True,
                wait=True,
            )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.CLUSTER_ENABLE_STARTED,
                    host_name_list=sorted(self.new_nodes),
                )
            ]
            + [
                fixture.info(reports.codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in self.new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_STARTED,
                    host_name_list=self.new_nodes,
                ),
                fixture.info(
                    reports.codes.WAIT_FOR_NODE_STARTUP_STARTED,
                    node_name_list=self.new_nodes,
                ),
            ]
            + [
                fixture.info(
                    reports.codes.CLUSTER_START_SUCCESS,
                    node=node,
                )
                for node in self.new_nodes
            ]
        )

    def test_enable_start_wait_1_existing_1_new(self):
        self._test_enable_start_wait(1, 1)

    def test_enable_start_wait_1_existing_2_new(self):
        self._test_enable_start_wait(1, 2)

    def test_enable_start_wait_1_existing_3_new(self):
        self._test_enable_start_wait(1, 3)

    def test_enable_start_wait_2_existing_1_new(self):
        self._test_enable_start_wait(2, 1)

    def test_enable_start_wait_2_existing_2_new(self):
        self._test_enable_start_wait(2, 2)

    def test_enable_start_wait_2_existing_3_new(self):
        self._test_enable_start_wait(2, 3)

    def test_enable_start_wait_3_existing_1_new(self):
        self._test_enable_start_wait(3, 1)

    def test_enable_start_wait_3_existing_2_new(self):
        self._test_enable_start_wait(3, 2)

    def test_enable_start_wait_3_existing_3_new(self):
        self._test_enable_start_wait(3, 3)


def _get_watchdog(node):
    return f"/dev/watchdog-{node}"


def _get_devices(node):
    return [f"/dev/block-{node}-{i}" for i in range(3)]


def _get_addrs(node, count=8):
    return [f"{node}-corosync{i}" for i in range(count)]


def _flat_list(list_of_lists):
    return [item for _list in list_of_lists for item in _list]


def _get_check_sbd_communication_list(node_list, with_devices=True):
    return [
        fixture.check_sbd_comm_success_fixture(
            node,
            _get_watchdog(node),
            _get_devices(node) if with_devices else [],
        )
        for node in node_list
    ]


def sbd_config_generator(node, with_devices=True):
    devices = ""
    if with_devices:
        devices = 'SBD_DEVICE="{}"\n'.format(
            ";".join([f"/dev/block-{node}-{i}" for i in range(3)])
        )
    return dedent(
        """\
    # This file has been generated by pcs.
    {devices}SBD_OPTS="-n {node_name}"
    SBD_WATCHDOG_DEV=/dev/watchdog-{node_name}
    """
    ).format(
        devices=devices,
        node_name=node,
    )


class SslCertSync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.existing_nodes, self.new_nodes = generate_nodes(3, 1)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]

        patch_getaddrinfo(self, self.new_nodes)
        (
            self.config.local.set_expected_reports_list(self.expected_reports)
            .env.set_known_nodes(
                self.existing_nodes + self.new_nodes + [QDEVICE_HOST]
            )
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
        )

        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )

    def _assert_certs_not_synced(self):
        (
            self.config.http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, node_id)
                        for node_id, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

        self.env_assist.assert_reports(self.expected_reports)

    def test_certs_not_synced_if_pcsd_config_missing(self):
        self.config.fs.isfile(
            settings.pcsd_config,
            return_value=False,
            name="fs.isfile.pcsd_config",
        )
        self._assert_certs_not_synced()

    def test_certs_not_synced_if_pcsd_config_empty(self):
        (
            self.config.fs.isfile(
                settings.pcsd_config, name="fs.isfile.pcsd_config"
            ).fs.open(
                settings.pcsd_config,
                mock.mock_open(read_data="")(),
                name="fs.open.pcsd_config",
            )
        )
        self._assert_certs_not_synced()

    def test_certs_not_synced_if_pcsd_config_commented(self):
        (
            self.config.fs.isfile(
                settings.pcsd_config, name="fs.isfile.pcsd_config"
            ).fs.open(
                settings.pcsd_config,
                mock.mock_open(
                    read_data="#PCSD_SSL_CERT_SYNC_ENABLED=true\n"
                )(),
                name="fs.open.pcsd_config",
            )
        )
        self._assert_certs_not_synced()


class AddNodeFull(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.existing_nodes, self.new_nodes = generate_nodes(3, 3)
        self.existing_corosync_nodes = [
            corosync_node_fixture(node_id, node, _get_addrs(node))
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]

        patch_getaddrinfo(
            self, _flat_list([_get_addrs(node) for node in self.new_nodes])
        )
        (
            self.config.local.set_expected_reports_list(self.expected_reports)
            .env.set_known_nodes(
                self.existing_nodes + self.new_nodes + [QDEVICE_HOST]
            )
            .services.is_enabled("sbd", return_value=True)
        )

    @mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
    def test_with_qdevice(self, mock_get_tmp_file):
        sbd_config = "SBD_DEVICE=/device\n"
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes,
                    qdevice_net=True,
                )
            )
            .runner.cib.load()
            .local.read_sbd_config(sbd_config)
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .local.check_sbd(self.new_nodes)
            .local.pcsd_ssl_cert_sync_enabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.setup_qdevice(mock_get_tmp_file, self.new_nodes)
            .local.setup_sbd(sbd_config, sbd_config_generator, self.new_nodes)
            .local.setup_booth(self.new_nodes)
            .local.files_sync(self.new_nodes)
            .local.pcsd_ssl_cert_sync(self.new_nodes)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        corosync_node_fixture(node_id, node, _get_addrs(node))
                        for node_id, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                    qdevice_net=True,
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [
                dict(
                    name=node,
                    addrs=_get_addrs(node),
                    watchdog=_get_watchdog(node),
                    devices=_get_devices(node),
                )
                for node in self.new_nodes
            ],
        )

        self.env_assist.assert_reports(self.expected_reports)

    def test_watchdog_not_supported(self):
        sbd_config = "SBD_DEVICE=/device\n"
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .local.read_sbd_config(sbd_config)
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.atb_needed(self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .http.sbd.check_sbd(
                communication_list=[
                    dict(
                        label=node,
                        output=json.dumps(
                            {
                                "sbd": {
                                    "installed": True,
                                },
                                "watchdog": {
                                    "exist": True,
                                    "path": _get_watchdog(node),
                                    "is_supported": False,
                                },
                                "device_list": [
                                    dict(
                                        path=dev, exist=True, block_device=True
                                    )
                                    for dev in _get_devices(node)
                                ],
                            }
                        ),
                        param_list=[
                            ("watchdog", _get_watchdog(node)),
                            ("device_list", json.dumps(_get_devices(node))),
                        ],
                    )
                    for node in self.new_nodes
                ],
            )
            .local.pcsd_ssl_cert_sync_enabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    dict(
                        name=node,
                        addrs=_get_addrs(node),
                        watchdog=_get_watchdog(node),
                        devices=_get_devices(node),
                    )
                    for node in self.new_nodes
                ],
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.info(reports.codes.SBD_CHECK_STARTED)]
            + [
                fixture.error(
                    reports.codes.SBD_WATCHDOG_NOT_SUPPORTED,
                    node=node,
                    watchdog=_get_watchdog(node),
                )
                for node in self.new_nodes
            ]
        )

    def test_no_watchdog_validation(self):
        sbd_config = "SBD_DEVICE=/device\n"
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .local.read_sbd_config(sbd_config)
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.atb_needed(self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .http.sbd.check_sbd(
                communication_list=[
                    dict(
                        label=node,
                        output=json.dumps(
                            {
                                "sbd": {
                                    "installed": True,
                                },
                                "device_list": [
                                    dict(
                                        path=dev, exist=True, block_device=True
                                    )
                                    for dev in _get_devices(node)
                                ],
                            }
                        ),
                        param_list=[
                            ("watchdog", ""),
                            ("device_list", json.dumps(_get_devices(node))),
                        ],
                    )
                    for node in self.new_nodes
                ],
            )
            .local.pcsd_ssl_cert_sync_enabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.setup_sbd(sbd_config, sbd_config_generator, self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .local.pcsd_ssl_cert_sync(self.new_nodes)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        corosync_node_fixture(node_id, node, _get_addrs(node))
                        for node_id, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                    [("auto_tie_breaker", "1")],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [
                dict(
                    name=node,
                    addrs=_get_addrs(node),
                    watchdog=_get_watchdog(node),
                    devices=_get_devices(node),
                )
                for node in self.new_nodes
            ],
            no_watchdog_validation=True,
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(reports.codes.SBD_CHECK_STARTED),
                fixture.warn(reports.codes.SBD_WATCHDOG_VALIDATION_INACTIVE),
            ]
            + [
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node=node)
                for node in self.new_nodes
            ]
        )

    def test_atb_needed(self):
        sbd_config = ""
        (
            self.config.corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .local.read_sbd_config()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.atb_needed(self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .local.check_sbd(self.new_nodes, with_devices=False)
            .local.pcsd_ssl_cert_sync_enabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.setup_sbd(
                sbd_config,
                lambda node: sbd_config_generator(node, with_devices=False),
                self.new_nodes,
            )
            .local.setup_booth(self.new_nodes)
            .local.files_sync(self.new_nodes)
            .local.pcsd_ssl_cert_sync(self.new_nodes)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        corosync_node_fixture(node_id, node, _get_addrs(node))
                        for node_id, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                    [("auto_tie_breaker", "1")],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [
                dict(
                    name=node,
                    addrs=_get_addrs(node),
                    watchdog=_get_watchdog(node),
                )
                for node in self.new_nodes
            ],
        )

        self.env_assist.assert_reports(self.expected_reports)


class FailureReloadCorosyncConf(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        patch_getaddrinfo(self, self.new_nodes)
        existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(
                node_labels=self.existing_nodes,
            )
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .http.corosync.set_corosync_conf(
                corosync_conf_fixture(
                    existing_corosync_nodes
                    + [
                        node_fixture(node, node_id)
                        for node_id, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ]
                ),
                node_labels=self.existing_nodes + self.new_nodes,
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
            + [fixture.info(reports.codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node=node
                )
                for node in self.existing_nodes + self.new_nodes
            ]
        )
        self.cmd_url = "remote/reload_corosync_conf"
        self.err_msg = "An error"

    def test_few_failed(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label="node1",
                        was_connected=False,
                        errno=7,
                        error_msg=self.err_msg,
                    )
                ],
                [
                    dict(
                        label="node2",
                        output=json.dumps(
                            dict(code="failed", message=self.err_msg)
                        ),
                    )
                ],
                [
                    dict(
                        label="node3",
                    )
                ],
            ]
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node1",
                    command=self.cmd_url,
                    reason=self.err_msg,
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node="node2",
                    reason=self.err_msg,
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node="node3",
                ),
            ]
        )

    def test_failed_and_corosync_not_running(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label="node1",
                        # corosync not running
                        output=json.dumps(dict(code="not_running", message="")),
                    )
                ],
                [
                    dict(
                        label="node2",
                        output=json.dumps(
                            dict(code="failed", message=self.err_msg)
                        ),
                    )
                ],
                [
                    dict(
                        label="node3",
                    )
                ],
            ]
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node="node1",
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node="node2",
                    reason=self.err_msg,
                ),
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_RELOADED,
                    node="node3",
                ),
            ]
        )

    def test_all_corosync_not_running(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label=node,
                        # corosync not running
                        output=json.dumps(dict(code="not_running", message="")),
                    )
                ]
                for node in self.existing_nodes
            ]
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
                    node=node,
                )
                for node in self.existing_nodes
            ]
        )

    def test_all_failed(self):
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label="node1",
                        was_connected=False,
                        errno=7,
                        error_msg=self.err_msg,
                    )
                ],
                [
                    dict(
                        label="node2",
                        output=json.dumps(
                            dict(code="failed", message=self.err_msg)
                        ),
                    )
                ],
                [
                    dict(
                        label="node3",
                        output="not a json",
                    )
                ],
                [
                    dict(
                        label="node4",
                        response_code=400,
                        output=self.err_msg,
                    )
                ],
            ]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node1",
                    command=self.cmd_url,
                    reason=self.err_msg,
                ),
                fixture.warn(
                    reports.codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node="node2",
                    reason=self.err_msg,
                ),
                fixture.warn(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node="node3",
                ),
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node4",
                    command=self.cmd_url,
                    reason=self.err_msg,
                ),
            ]
            + [
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
                )
            ]
        )


class FailureCorosyncConfDistribution(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        patch_getaddrinfo(self, self.new_nodes)
        existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(
                node_labels=self.existing_nodes,
            )
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
            + [fixture.info(reports.codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED)]
        )
        self.updated_corosync_conf_text = corosync_conf_fixture(
            existing_corosync_nodes
            + [
                node_fixture(node, node_id)
                for node_id, node in enumerate(
                    self.new_nodes, len(self.existing_nodes) + 1
                )
            ]
        )

    def test_failed_on_new(self):
        err_output = "an error"
        self.config.http.corosync.set_corosync_conf(
            self.updated_corosync_conf_text,
            communication_list=[{"label": node} for node in self.existing_nodes]
            + [
                {
                    "label": node,
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                }
                for node in self.new_nodes
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node=node
                )
                for node in self.existing_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/set_corosync_conf",
                    reason=err_output,
                )
                for node in self.new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=node,
                )
                for node in self.new_nodes
            ]
        )

    def test_failed_on_existing(self):
        err_output = "an error"
        self.config.http.corosync.set_corosync_conf(
            self.updated_corosync_conf_text,
            communication_list=[
                {"label": "node1"},
                {
                    "label": "node2",
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                },
                {"label": "node3"},
                {"label": "node4"},
            ]
            + [{"label": node} for node in self.new_nodes],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node=node
                )
                for node in ["node1", "node3", "node4"] + self.new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node2",
                    command="remote/set_corosync_conf",
                    reason=err_output,
                ),
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node="node2",
                ),
            ]
        )

    def test_failed_all(self):
        err_output = "an error"
        node_list = self.existing_nodes + self.new_nodes
        self.config.http.corosync.set_corosync_conf(
            self.updated_corosync_conf_text,
            communication_list=[
                {
                    "label": node,
                    "was_connected": False,
                    "errno": 1,
                    "error_msg": err_output,
                }
                for node in node_list
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            )
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/set_corosync_conf",
                    reason=err_output,
                )
                for node in node_list
            ]
            + [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=node,
                )
                for node in node_list
            ]
        )


class FailurePcsdSslCertSync(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        self.pcsd_ssl_cert = "pcsd ssl cert"
        self.pcsd_ssl_key = "pcsd ssl key"
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.error = "an error"
        patch_getaddrinfo(self, self.new_nodes)
        existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(
                node_labels=self.existing_nodes,
            )
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_enabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=self.new_nodes,
                )
            ]
        )

    def _add_nodes_with_lib_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node, "addrs": [node]} for node in self.new_nodes],
            )
        )

    def test_read_failure(self):
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

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCSD_SSL_CERT,
                    file_path=settings.pcsd_cert_location,
                    reason="error cert",
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCSD_SSL_KEY,
                    file_path=settings.pcsd_key_location,
                    reason="error key",
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_communication_failure(self):
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
                        "label": node,
                        "response_code": 400,
                        "output": self.error,
                    }
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS,
                    node=node,
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/set_certs",
                    reason=self.error,
                )
                for node in self.unsuccessful_nodes
            ]
        )


class FailureFilesDistribution(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        self.pcmk_authkey_content = b"pcmk authkey content"
        self.corosync_authkey_content = b"corosync authkey content"
        self.pcsd_dr_config_content = b"disaster recovery config data"
        self.pcmk_authkey_file_id = "pacemaker_remote authkey"
        self.corosync_authkey_file_id = "corosync authkey"
        self.pcsd_dr_config_file_id = "disaster-recovery config"
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        self.corosync_key_open_before_position = "fs.isfile.pacemaker_authkey"
        self.pacemaker_key_open_before_position = "fs.isfile.pcsd_dr_config"
        self.pcsd_dr_config_open_before_position = "fs.isfile.pcsd_settings"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(
                node_labels=self.existing_nodes,
            )
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .fs.isfile(
                settings.corosync_authkey_file,
                return_value=True,
                name="fs.isfile.corosync_authkey",
            )
            # open will be inserted here
            .fs.isfile(
                settings.pacemaker_authkey_file,
                return_value=True,
                name=self.corosync_key_open_before_position,
            )
            # open will be inserted here
            .fs.isfile(
                settings.pcsd_dr_config_location,
                return_value=True,
                name=self.pacemaker_key_open_before_position,
            )
            # open will be inserted here
            .fs.isfile(
                settings.pcsd_settings_conf_location,
                return_value=False,
                name=self.pcsd_dr_config_open_before_position,
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )
        self.distribution_started_reports = [
            fixture.info(
                reports.codes.FILES_DISTRIBUTION_STARTED,
                file_list=[
                    self.corosync_authkey_file_id,
                    "pacemaker authkey",
                    self.pcsd_dr_config_file_id,
                ],
                node_list=self.new_nodes,
            )
        ]
        self.successful_reports = (
            [
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=self.corosync_authkey_file_id,
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description="pacemaker authkey",
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.info(
                    reports.codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=self.pcsd_dr_config_file_id,
                )
                for node in self.successful_nodes
            ]
        )

    def _add_nodes_with_lib_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            )
        )

    def test_read_failure(self):
        self.config.fs.open(
            settings.corosync_authkey_file,
            mode="rb",
            side_effect=EnvironmentError(
                1, self.err_msg, settings.corosync_authkey_file
            ),
            name="fs.open.corosync_authkey",
            before=self.corosync_key_open_before_position,
        )
        self.config.fs.open(
            settings.pacemaker_authkey_file,
            mode="rb",
            side_effect=EnvironmentError(
                1, self.err_msg, settings.pacemaker_authkey_file
            ),
            name="fs.open.pacemaker_authkey",
            before=self.pacemaker_key_open_before_position,
        )
        self.config.fs.open(
            settings.pcsd_dr_config_location,
            mode="rb",
            side_effect=EnvironmentError(
                1, self.err_msg, settings.pcsd_dr_config_location
            ),
            name="fs.open.pcsd_dr_config",
            before=self.pcsd_dr_config_open_before_position,
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.COROSYNC_AUTHKEY,
                    file_path=settings.corosync_authkey_file,
                    reason=(
                        f"{self.err_msg}: '{settings.corosync_authkey_file}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.PACEMAKER_AUTHKEY,
                    file_path=settings.pacemaker_authkey_file,
                    reason=(
                        f"{self.err_msg}: '{settings.pacemaker_authkey_file}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    reason=(
                        f"{self.err_msg}: '{settings.pcsd_dr_config_location}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_read_failure_forced(self):
        (
            self.config.fs.open(
                settings.corosync_authkey_file,
                mode="rb",
                side_effect=EnvironmentError(
                    1, self.err_msg, settings.corosync_authkey_file
                ),
                name="fs.open.corosync_authkey",
                before=self.corosync_key_open_before_position,
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                mode="rb",
                side_effect=EnvironmentError(
                    1, self.err_msg, settings.pacemaker_authkey_file
                ),
                name="fs.open.pacemaker_authkey",
                before=self.pacemaker_key_open_before_position,
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                mode="rb",
                side_effect=EnvironmentError(
                    1, self.err_msg, settings.pcsd_dr_config_location
                ),
                name="fs.open.pcsd_dr_config",
                before=self.pcsd_dr_config_open_before_position,
            )
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_AUTHKEY,
                    file_path=settings.corosync_authkey_file,
                    reason=(
                        f"{self.err_msg}: '{settings.corosync_authkey_file}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PACEMAKER_AUTHKEY,
                    file_path=settings.pacemaker_authkey_file,
                    reason=(
                        f"{self.err_msg}: '{settings.pacemaker_authkey_file}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    reason=(
                        f"{self.err_msg}: '{settings.pcsd_dr_config_location}'"
                    ),
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_write_failure(self):
        (
            self.config.fs.open(
                settings.corosync_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.corosync_authkey_content
                )(),
                mode="rb",
                name="fs.open.corosync_authkey",
                before=self.corosync_key_open_before_position,
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.pcmk_authkey_content
                )(),
                mode="rb",
                name="fs.open.pacemaker_authkey",
                before=self.pacemaker_key_open_before_position,
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                return_value=mock.mock_open(
                    read_data=self.pcsd_dr_config_content
                )(),
                mode="rb",
                name="fs.open.pcsd_dr_config",
                before=self.pcsd_dr_config_open_before_position,
            )
            .http.files.put_files(
                pcmk_authkey=self.pcmk_authkey_content,
                corosync_authkey=self.corosync_authkey_content,
                pcs_disaster_recovery_conf=self.pcsd_dr_config_content,
                communication_list=[
                    dict(
                        label=node,
                        output=json.dumps(
                            dict(
                                files={
                                    self.corosync_authkey_file_id: dict(
                                        code="unexpected", message=self.err_msg
                                    ),
                                    self.pcmk_authkey_file_id: dict(
                                        code="unexpected", message=self.err_msg
                                    ),
                                    self.pcsd_dr_config_file_id: dict(
                                        code="unexpected", message=self.err_msg
                                    ),
                                }
                            )
                        ),
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.FILE_DISTRIBUTION_ERROR,
                    node=node,
                    file_description=self.corosync_authkey_file_id,
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.FILE_DISTRIBUTION_ERROR,
                    node=node,
                    file_description="pacemaker authkey",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.FILE_DISTRIBUTION_ERROR,
                    node=node,
                    file_description=self.pcsd_dr_config_file_id,
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_communication_failure(self):
        (
            self.config.fs.open(
                settings.corosync_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.corosync_authkey_content
                )(),
                mode="rb",
                name="fs.open.corosync_authkey",
                before=self.corosync_key_open_before_position,
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.pcmk_authkey_content
                )(),
                mode="rb",
                name="fs.open.pacemaker_authkey",
                before=self.pacemaker_key_open_before_position,
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                return_value=mock.mock_open(
                    read_data=self.pcsd_dr_config_content
                )(),
                mode="rb",
                name="fs.open.pcsd_dr_config",
                before=self.pcsd_dr_config_open_before_position,
            )
            .http.files.put_files(
                pcmk_authkey=self.pcmk_authkey_content,
                corosync_authkey=self.corosync_authkey_content,
                pcs_disaster_recovery_conf=self.pcsd_dr_config_content,
                communication_list=[
                    dict(
                        label=node,
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/put_file",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_invalid_response_format(self):
        (
            self.config.fs.open(
                settings.corosync_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.corosync_authkey_content
                )(),
                mode="rb",
                name="fs.open.corosync_authkey",
                before=self.corosync_key_open_before_position,
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.pcmk_authkey_content
                )(),
                mode="rb",
                name="fs.open.pacemaker_authkey",
                before=self.pacemaker_key_open_before_position,
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                return_value=mock.mock_open(
                    read_data=self.pcsd_dr_config_content
                )(),
                mode="rb",
                name="fs.open.pcsd_dr_config",
                before=self.pcsd_dr_config_open_before_position,
            )
            .http.files.put_files(
                pcmk_authkey=self.pcmk_authkey_content,
                corosync_authkey=self.corosync_authkey_content,
                pcs_disaster_recovery_conf=self.pcsd_dr_config_content,
                communication_list=[
                    dict(
                        label=node,
                        output="not json",
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=node,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_node_not_responding(self):
        (
            self.config.fs.open(
                settings.corosync_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.corosync_authkey_content
                )(),
                mode="rb",
                name="fs.open.corosync_authkey",
                before=self.corosync_key_open_before_position,
            )
            .fs.open(
                settings.pacemaker_authkey_file,
                return_value=mock.mock_open(
                    read_data=self.pcmk_authkey_content
                )(),
                mode="rb",
                name="fs.open.pacemaker_authkey",
                before=self.pacemaker_key_open_before_position,
            )
            .fs.open(
                settings.pcsd_dr_config_location,
                return_value=mock.mock_open(
                    read_data=self.pcsd_dr_config_content
                )(),
                mode="rb",
                name="fs.open.pcsd_dr_config",
                before=self.pcsd_dr_config_open_before_position,
            )
            .http.files.put_files(
                pcmk_authkey=self.pcmk_authkey_content,
                corosync_authkey=self.corosync_authkey_content,
                pcs_disaster_recovery_conf=self.pcsd_dr_config_content,
                communication_list=[
                    dict(
                        label=node,
                        errno=1,
                        error_msg=self.err_msg,
                        was_connected=False,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/put_file",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )


class FailureBoothConfigsDistribution(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        self.before_open_position = "fs.isfile.pcsd_settings"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]

        config_dir = settings.booth_config_dir
        self.config_file = "booth.conf"
        self.authfile = "booth.authfile"
        self.config_path = os.path.join(config_dir, self.config_file)
        self.authfile_path = os.path.join(config_dir, self.authfile)
        self.config_content = "authfile = {}\n".format(self.authfile_path)
        self.authfile_content = b"booth authfile"

        self.config_file2 = "booth2.conf"
        self.authfile2 = "booth2.authfile"
        self.config_path2 = os.path.join(config_dir, self.config_file2)
        self.authfile_path2 = os.path.join(config_dir, self.authfile2)
        self.config_content2 = "authfile = {}\n".format(self.authfile_path2)
        self.authfile_content2 = b"booth authfile 2"

        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(
                node_labels=self.existing_nodes,
            )
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir)
            .fs.listdir(
                settings.booth_config_dir,
                [self.config_file, "something", self.authfile],
            )
            .fs.isfile(self.config_path, name="fs.isfile.booth_config_file")
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )
        self.distribution_started_reports = [
            fixture.info(reports.codes.BOOTH_CONFIG_DISTRIBUTION_STARTED)
        ]
        self.successful_reports = [
            fixture.info(
                reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node=node,
                name_list=[self.authfile, self.config_file],
            )
            for node in self.successful_nodes
        ]

    def _set_up_multibooth(self):
        (
            self.config.fs.listdir(
                settings.booth_config_dir,
                [
                    self.config_file,
                    "something",
                    self.authfile,
                    self.authfile2,
                    self.config_file2,
                ],
                instead="fs.listdir",
            ).fs.isfile(self.config_path2, name="fs.isfile.booth_config_file2")
        )
        self.successful_reports = [
            fixture.info(
                reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                node=node,
                name_list=[self.authfile2, self.config_file2],
            )
            for node in self.new_nodes
        ]

    def _add_nodes_with_lib_error(self, report_list=None):
        if report_list is None:
            report_list = []
        self.env_assist.assert_raise_library_error(
            # pylint: disable=unnecessary-lambda
            lambda: self._add_nodes(),
            report_list,
            expected_in_processor=False,
        )

    def _add_nodes(self):
        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
        )

    def test_config_read_failure(self):
        self.config.raw_file.read(
            file_type_codes.BOOTH_CONFIG,
            self.config_path,
            exception_msg=self.err_msg,
            name="raw_file.read.booth_config_read",
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.config_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_config_read_failure_forced(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                exception_msg=self.err_msg,
                name="raw_file.read.booth_config_read",
            )
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.config_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_config_read_failure_forced_sends_other_configs(self):
        self._set_up_multibooth()
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                exception_msg=self.err_msg,
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path2,
                content=self.config_content2.encode("utf-8"),
                name="raw_file.read.booth_config_read2",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path2,
                content=self.authfile_content2,
                name="raw_file.read.booth_authfile_read2",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file2,
                        data=self.config_content2,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile2,
                        data=base64.b64encode(self.authfile_content2).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                rewrite_existing=True,
                saved=[self.config_file2, self.authfile2],
                node_labels=self.new_nodes,
            )
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_CONFIG,
                    file_path=self.config_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
            + self.distribution_started_reports
            + self.successful_reports
        )

    def test_authfile_read_failure(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            ).raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                exception_msg=self.err_msg,
                name="raw_file.read.booth_authfile_read",
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    force_code=reports.codes.FORCE,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.authfile_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_authfile_read_failure_forced(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                exception_msg=self.err_msg,
                name="raw_file.read.booth_authfile_read",
            )
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                    get_two_node(
                        len(self.existing_nodes) + len(self.new_nodes)
                    ),
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.authfile_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
        )

    def test_authfile_read_failure_forced_sends_other_configs(self):
        self._set_up_multibooth()
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                exception_msg=self.err_msg,
                name="raw_file.read.booth_authfile_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path2,
                content=self.config_content2.encode("utf-8"),
                name="raw_file.read.booth_config_read2",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path2,
                content=self.authfile_content2,
                name="raw_file.read.booth_authfile_read2",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file2,
                        data=self.config_content2,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile2,
                        data=base64.b64encode(self.authfile_content2).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                rewrite_existing=True,
                saved=[self.config_file2, self.authfile2],
                node_labels=self.new_nodes,
            )
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, len(self.existing_nodes) + 1
                        )
                    ],
                ),
                self.existing_nodes,
                self.new_nodes,
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node} for node in self.new_nodes],
            force_flags=[reports.codes.FORCE],
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.BOOTH_KEY,
                    file_path=self.authfile_path,
                    reason=self.err_msg,
                    operation=RawFileError.ACTION_READ,
                ),
            ]
            + self.distribution_started_reports
            + self.successful_reports
        )

    def test_write_failure(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                content=self.authfile_content,
                name="raw_file.read.booth_authfile_read",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file,
                        data=self.config_content,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile,
                        data=base64.b64encode(self.authfile_content).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                saved=[self.config_file, self.authfile],
                communication_list=[
                    dict(
                        label=node,
                        output=json.dumps(
                            dict(
                                saved=[self.authfile],
                                existing=[],
                                failed={
                                    self.config_file: self.err_msg,
                                },
                            )
                        ),
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.info(
                    reports.codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                    name_list=[self.authfile],
                )
                for node in self.unsuccessful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.BOOTH_CONFIG_DISTRIBUTION_NODE_ERROR,
                    node=node,
                    name=self.config_file,
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_communication_failure(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                content=self.authfile_content,
                name="raw_file.read.booth_authfile_read",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file,
                        data=self.config_content,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile,
                        data=base64.b64encode(self.authfile_content).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                saved=[self.config_file, self.authfile],
                communication_list=[
                    dict(
                        label=node,
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/booth_save_files",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_invalid_response_format(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                content=self.authfile_content,
                name="raw_file.read.booth_authfile_read",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file,
                        data=self.config_content,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile,
                        data=base64.b64encode(self.authfile_content).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                saved=[self.config_file, self.authfile],
                communication_list=[
                    dict(
                        label=node,
                        output="not json",
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=node,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_not_connected(self):
        (
            self.config.raw_file.read(
                file_type_codes.BOOTH_CONFIG,
                self.config_path,
                content=self.config_content.encode("utf-8"),
                name="raw_file.read.booth_config_read",
            )
            .raw_file.read(
                file_type_codes.BOOTH_KEY,
                self.authfile_path,
                content=self.authfile_content,
                name="raw_file.read.booth_authfile_read",
            )
            .http.booth.save_files(
                files_data=[
                    dict(
                        name=self.config_file,
                        data=self.config_content,
                        is_authfile=False,
                    ),
                    dict(
                        name=self.authfile,
                        data=base64.b64encode(self.authfile_content).decode(
                            "utf-8"
                        ),
                        is_authfile=True,
                    ),
                ],
                saved=[self.config_file, self.authfile],
                communication_list=[
                    dict(
                        label=node,
                        errno=1,
                        error_msg=self.err_msg,
                        was_connected=False,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + self.distribution_started_reports
            + self.successful_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/booth_save_files",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )


class FailureDisableSbd(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(4, 2)
        self.expected_reports = []
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        self.before_open_position = "fs.isfile.pcsd_settings"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]

        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_DISABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.successful_nodes
            ]
        )

    def _add_nodes_with_lib_error(self, report_list=None):
        if report_list is None:
            report_list = []
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            ),
            report_list,
            expected_in_processor=False,
        )

    def test_communication_failure(self):
        self.config.http.sbd.disable_sbd(
            communication_list=[
                dict(
                    label=node,
                    output=self.err_msg,
                    response_code=400,
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes]
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/sbd_disable",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_not_connected(self):
        self.config.http.sbd.disable_sbd(
            communication_list=[
                dict(
                    label=node,
                    errno=1,
                    error_msg=self.err_msg,
                    was_connected=False,
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes]
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/sbd_disable",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )


class FailureEnableSbd(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        # have 5 nodes in total so we do not need to enable atb
        self.existing_nodes, self.new_nodes = generate_nodes(3, 2)
        self.expected_reports = []
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.sbd_config = ""
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=True)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .local.read_sbd_config(self.sbd_config)
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .local.check_sbd(self.new_nodes, with_devices=False)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )

    def _add_nodes_with_lib_error(self, report_list=None):
        if report_list is None:
            report_list = []
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {"name": node, "watchdog": _get_watchdog(node)}
                    for node in self.new_nodes
                ],
            ),
            report_list,
            expected_in_processor=False,
        )

    def test_enable_communication_failure(self):
        (
            self.config.fs.open(
                settings.sbd_config,
                return_value=mock.mock_open(read_data=self.sbd_config)(),
                name="fs.open.sbd_config",
            )
            .http.sbd.set_sbd_config(
                config_generator=lambda node: sbd_config_generator(
                    node, with_devices=False
                ),
                node_labels=self.new_nodes,
            )
            .http.sbd.enable_sbd(
                communication_list=[
                    dict(
                        label=node,
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [dict(label=node) for node in self.successful_nodes]
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.info(reports.codes.SBD_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.SBD_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in self.new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_STARTED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service="sbd",
                    instance="",
                )
            ]
            + [
                fixture.info(
                    reports.codes.SERVICE_ACTION_SUCCEEDED,
                    action=reports.const.SERVICE_ACTION_ENABLE,
                    service="sbd",
                    node=node,
                    instance="",
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/sbd_enable",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_send_config_communication_failure(self):
        (
            self.config.fs.open(
                settings.sbd_config,
                return_value=mock.mock_open(read_data=self.sbd_config)(),
                name="fs.open.sbd_config",
            ).http.sbd.set_sbd_config(
                communication_list=[
                    dict(
                        label=node,
                        param_list=[
                            (
                                "config",
                                sbd_config_generator(node, with_devices=False),
                            )
                        ],
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [
                    dict(
                        label=node,
                        param_list=[
                            (
                                "config",
                                sbd_config_generator(node, with_devices=False),
                            )
                        ],
                    )
                    for node in self.successful_nodes
                ]
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [fixture.info(reports.codes.SBD_CONFIG_DISTRIBUTION_STARTED)]
            + [
                fixture.info(
                    reports.codes.SBD_CONFIG_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/set_sbd_config",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_read_config_failure(self):
        (
            self.config.fs.open(
                settings.sbd_config,
                side_effect=EnvironmentError(
                    1, self.err_msg, settings.sbd_config
                ),
                name="fs.open.sbd_config",
            )
        )

        self._add_nodes_with_lib_error(
            [
                fixture.error(
                    reports.codes.UNABLE_TO_GET_SBD_CONFIG,
                    node="local node",
                    reason=f"[Errno 1] {self.err_msg}: '{settings.sbd_config}'",
                )
            ]
        )

        self.env_assist.assert_reports(self.expected_reports)


class FailureQdevice(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(2, 2)
        self.expected_reports = []
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.sbd_config = ""
        self.config.env.set_known_nodes(
            self.existing_nodes + self.new_nodes + [QDEVICE_HOST]
        )
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes,
                    qdevice_net=True,
                )
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes + self.new_nodes,
            )
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )

    def _add_nodes_with_lib_error(self, report_list=None):
        if report_list is None:
            report_list = []
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            ),
            report_list,
            expected_in_processor=False,
        )

    @mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
    def test_import_pk12_failure(self, mock_get_tmp_file):
        cert = b"cert"
        tmp_file_path = "tmp_file_path"
        pk12_cert_path = "pk12_cert_path"
        pk12_cert = b"pk12_cert"
        (
            self.config.local.setup_qdevice_part1(
                mock_get_tmp_file, self.new_nodes
            )
            .http.corosync.qdevice_net_sign_certificate(
                CLUSTER_NAME,
                cert=cert,
                signed_cert=b"signed cert",
                node_labels=[QDEVICE_HOST],
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name="fs.exists.corosync_certs_db2",
            )
            .runner.corosync.qdevice_get_pk12(
                cert_path=tmp_file_path,
                output_path=pk12_cert_path,
            )
            .fs.open(
                pk12_cert_path,
                return_value=mock.mock_open(read_data=pk12_cert)(),
                mode="rb",
                name="fs.open.pk12_cert_read",
            )
            .http.corosync.qdevice_net_client_import_cert_and_key(
                cert=pk12_cert,
                communication_list=[
                    dict(
                        label=node,
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [
                    dict(
                        label=node,
                    )
                    for node in self.successful_nodes
                ],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
                    node=node,
                )
                for node in self.successful_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/qdevice_net_client_import_certificate",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    @mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
    def test_read_pk12_from_file_failure(self, mock_get_tmp_file):
        cert = b"cert"
        tmp_file_path = "tmp_file_path"
        pk12_cert_path = "pk12_cert_path"
        (
            self.config.local.setup_qdevice_part1(
                mock_get_tmp_file, self.new_nodes
            )
            .http.corosync.qdevice_net_sign_certificate(
                CLUSTER_NAME,
                cert=cert,
                signed_cert=b"signed cert",
                node_labels=[QDEVICE_HOST],
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name="fs.exists.corosync_certs_db2",
            )
            .runner.corosync.qdevice_get_pk12(
                cert_path=tmp_file_path,
                output_path=pk12_cert_path,
            )
            .fs.open(
                pk12_cert_path,
                side_effect=EnvironmentError(
                    1,
                    self.err_msg,
                    pk12_cert_path,
                ),
                mode="rb",
                name="fs.open.pk12_cert_read",
            )
        )

        self._add_nodes_with_lib_error(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    reason=f"{pk12_cert_path}: {self.err_msg}",
                ),
            ]
        )

        self.env_assist.assert_reports(self.expected_reports)

    @mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
    def test_transform_to_pk12_failure(self, mock_get_tmp_file):
        cert = b"cert"
        tmp_file_path = "tmp_file_path"
        (
            self.config.local.setup_qdevice_part1(
                mock_get_tmp_file, self.new_nodes
            )
            .http.corosync.qdevice_net_sign_certificate(
                CLUSTER_NAME,
                cert=cert,
                signed_cert=b"signed cert",
                node_labels=[QDEVICE_HOST],
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name="fs.exists.corosync_certs_db2",
            )
            .runner.corosync.qdevice_get_pk12(
                cert_path=tmp_file_path,
                output_path=None,
                stdout="",
                stderr=self.err_msg,
                returncode=1,
            )
        )

        self._add_nodes_with_lib_error(
            [
                fixture.error(
                    reports.codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
                    reason=self.err_msg,
                ),
            ]
        )

        self.env_assist.assert_reports(self.expected_reports)

    @mock.patch("pcs.lib.corosync.qdevice_net.get_tmp_file")
    def test_sign_certificate_failure(self, mock_get_tmp_file):
        cert = b"cert"
        (
            self.config.local.setup_qdevice_part1(
                mock_get_tmp_file, self.new_nodes
            ).http.corosync.qdevice_net_sign_certificate(
                CLUSTER_NAME,
                cert=cert,
                communication_list=[
                    {
                        "label": QDEVICE_HOST,
                        "output": "invalid base64 encoded certificate data",
                    },
                ],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=QDEVICE_HOST,
                )
            ]
        )

    def test_read_certificate_request_failure(self):
        ca_cert = b"ca_cert"
        cert_req_path = "cert_req_path"
        (
            self.config.http.corosync.qdevice_net_get_ca_cert(
                ca_cert=ca_cert,
                node_labels=[QDEVICE_HOST],
            )
            .http.corosync.qdevice_net_client_setup(
                ca_cert=ca_cert,
                node_labels=self.new_nodes,
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name="fs.exists.corosync_certs_db",
            )
            .runner.corosync.qdevice_generate_cert(
                CLUSTER_NAME,
                cert_req_path=cert_req_path,
            )
            .fs.open(
                cert_req_path,
                side_effect=EnvironmentError(1, self.err_msg, cert_req_path),
                mode="rb",
                name="fs.open.cert_req_read",
            )
        )

        self._add_nodes_with_lib_error(
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    model="net",
                    reason=f"{cert_req_path}: {self.err_msg}",
                ),
            ]
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
                )
            ]
        )

    def test_generate_certificate_request_failure(self):
        ca_cert = b"ca_cert"
        (
            self.config.http.corosync.qdevice_net_get_ca_cert(
                ca_cert=ca_cert,
                node_labels=[QDEVICE_HOST],
            )
            .http.corosync.qdevice_net_client_setup(
                ca_cert=ca_cert,
                node_labels=self.new_nodes,
            )
            .fs.exists(
                os.path.join(
                    settings.corosync_qdevice_net_client_certs_dir, "cert9.db"
                ),
                return_value=True,
                name="fs.exists.corosync_certs_db",
            )
            .runner.corosync.qdevice_generate_cert(
                CLUSTER_NAME,
                cert_req_path=None,
                stdout="",
                stderr=self.err_msg,
                returncode=1,
            )
        )

        self._add_nodes_with_lib_error(
            [
                fixture.error(
                    reports.codes.QDEVICE_INITIALIZATION_ERROR,
                    model="net",
                    reason=self.err_msg,
                ),
            ]
        )

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
                )
            ]
        )

    def test_initialize_new_nodes_failure(self):
        ca_cert = b"ca_cert"
        (
            self.config.http.corosync.qdevice_net_get_ca_cert(
                ca_cert=ca_cert,
                node_labels=[QDEVICE_HOST],
            ).http.corosync.qdevice_net_client_setup(
                ca_cert=ca_cert,
                communication_list=[
                    dict(
                        label=node,
                        output=self.err_msg,
                        response_code=400,
                    )
                    for node in self.unsuccessful_nodes
                ]
                + [
                    dict(
                        label=node,
                    )
                    for node in self.successful_nodes
                ],
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
                )
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command=(
                        "remote/qdevice_net_client_init_certificate_storage"
                    ),
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_get_ca_cert_failure(self):
        (
            self.config.http.corosync.qdevice_net_get_ca_cert(
                communication_list=[
                    {
                        "label": QDEVICE_HOST,
                        "output": "invalid base64 encoded certificate data",
                    },
                ]
            )
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.info(
                    reports.codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED
                ),
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node=QDEVICE_HOST,
                ),
            ]
        )


class FailureKnownHostsUpdate(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.existing_nodes, self.new_nodes = generate_nodes(2, 2)
        self.expected_reports = []
        self.unsuccessful_nodes = self.new_nodes[:1]
        self.successful_nodes = self.new_nodes[1:]
        self.err_msg = "an error message"
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, node_id)
            for node_id, node in enumerate(self.existing_nodes, 1)
        ]
        self.config.env.set_known_nodes(self.existing_nodes + self.new_nodes)
        self.config.local.set_expected_reports_list(self.expected_reports)
        (
            self.config.services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=self.existing_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )
        self.expected_reports.extend(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in self.new_nodes
            ]
        )

    def _add_nodes_with_lib_error(self, report_list=None):
        if report_list is None:
            report_list = []
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node} for node in self.new_nodes],
            ),
            report_list,
            expected_in_processor=False,
        )

    def test_communication_failure(self):
        self.config.http.host.update_known_hosts(
            to_add_hosts=self.existing_nodes + self.new_nodes,
            communication_list=[
                dict(
                    label=node,
                    output=self.err_msg,
                    response_code=400,
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=node,
                    command="remote/known_hosts_change",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )

    def test_not_connected(self):
        self.config.http.host.update_known_hosts(
            to_add_hosts=self.existing_nodes + self.new_nodes,
            communication_list=[
                dict(
                    label=node,
                    errno=1,
                    error_msg=self.err_msg,
                    was_connected=False,
                )
                for node in self.unsuccessful_nodes
            ]
            + [dict(label=node) for node in self.successful_nodes],
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=node,
                    command="remote/known_hosts_change",
                    reason=self.err_msg,
                )
                for node in self.unsuccessful_nodes
            ]
        )
