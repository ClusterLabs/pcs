import io
from unittest import (
    TestCase,
    mock,
)

import pcs.common.node_communicator as lib
from pcs import settings
from pcs.common import host
from pcs.common import pcs_pycurl as pycurl
from pcs.common.host import Destination

from pcs_test.tools.custom_mock import (
    MockCurl,
    MockCurlMulti,
)

PORT = settings.pcsd_default_port


class NodeTargetFactory(TestCase):
    def setUp(self):
        self.known_name = "node"
        self.unknown_name = "none"
        self.known_host = host.PcsKnownHost(
            self.known_name, "token", [host.Destination("addr", "port")]
        )
        self.factory = lib.NodeTargetFactory({self.known_name: self.known_host})

    def assert_equal_known_host_target(self, known_host, target):
        self.assertEqual(known_host.name, target.label)
        self.assertEqual(known_host.token, target.token)
        self.assertEqual(known_host.dest_list, target.dest_list)

    def test_get_target_success(self):
        self.assert_equal_known_host_target(
            self.known_host, self.factory.get_target(self.known_name)
        )

    def test_get_target_not_found(self):
        with self.assertRaises(lib.HostNotFound) as cm:
            self.factory.get_target(self.unknown_name)
        self.assertEqual(self.unknown_name, cm.exception.name)

    def test_from_hostname_known(self):
        self.assert_equal_known_host_target(
            self.known_host,
            self.factory.get_target_from_hostname(self.known_name),
        )

    def test_from_hostname_unknown(self):
        target = self.factory.get_target_from_hostname(self.unknown_name)
        self.assertEqual(self.unknown_name, target.label)
        self.assertEqual(None, target.token)
        self.assertEqual(
            [host.Destination(self.unknown_name, PORT)], target.dest_list
        )


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
            ("spacial characters", "+-+/%&?'\";[]()*^$#@!~`{:}<>"),
        ]
        data = lib.RequestData(action, orig_data)
        self.assertEqual(action, data.action)
        self.assertEqual(orig_data, data.structured_data)
        expected_raw_data_variants = (
            "key1=value1&spacial+characters=%2B-%2B%2F%25%26%3F%27%22%3B%5B"
            "%5D%28%29%2A%5E%24%23%40%21%7E%60%7B%3A%7D%3C%3E",
            "key1=value1&spacial+characters=%2B-%2B%2F%25%26%3F%27%22%3B%5B"
            "%5D%28%29%2A%5E%24%23%40%21~%60%7B%3A%7D%3C%3E",
        )
        self.assertTrue(data.data in expected_raw_data_variants)


def _addr_list_to_dest(addr_list, port=None):
    return [Destination(addr, port) for addr in addr_list]


class RequestTargetConstructorTest(TestCase):
    def test_no_addresses(self):
        label = "label"
        target = lib.RequestTarget(label)
        self.assertEqual(label, target.label)
        self.assertEqual(
            _addr_list_to_dest([label], port=PORT), target.dest_list
        )

    def test_with_addresses(self):
        label = "label"
        address_list = ["a1", "a2"]
        original_list = list(address_list)
        target = lib.RequestTarget(
            label, dest_list=_addr_list_to_dest(address_list)
        )
        address_list.append("a3")
        self.assertEqual(label, target.label)
        self.assertIsNot(_addr_list_to_dest(address_list), target.dest_list)
        self.assertEqual(_addr_list_to_dest(original_list), target.dest_list)


class RequestTargetFromKnownHost(TestCase):
    def test_success(self):
        known_host = host.PcsKnownHost(
            "name",
            "token",
            [
                host.Destination("addr1", "addr2"),
                host.Destination("addr2", "port2"),
            ],
        )
        target = lib.RequestTarget.from_known_host(known_host)
        self.assertEqual(known_host.name, target.label)
        self.assertEqual(known_host.token, target.token)
        self.assertEqual(known_host.dest_list, target.dest_list)


class RequestUrlTest(TestCase):
    action = "action"

    def _get_request(self, target):
        return lib.Request(target, lib.RequestData(self.action))

    def assert_url(self, actual_url, hostname, action, port=None):
        if port is None:
            port = settings.pcsd_default_port
        self.assertEqual(f"https://{hostname}:{port}/{action}", actual_url)

    def test_url_basic(self):
        hostname = "host"
        self.assert_url(
            self._get_request(lib.RequestTarget(hostname)).url,
            hostname,
            self.action,
        )

    def test_url_with_port(self):
        hostname = "host"
        port = 1234
        self.assert_url(
            self._get_request(
                lib.RequestTarget(
                    hostname, dest_list=[Destination(hostname, port)]
                )
            ).url,
            hostname,
            self.action,
            port=port,
        )

    def test_url_ipv6(self):
        host_addr = "::1"
        self.assert_url(
            self._get_request(lib.RequestTarget(host_addr)).url,
            "[{0}]".format(host_addr),
            self.action,
        )

    def test_url_multiaddr(self):
        hosts = ["ring0", "ring1"]
        action = "action"
        request = self._get_request(
            lib.RequestTarget("label", dest_list=_addr_list_to_dest(hosts))
        )
        self.assert_url(request.url, hosts[0], action)
        request.next_dest()
        self.assert_url(request.url, hosts[1], action)


class RequestHostTest(TestCase):
    action = "action"

    def _get_request(self, target):
        return lib.Request(target, lib.RequestData(self.action))

    def test_one_host(self):
        hostname = "host"
        request = self._get_request(lib.RequestTarget(hostname))
        self.assertEqual(Destination(hostname, PORT), request.dest)
        self.assertRaises(StopIteration, request.next_dest)

    def test_multiple_hosts(self):
        hosts = ["host1", "host2", "host3"]
        request = self._get_request(
            lib.RequestTarget("label", dest_list=_addr_list_to_dest(hosts))
        )
        for hostname in hosts:
            self.assertEqual(Destination(hostname, None), request.dest)
            if hostname == hosts[-1]:
                self.assertRaises(StopIteration, request.next_dest)
            else:
                request.next_dest()


class RequestCookiesTest(TestCase):
    @staticmethod
    def _get_request(token=None):
        return lib.Request(
            lib.RequestTarget("host", token=token), lib.RequestData("action")
        )

    def test_with_token(self):
        token = "token1"
        self.assertEqual({"token": token}, self._get_request(token).cookies)

    def test_without_token(self):
        self.assertEqual({}, self._get_request().cookies)


class ResponseTest(TestCase):
    @staticmethod
    def fixture_handle(info, request, data, debug):
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
    # pylint: disable=no-member
    _common_opts = {
        pycurl.PROTOCOLS: pycurl.PROTO_HTTPS,
        pycurl.VERBOSE: 1,
        pycurl.SSL_VERIFYHOST: 0,
        pycurl.SSL_VERIFYPEER: 0,
        pycurl.NOSIGNAL: 1,
    }

    def test_all_info(self, mock_curl):
        mock_curl.return_value = MockCurl(
            None,
            b"output",
            [
                (pycurl.DEBUG_TEXT, b"debug"),
                (pycurl.DEBUG_DATA_OUT, b"info\n"),
            ],
        )
        request = lib.Request(
            lib.RequestTarget(
                "label",
                token="token_val",
                dest_list=_addr_list_to_dest(["host1", "host2"], port=123),
            ),
            lib.RequestData("action", [("data", "value")]),
        )
        cookies = {
            "name1": "val1",
            "name2": "val2",
        }
        # pylint: disable=protected-access
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
        # pylint: disable=protected-access
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
        lib.RequestTarget("host{0}".format(host_id)),
        lib.RequestData(action),
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
    side_effect=lambda: MockCurlMulti([1]),
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
        self.mock_com_log.log_request_start.assert_called_once_with(
            response.request
        )
        self.mock_com_log.log_response.assert_called_once_with(response)
        self.assertEqual(0, self.mock_com_log.log_retry.call_count)
        self.assertEqual(0, self.mock_com_log.log_no_more_addresses.call_count)
        # pylint: disable=protected-access
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
        side_effect=lambda: MockCurlMulti([1, 1]),
    )
    def test_call_start_loop_multiple_times(self, _, mock_create_handle):
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
        side_effect=lambda: MockCurlMulti([2, 0, 0, 1, 0, 1, 1]),
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
            if not response_list:
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
            + [
                mock.call.log_response(response_list[0]),
                mock.call.log_request_start(request_list[3]),
            ]
            + [mock.call.log_response(response_list[i]) for i in range(1, 4)]
            + [
                mock.call.log_request_start(request_list[4]),
                mock.call.log_response(response_list[4]),
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        # pylint: disable=no-member, protected-access
        com._multi_handle.assert_no_handle_left()


def fixture_logger_request_retry_calls(response, hostname):
    return [
        mock.call.log_request_start(response.request),
        mock.call.log_response(response),
        mock.call.log_retry(response, hostname),
    ]


@mock.patch.object(lib.Response, "connection_failure")
@mock.patch.object(lib.Response, "connection_successful")
@mock.patch(
    "pcs.common.node_communicator.pycurl.CurlMulti",
    side_effect=lambda: MockCurlMulti([1, 0, 1, 1, 1]),
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
            return (
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
            lib.RequestTarget(
                "label",
                dest_list=_addr_list_to_dest(
                    ["host{0}".format(i) for i in range(4)]
                ),
            ),
            lib.RequestData("action"),
        )
        com.add_requests([request])
        response_list = list(com.start_loop())
        self.assertEqual(1, len(response_list))
        response = response_list[0]
        self.assertIs(response, expected_response_list[-1])
        self.assertTrue(response.was_connected)
        self.assertIs(request, response.request)
        self.assertEqual(Destination("host2", None), request.dest)
        self.assertEqual(3, mock_create_handle.call_count)
        self.assertEqual(3, len(expected_response_list))
        mock_create_handle.assert_has_calls(
            [
                mock.call(request, {}, settings.default_request_timeout)
                for _ in range(3)
            ]
        )
        logger_calls = (
            fixture_logger_request_retry_calls(
                expected_response_list[0], Destination("host0", None)
            )
            + fixture_logger_request_retry_calls(
                expected_response_list[1], Destination("host1", None)
            )
            + [
                mock.call.log_request_start(request),
                mock.call.log_response(response),
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        # pylint: disable=no-member, protected-access
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
            error=(pycurl.E_SEND_ERROR, "reason"),
            request=request,
        )
        request = lib.Request(
            lib.RequestTarget(
                "label",
                dest_list=_addr_list_to_dest(
                    ["host{0}".format(i) for i in range(4)]
                ),
            ),
            lib.RequestData("action"),
        )
        com.add_requests([request])
        response_list = list(com.start_loop())
        self.assertEqual(1, len(response_list))
        response = response_list[0]
        self.assertFalse(response.was_connected)
        self.assertIs(request, response.request)
        self.assertEqual(Destination("host3", None), request.dest)
        self.assertEqual(4, mock_create_handle.call_count)
        mock_con_successful.assert_not_called()
        self.assertEqual(4, len(expected_response_list))
        mock_create_handle.assert_has_calls(
            [
                mock.call(request, {}, settings.default_request_timeout)
                for _ in range(3)
            ]
        )
        logger_calls = (
            fixture_logger_request_retry_calls(
                expected_response_list[0], Destination("host0", None)
            )
            + fixture_logger_request_retry_calls(
                expected_response_list[1], Destination("host1", None)
            )
            + fixture_logger_request_retry_calls(
                expected_response_list[2], Destination("host2", None)
            )
            + [
                mock.call.log_request_start(request),
                mock.call.log_response(response),
                mock.call.log_no_more_addresses(response),
            ]
        )
        self.assertEqual(logger_calls, self.mock_com_log.mock_calls)
        # pylint: disable=no-member, protected-access
        com._multi_handle.assert_no_handle_left()
