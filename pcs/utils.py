from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import subprocess
import ssl
import inspect
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
import fcntl
import getpass
import base64
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
        install_opener as urllib_install_opener,
        HTTPCookieProcessor as urllib_HTTPCookieProcessor,
        HTTPSHandler as urllib_HTTPSHandler,
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )
except ImportError:
    # python3
    from urllib.request import (
        build_opener as urllib_build_opener,
        install_opener as urllib_install_opener,
        HTTPCookieProcessor as urllib_HTTPCookieProcessor,
        HTTPSHandler as urllib_HTTPSHandler
    )
    from urllib.error import (
        HTTPError as urllib_HTTPError,
        URLError as urllib_URLError
    )

import settings
import resource
import cluster
import corosync_conf as corosync_conf_utils


PYTHON2 = sys.version[0] == "2"

# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options = {}
fence_bin = settings.fence_agent_binaries

score_regexp = re.compile(r'^[+-]?((INFINITY)|(\d+))$')

def simple_cache(func):
    cache = {}
    def wrapper(*args):
        if args not in cache:
            cache[args] = func()
        return cache[args]
    return wrapper

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
    else:
        cluster.cluster_upgrade()
        return True

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
# Returns a dictionary {'nodeA':'tokenA'}
def readTokens():
    tokens = {}
    output, retval = run_pcsdcli("read_tokens")
    if retval == 0 and output['status'] == 'ok' and output['data']:
        tokens = output['data']
    return tokens

# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    return sendHTTPRequest(node, 'remote/get_corosync_conf', None, False, False)

def setCorosyncConfig(node,config):
    if is_rhel6():
        data = urllib_urlencode({'cluster_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_cluster_conf', data)
        if status != 0:
            err("Unable to set cluster.conf: {0}".format(data))
    else:
        data = urllib_urlencode({'corosync_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_corosync_conf', data)
        if status != 0:
            err("Unable to set corosync config: {0}".format(data))

def startCluster(node, quiet=False):
    return sendHTTPRequest(node, 'remote/cluster_start', None, False, not quiet)

def stopCluster(node, quiet=False, pacemaker=True, corosync=True, force=True):
    data = dict()
    if pacemaker and not corosync:
        data["component"] = "pacemaker"
    elif corosync and not pacemaker:
        data["component"] = "corosync"
    if force:
        data["force"] = 1
    data = urllib_urlencode(data)
    return sendHTTPRequest(node, 'remote/cluster_stop', data, False, not quiet)

def enableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_enable', None, False, True)

def disableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_disable', None, False, True)

def destroyCluster(node, quiet=False):
    return sendHTTPRequest(node, 'remote/cluster_destroy', None, not quiet, not quiet)

def restoreConfig(node, tarball_data):
    data = urllib_urlencode({"tarball": tarball_data})
    return sendHTTPRequest(node, "remote/config_restore", data, False, True)

def pauseConfigSyncing(node, delay_seconds=300):
  data = urllib_urlencode({"sync_thread_pause": delay_seconds})
  return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)

def resumeConfigSyncing(node):
  data = urllib_urlencode({"sync_thread_resume": 1})
  return sendHTTPRequest(node, "remote/set_sync_options", data, False, False)

def canAddNodeToCluster(node):
    retval, output = sendHTTPRequest(
        node, 'remote/node_available', None, False, False
    )
    if retval == 0:
        try:
            myout = json.loads(output)
            if "notauthorized" in myout and myout["notauthorized"] == "true":
                return (False, "unable to authenticate to node")
            if "node_available" in myout and myout["node_available"] == True:
                return (True, "")
            else:
                return (False, "node is already in a cluster")
        except ValueError:
            return (False, "response parsing error")
    return (False, "error checking node availability: {0}".format(output))

def addLocalNode(node, node_to_add, ring1_addr=None):
    options = {'new_nodename': node_to_add}
    if ring1_addr:
        options['new_ring1addr'] = ring1_addr
    data = urllib_urlencode(options)
    retval, output = sendHTTPRequest(node, 'remote/add_node', data, False, False)
    if retval == 0:
        try:
            myout = json.loads(output)
            retval2 = myout[0]
            output = myout[1]
        except ValueError:
            return 1, output
        return retval2, output
    else:
        return 1, output

def removeLocalNode(node, node_to_remove, pacemaker_remove=False):
    data = urllib_urlencode({'remove_nodename':node_to_remove, 'pacemaker_remove':pacemaker_remove})
    retval, output = sendHTTPRequest(node, 'remote/remove_node', data, False, False)
    if retval == 0:
        try:
            myout = json.loads(output)
        except ValueError:
            return 1,output
        return 0, myout
    else:
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
def sendHTTPRequest(host, request, data = None, printResult = True, printSuccess = True):
    url = 'https://' + host + ':2224/' + request
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

    tokens = readTokens()
    if "--debug" in pcs_options:
        print("Sending HTTP Request to: " + url)
        print("Data: {0}".format(data))
    # python3 requires data to by bytes not str
    if data:
        data = data.encode("utf-8")

    # cookies
    cookies = []
    if host in tokens:
        cookies.append("token=" + tokens[host])
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
                    value = base64.b64encode(value)
                cookies.append("{0}={1}".format(name, value))
    if cookies:
        opener.addheaders.append(('Cookie', ";".join(cookies)))

    # send the request
    urllib_install_opener(opener)
    try:
        result = opener.open(url,data)
        # python3 returns bytes not str
        html = result.read().decode("utf-8")
        if printResult or printSuccess:
            print(host + ": " + html.strip())
        if "--debug" in pcs_options:
            print("Response Code: 0")
            print("--Debug Response Start--\n{0}".format(html), end="")
            print("--Debug Response End--")
            print()
        return (0,html)
    except urllib_HTTPError as e:
        if "--debug" in pcs_options:
            print("Response Code: " + str(e.code))
        if e.code == 401:
            output = (
                3,
                "Unable to authenticate to {node} - (HTTP error: {code}), try running 'pcs cluster auth'".format(
                    node=host, code=e.code
                )
            )
        elif e.code == 403:
            output = (
                4,
                "{node}: Permission denied - (HTTP error: {code})".format(
                    node=host, code=e.code
                )
            )
        else:
            output = (
                1,
                "Error connecting to {node} - (HTTP error: {code})".format(
                    node=host, code=e.code
                )
            )
        if printResult:
            print(output[1])
        return output
    except urllib_URLError as e:
        if "--debug" in pcs_options:
            print("Response Reason: " + str(e.reason))
        if printResult:
            print("Unable to connect to %s (%s)" % (host, e.reason))
        return (2,"Unable to connect to %s (%s)" % (host, e.reason))

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

def getNodesFromPacemaker():
    ret_nodes = []
    root = get_cib_etree()
    nodes = root.findall(str(".//node"))
    for node in nodes:
        ret_nodes.append(node.attrib["uname"])
    ret_nodes.sort()
    return ret_nodes

def getCorosyncConf(conf=None):
    if not conf:
        if is_rhel6():
            conf = settings.cluster_conf_file
        else:
            conf = settings.corosync_conf_file
    try:
        out = open(conf).read()
    except IOError as e:
        err("Unable to read %s: %s" % (conf, e.strerror))
    return out

def getCorosyncConfParsed(conf=None, text=None):
    conf_text = getCorosyncConf(conf) if text is None else text
    if is_rhel6():
        try:
            return parseString(conf_text)
        except xml.parsers.expat.ExpatError as e:
            err("Unable to parse cluster.conf: %s" % e)
    try:
        return corosync_conf_utils.parse_string(conf_text)
    except corosync_conf_utils.CorosyncConfException as e:
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
    if is_rhel6():
        output, retval = run(["cman_tool", "nodes", "-F", "type,name"])
        if retval != 0:
            return []
        nodestatus_re = re.compile(r"^(.)\s+([^\s]+)\s*$", re.M)
        return [
            node_name
            for node_status, node_name in nodestatus_re.findall(output)
                if node_status == "M"
        ]

    args = ["corosync-cmapctl"]
    nodes = []
    output,retval = run(args)
    if retval != 0:
        return []

    nodename_re = re.compile(r"^nodelist\.node\.(\d+)\.ring0_addr.*= (.*)", re.M)
    nodestatus_re = re.compile(r"^runtime\.totem\.pg\.mrp\.srp\.members\.(\d+).status.*= (.*)", re.M)
    nodenameid_mapping_re = re.compile(r"nodelist\.node\.(\d+)\.nodeid.*= (\d+)", re.M)
    
    nodes = nodename_re.findall(output)
    nodes_status = nodestatus_re.findall(output)
    nodes_mapping = nodenameid_mapping_re.findall(output)
    node_status = {}

    for orig_id, node in nodes:
        mapped_id = None
        for old_id, new_id in nodes_mapping:
            if orig_id == old_id:
                mapped_id = new_id
                break
        if mapped_id == None:
            print("Error mapping %s" % node)
            continue
        for new_id, status in nodes_status:
            if new_id == mapped_id:
                node_status[node] = status
                break

    nodes_active = []
    for node,status in node_status.items():
        if status == "joined":
            nodes_active.append(node)

    return nodes_active

# Add node specified to corosync.conf and reload corosync.conf (if running)
def addNodeToCorosync(node):
# Before adding, make sure node isn't already in corosync.conf
    node0, node1 = parse_multiring_node(node)
    used_node_ids = []
    num_nodes_in_conf = 0
    corosync_conf_text = getCorosyncConf()
    for c_node in getNodesFromCorosyncConf(conf_text=corosync_conf_text):
        if (c_node == node0) or (c_node == node1):
            err("node already exists in corosync.conf")
        num_nodes_in_conf = num_nodes_in_conf + 1
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
    new_node = corosync_conf_utils.Section("node")
    nodelist.add_section(new_node)
    new_node.add_attribute("ring0_addr", node0)
    if node1:
        new_node.add_attribute("ring1_addr", node1)
    new_node.add_attribute("nodeid", new_nodeid)

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

    output, retval = run(["ccs", "-i", "-f", settings.cluster_conf_file, "--addmethod", "pcmk-method", node0])
    if retval != 0:
        print(output)
        err("error adding fence method: %s" % node)

    output, retval = run(["ccs", "-i", "-f", settings.cluster_conf_file, "--addfenceinst", "pcmk-redirect", node0, "pcmk-method", "port="+node0])
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

def removeNodeFromCorosync(node):
    removed_node = False
    num_nodes_in_conf = 0
    node0, node1 = parse_multiring_node(node)

    corosync_conf = getCorosyncConfParsed()
    for nodelist in corosync_conf.get_sections("nodelist"):
        for node in nodelist.get_sections("node"):
            num_nodes_in_conf += 1
            ring0_attrs = node.get_attributes("ring0_addr")
            if ring0_attrs:
                ring0_conf = ring0_attrs[0][1]
                if (ring0_conf == node0) or (node1 and ring0_conf == node1):
                    node.parent.del_section(node)
                    removed_node = True

    if removed_node:
        corosync_conf = autoset_2node_corosync(corosync_conf)
        setCorosyncConf(str(corosync_conf))

    return removed_node

def removeNodeFromClusterConf(node):
    node0, node1 = parse_multiring_node(node)
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
    node_count = 0
    auto_tie_breaker = False

    for nodelist in corosync_conf.get_sections("nodelist"):
        node_count += len(nodelist.get_sections("node"))
    quorum_sections = corosync_conf.get_sections("quorum")
    for quorum in quorum_sections:
        for attr in quorum.get_attributes("auto_tie_breaker"):
            auto_tie_breaker = attr[1] == "1"

    if node_count == 2 and not auto_tie_breaker:
        for quorum in quorum_sections:
            quorum.set_attribute("two_node", "1")
        if not quorum_sections:
            quorum = corosync_conf_utils.Section("quorum")
            quorum.add_attribute("two_node", "1")
            corosync_conf.add_section(quorum)
    else:
        for quorum in quorum_sections:
            quorum.del_attributes_by_name("two_node")
    return corosync_conf

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

# Run command, with environment and return (output, retval)
def run(
    args, ignore_stderr=False, string_for_stdin=None, env_extend=None,
    binary_output=False
):
    if not env_extend:
        env_extend = dict()
    env_var = env_extend
    env_var.update(dict(os.environ))
    if usefile:
        env_var["CIB_file"] = filename

        if not os.path.isfile(filename):
            try:
                write_empty_cib(filename)
            except IOError:
                err("Unable to write to file: " + filename)

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
            env=env_var,
            # decodes newlines and in python3 also converts bytes to str
            universal_newlines=(not PYTHON2 and not binary_output)
        )
        output,stderror = p.communicate(string_for_stdin)
        returnVal = p.returncode
        if "--debug" in pcs_options:
            print("Return Value: {0}".format(returnVal))
            print("--Debug Output Start--\n{0}".format(output), end="")
            print("--Debug Output End--")
            print()
    except OSError as e:
        print(e.strerror)
        err("unable to locate command: " + args[0])

    return output, returnVal

def run_pcsdcli(command, data=None):
    if not data:
        data = dict()
    env_var = dict()
    if "--debug" in pcs_options:
        env_var["PCSD_DEBUG"] = "true"
    pcs_dir = os.path.realpath(os.path.dirname(sys.argv[0]))
    if pcs_dir == "/usr/sbin":
        pcsd_dir_path = settings.pcsd_exec_location
    else:
        pcsd_dir_path = os.path.join(pcs_dir, '../pcsd')
    pcsdcli_path = os.path.join(pcsd_dir_path, 'pcsd-cli.rb')
    gem_home = os.path.join(pcsd_dir_path, 'vendor/bundle/ruby')
    env_var["GEM_HOME"] = gem_home
    output, retval = run(
        ["/usr/bin/ruby", "-I" + pcsd_dir_path, pcsdcli_path, command],
        string_for_stdin=json.dumps(data),
        env_extend=env_var
    )
    try:
        output_json = json.loads(output)
        for key in ['status', 'text', 'data']:
            if key not in output_json:
                output_json[key] = None
    except ValueError:
        output_json = {
            'status': 'bad_json_output',
            'text': output,
            'data': None,
        }
    return output_json, retval

def call_local_pcsd(argv, interactive_auth=False, std_in=None):
    # some commands cannot be run under a non-root account
    # so we pass those commands to locally running pcsd to execute them
    # returns [list_of_errors, exit_code, stdout, stderr]
    data = {
        "command": json.dumps(argv),
    }
    if std_in:
        data['stdin'] = std_in
    data_send = urllib_urlencode(data)
    code, output = sendHTTPRequest(
        "localhost", "run_pcs", data_send, False, False
    )

    # authenticate against local pcsd and run again
    if interactive_auth and 3 == code: # not authenticated
        print('Please authenticate yourself to the local pcsd')
        username = get_terminal_input('Username: ')
        password = get_terminal_password()
        cluster.auth_nodes_do(["localhost"], username, password, True, True)
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

def run_node_threads(node_threads):
    error_list = []
    for node, thread in node_threads.items():
        thread.daemon = True
        thread.start()
    while node_threads:
        for node in list(node_threads.keys()):
            thread = node_threads[node]
            thread.join(1)
            if thread.is_alive():
                continue
            output = node + ": " + thread.output.strip()
            print(output)
            if thread.retval != 0:
                error_list.append(output)
            del node_threads[node]
    return error_list

# Check is something exists in the CIB, if it does return it, if not, return
#  an empty string
def does_exist(xpath_query):
    args = ["cibadmin", "-Q", "--xpath", xpath_query]
    output,retval = run(args)
    if (retval != 0):
        return False
    return True

def is_pacemaker_node(node):
    p_nodes = getNodesFromPacemaker()
    if node in p_nodes:
        return True
    return False

def is_corosync_node(node):
    c_nodes = getNodesFromCorosyncConf()
    if node in c_nodes:
        return True
    return False

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
    return dom_elem_get_resource_clone_ms_parent(resource)

def dom_elem_get_resource_clone_ms_parent(resource):
    clone = resource
    while True:
        if not isinstance(clone, xml.dom.minidom.Element):
            return None
        if clone.tagName in ["clone", "master"]:
            return clone
        clone = clone.parentNode

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
def validate_constraint_resource(dom, resource_id):
    resource_el = (
        dom_get_clone(dom, resource_id)
        or
        dom_get_master(dom, resource_id)
    )
    if resource_el:
        # clone and master is always valid
        return True, "", resource_id

    resource_el = (
        dom_get_resource(dom, resource_id)
        or
        dom_get_group(dom, resource_id)
    )
    if not resource_el:
        return False, "Resource '%s' does not exist" % resource_id, None

    clone_el = dom_get_resource_clone_ms_parent(dom, resource_id)
    if not clone_el:
        # primitive and group is valid if not in clone nor master
        return True, "", resource_id

    if "--force" in pcs_options:
        return (
            True,
            "",
            clone_el.getAttribute("id") if clone_el else resource_id
        )

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
    return True, "", resource_id


def dom_get_resource_remote_node_name(dom_resource):
    if dom_resource.tagName != "primitive":
        return None
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

def dom_get_parent_by_tag_name(dom_el, tag_name):
    parent = dom_el.parentNode
    while parent:
        if not isinstance(parent, xml.dom.minidom.Element):
            return None
        if parent.tagName == tag_name:
            return parent
        parent = parent.parentNode
    return None

def dom_attrs_to_list(dom_el, with_id=False):
    attributes = [
        "%s=%s" % (name, value)
        for name, value in dom_el.attributes.items() if name != "id"
    ]
    if with_id:
        attributes.append("(id:%s)" % (dom_el.getAttribute("id")))
    return attributes

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

def does_resource_have_options(ra_type):
    if ra_type.startswith("ocf:") or ra_type.startswith("stonith:") or ra_type.find(':') == -1:
        return True
    return False

# Given a resource agent (ocf:heartbeat:XXX) return an list of default
# operations or an empty list if unable to find any default operations
def get_default_op_values(ra_type):
    allowable_operations = ["monitor","start","stop","promote","demote"]
    ra_split = ra_type.split(':')
    if len(ra_split) != 3:
        return []

    ra_path = "/usr/lib/ocf/resource.d/" + ra_split[1] + "/" + ra_split[2]
    metadata = get_metadata(ra_path)

    if metadata == False:
        return []

    return_list = []
    try:
        root = ET.fromstring(metadata)
        actions = root.findall(str(".//actions/action"))
        for action in actions:
            if action.attrib["name"] in allowable_operations:
                new_operation = []
                new_operation.append(action.attrib["name"])
                for attrib in action.attrib:
                    value = action.attrib[attrib]
                    if attrib == "name" or (attrib == "depth" and value == "0"):
                        continue
                    new_operation.append(attrib + "=" + value)
                return_list.append(new_operation)
    except xml.parsers.expat.ExpatError as e:
        err("Unable to parse xml for '%s': %s" % (ra_type, e))
    except xml.etree.ElementTree.ParseError as e:
        err("Unable to parse xml for '%s': %s" % (ra_type, e))

    return return_list

def get_timeout_seconds(timeout, return_unknown=False):
    if timeout.isdigit():
        return int(timeout)
    suffix_multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
    }
    for suffix, multiplier in suffix_multiplier.items():
        if timeout.endswith(suffix) and timeout[:-len(suffix)].isdigit():
            return int(timeout[:-len(suffix)]) * multiplier
    return timeout if return_unknown else None

def check_pacemaker_supports_resource_wait():
    output, retval = run(["crm_resource", "-?"])
    if "--wait" not in output:
        err("crm_resource does not support --wait, please upgrade pacemaker")

def validate_wait_get_timeout():
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

# Check and see if the specified resource (or stonith) type is present on the
# file system and properly responds to a meta-data request
def is_valid_resource(resource, caseInsensitiveCheck=False):
    if resource.startswith("ocf:"):
        resource_split = resource.split(":",3)
        if len(resource_split) != 3:
            err("ocf resource definition (" + resource + ") does not match the ocf:provider:name pattern")
        providers = [resource_split[1]]
        resource = resource_split[2]
    elif resource.startswith("stonith:"):
        resource_split = resource.split(":", 2)
        stonith = resource_split[1]
        metadata = get_stonith_metadata("/usr/sbin/" + stonith)
        if metadata != False:
            return True
        else:
            return False
    elif resource.startswith("nagios:"):
        # search for nagios script
        resource_split = resource.split(":", 2)
        if os.path.isfile("/usr/share/pacemaker/nagios/plugins-metadata/%s.xml" % resource_split[1]):
            return True
        else:
            return False
    elif resource.startswith("lsb:"):
        resource_split = resource.split(":",2)
        lsb_ra = resource_split[1]
        if os.path.isfile("/etc/init.d/" + lsb_ra):
            return True
        else:
            return False
    elif resource.startswith("systemd:"):
        resource_split = resource.split(":",2)
        systemd_ra = resource_split[1]
        if os.path.isfile("/usr/lib/systemd/system/" + systemd_ra + ".service"):
            return True
        else:
            return False
    else:
        providers = sorted(os.listdir("/usr/lib/ocf/resource.d"))

    # search for ocf script
    for provider in providers:
        filepath = "/usr/lib/ocf/resource.d/" + provider + "/"
        if caseInsensitiveCheck:
            if os.path.isdir(filepath):
                all_files = [ f for f in os.listdir(filepath ) ]
                for f in all_files:
                    if f.lower() == resource.lower() and os.path.isfile(filepath + f):
                        return "ocf:" + provider + ":" + f
                continue

        metadata = get_metadata(filepath + resource)
        if metadata == False:
            continue
        else:
            # found it
            return True

    return False

# Get metadata from resource agent
def get_metadata(resource_agent_script):
    os.environ['OCF_ROOT'] = "/usr/lib/ocf/"
    if (not os.path.isfile(resource_agent_script)) or (not os.access(resource_agent_script, os.X_OK)):
        return False

    (metadata, retval) = run([resource_agent_script, "meta-data"],True)
    if retval == 0:
        return metadata
    else:
        return False

def get_stonith_metadata(fence_agent_script):
    if (not os.path.isfile(fence_agent_script)) or (not os.access(fence_agent_script, os.X_OK)):
        return False
    (metadata, retval) = run([fence_agent_script, "-o", "metadata"], True)
    if retval == 0:
        return metadata
    else:
        return False

def get_default_stonith_options():
    (metadata, retval) = run([settings.stonithd_binary, "metadata"],True)
    if retval == 0:
        root = ET.fromstring(metadata)
        params = root.findall(str(".//parameter"))
        default_params = []
        for param in params:
            adv_param = False
            for short_desc in param.findall(str(".//shortdesc")):
                if short_desc.text.startswith("Advanced use only"):
                    adv_param = True
            if adv_param == False:
                default_params.append(param)
        return default_params
    else:
        return []

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
        new_dom = ET.tostring(dom)
    else:
        new_dom = dom.toxml()
    output, retval = run(["cibadmin", "--replace", "-o", "configuration", "-V", "--xml-pipe"],False,new_dom)
    if retval != 0:
        err("Unable to update cib\n"+output)

def is_valid_cib_scope(scope):
    return scope in [
        "configuration", "nodes", "resources", "constraints", "crm_config",
        "rsc_defaults", "op_defaults", "status",
    ]

# Checks to see if id exists in the xml dom passed
def does_id_exist(dom, check_id):
    if is_etree(dom):
        for elem in dom.findall(str(".//*")):
            if elem.get("id") == check_id:
                return True
    else:
        all_elem = dom.getElementsByTagName("*")
        for elem in all_elem:
            if elem.getAttribute("id") == check_id:
                return True
    return False

# Returns check_id if it doesn't exist in the dom, otherwise it adds an integer
# to the end of the id and increments it until a unique id is found
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

def is_valid_property(prop):
    output, retval = run([settings.pengine_binary, "metadata"])
    if retval != 0:
        err("unable to run pengine\n" + output)

# whitelisted properties
    if prop in ["enable-acl"]:
        return True

    dom = parseString(output)
    properties = dom.getElementsByTagName("parameter");
    for p in properties:
        if p.getAttribute("name") == prop:
            return True

    output, retval = run([settings.crmd_binary, "metadata"])
    if retval != 0:
        err("unable to run crmd\n" + output)

    dom = parseString(output)
    properties = dom.getElementsByTagName("parameter");
    for p in properties:
        if p.getAttribute("name") == prop:
            return True

    output, retval = run([settings.cib_binary, "metadata"])
    if retval != 0:
        err("unable to run cib\n" + output)

    dom = parseString(output)
    properties = dom.getElementsByTagName("parameter");
    for p in properties:
        if p.getAttribute("name") == prop:
            return True

    return False

def get_node_attributes():
    node_config = get_cib_xpath("//nodes")
    nas = {}
    if (node_config == ""):
        err("unable to get crm_config, is pacemaker running?")
    dom = parseString(node_config).documentElement
    for node in dom.getElementsByTagName("node"):
        nodename = node.getAttribute("uname")
        for attributes in node.getElementsByTagName("instance_attributes"):
            for nvp in attributes.getElementsByTagName("nvpair"):
                if nodename not in nas:
                    nas[nodename] = []
                nas[nodename].append(nvp.getAttribute("name") + "=" + nvp.getAttribute("value"))
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
def set_cib_property(prop, value):
    crm_config = get_cib_xpath("//crm_config")
    if (crm_config == ""):
        err("unable to get crm_config, is pacemaker running?")
    property_found = False
    document = parseString(crm_config)
    crm_config = document.documentElement
    cluster_property_set = crm_config.getElementsByTagName("cluster_property_set")
    if len(cluster_property_set) == 0:
        cluster_property_set = document.createElement("cluster_property_set")
        cluster_property_set.setAttribute("id", "cib-bootstrap-options")
        crm_config.appendChild(cluster_property_set) 
    else:
        cluster_property_set = cluster_property_set[0]
    for child in cluster_property_set.getElementsByTagName("nvpair"):
        if (child.nodeType != xml.dom.minidom.Node.ELEMENT_NODE):
            break
        if (child.getAttribute("name") == prop):
            child.parentNode.removeChild(child)
            property_found = True
            break

# If the value is empty we don't add it to the cluster
    if value != "":
        new_property = document.createElement("nvpair")
        new_property.setAttribute("id","cib-bootstrap-options-"+prop)
        new_property.setAttribute("name",prop)
        new_property.setAttribute("value",value)
        cluster_property_set.appendChild(new_property)
    elif not property_found and "--force" not in pcs_options:
        err("can't remove property: '%s' that doesn't exist" % (prop))

    replace_cib_configuration(crm_config)

def setAttribute(a_type, a_name, a_value):
    args = ["crm_attribute", "--type", a_type, "--attr-name", a_name,
            "--attr-value", a_value]

    if a_value == "":
        args.append("-D")

    output, retval = run(args)
    if retval != 0:
        print(output)

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
        sys.stdout.write('Username: ')
        sys.stdout.flush()
    if PYTHON2:
        return raw_input("")
    else:
        return input("")

def get_terminal_password(message="Password: "):
    if sys.stdout.isatty():
        return getpass.getpass(message)
    else:
        return get_terminal_input(message)

# Returns an xml dom containing the current status of the cluster
def getClusterState():
    (output, retval) = run(["crm_mon", "-1", "-X","-r"])
    if (retval != 0):
        err("error running crm_mon, is pacemaker running?")
    dom = parseString(output)
    return dom

def getNodeAttributes():
    dom = get_cib_dom()
    nodes = dom.getElementsByTagName("node")


# Returns true if stonith-enabled is not false/off & no stonith devices exist
# So if the cluster can't start due to missing stonith devices return true
def stonithCheck():
    et = get_cib_etree()
    cps = et.find("configuration/crm_config/cluster_property_set")
    if cps != None:
        for prop in cps.findall(str("nvpair")):
            if 'name' in prop.attrib and prop.attrib["name"] == "stonith-enabled":
                if prop.attrib["value"] == "off" or \
                        prop.attrib["value"] == "false":
                    return False
        
    primitives = et.findall(str("configuration/resources/primitive"))
    for p in primitives:
        if p.attrib["class"] == "stonith":
            return False

    primitives = et.findall(str("configuration/resources/clone/primitive"))
    for p in primitives:
        if p.attrib["class"] == "stonith":
            return False

    return True

def getCorosyncNodesID(allow_failure=False):
    if os.getuid() == 0:
        if is_rhel6():
            output, retval = run(["cman_tool", "nodes", "-F", "id,name"])
            if retval != 0:
                if allow_failure:
                    return {}
                else:
                    err("unable to get list of corosync nodes")
            nodeid_re = re.compile(r"^(.)\s+([^\s]+)\s*$", re.M)
            return dict([
                (node_id, node_name)
                for node_id, node_name in nodeid_re.findall(output)
            ])

        (output, retval) = run(['corosync-cmapctl', '-b', 'nodelist.node'])
    else:
        err_msgs, retval, output, std_err = call_local_pcsd(
            ['status', 'nodes', 'corosync-id'], True
        )
        if err_msgs:
            for msg in err_msgs:
                err(msg, False)
            sys.exit(1)

    if retval != 0:
        if allow_failure:
            return {}
        else:
            err("unable to get list of corosync nodes")

    cs_nodes = {}
    node_list_node_mapping = {}
    for line in output.rstrip().split("\n"):
        m = re.match("nodelist.node.(\d+).nodeid.*= (.*)",line)
        if m:
            node_list_node_mapping[m.group(1)] = m.group(2)

    for line in output.rstrip().split("\n"):
        m = re.match("nodelist.node.(\d+).ring0_addr.*= (.*)",line)
        if m:
            cs_nodes[node_list_node_mapping[m.group(1)]] = m.group(2)
    return cs_nodes

# Warning, if a node has never started the hostname may be '(null)'
#TODO This doesn't work on CMAN clusters at all and should be removed completely
def getPacemakerNodesID(allow_failure=False):
    if os.getuid() == 0:
        (output, retval) = run(['crm_node', '-l'])
    else:
        err_msgs, retval, output, std_err = call_local_pcsd(
            ['status', 'nodes', 'pacemaker-id'], True
        )
        if err_msgs:
            for msg in err_msgs:
                err(msg, False)
            sys.exit(1)

    if retval != 0:
        if allow_failure:
            return {}
        else:
            err("unable to get list of pacemaker nodes")

    pm_nodes = {}
    for line in output.rstrip().split("\n"):
        node_info = line.rstrip().split(" ")
        if len(node_info) <= 2 or node_info[2] != "lost":
            pm_nodes[node_info[0]] = node_info[1]

    return pm_nodes

def corosyncPacemakerNodeCheck():
    # does not work on CMAN clusters
    pm_nodes = getPacemakerNodesID()
    cs_nodes = getCorosyncNodesID()

    for node_id in pm_nodes:
        if pm_nodes[node_id] == "(null)":
            continue

        if node_id not in cs_nodes:
            continue

        if pm_nodes[node_id] == cs_nodes[node_id]:
            continue

        return True
    return False

def getResourceType(resource):
    resClass = resource.getAttribute("class")
    resProvider = resource.getAttribute("provider")
    resType = resource.getAttribute("type")
    return resClass + ":" + resProvider + ":" + resType

# Returns empty array if all attributes are valid, otherwise return an array
# of bad attributes
# res_id is the resource id
# ra_values is an array of 2 item tuples (key, value)
# resource is a python minidom element of the resource from the cib
def validInstanceAttributes(res_id, ra_values, resource_type):
    ra_values = dict(ra_values)
    found = False
    stonithDevice = False
    resSplit = resource_type.split(":")
    if len(resSplit) == 2:
        (resClass, resType) = resSplit
        metadata = get_stonith_metadata(fence_bin + resType)
        stonithDevice = True
    else:
        (resClass, resProvider, resType) = resource_type.split(":")
        metadata = get_metadata("/usr/lib/ocf/resource.d/" + resProvider + "/" + resType)

    if metadata == False:
        err("Unable to find resource: ocf:%s:%s" % (resProvider, resType))

    missing_required_parameters = []
    valid_parameters = ["pcmk_host_list", "pcmk_host_map", "pcmk_host_check", "pcmk_host_argument", "pcmk_arg_map", "pcmk_list_cmd", "pcmk_status_cmd", "pcmk_monitor_cmd"]
    valid_parameters = valid_parameters + ["stonith-timeout", "priority", "timeout"]
    valid_parameters = valid_parameters + ["pcmk_reboot_action", "pcmk_poweroff_action", "pcmk_list_action", "pcmk_monitor_action", "pcmk_status_action"]
    for a in ["off","on","status","list","metadata","monitor", "reboot"]:
        valid_parameters.append("pcmk_" + a + "_action")
        valid_parameters.append("pcmk_" + a + "_timeout")
        valid_parameters.append("pcmk_" + a + "_retries")
    bad_parameters = []
    try:
        actions = ET.fromstring(metadata).find("parameters")
        for action in actions.findall(str("parameter")):
            valid_parameters.append(action.attrib["name"])
            if "required" in action.attrib and action.attrib["required"] == "1":
# If a default value is set, then the attribute isn't really required (for 'action' on stonith devices only)
                default_exists = False
                if action.attrib["name"] == "action" and stonithDevice:
                    for ch in action:
                        if ch.tag == "content" and "default" in ch.attrib:
                            default_exists = True
                            break

                if not default_exists:
                    missing_required_parameters.append(action.attrib["name"])
    except xml.parsers.expat.ExpatError as e:
        err("Unable to parse xml for '%s': %s" % (resource_type, e))
    except xml.etree.ElementTree.ParseError as e:
        err("Unable to parse xml for '%s': %s" % (resource_type, e))
    for key,value in ra_values.items():
        if key not in valid_parameters:
            bad_parameters.append(key)
        if key in missing_required_parameters:
            missing_required_parameters.remove(key)

    if missing_required_parameters:
        if resClass == "stonith" and "port" in missing_required_parameters:
            # Temporarily make "port" an optional parameter. Once we are
            # getting metadata from pacemaker, this will be reviewed and fixed.
            #if (
            #    "pcmk_host_argument" in ra_values
            #    or
            #    "pcmk_host_map" in ra_values
            #    or
            #    "pcmk_host_list" in ra_values
            #):
            missing_required_parameters.remove("port")

    return bad_parameters, missing_required_parameters 

def getClusterName():
    if is_rhel6():
        try:
            dom = parse(settings.cluster_conf_file)
        except (IOError,xml.parsers.expat.ExpatError):
            return ""

        return dom.documentElement.getAttribute("name")
    else:
        try:
            f = open(settings.corosync_conf_file,'r')
            conf = corosync_conf_utils.parse_string(f.read())
            f.close()
            # mimic corosync behavior - the last cluster_name found is used
            cluster_name = None
            for totem in conf.get_sections("totem"):
                for attrs in totem.get_attributes("cluster_name"):
                    cluster_name = attrs[1]
            if cluster_name:
                return cluster_name
        except (IOError, corosync_conf_utils.CorosyncConfException) as e:
            return ""

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
    return score_regexp.match(var) is not None

def validate_xml_id(var, description="id"):
    # see NCName definition
    # http://www.w3.org/TR/REC-xml-names/#NT-NCName
    # http://www.w3.org/TR/REC-xml/#NT-Name
    if len(var) < 1:
        return False, "%s cannot be empty" % description
    first_char_re = re.compile("[a-zA-Z_]")
    if not first_char_re.match(var[0]):
        return (
            False,
            "invalid %s '%s', '%s' is not a valid first character for a %s"
                % (description, var, var[0], description)
        )
    char_re = re.compile("[a-zA-Z0-9_.-]")
    for char in var[1:]:
        if not char_re.match(char):
            return (
                False,
                "invalid %s '%s', '%s' is not a valid character for a %s"
                    % (description, var, char, description)
            )
    return True, ""

def is_iso8601_date(var):
    # using pacemaker tool to check if a value is a valid pacemaker iso8601 date
    output, retVal = run(["iso8601", "-d", var])
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

# Does pacemaker consider a variable as true in cib?
# See crm_is_true in pacemaker/lib/common/utils.c
def is_cib_true(var):
    return var.lower() in ("true", "on", "yes", "y", "1")

def is_systemctl():
    systemctl_paths = [
        '/usr/bin/systemctl',
        '/bin/systemctl',
        '/var/run/systemd/system',
    ]
    for path in systemctl_paths:
        if os.path.exists(path):
            return True
    return False

@simple_cache
def is_rhel6():
    # Checking corosync version works in most cases and supports non-rhel
    # distributions as well as running (manually compiled) corosync2 on rhel6.
    # - corosync2 does not support cman at all
    # - corosync1 runs with cman on rhel6
    # - corosync1 can be used without cman, but we don't support it anyways
    # - corosync2 is the default result if errors occur
    output, retval = run(["corosync", "-v"])
    if retval != 0:
        return False
    match = re.search(r"version\D+(\d+)", output)
    return match and match.group(1) == "1"

def err(errorText, exit_after_error=True):
    sys.stderr.write("Error: %s\n" % errorText)
    if exit_after_error:
        sys.exit(1)

def serviceStatus(prefix):
    if is_systemctl():
        print("Daemon Status:")
        daemons = ["corosync", "pacemaker", "pcsd"]
        out, ret = run(["systemctl", "is-active"] + daemons)
        status = out.split("\n")
        out, ret = run(["systemctl", "is-enabled"]+ daemons)
        enabled = out.split("\n")
        for i in range(len(daemons)):
            print(prefix + daemons[i] + ": " + status[i] + "/" + enabled[i])

def enableServices():
    if is_rhel6():
        run(["chkconfig", "pacemaker", "on"])
    else:
        if is_systemctl():
            run(["systemctl", "enable", "corosync.service"])
            run(["systemctl", "enable", "pacemaker.service"])
        else:
            run(["chkconfig", "corosync", "on"])
            run(["chkconfig", "pacemaker", "on"])

def disableServices():
    if is_rhel6():
        run(["chkconfig", "pacemaker", "off"])
        run(["chkconfig", "corosync", "off"]) # Left here for users of old pcs
                                              # which enabled corosync
    else:
        if is_systemctl():
            run(["systemctl", "disable", "corosync.service"])
            run(["systemctl", "disable", "pacemaker.service"])
        else:
            run(["chkconfig", "corosync", "off"])
            run(["chkconfig", "pacemaker", "off"])

def write_file(path, data, permissions=0o644, binary=False):
    if os.path.exists(path):
        if not "--force" in pcs_options:
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
    if (
        is_rhel6()
        and
        ":" in quorum_info
        and
        quorum_info.split(":", 1)[1].strip()
        ==
        "Cannot open connection to cman, is it running ?"
    ):
        return True
    if (
        not is_rhel6()
        and
        quorum_info.strip() == "Cannot initialize CMAP service"
    ):
        return True
    return False

def parse_cman_quorum_info(cman_info):
# get cman_info like this:
# cman_tool status
# echo ---Votes---
# cman_tool nodes -F id,type,votes,name
    parsed = {}
    in_node_list = False
    local_node_id = ""
    try:
        for line in cman_info.split("\n"):
            line = line.strip()
            if not line:
                continue
            if in_node_list:
                # node list command: cman_tool nodes -F id,type,votes,name
                parts = line.split()
                if parts[1] != "M" and parts[1] != "d":
                    continue # node is not online
                parsed["node_list"].append({
                    "name": parts[3],
                    "votes": int(parts[2]),
                    "local": local_node_id == parts[0]
                })
            else:
                if line == "---Votes---":
                    in_node_list = True
                    parsed["node_list"] = []
                    continue
                if not ":" in line:
                    continue
                parts = [x.strip() for x in line.split(":", 1)]
                if parts[0] == "Quorum":
                    parsed["quorate"] = "Activity blocked" not in parts[1]
                    match = re.match("(\d+).*", parts[1])
                    if match:
                        parsed["quorum"] = int(match.group(1))
                    else:
                        return None
                elif parts[0] == "Node ID":
                    local_node_id = parts[1]
    except (ValueError, IndexError):
        return None
    for required in ("quorum", "quorate", "node_list"):
        if required not in parsed:
            return None
    return parsed

def parse_quorumtool_output(quorumtool_output):
    parsed = {}
    in_node_list = False
    try:
        for line in quorumtool_output.split("\n"):
            line = line.strip()
            if not line:
                continue
            if in_node_list:
                if line.startswith("-") or line.startswith("Nodeid"):
                    # skip headers
                    continue
                parts = line.split()
                parsed["node_list"].append({
                    "name": parts[3],
                    "votes": int(parts[1]),
                    "local": len(parts) > 4 and parts[4] == "(local)"
                })
            else:
                if line == "Membership information":
                    in_node_list = True
                    parsed["node_list"] = []
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
    return votes_after_stop < quorum_info["quorum"]

def dom_prepare_child_element(dom_element, tag_name, id_prefix=""):
    dom = dom_element.ownerDocument
    child_elements = []
    for child in dom_element.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.tagName == tag_name:
            child_elements.append(child)

    if len(child_elements) == 0:
        child_element = dom.createElement(tag_name)
        child_element.setAttribute(
            "id", id_prefix + tag_name
        )
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
        id_prefix + dom_element.getAttribute("id") + "-"
    )

    for name, value in attributes:
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
    meta_attributes = dom_prepare_child_element(
        dom_element, "meta_attributes", dom_element.getAttribute("id") + "-"
    )

    for name, value in attributes:
        dom_update_nv_pair(
            meta_attributes,
            name,
            value,
            meta_attributes.getAttribute("id") + "-"
        )

def get_utilization(element):
    utilization = {}
    for e in element.getElementsByTagName("utilization"):
        for u in e.getElementsByTagName("nvpair"):
            name = u.getAttribute("name")
            value = u.getAttribute("value") if u.hasAttribute("value") else ""
            utilization[name] = value
        # Use just first element of utilization attributes. We don't support
        # utilization with rules just yet.
        break
    return utilization

def get_utilization_str(element):
    output = []
    for name, value in sorted(get_utilization(element).items()):
        output.append(name + "=" + value)
    return " ".join(output)
