import datetime
import os

from typing import (
    Any,
    List,
    Optional,
)

from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskState,
    TaskKillOrigin,
)
from pcs.common.interface.dto import ImplementsToDto
from pcs.common.reports.dto import ReportItemDto
from pcs.settings import (
    task_abandoned_timeout_seconds,
    task_unresponsive_timeout_seconds,
)
from pcs.common.async_tasks.dto import CommandDto, TaskResultDto
from .messaging import TaskExecuted, TaskFinished
from .worker import WorkerCommand


class Task(ImplementsToDto):
    def __init__(self, task_ident: str, command: CommandDto) -> None:
        self.task_ident: str = task_ident
        self.command: CommandDto = command
        self.reports: List[Any] = list()
        self.result: Any = None
        self.state: TaskState = TaskState.CREATED
        self.task_finish_type: TaskFinishType = TaskFinishType.UNFINISHED
        self.kill_scheduled: Optional[TaskKillOrigin] = None
        self._last_message_at: Optional[datetime.datetime] = None
        self._worker_pid: int = -1

    def is_abandoned(self) -> bool:
        if self._last_message_at and self.state == TaskState.FINISHED:
            # Last message of finished task is notification of its completion
            # and thus marks the time of its completion
            return datetime.datetime.now() - self._last_message_at > datetime.timedelta(
                seconds=task_abandoned_timeout_seconds
            )
        # Even if the client dies before task finishes, task is going
        # to finish and will be garbage collected then
        return False

    def is_defunct(self) -> bool:
        if self._last_message_at is None:
            return False
        return datetime.datetime.now() - self._last_message_at > datetime.timedelta(
            seconds=task_unresponsive_timeout_seconds
        )

    def kill(self) -> None:
        try:
            os.kill(self._worker_pid, 15)
            self.state = TaskState.FINISHED
        except ProcessLookupError:
            # PID doesn't exist, process might have died on its own or
            # finished
            pass

    # Message handlers
    def message_executed(self, message_payload: TaskExecuted) -> None:
        self._worker_pid = message_payload.worker_pid
        self.state = TaskState.EXECUTED

    def message_finished(self, message_payload: TaskFinished) -> None:
        self.result = message_payload.result
        self.state = TaskState.FINISHED
        self.task_finish_type = message_payload.task_finish_type

    def store_reports(self, message_payload: ReportItemDto) -> None:
        self.reports.append(message_payload)

    # Type conversions
    def to_worker_command(self) -> WorkerCommand:
        return WorkerCommand(self.task_ident, self.command)

    def to_dto(self) -> TaskResultDto:
        return TaskResultDto(
            self.task_ident,
            self.command,
            self.reports,
            self.state,
            self.task_finish_type,
            self.result,
        )
