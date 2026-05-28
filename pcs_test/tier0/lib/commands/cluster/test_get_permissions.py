from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.permissions.dto import (
    PermissionEntryDto,
    PermissionMetadataDependenciesDto,
    PermissionMetadataDto,
    PermissionMetadataPermissionTypeDto,
    PermissionMetadataTargetTypeDto,
)
from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.auth.const import ADMIN_GROUP
from pcs.lib.commands import cluster
from pcs.lib.permissions.config.types import PermissionEntry

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import fixture_pcs_settings_file_content


class GetPermissions(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_not_live_environment(self):
        self.config.env.set_corosync_conf_data("")
        self.env_assist.assert_raise_library_error(
            lambda: cluster.get_permissions(self.env_assist.get_env()),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ],
            expected_in_processor=False,
        )

    def test_success_file_does_not_exist(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            exists=False,
        )

        result = cluster.get_permissions(self.env_assist.get_env())

        self.assertEqual(
            result,
            [
                PermissionEntryDto(
                    name=ADMIN_GROUP,
                    type=PermissionTargetType.GROUP,
                    allow=[
                        PermissionGrantedType.READ,
                        PermissionGrantedType.WRITE,
                        PermissionGrantedType.GRANT,
                    ],
                )
            ],
        )
        self.env_assist.assert_reports(
            [
                fixture.debug(
                    reports.codes.FILE_DOES_NOT_EXIST_USING_DEFAULT,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )

    def test_success_empty_permissions(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(permissions=[]),
        )

        result = cluster.get_permissions(self.env_assist.get_env())

        self.assertEqual(result, [])

    def test_success_multiple_permissions(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                permissions=[
                    PermissionEntry(
                        "bob",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.FULL],
                    ),
                    PermissionEntry(
                        "wheel",
                        PermissionTargetType.GROUP,
                        allow=[PermissionGrantedType.READ],
                    ),
                ]
            ),
        )

        result = cluster.get_permissions(self.env_assist.get_env())

        self.assertEqual(
            result,
            [
                PermissionEntryDto(
                    "bob",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.FULL],
                ),
                PermissionEntryDto(
                    "wheel",
                    PermissionTargetType.GROUP,
                    [PermissionGrantedType.READ],
                ),
            ],
        )

    def test_error_reading_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.get_permissions(self.env_assist.get_env())
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="read",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )


class GetPermissionsMetadata(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    def test_success(self):
        result = cluster.get_permissions_metadata(self.env_assist.get_env())

        self.assertEqual(
            result,
            PermissionMetadataDto(
                user_types=[
                    PermissionMetadataTargetTypeDto(
                        PermissionTargetType.USER, "User", ""
                    ),
                    PermissionMetadataTargetTypeDto(
                        PermissionTargetType.GROUP, "Group", ""
                    ),
                ],
                permission_types=[
                    PermissionMetadataPermissionTypeDto(
                        PermissionGrantedType.READ,
                        "Read",
                        "Allows to view cluster settings",
                    ),
                    PermissionMetadataPermissionTypeDto(
                        PermissionGrantedType.WRITE,
                        "Write",
                        "Allows to modify cluster settings except permissions and ACLs",
                    ),
                    PermissionMetadataPermissionTypeDto(
                        PermissionGrantedType.GRANT,
                        "Grant",
                        "Allows to modify cluster permissions and ACLs",
                    ),
                    PermissionMetadataPermissionTypeDto(
                        PermissionGrantedType.FULL,
                        "Full",
                        "Allows unrestricted access to a cluster except for adding nodes",
                    ),
                ],
                permissions_dependencies=PermissionMetadataDependenciesDto(
                    {
                        PermissionGrantedType.WRITE: [
                            PermissionGrantedType.READ
                        ],
                        PermissionGrantedType.FULL: [
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                            PermissionGrantedType.GRANT,
                        ],
                    }
                ),
            ),
        )
