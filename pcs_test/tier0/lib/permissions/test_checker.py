from logging import Logger
from unittest import TestCase, mock

from pcs.common import reports
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.auth.types import AuthUser
from pcs.lib.permissions.checker import PermissionsChecker
from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.types import (
    ClusterPermissions,
    ConfigV2,
    PermissionEntry,
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.permissions.types import PermissionRequiredType


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
                allow=(PermissionGrantedType.READ,),
            ),
            PermissionEntry(
                name="user-write",
                type=PermissionTargetType.USER,
                allow=(PermissionGrantedType.WRITE,),
            ),
            PermissionEntry(
                name="user-full",
                type=PermissionTargetType.USER,
                allow=(PermissionGrantedType.FULL,),
            ),
            PermissionEntry(
                name="group-grant",
                type=PermissionTargetType.GROUP,
                allow=(PermissionGrantedType.GRANT,),
            ),
        )
    )
)


@mock.patch(
    "pcs.lib.permissions.checker.read_pcs_settings_conf",
    lambda: (_FACADE_FIXTURE, []),
)
class PermissionCheckerGetPermissions(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.checker = PermissionsChecker(self.logger)

    def test_completion_full(self):
        self.assertEqual(
            {
                PermissionRequiredType.READ,
                PermissionRequiredType.WRITE,
                PermissionRequiredType.GRANT,
                PermissionRequiredType.FULL,
            },
            self.checker._get_permissions(
                AuthUser(username="user-full", groups=tuple())
            ),
        )

    def test_completion_write(self):
        self.assertEqual(
            {
                PermissionRequiredType.READ,
                PermissionRequiredType.WRITE,
            },
            self.checker._get_permissions(
                AuthUser(username="user-write", groups=tuple())
            ),
        )

    def test_groups_permissions(self):
        self.assertEqual(
            {PermissionRequiredType.GRANT},
            self.checker._get_permissions(
                AuthUser(username="user", groups=("group-grant",))
            ),
        )

    def test_user_and_groups_permissions(self):
        self.assertEqual(
            {
                PermissionRequiredType.READ,
                PermissionRequiredType.WRITE,
                PermissionRequiredType.GRANT,
            },
            self.checker._get_permissions(
                AuthUser(username="user-write", groups=("group-grant",))
            ),
        )


@mock.patch(
    "pcs.lib.permissions.checker.read_pcs_settings_conf",
    lambda: (
        _FACADE_FIXTURE,
        [reports.ReportItem.debug(reports.messages.NoActionNecessary())],
    ),
)
class PermissionCheckerGetPermissionsReports(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.checker = PermissionsChecker(self.logger)

    def test_success(self):
        self.assertEqual(
            {PermissionRequiredType.READ, PermissionRequiredType.GRANT},
            self.checker._get_permissions(
                AuthUser(username="user-read", groups=("group-grant",))
            ),
        )
        self.logger.debug.assert_called_once_with(
            "No action necessary, requested change would have no effect"
        )


@mock.patch(
    "pcs.lib.permissions.checker.read_pcs_settings_conf",
    lambda: (_FACADE_FIXTURE, []),
)
class PermissionsCheckerIsAuthorizedTest(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.checker = PermissionsChecker(self.logger)

    def test_allowed(self):
        user = AuthUser("user-full", ("group1", "group2"))
        access = PermissionRequiredType.READ
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
                    "%s access %s", str(access.value).capitalize(), "granted"
                ),
            ],
            self.logger.debug.mock_calls,
        )

    def test_not_allowed(self):
        user = AuthUser("user-full", ("group1", "group2"))
        access = PermissionRequiredType.SUPERUSER
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
                    "%s access %s", str(access.value).capitalize(), "denied"
                ),
            ],
            self.logger.debug.mock_calls,
        )

    def test_unrestricted(self):
        user = AuthUser("user-full", ("group1", "group2"))
        access = PermissionRequiredType.NONE
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
                    "%s access %s", str(access.value).capitalize(), "granted"
                ),
            ],
            self.logger.debug.mock_calls,
        )

    def test_superuser(self):
        user = AuthUser(SUPERUSER, ("group1", "group2"))
        access = PermissionRequiredType.SUPERUSER
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
                    "%s access %s", str(access.value).capitalize(), "granted"
                ),
            ],
            self.logger.debug.mock_calls,
        )
