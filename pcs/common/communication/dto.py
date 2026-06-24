from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pcs.common.interface.dto import DataTransferObject
from pcs.common.reports.dto import ReportItemDto

from .types import CommunicationResultStatus as StatusType


@dataclass(frozen=True)
class InternalCommunicationResultDto(DataTransferObject):
    status: StatusType
    status_msg: str | None
    report_list: list[ReportItemDto]
    data: Any


@dataclass(frozen=True)
class InternalCommunicationRequestOptionsDto(DataTransferObject):
    request_timeout: int | None


@dataclass(frozen=True)
class InternalCommunicationRequestDto(DataTransferObject):
    options: InternalCommunicationRequestOptionsDto
    cmd: str
    cmd_data: Mapping[str, Any]
