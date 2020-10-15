import json
import logging

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
)

import tornado

from dacite import DaciteError, MissingValueError, UnexpectedDataError
from tornado.web import RequestHandler

from pcs.common.interface.dto import (
    DtoType,
    from_dict,
    to_dict,
)
from pcs.common.async_tasks.dto import CommandDto, TaskIdentDto
from pcs.daemon.async_tasks.scheduler import Scheduler, TaskNotFoundError


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
        self.add_header("Content-Type", "application/json")
        if (
            "Content-Type" in self.request.headers
            and self.request.headers["Content-Type"] == "application/json"
        ):
            try:
                self.json = json.loads(self.request.body)
            except json.JSONDecodeError:
                self.write_error(
                    400,
                    http_error="Bad Request",
                    error_msg="Malformed JSON data.",
                )

    def _from_dict_exc_handled(self, convert_to: Type[DtoType]) -> DtoType:
        """
        Dacite conversion to DTO from JSON with handled exceptions
        :param convert_to: DTO type to return and validate against
        :return: DTO if JSON follows its structure, sends error response
            and connection ends otherwise
        """
        try:
            dto = from_dict(convert_to, self.json, strict=True)
        except MissingValueError as exc:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg=f"Required key {exc.field_path} is missing.",
            )
        except UnexpectedDataError as exc:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg=f"Request body contains unexpected keys: "
                f"{', '.join(exc.keys)}.",
            )
        except DaciteError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed request body.",
            )
        return dto

    def write_error(
        self,
        status_code: int,
        http_error: str = None,
        error_msg: str = None,
        hints: str = None,
        **kwargs: Any,
    ) -> None:
        """
        Error responder for all handlers

        This function provides unified error response for the whole API. This
        format must be used for all errors returned to the client.
        :param status_code: HTTP status code
        :param http_error: HTTP error name
        :param error_msg: Detailed error description
        :param hints: Text that suggests how to remedy this error
        """
        self.logger.exception("API error occured.")

        self.set_status(status_code, http_error)
        response: Dict[str, str] = {}
        if status_code:
            response["http_code"] = str(status_code)
        if http_error:
            response["http_error"] = http_error
        if error_msg:
            response["error_message"] = error_msg
        if hints:
            response["hints"] = hints
        self.write(json.dumps(response))
        self.finish()


class NewTaskHandler(BaseAPIHandler):
    """Create a new task from command"""

    def post(self) -> None:
        if self.json is None:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task assignment is missing.",
            )

        command_dto = self._from_dict_exc_handled(CommandDto)
        task_ident = self.scheduler.new_task(command_dto)
        self.write(json.dumps(to_dict(TaskIdentDto(task_ident))))


class TaskInfoHandler(BaseAPIHandler):
    """Get task status"""

    def get(self) -> None:
        try:
            task_ident = self.get_query_argument("task_ident")
        except tornado.web.MissingArgumentError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task identifier (task_ident) is missing.",
            )
        try:
            self.write(json.dumps(to_dict(self.scheduler.get_task(task_ident))))
        except TaskNotFoundError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task with this identifier does not exist.",
            )


class KillTaskHandler(BaseAPIHandler):
    """Stop execution of a task"""

    def post(self) -> None:
        if self.json is None:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task identifier is missing.",
            )

        task_ident_dto = self._from_dict_exc_handled(TaskIdentDto)
        try:
            self.scheduler.kill_task(task_ident_dto.task_ident)
        except TaskNotFoundError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task with this identifier does not exist.",
            )
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
