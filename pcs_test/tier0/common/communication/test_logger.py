import logging
from textwrap import dedent
from unittest import (
    TestCase,
    mock,
)

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.common.communication import logger
from pcs.common.host import Destination
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.common.reports import codes as report_codes
from pcs.common.reports.processor import ReportProcessorToLog

from pcs_test.tools import fixture
from pcs_test.tools.custom_mock import (
    MockCurlSimple,
    MockLibraryReportProcessor,
)


def fixture_logger_call_send(url, data):
    send_msg = "Sending HTTP Request to: {url}"
    if data:
        send_msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--\n"
    return mock.call.debug(send_msg.format(url=url, data=data))


def fixture_logger_call_debug_data(url, data):
    send_msg = dedent(
        """\
        Communication debug info for calling: {url}
        --Debug Communication Info Start--
        {data}
        --Debug Communication Info End--
        """
    )
    return mock.call.debug(send_msg.format(url=url, data=data))


def fixture_logger_call_connected(url, response_code, response_data):
    result_msg = (
        "Finished calling: {url}\nResponse Code: {code}"
        + "\n--Debug Response Start--\n{response}\n--Debug Response End--\n"
    )
    return mock.call.debug(
        result_msg.format(url=url, code=response_code, response=response_data)
    )


def fixture_logger_call_not_connected(node, reason):
    msg = "Unable to connect to {node} ({reason})"
    return mock.call.debug(msg.format(node=node, reason=reason))


def fixture_logger_call_proxy_set():
    return mock.call.warning(
        "Proxy is set in environment variables, try disabling it"
    )


def fixture_logger_calls_on_success(
    url, response_code, response_data, debug_data
):
    return [
        fixture_logger_call_connected(url, response_code, response_data),
        fixture_logger_call_debug_data(url, debug_data),
    ]


def fixture_report_item_list_send(url, data):
    return [
        fixture.debug(
            report_codes.NODE_COMMUNICATION_STARTED, target=url, data=data
        )
    ]


def fixture_report_item_list_debug(url, data):
    return [
        fixture.debug(
            report_codes.NODE_COMMUNICATION_DEBUG_INFO, target=url, data=data
        )
    ]


def fixture_report_item_list_connected(url, response_code, response_data):
    return [
        fixture.debug(
            report_codes.NODE_COMMUNICATION_FINISHED,
            target=url,
            response_code=response_code,
            response_data=response_data,
        )
    ]


def fixture_report_item_list_not_connected(node, reason):
    return [
        fixture.debug(
            report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
            node=node,
            reason=reason,
        )
    ]


def fixture_report_item_list_proxy_set(node, address):
    return [
        fixture.warn(
            report_codes.NODE_COMMUNICATION_PROXY_IS_SET,
            node=node,
            address=address,
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
        self.log_reporter = ReportProcessorToLog(self.logger)
        self.reporter = MockLibraryReportProcessor()
        self.com_logger = logger.CommunicatorLogger(
            [self.reporter, self.log_reporter]
        )

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

    @mock.patch("pcs.common.communication.logger.is_proxy_set")
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

    @mock.patch("pcs.common.communication.logger.is_proxy_set")
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
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_RETRYING,
                    node=response.request.host_label,
                    failed_address=prev_addr,
                    failed_port=str(prev_port),
                    next_address=response.request.dest.addr,
                    next_port=str(settings.pcsd_default_port),
                    request=response.request.url,
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
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES,
                    node=response.request.host_label,
                    request=response.request.url,
                )
            ]
        )
        logger_call = mock.call.warning(
            "Unable to connect to '{label}' via any of its addresses".format(
                label=response.request.host_label
            )
        )
        self.assertEqual([logger_call], self.logger.mock_calls)
