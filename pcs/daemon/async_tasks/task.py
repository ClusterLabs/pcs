import datetime
import os
import signal
from asyncio import Event
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    List,
    Optional,
)

from pcs import settings
from pcs.common.async_tasks.dto import TaskResultDto
from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskKillReason,
    TaskState,
)
from pcs.common.interface.dto import ImplementsToDto
from pcs.common.reports.dto import ReportItemDto
from pcs.lib.auth.types import AuthUser

from .types import Command
from .worker.types import (
    Message,
    TaskExecuted,
    TaskFinished,
    WorkerCommand,
)


class UnknownMessageError(Exception):
    """
    A message with an unknown message type was received
    """

    def __init__(self, unknown_message: Message):
        super().__init__(self)
        self.payload_type = type(unknown_message.payload).__name__


_STATE_CHANGES_SEQUENCE = (
    TaskState.CREATED,
    TaskState.QUEUED,
    TaskState.EXECUTED,
    TaskState.FINISHED,
)


@dataclass(frozen=True)
class TaskConfig:
    abandoned_timeout: int = settings.task_abandoned_timeout_seconds
    unresponsive_timeout: int = settings.task_unresponsive_timeout_seconds
    deletion_timeout: int = settings.task_deletion_timeout_seconds


class Task(ImplementsToDto):
    """
    Task's representation in the scheduler
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(
        self,
        task_ident: str,
        command: Command,
        auth_user: AuthUser,
        config: TaskConfig,
    ) -> None:
        self._config = config
        self._task_ident: str = task_ident
        self._command: Command = command
        self._auth_user = auth_user
        self._reports: List[ReportItemDto] = []
        self._result: Any = None
        self._state: TaskState = TaskState.CREATED
        self._task_finish_type: TaskFinishType = TaskFinishType.UNFINISHED
        self._kill_reason: Optional[TaskKillReason] = None
        self._last_message_at: Optional[datetime.datetime] = None
        self._execution_started_at: Optional[datetime.datetime] = None
        self._worker_pid: int = -1
        self._finished_event = Event()
        self._to_delete_timestamp: Optional[datetime.datetime] = None

    @property
    def state(self) -> TaskState:
        return self._state

    @state.setter
    def state(self, state: TaskState) -> None:
        """
        Sets a new task state
        :param state: New task state
        """
        self._set_state(state)

    def _set_state(self, state: TaskState) -> None:
        try:
            if _STATE_CHANGES_SEQUENCE.index(
                self._state
            ) >= _STATE_CHANGES_SEQUENCE.index(state):
                raise AssertionError(
                    f"Invalid Task state change: {self._state} => {state}"
                )
        except ValueError as e:
            raise AssertionError(f"Invalid Task state: {state}") from e
        self._state = state
        if self.state == TaskState.FINISHED:
            self._finished_event.set()
        elif self.state == TaskState.EXECUTED:
            self._execution_started_at = datetime.datetime.now()

    @property
    def task_ident(self) -> str:
        return self._task_ident

    @property
    def auth_user(self) -> AuthUser:
        return self._auth_user

    def wait_until_finished(self) -> Awaitable[Any]:
        return self._finished_event.wait()

    def _get_last_updated_timestamp(self) -> Optional[datetime.datetime]:
        """
        Helper function for getting timestamp of the last message received

        This function forces a time of setting the task to FINISHED for the
        task that haven't received any messages.
        :return: Date and time of receiving the last message
        """
        if self._last_message_at is None and self.state == TaskState.FINISHED:
            # Update the timestamp of last message
            self._task_updated()
        return self._last_message_at

    def _is_timed_out(self, timeout_s: int) -> bool:
        """
        Helper function for watching time since last message was delivered
        :param timeout_s: Timeout in seconds
        :return: True if last message was delivered sooner than now - timeout,
            False otherwise
        """
        last_message_at = self._get_last_updated_timestamp()
        if last_message_at:
            return (
                datetime.datetime.now() - last_message_at
                > datetime.timedelta(seconds=timeout_s)
            )
        return False

    def is_abandoned(self) -> bool:
        """
        Checks that the task information were not queried after its finish
        :return: True if task was not queried for information before timeout,
            False otherwise
        """
        if self.state == TaskState.FINISHED:
            # Last message of finished task is notification of its completion
            # and thus marks the time of its completion
            return self._is_timed_out(self._config.abandoned_timeout)
        # Even if the client dies before task finishes, task is going
        # to finish and will be garbage collected as abandoned
        return False

    def is_defunct(self, timeout: Optional[int] = None) -> bool:
        """
        Checks that the task is not behaving as expected

        Healthy tasks are expected to send reports or other messages. If the
        task becomes stuck or malfunctions in some way, it's probable that it
        will stop sending reports or messages.
        :return: True if no messages were received during timeout period since
            the last message, False otherwise
        """
        if timeout is None or timeout < 0:
            timeout = self._config.unresponsive_timeout
        if self.state == TaskState.EXECUTED:
            return self._is_timed_out(timeout)
        return False

    def _task_updated(self) -> None:
        """
        Helper function for setting the last message timestamp to now
        """
        self._last_message_at = datetime.datetime.now()

    def is_kill_requested(self) -> bool:
        """
        Reports if the task needs to be killed

        :return: True for tasks marked for killing
        """
        return self._kill_reason is not None

    def request_kill(self, reason: TaskKillReason) -> None:
        """
        Marks the task for cleanup to the garbage collector
        :param reason: Reason for killing the task
        """
        self._kill_reason = reason

    def request_deletion(self) -> None:
        """
        Marks the task for deletion. .is_deletion_requested() method will
        return True after TaskConfig.deletion_timeout timeout.
        """
        if self._to_delete_timestamp is None:
            self._to_delete_timestamp = (
                datetime.datetime.now()
                + datetime.timedelta(seconds=self._config.deletion_timeout)
            )

    def is_deletion_requested(self) -> bool:
        """
        Indicates whether a task should be deleted.
        """
        if self._to_delete_timestamp is None:
            return False
        return datetime.datetime.now() >= self._to_delete_timestamp

    def kill(self) -> None:
        """
        Terminates the task and/or changes its state

        CREATED tasks are already prevented from being scheduled by requesting
        to kill them, only their state gets corrected here.
        EXECUTED tasks are terminated by by sending SIGTERM to their worker
        process and their state is changed here.
        """
        if self.state in (
            TaskState.QUEUED,
            TaskState.FINISHED,
        ):
            return
        if self.state == TaskState.EXECUTED:
            try:
                os.kill(self._worker_pid, signal.SIGTERM)
            except ProcessLookupError:
                # PID doesn't exist, process might have died on its own or
                # finished even in the time since task state was checked. Since
                # the killing wasn't successful, don't change the state
                return

        self._set_state(TaskState.FINISHED)
        self._task_finish_type = TaskFinishType.KILL

    # Message handlers
    def receive_message(self, message: Message) -> None:
        """
        Main message handler
        :param message: Message instance
        """
        if isinstance(message.payload, ReportItemDto):
            self._store_reports(message.payload)
        elif isinstance(message.payload, TaskExecuted):
            self._message_executed(message.payload)
        elif isinstance(message.payload, TaskFinished):
            self._message_finished(message.payload)
        else:
            raise UnknownMessageError(message)
        self._task_updated()

    def _message_executed(self, message_payload: TaskExecuted) -> None:
        """
        Handler for scheduler's TaskExecuted messages
        """
        self._worker_pid = message_payload.worker_pid
        self._set_state(TaskState.EXECUTED)

    def _message_finished(self, message_payload: TaskFinished) -> None:
        """
        Handler for scheduler's TaskFinished messages
        """
        self._result = message_payload.result
        self._set_state(TaskState.FINISHED)
        self._task_finish_type = message_payload.task_finish_type
        os.kill(self._worker_pid, signal.SIGCONT)

    def _store_reports(self, message_payload: ReportItemDto) -> None:
        """
        Handler for PCS reports
        """
        self._reports.append(message_payload)

    # Type conversions
    def to_worker_command(self) -> WorkerCommand:
        """
        Creates structure for sending task to a worker process
        :return: Instance with task identifier, command and parameters
        """
        return WorkerCommand(self._task_ident, self._command, self._auth_user)

    def to_dto(self) -> TaskResultDto:
        """
        Prepares response for task information query
        :return: DTO object with information about the task
        """
        return TaskResultDto(
            self._task_ident,
            self._command.command_dto,
            self._reports,
            self.state,
            self._task_finish_type,
            self._kill_reason,
            self._result,
        )
