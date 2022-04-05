import multiprocessing as mp
import sys
import uuid
from collections import deque
from logging import handlers
from queue import Empty
from typing import (
    Deque,
    Dict,
)

from pcs import settings
from pcs.common.async_tasks.dto import (
    CommandDto,
    TaskResultDto,
)
from pcs.common.async_tasks.types import TaskKillReason
from pcs.daemon.log import pcsd as pcsd_logger

from .messaging import Message
from .task import (
    Task,
    TaskState,
    UnknownMessageError,
)
from .worker import (
    task_executor,
    worker_init,
)


class TaskNotFoundError(Exception):
    """
    Task with requested task_ident was not found in task_register
    """

    def __init__(self, task_ident: str, message: str = ""):
        super().__init__(message)
        self.task_ident = task_ident


class Scheduler:
    # pylint: disable=too-many-instance-attributes
    """
    Task management core with an interface for the REST API
    """

    def __init__(self) -> None:
        # pylint: disable=consider-using-with
        self._proc_pool_manager = mp.Manager()
        self._worker_message_q = self._proc_pool_manager.Queue()
        self._logger = pcsd_logger
        self._logging_q = self._proc_pool_manager.Queue()
        self._worker_log_listener = self._init_worker_logging()
        self._proc_pool = mp.Pool(
            processes=settings.worker_count,
            maxtasksperchild=settings.worker_task_limit,
            initializer=worker_init,
            initargs=[self._worker_message_q, self._logging_q],
        )
        self._created_tasks_index: Deque[str] = deque()
        self._task_register: Dict[str, Task] = {}
        self._logger.info("Scheduler was successfully initialized.")
        self._logger.debug(
            "Process pool initialized with %d workers that reset "
            "after %d tasks",
            settings.worker_count,
            settings.worker_task_limit,
        )

    def _init_worker_logging(self) -> handlers.QueueListener:
        q_listener = handlers.QueueListener(
            self._logging_q, *self._logger.handlers
        )
        q_listener.start()
        return q_listener

    def get_task(self, task_ident: str) -> TaskResultDto:
        """
        Fetches all information about task for the client
        """
        task_result_dto = self._return_task(task_ident).to_dto()

        # Task deletion after first retrieval of finished task
        if task_result_dto.state == TaskState.FINISHED:
            del self._task_register[task_ident]

        return task_result_dto

    def kill_task(self, task_ident: str) -> None:
        """
        Terminates the specified task

        This method only marks the task to be killed, all killing is done by
        the garbage collector
        """
        task = self._return_task(task_ident)

        self._logger.debug("User is killing a task %s.", task_ident)
        task.request_kill(TaskKillReason.USER)

    def new_task(self, command_dto: CommandDto) -> str:
        """
        Creates a new task that will be executed by the scheduler
        :param command_dto: Command and its parameters
        :return: Task identifier
        """
        is_duplicate = True
        while is_duplicate:
            task_ident = uuid.uuid4().hex
            is_duplicate = task_ident in self._task_register

        self._task_register[task_ident] = Task(task_ident, command_dto)
        self._created_tasks_index.append(task_ident)
        self._logger.debug(
            "New task %s created (command: %s, parameters: %s)",
            task_ident,
            command_dto.command_name,
            command_dto.params,
        )
        return task_ident

    async def _garbage_collection(self) -> None:
        """
        Terminates and/or deletes tasks marked for garbage collection

        All tasks need to use kill requests to be killed which set the right
        kill reason.
        Task.kill method is responsible for changing state and deciding what
        actions needs to be taken to properly remove the task from the scheduler
        """
        # self._logger.debug("Running garbage collection.")
        task_idents_to_delete = []
        for task in self._task_register.values():
            if task.is_defunct():
                task.request_kill(TaskKillReason.COMPLETION_TIMEOUT)
            elif task.is_abandoned():
                task_idents_to_delete.append(task.task_ident)
            if task.is_kill_requested():
                task.kill()
        # Dictionary can't change size during iteration
        for task_ident in task_idents_to_delete:
            del self._task_register[task_ident]

    async def perform_actions(self) -> int:
        """
        Calls all actions that are done by the scheduler in one pass

        DO NOT USE IN TIER0 TESTS! Look for a function with the same name
        in scheduler's integration tests
        :return: Number of received messages (useful for testing)
        """
        # self._logger.debug("Scheduler tick.")
        await self._schedule_tasks()
        # We need to guarantee that all messages have been received in tests
        received_total = await self._receive_messages()
        # Garbage collection needs to run right after receiving messages to
        # kill executed tasks most quickly
        await self._garbage_collection()
        return received_total

    async def _receive_messages(self) -> int:
        """
        Processes all incoming messages from workers
        :return: Number of received messages (useful for testing)
        """
        # Unreliable message count, since this is the only consumer, there
        # should not be less messages
        received_total = 0
        for _ in range(self._worker_message_q.qsize()):
            try:
                message: Message = self._worker_message_q.get_nowait()
            except Empty:
                # This may happen when messages are on the way but not quite
                # delivered yet. We'll get them later.
                return received_total
            if not isinstance(message, Message):
                self._logger.error(
                    "Scheduler received something that is not a valid message."
                    'The type was: "%s".',
                    type(message).__name__,
                )
                received_total += 1
                continue
            try:
                task: Task = self._task_register[message.task_ident]
            except KeyError:
                self._logger.error(
                    "Message was delivered for task %s which is not located in "
                    "the task register.",
                    message.task_ident,
                )
            try:
                task.receive_message(message)
            except UnknownMessageError as exc:
                self._logger.critical(
                    'Message with unknown payload type "%s" was received by '
                    "the scheduler.",
                    exc.payload_type,
                )
                task.request_kill(TaskKillReason.INTERNAL_MESSAGING_ERROR)
            received_total += 1
        return received_total

    async def _schedule_tasks(self) -> None:
        """
        Inserts tasks into the process pool
        """
        while self._created_tasks_index:
            next_task_ident = self._created_tasks_index.popleft()
            try:
                next_task: Task = self._task_register[next_task_ident]
            except KeyError:
                self._logger.error(
                    "Schedule attempt for task %s located in created tasks "
                    "index failed because no such task exists in the task "
                    "register.",
                    next_task_ident,
                )
                continue
            if next_task.is_kill_requested():
                # The task state and finish types are set during garbage
                # collection, we only prevent tasks here from queuing if
                # they are killed in CREATED state
                continue
            try:
                self._proc_pool.apply_async(
                    func=task_executor,
                    args=[next_task.to_worker_command()],
                )
            except ValueError:
                self._logger.critical(
                    "Unable to send task %s to worker pool.",
                    next_task_ident,
                )
                sys.exit(1)
            next_task.state = TaskState.QUEUED

    def _return_task(self, task_ident: str) -> Task:
        """
        Helper method for accessing tasks in the task register
        :param task_ident: Task identifier
        :return: Task instance
        """
        try:
            return self._task_register[task_ident]
        except KeyError:
            raise TaskNotFoundError(task_ident) from None

    def terminate_nowait(self) -> None:
        """
        Cleanly terminates the scheduler
        """
        self._worker_log_listener.stop()
        self._proc_pool.terminate()
        self._logger.info("Scheduler is correctly terminated.")
