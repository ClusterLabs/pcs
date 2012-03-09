import sys
import usage
import utils
import xml.dom.minidom
import re
from xml.dom.minidom import parseString

def status_cmd(argv):
    if len(argv) == 0:
        cluster_status([])
        print
        resources_status([])
        print
        nodes_status([])
        sys.exit(0)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.status()
    elif (sub_cmd == "resources"):
        resources_status(argv)
    elif (sub_cmd == "cluster"):
        cluster_status(argv)
    elif (sub_cmd == "nodes"):
        nodes_status(argv)
    elif (sub_cmd == "actions"):
        actions_status(argv)
    else:
        usage.property()
        sys.exit(1)

def actions_status(argv):
    print "Not Yet Implemented"

# Parse crm_mon for status
def nodes_status(argv):
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1"])

    if (retval != 0):
        print "Error running crm_mon!"
        sys.exit(1)

    print "Nodes:"

    onlinereg = re.compile(r"^Online: (.*)$",re.M)
    onlinematch = onlinereg.search(output)
    if onlinematch:
        onlinenodes = onlinematch.group(1).split(" ")
        onlinenodes.pop(0) 
        onlinenodes.pop()
        print " Online:",
        for node in onlinenodes:
            print node,
        print ""

    offlinereg = re.compile(r"^OFFLINE: (.*)$", re.M)
    offlinematch = offlinereg.search(output)
    if offlinematch:
        offlinenodes = offlinematch.group(1).split(" ")
        offlinenodes.pop(0) 
        offlinenodes.pop()
        print " Offline:",
        for node in offlinenodes:
            print node,
        print ""

def resources_status(argv):
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1", "-r"])

    if (retval != 0):
        print "Error running crm_mon!"
        sys.exit(1)

    print "Resources:"
    in_resources = False
    resourcere = re.compile(r"\s+(\S+)\s+\((\S+)\):\s+(.*)$",re.M)
    resource_list = []
    blank_lines = 0
    for line in output.splitlines():
        if not in_resources:
            if line.find("Full list of resources:") == 0:
                in_resources = True
                continue
        else:
            if line.find("Resource Group:") == 1:
                continue
            if len(line) == 0:
                blank_lines += 1
                if blank_lines == 2:
                    break
                continue

            resource_match = resourcere.search(line)
            if (resource_match):
                resource_list.append((resource_match.group(1), resource_match.group(2), resource_match.group(3)))
                print " " + resource_match.group(1),
                print "("+ resource_match.group(2)+ ")",
                print "-", resource_match.group(3)


def cluster_status(argv):
    (output, retval) = utils.run(["/usr/sbin/crm_mon", "-1", "-r"])

    if (retval != 0):
        print "Error running crm_mon!"
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
