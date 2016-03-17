from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

try:
    # python 2
    from pipes import quote as shell_quote
except ImportError:
    # python 3
    from shlex import quote as shell_quote
import signal
import subprocess
import sys

from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem


class CommandRunner(object):
    def __init__(self, logger, env_vars=None):
        self._logger = logger
        self._env_vars = env_vars if env_vars else dict()
        self._python2 = sys.version[0] == "2"

    def run(
        self, args, ignore_stderr=False, stdin_string=None, env_extend=None,
        binary_output=False
    ):
        env_vars = dict(env_extend) if env_extend else dict()
        env_vars.update(self._env_vars)

        log_args = " ".join([shell_quote(x) for x in args])
        msg = "Running: {args}"
        if stdin_string:
            msg += "\n--Debug Input Start--\n{stdin}\n--Debug Input End--"
        self._logger.debug(msg.format(args=log_args, stdin=stdin_string))

        try:
            process = subprocess.Popen(
                args,
                # Some commands react differently if they get anything via stdin
                stdin=(subprocess.PIPE if stdin_string is not None else None),
                stdout=subprocess.PIPE,
                stderr=(
                    subprocess.PIPE if ignore_stderr else subprocess.STDOUT
                ),
                preexec_fn=(
                    lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)
                ),
                close_fds=True,
                shell=False,
                env=env_vars,
                # decodes newlines and in python3 also converts bytes to str
                universal_newlines=(not self._python2 and not binary_output)
            )
            output, dummy_stderror = process.communicate(stdin_string)
            retval = process.returncode
        except OSError as e:
            raise LibraryError(ReportItem.error(
                error_codes.RUN_EXTERNAL_PROCESS_ERROR,
                "unable to run command {command_raw[0]}: {reason}",
                info={
                    "command_raw": args,
                    "command": log_args,
                    "reason": e.strerror
                }
            ))

        self._logger.debug(
            (
                "Finished running: {args}\nReturn value: {retval}"
                + "\n--Debug Output Start--\n{output}\n--Debug Output End--"
            ).format(args=log_args, retval=retval, output=output)
        )
        return output, retval
