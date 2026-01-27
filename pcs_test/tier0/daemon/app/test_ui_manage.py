import logging
from typing import Any
from unittest import mock
from urllib.parse import urlencode

from tornado.httpclient import HTTPResponse
from tornado.web import Application

from pcs.common import reports
from pcs.daemon.app.auth import NotAuthorizedException
from pcs.daemon.app.auth_provider import ApiAuthProviderInterface
from pcs.daemon.app.ui_manage import base_handler, get_routes
from pcs.daemon.async_tasks.scheduler import Scheduler
from pcs.lib.auth.types import AuthUser

from pcs_test.tier0.daemon.app.fixtures_app_api import ApiTestBase

# Don't write errors to test output.
logging.getLogger("tornado.access").setLevel(logging.CRITICAL)


class MockApiAuthProvider(ApiAuthProviderInterface):
    def __init__(self):
        self.available = True
        self.user = AuthUser("testuser", ["testgroup"])
        self.auth_successful = True

    def can_handle_request(self) -> bool:
        return self.available

    async def auth_user(self) -> AuthUser:
        if not self.auth_successful:
            raise NotAuthorizedException()
        return self.user


class MockApiAuthProviderFactory:
    def __init__(self):
        self.provider = MockApiAuthProvider()

    def create(self, handler) -> ApiAuthProviderInterface:
        del handler
        return self.provider


class UiManageTest(ApiTestBase):
    """
    Base class for testing ui_manage handlers, provides useful tools used in tests
    """

    def setUp(self) -> None:
        self.scheduler = mock.AsyncMock(spec=Scheduler)
        self.api_auth_provider_factory = MockApiAuthProviderFactory()
        self.api_auth_provider = self.api_auth_provider_factory.provider
        super().setUp()

    def get_app(self) -> Application:
        raise NotImplementedError

    def fetch(
        self,
        path: str,
        raise_error: bool = False,
        add_ajax_header: bool = True,
        **kwargs: Any,
    ) -> HTTPResponse:
        if add_ajax_header:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            if "X-Requested-With" not in kwargs["headers"]:
                kwargs["headers"]["X-Requested-With"] = "XMLHttpRequest"

        response = super().fetch(
            path,
            raise_error,
            method=("GET" if kwargs.get("body") is None else "POST"),
            **kwargs,
        )
        self.assert_headers(response.headers)
        return response


class BaseAjaxProtectedManageHandlerTest(UiManageTest):
    """
    Tests of BaseAjaxProtectedManageHandler class
    """

    url = "/test"
    cmd_name = "test.command"
    cmd_params = {"test": "params"}

    class HandlerForTest(base_handler.BaseAjaxProtectedManageHandler):
        def initialize(
            self, scheduler, api_auth_provider_factory, cmd_name, cmd_params
        ):
            # pylint: disable=arguments-differ
            # pylint: disable=attribute-defined-outside-init
            super().initialize(scheduler, api_auth_provider_factory)
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

    def test_prepare_requires_ajax_header(self):
        response = self.fetch(self.url, add_ajax_header=False)
        self.assertEqual(response.code, 401)
        self.assert_body(response.body, '{"notauthorized":"true"}')

    def test_prepare_requires_auth_provider_available(self):
        self.api_auth_provider.available = False
        response = self.fetch(self.url)
        self.assertEqual(response.code, 401)
        self.assert_body(response.body, '{"notauthorized":"true"}')

    def test_process_request_auth_failure(self):
        self.api_auth_provider.auth_successful = False
        response = self.fetch(self.url)
        self.assertEqual(response.code, 401)
        self.assert_body(response.body, '{"notauthorized":"true"}')


class UiManageHandlerTest(UiManageTest):
    """
    Base class for testing BaseAjaxProtectedManageHandler descendants
    """

    def setUp(self):
        super().setUp()
        self.mock_run_library_command = mock.AsyncMock()
        run_library_command_patcher = mock.patch.object(
            base_handler.BaseAjaxProtectedManageHandler,
            "_run_library_command",
            self.mock_run_library_command,
        )
        run_library_command_patcher.start()
        self.addCleanup(run_library_command_patcher.stop)

    def get_app(self) -> Application:
        return Application(
            get_routes(self.api_auth_provider_factory, self.scheduler)
        )


class ManageExistingClusterHandlerTest(UiManageHandlerTest):
    url = "/manage/existingcluster"
    command_name = "manage_clusters.add_existing_cluster"

    def test_success_without_reports(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node1"}
        )

    def test_pass_empty_node_name(self):
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(self.url)
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": ""}
        )

    def test_success_with_unable_to_get_cluster_known_hosts(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                reports.ReportItem.warning(
                    reports.messages.UnableToGetClusterKnownHosts(
                        "test-cluster"
                    )
                ).to_dto()
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        self.assert_body(
            response.body,
            "Unable to automatically authenticate against cluster nodes: "
            "cannot get authentication info from cluster 'test-cluster'",
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node1"}
        )

    def test_unable_to_get_cluster_info_from_status(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.UnableToGetClusterInfoFromStatus(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto()
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        self.assert_body(
            response.body,
            "Unable to communicate with remote pcsd on node 'node1'.",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node1"}
        )

    def test_unable_to_get_cluster_info_from_status_without_context(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.UnableToGetClusterInfoFromStatus()
                ).to_dto()
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node2"}))
        self.assert_body(
            response.body,
            "Unable to communicate with remote pcsd on node 'node2'.",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node2"}
        )

    def test_node_not_in_cluster(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.NodeNotInCluster(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto()
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        self.assert_body(
            response.body,
            "The node, 'node1', does not currently have a cluster configured. "
            "You must create a cluster using this node before adding it to pcsd.",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node1"}
        )

    def test_cluster_name_already_in_use(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.ClusterNameAlreadyInUse("my-cluster")
                ).to_dto()
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        self.assert_body(
            response.body,
            "The cluster name 'my-cluster' has already been added. "
            "You may not add two clusters with the same name.",
        )
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"node_name": "node1"}
        )

    def test_generic_reports(self):
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingFailed("error1")
                ).to_dto(),
                reports.ReportItem.warning(
                    reports.messages.StonithUnfencingFailed("warning1")
                ).to_dto(),
                reports.ReportItem.info(
                    reports.messages.StonithUnfencingFailed("info1")
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        # Info should be filtered out, only errors and warnings
        self.assert_body(
            response.body,
            (
                "Error: Unfencing failed:\nerror1\n"
                "Warning: Unfencing failed:\nwarning1\n"
                "Unfencing failed:\ninfo1"
            ),
        )
        self.assertEqual(response.code, 400)

    def test_mixed_specific_and_generic_errors(self):
        # Test that specific errors are handled first, then generic errors
        self.mock_run_library_command.return_value = self.result_failure(
            report_items=[
                reports.ReportItem.error(
                    reports.messages.ClusterNameAlreadyInUse("test-cluster")
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingFailed("other error")
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=urlencode({"node-name": "node1"}))
        # Should return the first specific error it finds
        self.assert_body(
            response.body,
            "The cluster name 'test-cluster' has already been added. "
            "You may not add two clusters with the same name.",
        )
        self.assertEqual(response.code, 400)
