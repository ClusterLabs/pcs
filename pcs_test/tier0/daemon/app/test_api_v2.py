import json
import logging
from typing import Any
from unittest import mock

from tornado.httpclient import HTTPResponse
from tornado.web import Application

from pcs.common.async_tasks.dto import (
    CommandDto,
    CommandOptionsDto,
    TaskResultDto,
)
from pcs.common.async_tasks.types import (
    TaskFinishType,
    TaskKillReason,
    TaskState,
)
from pcs.daemon.app import api_v2
from pcs.daemon.async_tasks.scheduler import Scheduler, TaskNotFoundError
from pcs.daemon.async_tasks.types import Command

from pcs_test.tier0.daemon.app.fixtures_app_api import (
    ApiTestBase,
    MockAuthProviderFactory,
)

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class _TestHandler(api_v2._BaseApiV2Handler):
    """
    Minimal concrete handler for testing base class functionality.
    """

    async def post(self) -> None:
        """Echo back parsed JSON for testing base class functionality"""
        if self.json is None:
            raise api_v2.RequestBodyMissingError()
        # test DTO validation
        command_dto = self._from_dict_exc_handled(CommandDto, self.json)
        self.write(
            json.dumps(
                {
                    "success": True,
                    "user": self._auth_user.username,
                    "command": command_dto.command_name,
                }
            )
        )


class ApiV2Test(ApiTestBase):
    """
    Base class for testing API v2, provides useful tools used in tests
    """

    def setUp(self) -> None:
        self.scheduler = mock.AsyncMock(Scheduler)
        self.auth_provider_factory = MockAuthProviderFactory()
        super().setUp()

    def get_app(self) -> Application:
        return Application(
            api_v2.get_routes(self.auth_provider_factory, self.scheduler)
        )

    def fetch(
        self, path: str, raise_error: bool = False, **kwargs: Any
    ) -> HTTPResponse:
        if "headers" not in kwargs:
            kwargs["headers"] = {"Content-Type": "application/json"}

        response = super().fetch(
            path,
            raise_error,
            method=("GET" if kwargs.get("body") is None else "POST"),
            **kwargs,
        )

        # check that response always contains required security headers
        self.assert_headers(response.headers)
        return response

    @staticmethod
    def make_command_dict(
        command_name: str = "test.command",
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "command_name": command_name,
            "params": params or {"param1": "value1"},
            "options": options
            or {
                "effective_username": "hacluster",
                "effective_groups": ["haclient"],
            },
        }

    @staticmethod
    def make_command_dto(
        command_name: str = "test.command",
        params: dict[str, Any] | None = None,
        options: CommandOptionsDto | None = None,
    ) -> dict[str, Any]:
        return CommandDto(
            command_name=command_name,
            params=params or {"param1": "value1"},
            options=options
            or CommandOptionsDto(
                effective_username="hacluster", effective_groups=["haclient"]
            ),
        )

    @staticmethod
    def make_task_result_dto(
        task_ident: str = "task-123",
        command_name: str = "test.command",
        state: TaskState = TaskState.FINISHED,
        finish_type: TaskFinishType = TaskFinishType.SUCCESS,
        result: Any = None,
        report_list: list | None = None,
        kill_reason: TaskKillReason | None = None,
    ) -> TaskResultDto:
        return TaskResultDto(
            task_ident=task_ident,
            command=CommandDto(
                command_name=command_name,
                params={"param1": "value1"},
                options=CommandOptionsDto(
                    effective_username="hacluster",
                    effective_groups=["haclient"],
                ),
            ),
            reports=report_list or [],
            state=state,
            task_finish_type=finish_type,
            kill_reason=kill_reason,
            result=result,
        )

    def assert_json_response(
        self,
        response: HTTPResponse,
        expected_code: int,
        expected_keys: list[str] | None = None,
    ) -> dict[str, Any]:
        self.assertEqual(response.code, expected_code)
        self.assertEqual(
            response.headers.get("Content-Type"), "application/json"
        )
        data = json.loads(response.body)
        if expected_keys:
            self.assertEqual(sorted(data.keys()), sorted(expected_keys))
        return data

    def assert_success_response(self, response: HTTPResponse) -> dict[str, Any]:
        return self.assert_json_response(
            response,
            200,
            [
                "task_ident",
                "command",
                "reports",
                "state",
                "task_finish_type",
                "kill_reason",
                "result",
            ],
        )

    def assert_error_response(
        self,
        response: HTTPResponse,
        expected_code: int,
        expected_message: str | None = None,
    ) -> None:
        data = self.assert_json_response(
            response,
            expected_code,
            ["http_code", "http_error", "error_message"],
        )
        self.assertEqual(data["http_code"], expected_code)
        if expected_message:
            self.assertEqual(data["error_message"], expected_message)


class BaseApiV2HandlerTest(ApiV2Test):
    url = "/test"

    def get_app(self) -> Application:
        params = dict(
            api_auth_provider_factory=self.auth_provider_factory,
            scheduler=self.scheduler,
        )
        routes = [(self.url, _TestHandler, params)]
        return Application(routes)

    def test_authentication_success(self):
        response = self.fetch(
            self.url, body=json.dumps(self.make_command_dict())
        )

        data = self.assert_json_response(response, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["user"], "hacluster")
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_authentication_failure_auth_user_raises(self):
        self.auth_provider_factory.auth_result = "not_authorized"

        response = self.fetch(
            self.url, body=json.dumps(self.make_command_dict())
        )

        self.assert_error_response(response, 401)
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_malformed_json(self):
        response = self.fetch(self.url, body="not valid json")

        self.assert_error_response(response, 400, "Malformed JSON data.")
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_wrong_content_type(self):
        response = self.fetch(
            self.url,
            body=json.dumps(self.make_command_dict()),
            headers={"Content-Type": "text/plain"},
        )

        self.assert_error_response(
            response,
            400,
            "Request body is missing, has wrong format or wrong/missing headers.",
        )
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_missing_required_field(self):
        for field in ["command_name", "params", "options"]:
            with self.subTest(field=field):
                command_dict = self.make_command_dict()
                del command_dict[field]

                response = self.fetch(self.url, body=json.dumps(command_dict))

                self.assert_error_response(
                    response,
                    400,
                    f'Required key "{field}" is missing in request body.',
                )
                self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_unexpected_field(self):
        command_dict = self.make_command_dict()
        command_dict["unexpected_field"] = "value"

        response = self.fetch(self.url, body=json.dumps(command_dict))

        self.assert_error_response(
            response,
            400,
            "Request body contains unexpected keys: unexpected_field.",
        )
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_type_mismatch(self):
        command_dict = self.make_command_dict()
        command_dict["params"] = "not a dict"  # Should be a dict

        response = self.fetch(self.url, body=json.dumps(command_dict))

        self.assert_error_response(response, 400, "Malformed request body.")
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_validation_with_nested_dto(self):
        command_dict = self.make_command_dict()
        command_dict["options"]["unexpected_nested_field"] = "value"

        response = self.fetch(self.url, body=json.dumps(command_dict))

        self.assert_error_response(
            response,
            400,
            "Request body contains unexpected keys: unexpected_nested_field.",
        )
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_empty_params(self):
        command_dict = self.make_command_dict(params={})

        response = self.fetch(self.url, body=json.dumps(command_dict))

        data = self.assert_json_response(response, 200)
        self.assertEqual(data["success"], True)
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()


class NewTaskHandlerTest(ApiV2Test):
    url = "/api/v2/task/create"

    def tearDown(self):
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_success(self):
        self.scheduler.new_task.return_value = "task-123"

        response = self.fetch(
            self.url, body=json.dumps(self.make_command_dict())
        )

        data = self.assert_json_response(response, 200, ["task_ident"])
        self.assertEqual(data["task_ident"], "task-123")
        self.scheduler.new_task.assert_called_once_with(
            Command(self.make_command_dto()), self.auth_provider_factory.user
        )

    def test_no_json_in_body(self):
        response = self.fetch(self.url, body="", headers={})

        self.assert_error_response(
            response,
            400,
            "Request body is missing, has wrong format or wrong/missing headers.",
        )
        self.scheduler.new_task.assert_not_called()


class RunTaskHandlerTest(ApiV2Test):
    url = "/api/v2/task/run"

    def tearDown(self):
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_success(self):
        self.scheduler.new_task.return_value = "task-123"
        self.scheduler.wait_for_task.return_value = self.make_task_result_dto(
            task_ident="task-123", result="command result"
        )

        response = self.fetch(
            self.url, body=json.dumps(self.make_command_dict())
        )

        data = self.assert_success_response(response)
        self.assertEqual(data["task_ident"], "task-123")
        self.assertEqual(data["result"], "command result")
        self.scheduler.new_task.assert_called_once_with(
            Command(self.make_command_dto()), self.auth_provider_factory.user
        )
        self.scheduler.wait_for_task.assert_called_once_with(
            "task-123", self.auth_provider_factory.user
        )

    def test_no_json_in_body(self):
        response = self.fetch(self.url, body="", headers={})

        self.assert_error_response(
            response,
            400,
            "Request body is missing, has wrong format or wrong/missing headers.",
        )
        self.scheduler.new_task.assert_not_called()
        self.scheduler.wait_for_task.assert_not_called()

    def test_task_not_found_error(self):
        self.scheduler.new_task.return_value = "task-123"
        self.scheduler.wait_for_task.side_effect = TaskNotFoundError("task-123")

        response = self.fetch(
            self.url, body=json.dumps(self.make_command_dict())
        )

        self.assert_error_response(response, 500)
        self.scheduler.new_task.assert_called_once_with(
            Command(self.make_command_dto()), self.auth_provider_factory.user
        )
        self.scheduler.wait_for_task.assert_called_once_with(
            "task-123", self.auth_provider_factory.user
        )


class TaskInfoHandlerTest(ApiV2Test):
    url = "/api/v2/task/result"

    def tearDown(self):
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_success(self):
        self.scheduler.get_task.return_value = self.make_task_result_dto(
            task_ident="task-123"
        )

        response = self.fetch(f"{self.url}?task_ident=task-123", headers={})

        data = self.assert_success_response(response)
        self.assertEqual(data["task_ident"], "task-123")
        self.scheduler.get_task.assert_called_once_with(
            "task-123", self.auth_provider_factory.user
        )

    def test_missing_query_argument(self):
        response = self.fetch(self.url, headers={})

        self.assert_error_response(
            response, 400, 'URL argument "task_ident" is missing.'
        )
        self.scheduler.get_task.assert_not_called()

    def test_task_not_found(self):
        self.scheduler.get_task.side_effect = TaskNotFoundError(
            "nonexistent-task"
        )

        response = self.fetch(
            f"{self.url}?task_ident=nonexistent-task", headers={}
        )

        self.assert_error_response(
            response, 404, "Task with this identifier does not exist."
        )
        self.scheduler.get_task.assert_called_once_with(
            "nonexistent-task", self.auth_provider_factory.user
        )


class KillTaskHandlerTest(ApiV2Test):
    url = "/api/v2/task/kill"

    def tearDown(self):
        self.auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_success(self):
        response = self.fetch(
            self.url, body=json.dumps({"task_ident": "task-123"})
        )

        self.assertEqual(response.code, 200)
        self.assertEqual(response.body, b"")
        self.scheduler.kill_task.assert_called_once_with(
            "task-123", self.auth_provider_factory.user
        )

    def test_no_json_in_body(self):
        response = self.fetch(self.url, body="", headers={})

        self.assert_error_response(
            response,
            400,
            "Request body is missing, has wrong format or wrong/missing headers.",
        )
        self.scheduler.kill_task.assert_not_called()

    def test_task_not_found(self):
        self.scheduler.kill_task.side_effect = TaskNotFoundError(
            "nonexistent-task"
        )

        response = self.fetch(
            self.url, body=json.dumps({"task_ident": "nonexistent-task"})
        )

        self.assert_error_response(
            response, 404, "Task with this identifier does not exist."
        )
        self.scheduler.kill_task.assert_called_once_with(
            "nonexistent-task", self.auth_provider_factory.user
        )
