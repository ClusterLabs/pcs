from multiprocessing import Queue
from unittest import mock, TestCase

import pcs.common.async_tasks.types as types
import pcs.daemon.async_tasks.messaging as messaging
import pcs.daemon.async_tasks.worker as worker

from pcs.common.async_tasks.dto import CommandDto
from pcs.common.reports import ReportItem, ReportItemDto
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.lib.errors import LibraryError

TASK_IDENT = "00000000000000000123456789abcdef"
WORKER_PID = 2222
RESULT = "I'm done."

worker.worker_com = Queue()  # patched later

# These functions use _ to discard environment that is hardcoded in
# task_executor because all library functions use it
def dummy_workload(_) -> str:
    return RESULT


def dummy_workload_unhandled_exception(_) -> None:
    raise Exception("Whoa, something happened to this task!")


def dummy_workload_lib_exception(_) -> None:
    raise LibraryError()


def dummy_workload_lib_exception_reports(_) -> None:
    raise LibraryError(ReportItem.error(CibUpgradeSuccessful()))


test_command_map = {
    "success": dummy_workload,
    "unhandled_exc": dummy_workload_unhandled_exception,
    "lib_exc": dummy_workload_lib_exception,
    "lib_exc_reports": dummy_workload_lib_exception_reports,
}


@mock.patch("pcs.daemon.async_tasks.worker.command_map", test_command_map)
@mock.patch("pcs.daemon.async_tasks.worker.getLogger", mock.MagicMock())
@mock.patch("os.getpid")
class TestExecutor(TestCase):
    """
    Tests the test_executor function

    Every test needs its own queue to avoid mixing messages from other tests
    because tests are running concurrently
    """

    def _get_payload_from_worker_com(self, worker_com):
        message = worker_com.get()
        self.assertIsInstance(message, messaging.Message)
        return message.payload

    def _assert_task_executed(self, worker_com):
        payload = self._get_payload_from_worker_com(worker_com)
        self.assertIsInstance(payload, messaging.TaskExecuted)
        self.assertEqual(WORKER_PID, payload.worker_pid)

    @mock.patch("pcs.daemon.async_tasks.worker.worker_com", Queue())
    def test_successful_run(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        worker.task_executor(
            worker.WorkerCommand(TASK_IDENT, CommandDto("success", {}))
        )
        # 1. TaskExecuted
        self._assert_task_executed(worker.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertIsInstance(payload, messaging.TaskFinished)
        self.assertEqual(types.TaskFinishType.SUCCESS, payload.task_finish_type)
        self.assertEqual(RESULT, payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.worker_com", Queue())
    def test_unsuccessful_run(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        worker.task_executor(
            worker.WorkerCommand(TASK_IDENT, CommandDto("lib_exc", {}))
        )
        # 1. TaskExecuted
        self._assert_task_executed(worker.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertIsInstance(payload, messaging.TaskFinished)
        self.assertEqual(types.TaskFinishType.FAIL, payload.task_finish_type)
        self.assertEqual(None, payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.worker_com", Queue())
    def test_unsuccessful_run_additional_reports(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        worker.task_executor(
            worker.WorkerCommand(TASK_IDENT, CommandDto("lib_exc_reports", {}))
        )
        # 1. TaskExecuted
        self._assert_task_executed(worker.worker_com)
        # 2. Report from the LibraryError exception
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertIsInstance(payload, ReportItemDto)
        # 3. TaskFinished
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertIsInstance(payload, messaging.TaskFinished)
        self.assertEqual(types.TaskFinishType.FAIL, payload.task_finish_type)
        self.assertEqual(None, payload.result)

    @mock.patch("pcs.daemon.async_tasks.worker.worker_com", Queue())
    def test_unhandled_exception(self, mock_getpid):
        mock_getpid.return_value = WORKER_PID
        worker.task_executor(
            worker.WorkerCommand(TASK_IDENT, CommandDto("unhandled_exc", {}))
        )
        # 1. TaskExecuted
        self._assert_task_executed(worker.worker_com)
        # 2. TaskFinished
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertIsInstance(payload, messaging.TaskFinished)
        self.assertEqual(
            types.TaskFinishType.UNHANDLED_EXCEPTION, payload.task_finish_type
        )
        self.assertEqual(None, payload.result)
