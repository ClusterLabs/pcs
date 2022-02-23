from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import dr

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

REASON = "error msg"


class Config(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            ).raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="""
                    {
                        "local": {
                            "role": "PRIMARY"
                        },
                        "remote_sites": [
                            {
                                "nodes": [
                                    {
                                        "name": "recovery-node"
                                    }
                                ],
                                "role": "RECOVERY"
                            }
                        ]
                    }
                """,
            )
        )
        self.assertEqual(
            dr.get_config(self.env_assist.get_env()),
            {
                "local_site": {
                    "node_list": [],
                    "site_role": "PRIMARY",
                },
                "remote_site_list": [
                    {
                        "node_list": [
                            {"name": "recovery-node"},
                        ],
                        "site_role": "RECOVERY",
                    },
                ],
            },
        )

    def test_config_missing(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                exists=False,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.get_config(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.DR_CONFIG_DOES_NOT_EXIST,
                ),
            ]
        )

    def test_config_read_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            ).raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                exception_msg=REASON,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.get_config(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    operation=RawFileError.ACTION_READ,
                    reason=REASON,
                ),
            ]
        )

    def test_config_parse_error(self):
        (
            self.config.raw_file.exists(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
            ).raw_file.read(
                file_type_codes.PCS_DR_CONFIG,
                settings.pcsd_dr_config_location,
                content="bad content",
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: dr.get_config(self.env_assist.get_env()),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.PARSE_ERROR_JSON_FILE,
                    file_type_code=file_type_codes.PCS_DR_CONFIG,
                    file_path=settings.pcsd_dr_config_location,
                    line_number=1,
                    column_number=1,
                    position=0,
                    reason="Expecting value",
                    full_msg="Expecting value: line 1 column 1 (char 0)",
                ),
            ]
        )
