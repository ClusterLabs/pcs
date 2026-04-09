from urllib.parse import urlencode

from pcs.common import reports

from pcs_test.tier0.daemon.app.ui_manage.test_base import UiManageHandlerTest


class RemoveClusterHandlerTest(UiManageHandlerTest):
    url = "/manage/removecluster"
    command_name = "manage_clusters.remove_clusters"

    def test_success_single_cluster(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(
            self.url, body=urlencode({"clusterid-test-cluster": ""})
        )

        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name, {"cluster_names": ["test-cluster"]}
        )

    def test_success_multiple_clusters(self):
        self.mock_run_library_command.return_value = self.result_success()

        response = self.fetch(
            self.url,
            body=urlencode(
                {
                    "clusterid-cluster1": "values",
                    "clusterid-cluster2": "don't",
                    "clusterid-cluster3": "matter",
                }
            ),
        )

        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name,
            {"cluster_names": ["cluster1", "cluster2", "cluster3"]},
        )

    def test_mixed_parameters(self):
        # Test that only clusterid- prefixed parameters are used
        self.mock_run_library_command.return_value = self.result_success()
        response = self.fetch(
            self.url,
            body=urlencode(
                {
                    "clusterid-cluster1": "",
                    "other-param": "value",
                    "clusterid-cluster2": "",
                    "cluster": "data",
                }
            ),
        )
        self.assert_body(response.body, "")
        self.assertEqual(response.code, 200)
        self.mock_run_library_command.assert_called_once_with(
            self.command_name,
            {"cluster_names": ["cluster1", "cluster2"]},
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
            ]
        )
        response = self.fetch(
            self.url, body=urlencode({"clusterid-test-cluster": ""})
        )
        self.assert_body(
            response.body,
            (
                "Error: Unfencing failed:\nerror1\n"
                "Warning: Unfencing failed:\nwarning1"
            ),
        )
        self.assertEqual(response.code, 400)
