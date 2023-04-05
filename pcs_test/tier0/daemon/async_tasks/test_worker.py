from multiprocessing import Queue
from unittest import (
    TestCase,
    mock,
)

from pcs.common import reports
from pcs.common.async_tasks import types
from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
)
from pcs.daemon.async_tasks.types import Command
from pcs.daemon.async_tasks.worker import executor
from pcs.daemon.async_tasks.worker.types import (
    Message,
    TaskExecuted,
    TaskFinished,
    WorkerCommand,
)

from .dummy_commands import (
    RESULT,
    test_command_map,
    test_legacy_api_commands,
)
from .helpers import (
    AUTH_USER,
    MockOsKillMixin,
    PermissionsCheckerMock,
)

TASK_IDENT = "id0"
WORKER_PID = 2222
COMMAND_OPTIONS = CommandOptionsDto(request_timeout=None)


executor.worker_com = Queue()  # patched at runtime


@mock.patch(
    "pcs.daemon.async_tasks.worker.executor.COMMAND_MAP", test_command_map
)
@mock.patch(
    "pcs.daemon.async_tasks.worker.executor.LEGACY_API_COMMANDS",
    test_legacy_api_commands,
)
@mock.patch(
    "pcs.daemon.async_tasks.worker.executor.getLogger", mock.MagicMock()
)
@mock.patch(
    "pcs.daemon.async_tasks.worker.executor.PermissionsChecker",
    lambda _: PermissionsCheckerMock({}),
)
@mock.patch("os.getpid")
class TestExecutor(MockOsKillMixin, TestCase):
    """
    Tests the test_executor function

    Every test needs its own queue to avoid mixing messages from other tests
    because tests are running concurrently
    """

    def setUp(self) -> None:
        super().setUp()
        # Os.kill is used to pause the worker and we do not want to pause tests
        self._init_mock_os_kill()

    def _get_payload_from_worker_com(self, worker_com):
        message = worker_com.get()
        self.assertIsInstance(message, Message)
        return message.payload

    def _assert_task_executed(self, worker_com):
        payload = self._get_payload_from_worker_com(worker_com)
        self.assertIsInstance(payload, TaskExecuted)
        self.assertEqual(WORKER_PID, payload.worker_pid)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_successful_run(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(CommandDto("success", {}, COMMAND_OPTIONS)),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(types.TaskFinishType.SUCCESS, payload.task_finish_type)
        self.assertEqual(RESULT, payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_unsuccessful_run(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(CommandDto("lib_exc", {}, COMMAND_OPTIONS)),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(types.TaskFinishType.FAIL, payload.task_finish_type)
        self.assertIsNone(payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_unsuccessful_run_additional_reports(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(
                    CommandDto(
                        "lib_exc_reports",
                        {},
                        COMMAND_OPTIONS,
                    )
                ),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. Report from the LibraryError exception
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, reports.ReportItemDto)
        # 3. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(types.TaskFinishType.FAIL, payload.task_finish_type)
        self.assertIsNone(payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_unhandled_exception(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(CommandDto("unhandled_exc", {}, COMMAND_OPTIONS)),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(
            types.TaskFinishType.UNHANDLED_EXCEPTION, payload.task_finish_type
        )
        self.assertIsNone(payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_legacy_api_command_fails_when_not_allowed(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(CommandDto("success_api_v1", {}, COMMAND_OPTIONS)),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. Report from the LibraryError exception
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, reports.ReportItemDto)
        self.assertEqual(payload.message.code, reports.codes.COMMAND_UNKNOWN)
        # 3. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(types.TaskFinishType.FAIL, payload.task_finish_type)

    @mock.patch("pcs.daemon.async_tasks.worker.executor.worker_com", Queue())
    def test_legacy_api_command_succeeds_when_allowed(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        executor.task_executor(
            WorkerCommand(
                TASK_IDENT,
                Command(
                    CommandDto("success_api_v1", {}, COMMAND_OPTIONS),
                    is_legacy_command=True,
                ),
                AUTH_USER,
            )
        )
        # 1. TaskExecuted
        self._assert_task_executed(executor.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(executor.worker_com)
        self.assertIsInstance(payload, TaskFinished)
        self.assertEqual(types.TaskFinishType.SUCCESS, payload.task_finish_type)
        self.assertEqual(RESULT, payload.result)
