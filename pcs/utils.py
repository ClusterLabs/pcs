# pylint: disable=too-many-lines
import base64
import getpass
import json
import logging
import os
import re
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import xml.dom.minidom
import xml.etree.ElementTree as ET
from functools import lru_cache
from io import BytesIO
from textwrap import dedent
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Optional,
    Tuple,
)
from urllib.parse import urlencode
from xml.dom.minidom import Document as DomDocument
from xml.dom.minidom import parseString

import pcs.cli.booth.env
import pcs.lib.corosync.config_parser as corosync_conf_parser
from pcs import (
    settings,
    usage,
)
from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common import middleware
from pcs.cli.common.env_cli import Env
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.lib_wrapper import Library
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.common.tools import (
    print_to_stderr,
    timeout_to_seconds_legacy,
)
from pcs.cli.file import metadata as cli_file_metadata
from pcs.cli.reports import ReportProcessorToConsole, process_library_reports
from pcs.cli.reports import output as reports_output
from pcs.common import const, file_type_codes
from pcs.common import file as pcs_file
from pcs.common import pacemaker as common_pacemaker
from pcs.common import pcs_pycurl as pycurl
from pcs.common.host import PcsKnownHost
from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
)
from pcs.common.reports import ReportProcessor
from pcs.common.reports.messages import CibUpgradeFailedToMinimalRequiredVersion
from pcs.common.services.errors import ManageServiceError
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.str_tools import format_list
from pcs.common.tools import (
    Version,
    timeout_to_seconds,
)
from pcs.common.types import StringSequence
from pcs.lib.corosync.config_facade import ConfigFacade as corosync_conf_facade
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import (
    CommandRunner,
    is_proxy_set,
)
from pcs.lib.file.instance import FileInstance as LibFileInstance
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.pacemaker.live import get_cluster_status_dom
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.values import is_score as is_score_value
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.services import get_service_manager as _get_service_manager
from pcs.lib.services import service_exception_to_report

if TYPE_CHECKING:
    from pcs.common.reports.item import ReportItemList

# pylint: disable=invalid-name
# pylint: disable=too-many-branches

# usefile & filename variables are set in pcs module
usefile = False
filename = ""
# Note: not properly typed
pcs_options: Dict[Any, Any] = {}


def _getValidateWithVersion(dom) -> Version:
    """
    Commandline options: no options
    """
    cib = dom.getElementsByTagName("cib")
    if len(cib) != 1:
        err("Bad cib")

    cib = cib[0]

    version = cib.getAttribute("validate-with")
    r = re.compile(r"pacemaker-(\d+)\.(\d+)\.?(\d+)?")
    m = r.match(version)
    if m is None:
        raise AssertionError()
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3) or 0)
    return Version(major, minor, rev)


def isCibVersionSatisfied(cib_dom, required_version: Version) -> bool:
    if not isinstance(cib_dom, DomDocument):
        cib_dom = cib_dom.ownerDocument
    return _getValidateWithVersion(cib_dom) >= required_version


# Check the current pacemaker version in cib and upgrade it if necessary
# Returns False if not upgraded and True if upgraded
def _checkAndUpgradeCIB(required_version: Version) -> bool:
    """
    Commandline options:
      * -f - CIB file
    """
    if isCibVersionSatisfied(get_cib_dom(), required_version):
        return False
    cluster_upgrade()
    return True


def cluster_upgrade():
    """
    Commandline options:
      * -f - CIB file
    """
    output, retval = run(["cibadmin", "--upgrade", "--force"])
    if retval != 0:
        err("unable to upgrade cluster: %s" % output)
    if (
        output.strip()
        == "Upgrade unnecessary: Schema is already the latest available"
    ):
        return
    print_to_stderr("Cluster CIB has been upgraded to latest version")


def cluster_upgrade_to_version(required_version: Version) -> Any:
    """
    Commandline options:
      * -f - CIB file
    """
    _checkAndUpgradeCIB(required_version)
    dom = get_cib_dom()
    current_version = _getValidateWithVersion(dom)
    if current_version < required_version:
        err(
            CibUpgradeFailedToMinimalRequiredVersion(
                str(current_version),
                str(required_version),
            ).message
        )
    return dom


# Check status of node
def checkStatus(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(
        node, "remote/status", urlencode({"version": "2"}), False, False
    )


# Check and see if we're authorized (faster than a status check)
def checkAuthorization(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(node, "remote/check_auth", None, False, False)


def get_uid_gid_file_name(uid, gid):
    """
    Commandline options: no options
    """
    return "pcs-uidgid-%s-%s" % (uid, gid)


# Reads in uid file and returns dict of values {'uid':'theuid', 'gid':'thegid'}
def read_uid_gid_file(uidgid_filename):
    """
    Commandline options: no options
    """
    uidgid = {}
    with open(
        os.path.join(settings.corosync_uidgid_dir, uidgid_filename), "r"
    ) as myfile:
        data = myfile.read().split("\n")
    in_uidgid = False
    for data_line in data:
        line = re.sub(r"#.*", "", data_line)
        if not in_uidgid:
            if re.search(r"uidgid.*{", line):
                in_uidgid = True
            else:
                continue
        matches = re.search(r"uid:\s*(\S+)", line)
        if matches:
            uidgid["uid"] = matches.group(1)

        matches = re.search(r"gid:\s*(\S+)", line)
        if matches:
            uidgid["gid"] = matches.group(1)

    return uidgid


def get_uidgid_file_content(
    uid: Optional[str] = None, gid: Optional[str] = None
) -> Optional[str]:
    if not uid and not gid:
        return None
    uid_gid_lines = []
    if uid:
        uid_gid_lines.append(f"  uid: {uid}")
    if gid:
        uid_gid_lines.append(f"  gid: {gid}")
    return dedent(
        """\
        uidgid {{
        {uid_gid_keys}
        }}
        """
    ).format(uid_gid_keys="\n".join(uid_gid_lines))


def write_uid_gid_file(uid, gid):
    """
    Commandline options: no options
    """
    orig_filename = get_uid_gid_file_name(uid, gid)
    uidgid_filename = orig_filename
    counter = 0
    if find_uid_gid_files(uid, gid):
        err("uidgid file with uid=%s and gid=%s already exists" % (uid, gid))

    while os.path.exists(
        os.path.join(settings.corosync_uidgid_dir, uidgid_filename)
    ):
        counter = counter + 1
        uidgid_filename = orig_filename + "-" + str(counter)

    data = get_uidgid_file_content(uid, gid)
    if data:
        with open(
            os.path.join(settings.corosync_uidgid_dir, uidgid_filename), "w"
        ) as uidgid_file:
            uidgid_file.write(data)


def find_uid_gid_files(uid, gid):
    """
    Commandline options: no options
    """
    if uid == "" and gid == "":
        return []

    found_files = []
    uid_gid_files = os.listdir(settings.corosync_uidgid_dir)
    for uidgid_file in uid_gid_files:
        uid_gid_dict = read_uid_gid_file(uidgid_file)
        if ("uid" in uid_gid_dict and uid == "") or (
            "uid" not in uid_gid_dict and uid != ""
        ):
            continue
        if ("gid" in uid_gid_dict and gid == "") or (
            "gid" not in uid_gid_dict and gid != ""
        ):
            continue
        if "uid" in uid_gid_dict and uid != uid_gid_dict["uid"]:
            continue
        if "gid" in uid_gid_dict and gid != uid_gid_dict["gid"]:
            continue

        found_files.append(uidgid_file)

    return found_files


# Removes all uid/gid files with the specified uid/gid, returns false if we
# couldn't find one
def remove_uid_gid_file(uid, gid):
    """
    Commandline options: no options
    """
    if uid == "" and gid == "":
        return False

    file_removed = False
    for uidgid_file in find_uid_gid_files(uid, gid):
        os.remove(os.path.join(settings.corosync_uidgid_dir, uidgid_file))
        file_removed = True

    return file_removed


@lru_cache()
def read_known_hosts_file():
    return read_known_hosts_file_not_cached()


def read_known_hosts_file_not_cached():
    """
    Commandline options: no options
    """
    data = {}
    try:
        if os.getuid() != 0:
            known_hosts_raw_file = pcs_file.RawFile(
                cli_file_metadata.for_file_type(file_type_codes.PCS_KNOWN_HOSTS)
            )
            # json.loads handles bytes, it expects utf-8, 16 or 32 encoding
            known_hosts_struct = json.loads(known_hosts_raw_file.read())
        else:
            # TODO remove
            # This is here to provide known-hosts to functions not yet
            # overhauled to pcs.lib. Cli should never read known hosts from
            # /var/lib/pcsd/.
            known_hosts_instance = LibFileInstance.for_known_hosts()
            known_hosts_struct = known_hosts_instance.read_to_structure()

        # TODO use known hosts facade for getting info from json struct once the
        # facade exists
        data = {
            name: PcsKnownHost.from_known_host_file_dict(name, host)
            for name, host in known_hosts_struct["known_hosts"].items()
        }
    except LibraryError as e:
        # TODO remove
        # This is here to provide known-hosts to functions not yet
        # overhauled to pcs.lib. Cli should never read known hosts from
        # /var/lib/pcsd/.
        process_library_reports(e.args)
    except ParserErrorException as e:
        # TODO remove
        # This is here to provide known-hosts to functions not yet
        # overhauled to pcs.lib. Cli should never read known hosts from
        # /var/lib/pcsd/.
        process_library_reports(
            known_hosts_instance.parser_exception_to_report_list(e)
        )
    except pcs_file.RawFileError as e:
        reports_output.warn("Unable to read the known-hosts file: " + e.reason)
    except json.JSONDecodeError as e:
        reports_output.warn(f"Unable to parse the known-hosts file: {e}")
    except (TypeError, KeyError):
        reports_output.warn("Warning: Unable to parse the known-hosts file.")
    return data


def repeat_if_timeout(send_http_request_function, repeat_count=15):
    """
    Commandline options: no options
    NOTE: callback send_http_request_function may use --request-timeout
    """

    def repeater(node, *args, **kwargs):
        repeats_left = repeat_count
        while True:
            retval, output = send_http_request_function(node, *args, **kwargs)
            if (
                retval != 2
                or "Operation timed out" not in output
                or repeats_left < 1
            ):
                # did not timed out OR repeat limit exceeded
                return retval, output
            repeats_left = repeats_left - 1
            if "--debug" in pcs_options:
                print_to_stderr(f"{node}: {output}, trying again...")

    return repeater


# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(node, "remote/get_corosync_conf", None, False, False)


def setCorosyncConfig(node, config):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    data = urlencode({"corosync_conf": config})
    (status, data) = sendHTTPRequest(node, "remote/set_corosync_conf", data)
    if status != 0:
        err("Unable to set corosync config: {0}".format(data))


def getPacemakerNodeStatus(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(
        node, "remote/pacemaker_node_status", None, False, False
    )


def startCluster(node, quiet=False, timeout=None):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(
        node,
        "remote/cluster_start",
        printResult=False,
        printSuccess=not quiet,
        timeout=timeout,
    )


def stopPacemaker(node, quiet=False, force=True):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return stopCluster(
        node, pacemaker=True, corosync=False, quiet=quiet, force=force
    )


def stopCorosync(node, quiet=False, force=True):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return stopCluster(
        node, pacemaker=False, corosync=True, quiet=quiet, force=force
    )


def stopCluster(node, quiet=False, pacemaker=True, corosync=True, force=True):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    data = {}
    timeout = None
    if pacemaker and not corosync:
        data["component"] = "pacemaker"
        timeout = 2 * 60
    elif corosync and not pacemaker:
        data["component"] = "corosync"
    if force:
        data["force"] = 1
    data = urlencode(data)
    return sendHTTPRequest(
        node,
        "remote/cluster_stop",
        data,
        printResult=False,
        printSuccess=not quiet,
        timeout=timeout,
    )


def enableCluster(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(node, "remote/cluster_enable", None, False, True)


def disableCluster(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(node, "remote/cluster_disable", None, False, True)


def destroyCluster(node, quiet=False):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(
        node, "remote/cluster_destroy", None, not quiet, not quiet
    )


def restoreConfig(node, tarball_data):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    data = urlencode({"tarball": tarball_data})
    return sendHTTPRequest(node, "remote/config_restore", data, False, True)


def pauseConfigSyncing(node, delay_seconds=300):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    data = urlencode({"sync_thread_pause": delay_seconds})
    return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)


def resumeConfigSyncing(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    data = urlencode({"sync_thread_resume": 1})
    return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)


# Send an HTTP request to a node return a tuple with status, data
# If status is 0 then data contains server response
# Otherwise if non-zero then data contains error message
# Returns a tuple (error, error message)
# 0 = Success,
# 1 = HTTP Error
# 2 = No response,
# 3 = Auth Error
# 4 = Permission denied
def sendHTTPRequest(  # noqa: PLR0912, PLR0915
    host, request, data=None, printResult=True, printSuccess=True, timeout=None
):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
      * --debug
    """
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    port = None
    addr = host
    token = None
    known_host = read_known_hosts_file().get(host, None)
    # TODO: do not allow communication with unknown host
    if known_host:
        port = known_host.dest.port
        addr = known_host.dest.addr
        token = known_host.token
    if port is None:
        port = settings.pcsd_default_port
    url = "https://{host}:{port}/{request}".format(
        host="[{0}]".format(addr) if ":" in addr else addr,
        request=request,
        port=port,
    )
    if "--debug" in pcs_options:
        print_to_stderr(f"Sending HTTP Request to: {url}\nData: {data}")

    def __debug_callback(data_type, debug_data):
        prefixes = {
            # pylint: disable=no-member
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

    output = BytesIO()
    debug_output = BytesIO()
    cookies = __get_cookie_list(token)
    if not timeout:
        timeout = settings.default_request_timeout
    timeout = pcs_options.get("--request-timeout", timeout)

    handler = pycurl.Curl()
    handler.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTPS)
    handler.setopt(pycurl.URL, url.encode("utf-8"))
    handler.setopt(pycurl.WRITEFUNCTION, output.write)
    handler.setopt(pycurl.VERBOSE, 1)
    handler.setopt(pycurl.NOSIGNAL, 1)  # required for multi-threading
    handler.setopt(pycurl.DEBUGFUNCTION, __debug_callback)
    handler.setopt(pycurl.TIMEOUT_MS, int(timeout * 1000))
    handler.setopt(pycurl.SSL_VERIFYHOST, 0)
    handler.setopt(pycurl.SSL_VERIFYPEER, 0)
    handler.setopt(pycurl.HTTPHEADER, ["Expect: "])
    if cookies:
        handler.setopt(pycurl.COOKIE, ";".join(cookies).encode("utf-8"))
    if data:
        handler.setopt(pycurl.COPYPOSTFIELDS, data.encode("utf-8"))
    try:
        handler.perform()
        response_data = output.getvalue().decode("utf-8")
        response_code = handler.getinfo(pycurl.RESPONSE_CODE)
        if printResult or printSuccess:
            print_to_stderr(host + ": " + response_data.strip())
        if "--debug" in pcs_options:
            print_to_stderr(
                "Response Code: {response_code}\n"
                "--Debug Response Start--\n"
                "{response_data}\n"
                "--Debug Response End--\n"
                "Communication debug info for calling: {url}\n"
                "--Debug Communication Output Start--\n"
                "{debug_comm_output}\n"
                "--Debug Communication Output End--".format(
                    response_code=response_code,
                    response_data=response_data,
                    url=url,
                    debug_comm_output=debug_output.getvalue().decode(
                        "utf-8", "ignore"
                    ),
                )
            )

        if response_code == 401:
            output = (
                3,
                (
                    "Unable to authenticate to {node} - (HTTP error: {code}), "
                    "try running 'pcs host auth {node}'"
                ).format(node=host, code=response_code),
            )
        elif response_code == 403:
            output = (
                4,
                "{node}: Permission denied - (HTTP error: {code})".format(
                    node=host, code=response_code
                ),
            )
        elif response_code >= 400:
            output = (
                1,
                "Error connecting to {node} - (HTTP error: {code})".format(
                    node=host, code=response_code
                ),
            )
        else:
            output = (0, response_data)

        if printResult and output[0] != 0:
            print_to_stderr(output[1])

        return output
    except pycurl.error as e:
        if is_proxy_set(os.environ):
            reports_output.warn(
                "Proxy is set in environment variables, try disabling it"
            )
        # pylint: disable=unbalanced-tuple-unpacking
        dummy_errno, reason = e.args
        if "--debug" in pcs_options:
            print_to_stderr(f"Response Reason: {reason}")
        msg = (
            "Unable to connect to {host}, check if pcsd is running there or try "
            "setting higher timeout with --request-timeout option ({reason})"
        ).format(host=host, reason=reason)
        if printResult:
            print_to_stderr(msg)
        return (2, msg)


def __get_cookie_list(token):
    """
    Commandline options: no options
    """
    cookies = []
    if token:
        cookies.append("token=" + token)
    if os.geteuid() == 0:
        for name in ("CIB_user", "CIB_user_groups"):
            if name in os.environ and os.environ[name].strip():
                value = os.environ[name].strip()
                # Let's be safe about characters in env variables and do base64.
                # We cannot do it for CIB_user however to be backward compatible
                # so we at least remove disallowed characters.
                if name == "CIB_user":
                    value = re.sub(r"[^!-~]", "", value).replace(";", "")
                else:
                    # python3 requires the value to be bytes not str
                    value = base64.b64encode(value.encode("utf8")).decode(
                        "utf-8"
                    )
                cookies.append("{0}={1}".format(name, value))
    return cookies


def get_corosync_conf_facade(conf_text=None):
    """
    Commandline options:
      * --corosync_conf - path to a mocked corosync.conf is set directly to
        settings
    """
    try:
        return corosync_conf_facade(
            corosync_conf_parser.Parser.parse(
                (getCorosyncConf() if conf_text is None else conf_text).encode(
                    "utf-8"
                )
            )
        )
    except corosync_conf_parser.CorosyncConfParserException as e:
        return err("Unable to parse corosync.conf: %s" % e)


def getNodeAttributesFromPacemaker():
    """
    Commandline options: no options
    """
    try:
        return [
            node.attrs
            for node in ClusterState(
                get_cluster_status_dom(cmd_runner())
            ).node_section.nodes
        ]
    except LibraryError as e:
        return process_library_reports(e.args)


def hasCorosyncConf():
    """
    Commandline options:
      * --corosync_conf - path to a mocked corosync.conf is set directly to
        settings
    """
    return os.path.isfile(settings.corosync_conf_file)


def getCorosyncConf():
    """
    Commandline options:
      * --corosync_conf - path to a mocked corosync.conf is set directly to
        settings
    """
    corosync_conf_content = None
    try:
        with open(
            settings.corosync_conf_file, "r", encoding="utf-8"
        ) as corosync_conf_file:
            corosync_conf_content = corosync_conf_file.read()
    except IOError as e:
        err("Unable to read %s: %s" % (settings.corosync_conf_file, e.strerror))
    return corosync_conf_content


def reloadCorosync():
    """
    Commandline options: no options
    """
    output, retval = run(["corosync-cfgtool", "-R"])
    return output, retval


def getCorosyncActiveNodes():
    """
    Commandline options: no options
    """
    output, retval = run(["corosync-cmapctl"])
    if retval != 0:
        return []

    nodename_re = re.compile(r"^nodelist\.node\.(\d+)\.name .*= (.*)", re.M)
    nodestatus_re = re.compile(
        r"^runtime\.members\.(\d+).status .*= (.*)", re.M
    )
    nodenameid_mapping_re = re.compile(
        r"nodelist\.node\.(\d+)\.nodeid .*= (\d+)", re.M
    )

    node_names = nodename_re.findall(output)

    index_to_id = dict(nodenameid_mapping_re.findall(output))
    id_to_status = dict(nodestatus_re.findall(output))

    node_status = {}
    for index, node_name in node_names:
        if index in index_to_id:
            nodeid = index_to_id[index]
            if nodeid in id_to_status:
                node_status[node_name] = id_to_status[nodeid]
        else:
            print_to_stderr(f"Error mapping {node_name}")

    nodes_active = []
    for node, status in node_status.items():
        if status == "joined":
            nodes_active.append(node)

    return nodes_active


# is it needed to handle corosync-qdevice service when managing cluster services
def need_to_handle_qdevice_service():
    """
    Commandline options: no options
      * --corosync_conf - path to a mocked corosync.conf is set directly to
        settings but it doesn't make sense for contexts in which this function
        is used
    """
    try:
        with open(settings.corosync_conf_file, "rb") as corosync_conf_file:
            return (
                corosync_conf_facade(
                    corosync_conf_parser.Parser.parse(corosync_conf_file.read())
                ).get_quorum_device_model()
                is not None
            )
    except (EnvironmentError, corosync_conf_parser.CorosyncConfParserException):
        # corosync.conf not present or not valid => no qdevice specified
        return False


# Restore default behavior before starting subprocesses
def subprocess_setup():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


def touch_cib_file(cib_filename):
    if not os.path.isfile(cib_filename):
        try:
            write_empty_cib(cib_filename)
        except EnvironmentError as e:
            err(
                "Unable to write to file: '{0}': '{1}'".format(
                    cib_filename, str(e)
                )
            )


# Run command, with environment and return (output, retval)
# DEPRECATED, please use lib.external.CommandRunner via utils.cmd_runner()
def run(
    args,
    ignore_stderr=False,
    string_for_stdin=None,
    env_extend=None,
    binary_output=False,
):
    """
    Commandline options:
      * -f - CIB file (effective only for some pacemaker tools)
      * --debug
    """
    if not env_extend:
        env_extend = {}
    env_var = env_extend
    env_var.update(dict(os.environ))
    env_var["LC_ALL"] = "C"
    if usefile:
        env_var["CIB_file"] = filename
        touch_cib_file(filename)

    command = args[0]
    if command[0:3] == "crm" or command in [
        "cibadmin",
        "iso8601",
        "stonith_admin",
    ]:
        args[0] = os.path.join(settings.pacemaker_execs, command)
    elif command[0:8] == "corosync":
        args[0] = os.path.join(settings.corosync_execs, command)

    try:
        if "--debug" in pcs_options:
            print_to_stderr("Running: " + " ".join(args))
            if string_for_stdin:
                print_to_stderr(
                    f"--Debug Input Start--\n"
                    f"{string_for_stdin}\n"
                    f"--Debug Input End--"
                )

        # Some commands react differently if you give them anything via stdin
        if string_for_stdin is not None:
            stdin_pipe = subprocess.PIPE
        else:
            stdin_pipe = subprocess.DEVNULL

        # pylint: disable=subprocess-popen-preexec-fn, consider-using-with
        p = subprocess.Popen(
            args,
            stdin=stdin_pipe,
            stdout=subprocess.PIPE,
            stderr=(subprocess.PIPE if ignore_stderr else subprocess.STDOUT),
            preexec_fn=subprocess_setup,  # noqa: PLW1509
            close_fds=True,
            env=env_var,
            # decodes newlines and in python3 also converts bytes to str
            universal_newlines=(not binary_output),
        )
        output, dummy_stderror = p.communicate(string_for_stdin)
        retval = p.returncode
        if "--debug" in pcs_options:
            print_to_stderr(
                "Return Value: {retval}\n"
                "--Debug Output Start--\n"
                "{debug_output}\n"
                "--Debug Output End--".format(
                    retval=retval,
                    debug_output=output.rstrip(),
                )
            )
    except OSError as e:
        print_to_stderr(e.strerror)
        err("unable to locate command: " + args[0])

    return output, retval


def cmd_runner(cib_file_override=None):
    """
    Commandline options:
      * -f - CIB file
    """
    env_vars = {}
    if usefile:
        env_vars["CIB_file"] = filename
    if cib_file_override:
        env_vars["CIB_file"] = cib_file_override
    env_vars.update(os.environ)
    env_vars["LC_ALL"] = "C"
    return CommandRunner(
        logging.getLogger("pcs"), get_report_processor(), env_vars
    )


def run_pcsdcli(command, data=None):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP request, applicable for commands:
        * remove_known_hosts - only when running on cluster node (sync will
            be initiated)
        * auth
        * send_local_configs
    """
    if not data:
        data = {}
    env_var = {}
    if "--debug" in pcs_options:
        env_var["PCSD_DEBUG"] = "true"
    if "--request-timeout" in pcs_options:
        env_var["PCSD_NETWORK_TIMEOUT"] = str(pcs_options["--request-timeout"])
    else:
        env_var["PCSD_NETWORK_TIMEOUT"] = str(settings.default_request_timeout)
    pcsd_dir_path = settings.pcsd_exec_location
    pcsdcli_path = os.path.join(pcsd_dir_path, "pcsd-cli.rb")
    if settings.pcsd_gem_path is not None:
        env_var["GEM_HOME"] = settings.pcsd_gem_path
    stdout, dummy_stderr, retval = cmd_runner().run(
        [settings.ruby_exec, "-I" + pcsd_dir_path, pcsdcli_path, command],
        json.dumps(data),
        env_var,
    )
    try:
        output_json = json.loads(stdout)
        for key in ["status", "text", "data"]:
            if key not in output_json:
                output_json[key] = None

        output = "".join(output_json["log"])
        # check if some requests timed out, if so print message about it
        if "error: operation_timedout" in output:
            print_to_stderr("Error: Operation timed out")
        # check if there are any connection failures due to proxy in pcsd and
        # print warning if so
        proxy_msg = "Proxy is set in environment variables, try disabling it"
        if proxy_msg in output:
            reports_output.warn(proxy_msg)

    except ValueError:
        output_json = {
            "status": "bad_json_output",
            "text": stdout,
            "data": None,
        }
    return output_json, retval


def auth_hosts_token(host_dict):
    output, retval = run_pcsdcli("auth_with_token", dict(nodes=host_dict))
    if retval == 0:
        if output["status"] == "access_denied":
            err("Access denied")
        if output["status"] != "ok":
            err("Unable to communicate with pcsd")
    else:
        err("Unable to communicate with pcsd")


def auth_hosts(host_dict):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP request
    """
    output, retval = run_pcsdcli("auth", dict(nodes=host_dict))
    if retval == 0 and output["status"] == "access_denied":
        err("Access denied")
    if retval == 0 and output["status"] == "ok" and output["data"]:
        failed = False
        try:
            if not output["data"]["sync_successful"]:
                err(
                    "Some nodes had a newer known-hosts than the local node. "
                    + "Local node's known-hosts were updated. "
                    + "Please repeat the authentication if needed."
                )
            for node, result in output["data"]["auth_responses"].items():
                if result["status"] == "ok":
                    print_to_stderr(f"{node}: Authorized")
                elif result["status"] == "bad_password":
                    err(f"{node}: Username and/or password is incorrect", False)
                    failed = True
                elif result["status"] in ("noresponse", "error"):
                    err("Unable to communicate with {0}".format(node), False)
                    failed = True
                else:
                    err("Unexpected response from {0}".format(node), False)
                    failed = True
            if output["data"]["sync_nodes_err"]:
                err(
                    (
                        "Unable to synchronize and save known-hosts on nodes: "
                        + "{0}. Run 'pcs host auth {1}' to make sure the nodes "
                        + "are authorized."
                    ).format(
                        ", ".join(output["data"]["sync_nodes_err"]),
                        " ".join(output["data"]["sync_nodes_err"]),
                    )
                )
        except (ValueError, KeyError):
            err("Unable to communicate with pcsd")
        if failed:
            sys.exit(1)
        return
    err("Unable to communicate with pcsd")


def call_local_pcsd(argv, options, std_in=None):  # noqa: PLR0911
    """
    Commandline options:
      * --request-timeout - timeout of call to local pcsd
    """
    # pylint: disable=too-many-return-statements
    # some commands cannot be run under a non-root account
    # so we pass those commands to locally running pcsd to execute them
    # returns [list_of_errors, exit_code, stdout, stderr]
    data = {
        "command": json.dumps(argv),
        "options": json.dumps(options),
    }
    if std_in:
        data["stdin"] = std_in
    data_send = urlencode(data)
    code, output = sendHTTPRequest(
        "localhost", "run_pcs", data_send, False, False
    )

    if code == 3:  # not authenticated
        return [
            [
                "Unable to authenticate against the local pcsd. Run the same "
                "command as root or authenticate yourself to the local pcsd "
                "using command 'pcs client local-auth'"
            ],
            1,
            "",
            "",
        ]
    if code != 0:  # http error connecting to localhost
        return [[output], 1, "", ""]

    try:
        output_json = json.loads(output)
        for key in ["status", "data"]:
            if key not in output_json:
                output_json[key] = None
    except ValueError:
        return [["Unable to communicate with pcsd"], 1, "", ""]
    if output_json["status"] == "bad_command":
        return [["Command not allowed"], 1, "", ""]
    if output_json["status"] == "access_denied":
        return [["Access denied"], 1, "", ""]
    if output_json["status"] != "ok" or not output_json["data"]:
        return [["Unable to communicate with pcsd"], 1, "", ""]
    try:
        exitcode = output_json["data"]["code"]
        std_out = output_json["data"]["stdout"]
        std_err = output_json["data"]["stderr"]
        return [[], exitcode, std_out, std_err]
    except KeyError:
        return [["Unable to communicate with pcsd"], 1, "", ""]


def map_for_error_list(callab, iterab):
    """
    Commandline options: no options
    NOTE: callback 'callab' may use some options
    """
    error_list = []
    for item in iterab:
        retval, error = callab(item)
        if retval != 0:
            error_list.append(error)
    return error_list


def run_parallel(worker_list, wait_seconds=1):
    """
    Commandline options: no options
    """
    thread_list = set()
    for worker in worker_list:
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread_list.add(thread)

    while thread_list:
        thread = thread_list.pop()
        thread.join(wait_seconds)
        if thread.is_alive():
            thread_list.add(thread)


def create_task(report, action, node, *args, **kwargs):
    """
    Commandline options: no options
    """

    def worker():
        returncode, output = action(node, *args, **kwargs)
        report(node, returncode, output)

    return worker


def create_task_list(report, action, node_list, *args, **kwargs):
    """
    Commandline options: no options
    """
    return [
        create_task(report, action, node, *args, **kwargs) for node in node_list
    ]


def parallel_for_nodes(action, node_list, *args, **kwargs):
    """
    Commandline options: no options
    NOTE: callback 'action' may use some cmd options
    """
    node_errors = {}

    def report(node, returncode, output):
        message = "{0}: {1}".format(node, output.strip())
        print_to_stderr(message)
        if returncode != 0:
            node_errors[node] = message

    run_parallel(create_task_list(report, action, node_list, *args, **kwargs))
    return node_errors


def get_group_children(group_id):
    """
    Commandline options: no options
    """
    return dom_get_group_children(get_cib_dom(), group_id)


def dom_get_group_children(dom, group_id):
    groups = dom.getElementsByTagName("group")
    for g in groups:
        if g.getAttribute("id") == group_id:
            return [
                child_el.getAttribute("id")
                for child_el in get_group_children_el_from_el(g)
            ]
    return []


def get_group_children_el_from_el(group_el):
    child_resources = []
    for child in group_el.childNodes:
        if child.nodeType != xml.dom.minidom.Node.ELEMENT_NODE:
            continue
        if child.tagName == "primitive":
            child_resources.append(child)
    return child_resources


def dom_get_clone_ms_resource(dom, clone_ms_id):
    """
    Commandline options: no options
    """
    clone_ms = dom_get_clone(dom, clone_ms_id) or dom_get_master(
        dom, clone_ms_id
    )
    if clone_ms:
        return dom_elem_get_clone_ms_resource(clone_ms)
    return None


def dom_elem_get_clone_ms_resource(clone_ms):
    """
    Commandline options: no options
    """
    for child in clone_ms.childNodes:
        if (
            child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
            and child.tagName in ["group", "primitive"]
        ):
            return child
    return None


def dom_get_resource_clone_ms_parent(dom, resource_id):
    """
    Commandline options: no options
    """
    resource = dom_get_resource(dom, resource_id) or dom_get_group(
        dom, resource_id
    )
    if resource:
        return dom_get_parent_by_tag_names(resource, ["clone", "master"])
    return None


def dom_get_resource_bundle_parent(dom, resource_id):
    """
    Commandline options: no options
    """
    resource = dom_get_resource(dom, resource_id)
    if resource:
        return dom_get_parent_by_tag_names(resource, ["bundle"])
    return None


def dom_get_master(dom, master_id):
    """
    Commandline options: no options
    """
    for master in dom.getElementsByTagName("master"):
        if master.getAttribute("id") == master_id:
            return master
    return None


def dom_get_clone(dom, clone_id):
    """
    Commandline options: no options
    """
    for clone in dom.getElementsByTagName("clone"):
        if clone.getAttribute("id") == clone_id:
            return clone
    return None


def dom_get_group(dom, group_id):
    """
    Commandline options: no options
    """
    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_id:
            return group
    return None


def dom_get_bundle(dom, bundle_id):
    """
    Commandline options: no options
    """
    for bundle in dom.getElementsByTagName("bundle"):
        if bundle.getAttribute("id") == bundle_id:
            return bundle
    return None


def dom_get_resource_bundle(bundle_el):
    """
    Commandline options: no options
    """
    for child in bundle_el.childNodes:
        if (
            child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
            and child.tagName == "primitive"
        ):
            return child
    return None


def dom_get_group_clone(dom, group_id):
    """
    Commandline options: no options
    """
    for clone in dom.getElementsByTagName("clone"):
        group = dom_get_group(clone, group_id)
        if group:
            return group
    return None


def dom_get_group_masterslave(dom, group_id):
    """
    Commandline options: no options
    """
    for master in dom.getElementsByTagName("master"):
        group = dom_get_group(master, group_id)
        if group:
            return group
    return None


def dom_get_resource(dom, resource_id):
    """
    Commandline options: no options
    """
    for primitive in dom.getElementsByTagName("primitive"):
        if primitive.getAttribute("id") == resource_id:
            return primitive
    return None


def dom_get_any_resource(dom, resource_id):
    """
    Commandline options: no options
    """
    return (
        dom_get_resource(dom, resource_id)
        or dom_get_group(dom, resource_id)
        or dom_get_clone(dom, resource_id)
        or dom_get_master(dom, resource_id)
    )


def dom_get_resource_clone(dom, resource_id):
    """
    Commandline options: no options
    """
    for clone in dom.getElementsByTagName("clone"):
        resource = dom_get_resource(clone, resource_id)
        if resource:
            return resource
    return None


def dom_get_resource_masterslave(dom, resource_id):
    """
    Commandline options: no options
    """
    for master in dom.getElementsByTagName("master"):
        resource = dom_get_resource(master, resource_id)
        if resource:
            return resource
    return None


# returns tuple (is_valid, error_message, correct_resource_id_if_exists)
# there is a duplicate code in pcs/lib/cib/constraint/constraint.py
# please use function in pcs/lib/cib/constraint/constraint.py
def validate_constraint_resource(dom, resource_id):  # noqa: PLR0911
    """
    Commandline options:
      * --force - allow constraint on any resource
    """
    # pylint: disable=too-many-return-statements
    resource_el = (
        dom_get_clone(dom, resource_id)
        or dom_get_master(dom, resource_id)
        or dom_get_bundle(dom, resource_id)
    )
    if resource_el:
        # clones, masters and bundles are always valid
        return True, "", resource_id

    resource_el = dom_get_resource(dom, resource_id) or dom_get_group(
        dom, resource_id
    )
    if not resource_el:
        return False, "Resource '%s' does not exist" % resource_id, None

    clone_el = dom_get_resource_clone_ms_parent(
        dom, resource_id
    ) or dom_get_resource_bundle_parent(dom, resource_id)
    if not clone_el:
        # a primitive and a group is valid if not in a clone nor a master nor a
        # bundle
        return True, "", resource_id

    if "--force" in pcs_options:
        return True, "", clone_el.getAttribute("id")

    if clone_el.tagName in ["clone", "master"]:
        return (
            False,
            "%s is a clone resource, you should use the clone id: %s "
            "when adding constraints. Use --force to override."
            % (resource_id, clone_el.getAttribute("id")),
            clone_el.getAttribute("id"),
        )
    if clone_el.tagName == "bundle":
        return (
            False,
            "%s is a bundle resource, you should use the bundle id: %s "
            "when adding constraints. Use --force to override."
            % (resource_id, clone_el.getAttribute("id")),
            clone_el.getAttribute("id"),
        )
    return True, "", resource_id


def validate_resources_not_in_same_group(dom, resource_id1, resource_id2):
    resource_el1 = dom_get_resource(dom, resource_id1)
    resource_el2 = dom_get_resource(dom, resource_id2)
    if not resource_el1 or not resource_el2:
        # Only primitive resources can be in a group. If at least one of the
        # resources is not a primitive (resource_el is None), then the
        # resources are not in the same group.
        return True
    group1 = dom_get_parent_by_tag_names(resource_el1, ["group"])
    group2 = dom_get_parent_by_tag_names(resource_el2, ["group"])
    if not group1 or not group2:
        return True
    return group1 != group2


def dom_get_resource_remote_node_name(dom_resource):
    """
    Commandline options: no options
    """
    if dom_resource.tagName != "primitive":
        return None
    if (
        dom_resource.getAttribute("class").lower() == "ocf"
        and dom_resource.getAttribute("provider").lower() == "pacemaker"
        and dom_resource.getAttribute("type").lower() == "remote"
    ):
        return dom_resource.getAttribute("id")
    return dom_get_meta_attr_value(dom_resource, "remote-node")


def dom_get_meta_attr_value(dom_resource, meta_name):
    """
    Commandline options: no options
    """
    for meta in dom_resource.getElementsByTagName("meta_attributes"):
        for nvpair in meta.getElementsByTagName("nvpair"):
            if nvpair.getAttribute("name") == meta_name:
                return nvpair.getAttribute("value")
    return None


def dom_get_node(dom, node_name):
    """
    Commandline options: no options
    """
    for e in dom.getElementsByTagName("node"):
        if e.hasAttribute("uname") and e.getAttribute("uname") == node_name:
            return e
    return None


def _dom_get_children_by_tag_name(dom_el, tag_name):
    """
    Commandline options: no options
    """
    return [
        node
        for node in dom_el.childNodes
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
        and node.tagName == tag_name
    ]


def dom_get_parent_by_tag_names(dom_el, tag_names):
    """
    Commandline options: no options
    """
    parent = dom_el.parentNode
    while parent:
        if not isinstance(parent, xml.dom.minidom.Element):
            return None
        if parent.tagName in tag_names:
            return parent
        parent = parent.parentNode
    return None


# moved to pcs.lib.pacemaker.state
def get_resource_for_running_check(cluster_state, resource_id, stopped=False):
    """
    Commandline options: no options
    """

    def _isnum(value):
        return all(char in list("0123456789") for char in value)

    # pylint: disable=too-many-nested-blocks
    for clone in cluster_state.getElementsByTagName("clone"):
        if clone.getAttribute("id") == resource_id:
            for child in clone.childNodes:
                if child.nodeType == child.ELEMENT_NODE and child.tagName in [
                    "resource",
                    "group",
                ]:
                    resource_id = child.getAttribute("id")
                    # in a clone, a resource can have an id of '<name>:N'
                    if ":" in resource_id:
                        parts = resource_id.rsplit(":", 1)
                        if _isnum(parts[1]):
                            resource_id = parts[0]
                    break
    for group in cluster_state.getElementsByTagName("group"):
        # If resource is a clone it can have an id of '<resource name>:N'
        if group.getAttribute("id") == resource_id or group.getAttribute(
            "id"
        ).startswith(resource_id + ":"):
            if stopped:
                elem = group.getElementsByTagName("resource")[0]
            else:
                elem = group.getElementsByTagName("resource")[-1]
            resource_id = elem.getAttribute("id")
    return resource_id


# moved to pcs.lib.pacemaker.state
# see pcs.lib.commands.resource for usage
def resource_running_on(resource, passed_state=None, stopped=False):
    """
    Commandline options:
      * -f - has effect but doesn't make sense to check state of resource
    """
    # pylint: disable=too-many-locals
    nodes_started = []
    nodes_promoted = []
    nodes_unpromoted = []
    state = passed_state if passed_state else getClusterState()
    resource_original = resource
    resource = get_resource_for_running_check(state, resource, stopped)
    resources = state.getElementsByTagName("resource")
    for res in resources:
        # If resource is a clone it can have an id of '<resource name>:N'
        # If resource is a clone it will be found more than once - cannot break
        if (
            res.getAttribute("id") == resource
            or res.getAttribute("id").startswith(resource + ":")
        ) and res.getAttribute("failed") != "true":
            for node in res.getElementsByTagName("node"):
                node_name = node.getAttribute("name")
                role = res.getAttribute("role")
                if role == const.PCMK_ROLE_STARTED:
                    nodes_started.append(node_name)
                elif role in (
                    const.PCMK_ROLE_PROMOTED,
                    const.PCMK_ROLE_PROMOTED_LEGACY,
                ):
                    nodes_promoted.append(node_name)
                elif role in (
                    const.PCMK_ROLE_UNPROMOTED,
                    const.PCMK_ROLE_UNPROMOTED_LEGACY,
                ):
                    nodes_unpromoted.append(node_name)
    if not nodes_started and not nodes_promoted and not nodes_unpromoted:
        message = "Resource '%s' is not running on any node" % resource_original
    else:
        message_parts = []
        for alist, label in (
            (nodes_started, "running"),
            (nodes_promoted, str(const.PCMK_ROLE_PROMOTED).lower()),
            (nodes_unpromoted, str(const.PCMK_ROLE_UNPROMOTED).lower()),
        ):
            if alist:
                alist.sort()
                message_parts.append(
                    "%s on node%s %s"
                    % (label, "s" if len(alist) > 1 else "", ", ".join(alist))
                )
        message = "Resource '%s' is %s." % (
            resource_original,
            "; ".join(message_parts),
        )
    return {
        "message": message,
        "is_running": bool(nodes_started or nodes_promoted or nodes_unpromoted),
    }


def validate_wait_get_timeout(need_cib_support=True):
    """
    Commandline options:
      * --wait
      * -f - to check if -f and --wait are not used simultaneously
    """
    if need_cib_support and usefile:
        err("Cannot use '-f' together with '--wait'")
    wait_timeout = pcs_options["--wait"]
    if wait_timeout is None:
        return wait_timeout
    wait_timeout = timeout_to_seconds(wait_timeout)
    if wait_timeout is None:
        err(
            "%s is not a valid number of seconds to wait"
            % pcs_options["--wait"]
        )
    return wait_timeout


# Return matches from the CIB with the xpath_query
def get_cib_xpath(xpath_query):
    """
    Commandline options:
      * -f - CIB file
    """
    args = ["cibadmin", "-Q", "--xpath", xpath_query]
    output, retval = run(args)
    if retval != 0:
        return ""
    return output


def get_cib(scope=None):
    """
    Commandline options:
      * -f - CIB file
    """
    command = ["cibadmin", "-l", "-Q"]
    if scope:
        command.append("--scope=%s" % scope)
    output, retval = run(command)
    if retval != 0:
        if retval == 105 and scope:
            err("unable to get cib, scope '%s' not present in cib" % scope)
        else:
            err("unable to get cib")
    return output


def get_cib_dom(cib_xml=None):
    """
    Commandline options:
      * -f - CIB file
    """
    if cib_xml is None:
        cib_xml = get_cib()
    try:
        return parseString(cib_xml)
    except xml.parsers.expat.ExpatError:
        return err("unable to get cib")


def get_cib_etree(cib_xml=None):
    """
    Commandline options:
      * -f - CIB file
    """
    if cib_xml is None:
        cib_xml = get_cib()
    try:
        return ET.fromstring(cib_xml)
    except xml.etree.ElementTree.ParseError:
        return err("unable to get cib")


def is_etree(var):
    """
    Commandline options: no options
    """
    return var.__class__ == xml.etree.ElementTree.Element


# Replace only configuration section of cib with dom passed
def replace_cib_configuration(dom):
    """
    Commandline options:
      * -f - CIB file
    """
    if is_etree(dom):
        # etree returns string in bytes: b'xml'
        # python 3 removed .encode() from byte strings
        # run(...) calls subprocess.Popen.communicate which calls encode...
        # so there is bytes to str conversion
        new_dom = ET.tostring(dom).decode()
    elif hasattr(dom, "toxml"):
        new_dom = dom.toxml()
    else:
        new_dom = dom
    cmd = ["cibadmin", "--replace", "-V", "--xml-pipe", "-o", "configuration"]
    output, retval = run(cmd, False, new_dom)
    if retval != 0:
        err("Unable to update cib\n" + output)


def is_valid_cib_scope(scope):
    """
    Commandline options: no options
    """
    return scope in [
        "acls",
        "alerts",
        "configuration",
        "constraints",
        "crm_config",
        "fencing-topology",
        "nodes",
        "op_defaults",
        "resources",
        "rsc_defaults",
        "tags",
    ]


# Checks to see if id exists in the xml dom passed
# DEPRECATED use lxml version available in pcs.lib.cib.tools
def does_id_exist(dom, check_id):  # noqa: PLR0912
    """
    Commandline options: no options
    """
    # do not search in /cib/status, it may contain references to previously
    # existing and deleted resources and thus preventing creating them again
    if is_etree(dom):
        for elem in dom.findall(
            str('(/cib/*[name()!="status"]|/*[name()!="cib"])/*')
        ):
            if elem.get("id") == check_id:
                return True
    else:
        document = (
            dom
            if isinstance(dom, xml.dom.minidom.Document)
            else dom.ownerDocument
        )
        cib_found = False
        for cib in _dom_get_children_by_tag_name(document, "cib"):
            cib_found = True
            for section in cib.childNodes:
                if section.nodeType != xml.dom.minidom.Node.ELEMENT_NODE:
                    continue
                if section.tagName == "status":
                    continue
                for elem in section.getElementsByTagName("*"):
                    if elem.getAttribute("id") == check_id:
                        return True
        if not cib_found:
            for elem in document.getElementsByTagName("*"):
                if elem.getAttribute("id") == check_id:
                    return True
    return False


# Returns check_id if it doesn't exist in the dom, otherwise it adds an integer
# to the end of the id and increments it until a unique id is found
# DEPRECATED use lxml version available in pcs.lib.cib.tools
def find_unique_id(dom, check_id):
    """
    Commandline options: no options
    """
    counter = 1
    temp_id = check_id
    while does_id_exist(dom, temp_id):
        temp_id = check_id + "-" + str(counter)
        counter += 1
    return temp_id


# Checks to see if the specified operation already exists in passed set of
# operations
# pacemaker differentiates between operations only by name and interval
def operation_exists(operations_el, op_el):
    """
    Commandline options: no options
    """
    op_name = op_el.getAttribute("name")
    op_interval = timeout_to_seconds_legacy(op_el.getAttribute("interval"))
    return [
        op
        for op in operations_el.getElementsByTagName("op")
        if (
            op.getAttribute("name") == op_name
            and timeout_to_seconds_legacy(op.getAttribute("interval"))
            == op_interval
        )
    ]


def operation_exists_by_name(operations_el, op_el):
    """
    Commandline options: no options
    """

    def get_role(_el, new_roles_supported):
        return common_pacemaker.role.get_value_for_cib(
            _el.getAttribute("role") or const.PCMK_ROLE_STARTED,
            new_roles_supported,
        )

    new_roles_supported = isCibVersionSatisfied(
        operations_el, const.PCMK_NEW_ROLES_CIB_VERSION
    )
    existing = []
    op_name = op_el.getAttribute("name")
    op_role = get_role(op_el, new_roles_supported)
    ocf_check_level = None
    if op_name == "monitor":
        ocf_check_level = get_operation_ocf_check_level(op_el)

    for op in operations_el.getElementsByTagName("op"):
        if op.getAttribute("name") == op_name:
            if (
                op_name != "monitor"
                or get_role(op, new_roles_supported) == op_role
                and ocf_check_level == get_operation_ocf_check_level(op)
            ):
                existing.append(op)
    return existing


def get_operation_ocf_check_level(operation_el):
    """
    Commandline options: no options
    """
    for attr_el in operation_el.getElementsByTagName("instance_attributes"):
        for nvpair_el in attr_el.getElementsByTagName("nvpair"):
            if (
                nvpair_el.getAttribute("name")
                == OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME
            ):
                return nvpair_el.getAttribute("value")
    return None


def get_node_attributes(filter_node=None, filter_attr=None):
    """
    Commandline options:
      * -f - CIB file
    """
    node_config = get_cib_xpath("//nodes")
    if node_config == "":
        err("unable to get crm_config, is pacemaker running?")
    dom = parseString(node_config).documentElement
    nas = {}
    for node in dom.getElementsByTagName("node"):
        nodename = node.getAttribute("uname")
        if filter_node is not None and nodename != filter_node:
            continue
        for attributes in node.getElementsByTagName("instance_attributes"):
            for nvp in attributes.getElementsByTagName("nvpair"):
                attr_name = nvp.getAttribute("name")
                if filter_attr is not None and attr_name != filter_attr:
                    continue
                if nodename not in nas:
                    nas[nodename] = {}
                nas[nodename][attr_name] = nvp.getAttribute("value")
            # Use just first element of attributes. We don't support
            # attributes with rules just yet.
            break
    return nas


def set_node_attribute(prop, value, node):
    """
    Commandline options:
      * -f - CIB file
      * --force - no error if attribute to delete doesn't exist
    """
    if value == "":
        o, r = run(
            [
                "crm_attribute",
                "-t",
                "nodes",
                "--node",
                node,
                "--name",
                prop,
                "--query",
            ]
        )
        if r != 0 and "--force" not in pcs_options:
            err(
                "attribute: '%s' doesn't exist for node: '%s'" % (prop, node),
                False,
            )
            # This return code is used by pcsd
            sys.exit(2)
        o, r = run(
            [
                "crm_attribute",
                "-t",
                "nodes",
                "--node",
                node,
                "--name",
                prop,
                "--delete",
            ]
        )
    else:
        o, r = run(
            [
                "crm_attribute",
                "-t",
                "nodes",
                "--node",
                node,
                "--name",
                prop,
                "--update",
                value,
            ]
        )

    if r != 0:
        err("unable to set attribute %s\n%s" % (prop, o))


def getTerminalSize(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.

    :param fd: file descriptor (default: 1=stdout)

    Commandline options: no options
    """
    try:
        # pylint: disable=import-outside-toplevel
        import fcntl
        import struct
        import termios

        hw = struct.unpack(
            str("hh"), fcntl.ioctl(fd, termios.TIOCGWINSZ, "1234")
        )
    except OSError:
        try:
            hw = (os.environ["LINES"], os.environ["COLUMNS"])
        except KeyError:
            hw = (25, 80)
    return hw


def get_terminal_input(message=None):
    """
    Commandline options: no options
    """
    if message:
        sys.stdout.write(message)
        sys.stdout.flush()
    try:
        return input("")
    except EOFError:
        return ""
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(1)


def _get_continue_confirmation_interactive(warning_text: str) -> bool:
    """
    Warns user and asks for permission to continue. Returns True if user wishes
    to continue, False otherwise.

    This function is mostly intended for prompting user to confirm destructive
    operations - that's why WARNING is in all caps here and user is asked to
    explicitly type 'yes' or 'y' to continue.

    warning_text -- describes action that we want the user to confirm
    """
    print(f"WARNING: {warning_text}")
    print("Type 'yes' or 'y' to proceed, anything else to cancel: ", end="")
    response = get_terminal_input()
    if response in ["yes", "y"]:
        return True
    print("Canceled")
    return False


def is_run_interactive() -> bool:
    """
    Return True if pcs is running in an interactive environment, False otherwise
    """
    return (
        sys.stdin is not None
        and sys.stdout is not None
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )


def get_continue_confirmation(
    warning_text: str, yes: bool, force: bool
) -> bool:
    """
    Either asks user to confirm continuation interactively or use --yes to
    override when running from a script. Returns True if user wants to continue.
    Returns False if user cancels the action. If a non-interactive environment
    is detected, pcs exits with an error formed from warning_text.

    warning_text -- describes action that we want the user to confirm
    yes -- was --yes flag provided?
    force -- was --force flag provided? (deprecated)
    """
    if force and not yes:
        # Force may be specified for overriding library errors. We don't want
        # to report an issue in that case.
        # deprecated in the first pcs-0.12 version
        reports_output.deprecation_warning(
            "Using --force to confirm this action is deprecated and might be "
            "removed in a future release, use --yes instead"
        )
    if yes or force:
        reports_output.warn(warning_text)
        return True
    if not is_run_interactive():
        err(f"{warning_text}, use --yes to override")
        return False
    return _get_continue_confirmation_interactive(warning_text)


def get_terminal_password(message="Password: "):
    """
    Commandline options: no options
    """
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            return getpass.getpass(message)
        except KeyboardInterrupt:
            print("Interrupted")
            sys.exit(1)
    else:
        return get_terminal_input(message)


# Returns an xml dom containing the current status of the cluster
# DEPRECATED, please use
# ClusterState(lib.pacemaker.live.get_cluster_status_dom()) instead
def getClusterState():
    """
    Commandline options:
      * -f - CIB file
    """
    xml_string, returncode = run(
        ["crm_mon", "--one-shot", "--output-as=xml", "--inactive"],
        ignore_stderr=True,
    )
    if returncode != 0:
        err("error running crm_mon, is pacemaker running?")
    return parseString(xml_string)


def write_empty_cib(cibfile):
    """
    Commandline options: no options
    """
    empty_xml = """
        <cib admin_epoch="0" epoch="1" num_updates="1" validate-with="pacemaker-3.1">
          <configuration>
            <crm_config/>
            <nodes/>
            <resources/>
            <constraints/>
          </configuration>
          <status/>
        </cib>
    """
    with open(cibfile, "w") as f:
        f.write(empty_xml)


# Test if 'var' is a score or option (contains an '=')
def is_score_or_opt(var):
    """
    Commandline options: no options
    """
    if is_score(var):
        return True
    return var.find("=") != -1


def is_score(var):
    """
    Commandline options: no options
    """
    return is_score_value(var)


def validate_xml_id(var: str, description: str = "id") -> Tuple[bool, str]:
    """
    Commandline options: no options
    """
    report_list: ReportItemList = []
    validate_id(var, description, report_list)
    if report_list:
        return False, report_list[0].message.message
    return True, ""


# deprecated, moved to pcs.lib.pacemaker.live
def is_iso8601_date(var):
    """
    Commandline options: no options
    """
    # using pacemaker tool to check if a value is a valid pacemaker iso8601 date
    dummy_output, retVal = run(["iso8601", "-d", var])
    return retVal == 0


def err(errorText: str, exit_after_error: bool = True) -> None:
    retval = reports_output.error(errorText)
    if exit_after_error:
        raise retval


@lru_cache(typed=True)
def get_service_manager() -> ServiceManagerInterface:
    return _get_service_manager(cmd_runner(), get_report_processor())


def enableServices():
    """
    Commandline options: no options
    """
    # do NOT handle SBD in here, it is started by pacemaker not systemd or init
    service_list = ["corosync", "pacemaker"]
    if need_to_handle_qdevice_service():
        service_list.append("corosync-qdevice")
    service_manager = get_service_manager()

    report_item_list = []
    for service in service_list:
        try:
            service_manager.enable(service)
        except ManageServiceError as e:
            report_item_list.append(service_exception_to_report(e))
    if report_item_list:
        raise LibraryError(*report_item_list)


def disableServices():
    """
    Commandline options: no options
    """
    # do NOT handle SBD in here, it is started by pacemaker not systemd or init
    service_list = ["corosync", "pacemaker"]
    if need_to_handle_qdevice_service():
        service_list.append("corosync-qdevice")
    service_manager = get_service_manager()

    report_item_list = []
    for service in service_list:
        try:
            service_manager.disable(service)
        except ManageServiceError as e:
            report_item_list.append(service_exception_to_report(e))
    if report_item_list:
        raise LibraryError(*report_item_list)


def start_service(service):
    """
    Commandline options: no options
    """
    service_manager = get_service_manager()

    try:
        service_manager.start(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e


def stop_service(service):
    """
    Commandline options: no options
    """
    service_manager = get_service_manager()

    try:
        service_manager.stop(service)
    except ManageServiceError as e:
        raise LibraryError(service_exception_to_report(e)) from e


def write_file(path, data, permissions=0o644, binary=False):
    """
    Commandline options:
      * --force - overwrite a file if it already exists
    """
    if os.path.exists(path):
        if "--force" not in pcs_options:
            return False, "'%s' already exists, use --force to overwrite" % path
        try:
            os.remove(path)
        except EnvironmentError as e:
            return False, "unable to remove '%s': %s" % (path, e)
    mode = "wb" if binary else "w"
    try:
        with os.fdopen(
            os.open(path, os.O_WRONLY | os.O_CREAT, permissions), mode
        ) as outfile:
            outfile.write(data)
    except EnvironmentError as e:
        return False, "unable to write to '%s': %s" % (path, e)
    return True, ""


def tar_add_file_data(  # noqa: PLR0913
    tarball,
    data,
    name,
    *,
    mode=None,
    uid=None,
    gid=None,
    uname=None,
    gname=None,
    mtime=None,
):
    # pylint: disable=too-many-arguments
    """
    Commandline options: no options
    """
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.type = tarfile.REGTYPE
    info.mtime = int(time.time()) if mtime is None else mtime
    if mode is not None:
        info.mode = mode
    if uid is not None:
        info.uid = uid
    if gid is not None:
        info.gid = gid
    if uname is not None:
        info.uname = uname
    if gname is not None:
        info.gname = gname
    data_io = BytesIO(data)
    tarball.addfile(info, data_io)
    data_io.close()


# DEPRECATED, please use pcs.lib.pacemaker.live.simulate_cib
def simulate_cib(cib_dom):
    """
    Commandline options: no options
    """
    try:
        with (
            tempfile.NamedTemporaryFile(
                mode="w+", suffix=".pcs"
            ) as new_cib_file,
            tempfile.NamedTemporaryFile(
                mode="w+", suffix=".pcs"
            ) as transitions_file,
        ):
            output, retval = run(
                [
                    "crm_simulate",
                    "--simulate",
                    "--save-output",
                    new_cib_file.name,
                    "--save-graph",
                    transitions_file.name,
                    "--xml-pipe",
                ],
                string_for_stdin=cib_dom.toxml(),
            )
            if retval != 0:
                return err("Unable to run crm_simulate:\n%s" % output)
            new_cib_file.seek(0)
            transitions_file.seek(0)
            return (
                output,
                parseString(transitions_file.read()),
                parseString(new_cib_file.read()),
            )
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        return err("Unable to run crm_simulate:\n%s" % e)
    except xml.etree.ElementTree.ParseError as e:
        return err("Unable to run crm_simulate:\n%s" % e)


# DEPRECATED
# please use pcs.lib.pacemaker.simulate.get_operations_from_transitions
def get_operations_from_transitions(transitions_dom):
    """
    Commandline options: no options
    """
    operation_list = []
    watched_operations = (
        "start",
        "stop",
        "promote",
        "demote",
        "migrate_from",
        "migrate_to",
    )
    for rsc_op in transitions_dom.getElementsByTagName("rsc_op"):
        primitives = rsc_op.getElementsByTagName("primitive")
        if not primitives:
            continue
        if rsc_op.getAttribute("operation").lower() not in watched_operations:
            continue
        for prim in primitives:
            prim_id = prim.getAttribute("id")
            operation_list.append(
                (
                    int(rsc_op.getAttribute("id")),
                    {
                        "id": prim_id,
                        "long_id": prim.getAttribute("long-id") or prim_id,
                        "operation": rsc_op.getAttribute("operation").lower(),
                        "on_node": rsc_op.getAttribute("on_node"),
                    },
                )
            )
    operation_list.sort(key=lambda x: x[0])
    return [op[1] for op in operation_list]


def get_resources_location_from_operations(cib_dom, resources_operations):
    """
    Commandline options:
      * --force - allow constraints on any resource, may not have any effect as
        an invalid constraint is ignored anyway
    """
    locations = {}
    for res_op in resources_operations:
        operation = res_op["operation"]
        if operation not in ("start", "promote", "migrate_from"):
            continue
        long_id = res_op["long_id"]
        if long_id not in locations:
            # Move clone instances as if they were non-cloned resources, it
            # really works with current pacemaker (1.1.13-6). Otherwise there
            # is probably no way to move them other then setting their
            # stickiness to 0.
            res_id = res_op["id"]
            if ":" in res_id:
                res_id = res_id.split(":")[0]
            id_for_constraint = validate_constraint_resource(cib_dom, res_id)[2]
            if not id_for_constraint:
                continue
            locations[long_id] = {
                "id": res_op["id"],
                "long_id": long_id,
                "id_for_constraint": id_for_constraint,
            }
        if operation in ("start", "migrate_from"):
            locations[long_id]["start_on_node"] = res_op["on_node"]
        if operation == "promote":
            locations[long_id]["promote_on_node"] = res_op["on_node"]
    return {
        key: val
        for key, val in locations.items()
        if "start_on_node" in val or "promote_on_node" in val
    }


def get_remote_quorumtool_output(node):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    return sendHTTPRequest(node, "remote/get_quorum_info", None, False, False)


# return True if quorumtool_output is a string returned when the node is off
def is_node_offline_by_quorumtool_output(quorum_info):
    """
    Commandline options: no options
    """
    return quorum_info.strip() == "Cannot initialize CMAP service"


def dom_prepare_child_element(dom_element, tag_name, id_candidate):
    """
    Commandline options: no options
    """
    child_elements = [
        child
        for child in dom_element.childNodes
        if child.nodeType == child.ELEMENT_NODE and child.tagName == tag_name
    ]

    if not child_elements:
        dom = dom_element.ownerDocument
        child_element = dom.createElement(tag_name)
        child_element.setAttribute("id", find_unique_id(dom, id_candidate))
        dom_element.appendChild(child_element)
    else:
        child_element = child_elements[0]
    return child_element


def dom_update_nvset(dom_element, nvpair_tuples, tag_name, id_candidate):
    """
    Commandline options: no options
    """
    # Already ported to pcs.libcib.nvpair

    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514
    if not nvpair_tuples:
        return

    only_removing = True
    for _, value in nvpair_tuples:
        if value != "":
            only_removing = False
            break

    # Do not use dom.getElementsByTagName, that would get elements we do not
    # want to. For example if dom_element is a clone, we would get the clones's
    # as well as clone's primitive's attributes.
    nvset_element_list = _dom_get_children_by_tag_name(dom_element, tag_name)

    # Do not create new nvset if we are only removing values from it.
    if not nvset_element_list and only_removing:
        return

    if not nvset_element_list:
        dom = dom_element.ownerDocument
        nvset_element = dom.createElement(tag_name)
        nvset_element.setAttribute("id", find_unique_id(dom, id_candidate))
        dom_element.appendChild(nvset_element)
    else:
        nvset_element = nvset_element_list[0]

    for name, value in nvpair_tuples:
        dom_update_nv_pair(
            nvset_element, name, value, nvset_element.getAttribute("id") + "-"
        )


def dom_update_nv_pair(dom_element, name, value, id_prefix=""):
    """
    Commandline options: no options
    """
    # Do not ever remove the nvset element, even if it is empty. There may be
    # ACLs set in pacemaker which allow "write" for nvpairs (adding, changing
    # and removing) but not nvsets. In such a case, removing the nvset would
    # cause the whole change to be rejected by pacemaker with a "permission
    # denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514

    dom = dom_element.ownerDocument
    element_found = False
    for el in dom_element.getElementsByTagName("nvpair"):
        if el.getAttribute("name") == name:
            element_found = True
            if value == "":
                dom_element.removeChild(el)
            else:
                el.setAttribute("value", value)
            break
    if not element_found and value != "":
        el = dom.createElement("nvpair")
        el.setAttribute("id", id_prefix + name)
        el.setAttribute("name", name)
        el.setAttribute("value", value)
        dom_element.appendChild(el)
    return dom_element


# Passed an array of strings ["a=b","c=d"], return array of tuples
# [("a","b"),("c","d")]
def convert_args_to_tuples(ra_values):
    """
    Commandline options: no options
    """
    ret = []
    for ra_val in ra_values:
        if ra_val.count("=") != 0:
            split_val = ra_val.split("=", 1)
            ret.append((split_val[0], split_val[1]))
    return ret


def is_int(val):
    try:
        int(val)
        return True
    except ValueError:
        return False


def dom_update_utilization(dom_element, attributes, id_prefix=""):
    """
    Commandline options: no options
    """
    attr_tuples = []
    for name, value in sorted(attributes.items()):
        if value != "" and not is_int(value):
            err(
                "Value of utilization attribute must be integer: "
                "'{0}={1}'".format(name, value)
            )
        attr_tuples.append((name, value))
    dom_update_nvset(
        dom_element,
        attr_tuples,
        "utilization",
        id_prefix + dom_element.getAttribute("id") + "-utilization",
    )


def dom_update_meta_attr(dom_element, attributes):
    """
    Commandline options: no options
    """
    dom_update_nvset(
        dom_element,
        attributes,
        "meta_attributes",
        dom_element.getAttribute("id") + "-meta_attributes",
    )


def dom_update_instance_attr(dom_element, attributes):
    """
    Commandline options: no options
    """
    dom_update_nvset(
        dom_element,
        attributes,
        "instance_attributes",
        dom_element.getAttribute("id") + "-instance_attributes",
    )


def get_utilization(element, filter_name=None):
    """
    Commandline options: no options
    """
    utilization = {}
    for e in element.getElementsByTagName("utilization"):
        for u in e.getElementsByTagName("nvpair"):
            name = u.getAttribute("name")
            if filter_name is not None and name != filter_name:
                continue
            utilization[name] = u.getAttribute("value")
        # Use just first element of utilization attributes. We don't support
        # utilization with rules just yet.
        break
    return utilization


def get_utilization_str(element, filter_name=None):
    """
    Commandline options: no options
    """
    output = []
    for name, value in sorted(get_utilization(element, filter_name).items()):
        output.append(name + "=" + value)
    return " ".join(output)


def get_lib_env() -> LibraryEnvironment:
    """
    Commandline options:
      * -f - CIB file
      * --corosync_conf - corosync.conf file
      * --request-timeout - timeout of HTTP requests
    """
    user = None
    groups = None
    if os.geteuid() == 0:
        for name in ("CIB_user", "CIB_user_groups"):
            if name in os.environ and os.environ[name].strip():
                value = os.environ[name].strip()
                if name == "CIB_user":
                    user = value
                else:
                    groups = value.split(" ")

    cib_data = None
    if usefile:
        cib_data = get_cib()

    corosync_conf_data = None
    if "--corosync_conf" in pcs_options:
        conf = pcs_options["--corosync_conf"]
        try:
            with open(conf) as corosync_conf_file:
                corosync_conf_data = corosync_conf_file.read()
        except IOError as e:
            err("Unable to read %s: %s" % (conf, e.strerror))

    return LibraryEnvironment(
        logging.getLogger("pcs"),
        get_report_processor(),
        user,
        groups,
        cib_data,
        corosync_conf_data,
        known_hosts_getter=read_known_hosts_file,
        request_timeout=pcs_options.get("--request-timeout"),
    )


def get_cib_user_groups():
    """
    Commandline options: no options
    """
    user = None
    groups = None
    if os.geteuid() == 0:
        for name in ("CIB_user", "CIB_user_groups"):
            if name in os.environ and os.environ[name].strip():
                value = os.environ[name].strip()
                if name == "CIB_user":
                    user = value
                else:
                    groups = value.split(" ")
    return user, groups


def get_cli_env():
    """
    Commandline options:
      * --debug
      * --request-timeout
    """
    env = Env()
    env.user, env.groups = get_cib_user_groups()
    env.known_hosts_getter = read_known_hosts_file
    env.report_processor = get_report_processor()
    env.request_timeout = pcs_options.get("--request-timeout")
    return env


def get_middleware_factory():
    """
    Commandline options:
      * --corosync_conf
      * --name
      * --booth-conf
      * --booth-key
      * -f
    """
    return middleware.create_middleware_factory(
        cib=middleware.cib(filename if usefile else None, touch_cib_file),
        corosync_conf_existing=middleware.corosync_conf_existing(
            pcs_options.get("--corosync_conf")
        ),
        booth_conf=pcs.cli.booth.env.middleware_config(
            pcs_options.get("--booth-conf"),
            pcs_options.get("--booth-key"),
        ),
    )


def get_library_wrapper():
    """
    Commandline options:
      * --debug
      * --request-timeout
      * --corosync_conf
      * --name
      * --booth-conf
      * --booth-key
      * -f
    NOTE: usage of options may depend on used middleware for particular command
    """
    return Library(get_cli_env(), get_middleware_factory())


def exit_on_cmdline_input_error(
    error: CmdLineInputError, main_name: str, usage_name: StringSequence
) -> None:
    if error and error.message:
        reports_output.error(error.message)
    if error and error.hint:
        print_to_stderr(f"Hint: {error.hint}")
    if not error or (not error.message or error.show_both_usage_and_message):
        usage.show(main_name, list(usage_name))
    sys.exit(1)


def get_report_processor() -> ReportProcessor:
    return ReportProcessorToConsole(debug="--debug" in pcs_options)


def get_user_and_pass():
    """
    Commandline options:
      * -u - username
      * -p - password
    """
    username = (
        pcs_options["-u"]
        if "-u" in pcs_options
        else get_terminal_input("Username: ")
    )
    password = (
        pcs_options["-p"] if "-p" in pcs_options else get_terminal_password()
    )
    return username, password


def get_input_modifiers() -> InputModifiers:
    return InputModifiers(pcs_options)


def get_token_from_file(file_name: str) -> str:
    try:
        with open(file_name, "rb") as file:
            max_size = settings.pcsd_token_max_bytes  # type: ignore
            value_bytes = file.read(max_size + 1)
            if len(value_bytes) > max_size:
                err(f"Maximal token size of {max_size} bytes exceeded")
            if not value_bytes:
                err(f"File '{file_name}' is empty")
            return base64.b64encode(value_bytes).decode("utf-8")
    except OSError as e:
        err(f"Unable to read file '{file_name}': {e}", exit_after_error=False)
        raise SystemExit(1) from e


def print_warning_if_utilization_attrs_has_no_effect(
    properties_facade: PropertyConfigurationFacade,
):
    PLACEMENT_STRATEGIES_USING_UTILIZATION_ATTRS = [
        "balanced",
        "minimal",
        "utilization",
    ]
    value = properties_facade.get_property_value_or_default(
        "placement-strategy"
    )
    if value not in PLACEMENT_STRATEGIES_USING_UTILIZATION_ATTRS:
        reports_output.warn(
            "Utilization attributes configuration has no effect until cluster "
            "property option 'placement-strategy' is set to one of the "
            "values: "
            f"{format_list(PLACEMENT_STRATEGIES_USING_UTILIZATION_ATTRS)}"
        )
