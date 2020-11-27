# pylint: disable=protected-access
import logging
import multiprocessing as mp

from collections import deque
from unittest import TestCase, mock
from tornado.testing import AsyncTestCase, gen_test
from tornado.gen import sleep as async_sleep

from pcs.common.async_tasks.dto import CommandDto, TaskResultDto
from pcs.common.async_tasks.types import (
    TaskState,
    TaskKillReason,
    TaskFinishType,
)
from pcs.common.reports import ReportItem
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.daemon.async_tasks import scheduler
from pcs.daemon.async_tasks.messaging import Message, TaskExecuted
from pcs.daemon.async_tasks.worker import task_executor

TASK_IDENT = "00000000000000000123456789abcdef"
WORKER1_PID = 2222
WORKER2_PID = 3333


def _task_ident_from_idx(index):
    index_str = str(index)
    return f"{index_str}{TASK_IDENT[len(index_str):]}"


class FakeSchedulerMixin:
    def __init__(self):
        # pylint: disable=no-value-for-parameter
        self.scheduler = self._init_scheduler()

    @mock.patch("logging.getLogger")
    @mock.patch("multiprocessing.Pool", spec=mp.Pool)
    @mock.patch("multiprocessing.Manager")
    def _init_scheduler(self, mock_mp_manager, mock_mp_pool, mock_get_logger):
        # We can patch Queue here because every method will instantiate its own
        self.worker_com = mp.Queue()
        mock_mp_manager.return_value.Queue.return_value = self.worker_com
        self.mp_pool_mock = mock_mp_pool.return_value = mock.Mock()
        self.logger_mock = mock_get_logger.return_value = mock.Mock(
            spec=logging.Logger
        )
        return scheduler.Scheduler()

    def _create_tasks(self, count):
        for i in range(1, count + 1):
            with mock.patch("uuid.uuid4") as mock_uuid:
                mock_uuid().hex = _task_ident_from_idx(i)
                self.scheduler.new_task(CommandDto(f"command {i}", {}))


class SchedulerBaseTestCase(TestCase, FakeSchedulerMixin):
    def setUp(self):
        FakeSchedulerMixin.__init__(self)
        super().setUp()


class SchedulerBaseAsyncTestCase(AsyncTestCase, FakeSchedulerMixin):
    def setUp(self):
        FakeSchedulerMixin.__init__(self)
        super().setUp()


class GetTaskTest(SchedulerBaseTestCase):
    def test_task_exists(self):
        self._create_tasks(1)
        task_result = self.scheduler.get_task(_task_ident_from_idx(1))
        self.assertEqual("command 1", task_result.command.command_name)

    def test_task_not_exists(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task(TASK_IDENT)

    def test_delete_finished(self):
        self._create_tasks(3)
        self.scheduler._task_register[
            _task_ident_from_idx(2)
        ].state = TaskState.FINISHED
        self.scheduler.get_task(_task_ident_from_idx(2))
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task(_task_ident_from_idx(2))

    def test_malformed_task_ident(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.get_task("blatantly invalid task_ident")


class KillTaskTest(SchedulerBaseTestCase):
    def test_task_exists(self):
        self._create_tasks(2)
        self.scheduler.kill_task(_task_ident_from_idx(1))
        task1_dto = self.scheduler.get_task(_task_ident_from_idx(1))
        task2_dto = self.scheduler.get_task(_task_ident_from_idx(2))
        # State and task_finish_type is not changing, only kill_requested
        self.assertEqual(TaskKillReason.USER, task1_dto.kill_requested)
        self.assertEqual(TaskState.CREATED, task1_dto.state)
        self.assertEqual(TaskFinishType.UNFINISHED, task1_dto.task_finish_type)
        self.assertIsNone(task2_dto.kill_requested)
        self.assertEqual(TaskState.CREATED, task2_dto.state)
        self.assertEqual(TaskFinishType.UNFINISHED, task2_dto.task_finish_type)

    def test_task_not_exists(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.kill_task(TASK_IDENT)

    def test_malformed_task_id(self):
        self._create_tasks(1)
        with self.assertRaises(scheduler.TaskNotFoundError):
            self.scheduler.kill_task("blatantly invalid task_ident")


class NewTaskTest(SchedulerBaseTestCase):
    uuids = [
        _task_ident_from_idx(1),
        _task_ident_from_idx(1),
        _task_ident_from_idx(2),
    ]

    def test_new_task(self):
        self._create_tasks(1)
        self.assertEqual(
            deque([_task_ident_from_idx(1)]),
            self.scheduler._created_tasks_index,
        )
        self.assertEqual(
            TaskResultDto(
                _task_ident_from_idx(1),
                CommandDto("command 1", {}),
                [],
                TaskState.CREATED,
                TaskFinishType.UNFINISHED,
                None,
                None,
            ),
            self.scheduler.get_task(_task_ident_from_idx(1)),
        )
        self.assertListEqual(
            [_task_ident_from_idx(1)],
            list(self.scheduler._task_register.keys()),
        )

    class UuidStub:
        def __init__(self, x):
            self._iter = iter(x)

        @property
        def hex(self):
            return next(self._iter)

    @mock.patch("uuid.uuid4", new=UuidStub(uuids))
    def test_duplicate_task_ident(self):
        self._create_tasks(2)
        self.assertListEqual(
            [_task_ident_from_idx(1), _task_ident_from_idx(2)],
            list(self.scheduler._task_register.keys()),
        )


class GarbageHuntingTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_no_defunct_or_abandoned(self):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(1)).kill_requested
        )
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(2)).kill_requested
        )
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(3)).kill_requested
        )

    @mock.patch(
        "pcs.daemon.async_tasks.task.Task.is_defunct",
        side_effect=[False, True, False],
    )
    @gen_test
    async def test_defunct(self, _):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(1)).kill_requested
        )
        self.assertEqual(
            TaskKillReason.COMPLETION_TIMEOUT,
            self.scheduler.get_task(_task_ident_from_idx(2)).kill_requested,
        )
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(3)).kill_requested
        )

    @mock.patch(
        "pcs.daemon.async_tasks.task.Task.is_abandoned",
        side_effect=[False, True, True],
    )
    @gen_test
    async def test_abandoned(self, _):
        self._create_tasks(3)
        await self.scheduler._garbage_hunting()
        self.assertIsNone(
            self.scheduler.get_task(_task_ident_from_idx(1)).kill_requested
        )
        self.assertEqual(
            TaskKillReason.ABANDONED,
            self.scheduler.get_task(_task_ident_from_idx(2)).kill_requested,
        )
        self.assertEqual(
            TaskKillReason.ABANDONED,
            self.scheduler.get_task(_task_ident_from_idx(3)).kill_requested,
        )


class ReceiveMessagesTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_wrong_payload_type(self):
        worker_com = self.worker_com
        self._create_tasks(2)
        worker_com.put(
            Message(_task_ident_from_idx(1), TaskExecuted(WORKER1_PID))
        )
        worker_com.put(
            Message(_task_ident_from_idx(1), "definitely not a payload")
        )
        await async_sleep(0.2)
        await self.scheduler._receive_messages()
        task1_dto = self.scheduler.get_task(_task_ident_from_idx(1))
        task2_dto = self.scheduler.get_task(_task_ident_from_idx(2))
        self.assertEqual(
            TaskKillReason.INTERNAL_MESSAGING_ERROR, task1_dto.kill_requested
        )
        self.assertIsNone(task2_dto.kill_requested)

    @gen_test
    async def test_wrong_message_type(self):
        self._create_tasks(2)
        self.worker_com.put(
            Message(_task_ident_from_idx(1), TaskExecuted(WORKER1_PID))
        )
        self.worker_com.put("definitely not a message")
        await async_sleep(0.2)
        await self.scheduler._receive_messages()
        self.logger_mock.error.assert_called_once()

    @gen_test
    async def test_all_messages_consumed(self):
        task_num = 3
        self._create_tasks(task_num)
        for _ in range(3):
            for idx in range(1, task_num + 1):
                self.worker_com.put(
                    Message(
                        _task_ident_from_idx(idx),
                        ReportItem.error(CibUpgradeSuccessful()).to_dto(),
                    )
                )
        await async_sleep(0.2)
        await self.scheduler._receive_messages()
        self.assertEqual(0, self.worker_com.qsize())


class ScheduleTasksTest(SchedulerBaseAsyncTestCase):
    @gen_test
    async def test_empty_created_task_index(self):
        await self.scheduler._schedule_tasks()

    @gen_test
    async def test_normal_run(self):
        task_num = 4
        self._create_tasks(task_num)
        await self.scheduler._schedule_tasks()
        for task_ident in [
            _task_ident_from_idx(i) for i in range(1, task_num + 1)
        ]:
            self.assertEqual(
                TaskState.QUEUED, self.scheduler.get_task(task_ident).state
            )
        self.assertFalse(self.scheduler._created_tasks_index)

    @gen_test
    async def test_task_not_in_task_register(self):
        self._create_tasks(3)
        tasks = list(self.scheduler._task_register.values())
        del self.scheduler._task_register[_task_ident_from_idx(1)]
        await self.scheduler._schedule_tasks()
        self.logger_mock.error.assert_called_once()
        self.mp_pool_mock.apply_async.assert_has_calls(
            [
                mock.call(
                    func=task_executor, args=[tasks[1].to_worker_command()],
                ),
                mock.call(
                    func=task_executor, args=[tasks[2].to_worker_command()],
                ),
            ]
        )

    @gen_test
    async def test_killed_task(self):
        self._create_tasks(3)
        tasks = list(self.scheduler._task_register.values())
        self.scheduler.kill_task(_task_ident_from_idx(2))
        await self.scheduler._schedule_tasks()
        deleted_task = self.scheduler.get_task(_task_ident_from_idx(2))
        self.assertEqual(
            TaskFinishType.UNFINISHED, deleted_task.task_finish_type
        )
        self.assertEqual(TaskState.CREATED, deleted_task.state)
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task(_task_ident_from_idx(1)).state,
        )
        self.assertEqual(
            TaskState.QUEUED,
            self.scheduler.get_task(_task_ident_from_idx(3)).state,
        )
        self.mp_pool_mock.apply_async.assert_has_calls(
            [
                mock.call(
                    func=task_executor, args=[tasks[0].to_worker_command()],
                ),
                mock.call(
                    func=task_executor, args=[tasks[2].to_worker_command()],
                ),
            ]
        )
