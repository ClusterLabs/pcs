import sys
import os

from pcs import (
    settings,
    utils,
)
from pcs.cli.common.console_report import indent
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.reports import process_library_reports
from pcs.lib import reports
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import is_fence_history_supported
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.pacemaker.values import is_false
from pcs.lib.resource_agent import _STONITH_ACTION_REPLACED_BY
from pcs.lib.sbd import get_sbd_service_name

# pylint: disable=too-many-branches, too-many-locals, too-many-statements

def full_status(lib, argv, modifiers):
    """
    Options:
      * --hide-inactive - hide inactive resources
      * --full - show full details, node attributes and failcount
      * -f - CIB file, crm_mon accepts CIB_file environment variable
      * --corosync_conf - file corocync.conf
      * --request-timeout - HTTP timeout for node authorization check
    """
    modifiers.ensure_only_supported(
        "--hide-inactive", "--full", "-f", "--corosync_conf",
        "--request-timeout",
    )
    if argv:
        raise CmdLineInputError()
    if (
        modifiers.is_specified("--hide-inactive")
        and
        modifiers.is_specified("--full")
    ):
        utils.err("you cannot specify both --hide-inactive and --full")

    monitor_command = [
        os.path.join(settings.pacemaker_binaries, "crm_mon"),
        "--one-shot"
    ]
    if not modifiers.get("--hide-inactive"):
        monitor_command.append('--inactive')
    if modifiers.get("--full"):
        monitor_command.extend(
            ["--show-detail", "--show-node-attributes", "--failcounts"]
        )
        # by default, pending and failed actions are displayed
        # with --full, we display the whole history
        if is_fence_history_supported():
            monitor_command.append("--fence-history=3")

    stdout, stderr, retval = utils.cmd_runner().run(monitor_command)

    if retval != 0:
        utils.err("cluster is not currently running on this node")

    warnings = []
    if stderr.strip():
        for line in stderr.strip().splitlines():
            if line.startswith("DEBUG: "):
                if modifiers.get("--full"):
                    warnings.append(line)
            else:
                warnings.append(line)
    warnings.extend(status_stonith_check(modifiers))

    print("Cluster name: %s" % utils.getClusterName())
    if warnings:
        print()
        print("WARNINGS:")
        print("\n".join(warnings))
        print()
    print(stdout)

    if modifiers.get("--full"):
        tickets, retval = utils.run(["crm_ticket", "-L"])
        if retval != 0:
            print("WARNING: Unable to get information about tickets")
            print()
        elif tickets:
            print("Tickets:")
            print("\n".join(indent(tickets.split("\n"))))

    if not (
        modifiers.is_specified("-f")
        or
        modifiers.is_specified("--corosync_conf")
    ):
        # do this only if in live environment
        if modifiers.get("--full"):
            print_pcsd_daemon_status(lib, modifiers)
            print()
        utils.serviceStatus("  ")

def status_stonith_check(modifiers):
    """
    Commandline options:
      * -f - CIB file, to get stonith devices and cluster property
        stonith-enabled from CIB, to determine whenever we are working with
        files or cluster
    """
    # pylint: disable=too-many-nested-blocks
    # We should read the default value from pacemaker. However that may slow
    # pcs down as we need to run 'pacemaker-schedulerd metadata' to get it.
    warnings = []
    stonith_enabled = True
    stonith_devices = []
    stonith_devices_id_action = []
    stonith_devices_id_method_cycle = []
    sbd_running = False

    cib = utils.get_cib_dom()
    for conf in cib.getElementsByTagName("configuration"):
        for crm_config in conf.getElementsByTagName("crm_config"):
            for nvpair in crm_config.getElementsByTagName("nvpair"):
                if (
                    nvpair.getAttribute("name") == "stonith-enabled"
                    and
                    is_false(nvpair.getAttribute("value"))
                ):
                    stonith_enabled = False
                    break
            if not stonith_enabled:
                break
        for resource_el in conf.getElementsByTagName("primitive"):
            if resource_el.getAttribute("class") == "stonith":
                stonith_devices.append(resource_el)
                for attribs in resource_el.getElementsByTagName(
                    "instance_attributes"
                ):
                    for nvpair in attribs.getElementsByTagName("nvpair"):
                        if (
                            nvpair.getAttribute("name") == "action"
                            and
                            nvpair.getAttribute("value")
                        ):
                            stonith_devices_id_action.append(
                                resource_el.getAttribute("id")
                            )
                        if (
                            nvpair.getAttribute("name") == "method"
                            and
                            nvpair.getAttribute("value") == "cycle"
                        ):
                            stonith_devices_id_method_cycle.append(
                                resource_el.getAttribute("id")
                            )

    if not modifiers.is_specified("-f"):
        # check if SBD daemon is running
        try:
            sbd_running = utils.is_service_running(
                utils.cmd_runner(),
                get_sbd_service_name()
            )
        except LibraryError:
            pass

    if stonith_enabled and not stonith_devices and not sbd_running:
        warnings.append(
            "No stonith devices and stonith-enabled is not false"
        )

    if stonith_devices_id_action:
        warnings.append(
            "Following stonith devices have the 'action' option set, "
            "it is recommended to set {0} instead: {1}".format(
                ", ".join(
                    ["'{0}'".format(x) for x in _STONITH_ACTION_REPLACED_BY]
                ),
                ", ".join(sorted(stonith_devices_id_action))
            )
        )
    if stonith_devices_id_method_cycle:
        warnings.append(
            "Following stonith devices have the 'method' option set "
            "to 'cycle' which is potentially dangerous, please consider using "
            "'onoff': {0}".format(
                ", ".join(sorted(stonith_devices_id_method_cycle))
            )
        )
    return warnings

# Parse crm_mon for status
def nodes_status(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file - for config subcommand and not for both or corosync
      * --corosync_conf - only for config subcommand

    NOTE: modifiers check is in subcommand
    """
    del lib
    if len(argv) == 1 and (argv[0] == "config"):
        modifiers.ensure_only_supported("-f", "--corosync_conf")
        if utils.hasCorosyncConf():
            corosync_nodes, report_list = get_existing_nodes_names(
                utils.get_corosync_conf_facade()
            )
            if report_list:
                process_library_reports(report_list)
        else:
            corosync_nodes = []
        try:
            pacemaker_nodes = sorted([
                node.attrs.name for node
                in ClusterState(utils.getClusterStateXml()).node_section.nodes
                if node.attrs.type != 'remote'
            ])
        except LibraryError as e:
            process_library_reports(e.args)
        print("Corosync Nodes:")
        if corosync_nodes:
            print(" " + " ".join(corosync_nodes))
        print("Pacemaker Nodes:")
        if pacemaker_nodes:
            print(" " + " ".join(pacemaker_nodes))

        return

    if len(argv) == 1 and (argv[0] == "corosync" or argv[0] == "both"):
        modifiers.ensure_only_supported()
        all_nodes, report_list = get_existing_nodes_names(
            utils.get_corosync_conf_facade()
        )
        if report_list:
            process_library_reports(report_list)
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

    modifiers.ensure_only_supported("-f")
    info_dom = utils.getClusterState()

    nodes = info_dom.getElementsByTagName("nodes")
    if nodes.length == 0:
        utils.err("No nodes section found")

    onlinenodes = []
    offlinenodes = []
    standbynodes = []
    standbynodes_with_resources = []
    maintenancenodes = []
    remote_onlinenodes = []
    remote_offlinenodes = []
    remote_standbynodes = []
    remote_standbynodes_with_resources = []
    remote_maintenancenodes = []
    for node in nodes[0].getElementsByTagName("node"):
        node_name = node.getAttribute("name")
        node_remote = node.getAttribute("type") == "remote"
        if node.getAttribute("online") == "true":
            if node.getAttribute("standby") == "true":
                is_running_resources = (
                    node.getAttribute("resources_running") != "0"
                )
                if node_remote:
                    if is_running_resources:
                        remote_standbynodes_with_resources.append(node_name)
                    else:
                        remote_standbynodes.append(node_name)
                else:
                    if is_running_resources:
                        standbynodes_with_resources.append(node_name)
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
    print(" ".join(
        [" Standby with resource(s) running:"] + standbynodes_with_resources
    ))
    print(" ".join([" Maintenance:"] + maintenancenodes))
    print(" ".join([" Offline:"] + offlinenodes))

    print("Pacemaker Remote Nodes:")
    print(" ".join([" Online:"] + remote_onlinenodes))
    print(" ".join([" Standby:"] + remote_standbynodes))
    print(" ".join(
        [" Standby with resource(s) running:"]
        +
        remote_standbynodes_with_resources
    ))
    print(" ".join([" Maintenance:"] + remote_maintenancenodes))
    print(" ".join([" Offline:"] + remote_offlinenodes))

def cluster_status(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --request-timeout - HTTP timeout for checking status of pcsd, no effect
        if -f is specified
    """
    modifiers.ensure_only_supported("-f", "--request-timeout")
    if argv:
        raise CmdLineInputError()
    (output, retval) = utils.run(["crm_mon", "-1", "-r"])

    if retval != 0:
        utils.err("cluster is not currently running on this node")

    first_empty_line = False
    print("Cluster Status:")
    for line in output.splitlines():
        if line == "":
            if first_empty_line:
                break
            first_empty_line = True
            continue
        print("", line)

    if not modifiers.is_specified("-f") and utils.hasCorosyncConf():
        print()
        print_pcsd_daemon_status(lib, modifiers)

def corosync_status(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    (output, retval) = utils.run(["corosync-quorumtool", "-l"])
    if retval != 0:
        utils.err("corosync not running")
    else:
        print(output.rstrip())

def xml_status(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    (output, retval) = utils.run(
        ["crm_mon", "-1", "-r", "-X"],
        ignore_stderr=True
    )

    if retval != 0:
        utils.err("running crm_mon, is pacemaker running?")
    print(output.rstrip())

def print_pcsd_daemon_status(lib, modifiers):
    """
    Commandline options:
      * --request-timeout - HTTP timeout for node authorization check or when
        not running under root to call local pcsd
    """
    print("PCSD Status:")
    if os.getuid() == 0:
        cluster_pcsd_status(
            lib, [], modifiers.get_subset("--request-timeout"), dont_exit=True
        )
    else:
        err_msgs, exitcode, std_out, dummy_std_err = utils.call_local_pcsd(
            ['status', 'pcsd']
        )
        if err_msgs:
            for msg in err_msgs:
                print(msg)
        if exitcode == 0:
            print(std_out)
        else:
            print("Unable to get PCSD status")

def check_nodes(node_list, prefix=""):
    """
    Print pcsd status on node_list, return if there is any pcsd not online

    Commandline options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    online_code = 0
    status_desc_map = {
        online_code: 'Online',
        3: 'Unable to authenticate'
    }
    status_list = []
    def report(node, returncode, output):
        del output
        print("{0}{1}: {2}".format(
            prefix,
            node,
            status_desc_map.get(returncode, 'Offline')
        ))
        status_list.append(returncode)

    utils.read_known_hosts_file() # cache known hosts
    utils.run_parallel(
        utils.create_task_list(report, utils.checkAuthorization, node_list)
    )

    return any([status != online_code for status in status_list])

# If no arguments get current cluster node status, otherwise get listed
# nodes status
def cluster_pcsd_status(lib, argv, modifiers, dont_exit=False):
    """
    Options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    del lib
    modifiers.ensure_only_supported("--request-timeout")
    bad_nodes = False
    if not argv:
        nodes, report_list = get_existing_nodes_names(
            utils.get_corosync_conf_facade()
        )
        if not nodes and not dont_exit:
            report_list.append(reports.corosync_config_no_nodes_defined())
        if report_list:
            process_library_reports(report_list)
        bad_nodes = check_nodes(nodes, "  ")
    else:
        bad_nodes = check_nodes(argv, "  ")
    if bad_nodes and not dont_exit:
        sys.exit(2)
