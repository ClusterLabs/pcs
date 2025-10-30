import json
from typing import (
    Any,
    Dict,
    Mapping,
    Optional,
)

from tornado.web import HTTPError

from pcs.common import (
    communication,
    reports,
)
from pcs.common.async_tasks import types
from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
)
from pcs.common.interface.dto import to_dict
from pcs.daemon.app.auth import (
    LegacyTokenAuthProvider,
    NotAuthorizedException,
)
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser

from .common import (
    BaseHandler,
    RoutesType,
)

API_V1_MAP: Mapping[str, str] = {
    "acl-create-role/v1": "acl.create_role",
    "acl-remove-role/v1": "acl.remove_role",
    "acl-assign-role-to-target/v1": "acl.assign_role_to_target",
    "acl-assign-role-to-group/v1": "acl.assign_role_to_group",
    "acl-unassign-role-from-target/v1": "acl.unassign_role_from_target",
    "acl-unassign-role-from-group/v1": "acl.unassign_role_from_group",
    "acl-create-target/v1": "acl.create_target",
    "acl-create-group/v1": "acl.create_group",
    "acl-remove-target/v1": "acl.remove_target",
    "acl-remove-group/v1": "acl.remove_group",
    "acl-add-permission/v1": "acl.add_permission",
    "acl-remove-permission/v1": "acl.remove_permission",
    "alert-create-alert/v1": "alert.create_alert",
    "alert-update-alert/v1": "alert.update_alert",
    "alert-remove-alert/v1": "alert.remove_alert",
    "alert-add-recipient/v1": "alert.add_recipient",
    "alert-update-recipient/v1": "alert.update_recipient",
    "alert-remove-recipient/v1": "alert.remove_recipient",
    "cfgsync-get-configs/v1": "pcs_cfgsync.get_configs",
    "cib-element-description-get/v1": "cib.element_description_get",
    "cib-element-description-set/v1": "cib.element_description_set",
    "cluster-add-nodes/v1": "cluster.add_nodes",
    "cluster-node-clear/v1": "cluster.node_clear",
    "cluster-remove-nodes/v1": "cluster.remove_nodes",
    "cluster-setup/v1": "cluster.setup",
    "cluster-generate-cluster-uuid/v1": "cluster.generate_cluster_uuid",
    "cluster-property-remove-name/v1": "cluster_property.remove_cluster_name",
    "constraint-colocation-create-with-set/v1": "constraint.colocation.create_with_set",
    "constraint-order-create-with-set/v1": "constraint.order.create_with_set",
    "constraint-ticket-create-with-set/v1": "constraint.ticket.create_with_set",
    "constraint-ticket-create/v1": "constraint.ticket.create",
    "constraint-ticket-remove/v1": "constraint.ticket.remove",
    "fencing-topology-add-level/v1": "fencing_topology.add_level",
    "fencing-topology-remove-all-levels/v1": "fencing_topology.remove_all_levels",
    "fencing-topology-remove-levels-by-params/v1": "fencing_topology.remove_levels_by_params",
    "fencing-topology-verify/v1": "fencing_topology.verify",
    "node-maintenance-unmaintenance/v1": "node.maintenance_unmaintenance_list",
    "node-maintenance-unmaintenance-all/v1": "node.maintenance_unmaintenance_all",
    "node-standby-unstandby/v1": "node.standby_unstandby_list",
    "node-standby-unstandby-all/v1": "node.standby_unstandby_all",
    "qdevice-client-net-import-certificate/v1": "qdevice.client_net_import_certificate",
    "qdevice-qdevice-net-sign-certificate-request/v1": "qdevice.qdevice_net_sign_certificate_request",
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "resource-agent-describe-agent/v1": "resource_agent.describe_agent",
    "resource-agent-get-agents-list/v1": "resource_agent.get_agents_list",
    "resource-agent-get-agent-metadata/v1": "resource_agent.get_agent_metadata",
    "resource-agent-get-meta-attributes-metadata/v1": "resource_agent.get_meta_attributes_metadata",
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "resource-agent-list-agents/v1": "resource_agent.list_agents",
    "resource-agent-list-agents-for-standard-and-provider/v1": "resource_agent.list_agents_for_standard_and_provider",
    "resource-agent-list-ocf-providers/v1": "resource_agent.list_ocf_providers",
    "resource-agent-list-standards/v1": "resource_agent.list_standards",
    "resource-ban/v1": "resource.ban",
    "resource-create/v1": "resource.create",
    "resource-create-as-clone/v1": "resource.create_as_clone",
    "resource-create-in-group/v1": "resource.create_in_group",
    "resource-disable/v1": "resource.disable",
    "resource-disable-safe/v1": "resource.disable_safe",
    "resource-disable-simulate/v1": "resource.disable_simulate",
    "resource-enable/v1": "resource.enable",
    "resource-group-add/v1": "resource.group_add",
    "resource-manage/v1": "resource.manage",
    "resource-move/v1": "resource.move",
    "resource-move-autoclean/v1": "resource.move_autoclean",
    "resource-unmanage/v1": "resource.unmanage",
    "resource-unmove-unban/v1": "resource.unmove_unban",
    "sbd-disable-sbd/v1": "sbd.disable_sbd",
    "sbd-enable-sbd/v1": "sbd.enable_sbd",
    "scsi-unfence-node/v2": "scsi.unfence_node",
    "scsi-unfence-node-mpath/v1": "scsi.unfence_node_mpath",
    "status-full-cluster-status-plaintext/v1": "status.full_cluster_status_plaintext",
    # deprecated, use resource-agent-get-agent-metadata/v1 instead
    "stonith-agent-describe-agent/v1": "stonith_agent.describe_agent",
    # deprecated, use resource-agent-get-agents-list/v1 instead
    "stonith-agent-list-agents/v1": "stonith_agent.list_agents",
    "stonith-create/v1": "stonith.create",
}


class ApiError(HTTPError):
    def __init__(
        self,
        response_code: communication.types.CommunicationResultStatus,
        response_msg: str,
        http_code: int = 200,
    ) -> None:
        super().__init__(http_code)
        self.response_code = response_code
        self.response_msg = response_msg


class InvalidInputError(ApiError):
    def __init__(self, msg: str = "Input is not valid JSON object"):
        super().__init__(communication.const.COM_STATUS_INPUT_ERROR, msg)


class _BaseApiV1Handler(BaseHandler):
    """
    Base handler for the REST API

    Defines all common functions used by handlers, message body preprocessing,
    and HTTP(S) settings.
    """

    scheduler: Scheduler
    json: Optional[Dict[str, Any]] = None
    _auth_provider: LegacyTokenAuthProvider

    def initialize(
        self, scheduler: Scheduler, auth_provider: AuthProvider
    ) -> None:
        super().initialize()
        self._auth_provider = LegacyTokenAuthProvider(self, auth_provider)
        self.scheduler = scheduler

    def prepare(self) -> None:
        """JSON preprocessing"""
        self.add_header("Content-Type", "application/json")
        try:
            self.json = json.loads(self.request.body)
        except json.JSONDecodeError as e:
            raise InvalidInputError() from e

    async def get_auth_user(self) -> tuple[AuthUser, AuthUser]:
        try:
            return await self._auth_provider.auth_by_token_effective_user()
        except NotAuthorizedException as e:
            raise ApiError(
                response_code=communication.const.COM_STATUS_NOT_AUTHORIZED,
                response_msg="",
                http_code=401,
            ) from e

    def send_response(
        self, response: communication.dto.InternalCommunicationResultDto
    ) -> None:
        self.finish(json.dumps(to_dict(response)))

    def write_error(self, status_code: int, **kwargs: Any) -> None:
        del status_code
        response = communication.dto.InternalCommunicationResultDto(
            status=communication.const.COM_STATUS_EXCEPTION,
            status_msg=None,
            report_list=[],
            data=None,
        )

        if "exc_info" in kwargs:
            _, exc, _ = kwargs["exc_info"]
            if isinstance(exc, ApiError):
                if (
                    exc.response_code
                    == communication.const.COM_STATUS_NOT_AUTHORIZED
                ):
                    self.finish(json.dumps({"notauthorized": "true"}))
                    return
                response = communication.dto.InternalCommunicationResultDto(
                    status=exc.response_code,
                    status_msg=exc.response_msg,
                    report_list=[],
                    data=None,
                )

        self.send_response(response)

    async def process_request(
        self, cmd: str
    ) -> communication.dto.InternalCommunicationResultDto:
        real_user, effective_user = await self.get_auth_user()
        if cmd not in API_V1_MAP:
            raise ApiError(
                communication.const.COM_STATUS_UNKNOWN_CMD,
                f"Unknown command '{cmd}'",
            )
        if self.json is None:
            raise InvalidInputError()
        command_dto = CommandDto(
            command_name=API_V1_MAP[cmd],
            params=self.json,
            options=CommandOptionsDto(
                effective_username=effective_user.username,
                effective_groups=list(effective_user.groups),
            ),
        )
        task_ident = self.scheduler.new_task(
            Command(command_dto, is_legacy_command=True), real_user
        )

        try:
            task_result_dto = await self.scheduler.wait_for_task(
                task_ident, real_user
            )
        except TaskNotFoundError as e:
            raise ApiError(
                communication.const.COM_STATUS_EXCEPTION,
                "Internal server error",
            ) from e
        if (
            task_result_dto.task_finish_type == types.TaskFinishType.FAIL
            and task_result_dto.reports
            and task_result_dto.reports[0].message.code
            == reports.codes.NOT_AUTHORIZED
            and not task_result_dto.reports[0].context
        ):
            raise ApiError(
                communication.const.COM_STATUS_NOT_AUTHORIZED, "Not authorized"
            )

        status_map = {
            types.TaskFinishType.SUCCESS: communication.const.COM_STATUS_SUCCESS,
            types.TaskFinishType.FAIL: communication.const.COM_STATUS_ERROR,
        }
        return communication.dto.InternalCommunicationResultDto(
            status=status_map.get(
                task_result_dto.task_finish_type,
                communication.const.COM_STATUS_EXCEPTION,
            ),
            status_msg=None,
            report_list=task_result_dto.reports,
            data=task_result_dto.result,
        )


class ApiV1Handler(_BaseApiV1Handler):
    async def post(self, cmd: str) -> None:
        self.send_response(await self.process_request(cmd))

    # TODO: test get method
    async def get(self, cmd: str) -> None:
        self.send_response(await self.process_request(cmd))


class LegacyApiV1Handler(_BaseApiV1Handler):
    @staticmethod
    def _get_cmd() -> str:
        raise NotImplementedError()

    def prepare(self) -> None:
        self.add_header("Content-Type", "application/json")
        try:
            self.json = json.loads(self.get_argument("data_json", default=""))
        except json.JSONDecodeError as e:
            raise InvalidInputError() from e

    def send_response(
        self, response: communication.dto.InternalCommunicationResultDto
    ) -> None:
        result = to_dict(response)
        result["report_list"] = [
            dict(
                severity=report.severity.level,
                code=report.message.code,
                info=report.message.payload,
                forceable=report.severity.force_code,
                report_text=report.message.message,
            )
            for report in response.report_list
        ]
        self.finish(json.dumps(result))

    async def post(self) -> None:
        self.send_response(await self.process_request(self._get_cmd()))

    # TODO: test get method
    async def get(self) -> None:
        self.send_response(await self.process_request(self._get_cmd()))


class ClusterStatusLegacyHandler(LegacyApiV1Handler):
    @staticmethod
    def _get_cmd() -> str:
        return "status-full-cluster-status-plaintext/v1"


class ClusterAddNodesLegacyHandler(LegacyApiV1Handler):
    @staticmethod
    def _get_cmd() -> str:
        return "cluster-add-nodes/v1"


def get_routes(scheduler: Scheduler, auth_provider: AuthProvider) -> RoutesType:
    params = dict(scheduler=scheduler, auth_provider=auth_provider)
    return [
        (
            "/remote/cluster_status_plaintext",
            ClusterStatusLegacyHandler,
            params,
        ),
        (
            "/remote/cluster_add_nodes",
            ClusterAddNodesLegacyHandler,
            params,
        ),
        (r"/api/v1/(.*)", ApiV1Handler, params),
    ]
