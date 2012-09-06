import sys
import usage
import utils
import xml.dom.minidom
import re
import resource
import cluster
from xml.dom.minidom import parseString

def status_cmd(argv):
    if len(argv) == 0:
        full_status()
        sys.exit(0)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.status()
    elif (sub_cmd == "resources"):
        resource.resource_show(argv)
    elif (sub_cmd == "groups"):
        resource.resource_group_list(argv)
    elif (sub_cmd == "cluster"):
        cluster_status(argv)
    elif (sub_cmd == "nodes"):
        nodes_status(argv)
    elif (sub_cmd == "actions"):
        actions_status(argv)
    elif (sub_cmd == "pcsd"):
        cluster.cluster_gui_status(argv)
    elif (sub_cmd == "token"):
        token_status(argv)
    elif (sub_cmd == "xml"):
        xml_status()
    elif (sub_cmd == "corosync"):
        corosync_status()
    else:
        usage.status()
        sys.exit(1)

def full_status():
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1", "-r"])

    if (retval != 0):
        print "Error running crm_mon, is pacemaker running?"
        sys.exit(1)

    print output

def actions_status(argv):
    print "Not Yet Implemented"

# Parse crm_mon for status
def nodes_status(argv):
    if len(argv) == 1 and (argv[0] == "corosync" or argv[0] == "both"):
        all_nodes = utils.getNodesFromCorosyncConf()
        online_nodes = utils.getCorosyncActiveNodes()
        offline_nodes = []
        for node in all_nodes:
            if node in online_nodes:
                next
            else:
                offline_nodes.append(node)

        online_nodes.sort()
        offline_nodes.sort()
        print "Corosync Nodes:"
        print " Online:",
        for node in online_nodes:
            print node,
        print ""
        print " Offline:",
        for node in offline_nodes:
            print node,
        print ""
        if argv[0] != "both":
            sys.exit(0)

    info_dom = utils.getClusterState()

    nodes = info_dom.getElementsByTagName("nodes")
    if nodes.length == 0:
        print "Error: No nodes section found"
        sys.exit(1)

    onlinenodes = []
    offlinenodes = []
    standbynodes = []
    for node in nodes[0].getElementsByTagName("node"):
        if node.getAttribute("online") == "true":
            if node.getAttribute("standby") == "true":
                standbynodes.append(node.getAttribute("name"))
            else:
                onlinenodes.append(node.getAttribute("name"))
        else:
            offlinenodes.append(node.getAttribute("name"))

    print "Pacemaker Nodes:"

    print " Online:",
    for node in onlinenodes:
        print node,
    print ""

    print " Standby:",
    for node in standbynodes:
        print node,
    print ""

    print " Offline:",
    for node in offlinenodes:
        print node,
    print ""

# TODO: Remove, currently unused, we use status from the resource.py
def resources_status(argv):
    info_dom = utils.getClusterState()

    print "Resources:"

    groups = {}
    nongroup_resources = []
    resources = info_dom.getElementsByTagName("resources")
    if resources.length == 0:
        print "Error: No resources section found"
        sys.exit(1)

    for resource in resources[0].getElementsByTagName("resource"):
        nodes = resource.getElementsByTagName("node")
        node_line = ""
        if nodes.length > 0:
            for node in nodes:
                node_line += node.getAttribute("name") + " "

        print "", resource.getAttribute("id"),
        print "(" + resource.getAttribute("resource_agent") + ")",
        print "- " + resource.getAttribute("role") + " " + node_line

def cluster_status(argv):
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1", "-r"])

    if (retval != 0):
        print "Error running crm_mon, is pacemaker running?"
        sys.exit(1)

    in_cluster = False
    print "Cluster Status:"
    for line in output.splitlines():
        if not in_cluster:
            if line.find("============") == 0:
                in_cluster = True
                continue
        else:
            if line.find("============") == 0:
                break

            print "",line

def corosync_status():
    (output, retval) = utils.run(["/sbin/corosync-quorumtool", "-l"])
    if retval != 0:
        print "Error: Corosync not running"
        sys.exit(1)
    else:
        print output,

def xml_status():
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1", "-r", "-X"])

    if (retval != 0):
        print "Error running crm_mon, is pacemaker running?"
        sys.exit(1)
    print output
