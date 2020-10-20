import datetime
import os

from typing import (
    cast,
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
    """
    A message with an unknown message type was received
    """

    def __init__(self, unknown_message: Message):
        super().__init__(self)
        self.unknown_message = unknown_message


class Task(ImplementsToDto):
    """
    Task's representation in the scheduler
    """

    # pylint: disable=too-many-instance-attributes
    def __init__(self, task_ident: str, command: CommandDto) -> None:
        self._task_ident: str = task_ident
        self._command: CommandDto = command
        self._reports: List[Any] = list()
        self._result: Any = None
        self._state: TaskState = TaskState.CREATED
        self._task_finish_type: TaskFinishType = TaskFinishType.UNFINISHED
        self._kill_requested: Optional[TaskKillReason] = None
        self._last_message_at: Optional[datetime.datetime] = None
        self._worker_pid: int = -1

    @property
    def state(self) -> TaskState:
        return self._state

    @state.setter
    def state(self, state: TaskState) -> None:
        """
        Sets a new task state
        :param state: New task state
        """
        self._state = state

    def _is_timed_out(self, timeout_s: int) -> bool:
        """
        Helper function for watching time since last message was delivered
        :param timeout_s: Timeout in seconds
        :return: True if last message was delivered sooner than now - timeout,
            False otherwise
        """
        last_message_at = self._get_last_updated_timestamp()
        if last_message_at:
            return datetime.datetime.now() - last_message_at > datetime.timedelta(
                seconds=timeout_s
            )
        return False

    def is_abandoned(self) -> bool:
        """
        Checks that the task information were not queried after its finish
        :return: True if task was not queried for information before timeout,
            False otherwise
        """
        if self._state == TaskState.FINISHED:
            # Last message of finished task is notification of its completion
            # and thus marks the time of its completion
            return self._is_timed_out(task_abandoned_timeout_seconds)
        # Even if the client dies before task finishes, task is going
        # to finish and will be garbage collected as abandoned
        return False

    def is_defunct(self) -> bool:
        """
        Checks that the task is not behaving as expected

        Healthy tasks are expected to send reports or other messages. If the
        task becomes stuck or malfunctions in some way, it's probable that it
        will stop sending reports or messages.
        :return: True if no messages were received during timeout period since
            the last message, False otherwise
        """
        if self._state == TaskState.EXECUTED:
            return self._is_timed_out(task_unresponsive_timeout_seconds)
        return False

    def _task_updated(self) -> None:
        """
        Helper function for setting the last message timestamp to now
        """
        self._last_message_at = datetime.datetime.now()

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

    def is_kill_requested(self) -> bool:
        return self._kill_requested is not None

    def request_kill(self, reason: TaskKillReason) -> None:
        """
        Marks the task for cleanup to the garbage collector
        :param reason: Reason for killing the task
        """
        self._kill_requested = reason

    def kill(self) -> None:
        """
        Terminates the task

        This method terminates the task by sending SIGTERM to a worker process.
        It can be called on any task that needs to be terminated, even if the
        worker is not running, then it only sets the right status.
        """
        if self._state == TaskState.EXECUTED:
            try:
                os.kill(self._worker_pid, 15)
            except ProcessLookupError:
                # PID doesn't exist, process might have died on its own or
                # finished even in the time since task state was checked
                pass

        self._state = TaskState.FINISHED
        self._task_finish_type = TaskFinishType.KILL

    # Message handlers
    def receive_message(self, message: Message) -> None:
        """
        Main message handler
        :param message: Message instance
        """
        self._task_updated()
        if message.message_type == MessageType.REPORT:
            self._store_reports(cast(ReportItemDto, message.payload))
        elif message.message_type == MessageType.TASK_EXECUTED:
            self._message_executed(cast(TaskExecuted, message.payload))
        elif message.message_type == MessageType.TASK_FINISHED:
            self._message_finished(cast(TaskFinished, message.payload))
        else:
            raise UnknownMessageError(message)

    def _message_executed(self, message_payload: TaskExecuted) -> None:
        """
        Handler for scheduler's TaskExecuted messages
        """
        self._worker_pid = message_payload.worker_pid
        self._state = TaskState.EXECUTED

    def _message_finished(self, message_payload: TaskFinished) -> None:
        """
        Handler for scheduler's TaskFinished messages
        """
        self._result = message_payload.result
        self._state = TaskState.FINISHED
        self._task_finish_type = message_payload.task_finish_type

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
        return WorkerCommand(self._task_ident, self._command)

    def to_dto(self) -> TaskResultDto:
        """
        Prepares response for task information query
        :return: DTO object with information about the task
        """
        return TaskResultDto(
            self._task_ident,
            self._command,
            self._reports,
            self._state,
            self._task_finish_type,
            self._kill_requested,
            self._result,
        )
