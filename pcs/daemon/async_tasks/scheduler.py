import multiprocessing as mp
import sys
import uuid
from logging import handlers
from queue import Empty
from typing import Dict

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

    def __init__(
        self,
        worker_count: int,
        worker_reset_limit: int,
    ) -> None:
        """
        worker_count -- number of worker processes to use
        worker_reset_limit -- number of tasks a worker will process
            before restarting itself
        """
        # pylint: disable=consider-using-with
        self._proc_pool_manager = mp.Manager()
        self._worker_message_q = self._proc_pool_manager.Queue()
        self._logger = pcsd_logger
        self._logging_q = self._proc_pool_manager.Queue()
        self._worker_log_listener = self._init_worker_logging()
        self._proc_pool = mp.Pool(
            processes=worker_count,
            maxtasksperchild=worker_reset_limit,
            initializer=worker_init,
            initargs=[self._worker_message_q, self._logging_q],
        )
        self._task_register: Dict[str, Task] = {}
        self._logger.info("Scheduler was successfully initialized.")
        self._logger.debug(
            "Process pool initialized with %d workers that reset "
            "after %d tasks",
            worker_count,
            worker_reset_limit,
        )

    def _init_worker_logging(self) -> handlers.QueueListener:
        q_listener = handlers.QueueListener(
            self._logging_q,
            *self._logger.handlers,
            respect_handler_level=True,
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
        self._logger.debug(
            "New task %s created (command: %s, parameters: %s)",
            task_ident,
            command_dto.command_name,
            command_dto.params,
        )
        return task_ident

    async def _schedule_task(self, task: Task) -> None:
        if task.is_kill_requested():
            # The task state and finish types are set during garbage
            # collection, we only prevent tasks here from queuing if
            # they are killed in CREATED state
            return
        try:
            self._proc_pool.apply_async(
                func=task_executor,
                args=[task.to_worker_command()],
            )
        except ValueError:
            self._logger.critical(
                "Unable to send task %s to worker pool.",
                task.task_ident,
            )
            sys.exit(1)
        task.state = TaskState.QUEUED

    async def _process_tasks(self) -> None:
        task_idents_to_delete = []
        for task in self._task_register.values():
            if task.state == TaskState.CREATED:
                await self._schedule_task(task)
            elif task.is_defunct():
                task.request_kill(TaskKillReason.COMPLETION_TIMEOUT)
            elif task.is_abandoned():
                task_idents_to_delete.append(task.task_ident)
            if task.state != TaskState.FINISHED and task.is_kill_requested():
                task.kill()

        for task_ident in task_idents_to_delete:
            del self._task_register[task_ident]

    async def perform_actions(self) -> int:
        """
        Calls all actions that are done by the scheduler in one pass

        DO NOT USE IN TIER0 TESTS! Look for a function with the same name
        in scheduler's integration tests
        :return: Number of received messages (useful for testing)
        """
        received_total = await self._receive_messages()
        await self._process_tasks()
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
            received_total += 1
            if not isinstance(message, Message):
                self._logger.error(
                    "Scheduler received something that is not a valid message."
                    'The type was: "%s".',
                    type(message).__name__,
                )
                continue
            try:
                task: Task = self._task_register[message.task_ident]
            except KeyError:
                self._logger.error(
                    "Message was delivered for task %s which is not located in "
                    "the task register.",
                    message.task_ident,
                )
                continue
            try:
                task.receive_message(message)
            except UnknownMessageError as exc:
                self._logger.critical(
                    'Message with unknown payload type "%s" was received by '
                    "the scheduler.",
                    exc.payload_type,
                )
                task.request_kill(TaskKillReason.INTERNAL_MESSAGING_ERROR)
        return received_total

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
