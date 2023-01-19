import io
import logging
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.node_communication as lib
from pcs import settings
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
    MockCurlSimple,
    MockLibraryReportProcessor,
)
from pcs_test.tools.misc import outdent


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


class IsProxySetTest(TestCase):
    def test_without_proxy(self):
        self.assertFalse(
            lib.is_proxy_set(
                {
                    "var1": "value",
                    "var2": "val",
                }
            )
        )

    def test_multiple(self):
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "var1": "val",
                    "https_proxy": "test.proxy",
                    "var2": "val",
                    "all_proxy": "test2.proxy",
                    "var3": "val",
                }
            )
        )

    def test_empty_string(self):
        self.assertFalse(
            lib.is_proxy_set(
                {
                    "all_proxy": "",
                }
            )
        )

    def test_http_proxy(self):
        self.assertFalse(
            lib.is_proxy_set(
                {
                    "http_proxy": "test.proxy",
                }
            )
        )

    def test_HTTP_PROXY(self):
        # pylint: disable=invalid-name
        self.assertFalse(
            lib.is_proxy_set(
                {
                    "HTTP_PROXY": "test.proxy",
                }
            )
        )

    def test_https_proxy(self):
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "https_proxy": "test.proxy",
                }
            )
        )

    def test_HTTPS_PROXY(self):
        # pylint: disable=invalid-name
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "HTTPS_PROXY": "test.proxy",
                }
            )
        )

    def test_all_proxy(self):
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "all_proxy": "test.proxy",
                }
            )
        )

    def test_ALL_PROXY(self):
        # pylint: disable=invalid-name
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "ALL_PROXY": "test.proxy",
                }
            )
        )

    def test_no_proxy(self):
        self.assertTrue(
            lib.is_proxy_set(
                {
                    "no_proxy": "*",
                    "all_proxy": "test.proxy",
                }
            )
        )


def fixture_logger_call_send(url, data):
    send_msg = "Sending HTTP Request to: {url}"
    if data:
        send_msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
    return mock.call.debug(send_msg.format(url=url, data=data))


def fixture_logger_call_debug_data(url, data):
    send_msg = outdent(
        """\
        Communication debug info for calling: {url}
        --Debug Communication Info Start--
        {data}
        --Debug Communication Info End--"""
    )
    return mock.call.debug(send_msg.format(url=url, data=data))


def fixture_logger_call_connected(url, response_code, response_data):
    result_msg = (
        "Finished calling: {url}\nResponse Code: {code}"
        + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
    )
    return mock.call.debug(
        result_msg.format(url=url, code=response_code, response=response_data)
    )


def fixture_logger_call_not_connected(node, reason):
    msg = "Unable to connect to {node} ({reason})"
    return mock.call.debug(msg.format(node=node, reason=reason))


def fixture_logger_call_proxy_set():
    return mock.call.warning("Proxy is set")


def fixture_logger_calls_on_success(
    url, response_code, response_data, debug_data
):
    return [
        fixture_logger_call_connected(url, response_code, response_data),
        fixture_logger_call_debug_data(url, debug_data),
    ]


def fixture_report_item_list_send(url, data):
    return [
        (
            severity.DEBUG,
            report_codes.NODE_COMMUNICATION_STARTED,
            {
                "target": url,
                "data": data,
            },
        )
    ]


def fixture_report_item_list_debug(url, data):
    return [
        (
            severity.DEBUG,
            report_codes.NODE_COMMUNICATION_DEBUG_INFO,
            {
                "target": url,
                "data": data,
            },
        )
    ]


def fixture_report_item_list_connected(url, response_code, response_data):
    return [
        (
            severity.DEBUG,
            report_codes.NODE_COMMUNICATION_FINISHED,
            {
                "target": url,
                "response_code": response_code,
                "response_data": response_data,
            },
        )
    ]


def fixture_report_item_list_not_connected(node, reason):
    return [
        (
            severity.DEBUG,
            report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
            {
                "node": node,
                "reason": reason,
            },
            None,
        )
    ]


def fixture_report_item_list_proxy_set(node, address):
    return [
        (
            severity.WARNING,
            report_codes.NODE_COMMUNICATION_PROXY_IS_SET,
            {
                "node": node,
                "address": address,
            },
            None,
        )
    ]


def fixture_report_item_list_on_success(
    url, response_code, response_data, debug_data
):
    return fixture_report_item_list_connected(
        url, response_code, response_data
    ) + fixture_report_item_list_debug(url, debug_data)


def fixture_request():
    return Request(RequestTarget("host"), RequestData("action"))


class CommunicatorLoggerTest(TestCase):
    def setUp(self):
        self.logger = mock.MagicMock(spec_set=logging.Logger)
        self.reporter = MockLibraryReportProcessor()
        self.com_logger = lib.LibCommunicatorLogger(self.logger, self.reporter)

    def test_log_request_start(self):
        request = fixture_request()
        self.com_logger.log_request_start(request)
        self.reporter.assert_reports(
            fixture_report_item_list_send(request.url, request.data)
        )
        self.assertEqual(
            [fixture_logger_call_send(request.url, request.data)],
            self.logger.mock_calls,
        )

    def test_log_response_connected(self):
        expected_code = 200
        expected_data = "data"
        expected_debug_data = "* text\n>> data out\n"
        response = Response.connection_successful(
            MockCurlSimple(
                info={pycurl.RESPONSE_CODE: expected_code},
                output=expected_data.encode("utf-8"),
                debug_output=expected_debug_data.encode("utf-8"),
                request=fixture_request(),
            )
        )
        self.com_logger.log_response(response)
        self.reporter.assert_reports(
            fixture_report_item_list_on_success(
                response.request.url,
                expected_code,
                expected_data,
                expected_debug_data,
            )
        )
        logger_calls = fixture_logger_calls_on_success(
            response.request.url,
            expected_code,
            expected_data,
            expected_debug_data,
        )
        self.assertEqual(logger_calls, self.logger.mock_calls)

    @mock.patch("pcs.lib.node_communication.is_proxy_set")
    def test_log_response_not_connected(self, mock_proxy):
        mock_proxy.return_value = False
        expected_debug_data = "* text\n>> data out\n"
        error_msg = "error"
        response = Response.connection_failure(
            MockCurlSimple(
                debug_output=expected_debug_data.encode("utf-8"),
                request=fixture_request(),
            ),
            pycurl.E_HTTP_POST_ERROR,
            error_msg,
        )
        self.com_logger.log_response(response)
        self.reporter.assert_reports(
            fixture_report_item_list_not_connected(
                response.request.host_label, error_msg
            )
            + fixture_report_item_list_debug(
                response.request.url, expected_debug_data
            )
        )
        logger_calls = [
            fixture_logger_call_not_connected(
                response.request.host_label, error_msg
            ),
            fixture_logger_call_debug_data(
                response.request.url, expected_debug_data
            ),
        ]
        self.assertEqual(logger_calls, self.logger.mock_calls)

    @mock.patch("pcs.lib.node_communication.is_proxy_set")
    def test_log_response_not_connected_with_proxy(self, mock_proxy):
        mock_proxy.return_value = True
        expected_debug_data = "* text\n>> data out\n"
        error_msg = "error"
        response = Response.connection_failure(
            MockCurlSimple(
                debug_output=expected_debug_data.encode("utf-8"),
                request=fixture_request(),
            ),
            pycurl.E_HTTP_POST_ERROR,
            error_msg,
        )
        self.com_logger.log_response(response)
        self.reporter.assert_reports(
            fixture_report_item_list_not_connected(
                response.request.host_label, error_msg
            )
            + fixture_report_item_list_proxy_set(
                response.request.host_label, response.request.host_label
            )
            + fixture_report_item_list_debug(
                response.request.url, expected_debug_data
            )
        )
        logger_calls = [
            fixture_logger_call_not_connected(
                response.request.host_label, error_msg
            ),
            fixture_logger_call_proxy_set(),
            fixture_logger_call_debug_data(
                response.request.url, expected_debug_data
            ),
        ]
        self.assertEqual(logger_calls, self.logger.mock_calls)

    def test_log_retry(self):
        prev_addr = "addr"
        prev_port = 2225
        prev_host = Destination(prev_addr, prev_port)
        response = Response.connection_failure(
            MockCurlSimple(request=fixture_request()),
            pycurl.E_HTTP_POST_ERROR,
            "e",
        )
        self.com_logger.log_retry(response, prev_host)
        self.reporter.assert_reports(
            [
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_RETRYING,
                    {
                        "node": response.request.host_label,
                        "failed_address": prev_addr,
                        "failed_port": prev_port,
                        "next_address": response.request.dest.addr,
                        "next_port": settings.pcsd_default_port,
                        "request": response.request.url,
                    },
                    None,
                )
            ]
        )
        logger_call = mock.call.warning(
            (
                "Unable to connect to '{label}' via address '{old_addr}' and "
                "port '{old_port}'. Retrying request '{req}' via address "
                "'{new_addr}' and port '{new_port}'"
            ).format(
                label=response.request.host_label,
                old_addr=prev_addr,
                old_port=prev_port,
                new_addr=response.request.dest.addr,
                new_port=settings.pcsd_default_port,
                req=response.request.url,
            )
        )
        self.assertEqual([logger_call], self.logger.mock_calls)

    def test_log_no_more_addresses(self):
        response = Response.connection_failure(
            MockCurlSimple(request=fixture_request()),
            pycurl.E_HTTP_POST_ERROR,
            "e",
        )
        self.com_logger.log_no_more_addresses(response)
        self.reporter.assert_reports(
            [
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES,
                    {
                        "node": response.request.host_label,
                        "request": response.request.url,
                    },
                    None,
                )
            ]
        )
        logger_call = mock.call.warning(
            "No more addresses for node {label} to run '{req}'".format(
                label=response.request.host_label,
                req=response.request.url,
            )
        )
        self.assertEqual([logger_call], self.logger.mock_calls)
