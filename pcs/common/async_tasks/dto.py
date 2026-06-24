from dataclasses import dataclass
from typing import Any

from pcs.common.interface.dto import DataTransferObject
from pcs.common.reports.dto import ReportItemDto

from .types import (
    TaskFinishType,
    TaskKillReason,
    TaskState,
)


@dataclass(frozen=True)
class CommandOptionsDto(DataTransferObject):
    request_timeout: int | None = None
    effective_username: str | None = None
    effective_groups: list[str] | None = None


@dataclass(frozen=True)
class CommandDto(DataTransferObject):
    command_name: str
    params: dict[str, Any]
    options: CommandOptionsDto


@dataclass(frozen=True)
class TaskIdentDto(DataTransferObject):
    task_ident: str


@dataclass(frozen=True)
class TaskResultDto(DataTransferObject):
    task_ident: str
    command: CommandDto
    reports: list[ReportItemDto]
    state: TaskState
    task_finish_type: TaskFinishType
    kill_reason: TaskKillReason | None
    result: Any
