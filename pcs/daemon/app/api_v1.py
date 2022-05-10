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

from tornado.web import (
    HTTPError,
    RequestHandler,
)

from pcs.common import communication
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


class ApiError(HTTPError):
    def __init__(
        self,
        response_code: communication.types.CommunicationResultStatus,
        response_msg: str,
    ) -> None:
        super().__init__(200)
        self.response_code = response_code
        self.response_msg = response_msg


class InvalidInputError(ApiError):
    def __init__(self, msg="Input is not valid JSON object"):
        super().__init__(communication.const.COM_STATUS_INPUT_ERROR, msg)


class BaseAPIHandler(RequestHandler):
    """
    Base handler for the REST API

    Defines all common functions used by handlers, message body preprocessing,
    and HTTP(S) settings.
    """

    def initialize(self, scheduler: Scheduler) -> None:
        # pylint: disable=attribute-defined-outside-init
        self.scheduler = scheduler
        self.json: Optional[Dict[str, Any]] = None
        # TODO: Turn into a constant
        self.logger: logging.Logger = logging.getLogger("pcs_scheduler")

    def prepare(self) -> None:
        """JSON preprocessing"""
        # pylint: disable=attribute-defined-outside-init
        self.add_header("Content-Type", "application/json")
        if (
            "Content-Type" in self.request.headers
            and self.request.headers["Content-Type"] == "application/json"
        ):
            try:
                self.json = json.loads(self.request.body)
            except json.JSONDecodeError as e:
                raise InvalidInputError() from e

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


class ApiV1Handler(BaseAPIHandler):
    """Create a new task from command"""

    async def post(self, cmd) -> None:
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
            options=CommandOptionsDto(),
        )
        task_ident = self.scheduler.new_task(command_dto)

        try:
            task_result_dto = await self.scheduler.wait_for_task(task_ident)
        except TaskNotFoundError as e:
            raise ApiError(
                communication.const.COM_STATUS_EXCEPTION,
                "Internal server error",
            ) from e
        status_map = {
            types.TaskFinishType.SUCCESS: communication.const.COM_STATUS_SUCCESS,
            types.TaskFinishType.FAIL: communication.const.COM_STATUS_ERROR,
        }
        self.send_response(
            communication.dto.InternalCommunicationResultDto(
                status=status_map.get(
                    task_result_dto.task_finish_type,
                    communication.const.COM_STATUS_EXCEPTION,
                ),
                status_msg=None,
                report_list=task_result_dto.reports,
                data=task_result_dto.result,
            )
        )


def get_routes(
    scheduler: Scheduler,
) -> List[Tuple[str, Type[BaseAPIHandler], dict]]:
    params = dict(scheduler=scheduler)
    return [
        (r"/api/v1/(.*)", ApiV1Handler, params),
    ]
