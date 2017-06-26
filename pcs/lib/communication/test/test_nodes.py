from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.assertions import assert_report_item_list_equal

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

from pcs.lib.communication import nodes


class AvailabilityCheckerNode(TestCase):
    def setUp(self):
        self.node = "node1"

    def assert_result_causes_reports(
        self, availability_info, expected_report_items
    ):
        report_items = []
        nodes.availability_checker_node(
            availability_info,
            report_items,
            self.node
        )
        assert_report_item_list_equal(report_items, expected_report_items)

    def test_no_reports_when_available(self):
        self.assert_result_causes_reports({"node_available": True}, [])

    def test_report_node_is_in_cluster(self):
        self.assert_result_causes_reports({"node_available": False}, [
            (
                severity.ERROR,
                report_codes.CANNOT_ADD_NODE_IS_IN_CLUSTER,
                {
                    "node": self.node
                }
            ),
        ])

    def test_report_node_is_running_pacemaker_remote(self):
        self.assert_result_causes_reports(
            {"node_available": False, "pacemaker_remote": True},
            [
                (
                    severity.ERROR,
                    report_codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE,
                    {
                        "node": self.node,
                        "service": "pacemaker_remote",
                    }
                ),
            ]
        )

    def test_report_node_is_running_pacemaker(self):
        self.assert_result_causes_reports(
            {"node_available": False, "pacemaker_running": True},
            [
                (
                    severity.ERROR,
                    report_codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE,
                    {
                        "node": self.node,
                        "service": "pacemaker",
                    }
                ),
            ]
        )


class AvailabilityCheckerRemoteNode(TestCase):
    def setUp(self):
        self.node = "node1"

    def assert_result_causes_reports(
        self, availability_info, expected_report_items
    ):
        report_items = []
        nodes.availability_checker_remote_node(
            availability_info,
            report_items,
            self.node
        )
        assert_report_item_list_equal(report_items, expected_report_items)

    def test_no_reports_when_available(self):
        self.assert_result_causes_reports({"node_available": True}, [])

    def test_report_node_is_running_pacemaker(self):
        self.assert_result_causes_reports(
            {"node_available": False, "pacemaker_running": True},
            [
                (
                    severity.ERROR,
                    report_codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE,
                    {
                        "node": self.node,
                        "service": "pacemaker",
                    }
                ),
            ]
        )

    def test_report_node_is_in_cluster(self):
        self.assert_result_causes_reports({"node_available": False}, [
            (
                severity.ERROR,
                report_codes.CANNOT_ADD_NODE_IS_IN_CLUSTER,
                {
                    "node": self.node
                }
            ),
        ])

    def test_no_reports_when_pacemaker_remote_there(self):
        self.assert_result_causes_reports(
            {"node_available": False, "pacemaker_remote": True},
            []
        )
