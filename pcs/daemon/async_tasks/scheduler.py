import multiprocessing as mp
import sys
from collections import defaultdict
from dataclasses import dataclass
from logging import handlers
from multiprocessing.pool import worker as mp_worker_init  # type: ignore
from queue import Empty
from typing import (
    Dict,
    List,
)

from pcs import settings
from pcs.common.async_tasks.dto import TaskResultDto
from pcs.common.async_tasks.types import TaskKillReason
from pcs.common.tools import get_unique_uuid
from pcs.daemon.async_tasks.types import Command
from pcs.daemon.log import pcsd as pcsd_logger
from pcs.lib.auth.types import AuthUser

from .task import (
    Task,
    TaskConfig,
    TaskState,
    UnknownMessageError,
)
from .worker.executor import (
    task_executor,
    worker_init,
)
from .worker.types import Message


class TaskNotFoundError(Exception):
    """
    Task with requested task_ident was not found in task_register
    """

    def __init__(self, task_ident: str, message: str = ""):
        super().__init__(message)
        self.task_ident = task_ident


@dataclass(frozen=True)
class SchedulerConfig:
    worker_count: int = settings.pcsd_worker_count
    max_worker_count: int = (
        settings.pcsd_worker_count + settings.pcsd_temporary_workers
    )
    worker_reset_limit: int = settings.pcsd_worker_reset_limit
    deadlock_threshold_timeout: int = settings.pcsd_deadlock_threshold_timeout
    task_config: TaskConfig = TaskConfig()


class Scheduler:
    # pylint: disable=too-many-instance-attributes
    """
    Task management core with an interface for the REST API
    """

    def __init__(self, config: SchedulerConfig) -> None:
        """
        worker_count -- number of worker processes to use
        worker_reset_limit -- number of tasks a worker will process
            before restarting itself
        """
        # pylint: disable=consider-using-with
        self._config = config
        self._proc_pool_manager = mp.Manager()
        self._worker_message_q = self._proc_pool_manager.Queue()
        self._logger = pcsd_logger
        self._logging_q = self._proc_pool_manager.Queue()
        self._worker_log_listener = self._init_worker_logging()
        self._single_use_process_pool: List[mp.Process] = []
        self._proc_pool = mp.Pool(
            processes=self._config.worker_count,
            maxtasksperchild=self._config.worker_reset_limit,
            initializer=worker_init,
            initargs=[self._worker_message_q, self._logging_q],
        )
        self._task_register: Dict[str, Task] = {}
        self._logger.info("Scheduler was successfully initialized.")
        self._logger.debug(
            "Scheduler initialized with config: %s", self._config
        )

    def _init_worker_logging(self) -> handlers.QueueListener:
        q_listener = handlers.QueueListener(
            self._logging_q,
            *self._logger.handlers,
            respect_handler_level=True,
        )
        q_listener.start()
        return q_listener

    def get_task(self, task_ident: str, auth_user: AuthUser) -> TaskResultDto:
        """
        Fetches all information about task for the client
        """
        task = self._return_task(task_ident)
        self._check_user(task, auth_user)
        if task.state == TaskState.FINISHED:
            task.request_deletion()
        return task.to_dto()

    @staticmethod
    def _check_user(task: Task, auth_user: AuthUser) -> None:
        if task.auth_user.username != auth_user.username:
            raise TaskNotFoundError(task.task_ident)

    async def wait_for_task(
        self, task_ident: str, auth_user: AuthUser
    ) -> TaskResultDto:
        task = self._return_task(task_ident)
        self._check_user(task, auth_user)
        await task.wait_until_finished()
        task.request_deletion()
        return task.to_dto()

    def kill_task(self, task_ident: str, auth_user: AuthUser) -> None:
        """
        Terminates the specified task

        This method only marks the task to be killed, all killing is done by
        the garbage collector
        """
        task = self._return_task(task_ident)
        self._check_user(task, auth_user)

        self._logger.debug("User is killing a task %s.", task_ident)
        task.request_kill(TaskKillReason.USER)

    def new_task(self, command: Command, auth_user: AuthUser) -> str:
        """
        Creates a new task that will be executed by the scheduler
        :param command: Command and its parameters
        :return: Task identifier
        """
        task_ident = get_unique_uuid(tuple(self._task_register.keys()))

        self._task_register[task_ident] = Task(
            task_ident, command, auth_user, self._config.task_config
        )
        self._logger.debug(
            (
                "New task %s created (command: %s, parameters: %s, "
                "api_v1_compatibility_mode: %s, api_v0_compatibility_mode: %s)"
            ),
            task_ident,
            command.command_dto.command_name,
            command.command_dto.params,
            command.api_v1_compatible,
            command.api_v0_compatible,
        )
        return task_ident

    def _is_possibly_dead_locked(self) -> bool:
        counter: Dict[TaskState, List[Task]] = defaultdict(list)
        for task in self._task_register.values():
            counter[task.state].append(task)

        return (
            len(counter[TaskState.CREATED]) + len(counter[TaskState.QUEUED]) > 0
            and (self._config.worker_count + len(self._single_use_process_pool))
            <= len(counter[TaskState.EXECUTED])
            and all(
                task.is_defunct(self._config.deadlock_threshold_timeout)
                for task in counter[TaskState.EXECUTED]
            )
        )

    def _schedule_task(self, task: Task) -> None:
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
        for task in list(self._task_register.values()):
            await self._process_task(task)

    async def _process_task(self, task: Task) -> None:
        if task.state == TaskState.CREATED:
            self._schedule_task(task)
        elif task.is_defunct():
            task.request_kill(TaskKillReason.COMPLETION_TIMEOUT)
        elif task.is_abandoned():
            task.request_deletion()
        if task.state != TaskState.FINISHED and task.is_kill_requested():
            task.kill()
        if task.is_deletion_requested():
            del self._task_register[task.task_ident]

    def _spawn_new_single_use_worker(self) -> None:
        # pylint: disable=protected-access
        additional_process = mp.Process(
            group=None,
            target=mp_worker_init,
            args=(
                self._proc_pool._inqueue,  # type: ignore
                self._proc_pool._outqueue,  # type: ignore
                worker_init,
                (self._worker_message_q, self._logging_q),
                1,
                False,
            ),
        )
        self._single_use_process_pool.append(additional_process)
        self._logger.info("Starting new temporary worker")
        additional_process.start()

    def _handle_single_use_process_pool(self) -> None:
        new_pool: List[mp.Process] = []
        for process in self._single_use_process_pool:
            if process.is_alive():
                new_pool.append(process)
            else:
                self._logger.info("Temporary worker removed")
                process.close()
        self._single_use_process_pool = new_pool

    async def perform_actions(self) -> int:
        """
        Calls all actions that are done by the scheduler in one pass

        DO NOT USE IN TIER0 TESTS! Look for a function with the same name
        in scheduler's integration tests
        :return: Number of received messages (useful for testing)
        """
        # TODO: remove return and fix doctext
        received_total = await self._receive_messages()
        await self._process_tasks()
        self._handle_single_use_process_pool()
        if (
            self._is_possibly_dead_locked()
            and len(self._single_use_process_pool)
            < self._config.max_worker_count - self._config.worker_count
        ):
            self._logger.warning(
                "All workers busy, possible dead-lock detected!"
            )
            self._spawn_new_single_use_worker()
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
