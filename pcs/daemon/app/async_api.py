import json
import logging
import re
import tornado

from tornado.web import RequestHandler
from typing import (
    Any,
    Dict,
    List,
    Tuple,
    Type,
)

from pcs.common.interface.dto import to_dict
from pcs.daemon.async_tasks.commands import Command
from pcs.daemon.async_tasks.dto import CommandDto, from_dict
from pcs.daemon.async_tasks.scheduler import TaskNotFoundError


class BaseAPIHandler(RequestHandler):
    """
    Base handler for the REST API

    Defines all common functions used by handlers, message body preprocessing,
    and HTTP(S) settings.
    """

    def initialize(self, scheduler: scheduler.Scheduler) -> None:
        self.scheduler = scheduler
        # TODO: Turn into a constant
        self.logger: logging.Logger = logging.getLogger("pcs_scheduler")

    def prepare(self) -> None:
        """JSON preprocessing"""
        self.add_header("Content-Type", "application/x-json")
        if (
            "Content-Type" in self.request.headers
            and self.request.headers["Content-Type"] == "application/x-json"
        ):
            try:
                self.json: Dict[str, Any] = json.loads(self.request.body)
            except json.JSONDecodeError:
                self.write_error(
                    400,
                    http_error="Bad Request",
                    error_msg="Malformed JSON data",
                )

    def write_error(
        self,
        status_code: int,
        http_error: str = None,
        error_msg: str = None,
        hints: str = None,
        **kwargs,
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
            response["http_code"] = status_code
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
                error_msg="Task assignment is missing",
            )
        # Simple data validation
        expected_keys: List[str] = ["command_name", "params"]
        if (
            len(self.json) != 2
            or list(self.json.keys()).sort() != expected_keys.sort()
        ):
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Malformed task assignment.",
            )

        command_dto = from_dict(CommandDto, self.json)

        task_ident = self.scheduler.new_task(Command.from_dto(command_dto))

        self.write(json.dumps(dict(task_ident=task_ident)))


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
            return
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

    def get(self) -> None:
        try:
            task_ident: str = self.get_query_argument("task_ident")
        except tornado.web.MissingArgumentError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Non-optional argument task_ident is missing.",
            )
            return None
        try:
            self.scheduler.kill_task(task_ident)
        except TaskNotFoundError:
            self.write_error(
                400,
                http_error="Bad Request",
                error_msg="Task with this task_ident does not exist.",
            )
        self.set_status(200)
        self.finish()


def get_routes(scheduler) -> List[Tuple[str, Type[BaseAPIHandler], dict]]:
    params = dict(scheduler=scheduler)
    return [
        ("/async_api/task/result", TaskInfoHandler, params),
        ("/async_api/task/create", NewTaskHandler, params),
        ("/async_api/task/kill", KillTaskHandler, params),
    ]
