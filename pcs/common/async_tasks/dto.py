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
class CommandDto(DataTransferObject):
    command_name: str
    params: Dict[str, Any]


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
