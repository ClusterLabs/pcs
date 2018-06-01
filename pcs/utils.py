import os
import sys
import subprocess
import xml.dom.minidom
from xml.dom.minidom import parseString, parse
import xml.etree.ElementTree as ET
import re
import json
import tempfile
import signal
import time
from io import BytesIO
import tarfile
import getpass
import base64
import threading
import logging
from functools import lru_cache

from pcs import settings, usage

from pcs.common import (
    pcs_pycurl as pycurl,
    report_codes,
)
from pcs.common.host import PcsKnownHost
from pcs.common.tools import join_multilines

from pcs.cli.common import (
    console_report,
    middleware,
)
from pcs.cli.common.env_cli import Env
from pcs.cli.common.lib_wrapper import Library
from pcs.cli.common.reports import (
    build_report_message,
    process_library_reports,
    LibraryReportProcessorToConsole as LibraryReportProcessorToConsole,
)
from pcs.cli.booth.command import DEFAULT_BOOTH_NAME
import pcs.cli.booth.env

from pcs.lib import reports, sbd
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError, ReportListAnalyzer
from pcs.lib.external import (
    CommandRunner,
    disable_service,
    DisableServiceError,
    enable_service,
    EnableServiceError,
    is_cman_cluster as lib_is_cman_cluster,
    is_proxy_set,
    is_service_enabled,
    is_service_running,
    is_systemctl,
    _service,
    _systemctl,
)
from pcs.lib.communication.nodes import (
    availability_checker_node,
    PrecheckNewNode,
)
from pcs.lib.communication.tools import run as run_com_cmd
import pcs.lib.corosync.config_parser as corosync_conf_parser
from pcs.lib.corosync.config_facade import ConfigFacade as corosync_conf_facade
from pcs.lib.pacemaker.live import has_wait_for_idle_support
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.values import(
    is_boolean,
    is_score as is_score_value,
    timeout_to_seconds as get_timeout_seconds,
    validate_id,
)

from urllib.parse import urlencode


# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options = {}


class UnknownPropertyException(Exception):
    pass

def getValidateWithVersion(dom):
    cib = dom.getElementsByTagName("cib")
    if len(cib) != 1:
        err("Bad cib")

    cib = cib[0]

    version = cib.getAttribute("validate-with")
    r = re.compile(r"pacemaker-(\d+)\.(\d+)\.?(\d+)?")
    m = r.match(version)
    major = int(m.group(1))
    minor = int(m.group(2))
    rev = int(m.group(3) or 0)
    return (major,minor,rev)

# Check the current pacemaker version in cib and upgrade it if necessary
# Returns False if not upgraded and True if upgraded
def checkAndUpgradeCIB(major,minor,rev):
    cmajor, cminor, crev = getValidateWithVersion(get_cib_dom())
    if cmajor > major or (cmajor == major and cminor > minor) or (cmajor == major and cminor == minor and crev >= rev):
        return False
    cluster_upgrade()
    return True

def cluster_upgrade():
    output, retval = run(["cibadmin", "--upgrade", "--force"])
    if retval != 0:
        err("unable to upgrade cluster: %s" % output)
    print("Cluster CIB has been upgraded to latest version")

def cluster_upgrade_to_version(required_version):
    checkAndUpgradeCIB(*required_version)
    dom = get_cib_dom()
    current_version = getValidateWithVersion(dom)
    if current_version < required_version:
        err(
            console_report.CODE_TO_MESSAGE_BUILDER_MAP[
                report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION
            ]({
                "required_version": ".".join([str(x) for x in required_version]),
                "current_version": ".".join([str(x) for x in current_version]),
            })
        )
    return dom

# Check status of node
def checkStatus(node):
    return sendHTTPRequest(node, 'remote/status', None, False, False)

# Check and see if we're authorized (faster than a status check)
def checkAuthorization(node):
    return sendHTTPRequest(node, 'remote/check_auth', None, False, False)

def get_uid_gid_file_name(uid, gid):
    return "pcs-uidgid-%s-%s" % (uid, gid)

# Reads in uid file and returns dict of values {'uid':'theuid', 'gid':'thegid'}
def read_uid_gid_file(filename):
    uidgid = {}
    with open(settings.corosync_uidgid_dir + filename, "r") as myfile:
        data = myfile.read().split('\n')
    in_uidgid = False
    for line in data:
        line = re.sub(r'#.*','', line)
        if not in_uidgid:
            if re.search(r'uidgid.*{',line):
                in_uidgid = True
            else:
                continue
        matches = re.search(r'uid:\s*(\S+)', line)
        if matches:
            uidgid["uid"] = matches.group(1)

        matches = re.search(r'gid:\s*(\S+)', line)
        if matches:
            uidgid["gid"] = matches.group(1)

    return uidgid

def write_uid_gid_file(uid,gid):
    orig_filename = get_uid_gid_file_name(uid,gid)
    filename = orig_filename
    counter = 0
    if len(find_uid_gid_files(uid,gid)) != 0:
        err("uidgid file with uid=%s and gid=%s already exists" % (uid,gid))

    while os.path.exists(settings.corosync_uidgid_dir + filename):
        counter = counter + 1
        filename = orig_filename + "-" + str(counter)

    data = "uidgid {\n  uid: %s\ngid: %s\n}\n" % (uid,gid)
    with open(settings.corosync_uidgid_dir + filename,'w') as uidgid_file:
        uidgid_file.write(data)

def find_uid_gid_files(uid,gid):
    if uid == "" and gid == "":
        return []

    found_files = []
    uid_gid_files = os.listdir(settings.corosync_uidgid_dir)
    for uidgid_file in uid_gid_files:
        uid_gid_dict = read_uid_gid_file(uidgid_file)
        if ("uid" in uid_gid_dict and uid == "") or ("uid" not in uid_gid_dict and uid != ""):
            continue
        if ("gid" in uid_gid_dict and gid == "") or ("gid" not in uid_gid_dict and gid != ""):
            continue
        if "uid" in uid_gid_dict and uid != uid_gid_dict["uid"]:
            continue
        if "gid" in uid_gid_dict and gid != uid_gid_dict["gid"]:
            continue

        found_files.append(uidgid_file)

    return found_files
# Removes all uid/gid files with the specified uid/gid, returns false if we
# couldn't find one
def remove_uid_gid_file(uid,gid):
    if uid == "" and gid == "":
        return False

    file_removed = False
    for uidgid_file in find_uid_gid_files(uid,gid):
        os.remove(settings.corosync_uidgid_dir + uidgid_file)
        file_removed = True

    return file_removed

def read_known_hosts_file():
    output, retval = run_pcsdcli("read_known_hosts")
    data = {}
    if (
        retval == 0
        and
        output['status'] == 'ok'
        and
        output['data']
        and
        output['data'].get('known_hosts')
    ):
        try:
            data = {
                name: PcsKnownHost.from_known_host_file_dict(name, host)
                for name, host in output['data']['known_hosts'].items()
            }
        except KeyError:
            print("Warning: Unable to parse known host file.")
    return data

def repeat_if_timeout(send_http_request_function, repeat_count=15):
    def repeater(node, *args, **kwargs):
        repeats_left = repeat_count
        while True:
            retval, output = send_http_request_function(node, *args, **kwargs)
            if (
                retval != 2 or "Operation timed out" not in output
                or
                repeats_left < 1
            ):
                # did not timed out OR repeat limit exceeded
                return retval, output
            repeats_left = repeats_left - 1
            if "--debug" in pcs_options:
                print("{0}: {1}, trying again...". format(node, output))
    return repeater

# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    return sendHTTPRequest(node, 'remote/get_corosync_conf', None, False, False)

def setCorosyncConfig(node,config):
    if is_rhel6():
        data = urlencode({'cluster_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_cluster_conf', data)
        if status != 0:
            err("Unable to set cluster.conf: {0}".format(data))
    else:
        data = urlencode({'corosync_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_corosync_conf', data)
        if status != 0:
            err("Unable to set corosync config: {0}".format(data))

def getPacemakerNodeStatus(node):
    return sendHTTPRequest(
        node, "remote/pacemaker_node_status", None, False, False
    )

def startCluster(node, quiet=False, timeout=None):
    return sendHTTPRequest(
        node,
        "remote/cluster_start",
        printResult=False,
        printSuccess=not quiet,
        timeout=timeout
    )

def stopPacemaker(node, quiet=False, force=True):
    return stopCluster(
        node, pacemaker=True, corosync=False, quiet=quiet, force=force
    )

def stopCorosync(node, quiet=False, force=True):
    return stopCluster(
        node, pacemaker=False, corosync=True, quiet=quiet, force=force
    )

def stopCluster(node, quiet=False, pacemaker=True, corosync=True, force=True):
    data = dict()
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
        'remote/cluster_stop',
        data,
        printResult=False,
        printSuccess=not quiet,
        timeout=timeout
    )

def enableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_enable', None, False, True)

def disableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_disable', None, False, True)

def destroyCluster(node, quiet=False):
    return sendHTTPRequest(node, 'remote/cluster_destroy', None, not quiet, not quiet)

def restoreConfig(node, tarball_data):
    data = urlencode({"tarball": tarball_data})
    return sendHTTPRequest(node, "remote/config_restore", data, False, True)

def pauseConfigSyncing(node, delay_seconds=300):
    data = urlencode({"sync_thread_pause": delay_seconds})
    return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)

def resumeConfigSyncing(node):
    data = urlencode({"sync_thread_resume": 1})
    return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)

def canAddNodeToCluster(node_communicator, target):
    """
    Return tuple with two parts. The first part is information if the node can
    be added to a cluster. The second part is a relevant explanation for the
    first part.

    NodeCommunicator node_communicator -- provides connection to the node
    string target -- the request's destination
    """
    report_list = []
    com_cmd = PrecheckNewNode(report_list, availability_checker_node)
    com_cmd.add_request(target)
    run_com_cmd(node_communicator, com_cmd)

    analyzer = ReportListAnalyzer(report_list)
    if not analyzer.error_list:
        return True, ""

    first_problem = analyzer.error_list[0]

    report_message_map = {
        report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED:
           "unable to authenticate to node"
        ,
        report_codes.CANNOT_ADD_NODE_IS_IN_CLUSTER:
            "node is already in a cluster"
        ,
        report_codes.INVALID_RESPONSE_FORMAT:
            "response parsing error"
        ,
        report_codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE:
             "node is running pacemaker_remote"
        ,
    }

    if first_problem.code in report_message_map:
        return False, report_message_map[first_problem.code]

    return False, "error checking node availability{0}".format(
        ": {0}".format(first_problem.info["reason"])
            if "reason" in first_problem.info else ""
    )

def addLocalNode(node, node_to_add, ring1_addr=None):
    options = {'new_nodename': node_to_add}
    if ring1_addr:
        options['new_ring1addr'] = ring1_addr
    data = urlencode(options)
    retval, output = sendHTTPRequest(node, 'remote/add_node', data, False, False)
    if retval == 0:
        try:
            myout = json.loads(output)
            retval2 = myout[0]
            output = myout[1]
        except ValueError:
            return 1, output
        return retval2, output
    return 1, output

def removeLocalNode(node, node_to_remove, pacemaker_remove=False):
    data = urlencode({'remove_nodename':node_to_remove, 'pacemaker_remove':pacemaker_remove})
    retval, output = sendHTTPRequest(node, 'remote/remove_node', data, False, False)
    if retval == 0:
        try:
            myout = json.loads(output)
        except ValueError:
            return 1,output
        return 0, myout
    return 1, output


# Send an HTTP request to a node return a tuple with status, data
# If status is 0 then data contains server response
# Otherwise if non-zero then data contains error message
# Returns a tuple (error, error message)
# 0 = Success,
# 1 = HTTP Error
# 2 = No response,
# 3 = Auth Error
# 4 = Permission denied
def sendHTTPRequest(
    host, request, data=None, printResult=True, printSuccess=True, timeout=None
):
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
    url = "https://{addr}:{port}/{request}".format(
        addr=addr, request=request, port=port
    )
    if "--debug" in pcs_options:
        print("Sending HTTP Request to: " + url)
        print("Data: {0}".format(data))

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

    output = BytesIO()
    debug_output = BytesIO()
    cookies = __get_cookie_list(token)
    if not timeout:
        timeout = settings.default_request_timeout
    if "--request-timeout" in pcs_options:
        timeout = pcs_options["--request-timeout"]

    handler = pycurl.Curl()
    handler.setopt(pycurl.PROTOCOLS, pycurl.PROTO_HTTPS)
    handler.setopt(pycurl.URL, url.encode("utf-8"))
    handler.setopt(pycurl.WRITEFUNCTION, output.write)
    handler.setopt(pycurl.VERBOSE, 1)
    handler.setopt(pycurl.NOSIGNAL, 1) # required for multi-threading
    handler.setopt(pycurl.DEBUGFUNCTION, __debug_callback)
    handler.setopt(pycurl.TIMEOUT_MS, int(timeout * 1000))
    handler.setopt(pycurl.SSL_VERIFYHOST, 0)
    handler.setopt(pycurl.SSL_VERIFYPEER, 0)
    if cookies:
        handler.setopt(pycurl.COOKIE, ";".join(cookies).encode("utf-8"))
    if data:
        handler.setopt(pycurl.COPYPOSTFIELDS, data.encode("utf-8"))
    try:
        handler.perform()
        response_data = output.getvalue().decode("utf-8")
        response_code = handler.getinfo(pycurl.RESPONSE_CODE)
        if printResult or printSuccess:
            print(host + ": " + response_data.strip())
        if "--debug" in pcs_options:
            print("Response Code: {0}".format(response_code))
            print("--Debug Response Start--\n{0}".format(response_data))
            print("--Debug Response End--")
            print("Communication debug info for calling: {0}".format(url))
            print("--Debug Communication Output Start--")
            print(debug_output.getvalue().decode("utf-8", "ignore"))
            print("--Debug Communication Output End--")
            print()

        if response_code == 401:
            output = (
                3,
                (
                    "Unable to authenticate to {node} - (HTTP error: {code}), "
                    "try running 'pcs host auth {node}'"
                ).format(node=host, code=response_code)
            )
        elif response_code == 403:
            output = (
                4,
                "{node}: Permission denied - (HTTP error: {code})".format(
                    node=host, code=response_code
                )
            )
        elif response_code >= 400:
            output = (
                1,
                "Error connecting to {node} - (HTTP error: {code})".format(
                    node=host, code=response_code
                )
            )
        else:
            output = (0, response_data)

        if printResult and output[0] != 0:
            print(output[1])

        return output
    except pycurl.error as e:
        if is_proxy_set(os.environ):
            print(
                "Warning: Proxy is set in environment variables, try "
                "disabling it"
            )
        dummy_errno, reason = e.args
        if "--debug" in pcs_options:
            print("Response Reason: {0}".format(reason))
        msg = (
            "Unable to connect to {host}, try setting higher timeout in "
            "--request-timeout option ({reason})"
        ).format(host=host, reason=reason)
        if printResult:
            print(msg)
        return (2, msg)


def __get_cookie_list(token):
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
                if "CIB_user" == name:
                    value = re.sub(r"[^!-~]", "", value).replace(";", "")
                else:
                    # python3 requires the value to be bytes not str
                    value = base64.b64encode(
                        value.encode("utf8")
                    ).decode("utf-8")
                cookies.append("{0}={1}".format(name, value))
    return cookies

def get_corosync_conf_facade(conf_path=None, conf_text=None):
    try:
        return corosync_conf_facade.from_string(
            getCorosyncConf(conf_path) if conf_text is None else conf_text
        )
    except corosync_conf_parser.CorosyncConfParserException as e:
        err("Unable to parse corosync.conf: %s" % e)

# Deprecated, not needed, TODO: remove
def getNodesFromCorosyncConf(conf_text=None):
    if is_rhel6():
        dom = getCorosyncConfParsed(text=conf_text)
        return [
            node_el.getAttribute("name")
            for node_el in dom.getElementsByTagName("clusternode")
        ]

    conf_root = getCorosyncConfParsed(text=conf_text)
    nodes = []
    for nodelist in conf_root.get_sections("nodelist"):
        for node in nodelist.get_sections("node"):
            for attr in node.get_attributes("ring0_addr"):
                nodes.append(attr[1])
    return nodes

def getNodeAttributesFromPacemaker():
    try:
        return [
            node.attrs
            for node in ClusterState(getClusterStateXml()).node_section.nodes
        ]
    except LibraryError as e:
        process_library_reports(e.args)


def hasCorosyncConf(conf=None):
    if not conf:
        conf = settings.corosync_conf_file
    return os.path.isfile(conf)

def getCorosyncConf(conf=None):
    if not conf:
        conf = settings.corosync_conf_file
    try:
        out = open(conf).read()
    except IOError as e:
        err("Unable to read %s: %s" % (conf, e.strerror))
    return out

def getCorosyncConfParsed(conf=None, text=None):
    conf_text = getCorosyncConf(conf) if text is None else text
    try:
        return corosync_conf_parser.parse_string(conf_text)
    except corosync_conf_parser.CorosyncConfParserException as e:
        err("Unable to parse corosync.conf: %s" % e)

def setCorosyncConf(corosync_config, conf_file=None):
    if not conf_file:
        if is_rhel6():
            conf_file = settings.cluster_conf_file
        else:
            conf_file = settings.corosync_conf_file
    try:
        f = open(conf_file,'w')
        f.write(corosync_config)
        f.close()
    except EnvironmentError as e:
        err("Unable to write {0}, try running as root.\n{1}".format(
            conf_file, e.strerror
        ))

def reloadCorosync():
    if is_rhel6():
        output, retval = run(["cman_tool", "version", "-r", "-S"])
        return output, retval
    output, retval = run(["corosync-cfgtool", "-R"])
    return output, retval

def getCorosyncActiveNodes():
    output,retval = run(["corosync-cmapctl"])
    if retval != 0:
        return []

    nodename_re = re.compile(r"^nodelist\.node\.(\d+)\.name .*= (.*)", re.M)
    nodestatus_re = re.compile(
        r"^runtime\.members\.(\d+).status .*= (.*)",
        re.M
    )
    nodenameid_mapping_re = re.compile(
        r"nodelist\.node\.(\d+)\.nodeid .*= (\d+)",
        re.M
    )

    node_names = nodename_re.findall(output)
    node_statuses = nodestatus_re.findall(output)
    node_ids = nodenameid_mapping_re.findall(output)

    index_to_id = {index:nodeid for index, nodeid in node_ids}
    id_to_status = {nodeid:status for nodeid, status in node_statuses}

    node_status = {}
    for index, node_name in node_names:
        if index in index_to_id:
            nodeid = index_to_id[index]
            if nodeid in id_to_status:
                node_status[node_name] = id_to_status[nodeid]
        else:
            print("Error mapping %s" % node_name)

    nodes_active = []
    for node,status in node_status.items():
        if status == "joined":
            nodes_active.append(node)

    return nodes_active


def _enable_auto_tie_breaker_for_sbd(corosync_conf):
    """
    Enable auto tie breaker in specified corosync conf if it is needed by SBD.

    corosync_conf -- parsed corosync conf
    """
    try:
        corosync_facade = corosync_conf_facade(corosync_conf)
        if sbd.atb_has_to_be_enabled(cmd_runner(), corosync_facade):
            corosync_facade.set_quorum_options({"auto_tie_breaker": "1"})
    except LibraryError as e:
        process_library_reports(e.args)


# Add node specified to corosync.conf and reload corosync.conf (if running)
def addNodeToCorosync(node):
# Before adding, make sure node isn't already in corosync.conf
    node0, node1 = parse_multiring_node(node)
    corosync_conf_text = getCorosyncConf()
    for c_node in getNodesFromCorosyncConf(conf_text=corosync_conf_text):
        if (c_node == node0) or (c_node == node1):
            err("node already exists in corosync.conf")
    if "--corosync_conf" not in pcs_options:
        for c_node in getCorosyncActiveNodes():
            if (c_node == node0) or (c_node == node1):
                err("Node already exists in running corosync")
    corosync_conf = getCorosyncConfParsed(text=corosync_conf_text)
    new_nodeid = getNextNodeID(corosync_conf)

    nodelists = corosync_conf.get_sections("nodelist")
    if not nodelists:
        err("unable to find nodelist in corosync.conf")
    nodelist = nodelists[0]
    new_node = corosync_conf_parser.Section("node")
    nodelist.add_section(new_node)
    new_node.add_attribute("ring0_addr", node0)
    if node1:
        new_node.add_attribute("ring1_addr", node1)
    new_node.add_attribute("nodeid", new_nodeid)

    # enable ATB if it's needed
    _enable_auto_tie_breaker_for_sbd(corosync_conf)

    corosync_conf = autoset_2node_corosync(corosync_conf)
    setCorosyncConf(str(corosync_conf))
    return True

def addNodeToClusterConf(node):
    node0, node1 = parse_multiring_node(node)
    nodes = getNodesFromCorosyncConf()
    for existing_node in nodes:
        if (existing_node == node0) or (existing_node == node1):
            err("node already exists in cluster.conf")

    output, retval = run(["ccs", "-f", settings.cluster_conf_file, "--addnode", node0])
    if retval != 0:
        print(output)
        err("error adding node: %s" % node0)

    if node1:
        output, retval = run([
            "ccs", "-f", settings.cluster_conf_file,
            "--addalt", node0, node1
        ])
        if retval != 0:
            print(output)
            err(
                "error adding alternative address for node: %s" % node0
            )

    # ensure the pacemaker fence device exists
    pcmk_fence_name = None
    all_fence_names = set()
    output, retval = run([
        "ccs", "-i", "-f", settings.cluster_conf_file, "--lsfencedev"
    ])
    if retval == 0:
        for line in output.splitlines():
            fence_name, dummy_fence_args = line.split(":", 1)
            all_fence_names.add(fence_name)
            match = re.match("(^|(.* ))agent=fence_pcmk((,.+)|$)", line)
            if match:
                pcmk_fence_name = fence_name
    if not pcmk_fence_name:
        fence_index = 1
        pcmk_fence_name = "pcmk-redirect"
        while pcmk_fence_name in all_fence_names:
            pcmk_fence_name = "pcmk-redirect-{0}".format(fence_index)
            fence_index += 1

        output, retval = run([
            "ccs", "-i", "-f", settings.cluster_conf_file,
            "--addfencedev", pcmk_fence_name, "agent=fence_pcmk",
        ])
        if retval != 0:
            print(output)
            err("error fence device for node: %s" % node)

    output, retval = run(["ccs", "-i", "-f", settings.cluster_conf_file, "--addmethod", "pcmk-method", node0])
    if retval != 0:
        print(output)
        err("error adding fence method: %s" % node)

    output, retval = run(["ccs", "-i", "-f", settings.cluster_conf_file, "--addfenceinst", pcmk_fence_name, node0, "pcmk-method", "port="+node0])
    if retval != 0:
        print(output)
        err("error adding fence instance: %s" % node)

    if len(nodes) == 2:
        cman_options_map = get_cluster_conf_cman_options()
        cman_options_map.pop("expected_votes", None)
        cman_options_map.pop("two_node", None)
        cman_options = ["%s=%s" % (n, v) for n, v in cman_options_map.items()]
        output, retval = run(
            ["ccs", "-i", "-f", settings.cluster_conf_file, "--setcman"]
            + cman_options
        )
        if retval != 0:
            print(output)
            err("unable to set cman options")

    return True

def removeNodeFromCorosync(node_expression):
    removed_node = False
    node0, node1 = parse_multiring_node(node_expression)

    corosync_conf = getCorosyncConfParsed()
    for nodelist in corosync_conf.get_sections("nodelist"):
        for node in nodelist.get_sections("node"):
            ring0_attrs = node.get_attributes("ring0_addr")
            if ring0_attrs:
                ring0_conf = ring0_attrs[0][1]
                if (ring0_conf == node0) or (node1 and ring0_conf == node1):
                    node.parent.del_section(node)
                    removed_node = True

    if removed_node:
        # enable ATB if it's needed
        _enable_auto_tie_breaker_for_sbd(corosync_conf)

        corosync_conf = autoset_2node_corosync(corosync_conf)
        setCorosyncConf(str(corosync_conf))

    return removed_node

def removeNodeFromClusterConf(node):
    node0, dummy_node1 = parse_multiring_node(node)
    nodes = getNodesFromCorosyncConf()
    if node0 not in nodes:
        return False

    output, retval = run(["ccs", "-f", settings.cluster_conf_file, "--rmnode", node0])
    if retval != 0:
        print(output)
        err("error removing node: %s" % node)

    if len(nodes) == 3:
        cman_options_map = get_cluster_conf_cman_options()
        cman_options_map.pop("expected_votes", None)
        cman_options_map.pop("two_node", None)
        cman_options = ["%s=%s" % (n, v) for n, v in cman_options_map.items()]
        output, retval = run(
            ["ccs", "-f", settings.cluster_conf_file, "--setcman"]
            + ["two_node=1", "expected_votes=1"]
            + cman_options
        )
        if retval != 0:
            print(output)
            err("unable to set cman options: expected_votes and two_node")
    return True

def autoset_2node_corosync(corosync_conf):
    facade = corosync_conf_facade(corosync_conf)
    facade._ConfigFacade__update_two_node()
    return facade.config

# is it needed to handle corosync-qdevice service when managing cluster services
def need_to_handle_qdevice_service():
    try:
        cfg = corosync_conf_facade.from_string(
            open(settings.corosync_conf_file).read()
        )
        return cfg.has_quorum_device()
    except (EnvironmentError, corosync_conf_parser.CorosyncConfParserException):
        # corosync.conf not present or not valid => no qdevice specified
        return False

def getNextNodeID(corosync_conf):
    currentNodes = []
    highest = 0
    for nodelist in corosync_conf.get_sections("nodelist"):
        for node in nodelist.get_sections("node"):
            for attr in node.get_attributes("nodeid"):
                nodeid = int(attr[1])
                currentNodes.append(nodeid)
                if nodeid > highest:
                    highest = nodeid

    cur_test_id = highest
    while cur_test_id >= 1:
        if cur_test_id not in currentNodes:
            return cur_test_id
        cur_test_id = cur_test_id - 1

    return highest + 1

def parse_multiring_node(node):
    node_addr_count = node.count(",") + 1
    if node_addr_count == 2:
        return node.split(",")
    elif node_addr_count == 1:
        return node, None
    else:
        err(
            "You cannot specify more than two addresses for a node: %s"
            % node
        )

def need_ring1_address(corosync_conf_text):
    if is_rhel6():
        # ring1 address is required regardless of transport
        # it has to be added to cluster.conf in order to set up ring1
        # in corosync by cman
        try:
            dom = parseString(corosync_conf_text)
        except xml.parsers.expat.ExpatError as e:
            err("Unable parse cluster.conf: %s" % e)
        rrp = False
        for el in dom.getElementsByTagName("totem"):
            if el.getAttribute("rrp_mode") in ["active", "passive"]:
                rrp = True
        return rrp

    corosync_conf = getCorosyncConfParsed(text=corosync_conf_text)
    udpu_transport = False
    rrp = False
    for totem in corosync_conf.get_sections("totem"):
        for attr in totem.get_attributes():
            if attr[0] == "transport" and attr[1] == "udpu":
                udpu_transport = True
            if attr[0] == "rrp_mode" and attr[1] in ["active", "passive"]:
                rrp = True
    return udpu_transport and rrp

def is_cman_with_udpu_transport():
    if not is_rhel6():
        return False
    cman_options = get_cluster_conf_cman_options()
    return cman_options.get("transport", "").lower() == "udpu"

def get_cluster_conf_cman_options():
    try:
        dom = parse(settings.cluster_conf_file)
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        err("Unable to read cluster.conf: %s" % e)
    cman = dom.getElementsByTagName("cman")
    if not cman:
        return dict()
    cman = cman[0]
    options = dict()
    for name, value in cman.attributes.items():
        options[name] = value
    return options

# Restore default behavior before starting subprocesses
def subprocess_setup():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

def touch_cib_file(filename):
    if not os.path.isfile(filename):
        try:
            write_empty_cib(filename)
        except EnvironmentError as e:
            err(
                "Unable to write to file: '{0}': '{1}'".format(filename, str(e))
            )

# Run command, with environment and return (output, retval)
# DEPRECATED, please use lib.external.CommandRunner via utils.cmd_runner()
def run(
    args, ignore_stderr=False, string_for_stdin=None, env_extend=None,
    binary_output=False
):
    if not env_extend:
        env_extend = dict()
    env_var = env_extend
    env_var.update(dict(os.environ))
    env_var["LC_ALL"] = "C"
    if usefile:
        env_var["CIB_file"] = filename
        touch_cib_file(filename)

    command = args[0]
    if command[0:3] == "crm" or command in ["cibadmin", "cman_tool", "iso8601"]:
        args[0] = settings.pacemaker_binaries + command
    elif command[0:8] == "corosync":
        args[0] = settings.corosync_binaries + command
    elif command == "ccs":
        args[0] = settings.ccs_binaries + command

    try:
        if "--debug" in pcs_options:
            print("Running: " + " ".join(args))
            if string_for_stdin:
                print("--Debug Input Start--\n" + string_for_stdin)
                print("--Debug Input End--")

        # Some commands react differently if you give them anything via stdin
        if string_for_stdin != None:
            stdin_pipe = subprocess.PIPE
        else:
            stdin_pipe = None

        p = subprocess.Popen(
            args,
            stdin=stdin_pipe,
            stdout=subprocess.PIPE,
            stderr=(subprocess.PIPE if ignore_stderr else subprocess.STDOUT),
            preexec_fn=subprocess_setup,
            close_fds=True,
            env=env_var,
            # decodes newlines and in python3 also converts bytes to str
            universal_newlines=(not binary_output)
        )
        output, dummy_stderror = p.communicate(string_for_stdin)
        returnVal = p.returncode
        if "--debug" in pcs_options:
            print("Return Value: {0}".format(returnVal))
            print(("--Debug Output Start--\n{0}".format(output)).rstrip())
            print("--Debug Output End--")
            print()
    except OSError as e:
        print(e.strerror)
        err("unable to locate command: " + args[0])

    return output, returnVal

@lru_cache()
def cmd_runner():
    env_vars = dict()
    if usefile:
        env_vars["CIB_file"] = filename
    env_vars.update(os.environ)
    env_vars["LC_ALL"] = "C"
    return CommandRunner(
        logging.getLogger("pcs"),
        get_report_processor(),
        env_vars
    )

def run_pcsdcli(command, data=None):
    if not data:
        data = dict()
    env_var = dict()
    if "--debug" in pcs_options:
        env_var["PCSD_DEBUG"] = "true"
    if "--request-timeout" in pcs_options:
        env_var["PCSD_NETWORK_TIMEOUT"] = str(pcs_options["--request-timeout"])
    else:
        env_var["PCSD_NETWORK_TIMEOUT"] = str(settings.default_request_timeout)
    pcsd_dir_path = settings.pcsd_exec_location
    pcsdcli_path = os.path.join(pcsd_dir_path, 'pcsd-cli.rb')
    gem_home = os.path.join(pcsd_dir_path, settings.pcsd_gem_path)
    env_var["GEM_HOME"] = gem_home
    stdout, dummy_stderr, retval = cmd_runner().run(
        [settings.ruby_executable, "-I" + pcsd_dir_path, pcsdcli_path, command],
        json.dumps(data),
        env_var
    )
    try:
        output_json = json.loads(stdout)
        for key in ['status', 'text', 'data']:
            if key not in output_json:
                output_json[key] = None

        output = "".join(output_json['log'])
        # check if some requests timed out, if so print message about it
        if "error: operation_timedout" in output:
            print("Error: Operation timed out")
        # check if there are any connection failures due to proxy in pcsd and
        # print warning if so
        proxy_msg = (
            'Proxy is set in environment variables, try disabling it'
        )
        if proxy_msg in output:
            print("Warning: {0}".format(proxy_msg))

    except ValueError:
        output_json = {
            'status': 'bad_json_output',
            'text': stdout,
            'data': None,
        }
    return output_json, retval

def auth_hosts(host_dict):
    output, retval = run_pcsdcli('auth', dict(nodes=host_dict))
    if retval == 0 and output['status'] == 'access_denied':
        err('Access denied')
    if retval == 0 and output['status'] == 'ok' and output['data']:
        failed = False
        try:
            if not output['data']['sync_successful']:
                err(
                    "Some nodes had a newer known-hosts than the local node. "
                    + "Local node's known-hosts were updated. "
                    + "Please repeat the authentication if needed."
                )
            for node, result in output['data']['auth_responses'].items():
                if result['status'] == 'ok':
                    print("{0}: Authorized".format(node))
                elif result['status'] == 'bad_password':
                    err(
                        "{0}: Username and/or password is incorrect".format(node),
                        False
                    )
                    failed = True
                elif result['status'] in ('noresponse', 'error'):
                    err("Unable to communicate with {0}".format(node), False)
                    failed = True
                else:
                    err("Unexpected response from {0}".format(node), False)
                    failed = True
            if output['data']['sync_nodes_err']:
                err(
                    (
                        "Unable to synchronize and save known-hosts on nodes: "
                        + "{0}. Run 'pcs host auth {1}' to make sure the nodes "
                        + "are authorized."
                    ).format(
                        ", ".join(output['data']['sync_nodes_err']),
                        " ".join(output['data']['sync_nodes_err'])
                    )
                )
        except (ValueError, KeyError):
            err('Unable to communicate with pcsd')
        if failed:
            sys.exit(1)
        return
    err('Unable to communicate with pcsd')

def call_local_pcsd(argv, interactive_auth=False, std_in=None):
    # some commands cannot be run under a non-root account
    # so we pass those commands to locally running pcsd to execute them
    # returns [list_of_errors, exit_code, stdout, stderr]
    data = {
        "command": json.dumps(argv),
    }
    if std_in:
        data['stdin'] = std_in
    data_send = urlencode(data)
    code, output = sendHTTPRequest(
        "localhost", "run_pcs", data_send, False, False
    )

    # authenticate against local pcsd and run again
    if interactive_auth and 3 == code: # not authenticated
        print('Please authenticate yourself to the local pcsd')
        username = get_terminal_input('Username: ')
        password = get_terminal_password()
        port = get_terminal_input(
            'Port (default: {0}): '.format(settings.pcsd_default_port)
            # default port is not completely correct, because default port from
            # pcsd will be used
        )
        if not port:
            port = settings.pcsd_default_port
        auth_hosts(
            {
                "localhost": {
                    "username": username,
                    "password": password,
                    "dest_list": [{"addr": "localhost", "port": port, }]
                }
            }
        )
        print()
        code, output = sendHTTPRequest(
            "localhost", "run_pcs", data_send, False, False
        )

    if 3 == code: # not authenticated
        # don't advise to run 'pcs cluster auth' as that is not used to auth
        # to localhost
        return [['Unable to authenticate to the local pcsd'], 1, '', '']
    if 0 != code: # http error connecting to localhost
        return [[output], 1, '', '']

    try:
        output_json = json.loads(output)
        for key in ['status', 'data']:
            if key not in output_json:
                output_json[key] = None
    except ValueError:
        return [['Unable to communicate with pcsd'], 1, '', '']
    if output_json['status'] == 'bad_command':
        return [['Command not allowed'], 1, '', '']
    if output_json['status'] == 'access_denied':
        return [['Access denied'], 1, '', '']
    if output_json['status'] != "ok" or not output_json["data"]:
        return [['Unable to communicate with pcsd'], 1, '', '']
    try:
        exitcode = output_json["data"]["code"]
        std_out = output_json["data"]["stdout"]
        std_err = output_json["data"]["stderr"]
        return [[], exitcode, std_out, std_err]
    except KeyError:
        return [['Unable to communicate with pcsd'], 1, '', '']

def map_for_error_list(callab, iterab):
    error_list = []
    for item in iterab:
        (retval, err) = callab(item)
        if retval != 0:
            error_list.append(err)
    return error_list

def run_parallel(worker_list, wait_seconds=1):
    thread_list = []
    for worker in worker_list:
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread_list.append(thread)

    while thread_list:
        for thread in thread_list:
            thread.join(wait_seconds)
            if not thread.is_alive():
                thread_list.remove(thread)

def create_task(report, action, node, *args, **kwargs):
    def worker():
        returncode, output = action(node, *args, **kwargs)
        report(node, returncode, output)
    return worker

def create_task_list(report, action, node_list, *args, **kwargs):
    return [
        create_task(report, action, node, *args, **kwargs) for node in node_list
    ]

def parallel_for_nodes(action, node_list, *args, **kwargs):
    node_errors = dict()
    def report(node, returncode, output):
        message = '{0}: {1}'.format(node, output.strip())
        print(message)
        if returncode != 0:
            node_errors[node] = message
    run_parallel(
        create_task_list(report, action, node_list, *args, **kwargs)
    )
    return node_errors

# Check is something exists in the CIB, if it does return it, if not, return
#  an empty string
def does_exist(xpath_query):
    args = ["cibadmin", "-Q", "--xpath", xpath_query]
    dummy_output,retval = run(args)
    if (retval != 0):
        return False
    return True

def get_group_children(group_id):
    child_resources = []
    dom = get_cib_dom()
    groups = dom.getElementsByTagName("group")
    for g in groups:
        if g.getAttribute("id") == group_id:
            for child in g.childNodes:
                if (child.nodeType != xml.dom.minidom.Node.ELEMENT_NODE):
                    continue
                if child.tagName == "primitive":
                    child_resources.append(child.getAttribute("id"))
    return child_resources

def dom_get_clone_ms_resource(dom, clone_ms_id):
    clone_ms = (
        dom_get_clone(dom, clone_ms_id)
        or
        dom_get_master(dom, clone_ms_id)
    )
    if clone_ms:
        return dom_elem_get_clone_ms_resource(clone_ms)
    return None

def dom_elem_get_clone_ms_resource(clone_ms):
    for child in clone_ms.childNodes:
        if (
            child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
            and
            child.tagName in ["group", "primitive"]
        ):
            return child
    return None

def dom_get_resource_clone_ms_parent(dom, resource_id):
    resource = (
        dom_get_resource(dom, resource_id)
        or
        dom_get_group(dom, resource_id)
    )
    if resource:
        return dom_elem_get_resource_clone_ms_parent(resource)
    return None

def dom_elem_get_resource_clone_ms_parent(resource):
    return dom_get_parent_by_tag_names(resource, ["clone", "master"])

def dom_get_resource_bundle_parent(dom, resource_id):
    resource = dom_get_resource(dom, resource_id)
    if resource:
        return dom_get_parent_by_tag_names(resource, ["bundle"])
    return None

def dom_get_master(dom, master_id):
    for master in dom.getElementsByTagName("master"):
        if master.getAttribute("id") == master_id:
            return master
    return None

def dom_get_clone(dom, clone_id):
    for clone in dom.getElementsByTagName("clone"):
        if clone.getAttribute("id") == clone_id:
            return clone
    return None

def dom_get_group(dom, group_id):
    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_id:
            return group
    return None

def dom_get_bundle(dom, bundle_id):
    for bundle in dom.getElementsByTagName("bundle"):
        if bundle.getAttribute("id") == bundle_id:
            return bundle
    return None

def dom_get_resource_bundle(bundle_el):
    for child in bundle_el.childNodes:
        if (
            child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
            and
            child.tagName == "primitive"
        ):
            return child
    return None

def dom_get_group_clone(dom, group_id):
    for clone in dom.getElementsByTagName("clone"):
        group = dom_get_group(clone, group_id)
        if group:
            return group
    return None

def dom_get_group_masterslave(dom, group_id):
    for master in dom.getElementsByTagName("master"):
        group = dom_get_group(master, group_id)
        if group:
            return group
    return None

def dom_get_resource(dom, resource_id):
    for primitive in dom.getElementsByTagName("primitive"):
        if primitive.getAttribute("id") == resource_id:
            return primitive
    return None

def dom_get_any_resource(dom, resource_id):
    return (
        dom_get_resource(dom, resource_id)
        or
        dom_get_group(dom, resource_id)
        or
        dom_get_clone(dom, resource_id)
        or
        dom_get_master(dom, resource_id)
    )

def is_stonith_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"' and @class='stonith']")

def dom_get_resource_clone(dom, resource_id):
    for clone in dom.getElementsByTagName("clone"):
        resource = dom_get_resource(clone, resource_id)
        if resource:
            return resource
    return None

def dom_get_resource_masterslave(dom, resource_id):
    for master in dom.getElementsByTagName("master"):
        resource = dom_get_resource(master, resource_id)
        if resource:
            return resource
    return None

# returns tuple (is_valid, error_message, correct_resource_id_if_exists)
# there is a duplicate code in pcs/lib/cib/constraint/constraint.py
# please use function in pcs/lib/cib/constraint/constraint.py
def validate_constraint_resource(dom, resource_id):
    resource_el = (
        dom_get_clone(dom, resource_id)
        or
        dom_get_master(dom, resource_id)
        or
        dom_get_bundle(dom, resource_id)
    )
    if resource_el:
        # clones, masters and bundles are always valid
        return True, "", resource_id

    resource_el = (
        dom_get_resource(dom, resource_id)
        or
        dom_get_group(dom, resource_id)
    )
    if not resource_el:
        return False, "Resource '%s' does not exist" % resource_id, None

    clone_el = (
        dom_get_resource_clone_ms_parent(dom, resource_id)
        or
        dom_get_resource_bundle_parent(dom, resource_id)
    )
    if not clone_el:
        # a primitive and a group is valid if not in a clone nor a master nor a
        # bundle
        return True, "", resource_id

    if "--force" in pcs_options:
        return True, "", clone_el.getAttribute("id")

    if clone_el.tagName == "clone":
        return (
            False,
            "%s is a clone resource, you should use the clone id: %s "
                "when adding constraints. Use --force to override."
                % (resource_id, clone_el.getAttribute("id")),
            clone_el.getAttribute("id")
        )
    if clone_el.tagName == "master":
        return (
            False,
            "%s is a master/slave resource, you should use the master id: %s "
                "when adding constraints. Use --force to override."
                % (resource_id, clone_el.getAttribute("id")),
            clone_el.getAttribute("id")
        )
    if clone_el.tagName == "bundle":
        return (
            False,
            "%s is a bundle resource, you should use the bundle id: %s "
                "when adding constraints. Use --force to override."
                % (resource_id, clone_el.getAttribute("id")),
            clone_el.getAttribute("id")
        )
    return True, "", resource_id


def dom_get_resource_remote_node_name(dom_resource):
    if dom_resource.tagName != "primitive":
        return None
    if (
        dom_resource.getAttribute("class").lower() == "ocf"
        and
        dom_resource.getAttribute("provider").lower() == "pacemaker"
        and
        dom_resource.getAttribute("type").lower() == "remote"
    ):
        return dom_resource.getAttribute("id")
    return dom_get_meta_attr_value(dom_resource, "remote-node")

def dom_get_meta_attr_value(dom_resource, meta_name):
    for meta in dom_resource.getElementsByTagName("meta_attributes"):
        for nvpair in meta.getElementsByTagName("nvpair"):
            if nvpair.getAttribute("name") == meta_name:
                return nvpair.getAttribute("value")
    return None

def dom_get_element_with_id(dom, tag_name, element_id):
    for elem in dom.getElementsByTagName(tag_name):
        if elem.hasAttribute("id") and elem.getAttribute("id") == element_id:
            return elem
    return None

def dom_get_node(dom, node_name):
    for e in dom.getElementsByTagName("node"):
        if e.hasAttribute("uname") and e.getAttribute("uname") == node_name:
            return e
    return None

def dom_get_children_by_tag_name(dom_el, tag_name):
    return [
        node
        for node in dom_el.childNodes
        if node.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
            and node.tagName == tag_name
   ]

def dom_get_child_by_tag_name(dom_el, tag_name):
    children = dom_get_children_by_tag_name(dom_el, tag_name)
    if children:
        return children[0]
    return None

def dom_get_parent_by_tag_names(dom_el, tag_names):
    parent = dom_el.parentNode
    while parent:
        if not isinstance(parent, xml.dom.minidom.Element):
            return None
        if parent.tagName in tag_names:
            return parent
        parent = parent.parentNode
    return None

def dom_attrs_to_list(dom_el, with_id=False):
    attributes = [
        "%s=%s" % (name, value)
        for name, value in sorted(dom_el.attributes.items()) if name != "id"
    ]
    if with_id:
        attributes.append("(id:%s)" % (dom_el.getAttribute("id")))
    return attributes

# moved to pcs.lib.pacemaker.state
def get_resource_for_running_check(cluster_state, resource_id, stopped=False):
    for clone in cluster_state.getElementsByTagName("clone"):
        if clone.getAttribute("id") == resource_id:
            for child in clone.childNodes:
                if (
                    child.nodeType == child.ELEMENT_NODE
                    and
                    child.tagName in ["resource", "group"]
                ):
                    resource_id = child.getAttribute("id")
                    # in a clone a resource can have an id of '<name>:N'
                    if ":" in resource_id:
                        parts = resource_id.rsplit(":", 1)
                        if parts[1].isdigit():
                            resource_id = parts[0]
                    break
    for group in cluster_state.getElementsByTagName("group"):
        # If resource is a clone it can have an id of '<resource name>:N'
        if (
            group.getAttribute("id") == resource_id
            or
            group.getAttribute("id").startswith(resource_id + ":")
        ):
            if stopped:
                elem = group.getElementsByTagName("resource")[0]
            else:
                elem = group.getElementsByTagName("resource")[-1]
            resource_id = elem.getAttribute("id")
    return resource_id

# moved to pcs.lib.pacemaker.state
# see pcs.lib.commands.resource for usage
def resource_running_on(resource, passed_state=None, stopped=False):
    nodes_started = []
    nodes_master = []
    nodes_slave = []
    state = passed_state if passed_state else getClusterState()
    resource_original = resource
    resource = get_resource_for_running_check(state, resource, stopped)
    resources = state.getElementsByTagName("resource")
    for res in resources:
        # If resource is a clone it can have an id of '<resource name>:N'
        # If resource is a clone it will be found more than once - cannot break
        if (
            (
                res.getAttribute("id") == resource
                or
                res.getAttribute("id").startswith(resource+":")
            )
            and
            res.getAttribute("failed") != "true"
        ):
            for node in res.getElementsByTagName("node"):
                node_name = node.getAttribute("name")
                if res.getAttribute("role") == "Started":
                    nodes_started.append(node_name)
                elif res.getAttribute("role") == "Master":
                    nodes_master.append(node_name)
                elif res.getAttribute("role") == "Slave":
                    nodes_slave.append(node_name)
    if not nodes_started and not nodes_master and not nodes_slave:
        message = "Resource '%s' is not running on any node" % resource_original
    else:
        message_parts = []
        for alist, label in (
            (nodes_started, "running"),
            (nodes_master, "master"),
            (nodes_slave, "slave")
        ):
            if alist:
                alist.sort()
                message_parts.append(
                    "%s on node%s %s"
                    % (
                        label,
                        "s" if len(alist) > 1 else "",
                        ", ".join(alist)
                    )
                )
        message = "Resource '%s' is %s."\
            % (resource_original, "; ".join(message_parts))
    return {
        "message": message,
        "is_running": bool(nodes_started or nodes_master or nodes_slave),
        "nodes_started": nodes_started,
        "nodes_master": nodes_master,
        "nodes_slave": nodes_slave,
    }

def agent_action_to_cmdline_format(action):
    op = [action["name"]]
    for key in action.keys():
        if key != "name" and action[key] != "0":
            op.append("{0}={1}".format(key, action[key]))
    return op

def check_pacemaker_supports_resource_wait():
    if not has_wait_for_idle_support(cmd_runner()):
        err("crm_resource does not support --wait, please upgrade pacemaker")

def validate_wait_get_timeout(need_cib_support=True):
    if need_cib_support:
        check_pacemaker_supports_resource_wait()
        if usefile:
            err("Cannot use '-f' together with '--wait'")
    wait_timeout = pcs_options["--wait"]
    if wait_timeout is None:
        return wait_timeout
    wait_timeout = get_timeout_seconds(wait_timeout)
    if wait_timeout is None:
        err(
            "%s is not a valid number of seconds to wait"
            % pcs_options["--wait"]
        )
    return wait_timeout


# Return matches from the CIB with the xpath_query
def get_cib_xpath(xpath_query):
    args = ["cibadmin", "-Q", "--xpath", xpath_query]
    output,retval = run(args)
    if (retval != 0):
        return ""
    return output

def get_cib(scope=None):
    command = ["cibadmin", "-l", "-Q"]
    if scope:
        command.append("--scope=%s" % scope)
    output, retval = run(command)
    if retval != 0:
        if retval == 6 and scope:
            err("unable to get cib, scope '%s' not present in cib" % scope)
        else:
            err("unable to get cib")
    return output

def get_cib_dom():
    try:
        dom = parseString(get_cib())
        return dom
    except:
        err("unable to get cib")

def get_cib_etree():
    try:
        root = ET.fromstring(get_cib())
        return root
    except:
        err("unable to get cib")

def is_etree(var):
    return (
        var.__class__ == xml.etree.ElementTree.Element
        or
        (
            # in python3 _ElementInterface does not exist
            hasattr(xml.etree.ElementTree, "_ElementInterface")
            and
            var.__class__ == xml.etree.ElementTree._ElementInterface
        )
    )

# Replace only configuration section of cib with dom passed
def replace_cib_configuration(dom):
    if is_etree(dom):
        #etree returns string in bytes: b'xml'
        #python 3 removed .encode() from byte strings
        #run(...) calls subprocess.Popen.communicate which calls encode...
        #so there is bytes to str conversion
        new_dom = ET.tostring(dom).decode()
    elif hasattr(dom, "toxml"):
        new_dom = dom.toxml()
    else:
        new_dom = dom
    cmd = ["cibadmin", "--replace", "-V", "--xml-pipe", "-o", "configuration"]
    output, retval = run(cmd, False, new_dom)
    if retval != 0:
        err("Unable to update cib\n"+output)

def is_valid_cib_scope(scope):
    return scope in [
        "configuration", "nodes", "resources", "constraints", "crm_config",
        "rsc_defaults", "op_defaults", "status",
    ]

# Checks to see if id exists in the xml dom passed
# DEPRECATED use lxml version available in pcs.lib.cib.tools
def does_id_exist(dom, check_id):
    # do not search in /cib/status, it may contain references to previously
    # existing and deleted resources and thus preventing creating them again
    if is_etree(dom):
        for elem in dom.findall(str(
            '(/cib/*[name()!="status"]|/*[name()!="cib"])/*'
        )):
            if elem.get("id") == check_id:
                return True
    else:
        document = (
            dom
            if isinstance(dom, xml.dom.minidom.Document)
            else dom.ownerDocument
        )
        cib_found = False
        for cib in dom_get_children_by_tag_name(document, "cib"):
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
    counter = 1
    temp_id = check_id
    while does_id_exist(dom,temp_id):
        temp_id = check_id + "-" + str(counter)
        counter += 1
    return temp_id

# Checks to see if the specified operation already exists in passed set of
# operations
# pacemaker differentiates between operations only by name and interval
def operation_exists(operations_el, op_el):
    existing = []
    op_name = op_el.getAttribute("name")
    op_interval = get_timeout_seconds(op_el.getAttribute("interval"), True)
    for op in operations_el.getElementsByTagName("op"):
        if (
            op.getAttribute("name") == op_name
            and
            get_timeout_seconds(op.getAttribute("interval"), True) == op_interval
        ):
            existing.append(op)
    return existing

def operation_exists_by_name(operations_el, op_el):
    existing = []
    op_name = op_el.getAttribute("name")
    op_role = op_el.getAttribute("role") or "Started"
    ocf_check_level = None
    if "monitor" == op_name:
        ocf_check_level = get_operation_ocf_check_level(op_el)

    for op in operations_el.getElementsByTagName("op"):
        if op.getAttribute("name") == op_name:
            if op_name != "monitor":
                existing.append(op)
            elif (
                (op.getAttribute("role") or "Started") == op_role
                and
                ocf_check_level == get_operation_ocf_check_level(op)
            ):
                existing.append(op)
    return existing

def get_operation_ocf_check_level(operation_el):
    for attr_el in operation_el.getElementsByTagName("instance_attributes"):
        for nvpair_el in attr_el.getElementsByTagName("nvpair"):
            if nvpair_el.getAttribute("name") == "OCF_CHECK_LEVEL":
                return nvpair_el.getAttribute("value")
    return None

def set_unmanaged(resource):
    args = ["crm_resource", "--resource", resource, "--set-parameter",
            "is-managed", "--meta", "--parameter-value", "false"]
    return run(args)

def get_node_attributes(filter_node=None, filter_attr=None):
    node_config = get_cib_xpath("//nodes")
    if (node_config == ""):
        err("unable to get crm_config, is pacemaker running?")
    dom = parseString(node_config).documentElement
    nas = dict()
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
                    nas[nodename] = dict()
                nas[nodename][attr_name] = nvp.getAttribute("value")
            # Use just first element of attributes. We don't support
            # attributes with rules just yet.
            break
    return nas

def set_node_attribute(prop, value, node):
    if (value == ""):
        o,r = run(["crm_attribute", "-t", "nodes", "--node", node, "--name",prop,"--query"])
        if r != 0 and "--force" not in pcs_options:
            err(
                "attribute: '%s' doesn't exist for node: '%s'" % (prop, node),
                False
            )
            sys.exit(2)
        o,r = run(["crm_attribute", "-t", "nodes", "--node", node, "--name",prop,"--delete"])
    else:
        o,r = run(["crm_attribute", "-t", "nodes", "--node", node, "--name",prop,"--update",value])

    if r != 0:
        err("unable to set attribute %s\n%s" % (prop,o))


# If the property exists, remove it and replace it with the new property
# If the value is blank, then we just remove it
def set_cib_property(prop, value, cib_dom=None):
    update_cib = cib_dom is None
    if update_cib:
        crm_config = get_cib_xpath("//crm_config")
        if crm_config == "":
            err("unable to get crm_config, is pacemaker running?")
        crm_config = parseString(crm_config).documentElement
    else:
        document = cib_dom.getElementsByTagName("crm_config")
        if len(document) == 0:
            err("unable to get crm_config, is pacemaker running?")
        crm_config = document[0]

    property_found = False
    cluster_property_set = dom_prepare_child_element(
        crm_config, "cluster_property_set", "cib-bootstrap-options"
    )

    for child in cluster_property_set.getElementsByTagName("nvpair"):
        if child.getAttribute("name") == prop:
            property_found = True
            break
    if not property_found and value == "" and "--force" not in pcs_options:
        err("can't remove property: '{0}' that doesn't exist".format(prop))
    dom_update_nv_pair(
        cluster_property_set, prop, value, "cib-bootstrap-options-"
    )

    if update_cib:
        replace_cib_configuration(crm_config)

def getTerminalSize(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.

    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl, termios, struct
        hw = struct.unpack(
            str('hh'),
            fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234')
        )
    except:
        try:
            hw = (os.environ['LINES'], os.environ['COLUMNS'])
        except:
            hw = (25, 80)
    return hw

def get_terminal_input(message=None):
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

def get_terminal_password(message="Password: "):
    if sys.stdin.isatty():
        try:
            return getpass.getpass(message)
        except KeyboardInterrupt:
            print("Interrupted")
            sys.exit(1)
    else:
        return get_terminal_input(message)

# Returns an xml dom containing the current status of the cluster
# DEPRECATED, please use ClusterState(getClusterStateXml()) instead
def getClusterState():
    return parseString(getClusterStateXml())

# DEPRECATED, please use lib.pacemaker.live.get_cluster_status_xml in new code
def getClusterStateXml():
    xml, returncode = run(["crm_mon", "--one-shot", "--as-xml", "--inactive"])
    if returncode != 0:
        err("error running crm_mon, is pacemaker running?")
    return xml

def getResourceType(resource):
    resClass = resource.getAttribute("class")
    resProvider = resource.getAttribute("provider")
    resType = resource.getAttribute("type")
    return resClass + ":" + resProvider + ":" + resType

def getClusterName():
    if is_rhel6():
        try:
            dom = parse(settings.cluster_conf_file)
            return dom.documentElement.getAttribute("name")
        except (IOError,xml.parsers.expat.ExpatError):
            pass
    else:
        try:
            f = open(settings.corosync_conf_file,'r')
            conf = corosync_conf_parser.parse_string(f.read())
            f.close()
            # mimic corosync behavior - the last cluster_name found is used
            cluster_name = None
            for totem in conf.get_sections("totem"):
                for attrs in totem.get_attributes("cluster_name"):
                    cluster_name = attrs[1]
            if cluster_name:
                return cluster_name
        except (IOError, corosync_conf_parser.CorosyncConfParserException):
            pass

    # there is no corosync.conf or cluster.conf on remote nodes, we can try to
    # get cluster name from pacemaker
    try:
        return get_set_properties("cluster-name")["cluster-name"]
    except:
        # we need to catch SystemExit (from utils.err), parse errors and so on
        pass

    return ""

def write_empty_cib(cibfile):

    empty_xml = """<?xml version="1.0" encoding="UTF-8"?>
<cib admin_epoch="0" epoch="1" num_updates="1" validate-with="pacemaker-1.2">
  <configuration>
    <crm_config/>
    <nodes/>
    <resources/>
    <constraints/>
  </configuration>
  <status/>
</cib>"""
    f = open(cibfile, 'w')
    f.write(empty_xml)
    f.close()

# Test if 'var' is a score or option (contains an '=')
def is_score_or_opt(var):
    if is_score(var):
        return True
    elif var.find('=') != -1:
        return True
    return False

def is_score(var):
    return is_score_value(var)

def validate_xml_id(var, description="id"):
    try:
        validate_id(var, description)
    except LibraryError as e:
        return False, build_report_message(e.args[0])
    return True, ""

def is_iso8601_date(var):
    # using pacemaker tool to check if a value is a valid pacemaker iso8601 date
    dummy_output, retVal = run(["iso8601", "-d", var])
    return retVal == 0

def verify_cert_key_pair(cert, key):
    errors = []
    cert_modulus = ""
    key_modulus = ""

    output, retval = run(
        ["/usr/bin/openssl", "x509", "-modulus", "-noout"],
        string_for_stdin=cert
    )
    if retval != 0:
        errors.append("Invalid certificate: {0}".format(output.strip()))
    else:
        cert_modulus = output.strip()

    output, retval = run(
        ["/usr/bin/openssl", "rsa", "-modulus", "-noout"],
        string_for_stdin=key
    )
    if retval != 0:
        errors.append("Invalid key: {0}".format(output.strip()))
    else:
        key_modulus = output.strip()

    if not errors and cert_modulus and key_modulus:
        if cert_modulus != key_modulus:
            errors.append("Certificate does not match the key")

    return errors


def is_rhel6():
    return is_cman_cluster()

@lru_cache()
def is_cman_cluster():
    return lib_is_cman_cluster(cmd_runner())

def err(errorText, exit_after_error=True):
    sys.stderr.write("Error: %s\n" % errorText)
    if exit_after_error:
        sys.exit(1)


def serviceStatus(prefix):
    print("Daemon Status:")
    service_def = [
        # (
        #     service name,
        #     display even if not enabled nor running
        # )
        ("cman", False),
        ("corosync", True),
        ("pacemaker", True),
        ("pacemaker_remote", False),
        ("pcsd", True),
        (sbd.get_sbd_service_name(), False),
    ]
    for service, display_always in service_def:
        try:
            running = is_service_running(cmd_runner(), service)
            enabled = is_service_enabled(cmd_runner(), service)
            if display_always or enabled or running:
                print("{prefix}{service}: {active}/{enabled}".format(
                    prefix=prefix,
                    service=service,
                    active=("active" if running else "inactive"),
                    enabled=("enabled" if enabled else "disabled")
                ))
        except LibraryError:
            pass

def enableServices():
    # do NOT handle SBD in here, it is started by pacemaker not systemd or init
    if is_rhel6():
        service_list = ["pacemaker"]
    else:
        service_list = ["corosync", "pacemaker"]
        if need_to_handle_qdevice_service():
            service_list.append("corosync-qdevice")

    report_item_list = []
    for service in service_list:
        try:
            enable_service(cmd_runner(), service)
        except EnableServiceError as e:
            report_item_list.append(
                reports.service_enable_error(e.service, e.message)
            )
    if report_item_list:
        raise LibraryError(*report_item_list)

def disableServices():
    # do NOT handle SBD in here, it is started by pacemaker not systemd or init
    service_list = ["corosync", "pacemaker"]
    if need_to_handle_qdevice_service():
        service_list.append("corosync-qdevice")

    report_item_list = []
    for service in service_list:
        try:
            disable_service(cmd_runner(), service)
        except DisableServiceError as e:
            report_item_list.append(
                reports.service_disable_error(e.service, e.message)
            )
    if report_item_list:
        raise LibraryError(*report_item_list)

def start_service(service):
    if is_systemctl():
        stdout, stderr, retval = cmd_runner().run([
            _systemctl, "start", service
        ])
    else:
        stdout, stderr, retval = cmd_runner().run([_service, service, "start"])
    return join_multilines([stderr, stdout]), retval

def stop_service(service):
    if is_systemctl():
        stdout, stderr, retval = cmd_runner().run([_systemctl, "stop", service])
    else:
        stdout, stderr, retval = cmd_runner().run([_service, service, "stop"])
    return join_multilines([stderr, stdout]), retval

def write_file(path, data, permissions=0o644, binary=False):
    if os.path.exists(path):
        if "--force" not in pcs_options:
            return False, "'%s' already exists, use --force to overwrite" % path
        else:
            try:
                os.remove(path)
            except EnvironmentError as e:
                return False, "unable to remove '%s': %s" % (path, e)
    mode = "wb" if binary else "w"
    try:
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, permissions), mode) as outfile:
            outfile.write(data)
    except EnvironmentError as e:
        return False, "unable to write to '%s': %s" % (path, e)
    return True, ""

def tar_add_file_data(
    tarball, data, name, mode=None, uid=None, gid=None, uname=None, gname=None,
    mtime=None
):
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

def simulate_cib(cib_dom):
    new_cib_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs")
    transitions_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs")
    output, retval = run(
        ["crm_simulate", "--simulate", "--save-output", new_cib_file.name,
            "--save-graph", transitions_file.name, "--xml-pipe"],
        string_for_stdin=cib_dom.toxml()
    )
    if retval != 0:
        err("Unable to run crm_simulate:\n%s" % output)
    try:
        new_cib_file.seek(0)
        transitions_file.seek(0)
        return (
            output,
            parseString(transitions_file.read()),
            parseString(new_cib_file.read()),
        )
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        err("Unable to run crm_simulate:\n%s" % e)
    except xml.etree.ElementTree.ParseError as e:
        err("Unable to run crm_simulate:\n%s" % e)

def get_operations_from_transitions(transitions_dom):
    operation_list = []
    watched_operations = (
        "start", "stop", "promote", "demote", "migrate_from", "migrate_to"
    )
    for rsc_op in transitions_dom.getElementsByTagName("rsc_op"):
        primitives = rsc_op.getElementsByTagName("primitive")
        if not primitives:
            continue
        if rsc_op.getAttribute("operation").lower() not in watched_operations:
            continue
        for prim in primitives:
            prim_id = prim.getAttribute("id")
            operation_list.append((
                int(rsc_op.getAttribute("id")),
                {
                    "id": prim_id,
                    "long_id": prim.getAttribute("long-id") or prim_id,
                    "operation": rsc_op.getAttribute("operation").lower(),
                    "on_node": rsc_op.getAttribute("on_node"),
                }
            ))
    operation_list.sort(key=lambda x: x[0])
    op_list = [op[1] for op in operation_list]
    return op_list

def get_resources_location_from_operations(cib_dom, resources_operations):
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
            id_for_constraint = validate_constraint_resource(
                cib_dom, res_id
            )[2]
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
    locations_clean = dict([
        (key, val) for key, val in locations.items()
        if "start_on_node" in val or "promote_on_node" in val
    ])
    return locations_clean

def get_remote_quorumtool_output(node):
    return sendHTTPRequest(node, "remote/get_quorum_info", None, False, False)

# return True if quorumtool_output is a string returned when the node is off
def is_node_offline_by_quorumtool_output(quorum_info):
    return quorum_info.strip() == "Cannot initialize CMAP service"

def parse_quorumtool_output(quorumtool_output):
    parsed = {}
    in_node_list = False
    try:
        for line in quorumtool_output.splitlines():
            line = line.strip()
            if not line:
                continue
            if in_node_list:
                if line.startswith("-") or line.startswith("Nodeid"):
                    # skip headers
                    continue
                parts = line.split()
                if parts[0] == "0":
                    # this line has nodeid == 0, this is a qdevice line
                    parsed["qdevice_list"].append({
                        "name": parts[2],
                        "votes": int(parts[1]),
                        "local": False,
                    })
                else:
                    # this line has non-zero nodeid, this is a node line
                    parsed["node_list"].append({
                        "name": parts[3],
                        "votes": int(parts[1]),
                        "local": len(parts) > 4 and parts[4] == "(local)",
                    })
            else:
                if line == "Membership information":
                    in_node_list = True
                    parsed["node_list"] = []
                    parsed["qdevice_list"] = []
                    continue
                if not ":" in line:
                    continue
                parts = [x.strip() for x in line.split(":", 1)]
                if parts[0] == "Quorate":
                    parsed["quorate"] = parts[1].lower() == "yes"
                elif parts[0] == "Quorum":
                    match = re.match("(\d+).*", parts[1])
                    if match:
                        parsed["quorum"] = int(match.group(1))
                    else:
                        return None
    except (ValueError, IndexError):
        return None
    for required in ("quorum", "quorate", "node_list"):
        if required not in parsed:
            return None
    return parsed

# node_list - nodes to stop
# local - local node is going to be stopped
def is_node_stop_cause_quorum_loss(quorum_info, local=True, node_list=None):
    if not quorum_info["quorate"]:
        return False
    # sum the votes of nodes that are not going to be stopped
    votes_after_stop = 0
    for node_info in quorum_info.get("node_list", []):
        if local and node_info["local"]:
            continue
        if node_list and node_info["name"] in node_list:
            continue
        votes_after_stop += node_info["votes"]
    for qdevice_info in quorum_info.get("qdevice_list", []):
        votes_after_stop += qdevice_info["votes"]
    return votes_after_stop < quorum_info["quorum"]

def dom_prepare_child_element(dom_element, tag_name, id):
    dom = dom_element.ownerDocument
    child_elements = []
    for child in dom_element.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.tagName == tag_name:
            child_elements.append(child)

    if len(child_elements) == 0:
        child_element = dom.createElement(tag_name)
        child_element.setAttribute("id", find_unique_id(dom, id))
        dom_element.appendChild(child_element)
    else:
        child_element = child_elements[0]
    return child_element

def dom_update_nv_pair(dom_element, name, value, id_prefix=""):
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
    ret = []
    for ra_val in ra_values:
        if ra_val.count("=") != 0:
            split_val = ra_val.split("=", 1)
            ret.append((split_val[0],split_val[1]))
    return ret

def is_int(val):
    try:
        int(val)
        return True
    except ValueError:
        return False

def dom_update_utilization(dom_element, attributes, id_prefix=""):
    utilization = dom_prepare_child_element(
        dom_element,
        "utilization",
        id_prefix + dom_element.getAttribute("id") + "-utilization"
    )

    for name, value in sorted(attributes.items()):
        if value != "" and not is_int(value):
            err(
                "Value of utilization attribute must be integer: "
                "'{0}={1}'".format(name, value)
            )
        dom_update_nv_pair(
            utilization,
            name,
            value.strip(),
            utilization.getAttribute("id") + "-"
        )

def dom_update_meta_attr(dom_element, attributes):
    if not attributes:
        return

    meta_attributes = dom_prepare_child_element(
        dom_element,
        "meta_attributes",
        dom_element.getAttribute("id") + "-meta_attributes"
    )

    for name, value in attributes:
        dom_update_nv_pair(
            meta_attributes,
            name,
            value,
            meta_attributes.getAttribute("id") + "-"
        )

def get_utilization(element, filter_name=None):
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
    output = []
    for name, value in sorted(get_utilization(element, filter_name).items()):
        output.append(name + "=" + value)
    return " ".join(output)

def is_valid_cluster_property(prop_def_dict, property, value):
    if property not in prop_def_dict:
        raise UnknownPropertyException(
            "unknown cluster property: '{0}'".format(property)
        )
    return is_valid_cib_value(
        prop_def_dict[property]["type"],
        value,
        prop_def_dict[property].get("enum", [])
    )


def is_valid_cib_value(type, value, enum_options=[]):
    type = type.lower()
    if type == "enum":
        return value in enum_options
    if type == "boolean":
        return is_boolean(value)
    if type == "integer":
        return is_score(value)
    if type == "time":
        return get_timeout_seconds(value) is not None
    return True


def get_cluster_property_default(prop_def_dict, prop):
    if prop not in prop_def_dict:
        raise UnknownPropertyException(
            "unknown cluster property: '{0}'".format(prop)
        )
    return prop_def_dict[prop]["default"]


def get_cluster_properties_definition():
    # we don't want to change these properties
    banned_props = ["dc-version", "cluster-infrastructure"]
    basic_props = [
        "batch-limit", "no-quorum-policy", "symmetric-cluster", "enable-acl",
        "stonith-enabled", "stonith-action", "pe-input-series-max",
        "stop-orphan-resources", "stop-orphan-actions", "cluster-delay",
        "start-failure-is-fatal", "pe-error-series-max", "pe-warn-series-max"
        ]
    readable_names = {
        "batch-limit": "Batch Limit",
        "no-quorum-policy": "No Quorum Policy",
        "symmetric-cluster": "Symmetric",
        "stonith-enabled": "Stonith Enabled",
        "stonith-action": "Stonith Action",
        "cluster-delay": "Cluster Delay",
        "stop-orphan-resources": "Stop Orphan Resources",
        "stop-orphan-actions": "Stop Orphan Actions",
        "start-failure-is-fatal": "Start Failure is Fatal",
        "pe-error-series-max": "PE Error Storage",
        "pe-warn-series-max": "PE Warning Storage",
        "pe-input-series-max": "PE Input Storage",
        "enable-acl": "Enable ACLs"
    }
    sources = [
        {
            "name": "pengine",
            "path": settings.pengine_binary
        },
        {
            "name": "crmd",
            "path": settings.crmd_binary
        },
        {
            "name": "cib",
            "path": settings.cib_binary
        }
    ]
    definition = {}
    for source in sources:
        stdout, stderr, retval = cmd_runner().run([source["path"], "metadata"])
        if retval != 0:
            err("unable to run {0}\n{1}".format(source["name"], stderr))
        try:
            etree = ET.fromstring(stdout)
            for e in etree.findall("./parameters/parameter"):
                prop = get_cluster_property_from_xml(e)
                if prop["name"] not in banned_props:
                    prop["source"] = source["name"]
                    prop["advanced"] = prop["name"] not in basic_props
                    if prop["name"] in readable_names:
                        prop["readable_name"] = readable_names[prop["name"]]
                    else:
                        prop["readable_name"] = prop["name"]
                    definition[prop["name"]] = prop
        except xml.parsers.expat.ExpatError as e:
            err("unable to parse {0} metadata definition: {1}".format(
                source["name"],
                e
            ))
        except ET.ParseError as e:
            err("unable to parse {0} metadata definition: {1}".format(
                source["name"],
                e
            ))
    return definition


def get_cluster_property_from_xml(etree_el):
    property = {
        "name": etree_el.get("name", ""),
        "shortdesc": "",
        "longdesc": "",
    }
    for item in ["shortdesc", "longdesc"]:
        item_el = etree_el.find(item)
        if item_el is not None and item_el.text is not None:
            property[item] = item_el.text

    content = etree_el.find("content")
    if content is None:
        property["type"] = ""
        property["default"] = ""
    else:
        property["type"] = content.get("type", "")
        property["default"] = content.get("default", "")

    if property["type"] == "enum":
        property["enum"] = []
        if property["longdesc"]:
            values = property["longdesc"].split("  Allowed values: ")
            if len(values) == 2:
                property["enum"] = values[1].split(", ")
                property["longdesc"] = values[0]
        if property["default"] not in property["enum"]:
            property["enum"].append(property["default"])

    if property["longdesc"] == property["shortdesc"]:
        property["longdesc"] = ""
    return property

def get_lib_env():
    user = None
    groups = None
    if os.geteuid() == 0:
        for name in ("CIB_user", "CIB_user_groups"):
            if name in os.environ and os.environ[name].strip():
                value = os.environ[name].strip()
                if "CIB_user" == name:
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
            corosync_conf_data = open(conf).read()
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

def get_cli_env():
    user = None
    groups = None
    if os.geteuid() == 0:
        for name in ("CIB_user", "CIB_user_groups"):
            if name in os.environ and os.environ[name].strip():
                value = os.environ[name].strip()
                if "CIB_user" == name:
                    user = value
                else:
                    groups = value.split(" ")

    env = Env()
    env.user = user
    env.groups = groups
    env.known_hosts_getter = read_known_hosts_file
    env.debug = "--debug" in pcs_options
    env.request_timeout = pcs_options.get("--request-timeout")
    return env

def get_middleware_factory():
    return middleware.create_middleware_factory(
        cib=middleware.cib(filename if usefile else None, touch_cib_file),
        corosync_conf_existing=middleware.corosync_conf_existing(
            pcs_options.get("--corosync_conf", None)
        ),
        booth_conf=pcs.cli.booth.env.middleware_config(
            pcs_options.get("--name", DEFAULT_BOOTH_NAME),
            pcs_options.get("--booth-conf", None),
            pcs_options.get("--booth-key", None),
        ),
        cluster_conf_read_only=middleware.cluster_conf_read_only(
            pcs_options.get("--cluster_conf", None)
        ),
    )

def get_library_wrapper():
    return Library(get_cli_env(), get_middleware_factory())


def get_modifiers():
    #please keep in mind that this is not final implemetation
    #beside missing support of other possible options, cases may arise that can
    #not be solved using a dict - for example "wait" - maybe there will be
    #global default for it and maybe there will appear need for local default...
    #there is possible create class extending dict, so dict like access in
    #commands is not an issue
    return {
        "after": pcs_options.get("--after", None),
        "all": "--all" in pcs_options,
        "async": "--async" in pcs_options,
        "autocorrect": "--autocorrect" in pcs_options,
        "autodelete": "--autodelete" in pcs_options,
        "before": pcs_options.get("--before", None),
        "corosync_conf": pcs_options.get("--corosync_conf", None),
        "describe": "--nodesc" not in pcs_options,
        "device": pcs_options.get("--device", []),
        "disabled": "--disabled" in pcs_options,
        "enable": "--enable" in pcs_options,
        "encryption": pcs_options.get("--encryption", "0"),
        "force": "--force" in pcs_options,
        "full": "--full" in pcs_options,
        "group": pcs_options.get("--group", None),
        "monitor": "--monitor" in pcs_options,
        "name": pcs_options.get("--name", None),
        "no-default-ops": "--no-default-ops" in pcs_options,
        "skip_offline_nodes": "--skip-offline" in pcs_options,
        "start": "--start" in pcs_options,
        "wait": pcs_options.get("--wait", False),
        "watchdog": pcs_options.get("--watchdog", []),
    }

def exit_on_cmdline_input_errror(error, main_name, usage_name):
    if error and error.message:
        err(error.message)
    else:
        usage.show(main_name, [usage_name])
    sys.exit(1)

def get_report_processor():
    return LibraryReportProcessorToConsole(debug=("--debug" in pcs_options))

def get_set_properties(prop_name=None, defaults=None):
    properties = {} if defaults is None else dict(defaults)
    (output, retVal) = run(["cibadmin","-Q","--scope", "crm_config"])
    if retVal != 0:
        err("unable to get crm_config\n"+output)
    dom = parseString(output)
    de = dom.documentElement
    crm_config_properties = de.getElementsByTagName("nvpair")
    for prop in crm_config_properties:
        if prop_name is None or (prop_name == prop.getAttribute("name")):
            properties[prop.getAttribute("name")] = prop.getAttribute("value")
    return properties


def get_user_and_pass():
    if "-u" in pcs_options:
        username = pcs_options["-u"]
    else:
        username = get_terminal_input('Username: ')

    if "-p" in pcs_options:
        password = pcs_options["-p"]
    else:
        password = get_terminal_password()
    return username, password
