from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    List,
    Optional,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.reports.dto import ReportItemDto

from .types import (
    TaskFinishType,
    TaskKillReason,
    TaskState,
)


@dataclass(frozen=True)
class CommandOptionsDto(DataTransferObject):
    request_timeout: Optional[int] = None
    effective_username: Optional[str] = None
    effective_groups: Optional[List[str]] = None


@dataclass(frozen=True)
class CommandDto(DataTransferObject):
    command_name: str
    params: Dict[str, Any]
    options: CommandOptionsDto


@dataclass(frozen=True)
class TaskIdentDto(DataTransferObject):
    task_ident: str


@dataclass(frozen=True)
class TaskResultDto(DataTransferObject):
    task_ident: str
    command: CommandDto
    reports: List[ReportItemDto]
    state: TaskState
    task_finish_type: TaskFinishType
    kill_reason: Optional[TaskKillReason]
    result: Any
