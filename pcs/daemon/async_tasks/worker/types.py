from dataclasses import dataclass
from typing import (
    Any,
    Union,
)

from pcs.common.async_tasks.types import TaskFinishType
from pcs.common.reports import ReportItemDto
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser


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
    command: Command
    auth_user: AuthUser
