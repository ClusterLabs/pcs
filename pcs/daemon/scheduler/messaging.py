from dataclasses import dataclass
from enum import auto, Enum
from typing import (
    Any,
    Dict,
    List,
    Union
)

from pcs.common.reports import ReportItemDto

class MessageType(Enum):
    REPORT = auto()
    TASK_EXECUTED = auto()
    TASK_FINISHED = auto()

@dataclass(frozen=True)
class TaskExecuted:
    pid: int

@dataclass(frozen=True)
class TaskFinished:
    result: Any

@dataclass(frozen=True)
class Message:
    task_ident: str
    message_type: MessageType
    payload: Union[
        ReportItemDto,
        TaskExecuted,
        TaskFinished,
    ]
