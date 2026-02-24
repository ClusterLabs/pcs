from pcs.lib.auth.const import ADMIN_GROUP
from pcs.lib.permissions.config.types import (
    PermissionAccessType,
    PermissionEntry,
    PermissionTargetType,
)

DEFAULT_PERMISSIONS = (
    # Since ADMIN_GROUP has access to pacemaker by default anyway, we can safely
    # allow access in pcsd as well
    PermissionEntry(
        name=ADMIN_GROUP,
        type=PermissionTargetType.GROUP,
        allow=(
            PermissionAccessType.READ,
            PermissionAccessType.WRITE,
            PermissionAccessType.GRANT,
        ),
    ),
)
