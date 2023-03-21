import json
from dataclasses import dataclass
from typing import (
    Any,
    Iterable,
    Mapping,
)

from tornado.web import Finish

from pcs.common import reports
from pcs.common.async_tasks import types
from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
)
from pcs.common.reports.dto import ReportItemDto
from pcs.daemon.app.auth import LegacyTokenAuthenticationHandler
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.provider import AuthProvider

from .common import RoutesType


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


def _reports_to_str(report_items: Iterable[ReportItemDto]) -> str:
    return "\n".join(_report_to_str(item) for item in report_items)


class _BaseApiV0Handler(LegacyTokenAuthenticationHandler):
    """
    Base class of handlers for the original API implemented in remote.rb
    """

    _scheduler: Scheduler

    def initialize(
        self, scheduler: Scheduler, auth_provider: AuthProvider
    ) -> None:
        # pylint: disable=arguments-differ
        super().initialize(auth_provider)
        self._scheduler = scheduler

    async def _handle_request(self) -> None:
        """
        Main method for handling requests
        """
        raise NotImplementedError()

    def _error(self, message: str, http_code: int = 400) -> Finish:
        """
        Helper method for exit request processing with an error
        """
        self.set_status(http_code)
        self.write(message)
        return Finish()

    async def _process_request(
        self, cmd_name: str, cmd_params: Mapping[str, Any]
    ) -> SimplifiedResult:
        """
        Helper method for calling pcs library commands
        """
        command_dto = CommandDto(
            command_name=cmd_name,
            params=cmd_params,
            options=CommandOptionsDto(
                effective_username=self.effective_user.username,
                effective_groups=list(self.effective_user.groups),
            ),
        )
        task_ident = self._scheduler.new_task(
            Command(command_dto, api_v1_compatible=True), self.real_user
        )

        try:
            task_result_dto = await self._scheduler.wait_for_task(
                task_ident, self.real_user
            )
        except TaskNotFoundError as e:
            raise self._error("Internal server error", 500) from e

        if (
            task_result_dto.task_finish_type == types.TaskFinishType.FAIL
            and task_result_dto.reports
            and task_result_dto.reports[0].message.code
            == reports.codes.NOT_AUTHORIZED
        ):
            raise self._error("Permission denied", 403)

        if task_result_dto.task_finish_type == types.TaskFinishType.KILL:
            if (
                task_result_dto.kill_reason
                == types.TaskKillReason.COMPLETION_TIMEOUT
            ):
                raise self._error("Task processing timed out", 500)
            raise self._error("Task killed")

        if (
            task_result_dto.task_finish_type
            == types.TaskFinishType.UNHANDLED_EXCEPTION
        ):
            raise self._error("Unhandled exception", 500)

        return SimplifiedResult(
            task_result_dto.task_finish_type == types.TaskFinishType.SUCCESS,
            task_result_dto.result,
            task_result_dto.reports,
        )


class ResourceManageUnmanageHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        if not "resource_list_json" in self.request.arguments:
            raise self._error(
                "Required parameter 'resource_list_json' is missing."
            )
        try:
            resource_list = json.loads(self.get_argument("resource_list_json"))
        except json.JSONDecodeError as e:
            raise self._error("Invalid input data format") from e
        result = await self._process_request(
            self._get_cmd(), dict(resource_or_tag_ids=resource_list)
        )
        if not result.success:
            raise self._error(_reports_to_str(result.reports))

    @staticmethod
    def _get_cmd() -> str:
        raise NotImplementedError()


class ResourceManageHandler(ResourceManageUnmanageHandler):
    @staticmethod
    def _get_cmd() -> str:
        return "resource.manage"


class ResourceUnmanageHandler(ResourceManageUnmanageHandler):
    @staticmethod
    def _get_cmd() -> str:
        return "resource.unmanage"


def get_routes(scheduler: Scheduler, auth_provider: AuthProvider) -> RoutesType:
    params = dict(scheduler=scheduler, auth_provider=auth_provider)
    return [
        (
            "/remote/manage_resource",
            ResourceManageHandler,
            params,
        ),
        (
            "/remote/unmanage_resource",
            ResourceUnmanageHandler,
            params,
        ),
    ]
