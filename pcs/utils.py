import os, subprocess
import sys
import pcs
import xml.dom.minidom
import urllib,urllib2
from xml.dom.minidom import parseString
import re


# usefile & filename variables are set in pcs module
usefile = False
filename = ""

# Set the corosync.conf file on the specified node
def setCorosyncConfig(node,config):
    data = urllib.urlencode({'corosync_conf':config})
    sendHTTPRequest(node, 'remote/set_corosync_conf', data)

def startCluster(node):
    sendHTTPRequest(node, 'remote/cluster_start')

def stopCluster(node):
    sendHTTPRequest(node, 'remote/cluster_stop')

def sendHTTPRequest(host, request, data = None):
    url = 'http://' + host + ':2222/' + request
    opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
    urllib2.install_opener(opener)
    try:
        result = opener.open(url,data)
        html = result.read()
        print host + ": " + html
    except urllib2.HTTPError, e:
        print "Error connecting to %s - (HTTP error: %d)" % (host,e.code)
    except urllib2.URLError, e:
        print "Unable to connect to %s (%s)" % (host, e.reason)

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
    return open(conf).read()

def getCorosyncNodes():
    cc = getCorosyncConf()
    nodes = []

    ring_re = re.compile(r'ring0_addr:\s+([\w-]*)')
    for line in cc.split('\n'):
        x = ring_re.search(line)
        if x and x.groups():
            nodes.append(x.groups()[0])

    return nodes

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
        output = p.stdout.read()
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
