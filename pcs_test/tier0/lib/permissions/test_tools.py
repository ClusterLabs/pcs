from unittest import TestCase, mock

from pcs.common import reports
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.metadata import _for_pcs_settings_conf
from pcs.lib.file.raw_file import RawFileError
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.permissions import tools
from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.types import ClusterPermissions, ConfigV2
from pcs.lib.permissions.const import DEFAULT_PERMISSIONS

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class ReadPcsSettingsConf(TestCase):
    DEFAULT_EMPTY_CONFIG = ConfigV2(
        data_version=0,
        clusters=[],
        permissions=ClusterPermissions(local_cluster=DEFAULT_PERMISSIONS),
    )

    def setUp(self):
        self.file_instance_mock = mock.Mock(spec_set=FileInstance)
        self.patcher = mock.patch.object(
            FileInstance,
            "for_pcs_settings_config",
            return_value=self.file_instance_mock,
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_file_does_not_exist(self):
        self.file_instance_mock.raw_file.exists.return_value = False

        facade, report_list = tools.read_pcs_settings_conf()

        self.assertEqual(facade.config, self.DEFAULT_EMPTY_CONFIG)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.raw_file.read.assert_not_called()
        assert_report_item_list_equal(report_list, [])

    def test_read_success(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        facade = FacadeV2.create()
        self.file_instance_mock.read_to_facade.return_value = facade

        real_facade, report_list = tools.read_pcs_settings_conf()

        self.assertEqual(real_facade, facade)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.read_to_facade.assert_called_once_with()
        assert_report_item_list_equal(report_list, [])

    def test_read_raw_file_error(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        file_metadata = _for_pcs_settings_conf()
        self.file_instance_mock.read_to_facade.side_effect = RawFileError(
            file_metadata, RawFileError.ACTION_READ, ""
        )

        real_facade, report_list = tools.read_pcs_settings_conf()

        self.assertEqual(real_facade.config, self.DEFAULT_EMPTY_CONFIG)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.read_to_facade.assert_called_once_with()
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_metadata.file_type_code,
                    operation="read",
                    file_path=file_metadata.path,
                    reason="",
                )
            ],
        )

    def test_read_parser_error(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        file_metadata = _for_pcs_settings_conf()
        self.file_instance_mock.parser_exception_to_report_list.return_value = [
            reports.ReportItem.error(
                reports.messages.ParseErrorInvalidFileStructure(
                    reason="",
                    file_type_code=file_metadata.file_type_code,
                    file_path=file_metadata.path,
                )
            )
        ]
        self.file_instance_mock.read_to_facade.side_effect = (
            ParserErrorException()
        )

        real_facade, report_list = tools.read_pcs_settings_conf()

        self.assertEqual(real_facade.config, self.DEFAULT_EMPTY_CONFIG)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.read_to_facade.assert_called_once_with()
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    reason="",
                    file_type_code=file_metadata.file_type_code,
                    file_path=file_metadata.path,
                )
            ],
        )
