from dataclasses import dataclass
from enum import auto, Enum
from typing import (
    Any,
    Union,
)

from pcs.common.async_tasks.types import TaskFinishType
from pcs.common.reports import ReportItemDto


class MessageType(Enum):
    REPORT = auto()
    TASK_EXECUTED = auto()
    TASK_FINISHED = auto()


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
    message_type: MessageType
    payload: Union[
        ReportItemDto, TaskExecuted, TaskFinished,
    ]
