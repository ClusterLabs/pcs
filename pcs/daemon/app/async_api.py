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

from pcs.common.interface.dto import DataTransferObject, from_dict, to_dict
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

    def from_dict_exc_handled(
        self, convert_to: Type[DataTransferObject]
    ) -> DataTransferObject:
        try:
            dto = from_dict(convert_to, self.json, strict=True)
        except MissingValueError as exc:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg=f"Required value {exc.field_path} is missing.",
            )
        except UnexpectedDataError as exc:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg=f"Unexpected data ({', '.join(exc.keys)}) in "
                f"request body.",
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
        if not self.json:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task assignment is missing.",
            )

        try:
            command_dto = from_dict(CommandDto, self.json, strict=True)
        except MissingValueError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Required value of task assignment is missing.",
            )
            return
        except UnexpectedDataError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Unexpected data in task assignment.",
            )
            return
        except DaciteError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed task assignment.",
            )
            return

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
                error_msg="Non-optional argument task_ident is missing.",
            )
        try:
            self.write(json.dumps(to_dict(self.scheduler.get_task(task_ident))))
        except TaskNotFoundError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task with this task_ident does not exist.",
            )


class KillTaskHandler(BaseAPIHandler):
    """Stop execution of a task"""

    def post(self) -> None:
        if not self.json:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task assignment is missing.",
            )

        try:
            task_ident_dto = from_dict(TaskIdentDto, self.json, strict=True)
        except MissingValueError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task_ident is missing.",
            )
            return
        except UnexpectedDataError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Unexpected data in request body.",
            )
            return
        except DaciteError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed request body.",
            )
            return
        try:
            self.scheduler.kill_task(task_ident_dto.task_ident)
        except TaskNotFoundError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task with this task_ident does not exist.",
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
