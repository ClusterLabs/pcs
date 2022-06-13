from dataclasses import dataclass
from typing import (
    Any,
    Union,
)

from pcs.common.async_tasks.dto import CommandDto
from pcs.common.async_tasks.types import TaskFinishType
from pcs.common.reports import ReportItemDto
from pcs.lib.auth.provider import AuthUser


@dataclass(frozen=True)
class TaskExecuted:
    worker_pid: int


@dataclass(frozen=True)
class TaskFinished:
    task_finish_type: TaskFinishType
    result: Any


@dataclass(frozen=True)
class Message:
    task_ident: str
    payload: Union[
        ReportItemDto,
        TaskExecuted,
        TaskFinished,
    ]


@dataclass(frozen=True)
class WorkerCommand:
    task_ident: str
    command: CommandDto
    auth_user: AuthUser
