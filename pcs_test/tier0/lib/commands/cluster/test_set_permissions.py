from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.permissions.dto import PermissionEntryDto
from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.commands import cluster
from pcs.lib.permissions.config.types import PermissionEntry

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import (
    fixture_expected_save_sync_reports,
    fixture_pcs_settings_file_content,
    fixture_save_sync_new_version_conflict,
    fixture_save_sync_new_version_error,
    fixture_save_sync_new_version_success,
)


class SetPermissionsNotInCluster(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_input_validation_failed(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.set_permissions(
                self.env_assist.get_env(),
                [PermissionEntryDto("", PermissionTargetType.USER, [])],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )

    def test_success_superuser_can_change_everything(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                1,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.WRITE],
                    )
                ],
            ),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2,
                # check that the even the dependant permissions are written
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.READ],
                    ),
                    PermissionEntry(
                        "john",
                        PermissionTargetType.USER,
                        allow=[
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                        ],
                    ),
                    PermissionEntry(
                        "admin",
                        PermissionTargetType.GROUP,
                        allow=[
                            PermissionGrantedType.FULL,
                            PermissionGrantedType.GRANT,
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                        ],
                    ),
                ],
            ).encode(),
            can_overwrite=True,
        )

        cluster.set_permissions(
            self.env_assist.get_env(user_login=SUPERUSER, user_groups=[]),
            [
                PermissionEntryDto(
                    "martin",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.READ],
                ),
                PermissionEntryDto(
                    "john",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.WRITE],
                ),
                PermissionEntryDto(
                    "admin",
                    PermissionTargetType.GROUP,
                    [PermissionGrantedType.FULL],
                ),
            ],
        )

    def test_success_user_in_group_can_change_full_users(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        local_pcs_settings = fixture_pcs_settings_file_content(
            1,
            permissions=[
                PermissionEntry(
                    "group",
                    PermissionTargetType.GROUP,
                    allow=[PermissionGrantedType.FULL],
                )
            ],
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=local_pcs_settings,
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            name="raw_file.exists.pcs_settings.permission_check",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=local_pcs_settings,
            name="raw_file.read.pcs_settings.permission_check",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "john",
                        PermissionTargetType.USER,
                        allow=[
                            PermissionGrantedType.FULL,
                            PermissionGrantedType.GRANT,
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                        ],
                    ),
                ],
            ).encode(),
            can_overwrite=True,
        )

        cluster.set_permissions(
            self.env_assist.get_env(user_login="john", user_groups=["group"]),
            [
                PermissionEntryDto(
                    "john",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.FULL],
                ),
            ],
        )

    def test_user_has_no_permissions_to_change_full_users(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        local_pcs_settings = fixture_pcs_settings_file_content(
            1,
            permissions=[
                PermissionEntry(
                    "john",
                    PermissionTargetType.USER,
                    allow=[PermissionGrantedType.WRITE],
                )
            ],
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=local_pcs_settings,
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            name="raw_file.exists.pcs_settings.permission_check",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=local_pcs_settings,
            name="raw_file.read.pcs_settings.permission_check",
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.set_permissions(
                self.env_assist.get_env(
                    user_login="john", user_groups=["wheel"]
                ),
                [
                    PermissionEntryDto(
                        "james",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.FULL],
                    ),
                ],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NOT_AUTHORIZED_TO_CHANGE_FULL_PERMISSION
                )
            ]
        )

    def test_no_full_permissions_no_change_in_full_users(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                1,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[
                            PermissionGrantedType.FULL,
                            PermissionGrantedType.GRANT,
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                        ],
                    )
                ],
            ),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[
                            PermissionGrantedType.FULL,
                            PermissionGrantedType.GRANT,
                            PermissionGrantedType.READ,
                            PermissionGrantedType.WRITE,
                        ],
                    ),
                    PermissionEntry(
                        "group",
                        PermissionTargetType.GROUP,
                        allow=[PermissionGrantedType.READ],
                    ),
                ],
            ).encode(),
            can_overwrite=True,
        )

        cluster.set_permissions(
            # The user doesn't have GRANT permission, but thats okay in this
            # test.
            # The check if user can call the command is done in daemon command
            # executor and not in the command - the command itself only checks
            # the FULL permission in case the user tries to change users with
            # FULL permissions.
            self.env_assist.get_env(user_login="john", user_groups=["wheel"]),
            [
                PermissionEntryDto(
                    "martin",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.FULL],
                ),
                PermissionEntryDto(
                    "group",
                    PermissionTargetType.GROUP,
                    [PermissionGrantedType.READ],
                ),
            ],
        )

    def test_error_reading_pcs_settings_conf(self):
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
            lambda: cluster.set_permissions(
                self.env_assist.get_env(),
                [
                    PermissionEntryDto(
                        "martin",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.READ],
                    )
                ],
            )
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

    def test_error_writing_pcs_settings_conf(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(1, permissions=[]),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.READ],
                    )
                ],
            ).encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.set_permissions(
                self.env_assist.get_env(),
                [
                    PermissionEntryDto(
                        "martin",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.READ],
                    ),
                ],
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


class SetPermissionsInCluster(TestCase):
    NODE_LABELS = ["node1", "node2", "node3"]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(self.NODE_LABELS)

    def test_success(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync.exists",
        )
        self.config.corosync_conf.load(self.NODE_LABELS)
        fixture_save_sync_new_version_success(
            self.config,
            node_labels=self.NODE_LABELS,
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    2,
                    permissions=[
                        PermissionEntry(
                            "martin",
                            PermissionTargetType.USER,
                            allow=[PermissionGrantedType.READ],
                        ),
                    ],
                )
            },
        )

        cluster.set_permissions(
            self.env_assist.get_env(user_login=SUPERUSER, user_groups=[]),
            [
                PermissionEntryDto(
                    "martin",
                    PermissionTargetType.USER,
                    [PermissionGrantedType.READ],
                )
            ],
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
            )
        )

    def test_sync_conflict(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync.exists",
        )
        self.config.corosync_conf.load(self.NODE_LABELS)
        cluster_newest_file = fixture_pcs_settings_file_content(
            data_version=300,
            permissions=[
                PermissionEntry(
                    "john",
                    PermissionTargetType.USER,
                    allow=[PermissionGrantedType.READ],
                )
            ],
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.READ],
                    ),
                ],
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
            lambda: cluster.set_permissions(
                self.env_assist.get_env(user_login=SUPERUSER, user_groups=[]),
                [
                    PermissionEntryDto(
                        "martin",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.READ],
                    )
                ],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
                expected_result="conflict",
            )
        )

    def test_sync_conflict_error_writing_newest_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync.exists",
        )
        self.config.corosync_conf.load(self.NODE_LABELS)
        cluster_newest_file = fixture_pcs_settings_file_content(
            data_version=300,
            permissions=[
                PermissionEntry(
                    "john",
                    PermissionTargetType.USER,
                    allow=[PermissionGrantedType.READ],
                )
            ],
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.READ],
                    ),
                ],
            ),
            fetch_after_conflict=True,
            remote_file_content=cluster_newest_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            cluster_newest_file.encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.set_permissions(
                self.env_assist.get_env(user_login=SUPERUSER, user_groups=[]),
                [
                    PermissionEntryDto(
                        "martin",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.READ],
                    )
                ],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
                expected_result="conflict",
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                ),
            ]
        )

    def test_sync_error(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync.exists",
        )
        self.config.corosync_conf.load(self.NODE_LABELS)
        fixture_save_sync_new_version_error(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2,
                permissions=[
                    PermissionEntry(
                        "martin",
                        PermissionTargetType.USER,
                        allow=[PermissionGrantedType.READ],
                    ),
                ],
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.set_permissions(
                self.env_assist.get_env(user_login=SUPERUSER, user_groups=[]),
                [
                    PermissionEntryDto(
                        "martin",
                        PermissionTargetType.USER,
                        [PermissionGrantedType.READ],
                    )
                ],
            )
        )

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
                expected_result="error",
            )
        )
