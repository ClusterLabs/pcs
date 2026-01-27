from unittest import TestCase

from pcs.lib.permissions.config.facade import FacadeV2
from pcs.lib.permissions.config.types import (
    ClusterEntry,
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

_CLUSTER1 = ClusterEntry(name="cluster1", nodes=["A", "B"])
_CLUSTER2 = ClusterEntry(name="cluster2", nodes=["C", "D"])

_CONFIG = ConfigV2(
    data_version=1,
    clusters=[_CLUSTER1, _CLUSTER2],
    permissions=ClusterPermissions(
        local_cluster=[_USER1, _USER2, _GROUP1, _GROUP2]
    ),
)


class FacadeV2GetEntryTest(TestCase):
    def setUp(self):
        self.facade = FacadeV2(_CONFIG)

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


class FacadeV2DataVersionTest(TestCase):
    def test_success(self):
        facade = FacadeV2(_CONFIG)

        self.assertEqual(facade.data_version, 1)
        facade.set_data_version(10)
        self.assertEqual(facade.data_version, 10)


class FacadeV2IsClusterNameUsed(TestCase):
    def setUp(self):
        self.facade = FacadeV2(_CONFIG)

    def test_present(self):
        self.assertTrue(self.facade.is_cluster_name_in_use("cluster1"))

    def test_not_present(self):
        self.assertFalse(self.facade.is_cluster_name_in_use("cluster99"))


class FacadeV2AddCluster(TestCase):
    def test_success(self):
        facade = FacadeV2(_CONFIG)

        new_entry = ClusterEntry("cluster3", ["X", "Y"])
        facade.add_cluster(new_entry)
        self.assertEqual(
            facade.config.clusters, [_CLUSTER1, _CLUSTER2, new_entry]
        )
