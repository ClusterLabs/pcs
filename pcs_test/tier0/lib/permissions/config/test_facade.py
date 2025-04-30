from unittest import TestCase

from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.types import (
    ClusterPermissions,
    ConfigV2,
    PermissionAccessType,
    PermissionEntry,
    PermissionTargetType,
)

_USER1 = PermissionEntry(
    name="user1",
    type=PermissionTargetType.USER,
    allow=[PermissionAccessType.READ, PermissionAccessType.GRANT],
)
_USER2 = PermissionEntry(
    name="user2",
    type=PermissionTargetType.USER,
    allow=[PermissionAccessType.SUPERUSER],
)
_GROUP1 = PermissionEntry(
    name="group1",
    type=PermissionTargetType.GROUP,
    allow=[
        PermissionAccessType.READ,
        PermissionAccessType.WRITE,
        PermissionAccessType.GRANT,
    ],
)
_GROUP2 = PermissionEntry(
    name="group2",
    type=PermissionTargetType.GROUP,
    allow=[PermissionAccessType.WRITE],
)
_CONFIG = ConfigV2(
    data_version=1,
    clusters=[],
    permissions=ClusterPermissions(
        local_cluster=[_USER1, _USER2, _GROUP1, _GROUP2]
    ),
)


class FacadeV2GetEntryTest(TestCase):
    def setUp(self):
        self.facade = FacadeV2(_CONFIG)

    def test_data_version(self):
        self.assertEqual(1, self.facade.data_version)

    def test_user_success(self):
        self.assertEqual(
            _USER1, self.facade.get_entry(_USER1.name, _USER1.type)
        )

    def test_user_non_existing(self):
        self.assertIsNone(
            self.facade.get_entry("non-existing", PermissionTargetType.USER)
        )

    def test_user_wrong_type(self):
        self.assertIsNone(
            self.facade.get_entry(_GROUP1.name, PermissionTargetType.USER)
        )

    def test_group_success(self):
        self.assertEqual(
            _GROUP2, self.facade.get_entry(_GROUP2.name, _GROUP2.type)
        )

    def test_group_non_existing(self):
        self.assertIsNone(
            self.facade.get_entry("non-existing", PermissionTargetType.GROUP)
        )

    def test_group_wrong_type(self):
        self.assertIsNone(
            self.facade.get_entry(_USER2.name, PermissionTargetType.GROUP)
        )
