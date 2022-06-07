import base64
import binascii
import json
import logging
from typing import (
    Any,
    Awaitable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
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
from pcs.daemon.async_tasks.command_mapping import API_V1_MAP
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.lib.auth.provider import (
    AuthProvider,
    AuthUser,
)

from .common import (
    AuthProviderBaseHandler,
    NotAuthorizedException,
)


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


class BaseApiV1Handler(AuthProviderBaseHandler):
    """
    Base handler for the REST API

    Defines all common functions used by handlers, message body preprocessing,
    and HTTP(S) settings.
    """

    def initialize(
        self, scheduler: Scheduler, auth_provider: AuthProvider
    ) -> None:
        super()._init_auth_provider(auth_provider)
        # pylint: disable=attribute-defined-outside-init
        self.scheduler = scheduler
        self.json: Optional[Dict[str, Any]] = None
        # TODO: Turn into a constant
        self.logger: logging.Logger = logging.getLogger("pcs.daemon.scheduler")

    def prepare(self) -> None:
        """JSON preprocessing"""
        # pylint: disable=attribute-defined-outside-init
        self.add_header("Content-Type", "application/json")
        try:
            self.json = json.loads(self.request.body)
        except json.JSONDecodeError as e:
            raise InvalidInputError() from e

    async def get_auth_user(self) -> AuthUser:
        try:
            return await super().get_auth_user()
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
        self.logger.exception("API error occurred.")
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

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        # We do not support HTTP chunk mode, reimplementing abstract
        pass

    def _get_effective_username(self) -> Optional[str]:
        username = self.get_cookie("CIB_user")
        if username:
            return username
        return None

    def _get_effective_groups(self) -> Optional[List[str]]:
        if self._get_effective_username():
            # use groups only if user is specified as well
            groups_raw = self.get_cookie("CIB_user_groups")
            if groups_raw:
                try:
                    return (
                        base64.b64decode(groups_raw).decode("utf-8").split(" ")
                    )
                except (UnicodeError, binascii.Error):
                    self.logger.warning("Unable to decode users groups")
        return None

    async def process_request(
        self, cmd: str
    ) -> communication.dto.InternalCommunicationResultDto:
        auth_user = await self.get_auth_user()
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
                effective_username=self._get_effective_username(),
                effective_groups=self._get_effective_groups(),
            ),
        )
        task_ident = self.scheduler.new_task(command_dto, auth_user)

        try:
            task_result_dto = await self.scheduler.wait_for_task(task_ident)
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


class ApiV1Handler(BaseApiV1Handler):
    async def post(self, cmd: str) -> None:
        self.send_response(await self.process_request(cmd))

    # TODO: test get method
    async def get(self, cmd: str) -> None:
        self.send_response(await self.process_request(cmd))


class LegacyApiV1Handler(BaseApiV1Handler):
    @staticmethod
    def _get_cmd() -> str:
        raise NotImplementedError()

    def prepare(self) -> None:
        # pylint: disable=attribute-defined-outside-init
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
        return "status.full_cluster_status_plaintext"


class ClusterAddNodesLegacyHandler(LegacyApiV1Handler):
    @staticmethod
    def _get_cmd() -> str:
        return "cluster.add_nodes"


def get_routes(
    scheduler: Scheduler, auth_provider: AuthProvider
) -> List[Tuple[str, Type[BaseApiV1Handler], dict]]:
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
