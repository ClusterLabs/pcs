from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import unittest
try:
    import unittest.mock as mock
except ImportError:
    import mock

import logging
from pcs.test.library_test_tools import LibraryAssertionMixin

from pcs.lib import error_codes
from pcs.lib.errors import ReportItemSeverity as Severity
import pcs.lib.external as lib

@mock.patch("subprocess.Popen", autospec=True)
class CommandRunnerTest(unittest.TestCase, LibraryAssertionMixin):
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
                Severity.ERROR,
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
                Severity.ERROR,
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
