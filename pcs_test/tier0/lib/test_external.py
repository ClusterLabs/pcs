import logging
from subprocess import DEVNULL
from unittest import (
    TestCase,
    mock,
)

import pcs.lib.external as lib
from pcs import settings
from pcs.common.reports import ReportItemSeverity as severity
from pcs.common.reports import codes as report_codes

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor
from pcs_test.tools.misc import outdent


@mock.patch("subprocess.Popen", autospec=True)
class CommandRunnerTest(TestCase):
    def setUp(self):
        self.mock_logger = mock.MagicMock(logging.Logger)
        self.mock_reporter = MockLibraryReportProcessor()

    def assert_popen_called_with(self, mock_popen, args, kwargs):
        self.assertEqual(mock_popen.call_count, 1)
        real_args, real_kwargs = mock_popen.call_args
        filtered_kwargs = {
            name: value for name, value in real_kwargs.items() if name in kwargs
        }
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
            expected_stdout,
            expected_stderr,
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
            {
                "env": {},
                "stdin": DEVNULL,
            },
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
            ),
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
                        "environment": {},
                    },
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    },
                ),
            ],
        )

    def test_env(self, mock_popen):
        expected_stdout = "expected output"
        expected_stderr = "expected stderr"
        expected_retval = 123
        command = ["a_command"]
        command_str = "a_command"
        mock_process = mock.MagicMock(spec_set=["communicate", "returncode"])
        mock_process.communicate.return_value = (
            expected_stdout,
            expected_stderr,
        )
        mock_process.returncode = expected_retval
        mock_popen.return_value = mock_process

        global_env = {"a": "a", "b": "b"}
        runner = lib.CommandRunner(
            self.mock_logger, self.mock_reporter, global_env.copy()
        )
        # {C} is for check that no python template conflict appear
        real_stdout, real_stderr, real_retval = runner.run(
            command, env_extend={"b": "B", "c": "{C}"}
        )
        # check that env_exted did not affect initial env of runner
        # pylint: disable=protected-access
        self.assertEqual(runner._env_vars, global_env)

        self.assertEqual(real_stdout, expected_stdout)
        self.assertEqual(real_stderr, expected_stderr)
        self.assertEqual(real_retval, expected_retval)
        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {
                "env": {"a": "a", "b": "B", "c": "{C}"},
                "stdin": DEVNULL,
            },
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
            ),
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
                    },
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    },
                ),
            ],
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
            expected_stdout,
            expected_stderr,
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
            mock_popen, command, {"env": {}, "stdin": -1}
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
                )
            ),
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
                        "environment": {},
                    },
                ),
                (
                    severity.DEBUG,
                    report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
                    {
                        "command": command_str,
                        "return_value": expected_retval,
                        "stdout": expected_stdout,
                        "stderr": expected_stderr,
                    },
                ),
            ],
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
                },
            ),
        )

        mock_process.communicate.assert_not_called()
        self.assert_popen_called_with(
            mock_popen,
            command,
            {
                "env": {},
                "stdin": DEVNULL,
            },
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
                        "environment": {},
                    },
                )
            ],
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
                },
            ),
        )

        mock_process.communicate.assert_called_once_with(None)
        self.assert_popen_called_with(
            mock_popen,
            command,
            {
                "env": {},
                "stdin": DEVNULL,
            },
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
                        "environment": {},
                    },
                )
            ],
        )


class KillServicesTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=lib.CommandRunner)
        self.services = ["service1", "service2"]

    def test_success(self):
        self.mock_runner.run.return_value = ("", "", 0)
        lib.kill_services(self.mock_runner, self.services)
        self.mock_runner.run.assert_called_once_with(
            [settings.killall_exec, "--quiet", "--signal", "9", "--"]
            + self.services
        )

    def test_failed(self):
        self.mock_runner.run.return_value = ("", "error", 1)
        self.assertRaises(
            lib.KillServicesError,
            lambda: lib.kill_services(self.mock_runner, self.services),
        )
        self.mock_runner.run.assert_called_once_with(
            [settings.killall_exec, "--quiet", "--signal", "9", "--"]
            + self.services
        )

    def test_service_not_running(self):
        self.mock_runner.run.return_value = ("", "", 1)
        lib.kill_services(self.mock_runner, self.services)
        self.mock_runner.run.assert_called_once_with(
            [settings.killall_exec, "--quiet", "--signal", "9", "--"]
            + self.services
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
