from enum import EnumType
from typing import Any
from unittest import TestCase

from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.permissions import const


class ConstMetadataForAllEnumMembers(TestCase):
    def assert_all_members_in_const(
        self, metadata_const: dict[EnumType, Any], enum_type: EnumType
    ) -> None:
        enum_members = set(enum_type)
        metadata_keys = set(metadata_const.keys())
        self.assertEqual(
            enum_members,
            metadata_keys,
            msg="Make sure constant defines metadata for all enum members",
        )

    def test_target_type_metadata(self):
        self.assert_all_members_in_const(
            const.PERMISSION_TARGET_TYPE_METADATA, PermissionTargetType
        )

    def test_permission_type_metadata(self):
        self.assert_all_members_in_const(
            const.PERMISSION_GRANTED_TYPE_METADATA, PermissionGrantedType
        )

    def test_permission_dependencies(self):
        self.assert_all_members_in_const(
            const.PERMISSION_DEPENDENCIES, PermissionGrantedType
        )
