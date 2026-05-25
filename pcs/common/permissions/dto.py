from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject

from .types import PermissionGrantedType, PermissionTargetType


@dataclass(frozen=True)
class PermissionEntryDto(DataTransferObject):
    name: str
    type: PermissionTargetType
    allow: list[PermissionGrantedType]


@dataclass(frozen=True)
class PermissionMetadataTargetTypeDto(DataTransferObject):
    code: PermissionTargetType
    label: str
    description: str


@dataclass(frozen=True)
class PermissionMetadataPermissionTypeDto(DataTransferObject):
    code: PermissionGrantedType
    label: str
    description: str


@dataclass(frozen=True)
class PermissionMetadataDependenciesDto(DataTransferObject):
    also_allows: dict[PermissionGrantedType, list[PermissionGrantedType]]


@dataclass(frozen=True)
class PermissionMetadataDto(DataTransferObject):
    user_types: list[PermissionMetadataTargetTypeDto]
    permission_types: list[PermissionMetadataPermissionTypeDto]
    permissions_dependencies: PermissionMetadataDependenciesDto
