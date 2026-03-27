from dataclasses import dataclass
from typing import Collection, Sequence

from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)


@dataclass(frozen=True)
class ClusterEntry:
    name: str
    nodes: list[str]


@dataclass(frozen=True)
class PermissionEntry:
    name: str
    type: PermissionTargetType
    allow: Collection[PermissionGrantedType]


@dataclass(frozen=True)
class ClusterPermissions:
    local_cluster: Sequence[PermissionEntry]


@dataclass(frozen=True)
class ConfigV2:
    data_version: int
    clusters: Sequence[ClusterEntry]
    permissions: ClusterPermissions
