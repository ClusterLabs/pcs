from collections import Counter
import logging
import multiprocessing as mp

from dataclasses import dataclass
from datetime import datetime
from unittest import mock, TestCase
from tornado.testing import AsyncTestCase

from pcs.daemon.async_tasks import scheduler
from pcs.common.async_tasks.dto import CommandDto
from pcs.common.reports.item import ReportItemMessage
from pcs.common.reports.types import MessageCode

DATETIME_NOW = datetime(2020, 2, 20, 20, 20, 20, 20)


@dataclass(frozen=True)
class StubReportItem(ReportItemMessage):
    """Use this class to test report handling"""

    _code = MessageCode("REPORT_STUB")

    @property
    def message(self) -> str:
        return "This is a report item used for testing."


class SchedulerFake:
    """
    Scheduler for testing

    This class contains a scheduler that is suitable for use in tier0 tests -
    - it doesn't create new processes and contains mocks for easy testing, it
    should be used with AsyncTestCase or TestCase
    """

    scheduler = None
    worker_com = None
    mp_pool_mock = None
    logger_mock = None

    def prepare_scheduler(self):
        self.logger_mock = (
            mock.patch(
                "pcs.daemon.async_tasks.scheduler.setup_scheduler_logger",
                spec=logging.Logger,
            )
            .start()
            .return_value
        )
        # We can patch Queue here because it is NOT shared between tests
        self.worker_com = mp.Queue()
        # Manager has to be mocked because it creates a new process
        mock.patch(
            "multiprocessing.Manager"
        ).start().return_value.Queue.return_value = self.worker_com
        self.mp_pool_mock = (
            mock.patch("multiprocessing.Pool", spec=mp.Pool)
            .start()
            .return_value
        ) = mock.Mock()
        # This might be needed when logger is called by get_logger, but is it?
        self.scheduler = scheduler.Scheduler()

    def _create_tasks(self, count, start_from=0):
        """Creates tasks with task_ident from id0 to idN"""
        for i in range(start_from, count + start_from):
            with mock.patch("uuid.uuid4") as mock_uuid:
                mock_uuid().hex = f"id{i}"
                self.scheduler.new_task(CommandDto(f"command {i}", {}))


class SchedulerBaseTestCase(SchedulerFake, TestCase):
    def setUp(self):
        SchedulerFake.prepare_scheduler(self)
        super().setUp()
        self.addCleanup(mock.patch.stopall)


class SchedulerBaseAsyncTestCase(SchedulerFake, AsyncTestCase):
    def setUp(self):
        SchedulerFake.prepare_scheduler(self)
        super().setUp()
        self.addCleanup(mock.patch.stopall)


class AssertTaskStatesMixin:
    def assert_task_state_counts_equal(
        self, created, queued, executed, finished
    ):
        # pylint: disable=protected-access
        # Cannot use public method get_task because it deletes finished tasks
        state_counts = Counter(
            [task.state.name for task in self.scheduler._task_register.values()]
        )
        self.assertEqual(created, len(self.scheduler._created_tasks_index))
        self.assertEqual(created, state_counts["CREATED"])
        self.assertEqual(queued, state_counts["QUEUED"])
        self.assertEqual(executed, state_counts["EXECUTED"])
        self.assertEqual(finished, state_counts["FINISHED"])


class MockDateTimeNowMixin:
    """Capability to set up a mock of datetime.now() function in a TestCase"""

    def _init_mock_datetime_now(self):
        # Trying to shorten this is a really funny game
        # We can't patch datetime.datetime.now because builtins are immutable
        mock_datetime = mock.patch("datetime.datetime")
        self.addCleanup(mock_datetime.stop)
        mock_datetime = mock_datetime.start()
        mock_datetime.now = mock.Mock()
        mock_datetime.now.return_value = DATETIME_NOW
        return mock_datetime.now


class MockOsKillMixin:
    """Capability to set up a mock of os.kill() function in a TestCase"""

    def _init_mock_os_kill(self):
        mock_os_kill = mock.patch("os.kill")
        self.addCleanup(mock_os_kill.stop)
        return mock_os_kill.start()
