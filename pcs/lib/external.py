from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import base64
import inspect
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
import ssl
import subprocess
import sys
try:
    # python2
    from urllib import urlencode as urllib_urlencode
except ImportError:
    # python3
    from urllib.parse import urlencode as urllib_urlencode
try:
    # python2
    from urllib2 import (
        build_opener as urllib_build_opener,
        HTTPCookieProcessor as urllib_HTTPCookieProcessor,
        HTTPSHandler as urllib_HTTPSHandler,
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )
except ImportError:
    # python3
    from urllib.request import (
        build_opener as urllib_build_opener,
        HTTPCookieProcessor as urllib_HTTPCookieProcessor,
        HTTPSHandler as urllib_HTTPSHandler
    )
    from urllib.error import (
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )

from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem
from pcs import settings


def is_path_runnable(path):
    return os.path.isfile(path) and os.access(path, os.X_OK)


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
    output, retval = runner.run([
        os.path.join(settings.corosync_binaries, "corosync"),
        "-v"
    ])
    if retval != 0:
        return False
    match = re.search(r"version\D+(\d+)", output)
    return match is not None and match.group(1) == "1"


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


class NodeCommunicationException(Exception):
    # pylint: disable=super-init-not-called
    def __init__(self, node, command, reason):
        self.node = node
        self.command = command
        self.reason = reason


class NodeConnectionException(NodeCommunicationException):
    pass


class NodeAuthenticationException(NodeCommunicationException):
    pass


class NodePermissionDeniedException(NodeCommunicationException):
    pass


class NodeUnsupportedCommandException(NodeCommunicationException):
    pass


def node_communicator_exception_to_report_item(e):
    """
    Transform NodeCommunicationException to ReportItem
    """
    if e.__class__ == NodeAuthenticationException:
        return ReportItem.error(
            error_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
            "Unable to authenticate to {node} ({reason})",
            info={
                "node": e.node,
                "command": e.command,
                "reason": "HTTP error: {0}".format(e.reason),
            }
        )
    if e.__class__ == NodePermissionDeniedException:
        return ReportItem.error(
            error_codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED,
            "{node}: Permission denied ({reason})",
            info={
                "node": e.node,
                "command": e.command,
                "reason": "HTTP error: {0}".format(e.reason),
            }
        )
    if e.__class__ == NodeUnsupportedCommandException:
        return ReportItem.error(
            error_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
            "{node}: Unsupported command ({reason})",
            info={
                "node": e.node,
                "command": e.command,
                "reason": "HTTP error: {0}".format(e.reason),
            }
        )
    if e.__class__ == NodeCommunicationException:
        return ReportItem.error(
            error_codes.NODE_COMMUNICATION_ERROR,
            "Error connecting to {node} ({reason})",
            info={
                "node": e.node,
                "command": e.command,
                "reason": "HTTP error: {0}".format(e.reason),
            }
        )
    if e.__class__ == NodeConnectionException:
        return ReportItem.error(
            error_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
            "Unable to connect to {node} ({reason})",
            info={
                "node": e.node,
                "command": e.command,
                "reason": e.reason,
            }
        )
    raise e

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

    def __init__(self, logger, auth_tokens, user=None, groups=None):
        """
        auth_tokens authorization tokens for nodes: {node: token}
        user username
        groups groups the user is member of
        """
        self._logger = logger
        self._auth_tokens = auth_tokens
        self._user = user
        self._groups = groups

    def call_node(self, node_addr, request, data):
        """
        Send a request to a node
        node_addr destination node, instance of NodeAddresses
        request command to be run on the node
        data command parameters, encoded by format_data_* method
        """
        return self.call_host(node_addr.ring0, request, data)

    def call_host(self, host, request, data):
        """
        Send a request to a host
        host host address
        request command to be run on the host
        data command parameters, encoded by format_data_* method
        """
        opener = self.__get_opener()
        url = "https://{host}:2224/{request}".format(
            host=("[{0}]".format(host) if ":" in host else host),
            request=request
        )
        cookies = self.__prepare_cookies(host)
        if cookies:
            opener.addheaders.append(("Cookie", ";".join(cookies)))

        msg = "Sending HTTP Request to: {url}"
        if data:
            msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
        self._logger.debug(msg.format(url=url, data=data))
        result_msg = (
            "Finished calling: {url}\nResponse Code: {code}"
            + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
        )

        try:
            # python3 requires data to be bytes not str
            if data:
                data = data.encode("utf-8")
            result = opener.open(url, data)
            # python3 returns bytes not str
            response_data = result.read().decode("utf-8")
            self._logger.debug(result_msg.format(
                url=url,
                code=result.getcode(),
                response=response_data
            ))
            return response_data
        except urllib_HTTPError as e:
            # python3 returns bytes not str
            response_data = e.read().decode("utf-8")
            self._logger.debug(result_msg.format(
                url=url,
                code=e.code,
                response=response_data
            ))
            if e.code == 401:
                raise NodeAuthenticationException(host, request, e.code)
            elif e.code == 403:
                raise NodePermissionDeniedException(host, request, e.code)
            elif e.code == 404:
                raise NodeUnsupportedCommandException(host, request, e.code)
            else:
                raise NodeCommunicationException(host, request, e.code)
        except urllib_URLError as e:
            msg = "Unable to connect to {node} ({reason})"
            self._logger.debug(msg.format(node=host, reason=e.reason))
            raise NodeConnectionException(host, request, e.reason)

    def __get_opener(self):
        # enable self-signed certificates
        # https://www.python.org/dev/peps/pep-0476/
        # http://bugs.python.org/issue21308
        if (
            hasattr(ssl, "_create_unverified_context")
            and
            "context" in inspect.getargspec(urllib_HTTPSHandler.__init__).args
        ):
            opener = urllib_build_opener(
                urllib_HTTPSHandler(context=ssl._create_unverified_context()),
                urllib_HTTPCookieProcessor()
            )
        else:
            opener = urllib_build_opener(urllib_HTTPCookieProcessor())
        return opener

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
                base64.b64encode(" ".join(self._groups).encode("utf-8"))
            ))
        return cookies
