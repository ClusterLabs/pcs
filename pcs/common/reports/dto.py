from dataclasses import dataclass
from typing import (
    Any,
    Mapping,
    Optional,
)

from pcs.common.interface.dto import DataTransferObject

from .types import (
    ForceCode,
    MessageCode,
    SeverityLevel,
)


@dataclass(frozen=True)
class ReportItemSeverityDto(DataTransferObject):
    level: SeverityLevel
    force_code: Optional[ForceCode]


@dataclass(frozen=True)
class ReportItemMessageDto(DataTransferObject):
    code: MessageCode
    message: str
    payload: Mapping[str, Any]


@dataclass(frozen=True)
class ReportItemContextDto(DataTransferObject):
    node: str


@dataclass(frozen=True)
class ReportItemDto(DataTransferObject):
    severity: ReportItemSeverityDto
    message: ReportItemMessageDto
    context: Optional[ReportItemContextDto]
