from urllib.parse import urlencode

from pcs.common import reports

from pcs_test.tier0.daemon.app.ui_manage.test_base import UiManageHandlerTest


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
