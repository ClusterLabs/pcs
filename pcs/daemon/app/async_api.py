import json
import logging

from typing import (
    cast,
    Any,
    Awaitable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
)

import tornado

from dacite import DaciteError, MissingValueError, UnexpectedDataError
from tornado.httputil import responses
from tornado.web import HTTPError, RequestHandler

from pcs.common.interface.dto import (
    from_dict,
    to_dict,
    DtoType,
)
from pcs.common.async_tasks.dto import CommandDto, TaskIdentDto
from pcs.daemon.async_tasks.scheduler import Scheduler, TaskNotFoundError


class APIError(HTTPError):
    def __init__(
        self,
        http_code: int = 500,
        http_error: Optional[str] = None,
        error_msg: Optional[str] = None,
    ) -> None:
        super().__init__(http_code, reason=http_error)
        self.error_msg = error_msg


class RequestBodyMissingError(APIError):
    def __init__(self) -> None:
        super().__init__(
            400,
            error_msg="Request body is missing, has wrong format or "
            "wrong/missing headers.",
        )


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
            except json.JSONDecodeError:
                raise APIError(http_code=400, error_msg="Malformed JSON data.")

    @staticmethod
    def _from_dict_exc_handled(
        convert_to: Type[DtoType], dictionary: Dict[str, Any]
    ) -> DtoType:
        """
        Dacite conversion to DTO from JSON with handled exceptions
        :param convert_to: DTO type to return and validate against
        :return: DTO if JSON follows its structure, sends error response
            and connection ends otherwise
        """
        try:
            return from_dict(convert_to, dictionary, strict=True)
        except MissingValueError as exc:
            raise APIError(
                http_code=400,
                error_msg=f'Required key "{exc.field_path}" is missing in '
                f"request body.",
            ) from exc
        except UnexpectedDataError as exc:
            raise APIError(
                http_code=400,
                error_msg=f"Request body contains unexpected keys: "
                f"{', '.join(exc.keys)}.",
            ) from exc
        except DaciteError as exc:
            raise APIError(
                http_code=400, error_msg="Malformed request body."
            ) from exc

    def write_error(self, status_code: int, **kwargs: Any) -> None:
        """
        JSON error responder for all API handlers

        This function provides unified error response for the whole API. This
        function is called when tornado encounters any Exception while this
        handler is being used. No need to call set_status in this method, it is
        already set by tornado.
        :param status_code: HTTP status code
        """
        self.logger.exception("API error occured.")

        response = {
            "http_code": status_code,
            "http_error": responses.get(status_code, "Unknown"),
            "error_message": None,
        }
        if "exc_info" in kwargs:
            _, exc, _ = kwargs["exc_info"]
            if isinstance(exc, HTTPError) and exc.reason:
                # Rewrite http reason autoconverted from http status code
                response["http_error"] = exc.reason
            if isinstance(exc, APIError):
                response["error_message"] = exc.error_msg

        self.finish(json.dumps(response))

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        # We do not support HTTP chunk mode, reimplementing abstract
        pass


class NewTaskHandler(BaseAPIHandler):
    """Create a new task from command"""

    def post(self) -> None:
        if self.json is None:
            raise RequestBodyMissingError()

        command_dto = self._from_dict_exc_handled(CommandDto, self.json)
        task_ident = self.scheduler.new_task(command_dto)
        self.write(json.dumps(to_dict(TaskIdentDto(task_ident))))


class TaskInfoHandler(BaseAPIHandler):
    """Get task status"""

    def get(self) -> None:
        try:
            task_ident = self.get_query_argument("task_ident")
            self.write(
                json.dumps(
                    to_dict(self.scheduler.get_task(cast(str, task_ident)))
                )
            )
        except tornado.web.MissingArgumentError as exc:
            raise APIError(
                http_code=400,
                error_msg=f'URL argument "{exc.arg_name}" is missing.',
            ) from exc
        except TaskNotFoundError as exc:
            raise APIError(
                http_code=404,
                error_msg="Task with this identifier does not exist.",
            ) from exc


class KillTaskHandler(BaseAPIHandler):
    """Stop execution of a task"""

    def post(self) -> None:
        if self.json is None:
            raise RequestBodyMissingError()

        task_ident_dto = self._from_dict_exc_handled(TaskIdentDto, self.json)
        try:
            self.scheduler.kill_task(task_ident_dto.task_ident)
        except TaskNotFoundError as exc:
            raise APIError(
                http_code=404,
                error_msg="Task with this identifier does not exist.",
            ) from exc
        self.set_status(200)
        self.finish()


def get_routes(
    scheduler: Scheduler,
) -> List[Tuple[str, Type[BaseAPIHandler], dict]]:
    """
    Returns mapping of URL routes to functions and links API to the scheduler
    :param scheduler: Scheduler's instance
    :return: URL to handler mapping
    """
    params = dict(scheduler=scheduler)
    return [
        ("/async_api/task/result", TaskInfoHandler, params),
        ("/async_api/task/create", NewTaskHandler, params),
        ("/async_api/task/kill", KillTaskHandler, params),
    ]
