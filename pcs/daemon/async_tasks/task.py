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
    TaskKillReason,
)
from pcs.common.interface.dto import ImplementsToDto
from pcs.common.reports.dto import ReportItemDto
from pcs.settings import (
    task_abandoned_timeout_seconds,
    task_unresponsive_timeout_seconds,
)
from pcs.common.async_tasks.dto import CommandDto, TaskResultDto
from .messaging import Message, MessageType, TaskExecuted, TaskFinished
from .worker import WorkerCommand


class UnknownMessageError(Exception):
    def __init__(self, unknown_message: Message):
        super().__init__(self)
        self.unknown_message = unknown_message


class Task(ImplementsToDto):
    def __init__(self, task_ident: str, command: CommandDto) -> None:
        self.task_ident: str = task_ident
        self.command: CommandDto = command
        self.reports: List[Any] = list()
        self.result: Any = None
        self.state: TaskState = TaskState.CREATED
        self.task_finish_type: TaskFinishType = TaskFinishType.UNFINISHED
        self.kill_requested: Optional[TaskKillReason] = None
        self._last_message_at: Optional[datetime.datetime] = None
        self._worker_pid: int = -1

    def is_abandoned(self) -> bool:
        if self.state == TaskState.FINISHED:
            # Last message of finished task is notification of its completion
            # and thus marks the time of its completion
            return self._is_timed_out(task_abandoned_timeout_seconds)
        # Even if the client dies before task finishes, task is going
        # to finish and will be garbage collected as abandoned
        return False

    def is_defunct(self) -> bool:
        return self._is_timed_out(task_unresponsive_timeout_seconds)

    def _is_timed_out(self, timeout_s: int) -> bool:
        if self._last_message_at:
            return datetime.datetime.now() - self._last_message_at > datetime.timedelta(
                seconds=timeout_s
            )
        return False

    def request_kill(self, reason: TaskKillReason) -> None:
        self.kill_requested = reason
        if self.state != TaskState.QUEUED:
            self.kill()

    def kill(self, reason: TaskKillReason = None) -> None:
        if reason:
            self.kill_requested = reason

        if self.state == TaskState.EXECUTED:
            try:
                os.kill(self._worker_pid, 15)
            except ProcessLookupError:
                # PID doesn't exist, process might have died on its own or
                # finished even in the time since task state was checked
                pass

        self.state = TaskState.FINISHED

    # Message handlers
    def receive_message(self, message: Message) -> None:
        self._last_message_at = datetime.datetime.now()
        if message.message_type == MessageType.REPORT:
            self._store_reports(message.payload)
        elif message.message_type == MessageType.TASK_EXECUTED:
            self._message_executed(message.payload)
        elif message.message_type == MessageType.TASK_FINISHED:
            self._message_finished(message.payload)
        else:
            raise UnknownMessageError(message)

    def _message_executed(self, message_payload: TaskExecuted) -> None:
        self._worker_pid = message_payload.worker_pid
        self.state = TaskState.EXECUTED

    def _message_finished(self, message_payload: TaskFinished) -> None:
        self.result = message_payload.result
        self.state = TaskState.FINISHED
        self.task_finish_type = message_payload.task_finish_type

    def _store_reports(self, message_payload: ReportItemDto) -> None:
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
            self.kill_requested,
            self.result,
        )
