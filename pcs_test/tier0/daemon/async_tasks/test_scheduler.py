# pylint: disable=protected-access
from collections import deque
from unittest import mock
from queue import Empty
from tornado.testing import gen_test
from pcs.daemon.async_tasks import scheduler
from pcs.common.async_tasks.dto import CommandDto, TaskResultDto
from pcs.common.async_tasks.types import (
    TaskState,
    TaskKillReason,
    TaskFinishType,
)
from pcs.common.reports import ReportItem
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.daemon.async_tasks.messaging import Message, TaskExecuted
from pcs.daemon.async_tasks.worker import task_executor

from .helpers import SchedulerBaseTestCase, SchedulerBaseAsyncTestCase

WORKER1_PID = 2222
WORKER2_PID = 3333


class GetTaskTest(SchedulerBaseTestCase):
    def test_task_exists(self):
        self._create_tasks(1)
        task_result = self.scheduler.get_task("id0")
        self.assertEqual("command 0", task_result.command.command_name)

    def test_task_not_exists(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task("nonexistent")

    def test_delete_finished(self):
        self._create_tasks(3)
        self.scheduler._task_register["id1"].state = TaskState.FINISHED
        self.scheduler.get_task("id1")
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task("id1")


class KillTaskTest(SchedulerBaseTestCase):
    def test_task_exists(self):
        self._create_tasks(2)
        self.scheduler.kill_task("id0")
        task1_dto = self.scheduler.get_task("id0")
        task2_dto = self.scheduler.get_task("id1")
        # State and task_finish_type is not changing, only kill_reason
        self.assertEqual(TaskKillReason.USER, task1_dto.kill_reason)
        self.assertEqual(TaskState.CREATED, task1_dto.state)
        self.assertEqual(TaskFinishType.UNFINISHED, task1_dto.task_finish_type)
        self.assertIsNone(task2_dto.kill_reason)
        self.assertEqual(TaskState.CREATED, task2_dto.state)
        self.assertEqual(TaskFinishType.UNFINISHED, task2_dto.task_finish_type)

    def test_task_not_exists(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.kill_task("nonexistent")


class NewTaskTest(SchedulerBaseTestCase):
    def test_new_task(self):
        self._create_tasks(1)
        self.assertEqual(
            deque(["id0"]),
            self.scheduler._created_tasks_index,
        )
        self.assertEqual(
            TaskResultDto(
                "id0",
                CommandDto("command 0", {}),
                [],
                TaskState.CREATED,
                TaskFinishType.UNFINISHED,
                None,
                None,
            ),
            self.scheduler.get_task("id0"),
        )
        self.assertListEqual(
            ["id0"],
            list(self.scheduler._task_register.keys()),
        )

    class UuidStub:
        def __init__(self, x):
            self._iter = iter(x)

        @property
        def hex(self):
            return next(self._iter)

    @mock.patch("uuid.uuid4", new=UuidStub(["id0", "id0", "id1"]))
    def test_duplicate_task_ident(self):
        self._create_tasks(2)
        self.assertListEqual(
            ["id0", "id1"],
            list(self.scheduler._task_register.keys()),
        )


"""
class GarbageHuntingTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_no_defunct_or_abandoned(self):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(self.scheduler.get_task("id0").kill_reason)
        self.assertIsNone(self.scheduler.get_task("id1").kill_reason)
        self.assertIsNone(self.scheduler.get_task("id2").kill_reason)

    @mock.patch(
        "pcs.daemon.async_tasks.task.Task.is_defunct",
        side_effect=[False, True, False],
    )
    @gen_test
    async def test_defunct(self, _):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(self.scheduler.get_task("id0").kill_reason)
        self.assertEqual(
            TaskKillReason.COMPLETION_TIMEOUT,
            self.scheduler.get_task("id1").kill_reason,
        )
        self.assertIsNone(self.scheduler.get_task("id2").kill_reason)

    @mock.patch(
        "pcs.daemon.async_tasks.task.Task.is_abandoned",
        side_effect=[False, True, True],
    )
    @gen_test
    async def test_abandoned(self, _):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(self.scheduler.get_task("id0").kill_reason)
        self.assertEqual(
            TaskKillReason.ABANDONED,
            self.scheduler.get_task("id1").kill_reason,
        )
        self.assertEqual(
            TaskKillReason.ABANDONED,
            self.scheduler.get_task("id2").kill_reason,
        )
"""


class ReceiveMessagesTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_wrong_payload_type(self):
        worker_com = self.worker_com
        self._create_tasks(2)
        worker_com.put(Message("id0", TaskExecuted(WORKER1_PID)))
        worker_com.put(Message("id0", "definitely not a payload"))
        received = 0
        while received < 2:
            received += await self.scheduler._receive_messages()
        task1_dto = self.scheduler.get_task("id0")
        task2_dto = self.scheduler.get_task("id1")
        self.assertEqual(
            TaskKillReason.INTERNAL_MESSAGING_ERROR, task1_dto.kill_reason
        )
        self.assertIsNone(task2_dto.kill_reason)

    @gen_test
    async def test_wrong_message_type(self):
        self._create_tasks(2)
        self.worker_com.put(Message("id0", TaskExecuted(WORKER1_PID)))
        self.worker_com.put("definitely not a message")
        received = 0
        while received < 2:
            received += await self.scheduler._receive_messages()
        self.logger_mock.error.assert_called_once()

    @gen_test
    async def test_all_messages_consumed(self):
        task_count = 3
        message_count = 3
        self._create_tasks(task_count)
        for _ in range(message_count):
            for idx in range(task_count):
                self.worker_com.put(
                    Message(
                        f"id{idx}",
                        ReportItem.error(CibUpgradeSuccessful()).to_dto(),
                    )
                )
        received = 0
        while received < task_count * message_count:
            received += await self.scheduler._receive_messages()
        with self.assertRaises(Empty):
            self.worker_com.get_nowait()


class ScheduleTasksTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_empty_created_task_index(self):
        await self.scheduler._schedule_tasks()
        self.mp_pool_mock.assert_not_called()

    @gen_test
    async def test_normal_run(self):
        task_count = 4
        self._create_tasks(task_count)
        await self.scheduler._schedule_tasks()
        for task_ident in [f"id{i}" for i in range(task_count)]:
            self.assertEqual(
                TaskState.QUEUED, self.scheduler.get_task(task_ident).state
            )
        self.assertFalse(self.scheduler._created_tasks_index)

    @gen_test
    async def test_task_not_in_task_register(self):
        self._create_tasks(3)
        tasks = list(self.scheduler._task_register.values())
        del self.scheduler._task_register["id0"]
        await self.scheduler._schedule_tasks()
        self.logger_mock.error.assert_called_once()
        self.mp_pool_mock.apply_async.assert_has_calls(
            [
                mock.call(
                    func=task_executor,
                    args=[tasks[1].to_worker_command()],
                ),
                mock.call(
                    func=task_executor,
                    args=[tasks[2].to_worker_command()],
                ),
            ]
        )

    @gen_test
    async def test_killed_task(self):
        self._create_tasks(3)
        tasks = list(self.scheduler._task_register.values())
        self.scheduler.kill_task("id1")
        await self.scheduler._schedule_tasks()
        deleted_task = self.scheduler.get_task("id1")
        self.assertEqual(
            TaskFinishType.UNFINISHED, deleted_task.task_finish_type
        )
        self.assertEqual(TaskState.CREATED, deleted_task.state)
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task("id0").state,
        )
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task("id2").state,
        )
        self.mp_pool_mock.apply_async.assert_has_calls(
            [
                mock.call(
                    func=task_executor,
                    args=[tasks[0].to_worker_command()],
                ),
                mock.call(
                    func=task_executor,
                    args=[tasks[2].to_worker_command()],
                ),
            ]
        )
