from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import os

from pcs import (
    resource,
    usage,
    utils,
)
from pcs.qdevice import qdevice_status_cmd
from pcs.quorum import quorum_status_cmd
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker_state import ClusterState

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
        cluster_pcsd_status(argv)
    elif (sub_cmd == "xml"):
        xml_status()
    elif (sub_cmd == "corosync"):
        corosync_status()
    elif sub_cmd == "qdevice":
        try:
            qdevice_status_cmd(
                utils.get_library_wrapper(),
                argv,
                utils.get_modificators()
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(e, "status", sub_cmd)
    elif sub_cmd == "quorum":
        try:
            quorum_status_cmd(
                utils.get_library_wrapper(),
                argv,
                utils.get_modificators()
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        except CmdLineInputError as e:
            utils.exit_on_cmdline_input_errror(e, "status", sub_cmd)
    else:
        usage.status()
        sys.exit(1)

def full_status():
    if "--hide-inactive" in utils.pcs_options and "--full" in utils.pcs_options:
        utils.err("you cannot specify both --hide-inactive and --full")

    monitor_command = ["crm_mon", "--one-shot"]
    if "--hide-inactive" not in utils.pcs_options:
        monitor_command.append('--inactive')
    if "--full" in utils.pcs_options:
        monitor_command.extend(
            ["--show-detail", "--show-node-attributes", "--failcounts"]
        )

    output, retval = utils.run(monitor_command)

    if (retval != 0):
        utils.err("cluster is not currently running on this node")

    if not utils.usefile or "--corosync_conf" in utils.pcs_options:
        cluster_name = utils.getClusterName()
        print("Cluster name: %s" % cluster_name)

    if utils.stonithCheck():
        print("WARNING: no stonith devices and stonith-enabled is not false")

    if (
        not utils.usefile
        and
        not utils.is_rhel6()
        and
        utils.corosyncPacemakerNodeCheck()
    ):
        print("WARNING: corosync and pacemaker node names do not match (IPs used in setup?)")

    print(output)

    if not utils.usefile:
        if  "--full" in utils.pcs_options and utils.hasCorosyncConf():
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
        if utils.hasCorosyncConf():
            corosync_nodes = utils.getNodesFromCorosyncConf()
        else:
            corosync_nodes = []
        try:
            pacemaker_nodes = sorted([
                node.attrs.name for node
                in ClusterState(utils.getClusterStateXml()).node_section.nodes
                if node.attrs.type != 'remote'
            ])
        except LibraryError as e:
            utils.process_library_reports(e.args)
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
            if node not in online_nodes:
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

    if not utils.usefile and utils.hasCorosyncConf():
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

def is_service_running(service):
    if utils.is_systemctl():
        dummy_output, retval = utils.run(["systemctl", "status", service])
    else:
        dummy_output, retval = utils.run(["service", service, "status"])
    return retval == 0

def print_pcsd_daemon_status():
    print("PCSD Status:")
    if os.getuid() == 0:
        cluster_pcsd_status([], True)
    else:
        err_msgs, exitcode, std_out, dummy_std_err = utils.call_local_pcsd(
            ['status', 'pcsd'], True
        )
        if err_msgs:
            for msg in err_msgs:
                print(msg)
        if 0 == exitcode:
            print(std_out)
        else:
            print("Unable to get PCSD status")

def check_nodes(node_list, prefix=""):
    """
    Print pcsd status on node_list, return if there is any pcsd not online
    """
    if not utils.is_rhel6():
        pm_nodes = utils.getPacemakerNodesID(allow_failure=True)
        cs_nodes = utils.getCorosyncNodesID(allow_failure=True)

    STATUS_ONLINE = 0
    status_desc_map = {
        STATUS_ONLINE: 'Online',
        3: 'Unable to authenticate'
    }
    status_list = []
    def report(node, returncode, output):
        print("{0}{1}: {2}".format(
            prefix,
            node if utils.is_rhel6() else utils.prepare_node_name(
                node, pm_nodes, cs_nodes
            ),
            status_desc_map.get(returncode, 'Offline')
        ))
        status_list.append(returncode)

    utils.run_parallel(
        utils.create_task_list(report, utils.checkAuthorization, node_list)
    )

    return any([status != STATUS_ONLINE for status in status_list])

# If no arguments get current cluster node status, otherwise get listed
# nodes status
def cluster_pcsd_status(argv, dont_exit=False):
    bad_nodes = False
    if len(argv) == 0:
        nodes = utils.getNodesFromCorosyncConf()
        if len(nodes) == 0:
            if utils.is_rhel6():
                utils.err("no nodes found in cluster.conf")
            else:
                utils.err("no nodes found in corosync.conf")
        bad_nodes = check_nodes(nodes, "  ")
    else:
        bad_nodes = check_nodes(argv, "  ")
    if bad_nodes and not dont_exit:
        sys.exit(2)
