from __future__ import (
    absolute_import,
    division,
    print_function,
)

import io

from pcs.test.tools.pcs_unittest import mock, TestCase
from pcs.test.tools.custom_mock import (
    MockCurl,
    MockCurlMulti,
)

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.lib.node import NodeAddresses
import pcs.common.node_communicator as lib


class RequestDataUrlEncodeTest(TestCase):
    def test_no_data(self):
        action = "action"
        data = lib.RequestData(action)
        self.assertEqual(action, data.action)
        self.assertEqual(0, len(data.structured_data))
        self.assertEqual("", data.data)

    def test_with_data(self):
        action = "action"
        orig_data = [
            ("key1", "value1"),
            ("spacial characters", "+-+/%&?'\";[]()*^$#@!~`{:}<>")
        ]
        data = lib.RequestData(action, orig_data)
        self.assertEqual(action, data.action)
        self.assertEqual(orig_data, data.structured_data)
        expected_raw_data = (
            "key1=value1&spacial+characters=%2B-%2B%2F%25%26%3F%27%22%3B%5B" +
            "%5D%28%29%2A%5E%24%23%40%21%7E%60%7B%3A%7D%3C%3E"
        )
        self.assertEqual(expected_raw_data, data.data)


class RequestTargetConstructorTest(TestCase):
    def test_no_adresses(self):
        label = "label"
        target = lib.RequestTarget(label)
        self.assertEqual(label, target.label)
        self.assertEqual([label], target.address_list)

    def test_with_adresses(self):
        label = "label"
        address_list = ["a1", "a2"]
        original_list = list(address_list)
        target = lib.RequestTarget(label, address_list=address_list)
        address_list.append("a3")
        self.assertEqual(label, target.label)
        self.assertIsNot(address_list, target.address_list)
        self.assertEqual(original_list, target.address_list)


class RequestTargetFromNodeAdressesTest(TestCase):
    def test_ring0(self):
        ring0 = "ring0"
        target = lib.RequestTarget.from_node_addresses(NodeAddresses(ring0))
        self.assertEqual(ring0, target.label)
        self.assertEqual([ring0], target.address_list)

    def test_ring1(self):
        ring0 = "ring0"
        ring1 = "ring1"
        target = lib.RequestTarget.from_node_addresses(
            NodeAddresses(ring0, ring1)
        )
        self.assertEqual(ring0, target.label)
        self.assertEqual([ring0, ring1], target.address_list)

    def test_ring0_with_label(self):
        ring0 = "ring0"
        label = "label"
        target = lib.RequestTarget.from_node_addresses(
            NodeAddresses(ring0, name=label)
        )
        self.assertEqual(label, target.label)
        self.assertEqual([ring0], target.address_list)

    def test_ring1_with_label(self):
        ring0 = "ring0"
        ring1 = "ring1"
        label = "label"
        target = lib.RequestTarget.from_node_addresses(
            NodeAddresses(ring0, ring1, name=label)
        )
        self.assertEqual(label, target.label)
        self.assertEqual([ring0, ring1], target.address_list)


class RequestUrlTest(TestCase):
    action = "action"

    def _get_request(self, target):
        return lib.Request(target, lib.RequestData(self.action))

    def assert_url(self, actual_url, host, action, port=None):
        if port is None:
            port = settings.pcsd_default_port
        self.assertEqual(
            "https://{host}:{port}/{action}".format(
                host=host, action=action, port=port
            ),
            actual_url
        )

    def test_url_basic(self):
        host = "host"
        self.assert_url(
            self._get_request(lib.RequestTarget(host)).url, host, self.action,
        )

    def test_url_with_port(self):
        host = "host"
        port = 1234
        self.assert_url(
            self._get_request(lib.RequestTarget(host, port=port)).url,
            host, self.action, port=port,
        )

    def test_url_ipv6(self):
        host = "::1"
        self.assert_url(
            self._get_request(lib.RequestTarget(host)).url,
            "[{0}]".format(host), self.action,
        )

    def test_url_multiaddr(self):
        hosts = ["ring0", "ring1"]
        action = "action"
        request = self._get_request(
            lib.RequestTarget.from_node_addresses(NodeAddresses(*hosts))
        )
        self.assert_url(request.url, hosts[0], action)
        request.next_host()
        self.assert_url(request.url, hosts[1], action)


class RequestHostTest(TestCase):
    action = "action"

    def _get_request(self, target):
        return lib.Request(target, lib.RequestData(self.action))

    def test_one_host(self):
        host = "host"
        request = self._get_request(lib.RequestTarget(host))
        self.assertEqual(host, request.host)
        self.assertRaises(StopIteration, request.next_host)

    def test_multiple_hosts(self):
        hosts = ["host1", "host2", "host3"]
        request = self._get_request(lib.RequestTarget("label", hosts))
        for host in hosts:
            self.assertEqual(host, request.host)
            if host == hosts[-1]:
                self.assertRaises(StopIteration, request.next_host)
            else:
                request.next_host()


class RequestCookiesTest(TestCase):
    def _get_request(self, token=None):
        return lib.Request(
            lib.RequestTarget("host", token=token), lib.RequestData("action")
        )

    def test_with_token(self):
        token = "token1"
        self.assertEqual({"token": token}, self._get_request(token).cookies)

    def test_without_token(self):
        self.assertEqual({}, self._get_request().cookies)


class ResponseTest(TestCase):
    def fixture_handle(self, info, request, data, debug):
        handle = MockCurl(info)
        handle.request_obj = request
        handle.output_buffer = io.BytesIO()
        handle.output_buffer.write(data.encode("utf-8"))
        handle.debug_buffer = io.BytesIO()
        handle.debug_buffer.write(debug.encode("utf-8"))
        return handle

    def test_connection_successful(self):
        request = lib.Request(
            lib.RequestTarget("host"), lib.RequestData("request")
        )
        output = "output"
        debug = "debug"
        response_code = 200
        handle = self.fixture_handle(
            {pycurl.RESPONSE_CODE: 200}, request, output, debug
        )
        response = lib.Response.connection_successful(handle)
        self.assertEqual(request, response.request)
        self.assertTrue(response.was_connected)
        self.assertIsNone(response.errno)
        self.assertIsNone(response.error_msg)
        self.assertEqual(output, response.data)
        self.assertEqual(debug, response.debug)
        self.assertEqual(response_code, response.response_code)

    def test_connection_failure(self):
        request = lib.Request(
            lib.RequestTarget("host"), lib.RequestData("request")
        )
        output = "output"
        debug = "debug"
        errno = 1
        error_msg = "error"
        handle = self.fixture_handle({}, request, output, debug)
        response = lib.Response.connection_failure(handle, errno, error_msg)
        self.assertEqual(request, response.request)
        self.assertFalse(response.was_connected)
        self.assertEqual(errno, response.errno)
        self.assertEqual(error_msg, response.error_msg)
        self.assertEqual(output, response.data)
        self.assertEqual(debug, response.debug)
        self.assertIsNone(response.response_code)


@mock.patch("pcs.common.node_communicator.pycurl.Curl")
class CreateRequestHandleTest(TestCase):
    _common_opts = {
        pycurl.PROTOCOLS: pycurl.PROTO_HTTPS,
        pycurl.VERBOSE: 1,
        pycurl.SSL_VERIFYHOST: 0,
        pycurl.SSL_VERIFYPEER: 0,
        pycurl.NOSIGNAL: 1,
    }

    def test_all_info(self, mock_curl):
        mock_curl.return_value = MockCurl(
            None, b"output", [
                (pycurl.DEBUG_TEXT, b"debug"),
                (pycurl.DEBUG_DATA_OUT, b"info\n"),
            ]
        )
        request = lib.Request(
            lib.RequestTarget(
                "label", ["host1", "host2"], port=123, token="token_val",
            ),
            lib.RequestData("action", [("data", "value")])
        )
        cookies = {
            "name1": "val1",
            "name2": "val2",
        }
        handle = lib._create_request_handle(request, cookies, 1)
        expected_opts = {
            pycurl.TIMEOUT: 1,
            pycurl.URL: request.url.encode("utf-8"),
            pycurl.COOKIE: "name1=val1;name2=val2;token=token_val".encode(
                "utf-8"
            ),
            pycurl.COPYPOSTFIELDS: "data=value".encode("utf-8"),
        }
        expected_opts.update(self._common_opts)
        self.assertLessEqual(
            set(expected_opts.items()), set(handle.opts.items())
        )
        self.assertIs(request, handle.request_obj)
        self.assertEqual("", handle.output_buffer.getvalue().decode("utf-8"))
        self.assertEqual("", handle.debug_buffer.getvalue().decode("utf-8"))
        handle.perform()
        self.assertEqual(
            "output", handle.output_buffer.getvalue().decode("utf-8")
        )
        self.assertEqual(
            "* debug\n>> info\n", handle.debug_buffer.getvalue().decode("utf-8")
        )

    def test_basic(self, mock_curl):
        mock_curl.return_value = MockCurl(None)
        request = lib.Request(
            lib.RequestTarget("label"), lib.RequestData("action")
        )
        handle = lib._create_request_handle(request, {}, 10)
        expected_opts = {
            pycurl.TIMEOUT: 10,
            pycurl.URL: request.url.encode("utf-8"),
        }
        expected_opts.update(self._common_opts)
        self.assertLessEqual(
            set(expected_opts.items()), set(handle.opts.items())
        )
        self.assertFalse(pycurl.COOKIE in handle.opts)
        self.assertFalse(pycurl.COPYPOSTFIELDS in handle.opts)
        self.assertIs(request, handle.request_obj)
        self.assertEqual("", handle.output_buffer.getvalue().decode("utf-8"))
        self.assertEqual("", handle.debug_buffer.getvalue().decode("utf-8"))
        handle.perform()
        self.assertEqual("", handle.output_buffer.getvalue().decode("utf-8"))
        self.assertEqual("", handle.debug_buffer.getvalue().decode("utf-8"))


def fixture_request(host_id=1, action="action"):
    return lib.Request(
        lib.RequestTarget("host{0}".format(host_id)), lib.RequestData(action),
    )


class CommunicatorBaseTest(TestCase):
    def setUp(self):
        self.mock_com_log = mock.MagicMock(
            spec_set=lib.CommunicatorLoggerInterface
        )

    def get_communicator(self):
        return lib.Communicator(self.mock_com_log, None, None)

    def get_multiaddress_communicator(self):
        return lib.MultiaddressCommunicator(self.mock_com_log, None, None)


@mock.patch(
    "pcs.common.node_communicator.pycurl.CurlMulti",
    side_effect=lambda: MockCurlMulti([1])
)
@mock.patch("pcs.common.node_communicator._create_request_handle")
class CommunicatorSimpleTest(CommunicatorBaseTest):
    def get_response(self, com, mock_create_handle, handle):
        request = fixture_request(0, "action")
        handle.request_obj = request
        mock_create_handle.return_value = handle
        com.add_requests([request])
        self.assertEqual(0, self.mock_com_log.log_request_start.call_count)
        response_list = list(com.start_loop())
        self.assertEqual(1, len(response_list))
        response = response_list[0]
        self.assertIs(handle, response.handle)
        self.assertIs(request, response.request)
        mock_create_handle.assert_called_once_with(
            request, {}, settings.default_request_timeout
        )
        return response

    def assert_common_checks(self, com, response):
        self.assertEqual(response.handle.error is None, response.was_connected)
        self.mock_com_log.log_request_start.assert_called_once_with(response.request)
        self.mock_com_log.log_response.assert_called_once_with(response)
        self.assertEqual(0, self.mock_com_log.log_retry.call_count)
        self.assertEqual(0, self.mock_com_log.log_no_more_addresses.call_count)
        com._multi_handle.assert_no_handle_left()

    def test_simple(self, mock_create_handle, _):
        com = self.get_communicator()
        response = self.get_response(com, mock_create_handle, MockCurl())
        self.assert_common_checks(com, response)

    def test_failure(self, mock_create_handle, _):
        com = self.get_communicator()
        expected_reason = "expected reason"
        errno = pycurl.E_SEND_ERROR
        response = self.get_response(
            com, mock_create_handle, MockCurl(error=(errno, expected_reason))
        )
        self.assert_common_checks(com, response)
        self.assertEqual(errno, response.errno)
        self.assertEqual(expected_reason, response.error_msg)


class CommunicatorMultiTest(CommunicatorBaseTest):
    @mock.patch("pcs.common.node_communicator._create_request_handle")
    @mock.patch(
        "pcs.common.node_communicator.pycurl.CurlMulti",
        side_effect=lambda: MockCurlMulti([1, 1])
    )
    def test_call_start_loop_multiple_times(self, _,  mock_create_handle):
        com = self.get_communicator()
        mock_create_handle.side_effect = lambda request, _, __: MockCurl(
            request=request
        )
        com.add_requests([fixture_request(i) for i in range(2)])
        next(com.start_loop())
        with self.assertRaises(AssertionError):
            next(com.start_loop())

    @mock.patch("pcs.common.node_communicator.pycurl.Curl")
    @mock.patch(
        "pcs.common.node_communicator.pycurl.CurlMulti",
        side_effect=lambda: MockCurlMulti([2, 0, 0, 1, 0, 1, 1])
    )
    def test_multiple(self, _, mock_curl):
        com = self.get_communicator()
        action = "action"
        counter = {"counter": 0}
        def _create_mock_curl():
            counter["counter"] += 1
            return (
                MockCurl()
                if counter["counter"] != 2
                else MockCurl(error=(pycurl.E_SEND_ERROR, "reason"))
            )
        mock_curl.side_effect = _create_mock_curl
        request_list = [fixture_request(i, action) for i in range(3)]
        com.add_requests(request_list)
        self.assertEqual(0, self.mock_com_log.log_request_start.call_count)
        response_list = []
        for response in com.start_loop():
            if len(response_list) == 0:
                request = fixture_request(3, action)
                request_list.append(request)
                com.add_requests([request])
            elif len(response_list) == 3:
                request = fixture_request(4, action)
                request_list.append(request)
                com.add_requests([request])
            response_list.append(response)
        self.assertEqual(len(request_list), len(response_list))
        self.assertEqual(request_list, [r.request for r in response_list])
        for i in range(len(request_list)):
            self.assertEqual(i != 1, response_list[i].was_connected)
        logger_calls = (
            [mock.call.log_request_start(request_list[i]) for i in range(3)]
            +
            [
                mock.call.log_response(response_list[0]),
                mock.call.log_request_start(request_list[3]),
            ]
            +
            [mock.call.log_response(response_list[i]) for i in range(1, 4)]
            +
            [
                mock.call.log_request_start(request_list[4]),
                mock.call.log_response(response_list[4]),
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        com._multi_handle.assert_no_handle_left()


def fixture_logger_request_retry_calls(response, host):
    return [
        mock.call.log_request_start(response.request),
        mock.call.log_response(response),
        mock.call.log_retry(response, host),
    ]


@mock.patch.object(lib.Response, "connection_failure")
@mock.patch.object(lib.Response, "connection_successful")
@mock.patch(
    "pcs.common.node_communicator.pycurl.CurlMulti",
    side_effect=lambda: MockCurlMulti([1, 0, 1, 1, 1])
)
@mock.patch("pcs.common.node_communicator._create_request_handle")
class MultiaddressCommunicatorTest(CommunicatorBaseTest):
    def test_success(
        self, mock_create_handle, _, mock_con_successful, mock_con_failure
    ):
        com = self.get_multiaddress_communicator()
        counter = {"counter": 0}
        expected_response_list = []
        def _con_successful(handle):
            response = lib.Response(handle, True)
            expected_response_list.append(response)
            return response

        def _con_failure(handle, errno, err_msg):
            response = lib.Response(handle, False, errno, err_msg)
            expected_response_list.append(response)
            return response

        def _mock_create_request_handle(request, _, __):
            counter["counter"] += 1
            return(
                MockCurl(request=request)
                if counter["counter"] > 2
                else MockCurl(
                    error=(pycurl.E_SEND_ERROR, "reason"),
                    request=request,
                )
            )
        mock_con_successful.side_effect = _con_successful
        mock_con_failure.side_effect = _con_failure
        mock_create_handle.side_effect = _mock_create_request_handle
        request = lib.Request(
            lib.RequestTarget("label", ["host{0}".format(i) for i in range(4)]),
            lib.RequestData("action")
        )
        com.add_requests([request])
        response_list = list(com.start_loop())
        self.assertEqual(1, len(response_list))
        response = response_list[0]
        self.assertIs(response, expected_response_list[-1])
        self.assertTrue(response.was_connected)
        self.assertIs(request, response.request)
        self.assertEqual("host2", request.host)
        self.assertEqual(3, mock_create_handle.call_count)
        self.assertEqual(3, len(expected_response_list))
        mock_create_handle.assert_has_calls([
            mock.call(request, {}, settings.default_request_timeout)
            for _ in range(3)
        ])
        logger_calls = (
            fixture_logger_request_retry_calls(
                expected_response_list[0], "host0"
            )
            +
            fixture_logger_request_retry_calls(
                expected_response_list[1], "host1"
            )
            +
            [
                mock.call.log_request_start(request),
                mock.call.log_response(response),
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        com._multi_handle.assert_no_handle_left()

    def test_failure(
        self, mock_create_handle, _, mock_con_successful, mock_con_failure
    ):
        expected_response_list = []
        def _con_failure(handle, errno, err_msg):
            response = lib.Response(handle, False, errno, err_msg)
            expected_response_list.append(response)
            return response

        mock_con_failure.side_effect = _con_failure
        com = self.get_multiaddress_communicator()
        mock_create_handle.side_effect = lambda request, _, __: MockCurl(
            error=(pycurl.E_SEND_ERROR, "reason"), request=request,
        )
        request = lib.Request(
            lib.RequestTarget("label", ["host{0}".format(i) for i in range(4)]),
            lib.RequestData("action")
        )
        com.add_requests([request])
        response_list = list(com.start_loop())
        self.assertEqual(1, len(response_list))
        response = response_list[0]
        self.assertFalse(response.was_connected)
        self.assertIs(request, response.request)
        self.assertEqual("host3", request.host)
        self.assertEqual(4, mock_create_handle.call_count)
        mock_con_successful.assert_not_called()
        self.assertEqual(4, len(expected_response_list))
        mock_create_handle.assert_has_calls([
            mock.call(request, {}, settings.default_request_timeout)
            for _ in range(3)
        ])
        logger_calls = (
            fixture_logger_request_retry_calls(
                expected_response_list[0], "host0"
            )
            +
            fixture_logger_request_retry_calls(
                expected_response_list[1], "host1"
            )
            +
            fixture_logger_request_retry_calls(
                expected_response_list[2], "host2"
            )
            +
            [
                mock.call.log_request_start(request),
                mock.call.log_response(response),
                mock.call.log_no_more_addresses(response)
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        com._multi_handle.assert_no_handle_left()

