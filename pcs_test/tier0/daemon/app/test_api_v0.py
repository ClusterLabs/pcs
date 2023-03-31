import json
import logging
from typing import (
    Any,
    Optional,
)
from unittest import mock
from urllib.parse import urlencode

from tornado.httpclient import HTTPResponse
from tornado.httputil import HTTPHeaders
from tornado.testing import AsyncHTTPTestCase
from tornado.web import Application

from pcs.common import reports
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
from pcs.common.tools import bin_to_str
from pcs.daemon.app import api_v0
from pcs.daemon.async_tasks.scheduler import (
    Scheduler,
    TaskNotFoundError,
)
from pcs.daemon.async_tasks.types import Command
from pcs.lib.auth.types import AuthUser

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class MockAuthProvider:
    auth_successful: bool = True
    user = AuthUser("hacluster", ["haclient"])

    def auth_by_token(self, token: str) -> Optional[AuthUser]:
        del token
        return self.user if self.auth_successful else None


class ApiV0Test(AsyncHTTPTestCase):
    """
    Base class for testing API v0, provides useful tools used in tests
    """

    maxDiff = None

    def setUp(self) -> None:
        self.scheduler = mock.AsyncMock(Scheduler)
        self.auth_provider = MockAuthProvider()
        super().setUp()

    def get_app(self) -> Application:
        raise NotImplementedError

    def assert_body(self, val1, val2):
        # TestCase.assertEqual doesn't print full diff when instances of bytes
        # don't match. We want to see the whole diff, so we transform bytes to
        # str. As a bonus, we dont need to specify expected value as bytes.
        def to_str(value):
            return bin_to_str(value) if isinstance(value, bytes) else value

        return self.assertEqual(to_str(val1), to_str(val2))

    def assert_headers(self, headers: HTTPHeaders) -> None:
        banned_headers = {"Server"}
        required_headers = {
            "Cache-Control": "no-store, no-cache",
            "Content-Security-Policy": "frame-ancestors 'self'; default-src 'self'",
            "Pragma": "no-cache",
            "Referrer-Policy": "no-referrer",
            "Strict-Transport-Security": "max-age=63072000",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "SAMEORIGIN",
            "X-Xss-Protection": "1; mode=block",
        }
        required_real_headers = [
            hdr for hdr in headers.get_all() if hdr[0] in required_headers
        ]
        banned_real_headers = {
            hdr[0] for hdr in headers.get_all() if hdr[0] in banned_headers
        }
        self.assertEqual(
            sorted(required_headers.items()),
            sorted(required_real_headers),
            "Required headers are not present",
        )
        self.assertEqual(
            sorted(banned_real_headers), [], "Banned headers are present"
        )

    def fetch(
        self,
        path: str,
        raise_error: bool = False,
        add_token: bool = True,
        **kwargs: Any,
    ) -> HTTPResponse:
        if add_token:
            # pretends a token was sent in a cookie, so that daemon's
            # authentication mechanism tries to log in a user by the token and
            # calls AuthProvider.auth_by_token
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            if "Cookie" not in kwargs["headers"]:
                kwargs["headers"]["Cookie"] = "token=some-valid-pcsd-token"
            else:
                kwargs["headers"]["Cookie"] += ";token=some-valid-pcsd-token"

        response = super().fetch(
            path,
            raise_error,
            method=("GET" if kwargs.get("body", None) is None else "POST"),
            **kwargs,
        )
        self.assert_headers(response.headers)
        return response


class BaseApiV0Handler(ApiV0Test):
    """
    Tests of _BaseApiV0Handler class
    """

    url = "/test"
    cmd_name = "test.command"
    cmd_params = {"test": "params"}
    task_ident = "task-ident"
    command_executed = True

    class HandlerForTest(api_v0._BaseApiV0Handler):
        # pylint: disable=protected-access

        def initialize(self, scheduler, auth_provider, cmd_name, cmd_params):
            # pylint: disable=arguments-differ
            # pylint: disable=attribute-defined-outside-init
            super().initialize(scheduler, auth_provider)
            self.cmd_name = cmd_name
            self.cmd_params = cmd_params

        async def _handle_request(self):
            result = await self._process_request(self.cmd_name, self.cmd_params)
            messages = [
                report_item.message.message for report_item in result.reports
            ]
            self.write(
                f"success: {result.success}\n"
                f"result: {result.result}\n"
                f"reports: {messages}\n"
            )

    def get_app(self) -> Application:
        return Application(
            [
                (
                    self.url,
                    self.HandlerForTest,
                    dict(
                        cmd_name=self.cmd_name,
                        cmd_params=self.cmd_params,
                        scheduler=self.scheduler,
                        auth_provider=self.auth_provider,
                    ),
                )
            ]
        )

    def setUp(self):
        super().setUp()
        self.command_dto = CommandDto(
            command_name=self.cmd_name,
            params=self.cmd_params,
            options=CommandOptionsDto(
                effective_username=self.auth_provider.user.username,
                effective_groups=self.auth_provider.user.groups,
            ),
        )
        self.scheduler.new_task.return_value = self.task_ident
        self.addCleanup(self.assert_scheduler_calls)

    def assert_scheduler_calls(self):
        if self.command_executed:
            self.scheduler.new_task.assert_called_once_with(
                Command(self.command_dto, is_legacy_command=True),
                self.auth_provider.user,
            )
            self.scheduler.wait_for_task.assert_called_once_with(
                self.task_ident, self.auth_provider.user
            )

    def test_success(self):
        self.scheduler.wait_for_task.return_value = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingFailed("an error"),
                ).to_dto()
            ],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.SUCCESS,
            kill_reason=None,
            result="some result of the command",
        )

        response = self.fetch(self.url)
        self.assert_body(
            response.body,
            (
                "success: True\n"
                "result: some result of the command\n"
                "reports: ['Unfencing failed:\\nan error']\n"
            ),
        )
        self.assertEqual(response.code, 200)

    def test_task_not_found(self):
        self.scheduler.wait_for_task.side_effect = TaskNotFoundError(
            self.task_ident
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Internal server error")
        self.assertEqual(response.code, 500)

    def test_not_authorized(self):
        self.auth_provider.auth_successful = False
        self.command_executed = False

        response = self.fetch(self.url)
        self.assert_body(response.body, '{"notauthorized":"true"}')
        self.assertEqual(response.code, 401)

    def test_permission_denied(self):
        self.scheduler.wait_for_task.return_value = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[
                reports.ReportItem.error(
                    reports.messages.NotAuthorized()
                ).to_dto()
            ],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.FAIL,
            kill_reason=None,
            result=None,
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Permission denied")
        self.assertEqual(response.code, 403)

    def test_task_timeout(self):
        self.scheduler.wait_for_task.return_value = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.KILL,
            kill_reason=TaskKillReason.COMPLETION_TIMEOUT,
            result=None,
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Task processing timed out")
        self.assertEqual(response.code, 500)

    def test_task_killed(self):
        self.scheduler.wait_for_task.return_value = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.KILL,
            kill_reason=None,
            result=None,
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Task killed")
        self.assertEqual(response.code, 400)

    def test_task_exception(self):
        self.scheduler.wait_for_task.return_value = TaskResultDto(
            task_ident=self.task_ident,
            command=self.command_dto,
            reports=[],
            state=TaskState.FINISHED,
            task_finish_type=TaskFinishType.UNHANDLED_EXCEPTION,
            kill_reason=None,
            result=None,
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Unhandled exception")
        self.assertEqual(response.code, 500)


class ApiV0HandlerTest(ApiV0Test):
    """
    Base class for testing _BaseApiV0Handler descendants
    """

    def setUp(self):
        super().setUp()
        self.mock_process_request = mock.AsyncMock()
        process_request_patcher = mock.patch.object(
            # pylint: disable=protected-access
            api_v0._BaseApiV0Handler,
            "_process_request",
            self.mock_process_request,
        )
        process_request_patcher.start()
        self.addCleanup(process_request_patcher.stop)

    def get_app(self) -> Application:
        return Application(
            api_v0.get_routes(self.scheduler, self.auth_provider)
        )

    @staticmethod
    def result_success(result: Any = None) -> api_v0.SimplifiedResult:
        return api_v0.SimplifiedResult(True, result, [])

    @staticmethod
    def result_failure(
        result: Any = None,
        report_items: Optional[list[reports.ReportItemDto]] = None,
    ) -> api_v0.SimplifiedResult:
        return api_v0.SimplifiedResult(False, result, report_items or [])

    def assert_error_with_report(self, url, **kwargs):
        # Test that the handler returns http 400 and report items in body. The
        # actual report items don't matter, we can pick any simple report item.
        self.mock_process_request.return_value = self.result_failure(
            "some error",
            [
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingFailed("an error"),
                    context=reports.ReportItemContext("node1"),
                ).to_dto()
            ],
        )
        response = self.fetch(url, **kwargs)
        self.assert_body(
            response.body, "Error: node1: Unfencing failed:\nan error"
        )
        self.assertEqual(response.code, 400)


class ResourceManageUnmanageMixin:
    body_data = {"resource_list_json": json.dumps(["resource1", "resource2"])}
    command_data = {"resource_or_tag_ids": ["resource1", "resource2"]}

    def test_success(self):
        self.mock_process_request.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            self.command_name, self.command_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'resource_list_json'"
        )
        self.assertEqual(response.code, 400)
        self.mock_process_request.assert_not_called()

    def test_json_parse_error(self):
        response = self.fetch(
            self.url, body=urlencode({"resource_list_json": "not a json"})
        )
        self.assert_body(response.body, "Invalid input data format")
        self.assertEqual(response.code, 400)
        self.mock_process_request.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_process_request.assert_called_once_with(
            self.command_name, self.command_data
        )


class ResourceManageHandler(ResourceManageUnmanageMixin, ApiV0HandlerTest):
    url = "/remote/manage_resource"
    command_name = "resource.manage"


class ResourceUnmanageHandler(ResourceManageUnmanageMixin, ApiV0HandlerTest):
    url = "/remote/unmanage_resource"
    command_name = "resource.unmanage"


class QdeviceNetGetCaCertificateHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_get_ca_certificate"

    def test_success(self):
        self.mock_process_request.return_value = self.result_success(
            "certificate data"
        )
        response = self.fetch(self.url)
        self.assert_body(response.body, "certificate data")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_process_request.assert_called_once_with(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )


class QdeviceNetSignNodeCertificateHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_sign_node_certificate"
    body_data = {
        "certificate_request": "base64 certificate data",
        "cluster_name": "my-cluster",
    }

    def test_success(self):
        self.mock_process_request.return_value = self.result_success(
            "signed certificate data"
        )
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "signed certificate data")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            "qdevice.qdevice_net_sign_certificate_request", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body,
            "Required parameters missing: 'certificate_request', 'cluster_name'",
        )
        self.assertEqual(response.code, 400)
        self.mock_process_request.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_process_request.assert_called_once_with(
            "qdevice.qdevice_net_sign_certificate_request", self.body_data
        )


class QdeviceNetClientInitCertificateStorageHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_init_certificate_storage"
    body_data = {"ca_certificate": "base64 certificate data"}

    def test_success(self):
        self.mock_process_request.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_setup", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'ca_certificate'"
        )
        self.assertEqual(response.code, 400)
        self.mock_process_request.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_setup", self.body_data
        )


class QdeviceNetClientImportCertificateHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_import_certificate"
    body_data = {"certificate": "base64 certificate data"}

    def test_success(self):
        self.mock_process_request.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_import_certificate", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'certificate'"
        )
        self.assertEqual(response.code, 400)
        self.mock_process_request.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_import_certificate", self.body_data
        )


class QdeviceNetClientDestroyHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_destroy"

    def test_success(self):
        self.mock_process_request.return_value = self.result_success()
        response = self.fetch(self.url)
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_destroy", {}
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_process_request.assert_called_once_with(
            "qdevice.client_net_destroy", {}
        )
