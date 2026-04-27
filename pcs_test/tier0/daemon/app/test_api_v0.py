import base64
import json
import logging
from typing import Any
from unittest import mock
from urllib.parse import urlencode

from tornado.httpclient import HTTPResponse
from tornado.locks import Lock
from tornado.util import TimeoutError as TornadoTimeoutError
from tornado.web import Application

from pcs import settings
from pcs.common import file_type_codes, reports
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
from pcs.common.booth_dto import (
    BoothConfigAndAuthfileDto,
    BoothConfigFileDto,
)
from pcs.common.cluster_dto import (
    ClusterComponentVersionDto,
    ClusterDaemonsInfoDto,
)
from pcs.common.file import RawFileError
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.version_dto import VersionDto
from pcs.daemon.app import api_v0
from pcs.daemon.async_tasks.scheduler import Scheduler, TaskNotFoundError
from pcs.daemon.async_tasks.types import Command

from pcs_test.tier0.daemon.app.fixtures_app_api import (
    ApiTestBase,
    MockAuthProviderFactory,
)

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class ApiV0Test(ApiTestBase):
    """
    Base class for testing API v0, provides useful tools used in tests
    """

    def setUp(self) -> None:
        self.scheduler = mock.AsyncMock(Scheduler)
        self.api_auth_provider_factory = MockAuthProviderFactory()
        self.sync_config_lock = Lock()
        super().setUp()

    def get_app(self) -> Application:
        raise NotImplementedError

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
            method=("GET" if kwargs.get("body") is None else "POST"),
            **kwargs,
        )
        self.assert_headers(response.headers)
        return response

    def assert_error_with_report(self, url, **kwargs):
        """
        Test that the handler returns http 400 and report items in body.
        This method requires self.mock_process_request to be set up.
        """
        # The actual report items don't matter, we can pick any simple report item.
        self.mock_run_library_command.return_value = self.result_failure(
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

        def initialize(
            self, api_auth_provider_factory, scheduler, cmd_name, cmd_params
        ):
            # pylint: disable=arguments-differ
            # pylint: disable=attribute-defined-outside-init
            super().initialize(api_auth_provider_factory, scheduler)
            self.cmd_name = cmd_name
            self.cmd_params = cmd_params

        async def _handle_request(self):
            result = await self._run_library_command(
                self.cmd_name, self.cmd_params
            )
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
                        api_auth_provider_factory=self.api_auth_provider_factory,
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
                effective_username=None, effective_groups=None
            ),
        )
        self.scheduler.new_task.return_value = self.task_ident
        self.addCleanup(self.assert_scheduler_calls)

    def assert_scheduler_calls(self):
        if self.command_executed:
            self.scheduler.new_task.assert_called_once_with(
                Command(self.command_dto, is_legacy_command=True),
                self.api_auth_provider_factory.user,
            )
            self.scheduler.wait_for_task.assert_called_once_with(
                self.task_ident, self.api_auth_provider_factory.user
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
        self.api_auth_provider_factory.provider.auth_user.assert_called_once_with()

    def test_task_not_found(self):
        self.scheduler.wait_for_task.side_effect = TaskNotFoundError(
            self.task_ident
        )

        response = self.fetch(self.url)
        self.assert_body(response.body, "Internal server error")
        self.assertEqual(response.code, 500)

    def test_not_authorized(self):
        self.api_auth_provider_factory.auth_result = "not_authorized"
        self.command_executed = False

        response = self.fetch(self.url)
        self.assert_body(response.body, '{"notauthorized":"true"}')
        self.assertEqual(response.code, 401)
        self.api_auth_provider_factory.provider.auth_user.assert_called_once_with()

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

    def test_success_with_effective_user(self):
        self.command_dto = CommandDto(
            command_name=self.cmd_name,
            params=self.cmd_params,
            options=CommandOptionsDto(
                effective_username="foo",
                effective_groups=["haclient", "wheel", "square"],
            ),
        )
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

        groups_encoded = base64.b64encode(
            "haclient wheel square".encode("utf-8")
        ).decode("utf-8")
        response = self.fetch(
            self.url,
            headers={
                "Cookie": f"CIB_user=foo;CIB_user_groups={groups_encoded}"
            },
        )
        self.assert_body(
            response.body,
            (
                "success: True\n"
                "result: some result of the command\n"
                "reports: ['Unfencing failed:\\nan error']\n"
            ),
        )
        self.assertEqual(response.code, 200)


class ApiV0HandlerTest(ApiV0Test):
    """
    Base class for testing _BaseApiV0Handler descendants
    """

    def setUp(self):
        super().setUp()
        self.mock_run_library_command = mock.AsyncMock()
        run_library_command_patcher = mock.patch.object(
            # pylint: disable=protected-access
            api_v0._BaseApiV0Handler,
            "_run_library_command",
            self.mock_run_library_command,
        )
        run_library_command_patcher.start()
        self.addCleanup(run_library_command_patcher.stop)

    def get_app(self) -> Application:
        return Application(
            api_v0.get_routes(
                self.api_auth_provider_factory,
                self.scheduler,
                self.sync_config_lock,
            )
        )


class ManageServicesHandler(ApiV0HandlerTest):
    url = "/remote/manage_services"

    def fixture_body(self, data_json: str) -> str:
        return urlencode({"data_json": data_json})

    @staticmethod
    def fixture_action(
        type: str = "service_command",  # noqa: A002 `type` is shadowing a builtin
        service: str = "pacemaker_remote",
        command: str = "start",
    ) -> dict[str, str]:
        return {"type": type, "service": service, "command": command}

    def test_missing_data_json(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'data_json'"
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_invalid_json(self):
        response = self.fetch(
            self.url, body=self.fixture_body("not valid json")
        )
        self.assert_body(response.body, "Invalid input data format")
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_actions_not_dict(self):
        response = self.fetch(self.url, body=self.fixture_body("[]"))
        self.assert_body(
            response.body,
            "Invalid input data format: actions should be 'dict'. "
            "But it is 'list': []",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_action_not_dict(self):
        response = self.fetch(
            self.url, body=self.fixture_body(json.dumps({"a1": "string"}))
        )
        self.assert_body(
            response.body,
            "Invalid input data format: action (key: a1): "
            "should be 'dict'. But it is 'str': \"string\"",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_missing_required_key(self):
        for missing_key in self.fixture_action():
            with self.subTest(missing_key=missing_key):
                self.mock_run_library_command.reset_mock()
                action = self.fixture_action()
                del action[missing_key]
                response = self.fetch(
                    self.url,
                    body=self.fixture_body(json.dumps({"a1": action})),
                )
                self.assert_body(
                    response.body,
                    f"Invalid input data format: action (key: a1): "
                    f"'{missing_key}' is missing",
                )
                self.assertEqual(response.code, 400)
                self.mock_run_library_command.assert_not_called()

    def test_unsupported_value(self):
        supported_values = {
            "type": "'service_command'",
            "service": "'pacemaker_remote'",
            "command": "'disable', 'enable', 'start', 'stop'",
        }
        for key, supported in supported_values.items():
            with self.subTest(key=key):
                self.mock_run_library_command.reset_mock()
                action = self.fixture_action(**{key: "unknown"})
                response = self.fetch(
                    self.url,
                    body=self.fixture_body(json.dumps({"a1": action})),
                )
                self.assert_body(
                    response.body,
                    f"Invalid input data format: action (key: a1): "
                    f"unsupported '{key}' ('unknown'), "
                    f"supported are: {supported}",
                )
                self.assertEqual(response.code, 400)
                self.mock_run_library_command.assert_not_called()

    def test_unsupported_combination(self):
        response = self.fetch(
            self.url,
            body=self.fixture_body(
                json.dumps(
                    {
                        "a1": self.fixture_action(command="enable"),
                        "a2": self.fixture_action(command="stop"),
                    }
                )
            ),
        )
        self.assert_body(
            response.body,
            "Invalid input data format: unsupported combination of actions: "
            "'enable', 'stop'",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def _fixture_service_action_succeeded_report(
        self, action: reports.types.ServiceAction
    ) -> reports.dto.ReportItemDto:
        return reports.ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                action,
                "pacemaker_remote",
            )
        ).to_dto()

    def _fixture_service_action_failed_report(
        self, action: reports.types.ServiceAction
    ) -> reports.dto.ReportItemDto:
        return reports.ReportItem.error(
            reports.messages.ServiceActionFailed(
                action,
                "pacemaker_remote",
                "some error",
            )
        ).to_dto()

    def test_success_on(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                self._fixture_service_action_succeeded_report(
                    reports.const.SERVICE_ACTION_ENABLE
                ),
                self._fixture_service_action_succeeded_report(
                    reports.const.SERVICE_ACTION_START
                ),
            ]
        )
        response = self.fetch(
            self.url,
            body=self.fixture_body(
                json.dumps(
                    {
                        "a1": self.fixture_action(command="enable"),
                        "a2": self.fixture_action(command="start"),
                    }
                )
            ),
        )
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "actions": {
                        "a1": {"code": "success", "message": ""},
                        "a2": {"code": "success", "message": ""},
                    }
                }
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            "services.pacemaker_remote_on_local", {}
        )

    def test_success_off(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                self._fixture_service_action_succeeded_report(
                    reports.const.SERVICE_ACTION_STOP
                ),
                self._fixture_service_action_succeeded_report(
                    reports.const.SERVICE_ACTION_DISABLE
                ),
            ]
        )
        response = self.fetch(
            self.url,
            body=self.fixture_body(
                json.dumps(
                    {
                        "a1": self.fixture_action(command="stop"),
                        "a2": self.fixture_action(command="disable"),
                    }
                )
            ),
        )
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "actions": {
                        "a1": {"code": "success", "message": ""},
                        "a2": {"code": "success", "message": ""},
                    }
                }
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            "services.pacemaker_remote_off_local", {}
        )

    def test_failure_on(self):
        for failing_action, report_items, expected_enable_code in (
            (
                "enable",
                [
                    self._fixture_service_action_failed_report(
                        reports.const.SERVICE_ACTION_ENABLE
                    ),
                ],
                "fail",
            ),
            (
                "start",
                [
                    self._fixture_service_action_succeeded_report(
                        reports.const.SERVICE_ACTION_ENABLE
                    ),
                    self._fixture_service_action_failed_report(
                        reports.const.SERVICE_ACTION_START
                    ),
                ],
                "success",
            ),
        ):
            with self.subTest(failing_action=failing_action):
                self.mock_run_library_command.reset_mock()
                self.mock_run_library_command.return_value = (
                    self.result_failure(report_items=report_items)
                )
                response = self.fetch(
                    self.url,
                    body=self.fixture_body(
                        json.dumps(
                            {
                                "a1": self.fixture_action(command="enable"),
                                "a2": self.fixture_action(command="start"),
                            }
                        )
                    ),
                )
                self.assertEqual(response.code, 200)
                self.assert_body(
                    response.body,
                    json.dumps(
                        {
                            "actions": {
                                "a1": {
                                    "code": expected_enable_code,
                                    "message": "",
                                },
                                "a2": {"code": "fail", "message": ""},
                            }
                        }
                    ),
                )
                self.mock_run_library_command.assert_called_once_with(
                    "services.pacemaker_remote_on_local", {}
                )

    def test_failure_off(self):
        for failing_action, report_items, expected_stop_code in (
            (
                "stop",
                [
                    self._fixture_service_action_failed_report(
                        reports.const.SERVICE_ACTION_STOP
                    ),
                ],
                "fail",
            ),
            (
                "disable",
                [
                    self._fixture_service_action_succeeded_report(
                        reports.const.SERVICE_ACTION_STOP
                    ),
                    self._fixture_service_action_failed_report(
                        reports.const.SERVICE_ACTION_DISABLE
                    ),
                ],
                "success",
            ),
        ):
            with self.subTest(failing_action=failing_action):
                self.mock_run_library_command.reset_mock()
                self.mock_run_library_command.return_value = (
                    self.result_failure(report_items=report_items)
                )
                response = self.fetch(
                    self.url,
                    body=self.fixture_body(
                        json.dumps(
                            {
                                "a1": self.fixture_action(command="stop"),
                                "a2": self.fixture_action(command="disable"),
                            }
                        )
                    ),
                )
                self.assertEqual(response.code, 200)
                self.assert_body(
                    response.body,
                    json.dumps(
                        {
                            "actions": {
                                "a1": {
                                    "code": expected_stop_code,
                                    "message": "",
                                },
                                "a2": {"code": "fail", "message": ""},
                            }
                        }
                    ),
                )
                self.mock_run_library_command.assert_called_once_with(
                    "services.pacemaker_remote_off_local", {}
                )


class ResourceManageUnmanageMixin:
    body_data = {"resource_list_json": json.dumps(["resource1", "resource2"])}
    command_data = {"resource_or_tag_ids": ["resource1", "resource2"]}

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, self.command_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'resource_list_json'"
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_json_parse_error(self):
        response = self.fetch(
            self.url, body=urlencode({"resource_list_json": "not a json"})
        )
        self.assert_body(response.body, "Invalid input data format")
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_run_library_command.assert_called_once_with(
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
        self.mock_run_library_command.return_value = self.result_success(
            "certificate data"
        )
        response = self.fetch(self.url)
        self.assert_body(response.body, "certificate data")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.qdevice_net_get_ca_certificate", {}
        )


class QdeviceNetSignNodeCertificateHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_sign_node_certificate"
    body_data = {
        "certificate_request": "base64 certificate data",
        "cluster_name": "my-cluster",
    }

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success(
            "signed certificate data"
        )
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "signed certificate data")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.qdevice_net_sign_certificate_request", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body,
            "Required parameters missing: 'certificate_request', 'cluster_name'",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.qdevice_net_sign_certificate_request", self.body_data
        )


class QdeviceNetClientInitCertificateStorageHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_init_certificate_storage"
    body_data = {"ca_certificate": "base64 certificate data"}

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_setup", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'ca_certificate'"
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_setup", self.body_data
        )


class QdeviceNetClientImportCertificateHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_import_certificate"
    body_data = {"certificate": "base64 certificate data"}

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode(self.body_data))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_import_certificate", self.body_data
        )

    def test_missing_params(self):
        response = self.fetch(self.url)
        self.assert_body(
            response.body, "Required parameters missing: 'certificate'"
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()

    def test_failure(self):
        self.assert_error_with_report(self.url, body=urlencode(self.body_data))
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_import_certificate", self.body_data
        )


class QdeviceNetClientDestroyHandler(ApiV0HandlerTest):
    url = "/remote/qdevice_net_client_destroy"

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url)
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_destroy", {}
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_run_library_command.assert_called_once_with(
            "qdevice.client_net_destroy", {}
        )


class BoothGetConfigHandler(ApiV0HandlerTest):
    url = "/remote/booth_get_config"

    def test_success(self):
        result_dto = BoothConfigAndAuthfileDto(
            config=BoothConfigFileDto(name="booth.conf", data="some config"),
            authfile=BoothConfigFileDto(name="booth.key", data="base64data"),
        )
        self.mock_run_library_command.return_value = self.result_success(
            result_dto
        )
        response = self.fetch(self.url)
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "config": {"name": "booth.conf", "data": "some config"},
                    "authfile": {"name": "booth.key", "data": "base64data"},
                }
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            "booth.get_config_and_authfile", dict(instance_name=None)
        )

    def test_success_with_name(self):
        result_dto = BoothConfigAndAuthfileDto(
            config=BoothConfigFileDto(name="my_booth.conf", data="some config"),
            authfile=None,
        )
        self.mock_run_library_command.return_value = self.result_success(
            result_dto
        )
        response = self.fetch(self.url, body=urlencode({"name": "my_booth"}))
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "config": {
                        "name": "my_booth.conf",
                        "data": "some config",
                    },
                    "authfile": None,
                }
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            "booth.get_config_and_authfile", dict(instance_name="my_booth")
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_run_library_command.assert_called_once_with(
            "booth.get_config_and_authfile", dict(instance_name=None)
        )

    def test_authfile_not_in_booth_dir(self):
        result_dto = BoothConfigAndAuthfileDto(
            config=BoothConfigFileDto(name="booth.conf", data="some config"),
            authfile=None,
        )
        self.mock_run_library_command.return_value = self.result_success(
            result_dto,
            reports=[
                reports.ReportItem.warning(
                    reports.messages.BoothUnsupportedFileLocation(
                        "/etc/my_booth.key",
                        settings.booth_config_dir,
                        file_type_codes.BOOTH_KEY,
                    )
                ).to_dto()
            ],
        )
        response = self.fetch(self.url)
        self.assertEqual(response.code, 400)
        self.assert_body(
            response.body,
            "Warning: Booth key '/etc/my_booth.key' is outside of supported "
            f"booth config directory '{settings.booth_config_dir}', ignoring the file",
        )
        self.mock_run_library_command.assert_called_once_with(
            "booth.get_config_and_authfile", dict(instance_name=None)
        )


class CheckHostHandler(ApiV0HandlerTest):
    url = "/remote/check_host"

    def test_success(self):
        dto = ClusterDaemonsInfoDto(
            cluster_configuration_exists=True,
            services=[
                ServiceStatusDto(
                    service="pacemaker",
                    installed=True,
                    enabled=False,
                    running=True,
                ),
                ServiceStatusDto(
                    service="corosync",
                    installed=True,
                    enabled=False,
                    running=True,
                ),
                ServiceStatusDto(
                    service="corosync-qdevice",
                    installed=False,
                    enabled=False,
                    running=False,
                ),
            ],
            versions=ClusterComponentVersionDto(
                corosync=VersionDto(major=0, minor=0, revision=0),
                pacemaker=VersionDto(major=3, minor=0, revision=1),
                pcsd=VersionDto(major=0, minor=12, revision=2),
            ),
        )

        self.mock_run_library_command.return_value = self.result_success(dto)
        response = self.fetch(self.url)
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "services": {
                        "pacemaker": {
                            "installed": True,
                            "enabled": False,
                            "running": True,
                            "version": "3.0.1",
                        },
                        "corosync": {
                            "installed": True,
                            "enabled": False,
                            "running": True,
                            "version": None,
                        },
                        "qdevice": {
                            "installed": False,
                            "enabled": False,
                            "running": False,
                            "version": None,
                        },
                    },
                    "cluster_configuration_exists": True,
                }
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            "cluster.get_host_daemons_info", {}
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_run_library_command.assert_called_once_with(
            "cluster.get_host_daemons_info", {}
        )


class GetConfigsHandler(ApiV0HandlerTest):
    url = "/remote/get_configs"
    request_data = {"cluster_name": "test"}
    command = "pcs_cfgsync.get_configs"

    def test_success(self):
        file_contents = [
            ("foo", "bar"),
            ("foo", None),
            (None, "bar"),
            (None, None),
        ]
        for known_hosts_content, pcs_settings_content in file_contents:
            with self.subTest(
                value=(
                    f"known-hosts: {known_hosts_content};"
                    "pcs_settings.conf: {pcs_settings_content}"
                )
            ):
                self.mock_run_library_command.reset_mock()
                self.mock_run_library_command.return_value = self.result_success(
                    SyncConfigsDto(
                        "test",
                        {
                            file_type_codes.PCS_KNOWN_HOSTS: known_hosts_content,
                            file_type_codes.PCS_SETTINGS_CONF: pcs_settings_content,
                        },
                    )
                )
                response = self.fetch(
                    self.url, body=urlencode(self.request_data)
                )
                self.assertEqual(response.code, 200)
                self.assert_body(
                    response.body,
                    json.dumps(
                        {
                            "status": "ok",
                            "cluster_name": "test",
                            "configs": {
                                "known-hosts": {
                                    "type": "file",
                                    "text": known_hosts_content,
                                },
                                "pcs_settings.conf": {
                                    "type": "file",
                                    "text": pcs_settings_content,
                                },
                            },
                        }
                    ),
                )
                self.mock_run_library_command.assert_called_once_with(
                    self.command, self.request_data
                )

    def test_wrong_cluster_name(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.NodeReportsUnexpectedClusterName("test")
                ).to_dto()
            ],
        )
        response = self.fetch(self.url, body=urlencode(self.request_data))
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body, json.dumps({"status": "wrong_cluster_name"})
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.request_data
        )

    def test_cluster_name_parameter_not_provided(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.NodeReportsUnexpectedClusterName("test")
                ).to_dto()
            ],
        )
        response = self.fetch(self.url)
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body, json.dumps({"status": "wrong_cluster_name"})
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, {"cluster_name": ""}
        )

    def test_unable_to_read_corosync_conf(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.FileIoError(
                        file_type_codes.COROSYNC_CONF,
                        RawFileError.ACTION_READ,
                        reason="foo",
                        file_path="bar",
                    )
                ).to_dto()
            ],
        )
        response = self.fetch(self.url, body=urlencode(self.request_data))
        self.assertEqual(response.code, 200)
        self.assert_body(
            response.body, json.dumps({"status": "not_in_cluster"})
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.request_data
        )

    def test_failure(self):
        self.assert_error_with_report(
            self.url, body=urlencode(self.request_data)
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.request_data
        )


class SetSyncOptions(ApiV0HandlerTest):
    url = "/remote/set_sync_options"

    def test_locked(self):
        self.sync_config_lock.acquire()

        try:
            self.fetch(self.url)
        except TornadoTimeoutError:
            # The http_client timeouted because of lock and this is how we test
            # the locking function. However event loop on the server side should
            # finish. So we release the lock and the request successfully
            # finish.
            self.sync_config_lock.release()
            # Now, there is an unfinished request. It was started by calling
            # fetch("/remote/set_sync_options") (in self.fetch_set_sync_options)
            # and it was waiting for the lock to be released.
            # The lock was released and the request is able to be finished now.
            # So, io_loop needs an opportunity to execute the rest of request.
            # Next line runs io_loop to finish hanging request. Without this an
            # error appears during calling
            # `self.http_server.close_all_connections` in tearDown...
            self.io_loop.run_sync(lambda: None)
        else:
            raise AssertionError("Timeout not raised")

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(self.url)

        self.assert_body(
            response.body, "Sync thread options updated successfully"
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "pcs_cfgsync.update_sync_options", {"options": {}}
        )

    def test_success_with_args(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(self.url, body=urlencode({"foo": "", "bar": 123}))

        self.assert_body(
            response.body, "Sync thread options updated successfully"
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            "pcs_cfgsync.update_sync_options",
            {"options": {"foo": "", "bar": "123"}},
        )

    def test_failure(self):
        self.assert_error_with_report(self.url)
        self.mock_run_library_command.assert_called_once_with(
            "pcs_cfgsync.update_sync_options", {"options": {}}
        )


class SetPermissions(ApiV0HandlerTest):
    url = "/remote/set_permissions"
    command = "cluster.set_permissions"

    request_data = {
        "cluster_name": "ignored",
        "cluster": "ignored",
        "permissions": {
            "1": {
                "name": "username",
                "type": "user",
                "allow": {
                    "read": "1",
                    "write": "1",
                    "grant": "1",
                },
            },
            "2": {
                "name": "groupname",
                "type": "group",
                "allow": {
                    "read": "0",
                    "write": "0",
                    "superuser": "1",
                    "full": "1",
                },
            },
            # to verify that default values will be used.
            # real validation of the values is done in the lib command
            "3": {},
        },
    }
    lib_command_call_arguments = {
        "permissions": [
            {
                "name": "username",
                "type": "user",
                "allow": ["read", "write", "grant"],
            },
            {
                "name": "groupname",
                "type": "group",
                "allow": ["superuser", "full"],
            },
            {
                "name": "",
                "type": "",
                "allow": [],
            },
        ]
    }

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(
            self.url,
            body=urlencode({"json_data": json.dumps(self.request_data)}),
        )

        self.assertEqual(response.code, 200)
        self.assert_body(response.body, "Permissions saved")
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.lib_command_call_arguments
        )

    def test_success_empty_json_data(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(self.url, body=urlencode({"json_data": "{}"}))

        self.assertEqual(response.code, 200)
        self.assert_body(response.body, "Permissions saved")
        self.mock_run_library_command.assert_called_once_with(
            self.command, {"permissions": []}
        )

    def test_bad_json(self):
        bad_inputs = [
            [],
            "not a valid json",
            {"permissions": []},  # list instead of dict
            {"permissions": {"allow": []}},  # list for 'allow' instead of dict
        ]
        for data in bad_inputs:
            with self.subTest(value=data):
                self.mock_run_library_command.reset_mock()

                response = self.fetch(
                    self.url,
                    body=urlencode({"json_data": json.dumps(data)}),
                )

                self.assertEqual(response.code, 400)
                self.assert_body(response.body, "{'status': 'bad_json'}")

    def test_not_authorized_to_change_full_users(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.NotAuthorizedToChangeFullPermission()
                )
            ]
        )

        response = self.fetch(
            self.url,
            body=urlencode({"json_data": json.dumps(self.request_data)}),
        )

        self.assertEqual(response.code, 403)
        self.assert_body(
            response.body,
            (
                "Current user is not authorized for this operation.\n"
                "Only hacluster and users with Full permission can grant or "
                "revoke Full permission."
            ),
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.lib_command_call_arguments
        )

    def test_failure(self):
        self.assert_error_with_report(
            self.url,
            body=urlencode({"json_data": json.dumps(self.request_data)}),
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.lib_command_call_arguments
        )


class KnownHostsChange(ApiV0HandlerTest):
    url = "/remote/known_hosts_change"
    command = "auth.known_hosts_change"

    request_data = {
        "known_hosts_add": {
            "node1": {
                "token": "token1",
                "dest_list": [
                    {"addr": "1.2.3.4", "port": 1234},
                    {"addr": "", "port": ""},
                ],
            },
            "node2": {},  # default values, real validation in lib command
        },
        "known_hosts_remove": ["nodeX", "nodeY"],
    }
    lib_command_call_arguments = {
        "hosts_to_add": {
            "node1": {
                "token": "token1",
                "dest_list": [
                    {"addr": "1.2.3.4", "port": 1234},
                    {"addr": "node1", "port": 2224},
                ],
            },
            "node2": {"token": "", "dest_list": []},
        },
        "hosts_to_remove": ["nodeX", "nodeY"],
    }

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(
            self.url,
            body=urlencode({"data_json": json.dumps(self.request_data)}),
        )

        self.assertEqual(response.code, 200)
        self.assert_body(response.body, "")
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.lib_command_call_arguments
        )

    def test_failure(self):
        self.assert_error_with_report(
            self.url,
            body=urlencode({"data_json": json.dumps(self.request_data)}),
        )
        self.mock_run_library_command.assert_called_once_with(
            self.command, self.lib_command_call_arguments
        )

    def test_bad_json(self):
        bad_inputs = [
            [],
            "not a valid json",
            "",
            {
                "known_hosts_add": [],
            },
            {
                "known_hosts_add": {
                    "token": "",
                    "dest_list": "foo",
                }
            },
            {
                "known_hosts_add": {
                    "token": "",
                    "dest_list": ["foo", "bar"],
                }
            },
            {"known_hosts_remove": 123},
        ]
        for data in bad_inputs:
            with self.subTest(value=data):
                self.mock_run_library_command.reset_mock()

                response = self.fetch(
                    self.url,
                    body=urlencode({"data_json": json.dumps(data)}),
                )

                self.assertEqual(response.code, 400)
                self.assertTrue(
                    response.body.decode().startswith(
                        "Incorrect format of request data: "
                    )
                )
                self.mock_run_library_command.assert_not_called()
