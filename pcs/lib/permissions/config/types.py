from dataclasses import dataclass
from typing import (
    FrozenSet,
    Sequence,
)

from pcs.common.permissions.types import (
    PermissionAccessType,
    PermissionTargetType,
)


@dataclass(frozen=True)
class ClusterEntry:
    name: str
    nodes: Sequence[str]


@dataclass(frozen=True)
class PermissionEntry:
    name: str
    type: PermissionTargetType
    allow: FrozenSet[PermissionAccessType]


@dataclass(frozen=True)
class ClusterPermissions:
    local_cluster: Sequence[PermissionEntry]


@dataclass(frozen=True)
class ConfigV2:
    data_version: int
    clusters: Sequence[ClusterEntry]
    permissions: ClusterPermissions
