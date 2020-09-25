import multiprocessing as mp
import sys
import uuid

from collections import deque
from typing import (
    Dict,
    Deque,
)

from pcs import settings
from .commands import Command
from .messaging import (
    Message,
    MessageType,
)
from .task import (
    Task,
    TaskResult,
    TaskState,
    TaskFinishType,
)
from .worker import (
    worker_init,
    worker_error,
    task_executor
)

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

    def get_task(self, task_ident: str) -> TaskResult:
        try:
            return self._task_register[task_ident].to_task_result()
            #TODO JSON conversion
        except IndexError as e:
            #TODO Raise to the API? Custom exception?
            raise e

    def kill_task(self, task_ident: str) -> None:
        try:
            task: Task = self._task_register[task_ident]
            #TODO JSON conversion
        except IndexError as e:
            #TODO Raise to the API? Custom exception?
            raise e

        if task.state >= TaskState.EXECUTED:
            task.kill()

        task.state = TaskState.FINISHED
        task.task_finish_type = TaskFinishType.USER_KILL

    def new_task(self, command: Command) -> str:
        task_ident: str = uuid.uuid4().hex
        self._task_register[task_ident] = Task(task_ident, command)
        self._created_tasks_index.append(task_ident)
        return task_ident
        #TODO JSON conversion

    async def _garbage_collection(self) -> None:
        for _, task in self._task_register:
            if task.is_abandoned() or task.is_defunct():
                task.state = TaskState.FINISHED
                task.task_finish_type = TaskFinishType.SCHEDULER_KILL
                task.kill()

    async def perform_actions(self):
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
                #TODO Scheduler internal error, log and exit
                sys.exit(1)

            message_count -= 1

    async def _schedule_tasks(self) -> None:
        while self._created_tasks_index:
            next_task: Task = \
                self._task_register[self._created_tasks_index.popleft()]
            try:
                self._proc_pool.apply_async(
                    func=task_executor,
                    args=[next_task.to_worker_command()],
                    error_callback=worker_error,
                )
            except ValueError:
                #TODO Pool is not running - internal error, log and exit
                sys.exit(1)
