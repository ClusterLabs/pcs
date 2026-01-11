from unittest import IsolatedAsyncioTestCase, mock

from tornado.web import Finish

from pcs.common import reports
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
from pcs.daemon.app.api_v0_tools import (
    SimplifiedResult,
    _report_to_str,
    reports_to_str,
    run_library_command_in_scheduler,
)
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser


class ReportToStrTest(IsolatedAsyncioTestCase):
    def test_error_without_context(self):
        report_item = reports.ReportItem.error(
            reports.messages.StonithUnfencingFailed("test error")
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Error: Unfencing failed:\ntest error",
        )

    def test_warning_without_context(self):
        report_item = reports.ReportItem.warning(
            reports.messages.StonithUnfencingFailed("test warning")
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Warning: Unfencing failed:\ntest warning",
        )

    def test_info_without_context(self):
        report_item = reports.ReportItem.info(
            reports.messages.StonithUnfencingFailed("test info")
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Unfencing failed:\ntest info",
        )

    def test_debug_without_context(self):
        report_item = reports.ReportItem.debug(
            reports.messages.StonithUnfencingFailed("test debug")
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Debug: Unfencing failed:\ntest debug",
        )

    def test_deprecation_without_context(self):
        report_item = reports.ReportItem.deprecation(
            reports.messages.StonithUnfencingFailed("test deprecation")
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Deprecation warning: Unfencing failed:\ntest deprecation",
        )

    def test_error_with_context(self):
        report_item = reports.ReportItem.error(
            reports.messages.StonithUnfencingFailed("test error"),
            context=reports.ReportItemContext("node1"),
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Error: node1: Unfencing failed:\ntest error",
        )

    def test_warning_with_context(self):
        report_item = reports.ReportItem.warning(
            reports.messages.StonithUnfencingFailed("test warning"),
            context=reports.ReportItemContext("node2"),
        ).to_dto()
        self.assertEqual(
            _report_to_str(report_item),
            "Warning: node2: Unfencing failed:\ntest warning",
        )


class ReportsToStrTest(IsolatedAsyncioTestCase):
    def test_empty_list(self):
        self.assertEqual(reports_to_str([]), "")

    def test_single_report(self):
        report_items = [
            reports.ReportItem.error(
                reports.messages.StonithUnfencingFailed("test error")
            ).to_dto()
        ]
        self.assertEqual(
            reports_to_str(report_items),
            "Error: Unfencing failed:\ntest error",
        )

    def test_multiple_reports(self):
        report_items = [
            reports.ReportItem.error(
                reports.messages.StonithUnfencingFailed("first error"),
                context=reports.ReportItemContext("node1"),
            ).to_dto(),
            reports.ReportItem.warning(
                reports.messages.StonithUnfencingFailed("a warning")
            ).to_dto(),
        ]
        self.assertEqual(
            reports_to_str(report_items),
            "Error: node1: Unfencing failed:\nfirst error\n"
            "Warning: Unfencing failed:\na warning",
        )


class RunLibraryCommandInSchedulerTest(IsolatedAsyncioTestCase):
    def setUp(self):
        self.scheduler = mock.AsyncMock(spec=Scheduler)
        self.command_dto = CommandDto(
            command_name="test.command",
            params={"param1": "value1"},
            options=CommandOptionsDto(
                effective_username="testuser",
                effective_groups=["testgroup"],
            ),
        )
        self.auth_user = AuthUser("testuser", ["testgroup"])
        self.task_ident = "task-123"
        self.error_handler = mock.Mock(
            side_effect=lambda msg, code=400: Finish()
        )

        self.scheduler.new_task.return_value = self.task_ident

    async def test_success(self):
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.SUCCESS,
            kill_reason=None,
            result="command result",
        )
        self.scheduler.wait_for_task.return_value = task_result

        result = await run_library_command_in_scheduler(
            self.scheduler,
            self.command_dto,
            self.auth_user,
            self.error_handler,
        )

        self.assertIsInstance(result, SimplifiedResult)
        self.assertTrue(result.success)
        self.assertEqual(result.result, "command result")
        self.assertEqual(result.reports, [])

        self.scheduler.new_task.assert_called_once_with(
            Command(self.command_dto, is_legacy_command=True),
            self.auth_user,
        )
        self.scheduler.wait_for_task.assert_called_once_with(
            self.task_ident, self.auth_user
        )
        self.error_handler.assert_not_called()

    async def test_failure(self):
        report_items = [
            reports.ReportItem.error(
                reports.messages.StonithUnfencingFailed("test error")
            ).to_dto()
        ]
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=report_items,
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.FAIL,
            kill_reason=None,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        result = await run_library_command_in_scheduler(
            self.scheduler,
            self.command_dto,
            self.auth_user,
            self.error_handler,
        )

        self.assertIsInstance(result, SimplifiedResult)
        self.assertFalse(result.success)
        self.assertIsNone(result.result)
        self.assertEqual(result.reports, report_items)
        self.error_handler.assert_not_called()

    async def test_task_not_found(self):
        self.scheduler.wait_for_task.side_effect = TaskNotFoundError(
            self.task_ident
        )

        with self.assertRaises(Finish):
            await run_library_command_in_scheduler(
                self.scheduler,
                self.command_dto,
                self.auth_user,
                self.error_handler,
            )

        self.error_handler.assert_called_once_with("Internal server error", 500)

    async def test_permission_denied(self):
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[
                reports.ReportItem.error(
                    reports.messages.NotAuthorized()
                ).to_dto()
            ],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.FAIL,
            kill_reason=None,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        with self.assertRaises(Finish):
            await run_library_command_in_scheduler(
                self.scheduler,
                self.command_dto,
                self.auth_user,
                self.error_handler,
            )

        self.error_handler.assert_called_once_with("Permission denied", 403)

    async def test_permission_denied_with_context(self):
        # Permission denied with context should not raise error
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[
                reports.ReportItem.error(
                    reports.messages.NotAuthorized(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto()
            ],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.FAIL,
            kill_reason=None,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        result = await run_library_command_in_scheduler(
            self.scheduler,
            self.command_dto,
            self.auth_user,
            self.error_handler,
        )

        self.assertFalse(result.success)
        self.error_handler.assert_not_called()

    async def test_task_killed_completion_timeout(self):
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.KILL,
            kill_reason=TaskKillReason.COMPLETION_TIMEOUT,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        with self.assertRaises(Finish):
            await run_library_command_in_scheduler(
                self.scheduler,
                self.command_dto,
                self.auth_user,
                self.error_handler,
            )

        self.error_handler.assert_called_once_with(
            "Task processing timed out", 500
        )

    async def test_task_killed_other_reason(self):
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.KILL,
            kill_reason=None,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        with self.assertRaises(Finish):
            await run_library_command_in_scheduler(
                self.scheduler,
                self.command_dto,
                self.auth_user,
                self.error_handler,
            )

        self.error_handler.assert_called_once_with("Task killed")

    async def test_unhandled_exception(self):
        task_result = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.UNHANDLED_EXCEPTION,
            kill_reason=None,
            result=None,
        )
        self.scheduler.wait_for_task.return_value = task_result

        with self.assertRaises(Finish):
            await run_library_command_in_scheduler(
                self.scheduler,
                self.command_dto,
                self.auth_user,
                self.error_handler,
            )

        self.error_handler.assert_called_once_with("Unhandled exception", 500)
