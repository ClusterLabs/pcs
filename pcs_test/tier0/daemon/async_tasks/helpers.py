import logging
import multiprocessing as mp
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from queue import Queue
from unittest import (
    IsolatedAsyncioTestCase,
    mock,
)

from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
)
from pcs.common.async_tasks.types import TaskState
from pcs.common.reports.item import ReportItemMessage
from pcs.common.reports.types import MessageCode
from pcs.daemon.async_tasks import scheduler
from pcs.daemon.async_tasks.task import TaskConfig
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser

DATETIME_NOW = datetime(2020, 2, 20, 20, 20, 20, 20)
AUTH_USER = AuthUser("username", ("group1", "group2"))
ANOTHER_AUTH_USER = AuthUser("different user name", ["no group"])


class PermissionsCheckerMock:
    def __init__(self, permissions):
        self._permissions = permissions

    def is_authorized(self, auth_user, access):
        return access not in self._permissions.get(auth_user, tuple())


@dataclass(frozen=True)
class StubReportItem(ReportItemMessage):
    """Use this class to test report handling"""

    _code = MessageCode("REPORT_STUB")

    @property
    def message(self) -> str:
        return "This is a report item used for testing."


class SchedulerTestWrapper:
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
    logging_queue = None

    def prepare_scheduler(self):
        # Instance attributes are not created in the mock, this includes handler
        # list which is needed by QueueListener
        self.logger_mock = mock.patch(
            "pcs.daemon.async_tasks.scheduler.pcsd_logger",
            spec=logging.Logger,
            handlers=[],
        ).start()
        # We can patch Queue here because it is NOT shared between tests
        # self.worker_com = mp.Queue()
        self.worker_com = Queue()
        self.logging_queue = Queue()
        # Manager has to be mocked because it creates a new process
        # There are two queue calls, first is for worker message queue, second
        # is for the logging queue
        mock.patch(
            "multiprocessing.Manager"
        ).start().return_value.Queue.side_effect = [
            self.worker_com,
            self.logging_queue,
            # mp.Queue(),
        ]
        self.mp_pool_mock = mock.patch(
            "multiprocessing.Pool", spec=mp.Pool
        ).start().return_value = mock.Mock()
        # This might be needed when logger is called by get_logger, but is it?
        self.scheduler = scheduler.Scheduler(
            scheduler.SchedulerConfig(
                worker_count=1,
                worker_reset_limit=2,
                task_config=TaskConfig(deletion_timeout=0),
            )
        )

    def _create_tasks(self, count, start_from=0):
        """Creates tasks with task_ident from id0 to idN"""
        for i in range(start_from, count + start_from):
            with mock.patch(
                "pcs.daemon.async_tasks.scheduler.get_unique_uuid"
            ) as mock_uuid:
                mock_uuid.return_value = f"id{i}"
                self.scheduler.new_task(
                    Command(
                        CommandDto(
                            f"command {i}",
                            {},
                            CommandOptionsDto(request_timeout=None),
                        )
                    ),
                    AUTH_USER,
                )


class SchedulerBaseAsyncTestCase(SchedulerTestWrapper, IsolatedAsyncioTestCase):
    def setUp(self):
        SchedulerTestWrapper.prepare_scheduler(self)
        super().setUp()
        self.addCleanup(mock.patch.stopall)


class AssertTaskStatesMixin:
    def assert_task_state_counts_equal(
        self, created, queued, executed, finished
    ):
        # pylint: disable=protected-access
        # Cannot use public method get_task because it deletes finished tasks
        state_counts = Counter(
            [task.state for task in self.scheduler._task_register.values()]
        )
        self.assertEqual(
            created,
            state_counts[TaskState.CREATED],
            "Expected {0} CREATED tasks.".format(
                state_counts[TaskState.CREATED]
            ),
        )
        self.assertEqual(
            queued,
            state_counts[TaskState.QUEUED],
            "Expected {0} QUEUED tasks.".format(state_counts[TaskState.QUEUED]),
        )
        self.assertEqual(
            executed,
            state_counts[TaskState.EXECUTED],
            "Expected {0} EXECUTED tasks.".format(
                state_counts[TaskState.EXECUTED]
            ),
        )
        self.assertEqual(
            finished,
            state_counts[TaskState.FINISHED],
            "Expected {0} FINISHED tasks.".format(
                state_counts[TaskState.FINISHED]
            ),
        )


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
