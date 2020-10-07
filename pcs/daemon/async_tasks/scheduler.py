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
    TaskFinishType,
    TaskState,
    TaskKillOrigin,
)
from .logging import setup_scheduler_logger
from .messaging import (
    Message,
    MessageType,
)
from .task import Task
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
        try:
            task_result_dto = self._task_register[task_ident].to_dto()
        except KeyError:
            raise TaskNotFoundError(task_ident)

        # Task deletion after first retrieval of finished task
        if task_result_dto.state == TaskState.FINISHED:
            del self._task_register[task_ident]

        return task_result_dto

    def kill_task(self, task_ident: str) -> None:
        try:
            task = self._task_register[task_ident]
        except KeyError:
            raise TaskNotFoundError(task_ident)

        self._logger.debug(f"User is killing a task {task_ident}.")
        task.task_finish_type = TaskFinishType.KILL
        task.kill_scheduled = TaskKillOrigin.USER

    def new_task(self, command_dto: CommandDto) -> str:
        is_duplicate = True
        while is_duplicate:
            task_ident = uuid.uuid4().hex
            is_duplicate = task_ident in self._task_register

        self._task_register[task_ident] = Task(task_ident, command_dto)
        self._created_tasks_index.append(task_ident)
        self._logger.debug(f"New task {task_ident} created.")
        return task_ident

    async def _garbage_hunting(self) -> None:
        # TODO: Run less frequently (kill timeout/4?)
        # self._logger.debug("Running garbage hunting.")
        for _, task in self._task_register.items():
            if task.is_abandoned() or task.is_defunct():
                task.task_finish_type = TaskFinishType.KILL
                task.kill_scheduled = TaskKillOrigin.SCHEDULER

    async def _garbage_collection(self) -> None:
        # self._logger.debug("Running garbage collection.")
        for _, task in self._task_register.items():
            if task.state == TaskState.EXECUTED and task.kill_scheduled:
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

    async def _receive_messages(self):
        # Unreliable message count, since this is the only consumer, there
        # should not be less messages
        message_count: int = self._worker_message_q.qsize()

        while message_count:
            message: Message = self._worker_message_q.get_nowait()
            task: Task = self._task_register[message.task_ident]

            if message.message_type == MessageType.REPORT:
                task.store_reports(message.payload)
            elif message.message_type == MessageType.TASK_EXECUTED:
                task.message_executed(message.payload)
            elif message.message_type == MessageType.TASK_FINISHED:
                task.message_finished(message.payload)
            else:
                self._logger.critical(
                    f"Message with unknown message type "
                    f"({message.message_type}) was received by the scheduler."
                )
                sys.exit(1)

            message_count -= 1

    async def _schedule_tasks(self) -> None:
        while self._created_tasks_index:
            next_task: Task = self._task_register[
                self._created_tasks_index.popleft()
            ]
            if next_task.kill_scheduled:
                # Mark task FINISHED for proper deletion from task_register
                next_task.state = TaskState.FINISHED
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
                self._logger.critical("Process pool is not running.")
                sys.exit(1)
            next_task.state = TaskState.QUEUED

    def terminate_nowait(self) -> None:
        # TODO: Make scheduler exit cleanly on daemon exit
        self._proc_pool.terminate()
        self._logger.info("Scheduler is correctly terminated.")
