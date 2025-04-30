import io
from unittest import TestCase

import pcs.lib.node_communication as lib
from pcs.common import pcs_pycurl as pycurl
from pcs.common.host import (
    Destination,
    PcsKnownHost,
)
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_equal,
)
from pcs_test.tools.custom_mock import (
    MockCurl,
    MockLibraryReportProcessor,
)


class NodeTargetLibFactory(TestCase):
    def setUp(self):
        self.known_hosts = {
            "host{}".format(i): PcsKnownHost(
                "host{}".format(i),
                "token{}".format(i),
                [
                    Destination(
                        "addr{}{}".format(i, j), "port{}{}".format(i, j)
                    )
                    for j in range(2)
                ],
            )
            for i in range(2)
        }
        self.report_processor = MockLibraryReportProcessor()
        self.factory = lib.NodeTargetLibFactory(
            self.known_hosts, self.report_processor
        )

    def assert_equal_known_host_target(self, known_host, target):
        self.assertEqual(known_host.name, target.label)
        self.assertEqual(known_host.token, target.token)
        self.assertEqual(known_host.dest_list, target.dest_list)

    def test_one_host(self):
        host = "host0"
        self.assert_equal_known_host_target(
            self.known_hosts[host], self.factory.get_target_list([host])[0]
        )
        self.report_processor.assert_reports([])

    def test_multiple_hosts(self):
        host_list = ["host0", "host1"]
        target_list = self.factory.get_target_list(host_list)
        for i, host in enumerate(host_list):
            self.assert_equal_known_host_target(
                self.known_hosts[host], target_list[i]
            )
        self.report_processor.assert_reports([])

    def test_multiple_not_found(self):
        host = "host0"
        unknown_hosts = ["node0", "node1"]
        report = fixture.error(
            report_codes.HOST_NOT_FOUND,
            force_code=report_codes.SKIP_OFFLINE_NODES,
            host_list=unknown_hosts,
        )
        assert_raise_library_error(
            lambda: self.factory.get_target_list([host] + unknown_hosts)
        )
        self.report_processor.assert_reports([report])

    def test_multiple_skip_not_allowed(self):
        host = "host0"
        unknown_hosts = ["node0", "node1"]
        report = fixture.error(
            report_codes.HOST_NOT_FOUND, host_list=unknown_hosts
        )
        assert_raise_library_error(
            lambda: self.factory.get_target_list(
                [host] + unknown_hosts,
                allow_skip=False,
            )
        )
        self.report_processor.assert_reports([report])

    def test_multiple_not_found_skip_offline(self):
        host = "host0"
        unknown_hosts = ["node0", "node1"]
        target_list = self.factory.get_target_list(
            [host] + unknown_hosts, skip_non_existing=True
        )
        self.assert_equal_known_host_target(
            self.known_hosts[host], target_list[0]
        )
        self.report_processor.assert_reports(
            [fixture.warn(report_codes.HOST_NOT_FOUND, host_list=unknown_hosts)]
        )

    def test_no_host_found(self):
        unknown_hosts = ["node0", "node1"]
        report_list = [
            fixture.error(
                report_codes.HOST_NOT_FOUND,
                force_code=report_codes.SKIP_OFFLINE_NODES,
                host_list=unknown_hosts,
            ),
            fixture.error(report_codes.NONE_HOST_FOUND),
        ]
        assert_raise_library_error(
            lambda: self.factory.get_target_list(unknown_hosts),
        )
        self.report_processor.assert_reports(report_list)

    def test_no_host_found_skip_offline(self):
        unknown_hosts = ["node0", "node1"]
        report_list = [
            fixture.warn(report_codes.HOST_NOT_FOUND, host_list=unknown_hosts),
            fixture.error(report_codes.NONE_HOST_FOUND),
        ]
        assert_raise_library_error(
            lambda: self.factory.get_target_list(
                unknown_hosts, skip_non_existing=True
            )
        )
        self.report_processor.assert_reports(report_list)

    def test_empty_host_list(self):
        self.assertEqual([], self.factory.get_target_list([]))
        self.report_processor.assert_reports([])


class ResponseToReportItemTest(TestCase):
    def fixture_response_connected(self, response_code):
        handle = MockCurl({pycurl.RESPONSE_CODE: response_code})
        handle.request_obj = Request(
            RequestTarget(self.host), RequestData(self.request)
        )
        handle.output_buffer = io.BytesIO()
        handle.output_buffer.write(self.data)
        return Response.connection_successful(handle)

    def fixture_response_not_connected(self, errno, error_msg):
        handle = MockCurl()
        handle.request_obj = Request(
            RequestTarget(self.host), RequestData(self.request)
        )
        return Response.connection_failure(handle, errno, error_msg)

    def setUp(self):
        self.host = "host"
        self.request = "request"
        self.data = b"data"

    def test_code_200(self):
        self.assertIsNone(
            lib.response_to_report_item(self.fixture_response_connected(200))
        )

    def test_code_400(self):
        assert_report_item_equal(
            lib.response_to_report_item(self.fixture_response_connected(400)),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": self.data.decode("utf-8"),
                },
                None,
            ),
        )

    def test_code_401(self):
        assert_report_item_equal(
            lib.response_to_report_item(self.fixture_response_connected(401)),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "HTTP error: 401",
                },
                None,
            ),
        )

    def test_code_403(self):
        assert_report_item_equal(
            lib.response_to_report_item(self.fixture_response_connected(403)),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "HTTP error: 403",
                },
                None,
            ),
        )

    def test_code_404(self):
        assert_report_item_equal(
            lib.response_to_report_item(self.fixture_response_connected(404)),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "HTTP error: 404",
                },
                None,
            ),
        )

    def test_code_other(self):
        assert_report_item_equal(
            lib.response_to_report_item(self.fixture_response_connected(500)),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "HTTP error: 500",
                },
                None,
            ),
        )

    def test_timed_out(self):
        response = self.fixture_response_not_connected(
            pycurl.E_OPERATION_TIMEDOUT, "err"
        )
        assert_report_item_equal(
            lib.response_to_report_item(response),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_TIMED_OUT,
                {"node": self.host, "command": self.request, "reason": "err"},
                None,
            ),
        )

    def test_timeouted(self):
        response = self.fixture_response_not_connected(
            pycurl.E_OPERATION_TIMEOUTED, "err"
        )
        assert_report_item_equal(
            lib.response_to_report_item(response),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_TIMED_OUT,
                {"node": self.host, "command": self.request, "reason": "err"},
                None,
            ),
        )

    def test_unable_to_connect(self):
        response = self.fixture_response_not_connected(
            pycurl.E_SEND_ERROR, "err"
        )
        assert_report_item_equal(
            lib.response_to_report_item(response),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {"node": self.host, "command": self.request, "reason": "err"},
                None,
            ),
        )
