import multiprocessing as mp
import sys
import uuid

from collections import deque
from logging import Logger
from typing import (
    Dict,
    Deque,
)

from pcs import settings
from pcs.daemon.async_tasks.commands import Command
from pcs.daemon.async_tasks.dto import TaskResultDto
from pcs.daemon.async_tasks.logging import setup_scheduler_logger
from pcs.daemon.async_tasks.messaging import (
    Message,
    MessageType,
)
from pcs.daemon.async_tasks.task import (
    Task,
    TaskState,
    TaskFinishType,
)
from pcs.daemon.async_tasks.worker import worker_init, task_executor


class TaskNotFoundError(Exception):
    """Task with requested task_ident was not found in task_register"""

    def __init__(self, task_ident: str):
        self.task_ident: str = task_ident


class Scheduler:
    def __init__(self) -> None:
        self._proc_pool: mp.pool.Pool = mp.Pool(
            processes=settings.worker_count,
            maxtasksperchild=settings.worker_task_limit,
            initializer=worker_init,
        )
        self._proc_pool_manager: mp.Manager = mp.Manager()
        self._created_tasks_index: Deque[str] = deque()
        self._task_register: Dict[str, Task] = dict()
        self._worker_message_q: mp.Queue = mp.Queue()
        self._logger: Logger = setup_scheduler_logger()
        self._logger.info("Scheduler was successfully initialized.")

    def get_task(self, task_ident: str) -> TaskResultDto:
        try:
            return self._task_register[task_ident].to_dto()
        except IndexError:
            raise TaskNotFoundError(task_ident)

    def kill_task(self, task_ident: str) -> None:
        try:
            task: Task = self._task_register[task_ident]
        except IndexError:
            raise TaskNotFoundError(task_ident)

        if task.state == TaskState.CREATED:
            self._created_tasks_index.remove(task_ident)
            self._logger.debug(f"User is killing CREATED task {task_ident}.")
        elif task.state == TaskState.EXECUTED:
            task.kill()
            self._logger.debug(f"User is killing EXECUTED task {task_ident}.")

        # QUEUED tasks will be killed upon delivery of TaskExecuted message
        # in its handler by checking that TaskFinishType is USER_KILL
        # FINISHED tasks require no action.
        self._logger.debug(
            f"User is killing QUEUED or FINISHED task {task_ident}."
        )

        task.task_finish_type = TaskFinishType.USER_KILL

    def new_task(self, command: Command) -> str:
        task_ident: str = uuid.uuid4().hex
        while task_ident in self._task_register:
            task_ident = uuid.uuid4().hex

        self._task_register[task_ident] = Task(task_ident, command)
        self._created_tasks_index.append(task_ident)
        self._logger.debug(f"New task {task_ident} created.")
        return task_ident

    async def _garbage_collection(self) -> None:
        # TODO: Run less frequently
        # self._logger.debug("Running garbage collection.")
        for _, task in self._task_register.items():
            if task.is_abandoned() or task.is_defunct():
                task.task_finish_type = TaskFinishType.SCHEDULER_KILL
                task.kill()

    async def perform_actions(self):
        # self._logger.debug("Scheduler tick.")
        await self._schedule_tasks()
        await self._receive_messages()
        await self._garbage_collection()

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
            try:
                self._proc_pool.apply_async(
                    func=task_executor, args=[next_task.to_worker_command()],
                )
            except ValueError:
                self._logger.critical("Process pool is not running.")
                sys.exit(1)

    def terminate_nowait(self):
        # TODO: Make scheduler exit cleanly on daemon exit
        self._proc_pool.terminate()
        self._logger.info("Scheduler is correctly terminated.")
