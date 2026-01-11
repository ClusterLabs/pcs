from dataclasses import dataclass
from typing import Any, Callable, Iterable

from tornado.web import Finish

from pcs.common import reports
from pcs.common.async_tasks import types
from pcs.common.async_tasks.dto import (
    CommandDto,
)
from pcs.common.reports.dto import ReportItemDto
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser


@dataclass(frozen=True)
class SimplifiedResult:
    success: bool
    result: Any
    reports: list[ReportItemDto]


_SEVERITY_LABEL = {
    reports.ReportItemSeverity.DEBUG: "Debug: ",
    reports.ReportItemSeverity.DEPRECATION: "Deprecation warning: ",
    reports.ReportItemSeverity.ERROR: "Error: ",
    reports.ReportItemSeverity.INFO: "",
    reports.ReportItemSeverity.WARNING: "Warning: ",
}


def _report_to_str(report_item: ReportItemDto) -> str:
    return (
        _SEVERITY_LABEL.get(report_item.severity.level, "")
        + (f"{report_item.context.node}: " if report_item.context else "")
        + report_item.message.message
    )


def reports_to_str(report_items: Iterable[ReportItemDto]) -> str:
    return "\n".join(_report_to_str(item) for item in report_items)


async def run_library_command_in_scheduler(
    scheduler: Scheduler,
    command_dto: CommandDto,
    auth_user: AuthUser,
    error_handler: Callable[[str, int], Finish],
) -> SimplifiedResult:
    task_ident = scheduler.new_task(
        Command(command_dto, is_legacy_command=True), auth_user
    )

    try:
        task_result_dto = await scheduler.wait_for_task(task_ident, auth_user)
    except TaskNotFoundError as e:
        raise error_handler("Internal server error", 500) from e

    if (
        task_result_dto.task_finish_type == types.TaskFinishType.FAIL
        and task_result_dto.reports
        and task_result_dto.reports[0].message.code
        == reports.codes.NOT_AUTHORIZED
        and not task_result_dto.reports[0].context
    ):
        raise error_handler("Permission denied", 403)

    if task_result_dto.task_finish_type == types.TaskFinishType.KILL:
        if (
            task_result_dto.kill_reason
            == types.TaskKillReason.COMPLETION_TIMEOUT
        ):
            raise error_handler("Task processing timed out", 500)
        raise error_handler("Task killed")

    if (
        task_result_dto.task_finish_type
        == types.TaskFinishType.UNHANDLED_EXCEPTION
    ):
        raise error_handler("Unhandled exception", 500)

    return SimplifiedResult(
        task_result_dto.task_finish_type == types.TaskFinishType.SUCCESS,
        task_result_dto.result,
        task_result_dto.reports,
    )
