import json
from typing import Optional
from unittest import TestCase, mock

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.cfgsync_dto import SyncConfigsDto
from pcs.common.communication.const import COM_STATUS_ERROR, COM_STATUS_SUCCESS
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.communication.types import CommunicationResultStatus
from pcs.common.host import Destination, PcsKnownHost
from pcs.common.interface.dto import to_dict
from pcs.common.reports.processor import ReportProcessorToLog
from pcs.daemon.cfgsync import CfgSyncPullManager
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncFacade
from pcs.lib.corosync.config_parser import Exporter as CorosyncExporter
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.types import KnownHosts
from pcs.lib.permissions.config.exporter import (
    ExporterV2 as PcsSettingsExporter,
)
from pcs.lib.permissions.config.types import (
    ClusterPermissions,
)
from pcs.lib.permissions.config.types import (
    ConfigV2 as PcsSettingsConf,
)

from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.misc import read_test_resource


def fixture_communication_result_string(
    status: CommunicationResultStatus = COM_STATUS_SUCCESS,
    status_msg: Optional[str] = None,
    report_list: Optional[reports.dto.ReportItemDto] = None,
    data="",
) -> str:
    return json.dumps(
        to_dict(
            InternalCommunicationResultDto(
                status=status,
                status_msg=status_msg,
                report_list=report_list or [],
                data=data,
            )
        )
    )


def fixture_known_hosts_content(data_version=1, known_hosts=None):
    return KnownHostsExporter.export(
        KnownHosts(
            format_version=1,
            data_version=data_version,
            known_hosts=known_hosts or {},
        )
    ).decode("utf-8")


def fixture_pcs_settings_content(data_version=1):
    return PcsSettingsExporter.export(
        PcsSettingsConf(
            data_version=data_version,
            clusters=[],
            permissions=ClusterPermissions([]),
        )
    ).decode("utf-8")


def fixture_corosync_with_no_nodes():
    return CorosyncExporter.export(
        CorosyncFacade.create("test", [], "udp").config
    )


def fixture_corosync_3_nodes():
    return read_test_resource("corosync-3nodes.conf").encode("utf-8")


def fixture_known_hosts_3_nodes():
    return fixture_known_hosts_content(
        known_hosts={
            "rh7-1": PcsKnownHost(
                "rh7-1", "TOKEN", [Destination("rh7-1", 2224)]
            ),
            "rh7-2": PcsKnownHost(
                "rh7-2", "TOKEN", [Destination("rh7-2", 2224)]
            ),
            "rh7-3": PcsKnownHost(
                "rh7-3", "TOKEN", [Destination("rh7-3", 2224)]
            ),
        }
    )


class RunCfgSync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.logger = None

    def run_cfgsync(self):
        env = self.env_assist.get_env()
        self.logger = env.logger
        report_processor = ReportProcessorToLog(self.logger)
        puller = CfgSyncPullManager(
            report_processor, env.get_node_communicator(), self.logger
        )
        return puller.run_cfgsync()

    def assert_logger_calls(self, expected_calls):
        self.assertIsNotNone(
            self.logger,
            "You need to call `self.run_cfgsync()` before calling this assert",
        )
        self.logger.assert_has_calls(expected_calls, any_order=False)
        real_calls = self.logger.mock_calls
        self.assertEqual(
            len(real_calls),
            len(expected_calls),
            msg=(
                f"\nreal calls: {real_calls}\nexpected calls: {expected_calls}"
            ),
        )

    def fixture_before_fetch_config_files_all_successful(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.read(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            content=fixture_corosync_3_nodes(),
            name="corosync_conf.read",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_3_nodes(),
            name="known_hosts.read",
        )

    def test_no_corosync_conf(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync_conf.exists",
        )

        result = self.run_cfgsync()

        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Config files sync skipped, this host does not seem to be in a cluster of at least 2 nodes"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_no_corosync_no_cfgsync_ctl(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            exists=False,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync_conf.exists",
        )

        result = self.run_cfgsync()

        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.debug(
                    "File '%s' does not exist, using default settings for config files sync",
                    settings.cfgsync_ctl_location,
                ),
                mock.call.info(
                    "Config files sync skipped, this host does not seem to be in a cluster of at least 2 nodes"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_no_corosync_error_reading_cfgsync_ctl(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            exception_msg="Some error",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync_conf.exists",
        )

        result = self.run_cfgsync()

        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.error(
                    f"Unable to read Config synchronization configuration '{settings.cfgsync_ctl_location}': Some error"
                ),
                mock.call.info(
                    "Unable to read '%s', using default settings for config files sync",
                    settings.cfgsync_ctl_location,
                ),
                mock.call.info(
                    "Config files sync skipped, this host does not seem to be in a cluster of at least 2 nodes"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_no_2_nodes_in_corosync_conf(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.read(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            content=fixture_corosync_with_no_nodes(),
            name="corosync_conf.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Config files sync skipped, this host does not seem to be in a cluster of at least 2 nodes"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_error_reading_corosync_conf(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.read(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exception_msg="Some error",
            name="corosync_conf.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.error(
                    f"Unable to read Corosync configuration '{settings.corosync_conf_file}': Some error"
                ),
                mock.call.info(
                    "Config files sync skipped, this host does not seem to be in a cluster of at least 2 nodes"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_no_known_hosts(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.read(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            content=fixture_corosync_3_nodes(),
            name="corosync_conf.read",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exception_msg="No file",
            name="known_hosts.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.error(
                    f"Unable to read known-hosts '{settings.pcsd_known_hosts_location}': No file"
                ),
                mock.call.error(
                    "Hosts 'rh7-1', 'rh7-2', 'rh7-3' are not known to pcs"
                ),
                mock.call.error("None of hosts is known to pcs."),
                mock.call.info(
                    "Config files sync skipped, unable to find at least 2 request targets"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_hosts_from_corosync_not_in_known_hosts(self):
        self.config.raw_file.exists(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.CFGSYNC_CTL,
            settings.cfgsync_ctl_location,
            content="{}",
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.read(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            content=fixture_corosync_3_nodes(),
            name="corosync_conf.read",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_content(
                known_hosts={
                    "rh7-1": PcsKnownHost(
                        "rh7-1", "foobar", [Destination("10.0.1.2", 22234)]
                    )
                }
            ),
            name="known_hosts.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.error("Hosts 'rh7-2', 'rh7-3' are not known to pcs"),
                mock.call.info(
                    "Config files sync skipped, unable to find at least 2 request targets"
                ),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_fetch_known_hosts_not_newer_than_local(self):
        self.fixture_before_fetch_config_files_all_successful()
        known_hosts_file_content = fixture_known_hosts_content()
        self.config.http.place_multinode_call(
            "fetch.get_configs",
            communication_list=[
                {
                    "label": "rh7-1",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_file_content
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-2",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_file_content
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-3",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_file_content
                            },
                        )
                    ),
                },
            ],
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": "test99"}),
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.fetch.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=known_hosts_file_content,
            name="known_hosts.fetch.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Fetching config files from nodes: %s",
                    "'rh7-1', 'rh7-2', 'rh7-3'",
                ),
                mock.call.info("Config files sync finished"),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_fetch_known_hosts_newer_than_local(self):
        self.fixture_before_fetch_config_files_all_successful()
        known_hosts_older = fixture_known_hosts_content()
        known_hosts_new = fixture_known_hosts_content(data_version=99)

        self.config.http.place_multinode_call(
            "fetch.get_configs",
            communication_list=[
                {
                    "label": "rh7-1",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_new
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-2",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_older
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-3",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_older
                            },
                        )
                    ),
                },
            ],
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": "test99"}),
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.fetch.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=known_hosts_older,
            name="known_hosts.fetch.read",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=known_hosts_new.encode("utf-8"),
            can_overwrite=True,
            name="known_hosts.fetch.write",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Fetching config files from nodes: %s",
                    "'rh7-1', 'rh7-2', 'rh7-3'",
                ),
                mock.call.info(
                    "Saving config '%s' version %d to '%s'",
                    "known-hosts",
                    99,
                    settings.pcsd_known_hosts_location,
                ),
                mock.call.info("Config files sync finished"),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)

    def test_fetch_hosts_communication_failure(self):
        self.fixture_before_fetch_config_files_all_successful()
        self.config.http.place_multinode_call(
            "fetch.get_configs",
            communication_list=[
                {
                    "label": "rh7-1",
                    "output": fixture_communication_result_string(
                        status=COM_STATUS_ERROR, status_msg="Some error 1"
                    ),
                },
                {
                    "label": "rh7-2",
                    "output": fixture_communication_result_string(
                        status=COM_STATUS_ERROR, status_msg="Some error 2"
                    ),
                },
                {
                    "label": "rh7-3",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: fixture_known_hosts_content()
                            },
                        )
                    ),
                },
            ],
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": "test99"}),
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="known_hosts.fetch.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_content(),
            name="known_hosts.fetch.read",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Fetching config files from nodes: %s",
                    "'rh7-1', 'rh7-2', 'rh7-3'",
                ),
                mock.call.error("rh7-1: Some error 1"),
                mock.call.error("rh7-2: Some error 2"),
                mock.call.info("Config files sync finished"),
            ]
        )
        self.assertEqual(
            result,
            settings.cfgsync_thread_interval_previous_not_connected_default,
        )

    def test_multiple_files(self):
        self.fixture_before_fetch_config_files_all_successful()
        known_hosts_old = fixture_known_hosts_content()
        known_hosts_new = fixture_known_hosts_content(data_version=99)
        pcs_settings_old = fixture_pcs_settings_content()
        pcs_settings_new = fixture_pcs_settings_content(data_version=99)

        self.config.http.place_multinode_call(
            "fetch.get_configs",
            communication_list=[
                {
                    "label": "rh7-1",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_new,
                                file_type_codes.PCS_SETTINGS_CONF: pcs_settings_new,
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-2",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_old,
                                file_type_codes.PCS_SETTINGS_CONF: pcs_settings_old,
                            },
                        )
                    ),
                },
                {
                    "label": "rh7-3",
                    "output": fixture_communication_result_string(
                        data=SyncConfigsDto(
                            cluster_name="test99",
                            configs={
                                file_type_codes.PCS_KNOWN_HOSTS: known_hosts_old,
                                file_type_codes.PCS_SETTINGS_CONF: pcs_settings_old,
                            },
                        )
                    ),
                },
            ],
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": "test99"}),
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=fixture_known_hosts_content(),
            name="raw_file.read.known_hosts",
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            name="raw_file.exists.pcs_settings",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_content(),
            name="raw_file.read.pcs_settings",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=known_hosts_new.encode("utf-8"),
            can_overwrite=True,
            name="known_hosts.fetch.write",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            file_data=pcs_settings_new.encode("utf-8"),
            can_overwrite=True,
            name="pcs_settings.fetch.write",
        )

        result = self.run_cfgsync()
        self.assert_logger_calls(
            [
                mock.call.info("Config files sync started"),
                mock.call.info(
                    "Fetching config files from nodes: %s",
                    "'rh7-1', 'rh7-2', 'rh7-3'",
                ),
                mock.call.info(
                    "Saving config '%s' version %d to '%s'",
                    "known-hosts",
                    99,
                    settings.pcsd_known_hosts_location,
                ),
                mock.call.info(
                    "Saving config '%s' version %d to '%s'",
                    "pcs configuration",
                    99,
                    settings.pcsd_settings_conf_location,
                ),
                mock.call.info("Config files sync finished"),
            ]
        )
        self.assertEqual(result, settings.cfgsync_thread_interval_default)
