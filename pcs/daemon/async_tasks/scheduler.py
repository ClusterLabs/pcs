import multiprocessing as mp
import sys
import uuid

from collections import deque
from typing import (
    Dict,
    Deque,
)

from pcs import settings
from pcs.common.async_tasks.dto import CommandDto, TaskResultDto
from pcs.common.async_tasks.types import (
    TaskState,
    TaskKillReason,
)
from .logging import setup_scheduler_logger
from .messaging import Message
from .task import Task, UnknownMessageError
from .worker import worker_init, task_executor


class TaskNotFoundError(Exception):
    """Task with requested task_ident was not found in task_register"""

    def __init__(self, task_ident: str, message: str = ""):
        super().__init__(message)
        self.task_ident = task_ident


class Scheduler:
    def __init__(self) -> None:
        self._proc_pool = mp.Pool(
            processes=settings.worker_count,
            maxtasksperchild=settings.worker_task_limit,
            initializer=worker_init,
        )
        self._proc_pool_manager = mp.Manager()
        self._created_tasks_index: Deque[str] = deque()
        self._task_register: Dict[str, Task] = dict()
        self._worker_message_q = self._proc_pool_manager.Queue()
        self._logger = setup_scheduler_logger()
        self._logger.info("Scheduler was successfully initialized.")

    def get_task(self, task_ident: str) -> TaskResultDto:
        task_result_dto = self.return_task(task_ident).to_dto()

        # Task deletion after first retrieval of finished task
        if task_result_dto.state == TaskState.FINISHED:
            del self._task_register[task_ident]

        return task_result_dto

    def kill_task(self, task_ident: str) -> None:
        task = self.return_task(task_ident)

        self._logger.debug("User is killing a task %s.", task_ident)
        task.request_kill(TaskKillReason.USER)

    def new_task(self, command_dto: CommandDto) -> str:
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

    async def _garbage_hunting(self) -> None:
        # TODO: Run less frequently (kill timeout/4?)
        # self._logger.debug("Running garbage hunting.")
        for task in self._task_register.values():
            if task.is_defunct():
                task.request_kill(TaskKillReason.COMPLETION_TIMEOUT)
            if task.is_abandoned():
                task.request_kill(TaskKillReason.ABANDONED)

    async def _garbage_collection(self) -> None:
        # self._logger.debug("Running garbage collection.")
        for task in self._task_register.values():
            if task.kill_requested:
                task.kill()

    async def perform_actions(self):
        # self._logger.debug("Scheduler tick.")
        await self._schedule_tasks()
        await self._receive_messages()
        # Garbage collection needs to run right after receiving messages to
        # kill executed tasks most quickly
        await self._garbage_collection()
        # TODO: Run hunting less frequently
        await self._garbage_hunting()

    async def _receive_messages(self) -> None:
        # Unreliable message count, since this is the only consumer, there
        # should not be less messages
        for _ in range(self._worker_message_q.qsize()):
            message: Message = self._worker_message_q.get_nowait()
            task: Task = self._task_register[message.task_ident]
            try:
                task.receive_message(message)
            except UnknownMessageError:
                self._logger.critical(
                    'Message with unknown message type "%s" was received by '
                    "the scheduler.",
                    message.message_type,
                )
                task.request_kill(TaskKillReason.INTERNAL_MESSAGING_ERROR)

    async def _schedule_tasks(self) -> None:
        while self._created_tasks_index:
            try:
                next_task_ident = self._created_tasks_index.popleft()
                next_task: Task = self._task_register[next_task_ident]
            except KeyError:
                self._logger.error(
                    "Task %s is not located in task register and it should "
                    "because its task_ident was located in created tasks "
                    "index.",
                    next_task_ident,
                )
                continue
            if next_task.kill_requested:
                next_task.kill()
                continue
            try:
                self._proc_pool.apply_async(
                    func=task_executor,
                    args=[
                        next_task.to_worker_command(),
                        self._worker_message_q,
                    ],
                )
            except ValueError:
                self._logger.critical(
                    "Unable to send task %s to worker pool.",
                    next_task.task_ident,
                )
                sys.exit(1)
            next_task.state = TaskState.QUEUED

    def return_task(self, task_ident: str) -> Task:
        try:
            return self._task_register[task_ident]
        except KeyError:
            raise TaskNotFoundError(task_ident)

    def terminate_nowait(self) -> None:
        # TODO: Make scheduler exit cleanly on daemon exit
        self._proc_pool.terminate()
        self._logger.info("Scheduler is correctly terminated.")
