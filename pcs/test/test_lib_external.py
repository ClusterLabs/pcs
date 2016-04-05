from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
import logging
try:
    # python2
    from urllib2 import (
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )
except ImportError:
    # python3
    from urllib.error import (
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )

from pcs.test.tools.pcs_mock import mock
from pcs.test.library_test_tools import LibraryAssertionMixin

from pcs.lib import error_codes
from pcs.lib.errors import ReportItemSeverity as severity
import pcs.lib.external as lib

@mock.patch("subprocess.Popen", autospec=True)
class CommandRunnerTest(TestCase, LibraryAssertionMixin):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)

    def assert_popen_called_with(self, mock_popen, args, kwargs):
        self.assertEqual(mock_popen.call_count, 1)
        real_args, real_kwargs = mock_popen.call_args
        filtered_kwargs = dict([
            (name, value) for name, value in real_kwargs.items()
            if name in kwargs
        ])
        self.assertEqual(real_args, (args,))
        self.assertEqual(filtered_kwargs, kwargs)

    def test_basic(self, mock_popen):
        expected_output = "expected output"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (expected_output, "dummy")
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger)
        real_output, real_retval = runner.run(command)

        self.assertEqual(real_output, expected_output)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {}, "stdin": None,}
        )
        logger_calls = [
            mock.call("Running: {0}".format(command_str)),
            mock.call("""\
Finished running: {0}
Return value: {1}
--Debug Output Start--
{2}
--Debug Output End--""".format(command_str, expected_retval, expected_output))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_env(self, mock_popen):
        expected_output = "expected output"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (expected_output, "dummy")
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger, {"a": "a", "b": "b"})
        real_output, real_retval = runner.run(
            command,
            env_extend={"b": "B", "c": "C"}
        )

        self.assertEqual(real_output, expected_output)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {"a": "a", "b": "b", "c": "C"}, "stdin": None,}
        )
        logger_calls = [
            mock.call("Running: {0}".format(command_str)),
            mock.call("""\
Finished running: {0}
Return value: {1}
--Debug Output Start--
{2}
--Debug Output End--""".format(command_str, expected_retval, expected_output))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_stdin(self, mock_popen):
        expected_output = "expected output"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        stdin = "stdin string"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (expected_output, "dummy")
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger)
        real_output, real_retval = runner.run(command, stdin_string=stdin)

        self.assertEqual(real_output, expected_output)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(stdin)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {}, "stdin": -1}
        )
        logger_calls = [
            mock.call("""\
Running: {0}
--Debug Input Start--
{1}
--Debug Input End--""".format(command_str, stdin)),
            mock.call("""\
Finished running: {0}
Return value: {1}
--Debug Output Start--
{2}
--Debug Output End--""".format(command_str, expected_retval, expected_output))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_popen_error(self, mock_popen):
        expected_error = "expected error"
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        exception = OSError()
        exception.strerror = expected_error
        mock_popen.side_effect = exception

        runner = lib.CommandRunner(self.mock_logger)
        self.assert_raise_library_error(
            lambda: runner.run(command),
            (
                severity.ERROR,
                error_codes.RUN_EXTERNAL_PROCESS_ERROR,
                {
                    "command_raw": command,
                    "command": command_str,
                    "reason": expected_error
                }
            )
        )

        mock_process.communicate.assert_not_called()
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {}, "stdin": None,}
        )
        logger_calls = [
            mock.call("Running: {0}".format(command_str)),
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_communicate_error(self, mock_popen):
        expected_error = "expected error"
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        exception = OSError()
        exception.strerror = expected_error
        mock_process.communicate.side_effect = exception
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger)
        self.assert_raise_library_error(
            lambda: runner.run(command),
            (
                severity.ERROR,
                error_codes.RUN_EXTERNAL_PROCESS_ERROR,
                {
                    "command_raw": command,
                    "command": command_str,
                    "reason": expected_error
                }
            )
        )

        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {}, "stdin": None,}
        )
        logger_calls = [
            mock.call("Running: {0}".format(command_str)),
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)


@mock.patch(
    "pcs.lib.external.NodeCommunicator._NodeCommunicator__get_opener",
    autospec=True
)
class NodeCommunicatorTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)

    def fixture_response(self, response_code, response_data):
        response = mock.MagicMock(["getcode", "read"])
        response.getcode.return_value = response_code
        response.read.return_value = response_data.encode("utf-8")
        return response

    def fixture_http_exception(self, response_code, response_data):
        response = urllib_HTTPError("url", response_code, "msg", [], None)
        response.read = mock.MagicMock(
            return_value=response_data.encode("utf-8")
        )
        return response

    def fixture_logger_call_send(self, url, data):
        send_msg = "Sending HTTP Request to: {url}"
        if data:
            send_msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
        return mock.call(send_msg.format(url=url, data=data))

    def fixture_logger_calls(self, url, data, response_code, response_data):
        result_msg = (
            "Finished calling: {url}\nResponse Code: {code}"
            + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
        )
        return [
            self.fixture_logger_call_send(url, data),
            mock.call(result_msg.format(
                url=url, code=response_code, response=response_data
            ))
        ]

    def fixture_url(self, host, request):
        return "https://{host}:2224/{request}".format(
            host=host, request=request
        )

    def test_success(self, mock_get_opener):
        host = "test_host"
        request = "test_request"
        data = '{"key1": "value1", "key2": ["value2a", "value2b"]}'
        expected_response_code = 200
        expected_response_data = "expected response data"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        mock_opener.open.return_value = self.fixture_response(
            expected_response_code, expected_response_data
        )

        comm = lib.NodeCommunicator(self.mock_logger, {})
        real_response = comm.call_host(host, request, data)
        self.assertEqual(expected_response_data, real_response)

        mock_opener.addheaders.append.assert_not_called()
        mock_opener.open.assert_called_once_with(
            self.fixture_url(host, request),
            data.encode("utf-8")
        )
        logger_calls = self.fixture_logger_calls(
            self.fixture_url(host, request),
            data,
            expected_response_code,
            expected_response_data
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_ipv6(self, mock_get_opener):
        host = "cafe::1"
        request = "test_request"
        data = None
        token = "test_token"
        expected_response_code = 200
        expected_response_data = "expected response data"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        mock_opener.open.return_value = self.fixture_response(
            expected_response_code, expected_response_data
        )

        comm = lib.NodeCommunicator(self.mock_logger, {host: token,})
        real_response = comm.call_host(host, request, data)
        self.assertEqual(expected_response_data, real_response)

        mock_opener.addheaders.append.assert_called_once_with(
            ("Cookie", "token={0}".format(token))
        )
        mock_opener.open.assert_called_once_with(
            self.fixture_url("[{0}]".format(host), request),
            data
        )
        logger_calls = self.fixture_logger_calls(
            self.fixture_url("[{0}]".format(host), request),
            data,
            expected_response_code,
            expected_response_data
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_auth_token(self, mock_get_opener):
        host = "test_host"
        token = "test_token"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(
            self.mock_logger,
            {
                "some_host": "some_token",
                host: token,
                "other_host": "other_token"
            }
        )
        dummy_response = comm.call_host(host, "test_request", None)

        mock_opener.addheaders.append.assert_called_once_with(
            ("Cookie", "token={0}".format(token))
        )

    def test_user(self, mock_get_opener):
        host = "test_host"
        user = "test_user"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(self.mock_logger, {}, user=user)
        dummy_response = comm.call_host(host, "test_request", None)

        mock_opener.addheaders.append.assert_called_once_with(
            ("Cookie", "CIB_user={0}".format(user))
        )

    def test_one_group(self, mock_get_opener):
        host = "test_host"
        groups = ["group1"]
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(self.mock_logger, {}, groups=groups)
        dummy_response = comm.call_host(host, "test_request", None)

        mock_opener.addheaders.append.assert_called_once_with(
            (
                "Cookie",
                "CIB_user_groups={0}".format("Z3JvdXAx".encode("utf8"))
            )
        )

    def test_all_options(self, mock_get_opener):
        host = "test_host"
        token = "test_token"
        user = "test_user"
        groups = ["group1", "group2"]
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(
            self.mock_logger,
            {host: token},
            user, groups
        )
        dummy_response = comm.call_host(host, "test_request", None)

        mock_opener.addheaders.append.assert_called_once_with(
            (
                "Cookie",
                "token={token};CIB_user={user};CIB_user_groups={groups}".format(
                    token=token,
                    user=user,
                    groups="Z3JvdXAxIGdyb3VwMg==".encode("utf-8")
                )
            )
        )
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

    def base_test_http_error(self, mock_get_opener, code, exception):
        host = "test_host"
        request = "test_request"
        data = None
        expected_response_code = code
        expected_response_data = "expected response data"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        mock_opener.open.side_effect = self.fixture_http_exception(
            expected_response_code, expected_response_data
        )

        comm = lib.NodeCommunicator(self.mock_logger, {})
        self.assertRaises(
            exception,
            lambda: comm.call_host(host, request, data)
        )

        mock_opener.addheaders.append.assert_not_called()
        mock_opener.open.assert_called_once_with(
            self.fixture_url(host, request),
            data
        )
        logger_calls = self.fixture_logger_calls(
            self.fixture_url(host, request),
            data,
            expected_response_code,
            expected_response_data
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)

    def test_no_authenticated(self, mock_get_opener):
        self.base_test_http_error(
            mock_get_opener,
            401,
            lib.NodeAuthenticationException
        )

    def test_permission_denied(self, mock_get_opener):
        self.base_test_http_error(
            mock_get_opener,
            403,
            lib.NodePermissionDeniedException
        )

    def test_unsupported_command(self, mock_get_opener):
        self.base_test_http_error(
            mock_get_opener,
            404,
            lib.NodeUnsupportedCommandException
        )

    def test_other_error(self, mock_get_opener):
        self.base_test_http_error(
            mock_get_opener,
            500,
            lib.NodeCommunicationException
        )

    def test_connection_error(self, mock_get_opener):
        host = "test_host"
        request = "test_request"
        data = None
        expected_reason = "expected reason"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener
        mock_opener.open.side_effect = urllib_URLError(expected_reason)

        comm = lib.NodeCommunicator(self.mock_logger, {})
        self.assertRaises(
            lib.NodeConnectionException,
            lambda: comm.call_host(host, request, data)
        )

        mock_opener.addheaders.append.assert_not_called()
        mock_opener.open.assert_called_once_with(
            self.fixture_url(host, request),
            data
        )
        logger_calls = [
            self.fixture_logger_call_send(
                self.fixture_url(host, request),
                data
            ),
            mock.call(
                "Unable to connect to {0} ({1})".format(host, expected_reason)
            )
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)


class NodeCommunicatorExceptionTransformTest(TestCase, LibraryAssertionMixin):
    def test_transform_error_401(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        self.assert_equal_report_item_list(
            [
                lib.node_communicator_exception_to_report_item(
                    lib.NodeAuthenticationException(node, command, reason)
                )
            ],
            [
                (
                    severity.ERROR,
                    error_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                    {
                        "node": node,
                        "command": command,
                        "reason": "HTTP error: {0}".format(reason),
                    }
                )
            ]
        )

    def test_transform_error_403(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        self.assert_equal_report_item_list(
            [
                lib.node_communicator_exception_to_report_item(
                    lib.NodePermissionDeniedException(node, command, reason)
                )
            ],
            [
                (
                    severity.ERROR,
                    error_codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED,
                    {
                        "node": node,
                        "command": command,
                        "reason": "HTTP error: {0}".format(reason),
                    }
                )
            ]
        )

    def test_transform_error_404(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        self.assert_equal_report_item_list(
            [
                lib.node_communicator_exception_to_report_item(
                    lib.NodeUnsupportedCommandException(node, command, reason)
                )
            ],
            [
                (
                    severity.ERROR,
                    error_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
                    {
                        "node": node,
                        "command": command,
                        "reason": "HTTP error: {0}".format(reason),
                    }
                )
            ]
        )

    def test_transform_error_connecting(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        self.assert_equal_report_item_list(
            [
                lib.node_communicator_exception_to_report_item(
                    lib.NodeConnectionException(node, command, reason)
                )
            ],
            [
                (
                    severity.ERROR,
                    error_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    {
                        "node": node,
                        "command": command,
                        "reason": reason,
                    }
                )
            ]
        )

    def test_transform_error_other(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        self.assert_equal_report_item_list(
            [
                lib.node_communicator_exception_to_report_item(
                    lib.NodeCommunicationException(node, command, reason)
                )
            ],
            [
                (
                    severity.ERROR,
                    error_codes.NODE_COMMUNICATION_ERROR,
                    {
                        "node": node,
                        "command": command,
                        "reason": "HTTP error: {0}".format(reason),
                    }
                )
            ]
        )

    def test_unsupported_exception(self):
        exc = Exception("test")
        raised = False
        try:
            lib.node_communicator_exception_to_report_item(exc)
        except Exception as e:
            raised = True
            self.assertEqual(e, exc)
        self.assertTrue(raised)
