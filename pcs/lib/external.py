from __future__ import (
    absolute_import,
    division,
    print_function,
)

import base64
import io
import json
import os

try:
    # python 2
    from pipes import quote as shell_quote
except ImportError:
    # python 3
    from shlex import quote as shell_quote
import re
import signal
import subprocess
import sys
try:
    # python2
    from urllib import urlencode as urllib_urlencode
except ImportError:
    # python3
    from urllib.parse import urlencode as urllib_urlencode
try:
    # python 3
    from subprocess import DEVNULL
except ImportError:
    # python 2
    DEVNULL = open(os.devnull, "r")

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.common.tools import (
    join_multilines,
    simple_cache,
)
from pcs.lib import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity



_chkconfig = settings.chkconfig_binary
_service = settings.service_binary
_systemctl = settings.systemctl_binary

class ManageServiceError(Exception):
    #pylint: disable=super-init-not-called
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


def is_dir_nonempty(path):
    if not os.path.exists(path):
        return False
    if not os.path.isdir(path):
        return True
    return len(os.listdir(path)) > 0


def _get_service_name(service, instance=None):
    return "{0}{1}.service".format(
        service, "" if instance is None else "@{0}".format(instance)
    )

def ensure_is_systemd():
    """
    Ensure if current system is systemd system. Raises Library error if not.
    """
    if not is_systemctl():
        raise LibraryError(
            reports.unsupported_operation_on_non_systemd_systems()
        )



@simple_cache
def is_systemctl():
    """
    Check whenever is local system running on systemd.
    Returns True if current system is systemctl compatible, False otherwise.
    """
    systemd_paths = [
        '/run/systemd/system',
        '/var/run/systemd/system',
    ]
    for path in systemd_paths:
        if os.path.isdir(path):
            return True
    return False


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
        stdout, stderr, retval = runner.run([
            _systemctl, "disable", _get_service_name(service, instance)
        ])
    else:
        stdout, stderr, retval = runner.run([_chkconfig, service, "off"])
    if retval != 0:
        raise DisableServiceError(
            service,
            join_multilines([stderr, stdout]),
            instance
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
        stdout, stderr, retval = runner.run([
            _systemctl, "enable", _get_service_name(service, instance)
        ])
    else:
        stdout, stderr, retval = runner.run([_chkconfig, service, "on"])
    if retval != 0:
        raise EnableServiceError(
            service,
            join_multilines([stderr, stdout]),
            instance
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
        stdout, stderr, retval = runner.run([
            _systemctl, "start", _get_service_name(service, instance)
        ])
    else:
        stdout, stderr, retval = runner.run([_service, service, "start"])
    if retval != 0:
        raise StartServiceError(
            service,
            join_multilines([stderr, stdout]),
            instance
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
        stdout, stderr, retval = runner.run([
            _systemctl, "stop", _get_service_name(service, instance)
        ])
    else:
        stdout, stderr, retval = runner.run([_service, service, "stop"])
    if retval != 0:
        raise StopServiceError(
            service,
            join_multilines([stderr, stdout]),
            instance
        )


def kill_services(runner, services):
    """
    Kill specified services in local system
    CommandRunner runner
    iterable services service names
    """
    # make killall not report that a process is not running
    stdout, stderr, retval = runner.run(
        ["killall", "--quiet", "--signal", "9", "--"] + list(services)
    )
    # If a process isn't running, killall will still return 1 even with --quiet.
    # We don't consider that an error, so we check for output string as well.
    # If it's empty, no actuall error happened.
    if retval != 0:
        message = join_multilines([stderr, stdout])
        if message:
            raise KillServicesError(list(services), message)


def is_service_enabled(runner, service, instance=None):
    """
    Check if specified service is enabled in local system.

    runner -- CommandRunner
    service -- name of service
    """
    if is_systemctl():
        dummy_stdout, dummy_stderr, retval = runner.run(
            [_systemctl, "is-enabled", _get_service_name(service, instance)]
        )
    else:
        dummy_stdout, dummy_stderr, retval = runner.run([_chkconfig, service])

    return retval == 0


def is_service_running(runner, service, instance=None):
    """
    Check if specified service is currently running on local system.

    runner -- CommandRunner
    service -- name of service
    """
    if is_systemctl():
        dummy_stdout, dummy_stderr, retval = runner.run([
            _systemctl,
            "is-active",
            _get_service_name(service, instance)
        ])
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

    stdout, dummy_stderr, return_code = runner.run([
        _systemctl, "list-unit-files", "--full"
    ])
    if return_code != 0:
        return []

    service_list = []
    for service in stdout.splitlines():
        match = re.search(r'^([\S]*)\.service', service)
        if match:
            service_list.append(match.group(1))
    return service_list


def is_cman_cluster(runner):
    """
    Detect if underlaying locally installed cluster is CMAN based
    """
    # Checking corosync version works in most cases and supports non-rhel
    # distributions as well as running (manually compiled) corosync2 on rhel6.
    # - corosync2 does not support cman at all
    # - corosync1 runs with cman on rhel6
    # - corosync1 can be used without cman, but we don't support it anyways
    # - corosync2 is the default result if errors occur
    stdout, dummy_stderr, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync"),
        "-v"
    ])
    if retval != 0:
        return False
    match = re.search(r"version\D+(\d+)", stdout)
    return match is not None and match.group(1) == "1"


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


class CommandRunner(object):
    def __init__(self, logger, reporter, env_vars=None):
        self._logger = logger
        self._reporter = reporter
        # Reset environment variables by empty dict is desired here.  We need
        # to get rid of defaults - we do not know the context and environment
        # where the library runs.  We also get rid of PATH settings, so all
        # executables must be specified with full path unless the PATH variable
        # is set from outside.
        self._env_vars = env_vars if env_vars else dict()
        self._python2 = (sys.version_info.major == 2)

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
        env_vars.update(
            dict(env_extend) if env_extend else dict()
        )

        log_args = " ".join([shell_quote(x) for x in args])
        self._logger.debug(
            "Running: {args}\nEnvironment:{env_vars}{stdin_string}".format(
                args=log_args,
                stdin_string=("" if not stdin_string else (
                    "\n--Debug Input Start--\n{0}\n--Debug Input End--"
                    .format(stdin_string)
                )),
                env_vars=("" if not env_vars else (
                    "\n" + "\n".join([
                        "  {0}={1}".format(key, val)
                        for key, val in sorted(env_vars.items())
                    ])
                ))
            )
        )
        self._reporter.process(
            reports.run_external_process_started(
                log_args, stdin_string, env_vars
            )
        )

        try:
            process = subprocess.Popen(
                args,
                # Some commands react differently if they get anything via stdin
                stdin=(
                    subprocess.PIPE if stdin_string is not None else DEVNULL
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
                universal_newlines=(not self._python2 and not binary_output)
            )
            out_std, out_err = process.communicate(stdin_string)
            retval = process.returncode
        except OSError as e:
            raise LibraryError(
                reports.run_external_process_error(log_args, e.strerror)
            )

        self._logger.debug(
            (
                "Finished running: {args}\nReturn value: {retval}"
                + "\n--Debug Stdout Start--\n{out_std}\n--Debug Stdout End--"
                + "\n--Debug Stderr Start--\n{out_err}\n--Debug Stderr End--"
            ).format(
                args=log_args,
                retval=retval,
                out_std=out_std,
                out_err=out_err
            )
        )
        self._reporter.process(reports.run_external_process_finished(
            log_args, retval, out_std, out_err
        ))
        return out_std, out_err, retval


# deprecated
class NodeCommunicationException(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, node, command, reason):
        self.node = node
        self.command = command
        self.reason = reason


# deprecated
class NodeConnectionException(NodeCommunicationException):
    pass


# deprecated
class NodeAuthenticationException(NodeCommunicationException):
    pass


# deprecated
class NodePermissionDeniedException(NodeCommunicationException):
    pass

# deprecated
class NodeCommandUnsuccessfulException(NodeCommunicationException):
    pass

# deprecated
class NodeUnsupportedCommandException(NodeCommunicationException):
    pass


# deprecated
class NodeConnectionTimedOutException(NodeCommunicationException):
    pass


# deprecated
def node_communicator_exception_to_report_item(
    e, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Transform NodeCommunicationException to ReportItem
    """
    if isinstance(e, NodeCommandUnsuccessfulException):
        return reports.node_communication_command_unsuccessful(
            e.node,
            e.command,
            e.reason
        )
    exception_to_report = {
        NodeAuthenticationException:
            reports.node_communication_error_not_authorized,
        NodePermissionDeniedException:
            reports.node_communication_error_permission_denied,
        NodeUnsupportedCommandException:
            reports.node_communication_error_unsupported_command,
        NodeCommunicationException:
            reports.node_communication_error_other_error,
        NodeConnectionException:
            reports.node_communication_error_unable_to_connect,
        NodeConnectionTimedOutException:
            reports.node_communication_error_timed_out,
    }
    if e.__class__ in exception_to_report:
        return exception_to_report[e.__class__](
            e.node,
            e.command,
            e.reason,
            severity,
            forceable
        )
    raise e

# deprecated, use pcs.common.node_communicator.Communicator
class NodeCommunicator(object):
    """
    Sends requests to nodes
    """

    @classmethod
    def format_data_dict(cls, data):
        """
        Encode data for transport (only plain dict is supported)
        """
        return urllib_urlencode(data)

    @classmethod
    def format_data_json(cls, data):
        """
        Encode data for transport (more complex data than in format_data_dict)
        """
        return json.dumps(data)

    def __init__(
        self, logger, reporter, auth_tokens, user=None, groups=None,
        request_timeout=None
    ):
        """
        auth_tokens authorization tokens for nodes: {node: token}
        user username
        groups groups the user is member of
        request_timeout -- positive integer, time for one reqest in seconds
        """
        self._logger = logger
        self._reporter = reporter
        self._auth_tokens = auth_tokens
        self._user = user
        self._groups = groups
        self._request_timeout = request_timeout

    @property
    def request_timeout(self):
        return (
            settings.default_request_timeout
                if self._request_timeout is None
                else self._request_timeout
        )

    def call_node(self, node_addr, request, data, request_timeout=None):
        """
        Send a request to a node
        node_addr destination node, instance of NodeAddresses
        request command to be run on the node
        data command parameters, encoded by format_data_* method
        """
        return self.call_host(node_addr.ring0, request, data, request_timeout)

    def call_host(self, host, request, data, request_timeout=None):
        """
        Send a request to a host
        host host address
        request command to be run on the host
        data command parameters, encoded by format_data_* method
        request timeout float timeout for request, if not set object property
            will be used
        """
        def __debug_callback(data_type, debug_data):
            prefixes = {
                pycurl.DEBUG_TEXT: b"* ",
                pycurl.DEBUG_HEADER_IN: b"< ",
                pycurl.DEBUG_HEADER_OUT: b"> ",
                pycurl.DEBUG_DATA_IN: b"<< ",
                pycurl.DEBUG_DATA_OUT: b">> ",
            }
            if data_type in prefixes:
                debug_output.write(prefixes[data_type])
                debug_output.write(debug_data)
                if not debug_data.endswith(b"\n"):
                    debug_output.write(b"\n")

        output = io.BytesIO()
        debug_output = io.BytesIO()
        cookies = self.__prepare_cookies(host)
        timeout = (
            request_timeout
            if request_timeout is not None
            else self.request_timeout
        )
        url = "https://{host}:2224/{request}".format(
            host=("[{0}]".format(host) if ":" in host else host),
            request=request
        )

        handler = pycurl.Curl()
        handler.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTPS)
        handler.setopt(pycurl.TIMEOUT_MS, int(timeout * 1000))
        handler.setopt(pycurl.URL, url.encode("utf-8"))
        handler.setopt(pycurl.WRITEFUNCTION, output.write)
        handler.setopt(pycurl.VERBOSE, 1)
        handler.setopt(pycurl.DEBUGFUNCTION, __debug_callback)
        handler.setopt(pycurl.SSL_VERIFYHOST, 0)
        handler.setopt(pycurl.SSL_VERIFYPEER, 0)
        handler.setopt(pycurl.NOSIGNAL, 1) # required for multi-threading
        handler.setopt(pycurl.HTTPHEADER, ["Expect: "])
        if cookies:
            handler.setopt(pycurl.COOKIE, ";".join(cookies).encode("utf-8"))
        if data:
            handler.setopt(pycurl.COPYPOSTFIELDS, data.encode("utf-8"))

        msg = "Sending HTTP Request to: {url}"
        if data:
            msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
        self._logger.debug(msg.format(url=url, data=data))
        self._reporter.process(
            reports.node_communication_started(url, data)
        )
        result_msg = (
            "Finished calling: {url}\nResponse Code: {code}"
            + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
        )

        try:
            handler.perform()
            response_data = output.getvalue().decode("utf-8")
            response_code = handler.getinfo(pycurl.RESPONSE_CODE)
            self._logger.debug(result_msg.format(
                url=url,
                code=response_code,
                response=response_data
            ))
            self._reporter.process(reports.node_communication_finished(
                url, response_code, response_data
            ))
            if response_code == 400:
                # old pcsd protocol: error messages are commonly passed in plain
                # text in response body with HTTP code 400
                # we need to be backward compatible with that
                raise NodeCommandUnsuccessfulException(
                    host, request, response_data.rstrip()
                )
            elif response_code == 401:
                raise NodeAuthenticationException(
                    host, request, "HTTP error: {0}".format(response_code)
                )
            elif response_code == 403:
                raise NodePermissionDeniedException(
                    host, request, "HTTP error: {0}".format(response_code)
                )
            elif response_code == 404:
                raise NodeUnsupportedCommandException(
                    host, request, "HTTP error: {0}".format(response_code)
                )
            elif response_code >= 400:
                raise NodeCommunicationException(
                    host, request, "HTTP error: {0}".format(response_code)
                )
            return response_data
        except pycurl.error as e:
            # In pycurl versions lower then 7.19.3 it is not possible to set
            # NOPROXY option. Therefore for the proper support of proxy settings
            # we have to use environment variables.
            if is_proxy_set(os.environ):
                self._logger.warning("Proxy is set")
                self._reporter.process(
                    reports.node_communication_proxy_is_set()
                )
            errno, reason = e.args
            msg = "Unable to connect to {node} ({reason})"
            self._logger.debug(msg.format(node=host, reason=reason))
            self._reporter.process(
                reports.node_communication_not_connected(host, reason)
            )
            if errno == pycurl.E_OPERATION_TIMEDOUT:
                raise NodeConnectionTimedOutException(host, request, reason)
            else:
                raise NodeConnectionException(host, request, reason)
        finally:
            debug_data = debug_output.getvalue().decode("utf-8", "ignore")
            self._logger.debug(
                (
                    "Communication debug info for calling: {url}\n"
                    "--Debug Communication Info Start--\n"
                    "{data}\n"
                    "--Debug Communication Info End--"
                ).format(url=url, data=debug_data)
            )
            self._reporter.process(
                reports.node_communication_debug_info(url, debug_data)
            )

    def __prepare_cookies(self, host):
        # Let's be safe about characters in variables (they can come from env)
        # and do base64. We cannot do it for CIB_user however to be backward
        # compatible so we at least remove disallowed characters.
        cookies = []
        if host in self._auth_tokens:
            cookies.append("token={0}".format(self._auth_tokens[host]))
        if self._user:
            cookies.append("CIB_user={0}".format(
                re.sub(r"[^!-~]", "", self._user).replace(";", "")
            ))
        if self._groups:
            cookies.append("CIB_user_groups={0}".format(
                # python3 requires the value to be bytes not str
                base64.b64encode(
                    " ".join(self._groups).encode("utf-8")
                ).decode("utf-8")
            ))
        return cookies
