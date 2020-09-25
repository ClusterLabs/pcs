import datetime
import os

from dataclasses import dataclass
from enum import auto, Enum, IntEnum
from typing import (
    Any,
    List,
    Optional
)

from pcs.common.reports.dto import ReportItemDto
from pcs.settings import (
    task_abandoned_timeout_seconds,
    task_unresponsive_timeout_seconds,
)
from .commands import Command, WorkerCommand
from .messaging import TaskExecuted, TaskFinished


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
        if self.state == TaskState.FINISHED:
            # Last message of finished task is notification of its completion
            # and thus marks the time of its completion
            return datetime.datetime.now() - self._last_message_at \
               > datetime.timedelta(seconds=task_abandoned_timeout_seconds)
        # Even if the client dies before task finishes, task is going
        # to finish and will be garbage collected then
        return False

    def is_defunct(self) -> bool:
        if self._last_message_at is None:
            return False
        return datetime.datetime.now() - self._last_message_at \
            > datetime.timedelta(seconds=task_unresponsive_timeout_seconds)

    def kill(self) -> None:
        os.kill(self._worker_pid, 15)

    # Message handlers
    def message_executed(self, message_payload: TaskExecuted):
        self._worker_pid = message_payload.worker_pid
        self.state = TaskState.EXECUTED

    def message_finished(self, message_payload: TaskFinished):
        self.result = message_payload.result
        self.state = TaskState.FINISHED
        self.task_finish_type = TaskFinishType.SUCCESS
        #TODO Handle failure in TaskFinishType

    def store_reports(self, message_payload: ReportItemDto):
        self.reports.append(message_payload)

    # Type conversions
    def to_worker_command(self) -> WorkerCommand:
        return WorkerCommand(self.task_ident, self.command)

    def to_task_result(self) -> TaskResult:
        return TaskResult(
            self.task_ident,
            self.command,
            self.reports,
            self.state,
            self.task_finish_type,
            self.result,
        )
