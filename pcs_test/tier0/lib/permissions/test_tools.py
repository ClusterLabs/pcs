from unittest import TestCase, mock

from pcs.common import reports
from pcs.common.permissions.types import PermissionGrantedType
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.metadata import _for_pcs_settings_conf
from pcs.lib.file.raw_file import RawFileError
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.types import ClusterPermissions, ConfigV2
from pcs.lib.permissions.const import DEFAULT_PERMISSIONS
from pcs.lib.permissions.tools import (
    complete_access_list,
    read_pcs_settings_conf,
)

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal


class CompleteAccessList(TestCase):
    def test_combinations(self):
        combinations = (
            (
                [PermissionGrantedType.READ, PermissionGrantedType.GRANT],
                {PermissionGrantedType.READ, PermissionGrantedType.GRANT},
            ),
            (
                [PermissionGrantedType.WRITE, PermissionGrantedType.GRANT],
                {
                    PermissionGrantedType.READ,
                    PermissionGrantedType.WRITE,
                    PermissionGrantedType.GRANT,
                },
            ),
            (
                [PermissionGrantedType.FULL],
                {
                    PermissionGrantedType.READ,
                    PermissionGrantedType.WRITE,
                    PermissionGrantedType.GRANT,
                    PermissionGrantedType.FULL,
                },
            ),
        )

        for access_list, expected_result in combinations:
            with self.subTest(value=access_list):
                self.assertEqual(
                    complete_access_list(access_list), expected_result
                )


class ReadPcsSettingsConf(TestCase):
    DEFAULT_EMPTY_CONFIG = ConfigV2(
        data_version=0,
        clusters=[],
        permissions=ClusterPermissions(local_cluster=DEFAULT_PERMISSIONS),
    )

    DEFAULT_ERROR_EMPTY_CONFIG = ConfigV2(
        data_version=1, clusters=[], permissions=ClusterPermissions([])
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
        file_metadata = _for_pcs_settings_conf()
        self.file_instance_mock.raw_file.metadata = file_metadata

        facade, report_list = read_pcs_settings_conf()

        self.assertEqual(facade.config, self.DEFAULT_EMPTY_CONFIG)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.raw_file.read.assert_not_called()
        assert_report_item_list_equal(
            report_list,
            [
                fixture.debug(
                    reports.codes.FILE_DOES_NOT_EXIST_USING_DEFAULT,
                    file_type_code=file_metadata.file_type_code,
                    file_path=file_metadata.path,
                )
            ],
        )

    def test_read_success(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        facade = FacadeV2.create()
        self.file_instance_mock.read_to_facade.return_value = facade

        real_facade, report_list = read_pcs_settings_conf()

        self.assertEqual(real_facade, facade)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.read_to_facade.assert_called_once_with()
        assert_report_item_list_equal(report_list, [])

    def test_read_raw_file_error(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        file_metadata = _for_pcs_settings_conf()
        self.file_instance_mock.read_to_facade.side_effect = RawFileError(
            file_metadata, RawFileError.ACTION_READ, "reason"
        )

        real_facade, report_list = read_pcs_settings_conf()

        self.assertEqual(real_facade.config, self.DEFAULT_ERROR_EMPTY_CONFIG)
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
                    reason="reason",
                )
            ],
        )

    def test_read_parser_error(self):
        self.file_instance_mock.raw_file.exists.return_value = True
        file_metadata = _for_pcs_settings_conf()
        self.file_instance_mock.parser_exception_to_report_list.return_value = [
            reports.ReportItem.error(
                reports.messages.ParseErrorInvalidFileStructure(
                    reason="reason",
                    file_type_code=file_metadata.file_type_code,
                    file_path=file_metadata.path,
                )
            )
        ]
        self.file_instance_mock.read_to_facade.side_effect = (
            ParserErrorException()
        )

        real_facade, report_list = read_pcs_settings_conf()

        self.assertEqual(real_facade.config, self.DEFAULT_ERROR_EMPTY_CONFIG)
        self.file_instance_mock.raw_file.exists.assert_called_once_with()
        self.file_instance_mock.read_to_facade.assert_called_once_with()
        assert_report_item_list_equal(
            report_list,
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_INVALID_FILE_STRUCTURE,
                    reason="reason",
                    file_type_code=file_metadata.file_type_code,
                    file_path=file_metadata.path,
                )
            ],
        )
