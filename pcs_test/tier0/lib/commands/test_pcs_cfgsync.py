import json
from unittest import TestCase, mock

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.lib.commands import pcs_cfgsync as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import (
    fixture_expected_save_sync_reports,
    fixture_pcs_settings_file_content,
    fixture_save_sync_new_version_conflict,
    fixture_save_sync_new_version_error,
    fixture_save_sync_new_version_success,
)


class GetConfigs(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def fixture_files_operations(
        self, known_hosts_exists: bool = True, pcs_settings_exists: bool = True
    ) -> None:
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            path=settings.pcsd_known_hosts_location,
            exists=known_hosts_exists,
            name="known-hosts.exists",
        )
        if known_hosts_exists:
            self.config.raw_file.read(
                file_type_codes.PCS_KNOWN_HOSTS,
                path=settings.pcsd_known_hosts_location,
                content="known-hosts content".encode("utf-8"),
                name="known-hosts.read",
            )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            path=settings.pcsd_settings_conf_location,
            exists=pcs_settings_exists,
            name="pcs_settings.exists",
        )
        if pcs_settings_exists:
            self.config.raw_file.read(
                file_type_codes.PCS_SETTINGS_CONF,
                path=settings.pcsd_settings_conf_location,
                content="pcs_settings.conf content".encode("utf-8"),
                name="pcs_settings.read",
            )

    def test_bad_cluster_name(self):
        self.config.corosync_conf.load()
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_configs(
                self.env_assist.get_env(), "definitely not the right name"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME,
                    cluster_name="definitely not the right name",
                ),
            ]
        )

    def test_not_in_cluster(self):
        # cant read corosync conf
        self.config.corosync_conf.load_content("", exception_msg="some error")
        self.env_assist.assert_raise_library_error(
            lambda: lib.get_configs(self.env_assist.get_env(), "test99"),
            reports=[
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation="read",
                    reason="some error",
                    file_path=settings.corosync_conf_file,
                )
            ],
            expected_in_processor=False,
        )

    def test_no_files_exist(self):
        self.config.corosync_conf.load()
        self.fixture_files_operations(
            known_hosts_exists=False, pcs_settings_exists=False
        )
        result = lib.get_configs(self.env_assist.get_env(), "test99")
        self.assertEqual(
            SyncConfigsDto(cluster_name="test99", configs={}), result
        )

    def test_some_files_exist(self):
        self.config.corosync_conf.load()
        self.fixture_files_operations(
            known_hosts_exists=True, pcs_settings_exists=False
        )
        result = lib.get_configs(self.env_assist.get_env(), "test99")
        self.assertEqual(
            SyncConfigsDto(
                cluster_name="test99",
                configs={
                    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts content"
                },
            ),
            result,
        )

    def test_all_files_exist(self):
        self.config.corosync_conf.load()
        self.fixture_files_operations()
        result = lib.get_configs(self.env_assist.get_env(), "test99")
        self.assertEqual(
            SyncConfigsDto(
                cluster_name="test99",
                configs={
                    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts content",
                    file_type_codes.PCS_SETTINGS_CONF: "pcs_settings.conf content",
                },
            ),
            result,
        )

    def test_raw_file_error(self):
        self.config.corosync_conf.load()
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            path=settings.pcsd_known_hosts_location,
            name="known-hosts.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            path=settings.pcsd_known_hosts_location,
            exception_msg="some error",
            name="known-hosts.read",
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            path=settings.pcsd_settings_conf_location,
            name="pcs_settings.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            path=settings.pcsd_settings_conf_location,
            content="pcs_settings.conf content".encode("utf-8"),
            name="pcs_settings.read",
        )

        result = lib.get_configs(self.env_assist.get_env(), "test99")

        self.assertEqual(
            SyncConfigsDto(
                cluster_name="test99",
                configs={
                    file_type_codes.PCS_SETTINGS_CONF: "pcs_settings.conf content"
                },
            ),
            result,
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="some error",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )


class UpdateSyncOptions(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def fixture_expected_json(self, values) -> bytes:
        return json.dumps(values, indent=4, sort_keys=True).encode()

    def test_validation_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.update_sync_options(
                self.env_assist.get_env(),
                {"sync_thread_pause": "1", "sync_thread_resume": True},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                    option_names=["sync_thread_pause", "sync_thread_resume"],
                    option_type=None,
                )
            ]
        )

    def test_error_reading_config_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL, settings.pcs_cfgsync_ctl_location
        )
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.update_sync_options(
                self.env_assist.get_env(), {"sync_thread_enable": ""}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_CFGSYNC_CTL,
                    operation="read",
                    reason="Something bad",
                    file_path=settings.pcs_cfgsync_ctl_location,
                )
            ]
        )

    def test_error_invalid_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL, settings.pcs_cfgsync_ctl_location
        )
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            "{",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.update_sync_options(
                self.env_assist.get_env(), {"sync_thread_enable": ""}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_JSON_FILE,
                    file_type_code=file_type_codes.PCS_CFGSYNC_CTL,
                    line_number=1,
                    column_number=2,
                    position=1,
                    reason="Expecting property name enclosed in double quotes",
                    full_msg=(
                        "Expecting property name enclosed in double quotes: "
                        "line 1 column 2 (char 1)"
                    ),
                    file_path=settings.pcs_cfgsync_ctl_location,
                )
            ]
        )

    def test_success(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL, settings.pcs_cfgsync_ctl_location
        )
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            json.dumps({"file_backup_count": 123, "thread_interval": 500}),
        )
        self.config.raw_file.write(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            self.fixture_expected_json(
                {
                    "file_backup_count": 123,
                    "thread_interval": 500,
                    "thread_disabled": False,
                }
            ),
            can_overwrite=True,
        )
        lib.update_sync_options(
            self.env_assist.get_env(), {"sync_thread_enable": ""}
        )

    def _test_update_valid_options(self, options, expected_output):
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            self.fixture_expected_json(expected_output),
            can_overwrite=True,
        )

        lib.update_sync_options(self.env_assist.get_env(), options)

    def test_success_enable(self):
        self._test_update_valid_options(
            {"sync_thread_enable": ""}, {"thread_disabled": False}
        )

    def test_success_disable(self):
        self._test_update_valid_options(
            {"sync_thread_disable": ""}, {"thread_disabled": True}
        )

    def test_success_resume(self):
        self._test_update_valid_options({"sync_thread_resume": ""}, {})

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_success_pause_provided_value(self):
        self._test_update_valid_options(
            {"sync_thread_pause": "1000"}, {"thread_paused_until": 2000}
        )

    @mock.patch("pcs.lib.pcs_cfgsync.config.facade.time.time", lambda: 1000)
    def test_success_combination(self):
        self._test_update_valid_options(
            {"sync_thread_pause": "1000", "sync_thread_disable": ""},
            {"thread_paused_until": 2000, "thread_disabled": True},
        )

    def test_error_writing_config_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            self.fixture_expected_json({"thread_disabled": False}),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.update_sync_options(
                self.env_assist.get_env(), {"sync_thread_enable": ""}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_CFGSYNC_CTL,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcs_cfgsync_ctl_location,
                )
            ]
        )


class SaveSyncPcsSettingsInternalNotInCluster(TestCase):
    FILE_DATA_VERSION = 123

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_invalid_config_text(self):
        self.env_assist.assert_raise_library_error(
            lambda: lib.save_sync_pcs_settings_internal(
                self.env_assist.get_env(), "{}"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    reason="'format_version' not defined",
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )

    def test_success(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                self.FILE_DATA_VERSION + 1
            ).encode(),
            can_overwrite=True,
        )

        lib.save_sync_pcs_settings_internal(
            self.env_assist.get_env(),
            fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
        )

    def test_error_writing_pcs_settings_conf(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                self.FILE_DATA_VERSION + 1
            ).encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.save_sync_pcs_settings_internal(
                self.env_assist.get_env(),
                fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )


class SaveSyncPcsSettingsInternalInCluster(TestCase):
    FILE_DATA_VERSION = 123
    NODE_LABELS = ["node1", "node2", "node3"]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(self.NODE_LABELS)
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
        )
        self.config.corosync_conf.load(self.NODE_LABELS)

    def test_success(self):
        fixture_save_sync_new_version_success(
            self.config,
            node_labels=self.NODE_LABELS,
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    self.FILE_DATA_VERSION + 1
                )
            },
        )

        lib.save_sync_pcs_settings_internal(
            self.env_assist.get_env(),
            fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type_codes.PCS_SETTINGS_CONF, self.NODE_LABELS
            )
        )

    def test_no_tokens_for_some_nodes(self):
        self.config.env.set_known_nodes(self.NODE_LABELS[:1])
        fixture_save_sync_new_version_success(
            self.config,
            node_labels=self.NODE_LABELS[:1],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    self.FILE_DATA_VERSION + 1
                )
            },
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.save_sync_pcs_settings_internal(
                self.env_assist.get_env(),
                fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node2", "node3"]
                )
            ]
            + fixture_expected_save_sync_reports(
                file_type_codes.PCS_SETTINGS_CONF, self.NODE_LABELS[:1]
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node2", "node3"],
                ),
            ]
        )

    def test_sync_conflict(self):
        cluster_newest_file = fixture_pcs_settings_file_content(1000000)
        fixture_save_sync_new_version_conflict(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                self.FILE_DATA_VERSION + 1
            ),
            fetch_after_conflict=True,
            remote_file_content=cluster_newest_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            cluster_newest_file.encode(),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.save_sync_pcs_settings_internal(
                self.env_assist.get_env(),
                fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type_codes.PCS_SETTINGS_CONF,
                self.NODE_LABELS,
                expected_result="conflict",
            )
        )

    def test_sync_error(self):
        fixture_save_sync_new_version_error(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                self.FILE_DATA_VERSION + 1
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: lib.save_sync_pcs_settings_internal(
                self.env_assist.get_env(),
                fixture_pcs_settings_file_content(self.FILE_DATA_VERSION),
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type_codes.PCS_SETTINGS_CONF,
                self.NODE_LABELS,
                expected_result="error",
            )
        )
