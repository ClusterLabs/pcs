import json
from urllib.parse import urlencode

from pcs import settings
from pcs.common import reports
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS
from pcs.lib.auth.const import SUPERUSER

from pcs_test.tier0.daemon.app.ui_manage.test_base import UiManageHandlerTest


class AuthGuiAgainstNodes(UiManageHandlerTest):
    url = "/manage/auth_gui_against_nodes"
    command_name = "auth.auth_hosts"

    REQUEST_DATA_OK = urlencode(
        {
            "data_json": json.dumps(
                {
                    "nodes": {
                        "node1": {
                            "password": "password123",
                            "dest_list": [
                                {"addr": "192.168.1.10", "port": "8080"}
                            ],
                        },
                        "node2": {
                            "password": "password456",
                            # empty or missing fields are set to default values
                            "dest_list": [{"addr": ""}],
                        },
                    }
                }
            )
        }
    )

    COMMAND_ARGS_OK = {
        "hosts": {
            "node1": {
                "password": "password123",
                "username": SUPERUSER,
                "dest_list": [{"addr": "192.168.1.10", "port": "8080"}],
            },
            "node2": {
                "password": "password456",
                "username": SUPERUSER,
                "dest_list": [
                    {"addr": "node2", "port": settings.pcsd_default_port}
                ],
            },
        }
    }

    def test_success_without_reports(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto(),
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node2"),
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=self.REQUEST_DATA_OK)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "node_auth_error": {"node1": 0, "node2": 0},
                    "local_cluster_node_auth_error": {},
                    "plaintext_error": "",
                }
            ),
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, self.COMMAND_ARGS_OK
        )

    def test_success_unable_to_auth(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=self.REQUEST_DATA_OK)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "node_auth_error": {"node1": 0, "node2": 1},
                    "local_cluster_node_auth_error": {},
                    "plaintext_error": "",
                }
            ),
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, self.COMMAND_ARGS_OK
        )

    def test_local_cluster_node_auth_error(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto(),
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node2"),
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.HostNotFound(host_list=["h1", "h2"])
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.NodeCommunicationErrorNotAuthorized(
                        node="h3", command="foo", reason=""
                    ),
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.NodeCommunicationErrorNotAuthorized(
                        node="h4", command="foo", reason=""
                    ),
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=self.REQUEST_DATA_OK)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "node_auth_error": {"node1": 0, "node2": 0},
                    "local_cluster_node_auth_error": {
                        "h1": 1,
                        "h2": 1,
                        "h3": 1,
                        "h4": 1,
                    },
                    "plaintext_error": "",
                }
            ),
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, self.COMMAND_ARGS_OK
        )

    def test_plaintext_errors(self):
        self.mock_run_library_command.return_value = self.result_success(
            reports=[
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node1"),
                ).to_dto(),
                reports.ReportItem.info(
                    reports.messages.AuthorizationSuccessful(),
                    context=reports.ReportItemContext("node2"),
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.PcsCfgsyncSendingConfigsToNodesFailed(
                        file_type_code_list=[PCS_KNOWN_HOSTS],
                        node_name_list=["h1", "h2"],
                    )
                ),
                reports.ReportItem.error(
                    reports.messages.PcsCfgsyncConflictRepeatAction()
                ).to_dto(),
                reports.ReportItem.error(
                    reports.messages.NoActionNecessary()
                ).to_dto(),
            ]
        )
        response = self.fetch(self.url, body=self.REQUEST_DATA_OK)
        self.assert_body(
            response.body,
            json.dumps(
                {
                    "node_auth_error": {"node1": 0, "node2": 0},
                    "local_cluster_node_auth_error": {},
                    "plaintext_error": (
                        "Error: Unable to save file 'known-hosts' on nodes "
                        "'h1', 'h2'"
                        "\n"
                        "Error: Configuration conflict detected. Some nodes had "
                        "a newer configuration than the local node. Local "
                        "node's configuration was updated. Please repeat the "
                        "last action if appropriate."
                        "\n"
                        "Error: No action necessary, requested change would "
                        "have no effect"
                    ),
                }
            ),
        )
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, self.COMMAND_ARGS_OK
        )

    def test_invalid_input_missing_data_json(self):
        response = self.fetch(self.url, body=urlencode({"foo": "bar"}))
        self.assert_body(response.body, "Missing required parameter: data_json")
        self.assertEqual(response.code, 400)
        self.mock_run_library_command.assert_not_called()
