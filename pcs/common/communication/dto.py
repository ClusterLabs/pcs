from dataclasses import dataclass
from typing import (
    Any,
    List,
    Mapping,
    Optional,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.reports.dto import ReportItemDto

from .types import CommunicationResultStatus as StatusType


@dataclass(frozen=True)
class InternalCommunicationResultDto(DataTransferObject):
    status: StatusType
    status_msg: Optional[str]
    report_list: List[ReportItemDto]
    data: Any


@dataclass(frozen=True)
class InternalCommunicationRequestOptionsDto(DataTransferObject):
    request_timeout: Optional[int]


@dataclass(frozen=True)
class InternalCommunicationRequestDto(DataTransferObject):
    options: InternalCommunicationRequestOptionsDto
    cmd: str
    cmd_data: Mapping[str, Any]
