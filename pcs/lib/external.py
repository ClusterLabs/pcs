import re
from shlex import quote as shell_quote
import signal
import subprocess
from typing import Optional

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.system import is_systemd as is_systemctl
from pcs.common.str_tools import join_multilines
from pcs.lib.errors import LibraryError


_chkconfig = settings.chkconfig_binary
_service = settings.service_binary
_systemctl = settings.systemctl_binary


class ManageServiceError(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, service, message=None, instance=None):
        self.service = service
        self.message = message
        self.instance = instance


class DisableServiceError(ManageServiceError):
    pass


class EnableServiceError(ManageServiceError):
    pass


class StartServiceError(ManageServiceError):
    pass


class StopServiceError(ManageServiceError):
    pass


class KillServicesError(ManageServiceError):
    pass


class CommandRunner:
    def __init__(self, logger, reporter: ReportProcessor, env_vars=None):
        self._logger = logger
        self._reporter = reporter
        # Reset environment variables by empty dict is desired here.  We need
        # to get rid of defaults - we do not know the context and environment
        # where the library runs.  We also get rid of PATH settings, so all
        # executables must be specified with full path unless the PATH variable
        # is set from outside.
        self._env_vars = env_vars if env_vars else dict()

    @property
    def env_vars(self):
        return self._env_vars.copy()

    def run(
        self, args, stdin_string=None, env_extend=None, binary_output=False
    ):
        # Allow overriding default settings. If a piece of code really wants to
        # set own PATH or CIB_file, we must allow it. I.e. it wants to run
        # a pacemaker tool on a CIB in a file but cannot afford the risk of
        # changing the CIB in the file specified by the user.
        env_vars = self._env_vars.copy()
        env_vars.update(dict(env_extend) if env_extend else dict())

        log_args = " ".join([shell_quote(x) for x in args])
        self._logger.debug(
            "Running: {args}\nEnvironment:{env_vars}{stdin_string}".format(
                args=log_args,
                stdin_string=(
                    ""
                    if not stdin_string
                    else (
                        "\n--Debug Input Start--\n{0}\n--Debug Input End--"
                    ).format(stdin_string)
                ),
                env_vars=(
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
                ),
            )
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
                preexec_fn=(
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
                "Finished running: {args}\nReturn value: {retval}"
                + "\n--Debug Stdout Start--\n{out_std}\n--Debug Stdout End--"
                + "\n--Debug Stderr Start--\n{out_err}\n--Debug Stderr End--"
            ).format(
                args=log_args, retval=retval, out_std=out_std, out_err=out_err
            )
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


def _get_service_name(service, instance=None):
    return "{0}{1}.service".format(
        service, "" if instance is None else "@{0}".format(instance)
    )


def ensure_is_systemd():
    """
    Raise a LibraryError if the current system is not a systemd system
    """
    if not is_systemctl():
        raise LibraryError(
            ReportItem.error(
                reports.messages.UnsupportedOperationOnNonSystemdSystems()
            )
        )


def disable_service(runner, service, instance=None):
    """
    Disable specified service in local system.
    Raise DisableServiceError or LibraryError on failure.

    runner -- CommandRunner
    service -- name of service
    instance -- instance name, it ha no effect on not systemd systems.
        If None no instance name will be used.
    """
    if not is_service_installed(runner, service, instance):
        return
    if is_systemctl():
        stdout, stderr, retval = runner.run(
            [_systemctl, "disable", _get_service_name(service, instance)]
        )
    else:
        stdout, stderr, retval = runner.run([_chkconfig, service, "off"])
    if retval != 0:
        raise DisableServiceError(
            service, join_multilines([stderr, stdout]), instance
        )


def enable_service(runner, service, instance=None):
    """
    Enable specified service in local system.
    Raise EnableServiceError or LibraryError on failure.

    runner -- CommandRunner
    service -- name of service
    instance -- instance name, it ha no effect on not systemd systems.
        If None no instance name will be used.
    """
    if is_systemctl():
        stdout, stderr, retval = runner.run(
            [_systemctl, "enable", _get_service_name(service, instance)]
        )
    else:
        stdout, stderr, retval = runner.run([_chkconfig, service, "on"])
    if retval != 0:
        raise EnableServiceError(
            service, join_multilines([stderr, stdout]), instance
        )


def start_service(runner, service, instance=None):
    """
    Start specified service in local system
    CommandRunner runner
    string service service name
    string instance instance name, it ha no effect on not systemd systems.
        If None no instance name will be used.
    """
    if is_systemctl():
        stdout, stderr, retval = runner.run(
            [_systemctl, "start", _get_service_name(service, instance)]
        )
    else:
        stdout, stderr, retval = runner.run([_service, service, "start"])
    if retval != 0:
        raise StartServiceError(
            service, join_multilines([stderr, stdout]), instance
        )


def stop_service(runner, service, instance=None):
    """
    Stop specified service in local system
    CommandRunner runner
    string service service name
    string instance instance name, it ha no effect on not systemd systems.
        If None no instance name will be used.
    """
    if is_systemctl():
        stdout, stderr, retval = runner.run(
            [_systemctl, "stop", _get_service_name(service, instance)]
        )
    else:
        stdout, stderr, retval = runner.run([_service, service, "stop"])
    if retval != 0:
        raise StopServiceError(
            service, join_multilines([stderr, stdout]), instance
        )


def kill_services(runner, services):
    """
    Kill specified services in local system
    CommandRunner runner
    iterable services service names
    """
    # make killall not report that a process is not running
    stdout, stderr, retval = runner.run(
        [settings.killall_executable, "--quiet", "--signal", "9", "--"]
        + list(services)
    )
    # If a process isn't running, killall will still return 1 even with --quiet.
    # We don't consider that an error, so we check for output string as well.
    # If it's empty, no actuall error happened.
    if retval != 0:
        message = join_multilines([stderr, stdout])
        if message:
            raise KillServicesError(list(services), message)


def is_service_enabled(
    runner: CommandRunner, service: str, instance: Optional[str] = None
) -> bool:
    """
    Check if the specified service is enabled in the local system.

    runner -- CommandRunner
    service -- name of the service
    instance -- optional name of the services's instance
    """
    if is_systemctl():
        dummy_stdout, dummy_stderr, retval = runner.run(
            [_systemctl, "is-enabled", _get_service_name(service, instance)]
        )
    else:
        dummy_stdout, dummy_stderr, retval = runner.run([_chkconfig, service])

    return retval == 0


def is_service_running(
    runner: CommandRunner, service: str, instance: Optional[str] = None
) -> bool:
    """
    Check if the specified service is currently running on the local system.

    runner -- CommandRunner
    service -- name of the service
    instance -- optional name of the services's instance
    """
    if is_systemctl():
        dummy_stdout, dummy_stderr, retval = runner.run(
            [_systemctl, "is-active", _get_service_name(service, instance)]
        )
    else:
        dummy_stdout, dummy_stderr, retval = runner.run(
            [_service, service, "status"]
        )

    return retval == 0


def is_service_installed(runner, service, instance=None):
    """
    Check if specified service is installed on local system.

    runner -- CommandRunner
    service -- name of service
    instance -- systemd service instance
    """
    if not is_systemctl():
        return service in get_non_systemd_services(runner)
    service_name = "{0}{1}".format(service, "" if instance is None else "@")
    return service_name in get_systemd_services(runner)


def get_non_systemd_services(runner):
    """
    Returns list of all installed services on non systemd system.

    runner -- CommandRunner
    """
    if is_systemctl():
        return []

    stdout, dummy_stderr, return_code = runner.run([_chkconfig])
    if return_code != 0:
        return []

    service_list = []
    for service in stdout.splitlines():
        service = service.split(" ", 1)[0]
        if service:
            service_list.append(service)
    return service_list


def get_systemd_services(runner):
    """
    Returns list of all systemd services installed on local system.

    runner -- CommandRunner
    """
    if not is_systemctl():
        return []

    stdout, dummy_stderr, return_code = runner.run(
        [_systemctl, "list-unit-files", "--full"]
    )
    if return_code != 0:
        return []

    service_list = []
    for service in stdout.splitlines():
        match = re.search(r"^([\S]*)\.service", service)
        if match:
            service_list.append(match.group(1))
    return service_list


def is_proxy_set(env_dict):
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
