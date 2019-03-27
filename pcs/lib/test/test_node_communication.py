from __future__ import (
    absolute_import,
    division,
    print_function,
)

import io
import logging

from pcs.test.tools.assertions import assert_report_item_equal
from pcs.test.tools.custom_mock import (
    MockCurl,
    MockCurlSimple,
    MockLibraryReportProcessor,
)
from pcs.test.tools.misc import outdent
from pcs.test.tools.pcs_unittest import (
    mock,
    TestCase,
)

from pcs.common import (
    pcs_pycurl as pycurl,
    report_codes,
)
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.lib.errors import ReportItemSeverity as severity
import pcs.lib.node_communication as lib


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
                    "reason": self.data.decode("utf-8")
                },
                None
            )
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
                    "reason": "HTTP error: 401"
                },
                None
            )
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
                    "reason": "HTTP error: 403"
                },
                None
            )
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
                    "reason": "HTTP error: 404"
                },
                None
            )
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
                    "reason": "HTTP error: 500"
                },
                None
            )
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
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "err"
                },
                None
            )
        )

    def test_timedouted(self):
        response = self.fixture_response_not_connected(
            pycurl.E_OPERATION_TIMEOUTED, "err"
        )
        assert_report_item_equal(
            lib.response_to_report_item(response),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_TIMED_OUT,
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "err"
                },
                None
            )
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
                {
                    "node": self.host,
                    "command": self.request,
                    "reason": "err"
                },
                None
            )
        )


class IsProxySetTest(TestCase):
    def test_without_proxy(self):
        self.assertFalse(lib.is_proxy_set({
            "var1": "value",
            "var2": "val",
        }))

    def test_multiple(self):
        self.assertTrue(lib.is_proxy_set({
            "var1": "val",
            "https_proxy": "test.proxy",
            "var2": "val",
            "all_proxy": "test2.proxy",
            "var3": "val",
        }))

    def test_empty_string(self):
        self.assertFalse(lib.is_proxy_set({
            "all_proxy": "",
        }))

    def test_http_proxy(self):
        self.assertFalse(lib.is_proxy_set({
            "http_proxy": "test.proxy",
        }))

    def test_HTTP_PROXY(self):
        self.assertFalse(lib.is_proxy_set({
            "HTTP_PROXY": "test.proxy",
        }))

    def test_https_proxy(self):
        self.assertTrue(lib.is_proxy_set({
            "https_proxy": "test.proxy",
        }))

    def test_HTTPS_PROXY(self):
        self.assertTrue(lib.is_proxy_set({
            "HTTPS_PROXY": "test.proxy",
        }))

    def test_all_proxy(self):
        self.assertTrue(lib.is_proxy_set({
            "all_proxy": "test.proxy",
        }))

    def test_ALL_PROXY(self):
        self.assertTrue(lib.is_proxy_set({
            "ALL_PROXY": "test.proxy",
        }))

    def test_no_proxy(self):
        self.assertTrue(lib.is_proxy_set({
            "no_proxy": "*",
            "all_proxy": "test.proxy",
        }))


def fixture_logger_call_send(url, data):
    send_msg = "Sending HTTP Request to: {url}"
    if data:
        send_msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
    return mock.call.debug(send_msg.format(url=url, data=data))


def fixture_logger_call_debug_data(url, data):
    send_msg = outdent("""\
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
    return mock.call.debug(result_msg.format(
        url=url, code=response_code, response=response_data
    ))


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
    return [(
        severity.DEBUG,
        report_codes.NODE_COMMUNICATION_STARTED,
        {
            "target": url,
            "data": data,
        }
    )]


def fixture_report_item_list_debug(url, data):
    return [(
        severity.DEBUG,
        report_codes.NODE_COMMUNICATION_DEBUG_INFO,
        {
            "target": url,
            "data": data,
        }
    )]


def fixture_report_item_list_connected(url, response_code, response_data):
    return [(
        severity.DEBUG,
        report_codes.NODE_COMMUNICATION_FINISHED,
        {
            "target": url,
            "response_code": response_code,
            "response_data": response_data,
        }
    )]


def fixture_report_item_list_not_connected(node, reason):
    return [(
        severity.DEBUG,
        report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
        {
            "node": node,
            "reason": reason,
        },
        None
    )]


def fixture_report_item_list_proxy_set(node, address):
    return [(
        severity.WARNING,
        report_codes.NODE_COMMUNICATION_PROXY_IS_SET,
        {
            "node": node,
            "address": address,
        },
        None
    )]


def fixture_report_item_list_on_success(
    url, response_code, response_data, debug_data
):
    return (
        fixture_report_item_list_connected(url, response_code, response_data)
        +
        fixture_report_item_list_debug(url, debug_data)
    )


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
            self.logger.mock_calls
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
                expected_debug_data
            )
        )
        logger_calls = fixture_logger_calls_on_success(
            response.request.url,
            expected_code,
            expected_data,
            expected_debug_data
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
            +
            fixture_report_item_list_debug(
                response.request.url, expected_debug_data
            )
        )
        logger_calls = [
            fixture_logger_call_not_connected(
                response.request.host_label, error_msg
            ),
            fixture_logger_call_debug_data(
                response.request.url, expected_debug_data
            )
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
            +
            fixture_report_item_list_proxy_set(
                response.request.host_label, response.request.host
            )
            +
            fixture_report_item_list_debug(
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
            )
        ]
        self.assertEqual(logger_calls, self.logger.mock_calls)

    def test_log_retry(self):
        prev_host = "prev host"
        response = Response.connection_failure(
            MockCurlSimple(request=fixture_request()),
            pycurl.E_HTTP_POST_ERROR,
            "e",
        )
        self.com_logger.log_retry(response, prev_host)
        self.reporter.assert_reports([(
            severity.WARNING,
            report_codes.NODE_COMMUNICATION_RETRYING,
            {
                "node": response.request.host_label,
                "failed_address": prev_host,
                "next_address": response.request.host,
                "request": response.request.url,
            },
            None
        )])
        logger_call = mock.call.warning(
            (
                "Unable to connect to '{label}' via address '{old_addr}'. "
                "Retrying request '{req}' via address '{new_addr}'"
            ).format(
                label=response.request.host_label,
                old_addr=prev_host,
                new_addr=response.request.host,
                req=response.request.url,
            )
        )
        self.assertEqual([logger_call], self.logger.mock_calls)

    def test_log_no_more_addresses(self):
        response = Response.connection_failure(
            MockCurlSimple(request=fixture_request()),
            pycurl.E_HTTP_POST_ERROR,
            "e"
        )
        self.com_logger.log_no_more_addresses(response)
        self.reporter.assert_reports([(
            severity.WARNING,
            report_codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES,
            {
                "node": response.request.host_label,
                "request": response.request.url,
            },
            None
        )])
        logger_call = mock.call.warning(
            "No more addresses for node {label} to run '{req}'".format(
                label=response.request.host_label,
                req=response.request.url,
            )
        )
        self.assertEqual([logger_call], self.logger.mock_calls)
