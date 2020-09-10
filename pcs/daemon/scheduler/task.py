import datetime

from dataclasses import dataclass
from enum import auto, Enum, IntEnum
from typing import (
    Any,
    Dict,
    List,
    Optional
)

from .commands import Command, WorkerCommand
from .messaging import TaskExecuted, TaskFinished
from pcs.common.reports.dto import ReportItemDto

class TaskFinishType(Enum):
    FAIL = auto()
    UNFINISHED = auto()
    SUCCESS = auto()
    SCHEDULER_KILL = auto()
    USER_KILL = auto()

class TaskState(IntEnum):
    CREATED = 1
    QUEUED = 2
    EXECUTED = 3
    FINISHED = 4

@dataclass(frozen=True)
class TaskResult:
    task_ident: str
    command: Command
    reports: List[Any]
    state: TaskState
    task_finish_type: TaskFinishType
    result: Any

class Task:
    def __init__(self, task_ident: str, command: Command) -> None:
        self.command: Command = command
        self.reports: List[Any] = list()
        self.result: Any = None
        self.state: TaskState = TaskState.CREATED
        self.task_ident: str = task_ident
        self.task_finish_type: TaskFinishType = TaskFinishType.UNFINISHED
        self._last_message_at: Optional[datetime.datetime] = None
        self._worker_pid: int = -1

    def is_abandoned(self) -> bool:
        pass

    def is_defunct(self) -> bool:
        pass

    def kill(self) -> None:
        pass

    # Message handlers
    def message_executed(self, message_payload: TaskExecuted):
        pass

    def message_finished(self, message_payload: TaskFinished):
        pass

    def store_reports(self, message_payload: ReportItemDto):
        pass

    # Type conversions
    def to_worker_command(self) -> WorkerCommand:
        return WorkerCommand(self.task_ident, self.command)
