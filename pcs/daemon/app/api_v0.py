import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, cast

from tornado.web import Finish

from pcs.common import file_type_codes, reports
from pcs.common.async_tasks import types
from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
)
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.common.reports.dto import ReportItemDto
from pcs.common.str_tools import format_list
from pcs.daemon.app.auth import LegacyTokenAuthenticationHandler
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.pcs_cfgsync.const import SYNCED_CONFIGS

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

    def _check_required_params(self, required_params: set[str]) -> None:
        missing_params = required_params - set(self.request.arguments.keys())
        if missing_params:
            raise self._error(
                f"Required parameters missing: {format_list(missing_params)}"
            )

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
            Command(command_dto, is_legacy_command=True),
            self.real_user,
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
            and not task_result_dto.reports[0].context
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
        self._check_required_params({"resource_list_json"})
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


class QdeviceNetGetCaCertificateHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        result = await self._process_request(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )
        if not result.success:
            raise self._error(_reports_to_str(result.reports))
        self.write(result.result)


class QdeviceNetSignNodeCertificateHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"certificate_request", "cluster_name"})
        result = await self._process_request(
            "qdevice.qdevice_net_sign_certificate_request",
            dict(
                certificate_request=self.get_argument("certificate_request"),
                cluster_name=self.get_body_argument("cluster_name"),
            ),
        )
        if not result.success:
            raise self._error(_reports_to_str(result.reports))
        self.write(result.result)


class QdeviceNetClientInitCertificateStorageHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"ca_certificate"})
        result = await self._process_request(
            "qdevice.client_net_setup",
            dict(ca_certificate=self.get_argument("ca_certificate")),
        )
        if not result.success:
            raise self._error(_reports_to_str(result.reports))


class QdeviceNetClientImportCertificateHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"certificate"})
        result = await self._process_request(
            "qdevice.client_net_import_certificate",
            dict(certificate=self.get_argument("certificate")),
        )
        if not result.success:
            raise self._error(_reports_to_str(result.reports))


class QdeviceNetClientDestroyHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        result = await self._process_request("qdevice.client_net_destroy", {})
        if not result.success:
            raise self._error(_reports_to_str(result.reports))


class GetConfigsHandler(_BaseApiV0Handler):
    _FILE_TYPE_CODE_TO_LEGACY = {
        file_type_codes.PCS_SETTINGS_CONF: "pcs_settings.conf",
        file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    }

    async def _handle_request(self) -> None:
        result = await self._process_request(
            "pcs_cfgsync.get_configs",
            {"cluster_name": self.get_argument("cluster_name", "")},
        )

        if any(
            rep.message.code == reports.codes.FILE_IO_ERROR
            and rep.message.payload.get("file_type_code")
            == file_type_codes.COROSYNC_CONF
            and rep.message.payload.get("operation") == "read"
            for rep in result.reports
        ):
            # corosync.conf does not exists, or we were unable to read the file
            # so we say that the node is not in cluster - same as in the old
            # implementation
            self.write({"status": "not_in_cluster"})
            return
        if any(
            rep.message.code
            == reports.codes.NODE_REPORTS_UNEXPECTED_CLUSTER_NAME
            for rep in result.reports
        ):
            self.write({"status": "wrong_cluster_name"})
            return
        if not result.success or result.result is None:
            raise self._error(_reports_to_str(result.reports))

        command_result = cast(SyncConfigsDto, result.result)
        legacy_result = {
            "status": "ok",
            "cluster_name": command_result.cluster_name,
            "configs": {
                self._FILE_TYPE_CODE_TO_LEGACY[file_code]: {
                    "type": "file",
                    "text": command_result.configs.get(file_code),
                }
                for file_code in SYNCED_CONFIGS
            },
        }
        self.write(legacy_result)


def get_routes(scheduler: Scheduler, auth_provider: AuthProvider) -> RoutesType:
    def r(url: str) -> str:
        # pylint: disable=invalid-name
        return f"/remote/{url}"

    params = dict(scheduler=scheduler, auth_provider=auth_provider)
    return [
        # resources
        (r("manage_resource"), ResourceManageHandler, params),
        (r("unmanage_resource"), ResourceUnmanageHandler, params),
        # qdevice
        (
            r("qdevice_net_client_destroy"),
            QdeviceNetClientDestroyHandler,
            params,
        ),
        (
            # /api/v1/qdevice-client-net-import-certificate/v1
            r("qdevice_net_client_import_certificate"),
            QdeviceNetClientImportCertificateHandler,
            params,
        ),
        (
            r("qdevice_net_client_init_certificate_storage"),
            QdeviceNetClientInitCertificateStorageHandler,
            params,
        ),
        (
            r("qdevice_net_get_ca_certificate"),
            QdeviceNetGetCaCertificateHandler,
            params,
        ),
        (
            # /api/v1/qdevice-qdevice-net-sign-certificate-request/v1
            r("qdevice_net_sign_node_certificate"),
            QdeviceNetSignNodeCertificateHandler,
            params,
        ),
        # cfgsync
        (r("get_configs"), GetConfigsHandler, params),
    ]
