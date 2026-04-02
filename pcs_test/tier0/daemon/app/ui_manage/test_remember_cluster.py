from unittest import mock
from urllib.parse import urlencode

from pcs.common import reports

from pcs_test.tier0.daemon.app.ui_manage.test_base import UiManageHandlerTest


class RememberClusterHandlerTest(UiManageHandlerTest):
    url = "/manage/remember-cluster"
    command_name = "manage_clusters.add_cluster"

    def test_success(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(
            self.url,
            body=urlencode(
                [
                    ("cluster_name", "test-cluster"),
                    ("nodes[]", "node1"),
                    ("nodes[]", "node2"),
                    ("nodes[]", "node3"),
                ]
            ),
        )

        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name,
            {
                "cluster_name": "test-cluster",
                "cluster_nodes": ["node1", "node2", "node3"],
            },
        )

    def test_success_default_values(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(self.url, body=urlencode({}))

        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"cluster_name": "", "cluster_nodes": []}
        )

    def test_success_conflict_retry(self):
        # First call returns conflict, second call succeeds
        self.mock_run_library_command.side_effect = [
            self.result_success(
                reports=[
                    reports.ReportItem.error(
                        reports.messages.PcsCfgsyncConflictRepeatAction()
                    ).to_dto()
                ]
            ),
            self.result_success(),
        ]

        response = self.fetch(
            self.url,
            body=urlencode(
                [("cluster_name", "test-cluster"), ("nodes[]", "node1")]
            ),
        )

        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.assertEqual(self.mock_run_library_command.call_count, 2)
        expected_args = {
            "cluster_name": "test-cluster",
            "cluster_nodes": ["node1"],
        }
        self.mock_run_library_command.assert_has_calls(
            [
                mock.call(self.command_name, expected_args),
                mock.call(self.command_name, expected_args),
            ]
        )

    def test_generic_errors(self):
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

        response = self.fetch(
            self.url,
            body=urlencode(
                [("cluster_name", "test-cluster"), ("nodes[]", "node1")]
            ),
        )
        self.assert_body(
            response.body,
            (
                "Error: Unfencing failed:\nerror1\n"
                "Warning: Unfencing failed:\nwarning1\n"
                "Unfencing failed:\ninfo1"
            ),
        )
        self.assertEqual(response.code, 400)
