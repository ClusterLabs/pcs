import os, subprocess
import sys
import pcs
import xml.dom.minidom
import urllib,urllib2
from xml.dom.minidom import parseString
import re
import json


# usefile & filename variables are set in pcs module
usefile = False
filename = ""
pcs_options_hash = {}

# Check status of node
def checkStatus(node):
    out = sendHTTPRequest(node, 'remote/status', None, False)
    return out

def updateToken(node,username,password):
    data = urllib.urlencode({'username':username, 'password':password})
    out = sendHTTPRequest(node, 'remote/auth', data, False)
    if out[0] != 0:
        print "ERROR: Unable to connect to pcs-gui on %s" % node
        print out
        exit(1)
    token = out[1]
    if token == "":
        print "ERROR: Username and/or password is incorrect"
        exit(1)

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
    sendHTTPRequest(node, 'remote/set_corosync_conf', data)

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
        except ValueError:
            return 1,output
        return 0,myout
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
    url = 'http://' + host + ':2222/' + request
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
    tokens = readTokens()
    if host in tokens:
        opener.addheaders.append(('Cookie', 'token='+tokens[host]))
    urllib2.install_opener(opener)
    try:
        result = opener.open(url,data)
        html = result.read()
        if printResult:
            print host + ": " + html.strip()
        return (0,html)
    except urllib2.HTTPError, e:
        if printResult:
            if e.code == 401:
                print "Unable to authenticate to %s - (HTTP error: %d)" % (host,e.code)
            else:
                print "Error connecting to %s - (HTTP error: %d)" % (host,e.code)
        if e.code == 401:
            return (3,"Unable to authenticate to %s - (HTTP error: %d)" % (host,e.code))
        else:
            return (1,"Error connecting to %s - (HTTP error: %d)" % (host,e.code))
    except urllib2.URLError, e:
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

def getCorosyncConf(conf='/etc/corosync/corosync.conf'):
    try:
        out = open(conf).read()
    except IOError:
        return ""
    return out

def setCorosyncConf(corosync_config, conf_file='/etc/corosync/corosync.conf'):
    try:
        f = open(conf_file,'w')
        f.write(corosync_config)
        f.close()
    except IOError:
        print "ERROR: Unable to write corosync configuration file, try running as root."
        exit(1)

def getCorosyncActiveNodes():
    args = ["/sbin/corosync-cmapctl"]
    nodes = []
    output,retval = run(args)
    if retval != 0:
        return []

    p = re.compile(r"^nodelist\.node\.\d+\.ring\d+_addr.*= (.*)", re.M)
    nodes = p.findall(output)
    return nodes

# Add node specified to corosync.conf and insert into corosync (if running)
def addNodeToCorosync(node):
# Before adding, make sure node isn't already in corosync.conf or in running
# corosync process
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            print "Node already exists in corosync.conf"
            sys.exit(1)
    for c_node in getCorosyncActiveNodes():
        if c_node == node:
            print "Node already exists in running corosync"
            sys.exit(1)
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

        run(["/sbin/corosync-cmapctl", "-s", "nodelist.node." +
            str(new_nodeid - 1) + ".nodeid", "u32", str(new_nodeid)])
        run(["/sbin/corosync-cmapctl", "-s", "nodelist.node." +
            str(new_nodeid - 1) + ".ring0_addr", "str", node])
    else:
        print "Unable to find nodelist in corosync.conf"
        sys.exit(1)

    return True

# TODO: Need to make this smarter about parsing files not generated by pcs
def removeNodeFromCorosync(node):
    node_found = False
    for c_node in getNodesFromCorosyncConf():
        if c_node == node:
            node_found = True
            break

    corosync_conf = getCorosyncConf().split("\n")
    for x in range(len(corosync_conf)):
        if corosync_conf[x].find("node {") != -1:
            if corosync_conf[x+1].find("ring0_addr: "+node ) != -1:
                match = re.search(r'nodeid:.*(\d+)', corosync_conf[x+2])
                if match:
                    nodeid = match.group(1)
                else:
                    print "Error: Unable to determine nodeid for %s" % node
                new_corosync_conf = "\n".join(corosync_conf[0:x] + corosync_conf[x+4:])
                print new_corosync_conf
                setCorosyncConf(new_corosync_conf)
                run(["/sbin/corosync-cmapctl", "-D", "nodelist.node." +
                    str(nodeid) + "."])

def getHighestnodeid(corosync_conf):
    highest = 0
    corosync_conf = getCorosyncConf()
    p = re.compile(r"nodeid:\s*([0-9]+)")
    mall = p.findall(corosync_conf)
    for m in mall:
        if int(m) > highest:
            highest = int(m)
    return highest

# Run command, with environment and return (output, retval)
def run(args):
    env_var = os.environ
    if usefile:
        env_var["CIB_file"] = filename

        if not os.path.isfile(filename):
            try:
                write_empty_cib(filename)
            except IOError:
                print "Unable to write to file: " + filename
                sys.exit(1)

    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env = env_var)
        output,stderror = p.communicate()
        p.wait()
        returnVal = p.returncode
    except OSError:
        print "Unable to locate command: " + args[0]
        sys.exit(1)

    return output, returnVal

# Check is something exists in the CIB, if it does return it, if not, return
#  an empty string
def does_exist(xpath_query):
    args = ["cibadmin", "-Q", "--xpath", xpath_query]
    output,retval = run(args)
    if (retval != 0):
        return False
    return True

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
        print "Error: unable to get cib"
        sys.exit(1)
    return output

def get_cib_dom():
    try:
        dom = parseString(get_cib())
        return dom
    except:
        print "Error: unable to get cib"
        sys.exit(1)

# Replace only configuration section of cib with dom passed
def replace_cib_configuration(dom):
    output, retval = run(["cibadmin", "--replace", "-o", "configuration", "-X", dom.toxml()])
    if retval != 0:
        print "ERROR: Unable to update cib"
        print output
        sys.exit(1)

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

def set_unmanaged(resource):
    args = ["crm_resource", "--resource", resource, "--set-parameter",
            "is-managed", "--meta", "--parameter-value", "false"]
    return run(args)

# If the property exists, remove it and replace it with the new property
# If the value is blank, then we just remove it
def set_cib_property(prop, value):
    crm_config = get_cib_xpath("//crm_config")
    if (crm_config == ""):
        print "Unable to get crm_config, is pacemaker running?"
        sys.exit(1)
    document = parseString(crm_config)
    crm_config = document.documentElement
    cluster_property_set = crm_config.getElementsByTagName("cluster_property_set")[0]
    property_exists = False
    for child in cluster_property_set.getElementsByTagName("nvpair"):
        if (child.nodeType != xml.dom.minidom.Node.ELEMENT_NODE):
            break
        if (child.getAttribute("id") == "cib-bootstrap-options-" + prop):
            child.parentNode.removeChild(child)
            property_exists = True
            break

# If the value is empty we don't add it to the cluster
    if value != "":
        new_property = document.createElement("nvpair")
        new_property.setAttribute("id","cib-bootstrap-options-"+prop)
        new_property.setAttribute("name",prop)
        new_property.setAttribute("value",value)
        cluster_property_set.appendChild(new_property)


    args = ["cibadmin", "-c", "-R", "--xml-text", cluster_property_set.toxml()]
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
    (output, retval) = run(["/usr/sbin/crm_mon", "-1", "-X","-r"])
    if (retval != 0):
        print "Error running crm_mon, is pacemaker running?"
        sys.exit(1)
    dom = parseString(output)
    return dom

def write_empty_cib(filename):

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
    f = open(filename, 'w')
    f.write(empty_xml)
    f.close()
