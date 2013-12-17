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


# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options = {}
fence_bin = settings.fence_agent_binaries

# Check status of node
def checkStatus(node):
    out = sendHTTPRequest(node, 'remote/status', None, False)
    return out

# Check and see if we're authorized (faster than a status check)
def checkAuthorization(node):
    out = sendHTTPRequest(node, 'remote/check_auth', None, False, False)
    return out

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
    tokenfile = os.path.expanduser("~/.pcs/tokens")
    if (os.path.isfile(tokenfile) == False):
        return {}
    try:
        tokens = json.load(open(tokenfile))
    except:
        return {}
    return tokens

# Takes a dictionary {'nodeA':'tokenA'}
def writeTokens(tokens):
    tokenfile = os.path.expanduser("~/.pcs/tokens")
    if (os.path.isfile(tokenfile) == False):
        if not os.path.exists(os.path.expanduser("~/.pcs")):
            os.mkdir(os.path.expanduser("~/.pcs"),0700);
    f = os.fdopen (os.open(tokenfile, os.O_WRONLY | os.O_CREAT, 0600), 'w')
    f.write(json.dumps(tokens))
    f.close()

# Set the corosync.conf file on the specified node
def getCorosyncConfig(node):
    retval, output = sendHTTPRequest(node, 'remote/get_corosync_conf', None, False, False)
    return retval,output

def setCorosyncConfig(node,config):
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
    sendHTTPRequest(node, 'remote/cluster_destroy')

def addLocalNode(node,node_to_add):
    data = urllib.urlencode({'new_nodename':node_to_add})
    retval, output = sendHTTPRequest(node, 'remote/add_node', data, False)
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
    retval, output = sendHTTPRequest(node, 'remote/remove_node', data, False)
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

def getNodesFromCorosyncConf():
    nodes = []
    lines = getCorosyncConf().strip().split('\n')
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
        conf = settings.corosync_conf_file
    try:
        out = open(conf).read()
    except IOError:
        return ""
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
    args = ["corosync-cmapctl"]
    nodes = []
    output,retval = run(args)
    if retval != 0:
        return []

    nodename_re = re.compile(r"^nodelist\.node\.(\d+)\.ring\d+_addr.*= (.*)", re.M)
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

# Add node specified to corosync.conf and insert into corosync (if running)
def addNodeToCorosync(node):
# Before adding, make sure node isn't already in corosync.conf or in running
# corosync process
    num_nodes_in_conf = 0
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            err("node already exists in corosync.conf")
        num_nodes_in_conf = num_nodes_in_conf + 1
    for c_node in getCorosyncActiveNodes():
        if c_node == node:
            err("Node already exists in running corosync")
    corosync_conf = getCorosyncConf()
    new_nodeid = getHighestnodeid(corosync_conf) + 1
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
        new_corosync_conf += "        ring0_addr: %s\n" % (node)
        new_corosync_conf += "        nodeid: %d\n" % (new_nodeid)
        new_corosync_conf += "       }\n"
        new_corosync_conf += corosync_conf[count:]
        if num_nodes_in_conf == 2:
            new_corosync_conf = rmQuorumOption(new_corosync_conf,("two_node","1"))
        setCorosyncConf(new_corosync_conf)

        run(["corosync-cmapctl", "-s", "nodelist.node." +
            str(new_nodeid - 1) + ".nodeid", "u32", str(new_nodeid)])
        run(["corosync-cmapctl", "-s", "nodelist.node." +
            str(new_nodeid - 1) + ".ring0_addr", "str", node])
    else:
        err("unable to find nodelist in corosync.conf")

    return True

# TODO: Need to make this smarter about parsing files not generated by pcs
def removeNodeFromCorosync(node):
    error = False
    node_found = False
    num_nodes_in_conf = 0
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            node_found = True
        num_nodes_in_conf = num_nodes_in_conf + 1

    if not node_found:
        return False

    corosync_conf = getCorosyncConf().split("\n")
    for x in range(len(corosync_conf)):
        if corosync_conf[x].find("node {") != -1:
            if corosync_conf[x+1].find("ring0_addr: "+node ) != -1:
                match = re.search(r'nodeid:.*(\d+)', corosync_conf[x+2])
                if match:
                    nodeid = match.group(1)
                else:
                    print "Error: Unable to determine nodeid for %s" % node
                    error = True
                    break
                new_corosync_conf = "\n".join(corosync_conf[0:x] + corosync_conf[x+4:])
                if num_nodes_in_conf == 3:
                    new_corosync_conf = addQuorumOption(new_corosync_conf,("two_node","1"))
                setCorosyncConf(new_corosync_conf)
                run(["corosync-cmapctl", "-D", "nodelist.node." +
                    str(int(nodeid)-1) + ".ring0_addr"])
                run(["corosync-cmapctl", "-D", "nodelist.node." +
                    str(int(nodeid)-1) + ".nodeid"])

    if error:
        return False
    else:
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

def getHighestnodeid(corosync_conf):
    highest = 0
    corosync_conf = getCorosyncConf()
    p = re.compile(r"nodeid:\s*([0-9]+)")
    mall = p.findall(corosync_conf)
    for m in mall:
        if int(m) > highest:
            highest = int(m)
    return highest

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
    if command[0:3] == "crm" or command == "cibadmin":
        args[0] = settings.pacemaker_binaries + command
    if command[0:8] == "corosync":
        args[0] = settings.corosync_binaries + command
        
    try:
        if "--debug" in pcs_options:
            print "Running: " + " ".join(args)

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

def is_group(group_id):
    return does_exist("//group[@id='"+group_id+"']")

def is_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"']")

def is_stonith_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"' and @class='stonith']")

def is_resource_clone(resource_id):
    return does_exist("//clone//primitive[@id='"+resource_id+"']")

def is_resource_masterslave(resource_id):
    return does_exist("//master//primitive[@id='"+resource_id+"']")

def get_resource_master_id(resource_id):
    dom = get_cib_dom()
    primitives = dom.getElementsByTagName("primitive")
    for p in primitives:
        if p.getAttribute("id") == resource_id:
            if p.parentNode.tagName == "master":
                return p.parentNode.getAttribute("id")
    return None

def is_valid_constraint_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"']") or \
            does_exist("//group[@id='"+resource_id+"']") or \
            does_exist("//clone[@id='"+resource_id+"']") or \
            does_exist("//master[@id='"+resource_id+"']")

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

# Check and see if the specified resource (or stonith) type is present on the
# file system and properly responds to a meta-data request
def is_valid_resource(resource, caseInsensitiveCheck=False):
    found_resource = False
    stonith_resource = False
    if resource.startswith("ocf:"):
        resource_split = resource.split(":",3)
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

# Create an object in the cib
# Returns output, retval
def add_to_cib(scope, xml):
    args = ["cibadmin"]
    args = args  + ["-o", "resources", "-C", "-X", xml]
    return run(args)

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

# Adds the specified rule to the element in the dom
def rule_add(elem, argv):
# Check if valid rule argv
    rule_type = "expression"
    if len(argv) != 0:
        if argv[0] == "date":
            rule_type = "date_expression"

    if rule_type != "expression" and rule_type != "date_expression":
        err("rule_type must either be expression or date_expression")

    args = resource.convert_args_to_tuples(argv)
    dict_args = dict()
    for k,v in args:
        dict_args[k] = v
#    if rule_type == "expression": 
#        if "operation" not in dict_args or "attribute" not in dict_args:
#            err("with rule_type: expression you must specify an attribute and operation")
#    elif rule_type == "date_expression":
#        if "operation" not in dict_args or ("start" not in dict_args and "stop" not in dict_args):
#            err("with rule_type: date_expression you must specify an operation and a start/end")


    exp_arg = []
    for arg in argv:
        if arg.find('=') == -1:
            exp_arg.append(arg)
    if len(exp_arg) == 0:
        err("no rule expression was specified")
        
    if exp_arg[0] not in ["defined","not_defined", "date", "date-spec"] and len(exp_arg) >= 2 and exp_arg[1] not in ["lt","gt","lte","gte","eq","ne"]:
        err("'%s' is not a valid rule expression" % " ".join(exp_arg))

    date_spec = False

    if len(exp_arg) >= 1:
        if exp_arg[0] == "date":
            args.append(("operation",exp_arg[1]))
            rule_type = "date_expression"
        elif exp_arg[0] == "date-spec":
            args.append(("operation","date_spec"))
            rule_type = "date_expression"
            date_spec = True
        elif exp_arg[1] in ["lt","gt","lte","gte","eq","ne"] and len(exp_arg) >= 3:
            args.append(("attribute",exp_arg[0]))
            args.append(("operation",exp_arg[1]))
            args.append(("value",exp_arg[2]))
        elif exp_arg[0] in ["defined","not_defined"]:
            args.append(("attribute",exp_arg[1]))
            args.append(("operation",exp_arg[0]))
            
    rule = ET.SubElement(elem,"rule")
    expression = ET.SubElement(rule,rule_type)
    if date_spec:
        subexpression = ET.SubElement(expression,"date_spec")


    for arg in args:
        if arg[0] == "id":
            rule.set(arg[0], arg[1])
        elif arg[0] == "score":
            if is_score_or_opt(arg[1]):
                rule.set(arg[0], arg[1])
            else:
                rule.set("score-attribute","pingd")
        elif arg[0] == "role":
                rule.set(arg[0], arg[1])
        else:
            if date_spec:
                if arg[0] == "operation":
                    expression.set(arg[0],arg[1])
                else:
                    subexpression.set(arg[0],arg[1])
            else:
                expression.set(arg[0],arg[1])

    if rule.get("score") == None and rule.get("score-attribute") == None:
        rule.set("score", "INFINITY")

    dom = get_cib_dom()
    if rule.get("id") == None:
        rule.set("id", find_unique_id(dom,elem.get("id") + "-rule"))
    if expression.get("id") == None:
        expression.set("id", find_unique_id(dom,rule.get("id") + "-expr"))
    if date_spec and subexpression.get("id") == None:
        subexpression.set("id", find_unique_id(dom, expression.get("id")+"-datespec"))
    if "score" in elem.attrib:
        del elem.attrib["score"]
    if "node" in elem.attrib:
        del elem.attrib["node"]
    return elem


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
            if node not in nas:
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
        err("can't remove property property: '%s' that doesn't exist" % (prop))


    args = ["cibadmin", "-c", "-R", "--xml-text", crm_config.toxml()]
    output, retVal = run(args)
    if output != "":
        print output

def setAttribute(a_type, a_name, a_value):
    args = ["crm_attribute", "--type", a_type, "--attr-name", a_name,
            "--attr-value", a_value]

    if a_value == "":
        args.append("-D")

    output, retval = run(args)
    if retval != 0:
        print output

def getExpression(dom, element, argv, id_suffix=""):
    if len(argv) < 2:
        return None

    unary_expression = False
    if len(argv) == 2 and (argv[0] == "defined" or argv[0] == "not_defined"):
        expression = dom.createElement("expression")
        unary_expression = True
        expression.setAttribute("operation", argv[0])
        expression.setAttribute("attribute",argv[1])
        expression.setAttribute("id", find_unique_id (dom, element.getAttribute("id") + "-expr"))
        return expression
    elif argv[0] == "date":
        expression = dom.createElement("date_expression")
        expression.setAttribute("id", find_unique_id (dom, element.getAttribute("id") + "-rule" + id_suffix))
        date_expression = True
        argv.pop(0)
        count = 0
        for i in range(0,len(argv)):
            val = argv[i].split('=')
            expression.setAttribute(val[0], val[1])
            if val[0] == "operation" and val[1] == "date_spec":
                date_spec = getDateSpec(dom, expression, argv[(i+1):])
                expression.appendChild(date_spec)
                break
        expression.setAttribute("id", find_unique_id (dom, element.getAttribute("id") + "-dateexpr" + id_suffix))
        return expression
    elif len(argv) == 3 and argv[1] in ["lt","gt","lte","gte","eq","ne"]:
        expression = dom.createElement("expression")
        expression.setAttribute("attribute", argv[0])
        expression.setAttribute("operation", argv[1])
        expression.setAttribute("value", argv[2])
        expression.setAttribute("id", find_unique_id (dom, element.getAttribute("id") + "-expr" + id_suffix))
        return expression
    else:
        return None


def getDateSpec(dom, element, argv):
    date_spec = dom.createElement("date_spec")
    for val in argv:
        if val.find('=') != -1:
            date_spec.setAttribute(val.split('=')[0],val.split('=')[1])
    date_spec.setAttribute("id", find_unique_id(dom,element.getAttribute("id") + "-datespec"))
    return date_spec

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

    root = ET.fromstring(metadata)
    actions = root.find("parameters")
    valid_parameters = ["pcmk_host_list", "pcmk_host_map", "pcmk_host_check", "pcmk_host_argument", "pcmk_arg_map", "pcmk_list_cmd", "pcmk_status_cmd", "pcmk_monitor_cmd"]
    valid_parameters = valid_parameters + ["stonith-timeout", "priority"]
    for a in ["off","on","status","list","metadata","monitor", "reboot"]:
        valid_parameters.append("pcmk_" + a + "_action")
        valid_parameters.append("pcmk_" + a + "_timeout")
        valid_parameters.append("pcmk_" + a + "_retries")
    bad_parameters = []
    for action in actions.findall("parameter"):
        valid_parameters.append(action.attrib["name"])
    for key,value in ra_values:
        if key not in valid_parameters:
            bad_parameters.append(key)
    return bad_parameters 

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

# Returns true if we have a valid op attribute
def is_valid_op_attr(attr):
    if attr in ["id","name","interval","description","start-delay","interval-origin","timeout","enabled", "record-pending", "role", "requires","on-fail", "OCF_CHECK_LEVEL"]:
        return True
    return False

# Test if 'var' is a score or option (contains an '=')
def is_score_or_opt(var):
    if var == "INFINITY" or var == "-INFINITY" or var.isdigit():
        return True
    elif var.find('=') != -1:
        return True
    return False

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

    if re.search(r'(Red Hat Enterprise Linux Server|CentOS|Scientific Linux) release 6\.', issue):
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
    if is_systemctl():
        run(["systemctl", "enable", "corosync.service"])
        run(["systemctl", "enable", "pacemaker.service"])
    else:
        run(["chkconfig", "corosync", "on"])
        run(["chkconfig", "pacemaker", "on"])

def disableServices():
    if is_systemctl():
        run(["systemctl", "disable", "corosync.service"])
        run(["systemctl", "disable", "pacemaker.service"])
    else:
        run(["chkconfig", "corosync", "off"])
        run(["chkconfig", "pacemaker", "off"])
