# pylint: disable=protected-access
from datetime import datetime, timedelta
from unittest import mock, TestCase

import pcs.common.async_tasks.types as types
import pcs.daemon.async_tasks.task as tasks
import pcs.daemon.async_tasks.messaging as messaging


from pcs.settings import (
    task_abandoned_timeout_seconds,
    task_unresponsive_timeout_seconds,
)
from pcs.common.async_tasks.dto import CommandDto
from pcs.common.reports import ReportItemDto

TASK_IDENT = "00000000000000000123456789abcdef"
DATETIME_NOW = datetime(2020, 2, 20, 20, 20, 20, 20)
TEST_TIMEOUT_S = 10
DATETIME_BEFORE_TIMEOUT = DATETIME_NOW - timedelta(seconds=TEST_TIMEOUT_S / 2)
DATETIME_AFTER_TIMEOUT = DATETIME_NOW - timedelta(seconds=TEST_TIMEOUT_S + 1)
WORKER_PID = 2222


class MockDateTimeNowMixin:
    @staticmethod
    def _prepare_mock_datetime_now(mock_datetime):
        mock_datetime.now = mock.Mock()
        mock_datetime.now.return_value = DATETIME_NOW


class TaskBaseTestCase(TestCase):
    def setUp(self):
        self.task = tasks.Task(TASK_IDENT, CommandDto("command", {}))


@mock.patch("datetime.datetime")
class TestReceiveMessage(TaskBaseTestCase, MockDateTimeNowMixin):
    def test_report(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        payload = mock.MagicMock(ReportItemDto)
        message = messaging.Message(TASK_IDENT, payload)
        self.task.receive_message(message)
        self.assertEqual([payload], self.task.to_dto().reports)
        self.assertEqual(DATETIME_NOW, self.task._last_message_at)
        mock_datetime.now.assert_called_once()

    def test_task_executed(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        message = messaging.Message(
            TASK_IDENT, messaging.TaskExecuted(WORKER_PID)
        )
        self.task.receive_message(message)
        self.assertEqual(types.TaskState.EXECUTED, self.task.state)
        self.assertEqual(WORKER_PID, self.task._worker_pid)
        self.assertEqual(DATETIME_NOW, self.task._last_message_at)
        mock_datetime.now.assert_called_once()

    def test_task_finished(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        message = messaging.Message(
            TASK_IDENT,
            messaging.TaskFinished(types.TaskFinishType.SUCCESS, "result"),
        )
        self.task.receive_message(message)
        task_dto = self.task.to_dto()
        self.assertEqual(types.TaskState.FINISHED, task_dto.state)
        self.assertEqual(
            types.TaskFinishType.SUCCESS, task_dto.task_finish_type
        )
        self.assertEqual("result", task_dto.result)
        self.assertEqual(DATETIME_NOW, self.task._last_message_at)
        mock_datetime.now.assert_called_once()

    def test_unsupported_message_type(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        message = messaging.Message(TASK_IDENT, 3)
        with self.assertRaises(tasks.UnknownMessageError) as thrown_exc:
            self.task.receive_message(message)
        self.assertEqual(type(3).__name__, thrown_exc.exception.payload_type)
        mock_datetime.assert_not_called()


class TestRequestKill(TaskBaseTestCase):
    def test_kill_requested(self):
        self.task.request_kill(types.TaskKillReason.USER)
        self.assertEqual(
            types.TaskKillReason.USER, self.task.to_dto().kill_requested
        )
        self.assertTrue(self.task.is_kill_requested())

    def test_kill_not_requested(self):
        self.assertFalse(self.task.is_kill_requested())


@mock.patch("os.kill")
class TestKill(TaskBaseTestCase):
    def _assert_killed(self, mock_os_kill, start_state):
        self.task.state = start_state
        self.task.kill()
        task_dto = self.task.to_dto()
        mock_os_kill.assert_not_called()
        self.assertEqual(types.TaskState.FINISHED, task_dto.state)
        self.assertEqual(types.TaskFinishType.KILL, task_dto.task_finish_type)

    def test_kill_created(self, mock_os_kill):
        self._assert_killed(mock_os_kill, types.TaskState.CREATED)

    def test_kill_queued(self, mock_os_kill):
        self._assert_killed(mock_os_kill, types.TaskState.QUEUED)

    def test_kill_executed_worker_alive(self, mock_os_kill):
        message = messaging.Message(
            TASK_IDENT, messaging.TaskExecuted(WORKER_PID)
        )
        self.task.receive_message(message)
        self.task.kill()
        task_dto = self.task.to_dto()
        mock_os_kill.assert_called_once_with(WORKER_PID, 15)
        self.assertEqual(types.TaskState.FINISHED, task_dto.state)
        self.assertEqual(types.TaskFinishType.KILL, task_dto.task_finish_type)

    def test_kill_executed_worker_dead(self, mock_os_kill):
        message = messaging.Message(
            TASK_IDENT, messaging.TaskExecuted(WORKER_PID)
        )
        self.task.receive_message(message)
        mock_os_kill.raiseError.side_effect = ProcessLookupError()
        self.task.kill()
        task_dto = self.task.to_dto()
        mock_os_kill.assert_called_once_with(WORKER_PID, 15)
        self.assertEqual(types.TaskState.FINISHED, task_dto.state)
        self.assertEqual(types.TaskFinishType.KILL, task_dto.task_finish_type)

    def test_kill_finished(self, mock_os_kill):
        self._assert_killed(mock_os_kill, types.TaskState.FINISHED)


class TestGetLastTimestamp(TaskBaseTestCase, MockDateTimeNowMixin):
    def test_no_messages_created(self):
        self.assertIsNone(self.task._get_last_updated_timestamp())

    def test_no_messages_queued(self):
        self.task.state = types.TaskState.QUEUED
        self.assertIsNone(self.task._get_last_updated_timestamp())

    def test_no_messages_executed(self):
        # This can't happen - task is switched to executed by receiving
        # a TaskExecuted message
        pass

    @mock.patch("datetime.datetime")
    def test_no_messages_finished(self, mock_datetime):
        # This can happen when Task is killed in created state
        self.task.state = types.TaskState.FINISHED
        self._prepare_mock_datetime_now(mock_datetime)
        self.assertEqual(DATETIME_NOW, self.task._get_last_updated_timestamp())
        self.assertEqual(DATETIME_NOW, self.task._last_message_at)

    # There can't be created or queued tasks that have messages, task is
    # assigned to a worker (which sends messages) in executed state
    def test_created(self):
        pass

    def test_queued(self):
        pass

    @mock.patch("datetime.datetime")
    def test_executed(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        message = messaging.Message(
            TASK_IDENT, messaging.TaskExecuted(WORKER_PID)
        )
        self.task.receive_message(message)
        self.assertEqual(DATETIME_NOW, self.task._get_last_updated_timestamp())

    @mock.patch("datetime.datetime")
    def test_finished(self, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        message = messaging.Message(
            TASK_IDENT, messaging.TaskFinished(types.TaskFinishType.FAIL, None)
        )
        self.task.receive_message(message)
        self.assertEqual(DATETIME_NOW, self.task._get_last_updated_timestamp())


@mock.patch("datetime.datetime")
@mock.patch.object(tasks.Task, "_get_last_updated_timestamp")
class TestIsTimedOut(TaskBaseTestCase, MockDateTimeNowMixin):
    def test_not_timed_out(self, mock_last_timestamp, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        mock_last_timestamp.return_value = DATETIME_BEFORE_TIMEOUT
        self.assertFalse(self.task._is_timed_out(TEST_TIMEOUT_S))
        mock_last_timestamp.assert_called_once()

    def test_timed_out(self, mock_last_timestamp, mock_datetime):
        self._prepare_mock_datetime_now(mock_datetime)
        mock_last_timestamp.return_value = DATETIME_AFTER_TIMEOUT
        self.assertTrue(self.task._is_timed_out(TEST_TIMEOUT_S))
        mock_last_timestamp.assert_called_once()


@mock.patch.object(tasks.Task, "_is_timed_out")
class TestDefunct(TaskBaseTestCase):
    def _assert_not_defunct(self, mock_is_timed_out, state):
        self.task.state = state
        self.assertFalse(self.task.is_defunct())
        mock_is_timed_out.assert_not_called()

    def test_not_defunct_created(self, mock_is_timed_out):
        self._assert_not_defunct(mock_is_timed_out, types.TaskState.CREATED)

    def test_not_defunct_queued(self, mock_is_timed_out):
        self._assert_not_defunct(mock_is_timed_out, types.TaskState.QUEUED)

    def test_not_defunct_executed(self, mock_is_timed_out):
        self.task.state = types.TaskState.EXECUTED
        mock_is_timed_out.return_value = False
        self.assertFalse(self.task.is_defunct())
        mock_is_timed_out.assert_called_once_with(
            task_unresponsive_timeout_seconds
        )

    def test_defunct_executed(self, mock_is_timed_out):
        self.task.state = types.TaskState.EXECUTED
        mock_is_timed_out.return_value = True
        self.assertTrue(self.task.is_defunct())
        mock_is_timed_out.assert_called_once_with(
            task_unresponsive_timeout_seconds
        )

    def test_not_defunct_finished(self, mock_is_timed_out):
        self._assert_not_defunct(mock_is_timed_out, types.TaskState.FINISHED)


@mock.patch.object(tasks.Task, "_is_timed_out")
class TestAbandoned(TaskBaseTestCase):
    def _assert_not_abandoned(self, mock_is_timed_out, state):
        self.task.state = state
        self.assertFalse(self.task.is_abandoned())
        mock_is_timed_out.assert_not_called()

    def test_not_abandoned_created(self, mock_is_timed_out):
        self._assert_not_abandoned(mock_is_timed_out, types.TaskState.CREATED)

    def test_not_abandoned_queued(self, mock_is_timed_out):
        self._assert_not_abandoned(mock_is_timed_out, types.TaskState.QUEUED)

    def test_not_abandoned_executed(self, mock_is_timed_out):
        self._assert_not_abandoned(mock_is_timed_out, types.TaskState.EXECUTED)

    def test_abandoned_finished(self, mock_is_timed_out):
        self.task.state = types.TaskState.FINISHED
        mock_is_timed_out.return_value = True
        self.assertTrue(self.task.is_abandoned())
        mock_is_timed_out.assert_called_once_with(
            task_abandoned_timeout_seconds
        )

    def test_not_abandoned_finished(self, mock_is_timed_out):
        self.task.state = types.TaskState.FINISHED
        mock_is_timed_out.return_value = False
        self.assertFalse(self.task.is_abandoned())
        mock_is_timed_out.assert_called_once_with(
            task_abandoned_timeout_seconds
        )
