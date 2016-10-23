from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
import os.path
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

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_equal,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock

from pcs import settings
from pcs.common import report_codes
from pcs.lib import reports
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as severity
)

import pcs.lib.external as lib


_chkconfig = settings.chkconfig_binary
_service = settings.service_binary
_systemctl = settings.systemctl_binary


@mock.patch("subprocess.Popen", autospec=True)
class CommandRunnerTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

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
        expected_stdout = "expected stdout"
        expected_stderr = "expected stderr"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (
            expected_stdout, expected_stderr
        )
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger, self.mock_reporter)
        real_stdout, real_stderr, real_retval = runner.run(command)

        self.assertEqual(real_stdout, expected_stdout)
        self.assertEqual(real_stderr, expected_stderr)
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
--Debug Stdout Start--
{2}
--Debug Stdout End--
--Debug Stderr Start--
{3}
--Debug Stderr End--""".format(
                command_str, expected_retval, expected_stdout, expected_stderr
            ))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_STARTED,
                    {
                        "command": command_str,
                        "stdin": None,
                    }
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    }
                )
            ]
        )

    def test_env(self, mock_popen):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (
            expected_stdout, expected_stderr
        )
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(
            self.mock_logger,
            self.mock_reporter,
            {"a": "a", "b": "b"}
        )
        real_stdout, real_stderr, real_retval = runner.run(
            command,
            env_extend={"b": "B", "c": "C"}
        )

        self.assertEqual(real_stdout, expected_stdout)
        self.assertEqual(real_stderr, expected_stderr)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {"a": "a", "b": "B", "c": "C"}, "stdin": None,}
        )
        logger_calls = [
            mock.call("Running: {0}".format(command_str)),
            mock.call("""\
Finished running: {0}
Return value: {1}
--Debug Stdout Start--
{2}
--Debug Stdout End--
--Debug Stderr Start--
{3}
--Debug Stderr End--""".format(
                command_str, expected_retval, expected_stdout, expected_stderr
            ))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_STARTED,
                    {
                        "command": command_str,
                        "stdin": None,
                    }
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    }
                )
            ]
        )

    def test_stdin(self, mock_popen):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        stdin = "stdin string"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (
            expected_stdout, expected_stderr
        )
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger, self.mock_reporter)
        real_stdout, real_stderr, real_retval = runner.run(
            command, stdin_string=stdin
        )

        self.assertEqual(real_stdout, expected_stdout)
        self.assertEqual(real_stderr, expected_stderr)
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
--Debug Stdout Start--
{2}
--Debug Stdout End--
--Debug Stderr Start--
{3}
--Debug Stderr End--""".format(
                command_str, expected_retval, expected_stdout, expected_stderr
            ))
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_STARTED,
                    {
                        "command": command_str,
                        "stdin": stdin,
                    }
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    }
                )
            ]
        )

    def test_popen_error(self, mock_popen):
        expected_error = "expected error"
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        exception = OSError()
        exception.strerror = expected_error
        mock_popen.side_effect = exception

        runner = lib.CommandRunner(self.mock_logger, self.mock_reporter)
        assert_raise_library_error(
            lambda: runner.run(command),
            (
                severity.ERROR,
                report_codes.RUN_EXTERNAL_PROCESS_ERROR,
                {
                    "command": command_str,
                    "reason": expected_error,
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_STARTED,
                    {
                        "command": command_str,
                        "stdin": None,
                    }
                )
            ]
        )

    def test_communicate_error(self, mock_popen):
        expected_error = "expected error"
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        exception = OSError()
        exception.strerror = expected_error
        mock_process.communicate.side_effect = exception
        mock_popen.return_value = mock_process

        runner = lib.CommandRunner(self.mock_logger, self.mock_reporter)
        assert_raise_library_error(
            lambda: runner.run(command),
            (
                severity.ERROR,
                report_codes.RUN_EXTERNAL_PROCESS_ERROR,
                {
                    "command": command_str,
                    "reason": expected_error,
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_STARTED,
                    {
                        "command": command_str,
                        "stdin": None,
                    }
                )
            ]
        )


@mock.patch(
    "pcs.lib.external.NodeCommunicator._NodeCommunicator__get_opener",
    autospec=True
)
class NodeCommunicatorTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

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

    def fixture_report_item_list_send(self, url, data):
        return [
            (
                severity.DEBUG,
                report_codes.NODE_COMMUNICATION_STARTED,
                {
                    "target": url,
                    "data": data,
                }
            )
        ]

    def fixture_report_item_list(self, url, data, response_code, response_data):
        return (
            self.fixture_report_item_list_send(url, data)
            +
            [
                (
                    severity.DEBUG,
                    report_codes.NODE_COMMUNICATION_FINISHED,
                    {
                        "target": url,
                        "response_code": response_code,
                        "response_data": response_data,
                    }
                )
            ]
        )

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

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url(host, request),
                data,
                expected_response_code,
                expected_response_data
            )
        )

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

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {host: token,}
        )
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url("[{0}]".format(host), request),
                data,
                expected_response_code,
                expected_response_data
            )
        )

    def test_auth_token(self, mock_get_opener):
        host = "test_host"
        token = "test_token"
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
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

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {},
            user=user
        )
        dummy_response = comm.call_host(host, "test_request", None)

        mock_opener.addheaders.append.assert_called_once_with(
            ("Cookie", "CIB_user={0}".format(user))
        )

    def test_one_group(self, mock_get_opener):
        host = "test_host"
        groups = ["group1"]
        mock_opener = mock.MagicMock()
        mock_get_opener.return_value = mock_opener

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {},
            groups=groups
        )
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
            self.mock_reporter,
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

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url(host, request),
                data,
                expected_response_code,
                expected_response_data
            )
        )

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

    def test_command_unsuccessful(self, mock_get_opener):
        self.base_test_http_error(
            mock_get_opener,
            400,
            lib.NodeCommandUnsuccessfulException
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

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
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
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list_send(
                self.fixture_url(host, request),
                data
            )
            +
            [(
                severity.DEBUG,
                report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
                {
                    "node": host,
                    "reason": expected_reason,
                }
            )]
        )


class NodeCommunicatorExceptionTransformTest(TestCase):
    def test_transform_error_400(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodeCommandUnsuccessfulException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
        )

    def test_transform_error_401(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodeAuthenticationException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
        )

    def test_transform_error_403(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodePermissionDeniedException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
        )

    def test_transform_error_404(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodeUnsupportedCommandException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
        )

    def test_transform_error_connecting(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodeConnectionException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
        )

    def test_transform_error_other(self):
        node = "test_node"
        command = "test_command"
        reason = "test_reason"

        assert_report_item_equal(
            lib.node_communicator_exception_to_report_item(
                lib.NodeCommunicationException(node, command, reason)
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR,
                {
                    "node": node,
                    "command": command,
                    "reason": reason,
                }
            )
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


class ParallelCommunicationHelperTest(TestCase):
    def setUp(self):
        self.mock_reporter = MockLibraryReportProcessor()

    def fixture_raiser(self):
        def raiser(x, *args, **kwargs):
            if x == 1:
                raise lib.NodeConnectionException("node", "command", "reason")
            elif x == 2:
                raise LibraryError(
                    reports.corosync_config_distribution_node_error("node")
                )
        return raiser

    def test_success(self):
        func = mock.MagicMock()
        lib.parallel_nodes_communication_helper(
            func,
            [([x], {"a": x*2,}) for x in range(3)],
            self.mock_reporter,
            skip_offline_nodes=False
        )
        expected_calls = [
            mock.call(0, a=0),
            mock.call(1, a=2),
            mock.call(2, a=4),
        ]
        self.assertEqual(len(expected_calls), len(func.mock_calls))
        func.assert_has_calls(expected_calls, any_order=True)
        self.assertEqual(self.mock_reporter.report_item_list, [])

    def test_errors(self):
        func = self.fixture_raiser()
        assert_raise_library_error(
            lambda: lib.parallel_nodes_communication_helper(
                func,
                [([x], {"a": x*2,}) for x in range(4)],
                self.mock_reporter,
                skip_offline_nodes=False
            ),
            (
                severity.ERROR,
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                {
                    "node": "node",
                    "reason": "reason",
                    "command": "command",
                },
                report_codes.SKIP_OFFLINE_NODES
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                {
                    "node": "node",
                }
            )
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.ERROR,
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    {
                        "node": "node",
                        "reason": "reason",
                        "command": "command",
                    },
                    report_codes.SKIP_OFFLINE_NODES
                ),
                (
                    severity.ERROR,
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    {
                        "node": "node",
                    }
                )
            ]
        )

    def test_errors_skip_offline(self):
        func = self.fixture_raiser()
        assert_raise_library_error(
            lambda: lib.parallel_nodes_communication_helper(
                func,
                [([x], {"a": x*2,}) for x in range(4)],
                self.mock_reporter,
                skip_offline_nodes=True
            ),
            (
                severity.ERROR,
                report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                {
                    "node": "node",
                }
            )
        )
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            [
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    {
                        "node": "node",
                        "reason": "reason",
                        "command": "command",
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
                    {
                        "node": "node",
                    }
                )
            ]
        )

class IsCmanClusterTest(TestCase):
    def template_test(self, is_cman, corosync_output, corosync_retval=0):
        mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        mock_runner.run.return_value = (corosync_output, "", corosync_retval)
        self.assertEqual(is_cman, lib.is_cman_cluster(mock_runner))
        mock_runner.run.assert_called_once_with([
            os.path.join(settings.corosync_binaries, "corosync"),
            "-v"
        ])

    def test_is_not_cman(self):
        self.template_test(
            False,
            """\
Corosync Cluster Engine, version '2.3.4'
Copyright (c) 2006-2009 Red Hat, Inc.
"""
        )

    def test_is_cman(self):
        self.template_test(
            True,
            """\
Corosync Cluster Engine, version '1.4.7'
Copyright (c) 2006-2009 Red Hat, Inc.
"""
        )

    def test_bad_version_format(self):
        self.template_test(
            False,
            """\
Corosync Cluster Engine, nonsense '2.3.4'
Copyright (c) 2006-2009 Red Hat, Inc.
"""
        )

    def test_no_version(self):
        self.template_test(
            False,
            """\
Corosync Cluster Engine
Copyright (c) 2006-2009 Red Hat, Inc.
"""
        )

    def test_corosync_error(self):
        self.template_test(
            False,
            """\
Corosync Cluster Engine, version '1.4.7'
Copyright (c) 2006-2009 Red Hat, Inc.
""",
            1
        )


@mock.patch("pcs.lib.external.is_systemctl")
@mock.patch("pcs.lib.external.is_service_installed")
class DisableServiceTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Removed symlink", 0)
        lib.disable_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "disable", self.service + ".service"]
        )

    def test_systemctl_failed(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Failed", 1)
        self.assertRaises(
            lib.DisableServiceError,
            lambda: lib.disable_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "disable", self.service + ".service"]
        )

    def test_not_systemctl(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.disable_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "off"]
        )

    def test_not_systemctl_failed(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "error", 1)
        self.assertRaises(
            lib.DisableServiceError,
            lambda: lib.disable_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "off"]
        )

    def test_systemctl_not_installed(
            self, mock_is_installed, mock_systemctl
    ):
        mock_is_installed.return_value = False
        mock_systemctl.return_value = True
        lib.disable_service(self.mock_runner, self.service)
        self.assertEqual(self.mock_runner.run.call_count, 0)

    def test_not_systemctl_not_installed(
            self, mock_is_installed, mock_systemctl
    ):
        mock_is_installed.return_value = False
        mock_systemctl.return_value = False
        lib.disable_service(self.mock_runner, self.service)
        self.assertEqual(self.mock_runner.run.call_count, 0)

    def test_instance_systemctl(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Removed symlink", 0)
        lib.disable_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with([
            _systemctl,
            "disable",
            "{0}@{1}.service".format(self.service, "test")
        ])

    def test_instance_not_systemctl(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.disable_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "off"]
        )

@mock.patch("pcs.lib.external.is_systemctl")
class EnableServiceTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Created symlink", 0)
        lib.enable_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "enable", self.service + ".service"]
        )

    def test_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Failed", 1)
        self.assertRaises(
            lib.EnableServiceError,
            lambda: lib.enable_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "enable", self.service + ".service"]
        )

    def test_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.enable_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "on"]
        )

    def test_not_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "error", 1)
        self.assertRaises(
            lib.EnableServiceError,
            lambda: lib.enable_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "on"]
        )

    def test_instance_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Created symlink", 0)
        lib.enable_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with([
            _systemctl,
            "enable",
            "{0}@{1}.service".format(self.service, "test")
        ])

    def test_instance_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.enable_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service, "on"]
        )


@mock.patch("pcs.lib.external.is_systemctl")
class StartServiceTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "", 0)
        lib.start_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "start", self.service + ".service"]
        )

    def test_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Failed", 1)
        self.assertRaises(
            lib.StartServiceError,
            lambda: lib.start_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "start", self.service + ".service"]
        )

    def test_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("Starting...", "", 0)
        lib.start_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "start"]
        )

    def test_not_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "unrecognized", 1)
        self.assertRaises(
            lib.StartServiceError,
            lambda: lib.start_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "start"]
        )

    def test_instance_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "", 0)
        lib.start_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with([
            _systemctl, "start", "{0}@{1}.service".format(self.service, "test")
        ])

    def test_instance_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("Starting...", "", 0)
        lib.start_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "start"]
        )


@mock.patch("pcs.lib.external.is_systemctl")
class StopServiceTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "", 0)
        lib.stop_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "stop", self.service + ".service"]
        )

    def test_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Failed", 1)
        self.assertRaises(
            lib.StopServiceError,
            lambda: lib.stop_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "stop", self.service + ".service"]
        )

    def test_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("Stopping...", "", 0)
        lib.stop_service(self.mock_runner, self.service)
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "stop"]
        )

    def test_not_systemctl_failed(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "unrecognized", 1)
        self.assertRaises(
            lib.StopServiceError,
            lambda: lib.stop_service(self.mock_runner, self.service)
        )
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "stop"]
        )

    def test_instance_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "", 0)
        lib.stop_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with([
            _systemctl, "stop", "{0}@{1}.service".format(self.service, "test")
        ])

    def test_instance_not_systemctl(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("Stopping...", "", 0)
        lib.stop_service(self.mock_runner, self.service, instance="test")
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "stop"]
        )


class KillServicesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.services = ["service1", "service2"]

    def test_success(self):
        self.mock_runner.run.return_value = ("", "", 0)
        lib.kill_services(self.mock_runner, self.services)
        self.mock_runner.run.assert_called_once_with(
            ["killall", "--quiet", "--signal", "9", "--"] + self.services
        )

    def test_failed(self):
        self.mock_runner.run.return_value = ("", "error", 1)
        self.assertRaises(
            lib.KillServicesError,
            lambda: lib.kill_services(self.mock_runner, self.services)
        )
        self.mock_runner.run.assert_called_once_with(
            ["killall", "--quiet", "--signal", "9", "--"] + self.services
        )

    def test_service_not_running(self):
        self.mock_runner.run.return_value = ("", "", 1)
        lib.kill_services(self.mock_runner, self.services)
        self.mock_runner.run.assert_called_once_with(
            ["killall", "--quiet", "--signal", "9", "--"] + self.services
        )


@mock.patch("os.listdir")
@mock.patch("os.path.isdir")
@mock.patch("os.path.exists")
class IsDirNonemptyTest(TestCase):
    def test_path_does_not_exist(self, mock_exists, mock_isdir, mock_listdir):
        mock_exists.return_value = False
        self.assertFalse(lib.is_dir_nonempty("path"))
        mock_isdir.assert_not_called()
        mock_listdir.assert_not_called()

    def test_path_is_not_dir(self, mock_exists, mock_isdir, mock_listdir):
        mock_exists.return_value = True
        mock_isdir.return_value = False
        self.assertTrue(lib.is_dir_nonempty("path"))
        mock_listdir.assert_not_called()

    def test_dir_is_empty(self, mock_exists, mock_isdir, mock_listdir):
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_listdir.return_value = []
        self.assertFalse(lib.is_dir_nonempty("path"))

    def test_dir_is_not_empty(self, mock_exists, mock_isdir, mock_listdir):
        mock_exists.return_value = True
        mock_isdir.return_value = True
        mock_listdir.return_value = ["a_file"]
        self.assertTrue(lib.is_dir_nonempty("path"))


@mock.patch("pcs.lib.external.is_systemctl")
class IsServiceEnabledTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl_enabled(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("enabled\n", "", 0)
        self.assertTrue(lib.is_service_enabled(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "is-enabled", self.service + ".service"]
        )

    def test_systemctl_disabled(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("disabled\n", "", 2)
        self.assertFalse(lib.is_service_enabled(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "is-enabled", self.service + ".service"]
        )

    def test_not_systemctl_enabled(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        self.assertTrue(lib.is_service_enabled(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service]
        )

    def test_not_systemctl_disabled(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 3)
        self.assertFalse(lib.is_service_enabled(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_chkconfig, self.service]
        )


@mock.patch("pcs.lib.external.is_systemctl")
class IsServiceRunningTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.service = "service_name"

    def test_systemctl_running(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("active", "", 0)
        self.assertTrue(lib.is_service_running(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "is-active", self.service + ".service"]
        )

    def test_systemctl_not_running(self, mock_systemctl):
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("inactive", "", 2)
        self.assertFalse(lib.is_service_running(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "is-active", self.service + ".service"]
        )

    def test_not_systemctl_running(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("is running", "", 0)
        self.assertTrue(lib.is_service_running(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "status"]
        )

    def test_not_systemctl_not_running(self, mock_systemctl):
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("is stopped", "", 3)
        self.assertFalse(lib.is_service_running(self.mock_runner, self.service))
        self.mock_runner.run.assert_called_once_with(
            [_service, self.service, "status"]
        )


@mock.patch("pcs.lib.external.is_systemctl")
@mock.patch("pcs.lib.external.get_systemd_services")
@mock.patch("pcs.lib.external.get_non_systemd_services")
class IsServiceInstalledTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)

    def test_installed_systemd(
        self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        mock_systemd.return_value = ["service1", "service2"]
        mock_non_systemd.return_value = []
        self.assertTrue(lib.is_service_installed(self.mock_runner, "service2"))
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_non_systemd.call_count, 0)

    def test_not_installed_systemd(
            self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        mock_systemd.return_value = ["service1", "service2"]
        mock_non_systemd.return_value = []
        self.assertFalse(lib.is_service_installed(self.mock_runner, "service3"))
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_non_systemd.call_count, 0)

    def test_installed_not_systemd(
            self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = False
        mock_systemd.return_value = []
        mock_non_systemd.return_value = ["service1", "service2"]
        self.assertTrue(lib.is_service_installed(self.mock_runner, "service2"))
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_non_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_systemd.call_count, 0)

    def test_not_installed_not_systemd(
            self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = False

        mock_systemd.return_value = []
        mock_non_systemd.return_value = ["service1", "service2"]
        self.assertFalse(lib.is_service_installed(self.mock_runner, "service3"))
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_non_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_systemd.call_count, 0)


@mock.patch("pcs.lib.external.is_systemctl")
class GetSystemdServicesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)

    def test_success(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.mock_runner.run.return_value = ("""\
pcsd.service                                disabled
sbd.service                                 enabled
pacemaker.service                           enabled

3 unit files listed.
""", "", 0)
        self.assertEqual(
            lib.get_systemd_services(self.mock_runner),
            ["pcsd", "sbd", "pacemaker"]
        )
        self.assertEqual(mock_is_systemctl.call_count, 1)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "list-unit-files", "--full"]
        )

    def test_failed(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.mock_runner.run.return_value = ("stdout", "failed", 1)
        self.assertEqual(lib.get_systemd_services(self.mock_runner), [])
        self.assertEqual(mock_is_systemctl.call_count, 1)
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "list-unit-files", "--full"]
        )

    def test_not_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = False
        self.assertEqual(lib.get_systemd_services(self.mock_runner), [])
        mock_is_systemctl.assert_called_once_with()
        self.mock_runner.assert_not_called()


@mock.patch("pcs.lib.external.is_systemctl")
class GetNonSystemdServicesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)

    def test_success(self, mock_is_systemctl):
        mock_is_systemctl.return_value = False
        self.mock_runner.run.return_value = ("""\
pcsd           	0:off	1:off	2:on	3:on	4:on	5:on	6:off
sbd            	0:off	1:on	2:on	3:on	4:on	5:on	6:off
pacemaker      	0:off	1:off	2:off	3:off	4:off	5:off	6:off
""", "", 0)
        self.assertEqual(
            lib.get_non_systemd_services(self.mock_runner),
            ["pcsd", "sbd", "pacemaker"]
        )
        self.assertEqual(mock_is_systemctl.call_count, 1)
        self.mock_runner.run.assert_called_once_with([_chkconfig])

    def test_failed(self, mock_is_systemctl):
        mock_is_systemctl.return_value = False
        self.mock_runner.run.return_value = ("stdout", "failed", 1)
        self.assertEqual(lib.get_non_systemd_services(self.mock_runner), [])
        self.assertEqual(mock_is_systemctl.call_count, 1)
        self.mock_runner.run.assert_called_once_with([_chkconfig])

    def test_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", 0)
        self.assertEqual(lib.get_non_systemd_services(self.mock_runner), [])
        self.assertEqual(mock_is_systemctl.call_count, 1)
        self.assertEqual(self.mock_runner.call_count, 0)

@mock.patch("pcs.lib.external.is_systemctl")
class EnsureIsSystemctlTest(TestCase):
    def test_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        lib.ensure_is_systemd()

    def test_not_systemd(self, mock_is_systemctl):
        mock_is_systemctl.return_value = False
        assert_raise_library_error(
            lib.ensure_is_systemd,
            (
                severity.ERROR,
                report_codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS,
                {}
            )
        )

