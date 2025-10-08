from unittest import TestCase, mock

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.file import RawFileError
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import RequestTarget
from pcs.lib.communication.pcs_cfgsync import ConfigInfo, GetConfigsResult
from pcs.lib.file import metadata
from pcs.lib.file.instance import FileInstance
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.host.config.parser import InvalidFileStructureException
from pcs.lib.host.config.types import KnownHosts
from pcs.lib.pcs_cfgsync.fetcher import ConfigFetcher, _find_newest_config
from pcs.lib.permissions.config.exporter import ExporterV2
from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.parser import ParserError
from pcs.lib.permissions.config.types import ClusterPermissions, ConfigV2

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


def fixture_known_hosts(data_version=1, known_hosts=None):
    return KnownHosts(
        format_version=1,
        data_version=data_version,
        known_hosts=known_hosts or {},
    )


def fixture_known_hosts_facade(data_version=1, known_hosts=None):
    return KnownHostsFacade(fixture_known_hosts(data_version, known_hosts))


class FindNewestConfig(TestCase):
    def setUp(self):
        self.instance = FileInstance.for_known_hosts()

    def assert_equal_content(self, real, expected):
        self.assertEqual(real.config, expected.config)

    def test_empty(self):
        result = _find_newest_config(self.instance, [])
        self.assertIsNone(result)

    def test_all_the_same(self):
        config_1 = fixture_known_hosts_facade()
        config_2 = fixture_known_hosts_facade()
        result = _find_newest_config(self.instance, [config_1, config_2])

        self.assert_equal_content(result, config_1)

    def test_one_new(self):
        config_older = fixture_known_hosts_facade()
        config_newest = fixture_known_hosts_facade(data_version=99)
        result = _find_newest_config(
            self.instance,
            [config_older, config_newest],
        )

        self.assert_equal_content(result, config_newest)

    def test_same_version_choose_most_common(self):
        config_1_1 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"A": PcsKnownHost("A", "B", [])}
        )
        config_1_2 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"A": PcsKnownHost("A", "B", [])}
        )
        config_2 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"X": PcsKnownHost("X", "Y", [])}
        )
        result = _find_newest_config(
            self.instance, [config_1_1, config_1_2, config_2]
        )

        self.assert_equal_content(result, config_1_1)

    def test_same_version_same_amount_of_the_same_file(self):
        config_1_1 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"A": PcsKnownHost("A", "B", [])}
        )
        config_1_2 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"A": PcsKnownHost("A", "B", [])}
        )
        config_2_1 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"C": PcsKnownHost("C", "D", [])}
        )
        config_2_2 = fixture_known_hosts_facade(
            data_version=99, known_hosts={"C": PcsKnownHost("C", "D", [])}
        )

        # the function should always return the config with the same content,
        # without being dependent on how the input list was sorted
        configs = [
            [config_1_1, config_1_2, config_2_1, config_2_2],
            [config_1_1, config_2_1, config_1_2, config_2_2],
            [config_2_1, config_2_2, config_1_1, config_1_2],
            [config_2_1, config_1_1, config_2_2, config_1_2],
        ]
        for cfg_list in configs:
            with self.subTest(value=cfg_list):
                result = _find_newest_config(
                    self.instance,
                    [config_1_1, config_1_2, config_2_1, config_2_2],
                )
                self.assert_equal_content(result, config_2_1)


def fixture_known_hosts_file_content(data_version=1, known_hosts=None):
    return KnownHostsExporter.export(
        fixture_known_hosts(data_version, known_hosts)
    ).decode("utf-8")


def fixture_pcs_settings_file_content(data_version=1):
    return ExporterV2.export(
        ConfigV2(
            data_version=data_version,
            clusters=[],
            permissions=ClusterPermissions([]),
        )
    ).decode("utf-8")


@mock.patch("pcs.lib.pcs_cfgsync.fetcher.run")
@mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.raw_file")
class ConfigFetcherTest(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor()
        self.fetcher = ConfigFetcher(None, self.report_processor)

    def test_no_request_targets(
        self, mock_raw_file: mock.Mock, mock_run: mock.Mock
    ):
        mock_run.return_value = GetConfigsResult(False, {})

        configs, was_successful = self.fetcher.fetch("test", [])

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_not_called()
        self.assertEqual(configs, {})
        self.assertFalse(was_successful)

    def test_local_does_not_exist(
        self, mock_raw_file: mock.Mock, mock_run: mock.Mock
    ):
        file_content = fixture_known_hosts_file_content()
        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", file_content)
                ]
            },
        )
        mock_raw_file.exists.return_value = False

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once()
        self.assertEqual(len(configs.keys()), 1)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            file_content,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_not_newer_than_local(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        file_content = fixture_known_hosts_file_content()

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", file_content)
                ]
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.return_value = KnownHostsFacade(
            fixture_known_hosts()
        )

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once()
        mock_read_to_facade.assert_called_once()
        self.assertEqual(configs, {})
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_newer_than_local(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        file_content = fixture_known_hosts_file_content(data_version=99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", file_content)
                ]
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.return_value = KnownHostsFacade(
            fixture_known_hosts()
        )

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once()
        mock_read_to_facade.assert_called_once()
        self.assertEqual(len(configs.keys()), 1)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            file_content,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_multiple_nodes_chooses_newest(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        file_content_older = fixture_known_hosts_file_content()
        file_content_newer = fixture_known_hosts_file_content(data_version=99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE-1", file_content_older),
                    ConfigInfo("NODE-2", file_content_newer),
                ]
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.return_value = fixture_known_hosts_facade()

        configs, was_successful = self.fetcher.fetch(
            "test",
            [RequestTarget("NODE-1"), RequestTarget("NODE-2")],
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once()
        mock_read_to_facade.assert_called_once()
        self.assertEqual(len(configs), 1)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            file_content_newer,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_multiple_files(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        known_hosts = fixture_known_hosts_file_content(99)
        pcs_settings = fixture_pcs_settings_file_content(99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", known_hosts)
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE", pcs_settings)
                ],
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.side_effect = [
            fixture_known_hosts_facade(),
            FacadeV2(
                ConfigV2(
                    data_version=1,
                    clusters=[],
                    permissions=ClusterPermissions([]),
                )
            ),
        ]

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        # called twice
        mock_raw_file.exists.assert_has_calls(
            [mock.call.exists(), mock.call.exists()]
        )
        self.assertEqual(len(mock_raw_file.exists.mock_calls), 2)
        mock_read_to_facade.assert_has_calls([mock.call(), mock.call()])
        self.assertEqual(len(mock_read_to_facade.mock_calls), 2)
        self.assertEqual(len(configs), 2)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            known_hosts,
        )
        self.assertEqual(
            ExporterV2.export(
                configs[file_type_codes.PCS_SETTINGS_CONF].config
            ).decode("utf-8"),
            pcs_settings,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_unsupported_filetype(
        self, mock_raw_file: mock.Mock, mock_run: mock.Mock
    ):
        mock_run.return_value = GetConfigsResult(
            True,
            {file_type_codes.PCSD_SSL_CERT: [ConfigInfo("NODE", "")]},
        )
        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_not_called()
        self.assertEqual(len(configs.keys()), 0)
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )

    def test_invalid_remote_file_content(
        self, mock_raw_file: mock.Mock, mock_run: mock.Mock
    ):
        mock_run.return_value = GetConfigsResult(
            True,
            {file_type_codes.PCS_KNOWN_HOSTS: [ConfigInfo("NODE", "{}")]},
        )

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_not_called()
        self.assertEqual(configs, {})
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.warn(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    file_path=settings.pcsd_known_hosts_location,
                    reason='missing value for field "format_version"',
                    context=reports.dto.ReportItemContextDto(node="NODE"),
                )
            ],
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_local_raw_file_error(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        file_content = fixture_known_hosts_file_content(data_version=99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", file_content)
                ]
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.side_effect = RawFileError(
            metadata.for_file_type(file_type_codes.PCS_KNOWN_HOSTS, "AAA"),
            RawFileError.ACTION_READ,
            "foo",
        )

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once_with()
        mock_read_to_facade.assert_called_once_with()
        self.assertEqual(len(configs.keys()), 0)
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="foo",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ],
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_local_file_parse_error(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        file_content = fixture_known_hosts_file_content(data_version=99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", file_content)
                ]
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.side_effect = InvalidFileStructureException("AAA")

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once_with()
        mock_read_to_facade.assert_called_once_with()
        self.assertEqual(len(configs.keys()), 0)
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    reason="AAA",
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    file_path=settings.pcsd_known_hosts_location,
                )
            ],
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_multiple_files_skip_error_local(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        known_hosts = fixture_known_hosts_file_content(data_version=99)
        pcs_settings = fixture_pcs_settings_file_content(data_version=99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", known_hosts)
                ],
                file_type_codes.PCS_SETTINGS_CONF: [
                    ConfigInfo("NODE", pcs_settings)
                ],
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.side_effect = [
            fixture_known_hosts_facade(),
            ParserError("AAA"),
        ]

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")]
        )

        mock_run.assert_called_once()
        # called twice
        mock_raw_file.exists.assert_has_calls(
            [mock.call.exists(), mock.call.exists()]
        )
        self.assertEqual(len(mock_raw_file.exists.mock_calls), 2)
        mock_read_to_facade.assert_has_calls([mock.call(), mock.call()])
        self.assertEqual(len(mock_read_to_facade.mock_calls), 2)
        self.assertEqual(len(configs), 1)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            known_hosts,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list,
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    reason="AAA",
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    file_path=settings.pcsd_settings_conf_location,
                )
            ],
        )

    @mock.patch("pcs.lib.pcs_cfgsync.fetcher.FileInstance.read_to_facade")
    def test_fetch_filtered(
        self,
        mock_read_to_facade: mock.Mock,
        mock_raw_file: mock.Mock,
        mock_run: mock.Mock,
    ):
        known_hosts = fixture_known_hosts_file_content(99)

        mock_run.return_value = GetConfigsResult(
            True,
            {
                file_type_codes.PCS_KNOWN_HOSTS: [
                    ConfigInfo("NODE", known_hosts)
                ],
            },
        )
        mock_raw_file.exists.return_value = True
        mock_read_to_facade.side_effect = [fixture_known_hosts_facade()]

        configs, was_successful = self.fetcher.fetch(
            "test", [RequestTarget("NODE")], [file_type_codes.PCS_KNOWN_HOSTS]
        )

        mock_run.assert_called_once()
        mock_raw_file.exists.assert_called_once_with()
        mock_read_to_facade.assert_called_once_with()
        self.assertEqual(len(configs), 1)
        self.assertEqual(
            KnownHostsExporter.export(
                configs[file_type_codes.PCS_KNOWN_HOSTS].config
            ).decode("utf-8"),
            known_hosts,
        )
        self.assertTrue(was_successful)
        assert_report_item_list_equal(
            self.report_processor.report_item_list, []
        )
