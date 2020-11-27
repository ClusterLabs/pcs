from multiprocessing import Queue
from unittest import mock, TestCase

import pcs.common.async_tasks.types as types
import pcs.daemon.async_tasks.messaging as messaging
import pcs.daemon.async_tasks.worker as worker

from pcs.common.async_tasks.dto import CommandDto
from pcs.common.reports import ReportItemDto
from .test_command_mapping import test_command_map

TASK_IDENT = "00000000000000000123456789abcdef"
WORKER_PID = 2222

worker.worker_com = Queue()  # preventing parallel tests


@mock.patch("pcs.daemon.async_tasks.worker.command_map", test_command_map)
@mock.patch("os.getpid")
class TestExecutor(TestCase):
    """
    Tests the test_executor function

    Every test needs its own queue to avoid mixing messages from other tests
    because tests are running concurrently
    """

    def _get_payload_from_worker_com(self, worker_com):
        message = worker_com.get()
        self.assertTrue(isinstance(message, messaging.Message))
        return message.payload

    def _assert_task_executed(self, worker_com):
        payload = self._get_payload_from_worker_com(worker_com)
        self.assertTrue(isinstance(payload, messaging.TaskExecuted))
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
        self.assertTrue(isinstance(payload, messaging.TaskFinished))
        self.assertEqual(types.TaskFinishType.SUCCESS, payload.task_finish_type)
        self.assertEqual("I'm done.", payload.result)

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
        self.assertTrue(isinstance(payload, messaging.TaskFinished))
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
        self.assertTrue(isinstance(payload, ReportItemDto))
        # 3. TaskFinished
        payload = self._get_payload_from_worker_com(worker.worker_com)
        self.assertTrue(isinstance(payload, messaging.TaskFinished))
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
        self.assertTrue(isinstance(payload, messaging.TaskFinished))
        self.assertEqual(
            types.TaskFinishType.UNHANDLED_EXCEPTION, payload.task_finish_type
        )
        self.assertEqual(None, payload.result)
