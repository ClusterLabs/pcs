import json
import logging
from http.client import responses
from typing import Any, Optional, cast

from dacite import DaciteError, MissingValueError, UnexpectedDataError
from tornado.web import HTTPError, MissingArgumentError

from pcs.common.async_tasks.dto import CommandDto, TaskIdentDto
from pcs.common.interface.dto import (
    DTOTYPE,
    PayloadConversionError,
    from_dict,
    to_dict,
)
from pcs.daemon.app.auth_provider import (
    ApiAuthProviderFactoryInterface,
    ApiAuthProviderInterface,
    NotAuthorizedException,
)
from pcs.daemon.async_tasks.scheduler import Scheduler, TaskNotFoundError
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser

from .common import BaseHandler, RoutesType


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


class _BaseApiV2Handler(BaseHandler):
    """
    Base handler for the REST API

    Defines all common functions used by handlers, message body preprocessing,
    and HTTP(S) settings.
    """

    scheduler: Scheduler
    json: Optional[dict[str, Any]] = None
    logger: logging.Logger
    _auth_provider: ApiAuthProviderInterface
    _auth_user: AuthUser

    def initialize(
        self,
        scheduler: Scheduler,
        api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    ) -> None:
        super().initialize()
        self.scheduler = scheduler
        # TODO: Turn into a constant
        self.logger = logging.getLogger("pcs.daemon.scheduler")
        self._auth_provider = api_auth_provider_factory.create(self)

    async def prepare(self) -> None:
        self.set_header("Content-Type", "application/json")

        # Authentication
        try:
            self._auth_user = await self._auth_provider.auth_user()
        except NotAuthorizedException as e:
            raise APIError(http_code=401) from e

        # JSON preprocessing
        if (
            "Content-Type" in self.request.headers
            and self.request.headers["Content-Type"] == "application/json"
        ):
            try:
                self.json = json.loads(self.request.body)
            except json.JSONDecodeError as exc:
                raise APIError(
                    http_code=400, error_msg="Malformed JSON data."
                ) from exc

    @staticmethod
    def _from_dict_exc_handled(
        convert_to: type[DTOTYPE], dictionary: dict[str, Any]
    ) -> DTOTYPE:
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
        except (DaciteError, PayloadConversionError) as exc:
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
        self.set_header("Content-Type", "application/json")
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


class NewTaskHandler(_BaseApiV2Handler):
    """Create a new task from command"""

    async def post(self) -> None:
        if self.json is None:
            raise RequestBodyMissingError()

        command_dto = self._from_dict_exc_handled(CommandDto, self.json)
        task_ident = self.scheduler.new_task(
            Command(command_dto), self._auth_user
        )
        self.write(json.dumps(to_dict(TaskIdentDto(task_ident))))


class RunTaskHandler(_BaseApiV2Handler):
    """Run command synchronously"""

    async def post(self) -> None:
        if self.json is None:
            raise RequestBodyMissingError()

        command_dto = self._from_dict_exc_handled(CommandDto, self.json)
        task_ident = self.scheduler.new_task(
            Command(command_dto), self._auth_user
        )
        try:
            self.write(
                json.dumps(
                    to_dict(
                        await self.scheduler.wait_for_task(
                            task_ident, self._auth_user
                        )
                    )
                )
            )
        except TaskNotFoundError as exc:
            raise APIError(http_code=500) from exc


class TaskInfoHandler(_BaseApiV2Handler):
    """Get task status"""

    async def get(self) -> None:
        try:
            task_ident = self.get_query_argument("task_ident")
            self.write(
                json.dumps(
                    to_dict(
                        self.scheduler.get_task(
                            cast(str, task_ident), self._auth_user
                        )
                    )
                )
            )
        except MissingArgumentError as exc:
            raise APIError(
                http_code=400,
                error_msg=f'URL argument "{exc.arg_name}" is missing.',
            ) from exc
        except TaskNotFoundError as exc:
            raise APIError(
                http_code=404,
                error_msg="Task with this identifier does not exist.",
            ) from exc


class KillTaskHandler(_BaseApiV2Handler):
    """Stop execution of a task"""

    async def post(self) -> None:
        if self.json is None:
            raise RequestBodyMissingError()

        task_ident_dto = self._from_dict_exc_handled(TaskIdentDto, self.json)
        try:
            self.scheduler.kill_task(task_ident_dto.task_ident, self._auth_user)
        except TaskNotFoundError as exc:
            raise APIError(
                http_code=404,
                error_msg="Task with this identifier does not exist.",
            ) from exc
        self.set_status(200)
        self.finish()


def get_routes(
    api_auth_provider_factory: ApiAuthProviderFactoryInterface,
    scheduler: Scheduler,
) -> RoutesType:
    """
    Returns mapping of URL routes to functions and links API to the scheduler
    :param scheduler: Scheduler's instance
    :return: URL to handler mapping
    """
    params = dict(
        api_auth_provider_factory=api_auth_provider_factory, scheduler=scheduler
    )
    return [
        ("/api/v2/task/result", TaskInfoHandler, params),
        ("/api/v2/task/create", NewTaskHandler, params),
        ("/api/v2/task/kill", KillTaskHandler, params),
        ("/api/v2/task/run", RunTaskHandler, params),
    ]
