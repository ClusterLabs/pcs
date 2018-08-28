import logging
from subprocess import DEVNULL
from unittest import mock, TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_equal,
    assert_report_item_list_equal,
)
from pcs.test.tools.custom_mock import (
    MockCurl,
    MockLibraryReportProcessor,
)
from pcs.test.tools.misc import outdent

from pcs import settings
from pcs.common import (
    pcs_pycurl as pycurl,
    report_codes,
)
from pcs.lib.errors import ReportItemSeverity as severity

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
            {"env": {}, "stdin": DEVNULL,}
        )
        logger_calls = [
            mock.call("Running: {0}\nEnvironment:".format(command_str)),
            mock.call(
                outdent(
                    """\
                    Finished running: {0}
                    Return value: {1}
                    --Debug Stdout Start--
                    {2}
                    --Debug Stdout End--
                    --Debug Stderr Start--
                    {3}
                    --Debug Stderr End--"""
                ).format(
                    command_str,
                    expected_retval,
                    expected_stdout,
                    expected_stderr,
                )
            )
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
                        "environment": dict(),
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

        global_env = {"a": "a", "b": "b"}
        runner = lib.CommandRunner(
            self.mock_logger,
            self.mock_reporter,
            global_env.copy()
        )
        #{C} is for check that no python template conflict appear
        real_stdout, real_stderr, real_retval = runner.run(
            command,
            env_extend={"b": "B", "c": "{C}"}
        )
        #check that env_exted did not affect initial env of runner
        self.assertEqual(runner._env_vars, global_env)

        self.assertEqual(real_stdout, expected_stdout)
        self.assertEqual(real_stderr, expected_stderr)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {"env": {"a": "a", "b": "B", "c": "{C}"}, "stdin": DEVNULL,}
        )
        logger_calls = [
            mock.call(
                outdent(
                    """\
                    Running: {0}
                    Environment:
                      a=a
                      b=B
                      c={1}"""
                ).format(command_str, "{C}")
            ),
            mock.call(
                outdent(
                    """\
                    Finished running: {0}
                    Return value: {1}
                    --Debug Stdout Start--
                    {2}
                    --Debug Stdout End--
                    --Debug Stderr Start--
                    {3}
                    --Debug Stderr End--"""
                ).format(
                    command_str,
                    expected_retval,
                    expected_stdout,
                    expected_stderr,
                )
            )
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
                        "environment": {"a": "a", "b": "B", "c": "{C}"},
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
            mock.call(
                outdent(
                    """\
                    Running: {0}
                    Environment:
                    --Debug Input Start--
                    {1}
                    --Debug Input End--"""
                ).format(command_str, stdin)
            ),
            mock.call(
                outdent(
                    """\
                    Finished running: {0}
                    Return value: {1}
                    --Debug Stdout Start--
                    {2}
                    --Debug Stdout End--
                    --Debug Stderr Start--
                    {3}
                    --Debug Stderr End--"""
                ).format(
                    command_str,
                    expected_retval,
                    expected_stdout,
                    expected_stderr,
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
                        "environment": dict(),
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
            {"env": {}, "stdin": DEVNULL,}
        )
        logger_calls = [
            mock.call("Running: {0}\nEnvironment:".format(command_str)),
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
                        "environment": dict(),
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
            {"env": {}, "stdin": DEVNULL,}
        )
        logger_calls = [
            mock.call("Running: {0}\nEnvironment:".format(command_str)),
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
                        "environment": dict(),
                    }
                )
            ]
        )

@mock.patch(
    "pcs.lib.external.pycurl.Curl",
    autospec=True
)
class NodeCommunicatorTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def fixture_logger_call_send(self, url, data):
        send_msg = "Sending HTTP Request to: {url}"
        if data:
            send_msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
        return mock.call(send_msg.format(url=url, data=data))

    def fixture_logger_call_debug_data(self, url, data):
        send_msg = outdent("""\
            Communication debug info for calling: {url}
            --Debug Communication Info Start--
            {data}
            --Debug Communication Info End--"""
        )
        return mock.call(send_msg.format(url=url, data=data))

    def fixture_logger_calls(
        self, url, data, response_code, response_data, debug_data
    ):
        result_msg = (
            "Finished calling: {url}\nResponse Code: {code}"
            + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
        )
        return [
            self.fixture_logger_call_send(url, data),
            mock.call(result_msg.format(
                url=url, code=response_code, response=response_data
            )),
            self.fixture_logger_call_debug_data(url, debug_data)
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

    def fixture_report_item_list_debug(self, url, data):
        return [
            (
                severity.DEBUG,
                report_codes.NODE_COMMUNICATION_DEBUG_INFO,
                {
                    "target": url,
                    "data": data,
                }
            )
        ]

    def fixture_report_item_list(
        self, url, data, response_code, response_data, debug_data
    ):
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
            +
            self.fixture_report_item_list_debug(url, debug_data)
        )

    def fixture_url(self, host, request):
        return "https://{host}:2224/{request}".format(
            host=host, request=request
        )

    def test_success(self, mock_pycurl_init):
        host = "test_host"
        request = "test_request"
        data = '{"key1": "value1", "key2": ["value2a", "value2b"]}'
        expected_response_data = "expected response data"
        expected_response_code = 200
        expected_debug_data = "* text\n>> data out\n"
        mock_pycurl_obj = MockCurl(
            {
                pycurl.RESPONSE_CODE: expected_response_code,
            },
            expected_response_data.encode("utf-8"),
            [
                (pycurl.DEBUG_TEXT, b"text"),
                (pycurl.DEBUG_DATA_OUT, b"data out")
            ]
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
        real_response = comm.call_host(host, request, data)
        self.assertEqual(expected_response_data, real_response)

        expected_opts = {
            pycurl.URL: self.fixture_url(host, request).encode("utf-8"),
            pycurl.SSL_VERIFYHOST: 0,
            pycurl.SSL_VERIFYPEER: 0,
            pycurl.COPYPOSTFIELDS: data.encode("utf-8"),
            pycurl.TIMEOUT_MS: settings.default_request_timeout * 1000,
        }

        self.assertLessEqual(
            set(expected_opts.items()), set(mock_pycurl_obj.opts.items())
        )

        logger_calls = self.fixture_logger_calls(
            self.fixture_url(host, request),
            data,
            expected_response_code,
            expected_response_data,
            expected_debug_data
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url(host, request),
                data,
                expected_response_code,
                expected_response_data,
                expected_debug_data
            )
        )

    @mock.patch("pcs.lib.external.os")
    def test_success_proxy_set(self, mock_os, mock_pycurl_init):
        host = "test_host"
        request = "test_request"
        data = '{"key1": "value1", "key2": ["value2a", "value2b"]}'
        expected_response_data = "expected response data"
        expected_response_code = 200
        mock_os.environ = {
            "all_proxy": "proxy1",
            "https_proxy": "proxy2",
            "HTTPS_PROXY": "proxy3",
        }
        mock_pycurl_obj = MockCurl(
            {
                pycurl.RESPONSE_CODE: expected_response_code,
            },
            expected_response_data.encode("utf-8"),
            []
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
        real_response = comm.call_host(host, request, data)
        self.assertEqual(expected_response_data, real_response)

        expected_opts = {
            pycurl.URL: self.fixture_url(host, request).encode("utf-8"),
            pycurl.SSL_VERIFYHOST: 0,
            pycurl.SSL_VERIFYPEER: 0,
            pycurl.COPYPOSTFIELDS: data.encode("utf-8"),
            pycurl.TIMEOUT_MS: settings.default_request_timeout * 1000,
        }

        self.assertLessEqual(
            set(expected_opts.items()), set(mock_pycurl_obj.opts.items())
        )

        logger_calls = self.fixture_logger_calls(
            self.fixture_url(host, request),
            data,
            expected_response_code,
            expected_response_data,
            ""
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url(host, request),
                data,
                expected_response_code,
                expected_response_data,
                ""
            )
        )

    def test_ipv6(self, mock_pycurl_init):
        host = "cafe::1"
        request = "test_request"
        data = None
        token = "test_token"
        expected_response_code = 200
        expected_response_data = "expected response data"
        expected_debug_data = ""
        mock_pycurl_obj = MockCurl(
            {
                pycurl.RESPONSE_CODE: expected_response_code,
            },
            expected_response_data.encode("utf-8"),
            []
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {host: token,}
        )
        real_response = comm.call_host(host, request, data)
        self.assertEqual(expected_response_data, real_response)
        expected_opts = {
            pycurl.URL: self.fixture_url(
                "[{0}]".format(host), request
            ).encode("utf-8"),
            pycurl.COOKIE: "token={0}".format(token).encode("utf-8"),
            pycurl.SSL_VERIFYHOST: 0,
            pycurl.SSL_VERIFYPEER: 0,
        }
        self.assertLessEqual(
            set(expected_opts.items()), set(mock_pycurl_obj.opts.items())
        )

        self.assertTrue(pycurl.COPYPOSTFIELDS not in mock_pycurl_obj.opts)

        logger_calls = self.fixture_logger_calls(
            self.fixture_url("[{0}]".format(host), request),
            data,
            expected_response_code,
            expected_response_data,
            expected_debug_data
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url("[{0}]".format(host), request),
                data,
                expected_response_code,
                expected_response_data,
                expected_debug_data
            )
        )

    def test_communicator_timeout(self, mock_pycurl_init):
        host = "test_host"
        timeout = 10
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger, self.mock_reporter, {}, request_timeout=timeout
        )
        dummy_response = comm.call_host(host, "test_request", None)

        self.assertLessEqual(
            set([(pycurl.TIMEOUT_MS, timeout * 1000)]),
            set(mock_pycurl_obj.opts.items())
        )

    def test_call_host_timeout(self, mock_pycurl_init):
        host = "test_host"
        timeout = 10
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger, self.mock_reporter, {}, request_timeout=15
        )
        dummy_response = comm.call_host(host, "test_request", None, timeout)

        self.assertLessEqual(
            set([(pycurl.TIMEOUT_MS, timeout * 1000)]),
            set(mock_pycurl_obj.opts.items())
        )

    def test_auth_token(self, mock_pycurl_init):
        host = "test_host"
        token = "test_token"
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

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

        self.assertLessEqual(
            set([(pycurl.COOKIE, "token={0}".format(token).encode("utf-8"))]),
            set(mock_pycurl_obj.opts.items())
        )

    def test_user(self, mock_pycurl_init):
        host = "test_host"
        user = "test_user"
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {},
            user=user
        )
        dummy_response = comm.call_host(host, "test_request", None)

        self.assertLessEqual(
            set([(pycurl.COOKIE, "CIB_user={0}".format(user).encode("utf-8"))]),
            set(mock_pycurl_obj.opts.items())
        )

    def test_one_group(self, mock_pycurl_init):
        host = "test_host"
        groups = ["group1"]
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {},
            groups=groups
        )
        dummy_response = comm.call_host(host, "test_request", None)

        self.assertLessEqual(
            set([(
                pycurl.COOKIE,
                "CIB_user_groups={0}".format("Z3JvdXAx").encode("utf-8")
            )]),
            set(mock_pycurl_obj.opts.items())
        )

    def test_all_options(self, mock_pycurl_init):
        host = "test_host"
        token = "test_token"
        user = "test_user"
        groups = ["group1", "group2"]
        mock_pycurl_obj = MockCurl({pycurl.RESPONSE_CODE: 200}, b"", [])
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(
            self.mock_logger,
            self.mock_reporter,
            {host: token},
            user,
            groups
        )
        dummy_response = comm.call_host(host, "test_request", None)

        cookie_str = (
            "token={token};CIB_user={user};CIB_user_groups={groups}".format(
                token=token,
                user=user,
                groups="Z3JvdXAxIGdyb3VwMg=="
            ).encode("utf-8")
        )
        self.assertLessEqual(
            set([(pycurl.COOKIE, cookie_str)]),
            set(mock_pycurl_obj.opts.items())
        )

    def base_test_http_error(self, mock_pycurl_init, code, exception):
        host = "test_host"
        request = "test_request"
        data = None
        expected_response_code = code
        expected_response_data = "expected response data"
        mock_pycurl_obj = MockCurl(
            {
                pycurl.RESPONSE_CODE: expected_response_code,
            },
            expected_response_data.encode("utf-8"),
            []
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
        self.assertRaises(
            exception,
            lambda: comm.call_host(host, request, data)
        )

        self.assertTrue(pycurl.COOKIE not in mock_pycurl_obj.opts)
        self.assertTrue(pycurl.COPYPOSTFIELDS not in mock_pycurl_obj.opts)
        expected_opts = {
            pycurl.URL: self.fixture_url(host, request).encode("utf-8"),
            pycurl.SSL_VERIFYHOST: 0,
            pycurl.SSL_VERIFYPEER: 0,
        }
        self.assertLessEqual(
            set(expected_opts.items()), set(mock_pycurl_obj.opts.items())
        )
        logger_calls = self.fixture_logger_calls(
            self.fixture_url(host, request),
            data,
            expected_response_code,
            expected_response_data,
            ""
        )
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list(
                self.fixture_url(host, request),
                data,
                expected_response_code,
                expected_response_data,
                ""
            ),
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

    def test_connection_error(self, mock_pycurl_init):
        host = "test_host"
        request = "test_request"
        data = None
        expected_reason = "expected reason"
        expected_url = self.fixture_url(host, request)
        mock_pycurl_obj = MockCurl(
            {}, b"", [], pycurl.error(pycurl.E_SEND_ERROR, expected_reason)
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
        self.assertRaises(
            lib.NodeConnectionException,
            lambda: comm.call_host(host, request, data)
        )

        self.assertTrue(pycurl.COOKIE not in mock_pycurl_obj.opts)
        self.assertTrue(pycurl.COPYPOSTFIELDS not in mock_pycurl_obj.opts)
        expected_opts = {
            pycurl.URL: expected_url.encode("utf-8"),
            pycurl.SSL_VERIFYHOST: 0,
            pycurl.SSL_VERIFYPEER: 0,
        }
        self.assertLessEqual(
            set(expected_opts.items()), set(mock_pycurl_obj.opts.items())
        )
        logger_calls = [
            self.fixture_logger_call_send(expected_url, data),
            mock.call(
                "Unable to connect to {0} ({1})".format(host, expected_reason)
            ),
            self.fixture_logger_call_debug_data(expected_url, "")
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
            +
            self.fixture_report_item_list_debug(expected_url, "")
        )

    @mock.patch("pcs.lib.external.os")
    def test_connection_error_proxy_set(self, mock_os, mock_pycurl_init):
        host = "test_host"
        request = "test_request"
        data = None
        expected_reason = "expected reason"
        expected_url = self.fixture_url(host, request)
        mock_os.environ = {
            "all_proxy": "proxy1",
            "https_proxy": "proxy2",
            "HTTPS_PROXY": "proxy3",
        }
        mock_pycurl_obj = MockCurl(
            {}, b"", [], pycurl.error(pycurl.E_SEND_ERROR, expected_reason)
        )
        mock_pycurl_init.return_value = mock_pycurl_obj

        comm = lib.NodeCommunicator(self.mock_logger, self.mock_reporter, {})
        self.assertRaises(
            lib.NodeConnectionException,
            lambda: comm.call_host(host, request, data)
        )

        self.assertTrue(pycurl.COOKIE not in mock_pycurl_obj.opts)
        self.assertTrue(pycurl.COPYPOSTFIELDS not in mock_pycurl_obj.opts)
        logger_calls = [
            self.fixture_logger_call_send(expected_url, data),
            mock.call(
                "Unable to connect to {0} ({1})".format(host, expected_reason)
            ),
            self.fixture_logger_call_debug_data(expected_url, "")
        ]
        self.assertEqual(self.mock_logger.debug.call_count, len(logger_calls))
        self.mock_logger.debug.assert_has_calls(logger_calls)
        self.mock_logger.warning.assert_has_calls([mock.call("Proxy is set")])
        assert_report_item_list_equal(
            self.mock_reporter.report_item_list,
            self.fixture_report_item_list_send(
                self.fixture_url(host, request),
                data
            )
            +
            [
                (
                   severity.DEBUG,
                   report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
                   {
                       "node": host,
                       "reason": expected_reason,
                   }
                ),
                (
                    severity.WARNING,
                    report_codes.NODE_COMMUNICATION_PROXY_IS_SET,
                    {}
                )
            ]
            +
            self.fixture_report_item_list_debug(expected_url, "")
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
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
        )
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
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
        )
        self.mock_runner.run.assert_called_once_with(
            [_systemctl, "disable", self.service + ".service"]
        )

    def test_not_systemctl(self, mock_is_installed, mock_systemctl):
        mock_is_installed.return_value = True
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.disable_service(self.mock_runner, self.service)
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
        )
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
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
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
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
        )

    def test_not_systemctl_not_installed(
            self, mock_is_installed, mock_systemctl
    ):
        mock_is_installed.return_value = False
        mock_systemctl.return_value = False
        lib.disable_service(self.mock_runner, self.service)
        self.assertEqual(self.mock_runner.run.call_count, 0)
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, None
        )

    def test_instance_systemctl(self, mock_is_installed, mock_systemctl):
        instance = "test"
        mock_is_installed.return_value = True
        mock_systemctl.return_value = True
        self.mock_runner.run.return_value = ("", "Removed symlink", 0)
        lib.disable_service(self.mock_runner, self.service, instance=instance)
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, instance
        )
        self.mock_runner.run.assert_called_once_with([
            _systemctl,
            "disable",
            "{0}@{1}.service".format(self.service, "test")
        ])

    def test_instance_not_systemctl(self, mock_is_installed, mock_systemctl):
        instance = "test"
        mock_is_installed.return_value = True
        mock_systemctl.return_value = False
        self.mock_runner.run.return_value = ("", "", 0)
        lib.disable_service(self.mock_runner, self.service, instance=instance)
        mock_is_installed.assert_called_once_with(
            self.mock_runner, self.service, instance
        )
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

    def test_installed_systemd_instance(
        self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        mock_systemd.return_value = ["service1", "service2@"]
        mock_non_systemd.return_value = []
        self.assertTrue(
            lib.is_service_installed(self.mock_runner, "service2", "instance")
        )
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_non_systemd.call_count, 0)

    def test_not_installed_systemd_instance(
        self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = True
        mock_systemd.return_value = ["service1", "service2"]
        mock_non_systemd.return_value = []
        self.assertFalse(
            lib.is_service_installed(self.mock_runner, "service2", "instance")
        )
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_non_systemd.call_count, 0)

    def test_installed_not_systemd_instance(
        self, mock_non_systemd, mock_systemd, mock_is_systemctl
    ):
        mock_is_systemctl.return_value = False
        mock_systemd.return_value = []
        mock_non_systemd.return_value = ["service1", "service2"]
        self.assertTrue(
            lib.is_service_installed(self.mock_runner, "service2", "instance")
        )
        self.assertEqual(mock_is_systemctl.call_count, 1)
        mock_non_systemd.assert_called_once_with(self.mock_runner)
        self.assertEqual(mock_systemd.call_count, 0)


@mock.patch("pcs.lib.external.is_systemctl")
class GetSystemdServicesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)

    def test_success(self, mock_is_systemctl):
        mock_is_systemctl.return_value = True
        self.mock_runner.run.return_value = (outdent(
            """\
            pcsd.service                                disabled
            sbd.service                                 enabled
            pacemaker.service                           enabled

            3 unit files listed.
            """
        ), "", 0)
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
        self.mock_runner.run.return_value = (outdent(
            """\
            pcsd           	0:off	1:off	2:on	3:on	4:on	5:on	6:off
            sbd            	0:off	1:on	2:on	3:on	4:on	5:on	6:off
            pacemaker      	0:off	1:off	2:off	3:off	4:off	5:off	6:off
            """
        ), "", 0)
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
