from dataclasses import dataclass

from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.lib.auth.const import ADMIN_GROUP
from pcs.lib.permissions.config.types import PermissionEntry

DEFAULT_PERMISSIONS = [
    # Since ADMIN_GROUP has access to pacemaker by default anyway, we can safely
    # allow access in pcsd as well
    PermissionEntry(
        name=ADMIN_GROUP,
        type=PermissionTargetType.GROUP,
        allow=(
            PermissionGrantedType.READ,
            PermissionGrantedType.WRITE,
            PermissionGrantedType.GRANT,
        ),
    )
]


@dataclass(frozen=True)
class _Metadata:
    label: str
    description: str


PERMISSION_TARGET_TYPE_METADATA = {
    target_type: _Metadata(target_type.value.capitalize(), "")
    for target_type in PermissionTargetType
}


PERMISSION_GRANTED_TYPE_METADATA = {
    PermissionGrantedType.READ: _Metadata(
        "Read",
        "Allows to view cluster settings",
    ),
    PermissionGrantedType.WRITE: _Metadata(
        "Write",
        "Allows to modify cluster settings except permissions and ACLs",
    ),
    PermissionGrantedType.GRANT: _Metadata(
        "Grant",
        "Allows to modify cluster permissions and ACLs",
    ),
    PermissionGrantedType.FULL: _Metadata(
        "Full",
        "Allows unrestricted access to a cluster except for adding nodes",
    ),
}


PERMISSION_DEPENDENCIES = {
    PermissionGrantedType.READ: [],
    PermissionGrantedType.WRITE: [PermissionGrantedType.READ],
    PermissionGrantedType.GRANT: [],
    PermissionGrantedType.FULL: [
        PermissionGrantedType.READ,
        PermissionGrantedType.WRITE,
        PermissionGrantedType.GRANT,
    ],
}
