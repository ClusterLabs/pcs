from dataclasses import dataclass
from enum import auto, Enum
from typing import (
    Any,
    Union,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from pcs.common.reports import ReportItemDto
    from pcs.daemon.async_tasks.task import TaskFinishType


class MessageType(Enum):
    REPORT = auto()
    TASK_EXECUTED = auto()
    TASK_FINISHED = auto()


@dataclass(frozen=True)
class TaskExecuted:
    worker_pid: int


@dataclass(frozen=True)
class TaskFinished:
    task_finish_type: "TaskFinishType"
    result: Any


@dataclass(frozen=True)
class Message:
    task_ident: str
    message_type: MessageType
    payload: Union[
        "ReportItemDto", TaskExecuted, TaskFinished,
    ]
