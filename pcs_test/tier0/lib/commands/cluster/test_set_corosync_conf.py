import json
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.file import RawFileError
from pcs.lib.commands.cluster import config
from pcs.lib.corosync import config_parser

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import corosync_conf_fixture

_COROSYNC_CONF_CONTENT = corosync_conf_fixture()
_COROSYNC_CONF_WRITE_BYTES = config_parser.Exporter.export(
    config_parser.Parser.parse(_COROSYNC_CONF_CONTENT.encode("utf-8"))
)

_CFGSYNC_CTL_CUSTOM_BACKUP_COUNT = 10
_CFGSYNC_CTL_CUSTOM_CONTENT = json.dumps(
    {"file_backup_count": _CFGSYNC_CTL_CUSTOM_BACKUP_COUNT}
)


class SetCorosyncConfNotLiveEnv(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_not_live_corosync_conf(self):
        self.config.env.set_corosync_conf_data(_COROSYNC_CONF_CONTENT)
        self.env_assist.assert_raise_library_error(
            lambda: config.set_corosync_conf(
                self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
            ),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ],
            expected_in_processor=False,
        )


class SetCorosyncConfParseError(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_parse_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: config.set_corosync_conf(
                self.env_assist.get_env(), "totem {\n   version: 2\n"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                ),
            ]
        )

    def test_validation_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: config.set_corosync_conf(
                self.env_assist.get_env(), "totem {\n  option.name: value\n}"
            ),
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_CANNOT_SAVE_INVALID_NAMES_VALUES,
                    section_name_list=[],
                    attribute_name_list=["totem.option.name"],
                    attribute_value_pairs=[],
                )
            ],
            expected_in_processor=False,
        )


class SetCorosyncConfSuccess(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_corosync_conf_not_existing(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            file_data=_COROSYNC_CONF_WRITE_BYTES,
            can_overwrite=True,
        )
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )

    def test_corosync_conf_existing_cfgsync_ctl_not_existing(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exists=False,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.backup(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
        )
        self.config.raw_file.remove_old_backups(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            backup_count=settings.pcs_cfgsync_file_backup_count_default,
        )
        self.config.raw_file.write(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            file_data=_COROSYNC_CONF_WRITE_BYTES,
            can_overwrite=True,
        )
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )

    def fixture_success_with_cfgsyncctl(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            name="cfgsync_ctl.exists",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            content=_CFGSYNC_CTL_CUSTOM_CONTENT,
            name="cfgsync_ctl.read",
        )
        self.config.raw_file.backup(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
        )
        self.config.raw_file.remove_old_backups(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            backup_count=_CFGSYNC_CTL_CUSTOM_BACKUP_COUNT,
        )
        self.config.raw_file.write(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            file_data=_COROSYNC_CONF_WRITE_BYTES,
            can_overwrite=True,
        )

    def test_corosync_conf_existing_cfgsync_ctl_existing(self):
        self.fixture_success_with_cfgsyncctl()
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )

    def test_corosync_conf_existing_cfgsync_read_failure(self):
        self.fixture_success_with_cfgsyncctl()
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exception_msg="read failed",
            instead="cfgsync_ctl.read",
        )
        self.config.raw_file.remove_old_backups(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            backup_count=settings.pcs_cfgsync_file_backup_count_default,
            instead="raw_file.remove_old_backups",
        )
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_CFGSYNC_CTL,
                    operation=RawFileError.ACTION_READ,
                    reason="read failed",
                    file_path=settings.pcs_cfgsync_ctl_location,
                ),
            ]
        )

    def test_corosync_conf_existing_cfgsync_parse_failure(self):
        self.fixture_success_with_cfgsyncctl()
        self.config.raw_file.read(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            content="",
            instead="cfgsync_ctl.read",
        )
        self.config.raw_file.remove_old_backups(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            backup_count=settings.pcs_cfgsync_file_backup_count_default,
            instead="raw_file.remove_old_backups",
        )
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.PARSE_ERROR_JSON_FILE,
                    file_type_code=file_type_codes.PCS_CFGSYNC_CTL,
                    line_number=1,
                    column_number=1,
                    position=0,
                    reason="Expecting value",
                    full_msg=("Expecting value: line 1 column 1 (char 0)"),
                    file_path=settings.pcs_cfgsync_ctl_location,
                )
            ]
        )


class SetCorosyncConfWriteError(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def fixture_common(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync_conf.exists",
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_CFGSYNC_CTL,
            settings.pcs_cfgsync_ctl_location,
            exists=False,
            name="cfgsync_ctl.exists",
        )

    def test_backup_error(self):
        self.fixture_common()
        self.config.raw_file.backup(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exception_msg="backup failed",
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.set_corosync_conf(
                self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation=RawFileError.ACTION_BACKUP,
                    reason="backup failed",
                    file_path=settings.corosync_conf_file,
                ),
            ]
        )

    def test_backup_removal_error(self):
        self.fixture_common()
        self.config.raw_file.backup(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
        )
        self.config.raw_file.remove_old_backups(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            backup_count=settings.pcs_cfgsync_file_backup_count_default,
            exception_msg="Backup removal error",
        )
        self.config.raw_file.write(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            file_data=_COROSYNC_CONF_WRITE_BYTES,
            can_overwrite=True,
        )
        config.set_corosync_conf(
            self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation=RawFileError.ACTION_REMOVE_BACKUP,
                    reason="Backup removal error",
                    file_path=settings.corosync_conf_file,
                ),
            ]
        )

    def test_write_error(self):
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
        )
        self.config.raw_file.write(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            file_data=_COROSYNC_CONF_WRITE_BYTES,
            can_overwrite=True,
            exception_msg="write failed",
        )
        self.env_assist.assert_raise_library_error(
            lambda: config.set_corosync_conf(
                self.env_assist.get_env(), _COROSYNC_CONF_CONTENT
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.COROSYNC_CONF,
                    operation=RawFileError.ACTION_WRITE,
                    reason="write failed",
                    file_path=settings.corosync_conf_file,
                ),
            ]
        )
