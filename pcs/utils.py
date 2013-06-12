import os, subprocess
import sys
import pcs
import xml.dom.minidom
import urllib,urllib2
from xml.dom.minidom import parseString
import xml.etree.ElementTree as ET
import re
import json
import settings
import signal


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
    out = sendHTTPRequest(node, 'remote/check_auth', None, False)
    return out

def updateToken(node,username,password):
    data = urllib.urlencode({'username':username, 'password':password})
    out = sendHTTPRequest(node, 'remote/auth', data, False)
    if out[0] != 0:
        err("unable to connect to pcsd on %s\n" % node + out[1])
    token = out[1]
    if token == "":
        err("Username and/or password is incorrect")

    tokens = readTokens()
    tokens[node] = token
    writeTokens(tokens)

    return True

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
    retval, output = sendHTTPRequest(node, 'remote/get_corosync_conf', None, False)
    return retval,output

def setCorosyncConfig(node,config):
    data = urllib.urlencode({'corosync_conf':config})
    (status, data) = sendHTTPRequest(node, 'remote/set_corosync_conf', data)
    if status != 0:
        err("Unable to set corosync config")

def startCluster(node):
    sendHTTPRequest(node, 'remote/cluster_start')

def stopCluster(node):
    sendHTTPRequest(node, 'remote/cluster_stop')

def enableCluster(node):
    sendHTTPRequest(node, 'remote/cluster_enable')

def disableCluster(node):
    sendHTTPRequest(node, 'remote/cluster_disable')

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
def sendHTTPRequest(host, request, data = None, printResult = True):
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
        if printResult:
            print host + ": " + html.strip()
        if "--debug" in pcs_options:
            print "Response Code: 0"
            print "--Debug Response Start--\n" + html,
            print "--Debug Response End--"
        return (0,html)
    except urllib2.HTTPError, e:
        if "--debug" in pcs_options:
            print "Response Code: " + e.code
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
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            err("node already exists in corosync.conf")
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
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            node_found = True
            break

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
                print new_corosync_conf
                setCorosyncConf(new_corosync_conf)
                run(["corosync-cmapctl", "-D", "nodelist.node." +
                    str(int(nodeid)-1) + ".ring0_addr"])
                run(["corosync-cmapctl", "-D", "nodelist.node." +
                    str(int(nodeid)-1) + ".nodeid"])

    if error:
        return False
    else:
        return True

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
def run(args, ignore_stderr=False):
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
        if ignore_stderr:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env = env_var, preexec_fn=subprocess_setup)
        else:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env = env_var, preexec_fn=subprocess_setup)
        output,stderror = p.communicate()
        returnVal = p.returncode
        if "--debug" in pcs_options:
            print "Return Value: " + str(returnVal)
            print "--Debug Output Start--\n" + output
            print "--Debug Output End--\n"
    except OSError:
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

def is_valid_constraint_resource(resource_id):
    return does_exist("//primitive[@id='"+resource_id+"']") or \
            does_exist("//group[@id='"+resource_id+"']") or \
            does_exist("//clone[@id='"+resource_id+"']") or \
            does_exist("//master[@id='"+resource_id+"']")

def does_resource_have_options(ra_type):
    if ra_type.startswith("ocf:") or ra_type.startswith("stonith:") or ra_type.find(':') == -1:
        return True
    return False

# Check and see if the specified resource (or stonith) type is present on the
# file system and properly responds to a meta-data request
def is_valid_resource(resource):
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
            metadata = get_metadata("/usr/lib/ocf/resource.d/" + provider + "/" + resource)
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

    (metadata, retval) = run([resource_agent_script, "meta-data"])
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
    output, retval = run(["cibadmin", "--replace", "-o", "configuration", "-X", dom.toxml()])
    if retval != 0:
        err("Unable to update cib\n"+output)

# Checks to see if id exists in the xml dom passed
def does_id_exist(dom, check_id):
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

    return False

# If the property exists, remove it and replace it with the new property
# If the value is blank, then we just remove it
def set_cib_property(prop, value):
    crm_config = get_cib_xpath("//crm_config")
    if (crm_config == ""):
        err("unable to get crm_config, is pacemaker running?")
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
        if (child.getAttribute("id") == "cib-bootstrap-options-" + prop):
            child.parentNode.removeChild(child)
            break

# If the value is empty we don't add it to the cluster
    if value != "":
        new_property = document.createElement("nvpair")
        new_property.setAttribute("id","cib-bootstrap-options-"+prop)
        new_property.setAttribute("name",prop)
        new_property.setAttribute("value",value)
        cluster_property_set.appendChild(new_property)


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
    root = ET.fromstring(metadata)
    actions = root.find("parameters")
    valid_parameters = ["pcmk_host_list", "pcmk_host_map", "pcmk_host_check", "pcmk_host_argument"]
    bad_parameters = []
    for action in actions.findall("parameter"):
        valid_parameters.append(action.attrib["name"])
    for key,value in ra_values:
        if key not in valid_parameters:
            bad_parameters.append(key)
    return bad_parameters 

def getClusterName():
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

    if re.search(r'Red Hat Enterprise Linux Server release 6\.', issue):
        return True
    else:
        return False

def err(errorText):
    sys.stderr.write("Error: %s\n" % errorText)
    sys.exit(1)

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
