from lxml import etree
from unittest import TestCase

from pcs.lib.cib import status


class GetResourcesFailcounts(TestCase):
    def test_no_failures(self):
        status_xml = etree.fromstring("""
            <status>
                <node_state uname="node1">
                    <transient_attributes>
                        <instance_attributes>
                        </instance_attributes>
                    </transient_attributes>
                </node_state>
                <node_state uname="node2">
                    <transient_attributes>
                    </transient_attributes>
                </node_state>
                <node_state uname="node3">
                </node_state>
            </status>
        """)
        self.assertEqual(
            status.get_resources_failcounts(status_xml),
            []
        )

    def test_failures(self):
        status_xml = etree.fromstring("""
            <status>
                <node_state uname="node1">
                    <transient_attributes>
                        <instance_attributes>
                            <nvpair name="fail-count-clone:0#start_0"
                                value="INFINITY"/>
                            <nvpair name="last-failure-clone:0#start_0"
                                value="1528871936"/>
                            <nvpair name="fail-count-clone:1#start_0"
                                value="999"/>
                            <nvpair name="last-failure-clone:1#start_0"
                                value="1528871937"/>
                        </instance_attributes>
                    </transient_attributes>
                </node_state>
                <node_state uname="node2">
                    <transient_attributes>
                        <instance_attributes>
                            <nvpair name="fail-count-resource#monitor_500"
                                value="10"/>
                            <nvpair name="last-failure-resource#monitor_500"
                                value="1528871946"/>
                            <nvpair name="fail-count-no-last#stop_0"
                                value="3"/>
                            <nvpair name="last-failure-no-count#monitor_1000"
                                value="1528871956"/>
                            <nvpair name="ignored-resource#monitor_1000"
                                value="ignored"/>
                            <nvpair name="fail-count-no-int#start_0"
                                value="a few"/>
                            <nvpair name="last-failure-no-int#start_0"
                                value="an hour ago"/>
                        </instance_attributes>
                    </transient_attributes>
                </node_state>
            </status>
        """)
        self.assertEqual(
            sorted(
                status.get_resources_failcounts(status_xml),
                key=lambda x: [str(x[key]) for key in sorted(x.keys())]
            ),
            sorted([
                {
                    "node": "node1",
                    "resource": "clone",
                    "clone_id": "0",
                    "operation": "start",
                    "interval": "0",
                    "fail_count": "INFINITY",
                    "last_failure": 1528871936,
                },
                {
                    "node": "node1",
                    "resource": "clone",
                    "clone_id": "1",
                    "operation": "start",
                    "interval": "0",
                    "fail_count": 999,
                    "last_failure": 1528871937,
                },
                {
                    "node": "node2",
                    "resource": "resource",
                    "clone_id": None,
                    "operation": "monitor",
                    "interval": "500",
                    "fail_count": 10,
                    "last_failure": 1528871946,
                },
                {
                    "node": "node2",
                    "resource": "no-last",
                    "clone_id": None,
                    "operation": "stop",
                    "interval": "0",
                    "fail_count": 3,
                    "last_failure": 0,
                },
                {
                    "node": "node2",
                    "resource": "no-count",
                    "clone_id": None,
                    "operation": "monitor",
                    "interval": "1000",
                    "fail_count": 0,
                    "last_failure": 1528871956,
                },
                {
                    "node": "node2",
                    "resource": "no-int",
                    "clone_id": None,
                    "operation": "start",
                    "interval": "0",
                    "fail_count": 1,
                    "last_failure": 0,
                },
            ],
                key=lambda x: [str(x[key]) for key in sorted(x.keys())]
            )
        )

class ParseFailureName(TestCase):
    def test_without_clone_id(self):
        self.assertEqual(
            status._parse_failure_name("resource#monitor_1000"),
            ("resource", None, "monitor", "1000")
        )

    def test_with_clone_id(self):
        self.assertEqual(
            status._parse_failure_name("resource:2#monitor_1000"),
            ("resource", "2", "monitor", "1000")
        )

class FilterResourceFailcounts(TestCase):
    # pylint: disable=too-many-instance-attributes
    def setUp(self):
        self.fail_01 = {
            "node": "nodeA",
            "resource": "resourceA",
            "clone_id": None,
            "operation": "start",
            "interval": "0",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_02 = {
            "node": "nodeA",
            "resource": "resourceB",
            "clone_id": None,
            "operation": "monitor",
            "interval": "1000",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_03 = {
            "node": "nodeB",
            "resource": "resourceA",
            "clone_id": None,
            "operation": "monitor",
            "interval": "1000",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_04 = {
            "node": "nodeB",
            "resource": "resourceB",
            "clone_id": None,
            "operation": "start",
            "interval": "0",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_05 = {
            "node": "nodeB",
            "resource": "resourceA",
            "clone_id": None,
            "operation": "monitor",
            "interval": "500",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_06 = {
            "node": "nodeB",
            "resource": "resourceA",
            "clone_id": None,
            "operation": "start",
            "interval": "0",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.fail_07 = {
            "node": "nodeB",
            "resource": "resourceB",
            "clone_id": None,
            "operation": "monitor",
            "interval": "1000",
            "fail_count": "INFINITY",
            "last_failure": "100",
        }
        self.failures = [
            self.fail_01, self.fail_02, self.fail_03, self.fail_04,
            self.fail_05, self.fail_06, self.fail_07
        ]

    def test_no_filter(self):
        self.assertEqual(
            status.filter_resources_failcounts(self.failures),
            self.failures
        )

    def test_no_match(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, resource="resourceX"
            ),
            []
        )

    def test_filter_by_resource(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, resource="resourceA"
            ),
            [self.fail_01, self.fail_03, self.fail_05, self.fail_06]
        )

    def test_filter_by_node(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, node="nodeA"
            ),
            [self.fail_01, self.fail_02]
        )

    def test_filter_by_operation(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, operation="monitor"
            ),
            [self.fail_02, self.fail_03, self.fail_05, self.fail_07]
        )

    def test_filter_by_operation_and_interval(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, operation="monitor", interval="500"
            ),
            [self.fail_05]
        )

    def test_filter_by_operation_and_interval_int(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, operation="monitor", interval=500
            ),
            [self.fail_05]
        )

    def test_filter_by_resource_and_node(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, resource="resourceA", node="nodeB"
            ),
            [self.fail_03, self.fail_05, self.fail_06]
        )

    def test_filter_by_resource_and_node_and_operation(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, resource="resourceA", node="nodeB",
                operation="monitor"
            ),
            [self.fail_03, self.fail_05]
        )

    def test_filter_by_resource_and_node_and_operation_and_interval(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, resource="resourceA", node="nodeB",
                operation="monitor", interval="1000"
            ),
            [self.fail_03]
        )

    def test_filter_by_node_and_operation(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, node="nodeB", operation="monitor"
            ),
            [self.fail_03, self.fail_05, self.fail_07]
        )

    def test_filter_by_node_and_operation_and_interval(self):
        self.assertEqual(
            status.filter_resources_failcounts(
                self.failures, node="nodeB", operation="monitor", interval="1000"
            ),
            [self.fail_03, self.fail_07]
        )
