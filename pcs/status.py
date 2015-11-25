from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import os

import resource
import cluster
import settings
import usage
import utils


def status_cmd(argv):
    if len(argv) == 0:
        full_status()
        sys.exit(0)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.status(argv)
    elif (sub_cmd == "resources"):
        resource.resource_show(argv)
    elif (sub_cmd == "groups"):
        resource.resource_group_list(argv)
    elif (sub_cmd == "cluster"):
        cluster_status(argv)
    elif (sub_cmd == "nodes"):
        nodes_status(argv)
    elif (sub_cmd == "pcsd"):
        cluster.cluster_gui_status(argv)
    elif (sub_cmd == "xml"):
        xml_status()
    elif (sub_cmd == "corosync"):
        corosync_status()
    else:
        usage.status()
        sys.exit(1)

def full_status():
    if "--full" in utils.pcs_options:
        (output, retval) = utils.run(["crm_mon", "-1", "-r", "-R", "-A", "-f"])
    else:
        (output, retval) = utils.run(["crm_mon", "-1", "-r"])

    if (retval != 0):
        utils.err("cluster is not currently running on this node")

    if not utils.usefile or "--corosync_conf" in utils.pcs_options:
        cluster_name = utils.getClusterName()
        print("Cluster name: %s" % cluster_name)

    if utils.stonithCheck():
        print("WARNING: no stonith devices and stonith-enabled is not false")

    if not utils.is_rhel6() and utils.corosyncPacemakerNodeCheck():
        print("WARNING: corosync and pacemaker node names do not match (IPs used in setup?)")

    print(output)

    if not utils.usefile:
        print_pcsd_daemon_status()
        print()
        utils.serviceStatus("  ")

# Parse crm_mon for status
def nodes_status(argv):
    if len(argv) == 1 and argv[0] == "pacemaker-id":
        for node_id, node_name in utils.getPacemakerNodesID().items():
            print("{0} {1}".format(node_id, node_name))
        return

    if len(argv) == 1 and argv[0] == "corosync-id":
        for node_id, node_name in utils.getCorosyncNodesID().items():
            print("{0} {1}".format(node_id, node_name))
        return

    if len(argv) == 1 and (argv[0] == "config"):
        corosync_nodes = utils.getNodesFromCorosyncConf()
        pacemaker_nodes = utils.getNodesFromPacemaker()
        print("Corosync Nodes:")
        if corosync_nodes:
            print(" " + " ".join(corosync_nodes))
        print("Pacemaker Nodes:")
        if pacemaker_nodes:
            print(" " + " ".join(pacemaker_nodes))

        return

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
        print("Corosync Nodes:")
        print(" ".join([" Online:"] + online_nodes))
        print(" ".join([" Offline:"] + offline_nodes))
        if argv[0] != "both":
            sys.exit(0)

    info_dom = utils.getClusterState()

    nodes = info_dom.getElementsByTagName("nodes")
    if nodes.length == 0:
        utils.err("No nodes section found")

    onlinenodes = []
    offlinenodes = []
    standbynodes = []
    maintenancenodes = []
    remote_onlinenodes = []
    remote_offlinenodes = []
    remote_standbynodes = []
    remote_maintenancenodes = []
    for node in nodes[0].getElementsByTagName("node"):
        node_name = node.getAttribute("name")
        node_remote = node.getAttribute("type") == "remote"
        if node.getAttribute("online") == "true":
            if node.getAttribute("standby") == "true":
                if node_remote:
                    remote_standbynodes.append(node_name)
                else:
                    standbynodes.append(node_name)
            elif node.getAttribute("maintenance") == "true":
                if node_remote:
                    remote_maintenancenodes.append(node_name)
                else:
                    maintenancenodes.append(node_name)
            else:
                if node_remote:
                    remote_onlinenodes.append(node_name)
                else:
                    onlinenodes.append(node_name)
        else:
            if node_remote:
                remote_offlinenodes.append(node_name)
            else:
                offlinenodes.append(node_name)

    print("Pacemaker Nodes:")
    print(" ".join([" Online:"] + onlinenodes))
    print(" ".join([" Standby:"] + standbynodes))
    print(" ".join([" Maintenance:"] + maintenancenodes))
    print(" ".join([" Offline:"] + offlinenodes))

    print("Pacemaker Remote Nodes:")
    print(" ".join([" Online:"] + remote_onlinenodes))
    print(" ".join([" Standby:"] + remote_standbynodes))
    print(" ".join([" Maintenance:"] + remote_maintenancenodes))
    print(" ".join([" Offline:"] + remote_offlinenodes))

# TODO: Remove, currently unused, we use status from the resource.py
def resources_status(argv):
    info_dom = utils.getClusterState()

    print("Resources:")

    resources = info_dom.getElementsByTagName("resources")
    if resources.length == 0:
        utils.err("no resources section found")

    for resource in resources[0].getElementsByTagName("resource"):
        nodes = resource.getElementsByTagName("node")
        node_line = ""
        if nodes.length > 0:
            for node in nodes:
                node_line += node.getAttribute("name") + " "

        print("", resource.getAttribute("id"), end=' ')
        print("(" + resource.getAttribute("resource_agent") + ")", end=' ')
        print("- " + resource.getAttribute("role") + " " + node_line)

def cluster_status(argv):
    (output, retval) = utils.run(["crm_mon", "-1", "-r"])

    if (retval != 0):
        utils.err("cluster is not currently running on this node")

    first_empty_line = False
    print("Cluster Status:")
    for line in output.splitlines():
        if line == "":
            if first_empty_line:
                break
            first_empty_line = True
            continue
        else:
            print("",line)

    if not utils.usefile:
        print()
        print_pcsd_daemon_status()

def corosync_status():
    (output, retval) = utils.run(["corosync-quorumtool", "-l"])
    if retval != 0:
        utils.err("corosync not running")
    else:
        print(output, end="")

def xml_status():
    (output, retval) = utils.run(["crm_mon", "-1", "-r", "-X"])

    if (retval != 0):
        utils.err("running crm_mon, is pacemaker running?")
    print(output, end="")

def is_cman_running():
    if utils.is_systemctl():
        output, retval = utils.run(["systemctl", "status", "cman.service"])
    else:
        output, retval = utils.run(["service", "cman", "status"])
    return retval == 0

def is_corosyc_running():
    if utils.is_systemctl():
        output, retval = utils.run(["systemctl", "status", "corosync.service"])
    else:
        output, retval = utils.run(["service", "corosync", "status"])
    return retval == 0

def is_pacemaker_running():
    if utils.is_systemctl():
        output, retval = utils.run(["systemctl", "status", "pacemaker.service"])
    else:
        output, retval = utils.run(["service", "pacemaker", "status"])
    return retval == 0

def print_pcsd_daemon_status():
    print("PCSD Status:")
    if os.getuid() == 0:
        cluster.cluster_gui_status([], True)
    else:
        err_msgs, exitcode, std_out, std_err = utils.call_local_pcsd(
            ['status', 'pcsd'], True
        )
        if err_msgs:
            for msg in err_msgs:
                print(msg)
        if 0 == exitcode:
            print(std_out)
        else:
            print("Unable to get PCSD status")

