from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import re
import json

from pcs import (
    resource,
    usage,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.reports import build_report_message
from pcs.lib.errors import LibraryError, ReportItemSeverity
import pcs.lib.resource_agent as lib_ra

def stonith_cmd(argv):
    if len(argv) < 1:
        sub_cmd, argv_next = "show", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    lib = utils.get_library_wrapper()
    modifiers = utils.get_modificators()

    try:
        if sub_cmd == "help":
            usage.stonith(argv)
        elif sub_cmd == "list":
            stonith_list_available(lib, argv_next, modifiers)
        elif sub_cmd == "describe":
            stonith_list_options(lib, argv_next, modifiers)
        elif sub_cmd == "create":
            stonith_create(argv_next)
        elif sub_cmd == "update":
            if len(argv_next) > 1:
                stn_id = argv_next.pop(0)
                resource.resource_update(stn_id, argv_next)
            else:
                raise CmdLineInputError()
        elif sub_cmd == "delete":
            if len(argv_next) == 1:
                stn_id = argv_next.pop(0)
                resource.resource_remove(stn_id)
            else:
                raise CmdLineInputError()
        elif sub_cmd == "show":
            resource.resource_show(argv_next, True)
            stonith_level([])
        elif sub_cmd == "level":
            stonith_level(argv_next)
        elif sub_cmd == "fence":
            stonith_fence(argv_next)
        elif sub_cmd == "cleanup":
            resource.resource_cleanup(argv_next)
        elif sub_cmd == "confirm":
            stonith_confirm(argv_next)
        elif sub_cmd == "get_fence_agent_info":
            get_fence_agent_info(argv_next)
        elif sub_cmd == "sbd":
            sbd_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "stonith", sub_cmd)


def stonith_list_available(lib, argv, modifiers):
    if len(argv) > 1:
        raise CmdLineInputError()

    search = argv[0] if argv else None
    agent_list = lib.stonith_agent.list_agents(modifiers["describe"], search)

    if not agent_list:
        if search:
            utils.err("No stonith agents matching the filter.")
        utils.err(
            "No stonith agents available. "
            "Do you have fence agents installed?"
        )

    for agent_info in agent_list:
        name = agent_info["name"]
        shortdesc = agent_info["shortdesc"]
        if shortdesc:
            print("{0} - {1}".format(
                name,
                resource._format_desc(
                    len(name + " - "), shortdesc.replace("\n", " ")
                )
            ))
        else:
            print(name)


def stonith_list_options(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = argv[0]

    print(resource._format_agent_description(
        lib.stonith_agent.describe_agent(agent_name),
        True
    ))


def stonith_create(argv):
    if len(argv) < 2:
        usage.stonith(["create"])
        sys.exit(1)

    stonith_id = argv.pop(0)
    stonith_type = argv.pop(0)
    st_values, op_values, meta_values = resource.parse_resource_options(
        argv, with_clone=False
    )

    try:
        metadata = lib_ra.StonithAgent(
            utils.cmd_runner(),
            stonith_type
        )
        if metadata.get_provides_unfencing():
            meta_values = [
                meta for meta in meta_values if not meta.startswith("provides=")
            ]
            meta_values.append("provides=unfencing")
    except lib_ra.ResourceAgentError as e:
        forced = utils.get_modificators().get("force", False)
        if forced:
            severity = ReportItemSeverity.WARNING
        else:
            severity = ReportItemSeverity.ERROR
        utils.process_library_reports([
            lib_ra.resource_agent_error_to_report_item(
                e, severity, not forced
            )
        ])
    except LibraryError as e:
        utils.process_library_reports(e.args)

    resource.resource_create(
        stonith_id, "stonith:" + stonith_type, st_values, op_values, meta_values,
        group=utils.pcs_options.get("--group", None)
    )

def stonith_level(argv):
    if len(argv) == 0:
        stonith_level_show()
        return

    subcmd = argv.pop(0)

    if subcmd == "add":
        if len(argv) < 3:
            usage.stonith(["level add"])
            sys.exit(1)
        stonith_level_add(argv[0], argv[1], ",".join(argv[2:]))
    elif subcmd in ["remove","delete"]:
        if len(argv) < 1:
            usage.stonith(["level remove"])
            sys.exit(1)

        node = ""
        devices = ""
        if len(argv) == 2:
            node = argv[1]
        elif len(argv) > 2:
            node = argv[1]
            devices = ",".join(argv[2:])

        stonith_level_rm(argv[0], node, devices)
    elif subcmd == "clear":
        if len(argv) == 0:
            stonith_level_clear()
        else:
            stonith_level_clear(argv[0])
    elif subcmd == "verify":
        stonith_level_verify()
    else:
        print("pcs stonith level: invalid option -- '%s'" % subcmd)
        usage.stonith(["level"])
        sys.exit(1)

def stonith_level_add(level, node, devices):
    dom = utils.get_cib_dom()

    if not re.search(r'^\d+$', level) or re.search(r'^0+$', level):
        utils.err("invalid level '{0}', use a positive integer".format(level))
    level = level.lstrip('0')
    if "--force" not in utils.pcs_options:
        for dev in devices.split(","):
            if not utils.is_stonith_resource(dev):
                utils.err("%s is not a stonith id (use --force to override)" % dev)
        corosync_nodes = []
        if utils.hasCorosyncConf():
            corosync_nodes = utils.getNodesFromCorosyncConf()
        pacemaker_nodes = utils.getNodesFromPacemaker()
        if node not in corosync_nodes and node not in pacemaker_nodes:
            utils.err("%s is not currently a node (use --force to override)" % node)

    ft = dom.getElementsByTagName("fencing-topology")
    if len(ft) == 0:
        conf = dom.getElementsByTagName("configuration")[0]
        ft = dom.createElement("fencing-topology")
        conf.appendChild(ft)
    else:
        ft = ft[0]

    fls = ft.getElementsByTagName("fencing-level")
    for fl in fls:
        if fl.getAttribute("target") == node and fl.getAttribute("index") == level and fl.getAttribute("devices") == devices:
            utils.err("unable to add fencing level, fencing level for node: %s, at level: %s, with device: %s already exists" % (node,level,devices))

    new_fl = dom.createElement("fencing-level")
    ft.appendChild(new_fl)
    new_fl.setAttribute("target", node)
    new_fl.setAttribute("index", level)
    new_fl.setAttribute("devices", devices)
    new_fl.setAttribute("id", utils.find_unique_id(dom, "fl-" + node +"-" + level))

    utils.replace_cib_configuration(dom)

def stonith_level_rm(level, node, devices):
    dom = utils.get_cib_dom()

    if devices != "":
        node_devices_combo  = node + "," + devices
    else:
        node_devices_combo = node

    ft = dom.getElementsByTagName("fencing-topology")
    if len(ft) == 0:
        utils.err("unable to remove fencing level, fencing level for node: %s, at level: %s, with device: %s doesn't exist" % (node,level,devices))
    else:
        ft = ft[0]

    fls = ft.getElementsByTagName("fencing-level")

    if node != "":
        if devices != "":
            found = False
            for fl in fls:
                if fl.getAttribute("target") == node and fl.getAttribute("index") == level and fl.getAttribute("devices") == devices:
                    found = True
                    break

                if fl.getAttribute("index") == level and fl.getAttribute("devices") == node_devices_combo:
                    found = True
                    break

            if found == False:
                utils.err("unable to remove fencing level, fencing level for node: %s, at level: %s, with device: %s doesn't exist" % (node,level,devices))

            fl.parentNode.removeChild(fl)
        else:
            for fl in fls:
                if fl.getAttribute("index") == level and (fl.getAttribute("target") == node or fl.getAttribute("devices") == node):
                    fl.parentNode.removeChild(fl)
    else:
        for fl in fls:
            if fl.getAttribute("index") == level:
                parent = fl.parentNode
                parent.removeChild(fl)
                if len(parent.getElementsByTagName("fencing-level")) == 0:
                    parent.parentNode.removeChild(parent)
                    break

    utils.replace_cib_configuration(dom)

def stonith_level_clear(node = None):
    dom = utils.get_cib_dom()
    ft = dom.getElementsByTagName("fencing-topology")

    if len(ft) == 0:
        return

    if node == None:
        ft = ft[0]
        childNodes = ft.childNodes[:]
        for node in childNodes:
            node.parentNode.removeChild(node)
    else:
        fls = dom.getElementsByTagName("fencing-level")
        if len(fls) == 0:
            return
        for fl in fls:
            if fl.getAttribute("target") == node or fl.getAttribute("devices") == node:
                fl.parentNode.removeChild(fl)

    utils.replace_cib_configuration(dom)

def stonith_level_verify():
    dom = utils.get_cib_dom()
    corosync_nodes = []
    if utils.hasCorosyncConf():
        corosync_nodes = utils.getNodesFromCorosyncConf()
    pacemaker_nodes = utils.getNodesFromPacemaker()

    fls = dom.getElementsByTagName("fencing-level")
    for fl in fls:
        node = fl.getAttribute("target")
        devices = fl.getAttribute("devices")
        for dev in devices.split(","):
            if not utils.is_stonith_resource(dev):
                utils.err("%s is not a stonith id" % dev)
        if node not in corosync_nodes and node not in pacemaker_nodes:
            utils.err("%s is not currently a node" % node)

def stonith_level_show():
    dom = utils.get_cib_dom()

    node_levels = {}
    fls = dom.getElementsByTagName("fencing-level")
    for fl in fls:
        node = fl.getAttribute("target")
        level = fl.getAttribute("index")
        devices = fl.getAttribute("devices")

        if node in node_levels:
            node_levels[node].append((level,devices))
        else:
            node_levels[node] = [(level,devices)]

    if len(node_levels.keys()) == 0:
        return

    nodes = sorted(node_levels.keys())

    for node in nodes:
        print(" Node: " + node)
        for level in sorted(node_levels[node], key=lambda x: int(x[0])):
            print("  Level " + level[0] + " - " + level[1])


def stonith_fence(argv):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to fence")

    node = argv.pop(0)
    if "--off" in utils.pcs_options:
        args = ["stonith_admin", "-F", node]
    else:
        args = ["stonith_admin", "-B", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to fence '%s'\n" % node + output)
    else:
        print("Node: %s fenced" % node)

def stonith_confirm(argv, skip_question=False):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to confirm fenced")

    node = argv.pop(0)
    if not skip_question and "--force" not in utils.pcs_options:
        answer = utils.get_terminal_input(
            (
                "WARNING: If node {node} is not powered off or it does"
                + " have access to shared resources, data corruption and/or"
                + " cluster failure may occur. Are you sure you want to"
                + " continue? [y/N] "
            ).format(node=node)
        )
        if answer.lower() not in ["y", "yes"]:
            print("Canceled")
            return
    args = ["stonith_admin", "-C", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to confirm fencing of node '%s'\n" % node + output)
    else:
        print("Node: %s confirmed fenced" % node)


def get_fence_agent_info(argv):
# This is used only by pcsd, will be removed in new architecture
    if len(argv) != 1:
        utils.err("One parameter expected")

    agent = argv[0]
    if not agent.startswith("stonith:"):
        utils.err("Invalid fence agent name")

    runner = utils.cmd_runner()

    try:
        metadata = lib_ra.StonithAgent(runner, agent[len("stonith:"):])
        info = metadata.get_full_info()
        info["name"] = "stonith:{0}".format(info["name"])
        print(json.dumps(info))
    except lib_ra.ResourceAgentError as e:
        utils.process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e)]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)


def sbd_cmd(lib, argv, modifiers):
    if len(argv) == 0:
        raise CmdLineInputError()
    cmd = argv.pop(0)
    try:
        if cmd == "enable":
            sbd_enable(lib, argv, modifiers)
        elif cmd == "disable":
            sbd_disable(lib, argv, modifiers)
        elif cmd == "status":
            sbd_status(lib, argv, modifiers)
        elif cmd == "config":
            sbd_config(lib, argv, modifiers)
        elif cmd == "local_config_in_json":
            local_sbd_config(lib, argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "stonith", "sbd {0}".format(cmd)
        )


def sbd_enable(lib, argv, modifiers):
    sbd_cfg = parse_args.prepare_options(argv)
    default_watchdog, watchdog_dict = _sbd_parse_watchdogs(
        modifiers["watchdog"]
    )
    lib.sbd.enable_sbd(
        default_watchdog,
        watchdog_dict,
        sbd_cfg,
        allow_unknown_opts=modifiers["force"],
        ignore_offline_nodes=modifiers["skip_offline_nodes"]
    )


def _sbd_parse_watchdogs(watchdog_list):
    default_watchdog = None
    watchdog_dict = {}

    for watchdog_node in watchdog_list:
        if "@" not in watchdog_node:
            if default_watchdog:
                raise CmdLineInputError("Multiple watchdog definitions.")
            default_watchdog = watchdog_node
        else:
            watchdog, node_name = watchdog_node.rsplit("@", 1)
            if node_name in watchdog_dict:
                raise CmdLineInputError(
                    "Multiple watchdog definitions for node '{node}'".format(
                        node=node_name
                    )
                )
            watchdog_dict[node_name] = watchdog

    return default_watchdog, watchdog_dict


def sbd_disable(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    lib.sbd.disable_sbd(modifiers["skip_offline_nodes"])


def sbd_status(lib, argv, modifiers):
    def _bool_to_str(val):
        if val is None:
            return "N/A"
        return "YES" if val else " NO"

    if argv:
        raise CmdLineInputError()

    status_list = lib.sbd.get_cluster_sbd_status()
    if not len(status_list):
        utils.err("Unable to get SBD status from any node.")

    print("SBD STATUS")
    print("<node name>: <installed> | <enabled> | <running>")
    for node_status in status_list:
        status = node_status["status"]
        print("{node}: {installed} | {enabled} | {running}".format(
            node=node_status["node"].label,
            installed=_bool_to_str(status.get("installed")),
            enabled=_bool_to_str(status.get("enabled")),
            running=_bool_to_str(status.get("running"))
        ))


def sbd_config(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    config_list = lib.sbd.get_cluster_sbd_config()

    if not config_list:
        utils.err("No config obtained.")

    config = config_list[0]["config"]

    filtered_options = ["SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER"]
    for key, val in config.items():
        if key in filtered_options:
            continue
        print("{key}={val}".format(key=key, val=val))

    print()
    print("Watchdogs:")
    for config in config_list:
        watchdog = "<unknown>"
        if config["config"] is not None:
            watchdog = config["config"].get("SBD_WATCHDOG_DEV", "<unknown>")
        print("  {node}: {watchdog}".format(
            node=config["node"].label,
            watchdog=watchdog
        ))


def local_sbd_config(lib, argv, modifiers):
    print(json.dumps(lib.sbd.get_local_sbd_config()))
