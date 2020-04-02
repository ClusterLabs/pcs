from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import resource


class GetFailcounts(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(test_case=self)

    @staticmethod
    def fixture_cib():
        return """
        <cib>
            <status>
                <node_state uname="node1">
                    <transient_attributes>
                        <instance_attributes>
                            <nvpair name="fail-count-resource#start_0"
                                value="INFINITY"/>
                            <nvpair name="last-failure-resource#start_0"
                                value="1528871936"/>
                        </instance_attributes>
                    </transient_attributes>
                </node_state>
                <node_state uname="node2">
                    <transient_attributes>
                        <instance_attributes>
                            <nvpair name="fail-count-resource#monitor_5000"
                                value="10"/>
                            <nvpair name="last-failure-resource#monitor_5000"
                                value="1528871946"/>
                        </instance_attributes>
                    </transient_attributes>
                </node_state>
            </status>
        </cib>
        """

    def test_operation_requires_interval(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.get_failcounts(
                self.env_assist.get_env(), interval="1000"
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="interval",
                    option_type="",
                    prerequisite_name="operation",
                    prerequisite_type="",
                ),
            ],
            expected_in_processor=False,
        )

    def test_bad_interval(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.get_failcounts(
                self.env_assist.get_env(), operation="start", interval="often"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="often",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
            expected_in_processor=False,
        )

    def test_all_validation_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: resource.get_failcounts(
                self.env_assist.get_env(), interval="often"
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="interval",
                    option_type="",
                    prerequisite_name="operation",
                    prerequisite_type="",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="often",
                    allowed_values="time interval (e.g. 1, 2s, 3m, 4h, ...)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
            expected_in_processor=False,
        )

    def test_get_all(self):
        self.config.runner.cib.load_content(self.fixture_cib())
        self.assertEqual(
            resource.get_failcounts(self.env_assist.get_env()),
            [
                {
                    "node": "node1",
                    "resource": "resource",
                    "clone_id": None,
                    "operation": "start",
                    "interval": "0",
                    "fail_count": "INFINITY",
                    "last_failure": 1528871936,
                },
                {
                    "node": "node2",
                    "resource": "resource",
                    "clone_id": None,
                    "operation": "monitor",
                    "interval": "5000",
                    "fail_count": 10,
                    "last_failure": 1528871946,
                },
            ],
        )

    def test_filter_node(self):
        self.config.runner.cib.load_content(self.fixture_cib())
        self.assertEqual(
            resource.get_failcounts(self.env_assist.get_env(), node="node2"),
            [
                {
                    "node": "node2",
                    "resource": "resource",
                    "clone_id": None,
                    "operation": "monitor",
                    "interval": "5000",
                    "fail_count": 10,
                    "last_failure": 1528871946,
                },
            ],
        )

    def test_filter_interval(self):
        self.config.runner.cib.load_content(self.fixture_cib())
        self.assertEqual(
            resource.get_failcounts(
                self.env_assist.get_env(), operation="monitor", interval="5"
            ),
            [
                {
                    "node": "node2",
                    "resource": "resource",
                    "clone_id": None,
                    "operation": "monitor",
                    "interval": "5000",
                    "fail_count": 10,
                    "last_failure": 1528871946,
                },
            ],
        )
