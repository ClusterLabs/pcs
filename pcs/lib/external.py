import signal
import subprocess
from logging import Logger
from shlex import quote as shell_quote
from typing import (
    Dict,
    Mapping,
    Optional,
    Tuple,
)

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.str_tools import join_multilines
from pcs.common.types import StringSequence
from pcs.lib.errors import LibraryError


class KillServicesError(Exception):
    def __init__(self, service, message=None, instance=None):
        self.service = service
        self.message = message
        self.instance = instance


class CommandRunner:
    def __init__(
        self,
        logger: Logger,
        reporter: ReportProcessor,
        env_vars: Optional[Mapping[str, str]] = None,
    ):
        self._logger = logger
        self._reporter = reporter
        # Reset environment variables by empty dict is desired here.  We need
        # to get rid of defaults - we do not know the context and environment
        # where the library runs.  We also get rid of PATH settings, so all
        # executables must be specified with full path unless the PATH variable
        # is set from outside.
        self._env_vars = env_vars if env_vars else {}

    @property
    def env_vars(self) -> Dict[str, str]:
        return dict(self._env_vars)

    def run(
        self,
        args: StringSequence,
        stdin_string: Optional[str] = None,
        env_extend: Optional[Mapping[str, str]] = None,
        binary_output: bool = False,
    ) -> Tuple[str, str, int]:
        # Allow overriding default settings. If a piece of code really wants to
        # set own PATH or CIB_file, we must allow it. I.e. it wants to run
        # a pacemaker tool on a CIB in a file but cannot afford the risk of
        # changing the CIB in the file specified by the user.
        env_vars = dict(self._env_vars)
        env_vars.update(dict(env_extend) if env_extend else {})

        log_args = " ".join([shell_quote(x) for x in args])
        env = (
            ""
            if not env_vars
            else (
                "\n"
                + "\n".join(
                    [
                        "  {0}={1}".format(key, val)
                        for key, val in sorted(env_vars.items())
                    ]
                )
            )
        )
        stdin = (
            ""
            if not stdin_string
            else ("\n--Debug Input Start--\n{0}\n--Debug Input End--").format(
                stdin_string
            )
        )
        self._logger.debug(
            "Running: %s\nEnvironment:%s%s", log_args, env, stdin
        )
        self._reporter.report(
            ReportItem.debug(
                reports.messages.RunExternalProcessStarted(
                    log_args,
                    stdin_string,
                    env_vars,
                )
            )
        )

        try:
            # pylint: disable=subprocess-popen-preexec-fn, consider-using-with
            # this is OK as pcs is only single-threaded application
            process = subprocess.Popen(
                args,
                # Some commands react differently if they get anything via stdin
                stdin=(
                    subprocess.PIPE
                    if stdin_string is not None
                    else subprocess.DEVNULL
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=(  # noqa: PLW1509
                    lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)
                ),
                close_fds=True,
                shell=False,
                env=env_vars,
                # decodes newlines and in python3 also converts bytes to str
                universal_newlines=(not binary_output),
            )
            out_std, out_err = process.communicate(stdin_string)
            retval = process.returncode
        except OSError as e:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.RunExternalProcessError(
                        log_args,
                        e.strerror,
                    )
                )
            ) from e

        self._logger.debug(
            (
                "Finished running: %s\nReturn value: %s"
                "\n--Debug Stdout Start--\n%s\n--Debug Stdout End--"
                "\n--Debug Stderr Start--\n%s\n--Debug Stderr End--"
            ),
            log_args,
            retval,
            out_std,
            out_err,
        )
        self._reporter.report(
            ReportItem.debug(
                reports.messages.RunExternalProcessFinished(
                    log_args,
                    retval,
                    out_std,
                    out_err,
                )
            )
        )
        return out_std, out_err, retval


def kill_services(runner, services):
    """
    Kill specified services in local system
    CommandRunner runner
    iterable services service names
    """
    # make killall not report that a process is not running
    stdout, stderr, retval = runner.run(
        [settings.killall_exec, "--quiet", "--signal", "9", "--"]
        + list(services)
    )
    # If a process isn't running, killall will still return 1 even with --quiet.
    # We don't consider that an error, so we check for output string as well.
    # If it's empty, no actual error happened.
    if retval != 0:
        message = join_multilines([stderr, stdout])
        if message:
            raise KillServicesError(list(services), message)


def is_proxy_set(env_dict: Mapping) -> bool:
    """
    Returns True whenever any of proxy environment variables (https_proxy,
    HTTPS_PROXY, all_proxy, ALL_PROXY) are set in env_dict. False otherwise.

    env_dict -- environment variables in dict
    """
    proxy_list = ["https_proxy", "all_proxy"]
    for var in proxy_list + [v.upper() for v in proxy_list]:
        if env_dict.get(var, "") != "":
            return True
    return False
