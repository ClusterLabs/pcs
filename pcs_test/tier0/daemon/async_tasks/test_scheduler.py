# pylint: disable=protected-access
import dataclasses
from queue import Empty
from unittest import mock

from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
    TaskResultDto,
)
from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskKillReason,
    TaskState,
)
from pcs.common.reports import ReportItem
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.daemon.async_tasks import scheduler
from pcs.daemon.async_tasks.task import (
    Task,
    TaskConfig,
)
from pcs.daemon.async_tasks.worker.executor import task_executor
from pcs.daemon.async_tasks.worker.types import (
    Message,
    TaskExecuted,
)

from .helpers import (
    ANOTHER_AUTH_USER,
    AUTH_USER,
    SchedulerBaseAsyncTestCase,
)

WORKER1_PID = 2222
WORKER2_PID = 3333


class GetTaskTest(SchedulerBaseAsyncTestCase):
    def test_task_exists(self):
        self._create_tasks(1)
        task_result = self.scheduler.get_task("id0", AUTH_USER)
        self.assertEqual("command 0", task_result.command.command_name)

    def test_task_not_exists(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task("nonexistent", AUTH_USER)

    def test_delete_finished(self):
        self._create_tasks(3)
        self.scheduler._task_register["id1"].state = TaskState.FINISHED
        self.assertIsNone(
            self.scheduler._task_register["id1"]._to_delete_timestamp
        )
        self.scheduler.get_task("id1", AUTH_USER)
        self.assertIsNotNone(
            self.scheduler._task_register["id1"]._to_delete_timestamp
        )

    def test_different_user(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task("id0", ANOTHER_AUTH_USER)


class KillTaskTest(SchedulerBaseAsyncTestCase):
    def test_task_exists(self):
        self._create_tasks(2)
        self.scheduler.kill_task("id0", AUTH_USER)
        task1_dto = self.scheduler.get_task("id0", AUTH_USER)
        task2_dto = self.scheduler.get_task("id1", AUTH_USER)
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
            self.scheduler.kill_task("nonexistent", AUTH_USER)

    def test_different_user(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.kill_task("id0", ANOTHER_AUTH_USER)


class NewTaskTest(SchedulerBaseAsyncTestCase):
    def test_new_task(self):
        self._create_tasks(1)
        self.assertEqual(
            TaskResultDto(
                "id0",
                CommandDto(
                    "command 0", {}, CommandOptionsDto(request_timeout=None)
                ),
                [],
                TaskState.CREATED,
                TaskFinishType.UNFINISHED,
                None,
                None,
            ),
            self.scheduler.get_task("id0", AUTH_USER),
        )
        self.assertListEqual(
            ["id0"],
            list(self.scheduler._task_register.keys()),
        )

    class UuidStub:
        def __init__(self, uuid_list):
            self._iter = iter(uuid_list)

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


class ReceiveMessagesTest(SchedulerBaseAsyncTestCase):
    async def test_wrong_payload_type(self):
        worker_com = self.worker_com
        self._create_tasks(2)
        worker_com.put(Message("id0", TaskExecuted(WORKER1_PID)))
        worker_com.put(Message("id0", "definitely not a payload"))
        received = 0
        while received < 2:
            received += await self.scheduler._receive_messages()
        task1_dto = self.scheduler.get_task("id0", AUTH_USER)
        task2_dto = self.scheduler.get_task("id1", AUTH_USER)
        self.assertEqual(
            TaskKillReason.INTERNAL_MESSAGING_ERROR, task1_dto.kill_reason
        )
        self.assertIsNone(task2_dto.kill_reason)

    async def test_wrong_message_id(self):
        # TODO
        pass

    async def test_wrong_message_type(self):
        self._create_tasks(2)
        self.worker_com.put(Message("id0", TaskExecuted(WORKER1_PID)))
        self.worker_com.put("definitely not a message")
        received = 0
        while received < 2:
            received += await self.scheduler._receive_messages()
        self.logger_mock.error.assert_called_once()

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


class ProcessTasksTest(SchedulerBaseAsyncTestCase):
    async def test_empty_created_task_index(self):
        await self.scheduler._process_tasks()
        self.mp_pool_mock.assert_not_called()

    async def test_normal_run(self):
        task_count = 4
        self._create_tasks(task_count)
        await self.scheduler._process_tasks()
        for task_ident in [f"id{i}" for i in range(task_count)]:
            self.assertEqual(
                TaskState.QUEUED,
                self.scheduler.get_task(task_ident, AUTH_USER).state,
            )
        self.assertEqual(
            0,
            len(
                [
                    task
                    for task in self.scheduler._task_register.values()
                    if task.state == TaskState.CREATED
                ]
            ),
        )

    async def test_killed_task(self):
        self._create_tasks(3)
        tasks = list(self.scheduler._task_register.values())
        self.scheduler.kill_task("id1", AUTH_USER)
        await self.scheduler._process_tasks()
        deleted_task = self.scheduler.get_task("id1", AUTH_USER)
        self.assertEqual(TaskFinishType.KILL, deleted_task.task_finish_type)
        self.assertEqual(TaskState.FINISHED, deleted_task.state)
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task("id0", AUTH_USER).state,
        )
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task("id2", AUTH_USER).state,
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


def get_generator(return_values):
    def generator():
        yield from return_values

    gen = generator()
    return lambda *args, **kwargs: next(gen)


class DeadlockDetectionTest(SchedulerBaseAsyncTestCase):
    @staticmethod
    def _create_task(index, state=TaskState.CREATED):
        task = Task(
            f"id{index}",
            CommandDto(f"cmd{index}", {}, CommandOptionsDto()),
            AUTH_USER,
            TaskConfig(),
        )
        if state != TaskState.CREATED:
            task.state = state
        return task

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: False)
    def test_threshold_not_achieved(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2")
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2)
        }
        self.assertFalse(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", get_generator([True, False]))
    def test_threshold_not_achieved_for_some(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.EXECUTED)
        task3 = self._create_task("3")
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2, task3)
        }
        self.assertFalse(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_no_tasks_waiting(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.EXECUTED)
        task3 = self._create_task("3", TaskState.FINISHED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2, task3)
        }
        self.assertFalse(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_new_tasks_waiting(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.CREATED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2)
        }
        self.assertTrue(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_queued_tasks_waiting(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.QUEUED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2)
        }
        self.assertTrue(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_any_tasks_waiting(self):
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.QUEUED)
        task3 = self._create_task("3", TaskState.CREATED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2, task3)
        }
        self.assertTrue(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_workers_available(self):
        self.scheduler._config = dataclasses.replace(
            self.scheduler._config, worker_count=3
        )
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.QUEUED)
        task3 = self._create_task("3", TaskState.CREATED)
        task4 = self._create_task("4", TaskState.EXECUTED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2, task3, task4)
        }
        self.assertFalse(self.scheduler._is_possibly_dead_locked())

    @mock.patch.object(Task, "is_defunct", lambda self, timeout: True)
    def test_workers_available_with_tmp_workers(self):
        self.scheduler._config = dataclasses.replace(
            self.scheduler._config, worker_count=1
        )
        self.scheduler._single_use_process_pool = list(range(2))
        task1 = self._create_task("1", TaskState.EXECUTED)
        task2 = self._create_task("2", TaskState.QUEUED)
        task3 = self._create_task("3", TaskState.CREATED)
        task4 = self._create_task("4", TaskState.EXECUTED)
        self.scheduler._task_register = {
            task.task_ident: task for task in (task1, task2, task3, task4)
        }
        self.assertFalse(self.scheduler._is_possibly_dead_locked())
