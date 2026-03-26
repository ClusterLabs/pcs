from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject

from .types import PermissionGrantedType, PermissionTargetType


@dataclass(frozen=True)
class PermissionEntryDto(DataTransferObject):
    name: str
    type: PermissionTargetType
    allow: list[PermissionGrantedType]
