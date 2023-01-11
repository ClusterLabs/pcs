from logging import Logger
from unittest import (
    TestCase,
    mock,
)

from pcs.common.file import (
    FileMetadata,
    RawFileError,
)
from pcs.common.file_type_codes import PCS_SETTINGS_CONF
from pcs.lib.auth.const import (
    ADMIN_GROUP,
    SUPERUSER,
)
from pcs.lib.auth.types import AuthUser
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.permissions.checker import PermissionsChecker
from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.parser import ParserError
from pcs.lib.permissions.config.types import (
    ClusterPermissions,
    ConfigV2,
    PermissionAccessType,
    PermissionEntry,
    PermissionTargetType,
)

_FILE_PATH = "file path"
_FILE_METADATA = FileMetadata(
    file_type_code=PCS_SETTINGS_CONF,
    path=_FILE_PATH,
    owner_user_name="root",
    owner_group_name="root",
    permissions=None,
    is_binary=False,
)


def _config_fixture(permissions=tuple()):
    return ConfigV2(
        data_version=1,
        clusters=[],
        permissions=ClusterPermissions(local_cluster=permissions),
    )


_FACADE_FIXTURE = FacadeV2(
    _config_fixture(
        (
            PermissionEntry(
                name="user-read",
                type=PermissionTargetType.USER,
                allow=(PermissionAccessType.READ,),
            ),
            PermissionEntry(
                name="user-write",
                type=PermissionTargetType.USER,
                allow=(PermissionAccessType.WRITE,),
            ),
            PermissionEntry(
                name="user-full",
                type=PermissionTargetType.USER,
                allow=(PermissionAccessType.FULL,),
            ),
            PermissionEntry(
                name="group-grant",
                type=PermissionTargetType.GROUP,
                allow=(PermissionAccessType.GRANT,),
            ),
        )
    )
)


_EMPTY_CONFIG = _config_fixture()


class PermissionCheckerGetFacadeTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.file_instance_mock = mock.Mock(spec_set=FileInstance)
        self.file_instance_mock.raw_file.metadata = _FILE_METADATA
        self.file_instance_mock.raw_file.exists.return_value = True
        self.logger = mock.Mock(spec_set=Logger)
        with mock.patch.object(
            FileInstance,
            "for_pcs_settings_config",
            lambda *_args, **_kwargs: self.file_instance_mock,
        ):
            self.provider = PermissionsChecker(self.logger)

    def test_io_error(self):
        reason = "reason"
        self.file_instance_mock.read_to_facade.side_effect = RawFileError(
            _FILE_METADATA, RawFileError.ACTION_READ, reason
        )
        self.assertEqual(_EMPTY_CONFIG, self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to read file '%s': %s", _FILE_PATH, reason
        )

    def test_file_doesnt_exist(self):
        reason = "reason"
        self.file_instance_mock.raw_file.exists.return_value = False
        self.file_instance_mock.read_to_facade.side_effect = RawFileError(
            _FILE_METADATA, RawFileError.ACTION_READ, reason
        )
        self.assertEqual(
            ConfigV2(
                data_version=1,
                clusters=[],
                permissions=ClusterPermissions(
                    local_cluster=(
                        PermissionEntry(
                            type=PermissionTargetType.GROUP,
                            name=ADMIN_GROUP,
                            allow=(
                                PermissionAccessType.READ,
                                PermissionAccessType.WRITE,
                                PermissionAccessType.GRANT,
                            ),
                        ),
                    ),
                ),
            ),
            self.provider._get_facade().config,
        )
        self.logger.debug.assert_called_once_with(
            "File '%s' doesn't exist, using default configuration", _FILE_PATH
        )

    def test_json_parser_error(self):
        self.file_instance_mock.read_to_facade.side_effect = (
            JsonParserException(None)
        )
        self.assertEqual(_EMPTY_CONFIG, self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s': not valid json", _FILE_PATH
        )

    def test_invalid_format(self):
        reason = "reason"
        self.file_instance_mock.read_to_facade.side_effect = ParserError(reason)
        self.assertEqual(_EMPTY_CONFIG, self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s': %s", _FILE_PATH, reason
        )

    def test_other_parsing_error(self):
        self.file_instance_mock.read_to_facade.side_effect = (
            ParserErrorException()
        )
        self.assertEqual(_EMPTY_CONFIG, self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s'", _FILE_PATH
        )

    def test_success(self):
        facade = FacadeV2(
            ConfigV2(
                data_version=1,
                clusters=[],
                permissions=ClusterPermissions(
                    local_cluster=(
                        PermissionEntry(
                            name="user1",
                            type=PermissionTargetType.USER,
                            allow=(PermissionAccessType.WRITE),
                        ),
                    )
                ),
            )
        )
        self.file_instance_mock.read_to_facade.return_value = facade
        self.assertEqual(facade, self.provider._get_facade())
        self.logger.error.assert_not_called()


@mock.patch.object(
    PermissionsChecker, "_get_facade", lambda _self: _FACADE_FIXTURE
)
class PermissionCheckerGetPermissions(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.checker = PermissionsChecker(self.logger)

    def test_superuser(self):
        self.assertEqual(
            set(PermissionAccessType),
            self.checker.get_permissions(
                AuthUser(username=SUPERUSER, groups=tuple())
            ),
        )

    def test_completion_full(self):
        self.assertEqual(
            {
                PermissionAccessType.READ,
                PermissionAccessType.WRITE,
                PermissionAccessType.GRANT,
                PermissionAccessType.FULL,
            },
            self.checker.get_permissions(
                AuthUser(username="user-full", groups=tuple())
            ),
        )

    def test_completion_write(self):
        self.assertEqual(
            {
                PermissionAccessType.READ,
                PermissionAccessType.WRITE,
            },
            self.checker.get_permissions(
                AuthUser(username="user-write", groups=tuple())
            ),
        )

    def test_groups_permissions(self):
        self.assertEqual(
            {PermissionAccessType.GRANT},
            self.checker.get_permissions(
                AuthUser(username="user", groups=("group-grant",))
            ),
        )

    def test_user_and_groups_permissions(self):
        self.assertEqual(
            {
                PermissionAccessType.READ,
                PermissionAccessType.WRITE,
                PermissionAccessType.GRANT,
            },
            self.checker.get_permissions(
                AuthUser(username="user-write", groups=("group-grant",))
            ),
        )


@mock.patch.object(
    PermissionsChecker, "_get_facade", lambda _self: _FACADE_FIXTURE
)
class PermissionsCheckerIsAuthorizedTest(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.checker = PermissionsChecker(self.logger)

    def test_allowed(self):
        user = AuthUser("user-full", ("group1", "group2"))
        access = PermissionAccessType.READ
        self.assertTrue(self.checker.is_authorized(user, access))
        self.assertEqual(
            [
                mock.call(
                    "Permission check: username=%s groups=%s access=%s",
                    user.username,
                    ",".join(user.groups),
                    str(access.value),
                ),
                mock.call(
                    "Current user permissions: %s",
                    ",".join(
                        sorted(
                            str(permission.value)
                            for permission in (
                                PermissionAccessType.READ,
                                PermissionAccessType.WRITE,
                                PermissionAccessType.GRANT,
                                PermissionAccessType.FULL,
                            )
                        )
                    ),
                ),
                mock.call("%s access granted", str(access.value).capitalize()),
            ],
            self.logger.debug.mock_calls,
        )

    def test_not_allowed(self):
        user = AuthUser("user-full", ("group1", "group2"))
        access = PermissionAccessType.SUPERUSER
        self.assertFalse(self.checker.is_authorized(user, access))
        self.assertEqual(
            [
                mock.call(
                    "Permission check: username=%s groups=%s access=%s",
                    user.username,
                    ",".join(user.groups),
                    str(access.value),
                ),
                mock.call(
                    "Current user permissions: %s",
                    ",".join(
                        sorted(
                            str(permission.value)
                            for permission in (
                                PermissionAccessType.READ,
                                PermissionAccessType.WRITE,
                                PermissionAccessType.GRANT,
                                PermissionAccessType.FULL,
                            )
                        )
                    ),
                ),
                mock.call("%s access denied", str(access.value).capitalize()),
            ],
            self.logger.debug.mock_calls,
        )
