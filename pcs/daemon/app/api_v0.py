import json
from typing import Any, Mapping, cast

from tornado.locks import Lock
from tornado.web import Finish

from pcs.common import file_type_codes, reports
from pcs.common.async_tasks.dto import CommandDto, CommandOptionsDto
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.common.str_tools import format_list
from pcs.daemon import log
from pcs.daemon.app.api_v0_tools import (
    SimplifiedResult,
    reports_to_str,
    run_library_command_in_scheduler,
)
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    NotAuthorizedException,
)
from pcs.daemon.app.common import (
    LegacyApiHandler,
    get_legacy_desired_user_from_request,
)
from pcs.daemon.async_tasks.scheduler import Scheduler
from pcs.lib.auth.tools import DesiredUser
from pcs.lib.auth.types import AuthUser
from pcs.lib.pcs_cfgsync.const import SYNCED_CONFIGS

from .common import RoutesType


class _BaseApiV0Handler(LegacyApiHandler):
    """
    Base class of handlers for the original API implemented in remote.rb
    """

    _auth_provider: ApiAuthProviderInterface
    _scheduler: Scheduler
    _real_user: AuthUser
    _desired_user: DesiredUser

    def initialize(
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        scheduler: Scheduler,
    ) -> None:
        self._auth_provider = api_auth_provider_factory.create(self)
        self._scheduler = scheduler

    async def prepare(self) -> None:
        try:
            self._real_user = await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise self.unauthorized() from e

        self._desired_user = get_legacy_desired_user_from_request(
            self, log.pcsd
        )

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

    async def _run_library_command(
        self, cmd_name: str, cmd_params: Mapping[str, Any]
    ) -> SimplifiedResult:
        """
        Helper method for calling pcs library commands
        """
        command_dto = CommandDto(
            command_name=cmd_name,
            params=dict(cmd_params),
            # the scheduler/executor handles whether the command is run with
            # real_user permissions or the effective user is used
            options=CommandOptionsDto(
                effective_username=self._desired_user.username,
                effective_groups=list(self._desired_user.groups)
                if self._desired_user.groups
                else None,
            ),
        )
        return await run_library_command_in_scheduler(
            self._scheduler, command_dto, self._real_user, self._error
        )


class ResourceManageUnmanageHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"resource_list_json"})
        try:
            resource_list = json.loads(self.get_argument("resource_list_json"))
        except json.JSONDecodeError as e:
            raise self._error("Invalid input data format") from e
        result = await self._run_library_command(
            self._get_cmd(), dict(resource_or_tag_ids=resource_list)
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))

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
        result = await self._run_library_command(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))
        self.write(result.result)


class QdeviceNetSignNodeCertificateHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"certificate_request", "cluster_name"})
        result = await self._run_library_command(
            "qdevice.qdevice_net_sign_certificate_request",
            dict(
                certificate_request=self.get_argument("certificate_request"),
                cluster_name=self.get_body_argument("cluster_name"),
            ),
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))
        self.write(result.result)


class QdeviceNetClientInitCertificateStorageHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"ca_certificate"})
        result = await self._run_library_command(
            "qdevice.client_net_setup",
            dict(ca_certificate=self.get_argument("ca_certificate")),
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))


class QdeviceNetClientImportCertificateHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        self._check_required_params({"certificate"})
        result = await self._run_library_command(
            "qdevice.client_net_import_certificate",
            dict(certificate=self.get_argument("certificate")),
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))


class QdeviceNetClientDestroyHandler(_BaseApiV0Handler):
    async def _handle_request(self) -> None:
        result = await self._run_library_command(
            "qdevice.client_net_destroy", {}
        )
        if not result.success:
            raise self._error(reports_to_str(result.reports))


class GetConfigsHandler(_BaseApiV0Handler):
    _FILE_TYPE_CODE_TO_LEGACY = {
        file_type_codes.PCS_SETTINGS_CONF: "pcs_settings.conf",
        file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    }

    async def _handle_request(self) -> None:
        result = await self._run_library_command(
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
            raise self._error(reports_to_str(result.reports))

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


class SetSyncOptionsHandler(_BaseApiV0Handler):
    _sync_config_lock: Lock

    def initialize(  # type: ignore[override]
        self,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
        scheduler: Scheduler,
        sync_config_lock: Lock,
    ) -> None:
        super().initialize(api_auth_provider_factory, scheduler)
        self._sync_config_lock = sync_config_lock

    async def _handle_request(self) -> None:
        options = {
            key: self.get_argument(key) for key in self.request.arguments
        }

        async with self._sync_config_lock:
            result = await self._run_library_command(
                "pcs_cfgsync.update_sync_options", {"options": options}
            )

        if not result.success:
            raise self._error(reports_to_str(result.reports))
        self.write("Sync thread options updated successfully")


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    scheduler: Scheduler,
    sync_config_lock: Lock,
) -> RoutesType:
    def r(url: str) -> str:
        # pylint: disable=invalid-name
        return f"/remote/{url}"

    params = dict(
        api_auth_provider_factory=api_auth_provider_factory, scheduler=scheduler
    )
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
        (
            r("set_sync_options"),
            SetSyncOptionsHandler,
            {**params, "sync_config_lock": sync_config_lock},
        ),
    ]
