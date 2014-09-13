import os, subprocess
import sys
import pcs
import xml.dom.minidom
import urllib,urllib2
from xml.dom.minidom import parseString,parse
import xml.etree.ElementTree as ET
import re
import json
import settings
import resource
import signal
import time
import cluster


# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options = {}
fence_bin = settings.fence_agent_binaries

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
        err("unable to connect to pcsd on %s\n" % node + out[1])
    token = out[1]
    if token == "":
        err("Username and/or password is incorrect")

    tokens = readTokens()
    tokens[node] = token
    writeTokens(tokens)

    return True

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
    orig_filename = "pcs-uidgid-%s-%s" % (uid,gid)
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
    if (os.path.isfile(tokenfile) == False):
        return {}
    try:
        tokens = json.load(open(tokenfile))
    except:
        return {}
    return tokens

# Takes a dictionary {'nodeA':'tokenA'}
def writeTokens(tokens):
    tokenfile = tokenFile()
    if (os.path.isfile(tokenfile) == False) and 'PCS_TOKEN_FILE' not in os.environ:
        if not os.path.exists(os.path.dirname(tokenfile)):
            os.makedirs(os.path.dirname(tokenfile),0700);
    f = os.fdopen (os.open(tokenfile, os.O_WRONLY | os.O_CREAT, 0600), 'w')
    f.write(json.dumps(tokens))
    f.close()

# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    retval, output = sendHTTPRequest(node, 'remote/get_corosync_conf', None, False, False)
    return retval,output

def setCorosyncConfig(node,config):
    if not is_rhel7_compat():
        data = urllib.urlencode({'cluster_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_cluster_conf', data)
        if status != 0:
            err("Unable to set cluster.conf")
    else:
        data = urllib.urlencode({'corosync_conf':config})
        (status, data) = sendHTTPRequest(node, 'remote/set_corosync_conf', data)
        if status != 0:
            err("Unable to set corosync config")

def startCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_start', None, False, True)

def stopCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_stop', None, False, True)

def enableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_enable', None, False, True)

def disableCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_disable', None, False, True)

def destroyCluster(node):
    return sendHTTPRequest(node, 'remote/cluster_destroy')

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
    if not is_rhel7_compat():
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
        if not is_rhel7_compat():
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
    output, retval = run(["corosync-cfgtool", "-R"])
    return output, retval

def getCorosyncActiveNodes():
    if not is_rhel7_compat():
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
    if "," in node:
        node0 = node.split(",")[0]
        node1 = node.split(",")[1]
    else:
        node0 = node
        node1 = None
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
        reloadCorosync()
    else:
        err("unable to find nodelist in corosync.conf")

    return True

def addNodeToClusterConf(node):
    nodes = getNodesFromCorosyncConf()
    output, retval = run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--addnode", node])
    if retval != 0:
        print output
        err("error adding node: %s" % node)

    output, retval = run(["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--addmethod", "pcmk-method", node])
    if retval != 0:
        print output
        err("error adding fence method: %s" % node)

    output, retval = run(["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--addfenceinst", "pcmk-redirect", node, "pcmk-method", "port="+node])
    if retval != 0:
        print output
        err("error adding fence instance: %s" % node)

    if len(nodes) == 2:
        output, retval = run(["/usr/sbin/ccs", "-i", "-f", settings.cluster_conf_file, "--setcman"])
        if retval != 0:
            print output
            err("unable to set cman options")

    return True

# TODO: Need to make this smarter about parsing files not generated by pcs
def removeNodeFromCorosync(node):
    removed_node = False
    node_found = False
    num_nodes_in_conf = 0

    if "," in node:
        node0 = node.split(",")[0]
        node1 = node.split(",")[1]
    else:
        node0 = node
        node1 = None

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
        reloadCorosync()

    return removed_node

def removeNodeFromClusterConf(node):
    nodes = getNodesFromCorosyncConf()
    if node not in nodes:
        return False

    output, retval = run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--rmnode", node])
    if retval != 0:
        print output
        err("error removing node: %s" % node)

    if len(nodes) == 3:
        output, retval = run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--setcman", "two_node=1", "expected_votes=1"])
        if retval != 0:
            print output
            err("unable to set cman_options: expected_votes and two_node" % node)
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

def need_ring1_address(corosync_conf):
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

# Restore default behavior before starting subprocesses
def subprocess_setup():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Run command, with environment and return (output, retval)
def run(args, ignore_stderr=False, string_for_stdin=None):
    env_var = os.environ
    if usefile:
        env_var["CIB_file"] = filename

        if not os.path.isfile(filename):
            try:
                write_empty_cib(filename)
            except IOError:
                err("Unable to write to file: " + filename)

    command = args[0]
    if command[0:3] == "crm" or command in ["pacemakerd", "cibadmin", "cman_tool", "iso8601"]:
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

def validate_constraint_resource(dom, resource_id):
    resource_el = (
        dom_get_clone(dom, resource_id)
        or
        dom_get_master(dom, resource_id)
    )
    if resource_el:
        # clone and master is always valid
        return True, ""

    resource_el = (
        dom_get_resource(dom, resource_id)
        or
        dom_get_group(dom, resource_id)
    )
    if not resource_el:
        return False, "Resource '%s' does not exist" % resource_id

    if "--force" in pcs_options:
        return True, ""

    clone_el = dom_get_resource_clone_ms_parent(dom, resource_id)
    if not clone_el:
        # primitive and group is valid if not in clone nor master
        return True, ""

    if clone_el.tagName == "clone":
        return (
            False,
            "%s is a clone resource, you should use the clone id: %s "
                "when adding constraints. Use --force to override."
            % (resource_id, clone_el.getAttribute("id"))
        )
    if clone_el.tagName == "master":
        return (
            False,
            "%s is a master/slave resource, you should use the master id: %s "
                "when adding constraints. Use --force to override."
            % (resource_id, clone_el.getAttribute("id"))
        )
    return True, ""


def dom_get_resource_remote_node_name(dom_resource):
    if dom_resource.tagName != "primitive":
        return None
    for meta in dom_resource.getElementsByTagName("meta_attributes"):
        for nvpair in meta.getElementsByTagName("nvpair"):
            if nvpair.getAttribute("name") == "remote-node":
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

# Check if resoure is started (or stopped) for 'wait' seconds
def is_resource_started(resource,wait,stopped=False):
    expire_time = int(time.time()) + wait
    while True:
        state = getClusterState()
        resources = state.getElementsByTagName("resource")
        for res in resources:
            # If resource is a clone it can have an id of '<resource name>:N'
            if res.getAttribute("id") == resource or res.getAttribute("id").startswith(resource+":"):
                if (res.getAttribute("role") == "Started" and not stopped) or (res.getAttribute("role") == "Stopped" and stopped):
                    return True
                break
        if (expire_time < int(time.time())):
            break
        time.sleep(1)
    return False

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

def remove_from_cib(xml):
    args = ["cibadmin"]
    args = args + ["-D", "-X", xml]
    return run(args)

def get_cib():
    output, retval = run(["cibadmin", "-l", "-Q"])
    if retval != 0:
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
# operations (ignoring id)
def operation_exists(operations, op):
    for existing_op in operations.getElementsByTagName("op"):
        if len(existing_op.attributes.items()) != len(op.attributes.items()):
            continue
        match = False
        for k,v in existing_op.attributes.items():
            if k == "id":
                continue
            if v == op.getAttribute(k):
                match = True
            else:
                match = False
                break
        if match == True:
            return True
    return False

def set_unmanaged(resource):
    args = ["crm_resource", "--resource", resource, "--set-parameter",
            "is-managed", "--meta", "--parameter-value", "false"]
    return run(args)

def is_valid_property(prop):
    output, retval = run([settings.pengine_binary, "metadata"])
    if retval != 0:
        err("unable to run pengine\n" + output)

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
    found = False
    resSplit = resource_type.split(":")
    if len(resSplit) == 2:
        (resClass, resType) = resSplit
        metadata = get_stonith_metadata(fence_bin + resType)
    else:
        (resClass, resProvider, resType) = resource_type.split(":")
        metadata = get_metadata("/usr/lib/ocf/resource.d/" + resProvider + "/" + resType)

    if metadata == False:
        err("Unable to find resource: ocf:%s:%s" % (resProvider, resType))

    missing_required_parameters = []
    valid_parameters = ["pcmk_host_list", "pcmk_host_map", "pcmk_host_check", "pcmk_host_argument", "pcmk_arg_map", "pcmk_list_cmd", "pcmk_status_cmd", "pcmk_monitor_cmd"]
    valid_parameters = valid_parameters + ["stonith-timeout", "priority"]
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
                missing_required_parameters.append(action.attrib["name"])
    except xml.parsers.expat.ExpatError as e:
        err("Unable to parse xml for '%s': %s" % (resource_type, e))
    except xml.etree.ElementTree.ParseError as e:
        err("Unable to parse xml for '%s': %s" % (resource_type, e))
    for key,value in ra_values:
        if key not in valid_parameters:
            bad_parameters.append(key)
        if key in missing_required_parameters:
            missing_required_parameters.remove(key)

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
    if not is_rhel7_compat():
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

# Returns true if we have a valid op attribute
def is_valid_op_attr(attr):
    if attr in ["id","name","interval","description","start-delay","interval-origin","timeout","enabled", "record-pending", "role", "requires","on-fail", "OCF_CHECK_LEVEL"]:
        return True
    return False

# Test if 'var' is a score or option (contains an '=')
def is_score_or_opt(var):
    if is_score(var):
        return True
    elif var.find('=') != -1:
        return True
    return False

def is_score(var):
    return (
        var == "INFINITY" or var == "-INFINITY"
        or
        var.isdigit() or (len(var) > 1 and var[0] == "-" and var[1:].isdigit())
    )

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

def is_systemctl():
    if os.path.exists('/usr/bin/systemctl'):
        return True
    else:
        return False

   
def is_rhel7_compat():
    is_compatible = True
# We want to make sure we're running Corosync 2.3
    out, ret = run(['corosync', '-v'])
    match = re.search(r'(\d)\.(\d)', out)
    if not (match and match.group(1) == "2" and match.group(2) == "3"):
        is_compatible = False
# We also need Pacemaker 1.1 (sorry, RHEL 5 folks!)
    out, ret = run(['pacemakerd', '-$'])
    match = re.search(r'(\d)\.(\d)', out)
    if not (match and match.group(1) == "1" and match.group(2) == "1"):
        is_compatible = False
    return is_compatible

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
    if not is_rhel7_compat():
        run(["chkconfig", "pacemaker", "on"])
    else:
        if is_systemctl():
            run(["systemctl", "enable", "corosync.service"])
            run(["systemctl", "enable", "pacemaker.service"])
        else:
            run(["chkconfig", "corosync", "on"])
            run(["chkconfig", "pacemaker", "on"])

def disableServices():
    if not is_rhel7_compat():
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
