import os, subprocess
import sys
import pcs
import xml.dom.minidom
import urllib,urllib2
from xml.dom.minidom import parseString,parse
import xml.etree.ElementTree as ET
import re
import json
import tempfile
import settings
import resource
import signal
import time
import cStringIO
import tarfile
import cluster
import prop
import fcntl


# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options = {}
fence_bin = settings.fence_agent_binaries

score_regexp = re.compile(r'^[+-]?((INFINITY)|(\d+))$')

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
    out = sendHTTPRequest(node, 'remote/check_auth', None, False, False)
    return out

def tokenFile():
    if 'PCS_TOKEN_FILE' in os.environ:
        return os.environ['PCS_TOKEN_FILE']
    else:
        if os.getuid() == 0:
            return "/var/lib/pcsd/tokens"
        else:
            return os.path.expanduser("~/.pcs/tokens")

def updateToken(node,nodes,username,password):
    count = 0
    orig_data = {}
    for n in nodes:
        orig_data["node-"+str(count)] = n
        count = count + 1
    orig_data["username"] = username
    orig_data["password"] = password
    if "--local" not in pcs_options and node != os.uname()[1]:
        orig_data["bidirectional"] = 1

    if "--force" in pcs_options:
        orig_data["force"] = 1

    data = urllib.urlencode(orig_data)
    out = sendHTTPRequest(node, 'remote/auth', data, False, False)
    if out[0] != 0:
        err("%s: Unable to connect to pcsd: %s" % (node, out[1]), False)
        return False
    token = out[1]
    if token == "":
        err("%s: Username and/or password is incorrect" % node, False)
        return False

    tokens = readTokens()
    tokens[node] = token
    writeTokens(tokens)

    return True

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
    tokenfile = tokenFile()
    tokens = {}
    f = None
    if not os.path.isfile(tokenfile):
        return tokens
    try:
        f = open(tokenfile, "r")
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        tokens = json.load(f)
    except:
        pass
    finally:
        if f is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()
    return tokens

# Takes a dictionary {'nodeA':'tokenA'}
def writeTokens(tokens):
    tokenfile = tokenFile()
    f = None
    if not os.path.isfile(tokenfile) and 'PCS_TOKEN_FILE' not in os.environ:
        if not os.path.exists(os.path.dirname(tokenfile)):
            os.makedirs(os.path.dirname(tokenfile),0700)
    try:
        f = os.fdopen(os.open(tokenfile, os.O_WRONLY | os.O_CREAT, 0600), "w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        f.truncate()
        json.dump(tokens, f)
    except Exception as ex:
        err("Failed to store tokens into file '%s': %s" % (tokenfile, ex.message))
    finally:
        if f is not None:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()

# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    retval, output = sendHTTPRequest(node, 'remote/get_corosync_conf', None, False, False)
    return retval,output

def setCorosyncConfig(node,config):
    if is_rhel6():
        data = urllib.urlencode({'cluster_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_cluster_conf', data)
        if status != 0:
            err("Unable to set cluster.conf")
    else:
        data = urllib.urlencode({'corosync_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_corosync_conf', data)
        if status != 0:
            err("Unable to set corosync config")

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
    data = urllib.urlencode(data)
    return sendHTTPRequest(node, 'remote/cluster_stop', data, False, not quiet)

def enableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_enable', None, False, True)

def disableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_disable', None, False, True)

def destroyCluster(node, quiet=False):
    return sendHTTPRequest(node, 'remote/cluster_destroy', None, not quiet, not quiet)

def restoreConfig(node, tarball_data):
    data = urllib.urlencode({"tarball": tarball_data})
    return sendHTTPRequest(node, "remote/config_restore", data, False, True)

def canAddNodeToCluster(node):
    retval, output = sendHTTPRequest(node, 'remote/node_available', [], False, False)
    if retval == 0:
        try:
            myout = json.loads(output)
            if "notauthorized" in myout and myout["notauthorized"] == "true":
                return (False, "unable to authenticate to node")
            if "node_available" in myout and myout["node_available"] == True:
                return (True,"")
            else:
                return (False,"node is already in a cluster")
        except ValueError:
            return (False, "response parsing error")

    return (False,"error checking node availability")

def addLocalNode(node, node_to_add, ring1_addr=None):
    options = {'new_nodename': node_to_add}
    if ring1_addr:
        options['new_ring1addr'] = ring1_addr
    data = urllib.urlencode(options)
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
    data = urllib.urlencode({'remove_nodename':node_to_remove, 'pacemaker_remove':pacemaker_remove})
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
def sendHTTPRequest(host, request, data = None, printResult = True, printSuccess = True):
    url = 'https://' + host + ':2224/' + request
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
    tokens = readTokens()
    if "--debug" in pcs_options:
        print "Sending HTTP Request to: " + url
        print "Data: " + str(data)
    if host in tokens:
        opener.addheaders.append(('Cookie', 'token='+tokens[host]))
    urllib2.install_opener(opener)
    try:
        result = opener.open(url,data)
        html = result.read()
        if printResult or printSuccess:
            print host + ": " + html.strip()
        if "--debug" in pcs_options:
            print "Response Code: 0"
            print "--Debug Response Start--\n" + html,
            print "--Debug Response End--"
        return (0,html)
    except urllib2.HTTPError, e:
        if "--debug" in pcs_options:
            print "Response Code: " + str(e.code)
        if printResult:
            if e.code == 401:
                print "Unable to authenticate to %s - (HTTP error: %d), try running 'pcs cluster auth'" % (host,e.code)
            else:
                print "Error connecting to %s - (HTTP error: %d)" % (host,e.code)
        if e.code == 401:
            return (3,"Unable to authenticate to %s - (HTTP error: %d), try running 'pcs cluster auth'" % (host,e.code))
        else:
            return (1,"Error connecting to %s - (HTTP error: %d)" % (host,e.code))
    except urllib2.URLError, e:
        if "--debug" in pcs_options:
            print "Response Reason: " + str(e.reason)
        if printResult:
            print "Unable to connect to %s (%s)" % (host, e.reason)
        return (2,"Unable to connect to %s (%s)" % (host, e.reason))

def getNodesFromCorosyncConf(conf_text=None):
    if is_rhel6():
        try:
            dom = (
                parse(settings.cluster_conf_file) if conf_text is None
                else parseString(conf_text)
            )
        except IOError:
            err("Unable to open cluster.conf file to get nodes list")
        return [
            node_el.getAttribute("name")
            for node_el in dom.getElementsByTagName("clusternode")
        ]

    nodes = []
    corosync_conf = getCorosyncConf() if conf_text is None else conf_text
    lines = corosync_conf.strip().split('\n')
    preg = re.compile(r'.*ring0_addr: (.*)')
    for line in lines:
        match = preg.match(line)
        if match:
            nodes.append (match.group(1))

    return nodes

def getNodesFromPacemaker():
    ret_nodes = []
    root = get_cib_etree()
    nodes = root.findall(".//node")
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

def setCorosyncConf(corosync_config, conf_file=None):
    if conf_file == None:
        conf_file = settings.corosync_conf_file
    try:
        f = open(conf_file,'w')
        f.write(corosync_config)
        f.close()
    except IOError:
        err("unable to write corosync configuration file, try running as root.")

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
            print "Error mapping %s" % node
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
    for c_node in getNodesFromCorosyncConf():
        if (c_node == node0) or (c_node == node1):
            err("node already exists in corosync.conf")
        num_nodes_in_conf = num_nodes_in_conf + 1
    if "--corosync_conf" not in pcs_options:
        for c_node in getCorosyncActiveNodes():
            if (c_node == node0) or (c_node == node1):
                err("Node already exists in running corosync")
    corosync_conf = getCorosyncConf()
    new_nodeid = getNextNodeID(corosync_conf)
    nl_re = re.compile(r"nodelist\s*{")
    results = nl_re.search(corosync_conf)
    if results:
        bracket_depth = 1
        count = results.end()
        for c in corosync_conf[results.end():]:
            if c == "}":
                bracket_depth -= 1
            if c == "{":
                bracket_depth += 1

            if bracket_depth == 0:
                break
            count += 1
        new_corosync_conf = corosync_conf[:count]
        new_corosync_conf += "  node {\n"
        if node1 is not None:
            new_corosync_conf += "        ring0_addr: %s\n" % (node0)
            new_corosync_conf += "        ring1_addr: %s\n" % (node1)
        else:
            new_corosync_conf += "        ring0_addr: %s\n" % (node0)
        new_corosync_conf += "        nodeid: %d\n" % (new_nodeid)
        new_corosync_conf += "       }\n"
        new_corosync_conf += corosync_conf[count:]
        if num_nodes_in_conf >= 2:
            new_corosync_conf = rmQuorumOption(new_corosync_conf,("two_node","1"))
        setCorosyncConf(new_corosync_conf)
    else:
        err("unable to find nodelist in corosync.conf")

    return True

def addNodeToClusterConf(node):
    node0, node1 = parse_multiring_node(node)
    nodes = getNodesFromCorosyncConf()
    for existing_node in nodes:
        if (existing_node == node0) or (existing_node == node1):
            err("node already exists in cluster.conf")

    output, retval = run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--addnode", node0])
    if retval != 0:
        print output
        err("error adding node: %s" % node0)

    if node1:
        output, retval = run([
            "/usr/sbin/ccs", "-f", settings.cluster_conf_file,
            "--addalt", node0, node1
        ])
        if retval != 0:
            print output
            err(
                "error adding alternative address for node: %s" % node0
            )

    output, retval = run(["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--addmethod", "pcmk-method", node0])
    if retval != 0:
        print output
        err("error adding fence method: %s" % node)

    output, retval = run(["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--addfenceinst", "pcmk-redirect", node0, "pcmk-method", "port="+node0])
    if retval != 0:
        print output
        err("error adding fence instance: %s" % node)

    if len(nodes) == 2:
        cman_options_map = get_cluster_conf_cman_options()
        cman_options_map.pop("expected_votes", None)
        cman_options_map.pop("two_node", None)
        cman_options = ["%s=%s" % (n, v) for n, v in cman_options_map.items()]
        output, retval = run(
            ["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--setcman"]
            + cman_options
        )
        if retval != 0:
            print output
            err("unable to set cman options")

    return True

# TODO: Need to make this smarter about parsing files not generated by pcs
def removeNodeFromCorosync(node):
    removed_node = False
    node_found = False
    num_nodes_in_conf = 0

    node0, node1 = parse_multiring_node(node)

    for c_node in getNodesFromCorosyncConf():
        if c_node == node0:
            node_found = True
        num_nodes_in_conf = num_nodes_in_conf + 1

    if not node_found:
        return False

    new_corosync_conf_lines = []
    in_node = False
    node_match = False
    node_buffer = []
    for line in getCorosyncConf().split("\n"):
        if in_node:
            node_buffer.append(line)
            if (
                ("ring0_addr: " + node0 in line)
                or
                (node1 is not None and "ring0_addr: " + node1 in line)
            ):
                node_match = True
                removed_node = True
            if "}" in line:
                if not node_match:
                    new_corosync_conf_lines.extend(node_buffer)
                node_buffer = []
                node_match = False
        elif "node {" in line:
            node_buffer.append(line)
            in_node = True
        else:
            new_corosync_conf_lines.append(line)
    new_corosync_conf = "\n".join(new_corosync_conf_lines) + "\n"

    if removed_node:
        if num_nodes_in_conf == 3:
            new_corosync_conf = addQuorumOption(new_corosync_conf,("two_node","1"))
        setCorosyncConf(new_corosync_conf)

    return removed_node

def removeNodeFromClusterConf(node):
    node0, node1 = parse_multiring_node(node)
    nodes = getNodesFromCorosyncConf()
    if node0 not in nodes:
        return False

    output, retval = run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--rmnode", node0])
    if retval != 0:
        print output
        err("error removing node: %s" % node)

    if len(nodes) == 3:
        cman_options_map = get_cluster_conf_cman_options()
        cman_options_map.pop("expected_votes", None)
        cman_options_map.pop("two_node", None)
        cman_options = ["%s=%s" % (n, v) for n, v in cman_options_map.items()]
        output, retval = run(
            ["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--setcman"]
            + ["two_node=1", "expected_votes=1"]
            + cman_options
        )
        if retval != 0:
            print output
            err("unable to set cman options: expected_votes and two_node")
    return True

# Adds an option to the quorum section to the corosync.conf passed in and
# returns a string containing the updated corosync.conf
# corosync_conf is a string containing the full corosync.conf 
# option is a tuple with (option, value)
def addQuorumOption(corosync_conf,option):
    lines = corosync_conf.split("\n")
    newlines = []
    output = ""
    done = False

    inQuorum = False
    for line in lines:
        if inQuorum and line.startswith(option[0] + ":"):
            line = option[0] + ": " + option[1]
            done = True
        if line.startswith("quorum {"):
            inQuorum = True
        newlines.append(line)

    if not done:
        inQuorum = False
        for line in newlines:
            if inQuorum and line.startswith("provider:"):
                line = line + "\n" + option[0] + ": " + option[1]
                done = True
            if line.startswith("quorum {") and not done:
                inQuorum = True
            if line.startswith("}") and inQuorum:
                inQuorum = False
            if not inQuorum or not line == "":
                output = output + line + "\n"

    return output.rstrip('\n') + "\n"

# Removes an option in the quorum section of the corosync.conf passed in and
# returns a string containing the updated corosync.conf
# corosync_conf is a string containing the full corosync.conf 
# option is a tuple with (option, value)
def rmQuorumOption(corosync_conf,option):
    lines = corosync_conf.split("\n")
    newlines = []
    output = ""
    done = False

    inQuorum = False
    for line in lines:
        if inQuorum and line.startswith(option[0] + ":"):
            continue
        if line.startswith("quorum {"):
            inQuorum = True
        output = output + line + "\n"

    return output.rstrip('\n') + "\n"

def getNextNodeID(corosync_conf):
    currentNodes = []
    highest = 0
    corosync_conf = getCorosyncConf()
    p = re.compile(r"nodeid:\s*([0-9]+)")
    mall = p.findall(corosync_conf)
    for m in mall:
        currentNodes.append(int(m))
        if int(m) > highest:
            highest = int(m)

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

def need_ring1_address(corosync_conf):
    if is_rhel6():
        # ring1 address is required regardless of transport
        # it has to be added to cluster.conf in order to set up ring1
        # in corosync by cman
        try:
            dom = parseString(corosync_conf)
        except xml.parsers.expat.ExpatError as e:
            err("Unable parse cluster.conf: %s" % e)
        rrp = False
        for el in dom.getElementsByTagName("totem"):
            if el.getAttribute("rrp_mode") in ["active", "passive"]:
                rrp = True
        return rrp

    line_list = corosync_conf.split("\n")
    in_totem = False
    udpu_transport = False
    rrp = False
    for line in line_list:
        line = line.strip()
        if in_totem:
            if ":" in line:
                name, value = map(lambda x: x.strip(), line.split(":"))
                if name == "transport" and value == "udpu":
                    udpu_transport = True
                if name == "rrp_mode" and value in ["active", "passive"]:
                    rrp = True
            if "}" in line:
                in_totem = False
        if line.startswith("totem {"):
            in_totem = True
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
def run(args, ignore_stderr=False, string_for_stdin=None):
    env_var = dict(os.environ)
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
    if command[0:8] == "corosync":
        args[0] = settings.corosync_binaries + command
        
    try:
        if "--debug" in pcs_options:
            print "Running: " + " ".join(args)
            if string_for_stdin:
                print "--Debug Input Start--\n" + string_for_stdin
                print "--Debug Input End--\n"

        # Some commands react differently if you give them anything via stdin
        if string_for_stdin != None:
            stdin_pipe = subprocess.PIPE
        else:
            stdin_pipe = None

        if ignore_stderr:
            p = subprocess.Popen(args, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env = env_var, preexec_fn=subprocess_setup)
        else:
            p = subprocess.Popen(args, stdin=stdin_pipe, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env = env_var, preexec_fn=subprocess_setup)
        output,stderror = p.communicate(string_for_stdin)
        returnVal = p.returncode
        if "--debug" in pcs_options:
            print "Return Value: " + str(returnVal)
            print "--Debug Output Start--\n" + output
            print "--Debug Output End--\n"
    except OSError as e:
        print e.strerror
        err("unable to locate command: " + args[0])

    return output, returnVal

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
        for node in node_threads.keys():
            thread = node_threads[node]
            thread.join(1)
            if thread.is_alive():
                continue
            output = node + ": " + thread.output.strip()
            print output
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
    clone = resource
    while True:
        if not isinstance(clone, xml.dom.minidom.Element):
            return None
        if clone.tagName in ["clone", "master"]:
            return clone
        clone = clone.parentNode

# deprecated, use dom_get_master
def is_master(ms_id):
    return does_exist("//master[@id='"+ms_id+"']")

def dom_get_master(dom, master_id):
    for master in dom.getElementsByTagName("master"):
        if master.getAttribute("id") == master_id:
            return master
    return None

# deprecated, use dom_get_clone
def is_clone(clone_id):
    return does_exist("//clone[@id='"+clone_id+"']")

def dom_get_clone(dom, clone_id):
    for clone in dom.getElementsByTagName("clone"):
        if clone.getAttribute("id") == clone_id:
            return clone
    return None

# deprecated, use dom_get_group
def is_group(group_id):
    return does_exist("//group[@id='"+group_id+"']")

def dom_get_group(dom, group_id):
    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_id:
            return group
    return None

# deprecated, use dom_get_group_clone
def is_group_clone(group_id):
    return does_exist("//clone//group[@id='"+group_id+"']")

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

# deprecated, use dom_get_resource
def is_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"']")

def dom_get_resource(dom, resource_id):
    for primitive in dom.getElementsByTagName("primitive"):
        if primitive.getAttribute("id") == resource_id:
            return primitive
    return None

def is_stonith_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"' and @class='stonith']")

# deprecated, use dom_get_resource_clone
def is_resource_clone(resource_id):
    return does_exist("//clone//primitive[@id='"+resource_id+"']")

def dom_get_resource_clone(dom, resource_id):
    for clone in dom.getElementsByTagName("clone"):
        resource = dom_get_resource(clone, resource_id)
        if resource:
            return resource
    return None

# deprecated, use dom_get_resource_masterslave
def is_resource_masterslave(resource_id):
    return does_exist("//master//primitive[@id='"+resource_id+"']")

def dom_get_resource_masterslave(dom, resource_id):
    for master in dom.getElementsByTagName("master"):
        resource = dom_get_resource(master, resource_id)
        if resource:
            return resource
    return None

# deprecated, use dom_get_resource_clone_ms_parent
def get_resource_master_id(resource_id):
    dom = get_cib_dom()
    primitives = dom.getElementsByTagName("primitive")
    for p in primitives:
        if p.getAttribute("id") == resource_id:
            if p.parentNode.tagName == "master":
                return p.parentNode.getAttribute("id")
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

# Check if resource is started (or stopped) for 'wait' seconds
# options for started mode:
#   count - do not success unless 'count' instances of the resource are Started
#       or Master (Slave does not count)
#   allowed_nodes - do not success if resource is running on any other node
#   banned_nodes - do not success if resource is running on any banned node
#   desired_nodes - do not success unless resource is running on all desired
#       nodes
#   cluster state - use passed cluster state instead of live one
# options for stopped mode:
#   desired_nodes - do not success unless resource is stopped on all desired
#       nodes
# options for both:
#   slave_as_started - consider Slave role as started, otherwise only Started
#       and Master are considered
def is_resource_started(
    resource, wait, stopped=False,
    count=None, allowed_nodes=None, banned_nodes=None, desired_nodes=None,
    cluster_state=None, slave_as_started=False
):
    running_roles = set(("Started", "Master"))
    if slave_as_started:
        running_roles.add("Slave")
    timeout = False
    fail = False
    success = False
    resource_original = resource
    nodes_running_original = set()
    set_allowed_nodes = set(allowed_nodes) if allowed_nodes else allowed_nodes
    set_banned_nodes = set(banned_nodes) if banned_nodes else banned_nodes
    set_desired_nodes = set(desired_nodes) if desired_nodes else desired_nodes
    expire_time = time.time() + wait
    while not fail and not success and not timeout:
        state = cluster_state if cluster_state else getClusterState()
        cib_dom = get_cib_dom()
        node_count = len(cib_dom.getElementsByTagName("node"))
        resource = get_resource_for_running_check(state, resource, stopped)
        running_on = resource_running_on(resource_original, state)
        if not nodes_running_original:
            nodes_running_original = set(
                running_on["nodes_started"] + running_on["nodes_master"]
            )
            if slave_as_started:
                nodes_running_original.update(running_on["nodes_slave"])
        failed_op_list = get_lrm_rsc_op_failed(cib_dom, resource)
        resources = state.getElementsByTagName("resource")
        all_stopped = True
        for res in resources:
            # If resource is a clone it can have an id of '<resource name>:N'
            if res.getAttribute("id") == resource or res.getAttribute("id").startswith(resource+":"):
                list_running_on = (
                    running_on["nodes_started"] + running_on["nodes_master"]
                )
                if slave_as_started:
                    list_running_on.extend(running_on["nodes_slave"])
                set_running_on = set(list_running_on)
                if stopped:
                    if (
                        res.getAttribute("role") != "Stopped"
                        or
                        (
                            res.getAttribute("role") == "Stopped"
                            and
                            res.getAttribute("failed") == "true"
                        )
                    ):
                        if desired_nodes:
                            for node in res.getElementsByTagName("node"):
                                if node.getAttribute("name") in desired_nodes:
                                    all_stopped = False
                        else:
                            all_stopped = False
                    nodes_failed = set()
                    for op in failed_op_list:
                        if op.getAttribute("operation") in ["stop", "demote"]:
                            nodes_failed.add(op.getAttribute("on_node"))
                    if nodes_failed >= nodes_running_original:
                        fail = True
                else:
                    if (
                        res.getAttribute("role") in running_roles
                        and
                        res.getAttribute("failed") != "true"
                        and
                        (count is None or len(list_running_on) == count)
                        and
                        (
                            not banned_nodes
                            or
                            set_running_on.isdisjoint(set_banned_nodes)
                        )
                        and
                        (
                            not allowed_nodes
                            or
                            set_running_on <= set_allowed_nodes
                        )
                        and
                        (
                            not desired_nodes
                            or
                            set_running_on >= set_desired_nodes
                        )
                    ):
                        success = True
                    # check for failures but give pacemaker a chance to try
                    # to start the resource on another node (it will try anyway
                    # so don't report fail prematurely)
                    nodes_failed = set()
                    for op in failed_op_list:
                        if op.getAttribute("operation") in ["start", "promote"]:
                            nodes_failed.add(op.getAttribute("on_node"))
                    if (
                        len(nodes_failed) >= node_count
                        or
                        (allowed_nodes and set(allowed_nodes) == nodes_failed)
                    ):
                        fail = True
        if stopped and all_stopped:
            success = True
        if (expire_time < time.time()):
            timeout = True
        if not timeout:
            time.sleep(0.25)
    message = ""
    if not success and timeout and not failed_op_list:
        message += "waiting timed out\n"
    message += running_on["message"]
    if failed_op_list:
        failed_op_list.sort(key=lambda x: x.getAttribute("on_node"))
        message += "\nResource failures:\n  "
        message += "\n  ".join(get_lrm_rsc_op_failures(failed_op_list))
    return success, message

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

# op_list can be obtained from get_operations_from_transitions
# it looks like this: [(resource_id, operation, node), ...]
def wait_for_primitive_ops_to_process(op_list, timeout=None):
    if timeout:
        timeout = int(timeout)
        start_time = time.time()
    else:
        cib_dom = get_cib_dom()

    for op in op_list:
        print "Waiting for '%s' to %s on %s" % (op[0], op[1], op[2])
        if timeout:
            remaining_timeout = timeout - (time.time() - start_time)
        else:
            remaining_timeout = get_resource_op_timeout(cib_dom, op[0], op[1])
        # crm_simulate can start resources as slave and promote them later
        # so we need to consider slave resources as started
        success, message = is_resource_started(
            op[0], remaining_timeout, op[1] == "stop",
            desired_nodes=[op[2]], slave_as_started=(op[1] == "start")
        )
        if success:
            print message
        else:
            err(
                "Unable to %s '%s' on %s\n%s"
                % (op[1], op[0], op[2], message)
            )

def get_resource_status_for_wait(dom, resource_el, node_count):
    res_id = resource_el.getAttribute("id")
    clone_ms_parent = dom_get_resource_clone_ms_parent(dom, res_id)
    meta_resource_el = clone_ms_parent if clone_ms_parent else resource_el
    status_running = is_resource_started(res_id, 0)[0]
    status_enabled = True
    for meta in meta_resource_el.getElementsByTagName("meta_attributes"):
        for nvpair in meta.getElementsByTagName("nvpair"):
            if nvpair.getAttribute("name") == "target-role":
                if nvpair.getAttribute("value").lower() == "stopped":
                    status_enabled = False
    status_instances = count_expected_resource_instances(
        meta_resource_el, node_count
    )
    return {
        "running": status_running,
        "enabled": status_enabled,
        "instances": status_instances,
    }

def get_resource_wait_decision(old_status, new_status):
    wait_for_start = False
    wait_for_stop = False
    if old_status["running"] and not new_status["enabled"]:
        wait_for_stop = True
    elif (
        not old_status["running"]
        and
        (not old_status["enabled"] and new_status["enabled"])
    ):
        wait_for_start = True
    elif (
        old_status["running"]
        and
        old_status["instances"] != new_status["instances"]
    ):
        wait_for_start = True
    return wait_for_start, wait_for_stop

def get_lrm_rsc_op(cib, resource, op_list=None, last_call_id=None):
    lrm_rsc_op_list = []
    for lrm_resource in cib.getElementsByTagName("lrm_resource"):
        if lrm_resource.getAttribute("id") != resource:
            continue
        for lrm_rsc_op in lrm_resource.getElementsByTagName("lrm_rsc_op"):
            if op_list and lrm_rsc_op.getAttribute("operation") not in op_list:
                continue
            if (
                last_call_id is not None
                and
                int(lrm_rsc_op.getAttribute("call-id")) <= int(last_call_id)
            ):
                continue
            if not lrm_rsc_op.getAttribute("on_node"):
                state = dom_get_parent_by_tag_name(lrm_rsc_op, "node_state")
                if state:
                    lrm_rsc_op.setAttribute(
                        "on_node", state.getAttribute("uname")
                    )
            lrm_rsc_op_list.append(lrm_rsc_op)
    lrm_rsc_op_list.sort(key=lambda x: int(x.getAttribute("call-id")))
    return lrm_rsc_op_list

def get_lrm_rsc_op_failed(cib, resource, op_list=None, last_call_id=None):
    failed_op_list = []
    for op in get_lrm_rsc_op(cib, resource, op_list, last_call_id):
        if (
            op.getAttribute("operation") == "monitor"
            and
            op.getAttribute("rc-code") == "7"
        ):
            continue
        if op.getAttribute("rc-code") != "0":
            failed_op_list.append(op)
    return failed_op_list

def get_lrm_rsc_op_failures(lrm_rsc_op_list):
    failures = []
    for rsc_op in lrm_rsc_op_list:
        if rsc_op.getAttribute("rc-code") == "0":
            continue
        reason = rsc_op.getAttribute("exit-reason")
        if not reason:
            reason = "failed"
        node = rsc_op.getAttribute("on_node")
        if not node:
            state = dom_get_parent_by_tag_name(rsc_op, "node_state")
            if state:
                node = state.getAttribute("uname")
        if node:
            failures.append("%s: %s" % (node, reason))
        else:
            failures.append(reason)
    return failures

def resource_running_on(resource, passed_state=None):
    nodes_started = []
    nodes_master = []
    nodes_slave = []
    state = passed_state if passed_state else getClusterState()
    resource_original = resource
    resource = get_resource_for_running_check(state, resource)
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
        "nodes_started": nodes_started,
        "nodes_master": nodes_master,
        "nodes_slave": nodes_slave,
    }

# get count of expected running instances of a resource
# counts promoted instances for master/slave resource
def count_expected_resource_instances(res_el, node_count):
    if res_el.tagName in ["primitive", "group"]:
        return 1
    unique = dom_get_meta_attr_value(res_el, "globally-unique") == "true"
    clone_max = dom_get_meta_attr_value(res_el, "clone-max")
    clone_max = int(clone_max) if clone_max else node_count
    clone_node_max = dom_get_meta_attr_value(res_el, "clone-node-max")
    clone_node_max = int(clone_node_max) if clone_node_max else 1
    if res_el.tagName == "master":
        master_max = dom_get_meta_attr_value(res_el, "master-max")
        master_max = int(master_max) if master_max else 1
        master_node_max = dom_get_meta_attr_value(res_el, "master-node-max")
        master_node_max = int(master_node_max) if master_node_max else 1
        if unique:
            return min(clone_max, master_max, node_count * clone_node_max)
        else:
            return min(clone_max, master_max, node_count)
    else:
        if unique:
            return min(clone_max, node_count * clone_node_max)
        else:
            return min(clone_max, node_count)

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
        actions = root.findall(".//actions/action")
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
    if timeout.endswith("s") and timeout[:-1].isdigit():
        return int(timeout[:-1])
    if timeout.endswith("min") and timeout[:-3].isdigit():
        return int(timeout[:-3]) * 60
    return timeout if return_unknown else None

def get_default_op_timeout():
    output, retVal = run([
        "crm_attribute", "--type", "op_defaults", "--name", "timeout",
        "--query", "--quiet"
    ])
    if retVal == 0 and output.strip():
        timeout = get_timeout_seconds(output)
        if timeout is not None:
            return timeout

    properties = prop.get_set_properties(defaults=prop.get_default_properties())
    if properties["default-action-timeout"]:
        timeout = get_timeout_seconds(properties["default-action-timeout"])
        if timeout is not None:
            return timeout

    return settings.default_wait

def get_resource_op_timeout(cib_dom, resource, operation):
    resource_el = dom_get_resource(cib_dom, resource)
    if resource_el:
        for op_el in resource_el.getElementsByTagName("op"):
            if op_el.getAttribute("name") == operation:
                timeout = get_timeout_seconds(op_el.getAttribute("timeout"))
                if timeout is not None:
                    return timeout

        defaults = get_default_op_values(
            "%s:%s:%s"
            % (
                resource_el.getAttribute("class"),
                resource_el.getAttribute("provider"),
                resource_el.getAttribute("type"),
            )
        )
        for op in defaults:
            if op[0] == operation:
                for op_setting in op[1:]:
                    match = re.match("timeout=(.+)", op_setting)
                    if match:
                        timeout = get_timeout_seconds(match.group(1))
                        if timeout is not None:
                            return timeout

    return get_default_op_timeout()

# Check and see if the specified resource (or stonith) type is present on the
# file system and properly responds to a meta-data request
def is_valid_resource(resource, caseInsensitiveCheck=False):
    found_resource = False
    stonith_resource = False
    if resource.startswith("ocf:"):
        resource_split = resource.split(":",3)
        if len(resource_split) != 3:
            err("ocf resource definition (" + resource + ") does not match the ocf:provider:name pattern")
        providers = [resource_split[1]]
        resource = resource_split[2]
    elif resource.startswith("stonith:"):
        stonith_resource = True
        resource_split = resource.split(":", 2)
        stonith = resource_split[1]
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

    if stonith_resource:
        metadata = get_stonith_metadata("/usr/sbin/" + stonith)
        if metadata != False:
            found_resource = True
    else:
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
                found_resource = True
                break

    return found_resource

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
        params = root.findall(".//parameter")
        default_params = []
        for param in params:
            adv_param = False
            for short_desc in param.findall(".//shortdesc"):
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

# Replace only configuration section of cib with dom passed
def replace_cib_configuration(dom):
    if dom.__class__ == xml.etree.ElementTree.Element or dom.__class__ == xml.etree.ElementTree._ElementInterface:
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
    if dom.__class__ == xml.etree.ElementTree.Element or dom.__class__ == xml.etree.ElementTree._ElementInterface:
        for elem in dom.findall(".//*"):
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
    op_name = op_el.getAttribute("name")
    op_interval = get_timeout_seconds(op_el.getAttribute("interval"), True)
    for op in operations_el.getElementsByTagName("op"):
        if (
            op.getAttribute("name") == op_name
            and
            get_timeout_seconds(op.getAttribute("interval"), True) == op_interval
        ):
            return op
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
        for nvp in node.getElementsByTagName("nvpair"):
            if nodename not in nas:
                nas[nodename] = []
            nas[nodename].append(nvp.getAttribute("name") + "=" + nvp.getAttribute("value"))
    return nas

def set_node_attribute(prop, value, node):
    if (value == ""):
        o,r = run(["crm_attribute", "-t", "nodes", "--node", node, "--name",prop,"--query"])
        if r != 0 and "--force" not in pcs_options:
            err("attribute: '%s' doesn't exist for node: '%s'" % (prop,node))
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
        print output

def getTerminalSize(fd=1):
    """
    Returns height and width of current terminal. First tries to get
    size via termios.TIOCGWINSZ, then from environment. Defaults to 25
    lines x 80 columns if both methods fail.
 
    :param fd: file descriptor (default: 1=stdout)
    """
    try:
        import fcntl, termios, struct
        hw = struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    except:
        try:
            hw = (os.environ['LINES'], os.environ['COLUMNS'])
        except:  
            hw = (25, 80)
 
    return hw

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
        for prop in cps.findall("nvpair"):
            if 'name' in prop.attrib and prop.attrib["name"] == "stonith-enabled":
                if prop.attrib["value"] == "off" or \
                        prop.attrib["value"] == "false":
                    return False
        
    primitives = et.findall("configuration/resources/primitive")
    for p in primitives:
        if p.attrib["class"] == "stonith":
            return False

    primitives = et.findall("configuration/resources/clone/primitive")
    for p in primitives:
        if p.attrib["class"] == "stonith":
            return False

    return True

def getCorosyncNodesID(allow_failure=False):
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

    cs_nodes = {}
    (output, retval) = run(['corosync-cmapctl', '-b', 'nodelist.node'])
    if retval != 0:
        if allow_failure:
            return {}
        else:
            err("unable to get list of corosync nodes")

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
def getPacemakerNodesID(allow_failure=False):
    (output, retval) = run(['crm_node', '-l'])
    if retval != 0:
        if allow_failure:
            return {}
        else:
            err("unable to get list of pacemaker nodes")

    pm_nodes = {}
    for line in output.rstrip().split("\n"):
        node_info = line.rstrip().split(" ",1)
        pm_nodes[node_info[0]] = node_info[1]

    return pm_nodes

def corosyncPacemakerNodeCheck():
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
        for action in actions.findall("parameter"):
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
            if (
                "pcmk_host_argument" in ra_values
                or
                "pcmk_host_map" in ra_values
                or
                "pcmk_host_list" in ra_values
            ):
                missing_required_parameters.remove("port")

    return bad_parameters, missing_required_parameters 

def generate_rrp_corosync_config(interface):
    interface = str(interface)
    if interface == "0":
        mcastaddr = "239.255.1.1"
    else:
        mcastaddr = "239.255.2.1"
    mcastport = "5405"

    ir = "  interface {\n"
    ir += "    ringnumber: %s\n" % interface
    ir += "    bindnetaddr: " + pcs_options["--addr"+interface] + "\n"
    if "--broadcast" + interface in pcs_options:
        ir += "    broadcast: yes\n"
    else:
        if "--mcast" + interface in pcs_options:
            mcastaddr = pcs_options["--mcast"+interface]
        ir += "    mcastaddr: " + mcastaddr + "\n"
        if "--mcastport"+interface in pcs_options:
            mcastport = pcs_options["--mcastport"+interface]
        ir += "    mcastport: " + mcastport + "\n"
        if "--ttl" + interface in pcs_options:
            ir += "    ttl: " + pcs_options["--ttl"+interface] + "\n"
    ir += "  }\n"
    return ir

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
        except IOError as e:
            return ""

        p = re.compile('cluster_name: *(.*)')
        for line in f:
            m = p.match(line)
            if m:
                return m.group(1)

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

# Does pacemaker consider a variable as true in cib?
# See crm_is_true in pacemaker/lib/common/utils.c
def is_cib_true(var):
    return var.lower() in ("true", "on", "yes", "y", "1")

def is_systemctl():
    if os.path.exists('/usr/bin/systemctl'):
        return True
    else:
        return False

def is_rhel6():
    try:
        issue = open('/etc/system-release').read()
    except IOError as e:
        return False

# Since there are so many RHEL 6 variants, this check looks for the first
# number in /etc/system-release followed by a period and number, and if it's 6.N,
# it returns true.
    match = re.search(r'(\d)\.\d', issue)
    if match and match.group(1) == "6":
        return True
    else:
        return False

def err(errorText, exit_after_error=True):
    sys.stderr.write("Error: %s\n" % errorText)
    if exit_after_error:
        sys.exit(1)

def serviceStatus(prefix):
    if is_systemctl():
        print "Daemon Status:"
        daemons = ["corosync", "pacemaker", "pcsd"]
        out, ret = run(["systemctl", "is-active"] + daemons)
        status = out.split("\n")
        out, ret = run(["systemctl", "is-enabled"]+ daemons)
        enabled = out.split("\n")
        for i in range(len(daemons)):
            print prefix + daemons[i] + ": " + status[i] + "/" + enabled[i]

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

def write_file(path, data):
    if os.path.exists(path):
        if not "--force" in pcs_options:
            return False, "'%s' already exists, use --force to overwrite" % path
        else:
            try:
                os.remove(path)
            except EnvironmentError as e:
                return False, "unable to remove '%s': %s" % (path, e)
    try:
        with open(path, "w") as outfile:
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
    data_io = cStringIO.StringIO(data)
    tarball.addfile(info, data_io)
    data_io.close()

def simulate_cib(cib_dom):
    new_cib_file = tempfile.NamedTemporaryFile("w+b", -1, ".pcs")
    transitions_file = tempfile.NamedTemporaryFile("w+b", -1, ".pcs")
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
    watched_operations = ("start", "stop", "promote")
    for rsc_op in transitions_dom.getElementsByTagName("rsc_op"):
        primitives = rsc_op.getElementsByTagName("primitive")
        if not primitives:
            continue
        if rsc_op.getAttribute("operation").lower() not in watched_operations:
            continue
        for prim in primitives:
            operation_list.append((
                int(rsc_op.getAttribute("id")),
                (
                prim.getAttribute("id"),
                rsc_op.getAttribute("operation").lower(),
                rsc_op.getAttribute("on_node"),
                )
            ))
    operation_list.sort(key=lambda x: x[0])
    op_list = [op[1] for op in operation_list]
    return op_list

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
                parts = map(lambda x: x.strip(), line.split(":", 1))
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
                parts = map(lambda x: x.strip(), line.split(":", 1))
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

