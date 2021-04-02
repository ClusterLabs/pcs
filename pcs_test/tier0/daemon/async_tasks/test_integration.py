from datetime import timedelta
from logging import Logger
from multiprocessing import Queue
from unittest import mock
from tornado.testing import gen_test

import pcs.settings as settings
import pcs.daemon.async_tasks.worker as worker

from pcs.common.async_tasks.dto import CommandDto
from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskState,
    TaskKillReason,
)
from pcs.common.reports.dto import ReportItemDto
from pcs.daemon.async_tasks.messaging import Message, TaskExecuted, TaskFinished
from pcs.daemon.async_tasks.report_proc import WorkerReportProcessor
from pcs.daemon.async_tasks.scheduler import TaskNotFoundError
from pcs.daemon.async_tasks.worker import task_executor

from .dummy_commands import RESULT, test_command_map
from .helpers import (
    DATETIME_NOW,
    AssertTaskStatesMixin,
    MockDateTimeNowMixin,
    MockOsKillMixin,
    SchedulerBaseAsyncTestCase,
)

worker.worker_com = Queue()  # patched at runtime


class IntegrationBaseTestCase(SchedulerBaseAsyncTestCase):
    async def perform_actions(self, message_count):
        # pylint: disable=protected-access
        """
        USE THIS FUNCTION IN TIER0 TESTS instead of the scheduler function with
        the same name to guarantee consistency between test runs. This function
        guarantees that worker_com is emptied in one call, removing variability
        between test runs.
        """
        received = await self.scheduler.perform_actions()
        while received < message_count:
            received += await self.scheduler._receive_messages()

    def execute_tasks(self, task_ident_list):
        """Simulates process pool workers launching tasks

        Emits one message into worker_com queue per task. Process IDs of these
        tasks are task_idents stripped of the "id" prefix.
        :param task_ident_list: Contains task_idents of tasks to execute
        """
        for task_ident in task_ident_list:
            self.worker_com.put_nowait(
                Message(task_ident, TaskExecuted(int(task_ident[2:])))
            )

    def finish_tasks(
        self, task_ident_list, finish_type=TaskFinishType.SUCCESS, result=None
    ):
        """Simulates process pool workers handing over results when task ends

        Emits one message into worker_com queue per task
        :param task_ident_list: Contains task_idents of tasks that finished
        :param finish_type: Task finish type for all task_idents
        :param result: Return value of an executed function for all task_idents
        """
        for task_ident in task_ident_list:
            self.worker_com.put_nowait(
                Message(task_ident, TaskFinished(finish_type, result))
            )


class StateChangeTest(AssertTaskStatesMixin, IntegrationBaseTestCase):
    """Tests that check that task state is correct at each stage

    Task state changes prompted by errors or other special events are tested
    in the specific classes, these are just baseline tests for how everything
    should work in an ideal (error-free) scenario.
    """

    @gen_test
    async def test_created_from_empty(self):
        self._create_tasks(5)
        self.assert_task_state_counts_equal(5, 0, 0, 0)

    @gen_test
    async def test_created_on_top_of_existing(self):
        self._create_tasks(5)
        await self.perform_actions(0)
        """ NOTE: code replaced by execute_tasks, would be more complicated for 
        non-contiguos task_ident sets
        for i in range(worker_count):
            self.worker_com.put_nowait(Message(f"id{i}", TaskExecuted(i)))
        """
        self.execute_tasks(["id0", "id1", "id2"])
        await self.perform_actions(3)
        self._create_tasks(2, start_from=5)
        # 3/5 were executed, remaining are queued, 2 new arrived
        self.assert_task_state_counts_equal(2, 2, 3, 0)

    @gen_test
    async def test_created_to_scheduled(self):
        self._create_tasks(4)
        await self.perform_actions(0)
        self.assert_task_state_counts_equal(0, 4, 0, 0)

    @gen_test
    async def test_scheduled_to_executed(self):
        self._create_tasks(4)
        await self.perform_actions(0)
        # Tasks are scheduled, now 2 will start executing
        self.execute_tasks(["id0", "id1"])
        await self.perform_actions(2)
        self.assert_task_state_counts_equal(0, 2, 2, 0)

    @gen_test
    async def test_executed_to_finished(self):
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        self.finish_tasks(["id0"])
        await self.perform_actions(1)
        self.assert_task_state_counts_equal(0, 0, 0, 1)

    # NOTE: This was the original test which is now split up into other tests
    """
    @gen_test
    async def test_complex_scenario1(self):
        # Create more tasks that can be executed at once
        worker_count = 4
        task_count = 5

        assert worker_count >= 2  # minimum of 2 workers for this test
        assert task_count == 5  # changing this will break the test

        self._create_tasks(task_count)
        self.assert_task_state_counts_equal(task_count, 0, 0, 0)

        # First set of tasks is going to execute
        self.execute_tasks(["id0", "id1", "id2", "id3"])
        await self.perform_actions(worker_count)
        self.assertEqual(task_count, self.mp_pool_mock.apply_async.call_count)

        # One more task arrives
        task_count += 1
        with mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid().hex = "id5"
            self.scheduler.new_task(CommandDto("command 5", {}))
        """ """state_counts = count_task_states(self.scheduler)
        self.assertEqual(1, state_counts["created"])
        self.assertEqual(task_count - worker_count - 1, state_counts["queued"])
        self.assertEqual(worker_count, state_counts["executed"])
        self.assertEqual(0, state_counts["finished"])""" """

        # First two tasks finish, two are still running, the new task is queued
        # and scheduled
        """ """self.worker_com.put_nowait(
            Message("id0", TaskFinished(TaskFinishType.SUCCESS, None))
        )
        self.worker_com.put_nowait(
            Message("id1", TaskFinished(TaskFinishType.SUCCESS, None))
        )""" """
        self.finish_tasks(["id0", "id1"])
        await self.perform_actions(2)
        self.assertEqual(task_count, self.mp_pool_mock.apply_async.call_count)
        """ """state_counts = count_task_states(self.scheduler)
        self.assertEqual(0, state_counts["created"])
        self.assertEqual(task_count - worker_count, state_counts["queued"])
        # 2 finished, 2 running, workers are unused until next perform_actions
        self.assertEqual(worker_count - 2, state_counts["executed"])
        self.assertEqual(2, state_counts["finished"])""" """
        self.assert_task_state_counts_equal(
            0, task_count - worker_count, worker_count - 2, 2
        )
 
        # Other two tasks finish, all workers are idling until perform_actions
        """ """self.worker_com.put_nowait(
            Message("id2", TaskFinished(TaskFinishType.SUCCESS, None))
        )
        self.worker_com.put_nowait(
            Message("id3", TaskFinished(TaskFinishType.SUCCESS, None))
        )""" """
        self.finish_tasks(["id2", "id3"])
        """ """self.worker_com.put_nowait(Message("id4", TaskExecuted(4)))
        self.worker_com.put_nowait(Message("id5", TaskExecuted(5)))""" """
        self.execute_tasks(["id4", "id5"])
        # Only two workers pick up new tasks, messages are handled after
        # scheduling so the other two workers will only start
        await self.perform_actions(4)
        """ """state_counts = count_task_states(self.scheduler)
        self.assertEqual(0, state_counts["created"])
        self.assertEqual(0, state_counts["queued"])
        self.assertEqual(2, state_counts["executed"])
        self.assertEqual(4, state_counts["finished"])""" """
        self.assert_task_state_counts_equal(0, 0, 2, 4)

        # Finish all running tasks
        """ """self.worker_com.put_nowait(
            Message("id4", TaskFinished(TaskFinishType.SUCCESS, None))
        )
        self.worker_com.put_nowait(
            Message("id5", TaskFinished(TaskFinishType.SUCCESS, None))
        )""" """
        self.finish_tasks(["id4", "id5"])
        await self.perform_actions(2)
        """ """state_counts = count_task_states(self.scheduler)
        self.assertEqual(0, state_counts["created"])
        self.assertEqual(0, state_counts["queued"])
        self.assertEqual(0, state_counts["executed"])
        self.assertEqual(6, state_counts["finished"])""" """
        self.assert_task_state_counts_equal(0, 0, 0, 6)"""


class GarbageCollectionTests(
    MockOsKillMixin, MockDateTimeNowMixin, IntegrationBaseTestCase
):
    """Testing garbage collection and timeout behavior

    These tests focus on the correct function of the garbage collector and
    garbage hunting functions.
    """

    def setUp(self):
        super().setUp()
        # This mock already sets current time to DATETIME_NOW
        self.mock_datetime_now = self._init_mock_datetime_now()
        self.mock_os_kill = self._init_mock_os_kill()

    async def _run_gc_and_assert_state(
        self, timeout_s, task_finish_type, task_kill_reason
    ):
        self.mock_datetime_now.return_value = DATETIME_NOW + timedelta(
            seconds=timeout_s + 1
        )
        await self.perform_actions(0)
        task_info = self.scheduler.get_task("id0")
        self.assertEqual(task_finish_type, task_info.task_finish_type)
        self.assertEqual(task_kill_reason, task_info.kill_reason)
        if task_kill_reason is not None:
            with self.assertRaises(TaskNotFoundError):
                self.scheduler.get_task("id0")

    @gen_test
    async def test_get_task_removes_finished(self):
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        self.finish_tasks(["id0"])
        await self.perform_actions(1)
        self.scheduler.get_task("id0")
        with self.assertRaises(TaskNotFoundError):
            self.scheduler.get_task("id0")

    @gen_test
    async def test_created_defunct_timeout(self):
        # Nothing should happen, created tasks can't be defunct
        self._create_tasks(1)
        await self._run_gc_and_assert_state(
            settings.task_unresponsive_timeout_seconds,
            TaskFinishType.UNFINISHED,
            task_kill_reason=None,
        )

    @gen_test
    async def test_scheduled_defunct_timeout(self):
        # Nothing should happen, scheduled tasks can't be defunct
        self._create_tasks(1)
        await self.perform_actions(0)
        await self._run_gc_and_assert_state(
            settings.task_unresponsive_timeout_seconds,
            TaskFinishType.UNFINISHED,
            task_kill_reason=None,
        )

    @gen_test
    async def test_executed_defunct_timeout(self):
        # Task should be killed
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        await self._run_gc_and_assert_state(
            settings.task_unresponsive_timeout_seconds,
            TaskFinishType.KILL,
            TaskKillReason.COMPLETION_TIMEOUT,
        )

    @gen_test
    async def test_finished_defunct_timeout(self):
        # Interesting point of order - since the abandoned timeout is smaller
        # than defunct timeout and task is being examined in FINISHED state,
        # this test will mark the task as abandoned but not defunct
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        self.finish_tasks(["id0"])
        await self.perform_actions(1)
        await self._run_gc_and_assert_state(
            settings.task_unresponsive_timeout_seconds,
            TaskFinishType.KILL,
            TaskKillReason.ABANDONED,
        )

    @gen_test
    async def test_created_abandoned_timeout(self):
        self._create_tasks(1)
        await self._run_gc_and_assert_state(
            settings.task_abandoned_timeout_seconds,
            TaskFinishType.UNFINISHED,
            task_kill_reason=None,
        )

    @gen_test
    async def test_scheduled_abandoned_timeout(self):
        self._create_tasks(1)
        await self.perform_actions(0)
        await self._run_gc_and_assert_state(
            settings.task_abandoned_timeout_seconds,
            TaskFinishType.UNFINISHED,
            task_kill_reason=None,
        )

    @gen_test
    async def test_executed_abandoned_timeout(self):
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        await self._run_gc_and_assert_state(
            settings.task_abandoned_timeout_seconds,
            TaskFinishType.UNFINISHED,
            task_kill_reason=None,
        )

    @gen_test
    async def test_finished_abandoned_timeout(self):
        self._create_tasks(1)
        await self.perform_actions(0)
        self.execute_tasks(["id0"])
        await self.perform_actions(1)
        self.finish_tasks(["id0"])
        await self.perform_actions(1)
        await self._run_gc_and_assert_state(
            settings.task_abandoned_timeout_seconds,
            TaskFinishType.KILL,
            TaskKillReason.ABANDONED,
        )


class TaskResultsTests(IntegrationBaseTestCase):
    """These tests check all task outcomes with real task_executor

    These test go one level deeper to include task_executor and test its
    behavior. All possible task outcomes are tested.
    """

    def setUp(self):
        super().setUp()
        self.addCleanup(mock.patch.stopall)
        mock.patch(
            "pcs.daemon.async_tasks.worker.command_map", test_command_map
        ).start()
        mock.patch(
            "pcs.daemon.async_tasks.worker.getLogger", spec=Logger
        ).start()
        mock.patch(
            "pcs.daemon.async_tasks.worker.worker_com",
            self.worker_com,
        ).start()
        lib_env_mock = (
            mock.patch("pcs.daemon.async_tasks.worker.LibraryEnvironment")
            .start()
            .return_value
        )
        lib_env_mock.report_processor = WorkerReportProcessor(
            self.worker_com, "id0"
        )

    def _send_report_mocks(self, task_ident, count):
        """Emulate sending reports from the worker

        Returns a list of mock references for inspecting usage and mock reports
        are sent into the worker_com queue
        """
        mock_list = []
        for i in range(count):
            mock_list[i] = mock.Mock(spec=ReportItemDto)
            self.worker_com.put_nowait(Message(task_ident, mock_list[i]))
        return mock_list

    @gen_test
    async def test_task_successful_no_result_with_reports(self):
        # How is no result different from a None return value in DTO?
        # Functions without return values also return None - should we
        # distinguish between cases of ex/implicitly returned None
        with mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid().hex = "id0"
            self.scheduler.new_task(CommandDto("success_with_reports", {}))
        await self.perform_actions(0)
        # This task sends one report and returns immediately, task_executor
        # sends two messages - TaskExecuted and TaskFinished
        task_executor(self.scheduler._task_register["id0"].to_worker_command())
        await self.perform_actions(3)

        task_info = self.scheduler.get_task("id0")
        self.assertEqual(1, len(task_info.reports))
        self.assertEqual(TaskFinishType.SUCCESS, task_info.task_finish_type)
        self.assertIsNone(task_info.result)

    @gen_test
    async def test_task_successful_with_result(self):
        with mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid().hex = "id0"
            self.scheduler.new_task(CommandDto("success", {}))
        await self.perform_actions(0)
        # This task sends no reports and returns immediately, task_executor
        # sends two messages - TaskExecuted and TaskFinished
        task_executor(self.scheduler._task_register["id0"].to_worker_command())
        await self.perform_actions(2)

        task_info = self.scheduler.get_task("id0")
        self.assertEqual(0, len(task_info.reports))
        self.assertEqual(TaskFinishType.SUCCESS, task_info.task_finish_type)
        self.assertEqual(RESULT, task_info.result)

    @gen_test
    async def test_task_error(self):
        with mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid().hex = "id0"
            self.scheduler.new_task(CommandDto("lib_exc", {}))
        await self.perform_actions(0)
        # This task immediately raises a LibraryException and executor detects
        # that as an error, sends two messages - TaskExecuted and TaskFinished
        task_executor(self.scheduler._task_register["id0"].to_worker_command())
        await self.perform_actions(2)

        task_info = self.scheduler.get_task("id0")
        self.assertEqual(0, len(task_info.reports))
        self.assertEqual(TaskFinishType.FAIL, task_info.task_finish_type)
        self.assertIsNone(task_info.result)

    @gen_test
    async def test_task_unhandled_exception(self):
        with mock.patch("uuid.uuid4") as mock_uuid:
            mock_uuid().hex = "id0"
            self.scheduler.new_task(CommandDto("unhandled_exc", {}))
        await self.perform_actions(0)
        # This task immediately raises a a plain Exception and executor catches
        # and logs it accordingly
        task_executor(self.scheduler._task_register["id0"].to_worker_command())
        await self.perform_actions(2)

        task_info = self.scheduler.get_task("id0")
        self.assertEqual(0, len(task_info.reports))
        self.assertEqual(
            TaskFinishType.UNHANDLED_EXCEPTION, task_info.task_finish_type
        )
        self.assertIsNone(task_info.result)


class KillTaskTests(
    MockOsKillMixin, AssertTaskStatesMixin, IntegrationBaseTestCase
):
    """Tests killing tasks at various stages

    Testing the killing functionality exposed through the public API to the user
    """

    def setUp(self):
        super().setUp()
        self.mock_os_kill = self._init_mock_os_kill()

    def assert_end_state(self):
        task_info_killed = self.scheduler.get_task("id0")
        self.assertEqual(TaskState.FINISHED, task_info_killed.state)
        self.assertEqual(TaskFinishType.KILL, task_info_killed.task_finish_type)
        self.assertEqual(TaskKillReason.USER, task_info_killed.kill_reason)

        task_info_alive = self.scheduler.get_task("id1")
        self.assertEqual(
            TaskFinishType.UNFINISHED, task_info_alive.task_finish_type
        )
        self.assertIsNone(task_info_alive.kill_reason)

    @gen_test
    async def test_kill_created(self):
        self._create_tasks(2)
        self.scheduler.kill_task("id0")
        # Kill_task doesn't produce any messages since the worker is killed by
        # the system
        await self.perform_actions(0)
        self.assert_task_state_counts_equal(0, 1, 0, 1)

        self.mock_os_kill.assert_not_called()
        self.assert_end_state()

    @gen_test
    async def test_kill_scheduled(self):
        self._create_tasks(2)
        await self.perform_actions(0)
        self.scheduler.kill_task("id0")
        self.execute_tasks(["id1"])
        await self.perform_actions(1)
        self.assert_task_state_counts_equal(0, 0, 1, 1)

        self.mock_os_kill.assert_not_called()
        self.assert_end_state()

    @gen_test
    async def test_kill_executed(self):
        self._create_tasks(2)
        await self.perform_actions(0)
        self.execute_tasks(["id0", "id1"])
        await self.perform_actions(2)
        self.scheduler.kill_task("id0")
        await self.perform_actions(0)
        self.assert_task_state_counts_equal(0, 0, 1, 1)

        self.mock_os_kill.assert_called_once()
        self.assert_end_state()

    @gen_test
    async def test_kill_finished(self):
        self._create_tasks(2)
        await self.perform_actions(0)
        self.execute_tasks(["id0", "id1"])
        await self.perform_actions(2)
        self.finish_tasks(["id0"])
        await self.perform_actions(1)
        self.scheduler.kill_task("id0")
        await self.perform_actions(0)
        self.assert_task_state_counts_equal(0, 0, 1, 1)

        self.mock_os_kill.assert_not_called()
        self.assert_end_state()
