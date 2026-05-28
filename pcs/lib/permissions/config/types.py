from dataclasses import dataclass
from typing import Collection, Sequence

from pcs.common.interface.dto import ImplementsToDto
from pcs.common.permissions.dto import PermissionEntryDto
from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)


@dataclass(frozen=True)
class ClusterEntry:
    name: str
    nodes: list[str]


@dataclass(frozen=True)
class PermissionEntry(ImplementsToDto):
    name: str
    type: PermissionTargetType
    allow: Collection[PermissionGrantedType]

    def to_dto(self) -> PermissionEntryDto:
        return PermissionEntryDto(
            name=self.name, type=self.type, allow=list(self.allow)
        )


@dataclass(frozen=True)
class ClusterPermissions:
    local_cluster: Sequence[PermissionEntry]


@dataclass(frozen=True)
class ConfigV2:
    data_version: int
    clusters: Sequence[ClusterEntry]
    permissions: ClusterPermissions
