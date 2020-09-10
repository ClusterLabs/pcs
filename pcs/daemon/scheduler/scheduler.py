import multiprocessing as mp
import uuid

from collections import deque
from typing import (
    Dict,
    Deque,
    List
)

from pcs import settings
from . import task
from .commands import Command
from .worker import worker_init, worker_error, task_executor

class Scheduler:
    def __init__(self):
        self._proc_pool : mp.pool.Pool = mp.Pool(
            processes=settings.worker_count,
            maxtasksperchild=settings.worker_task_limit,
            initializer=worker_init,
        )
        self._proc_pool_manager: mp.Manager = mp.Manager()
        self._created_tasks_index: Deque[str] = deque()
        self._task_register: Dict[str, task.Task] = dict()
        self._worker_message_q: mp.Queue = mp.Queue()

    def get_task(self, task_ident: str) -> task.TaskResult:
        pass

    def kill_task(self, task_ident: str) -> task.TaskResult:
        pass

    def new_task(self, command: Command) -> str:
        task_ident = uuid.uuid4().hex
        self._task_register[task_ident] = task.Task(task_ident, command)
        self._created_tasks_index.append(task_ident)
        return task_ident

    async def _garbage_collection(self):
        pass

    async def perform_actions(self):
        await self._schedule_tasks()
        await self._receive_messages()
        await self._garbage_collection()

    async def _receive_messages(self):
        message_count = self._worker_message_q.qsize()

        while message_count:

            message_count -= 1

    async def _schedule_tasks(self) -> None:
        while self._created_tasks_index:
            next_task = self._task_register[self._created_tasks_index.popleft()]
            try:
                self._proc_pool.apply_async(
                    func=task_executor,
                    args=[next_task.to_worker_command()],
                    error_callback=worker_error,
                )
            except ValueError:
                # Pool is not running - internal error
                # Fatal - scheduler needs to restart
                exit(1)
