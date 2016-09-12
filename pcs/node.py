from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import json

from pcs import (
    usage,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import prepare_options
from pcs.lib.errors import LibraryError
import pcs.lib.pacemaker as lib_pacemaker
from pcs.lib.pacemaker_values import get_valid_timeout_seconds


def node_cmd(argv):
    if len(argv) == 0:
        usage.node()
        sys.exit(1)

    sub_cmd = argv.pop(0)
    if sub_cmd == "help":
        usage.node(argv)
    elif sub_cmd == "maintenance":
        node_maintenance(argv)
    elif sub_cmd == "unmaintenance":
        node_maintenance(argv, False)
    elif sub_cmd == "standby":
        node_standby(argv)
    elif sub_cmd == "unstandby":
        node_standby(argv, False)
    elif sub_cmd == "attribute":
        if "--name" in utils.pcs_options and len(argv) > 1:
            usage.node("attribute")
            sys.exit(1)
        filter_attr=utils.pcs_options.get("--name", None)
        if len(argv) == 0:
            attribute_show_cmd(filter_attr=filter_attr)
        elif len(argv) == 1:
            attribute_show_cmd(argv.pop(0), filter_attr=filter_attr)
        else:
            attribute_set_cmd(argv.pop(0), argv)
    elif sub_cmd == "utilization":
        if "--name" in utils.pcs_options and len(argv) > 1:
            usage.node("utilization")
            sys.exit(1)
        filter_name=utils.pcs_options.get("--name", None)
        if len(argv) == 0:
            print_node_utilization(filter_name=filter_name)
        elif len(argv) == 1:
            print_node_utilization(argv.pop(0), filter_name=filter_name)
        else:
            try:
                set_node_utilization(argv.pop(0), argv)
            except CmdLineInputError as e:
                utils.exit_on_cmdline_input_errror(e, "node", "utilization")
    # pcs-to-pcsd use only
    elif sub_cmd == "pacemaker-status":
        node_pacemaker_status()
    else:
        usage.node()
        sys.exit(1)


def node_maintenance(argv, on=True):
    action = ["-v", "on"] if on else ["-D"]

    cluster_nodes = utils.getNodesFromPacemaker()
    nodes = []
    failed_count = 0
    if "--all" in utils.pcs_options:
        nodes = cluster_nodes
    elif argv:
        for node in argv:
            if node not in cluster_nodes:
                utils.err(
                    "Node '{0}' does not appear to exist in "
                    "configuration".format(node),
                    False
                )
                failed_count += 1
            else:
                nodes.append(node)
    else:
        nodes.append("")

    if failed_count > 0:
        sys.exit(1)

    for node in nodes:
        node_attr = ["-N", node] if node else []
        output, retval = utils.run(
            ["crm_attribute", "-t", "nodes", "-n", "maintenance"] + action +
            node_attr
        )
        if retval != 0:
            node_name = ("node '{0}'".format(node)) if argv else "current node"
            failed_count += 1
            if on:
                utils.err(
                    "Unable to put {0} to maintenance mode: {1}".format(
                        node_name, output
                    ),
                    False
                )
            else:
                utils.err(
                    "Unable to remove {0} from maintenance mode: {1}".format(
                        node_name, output
                    ),
                    False
                )
    if failed_count > 0:
        sys.exit(1)

def node_standby(argv, standby=True):
    if (len(argv) > 1) or (len(argv) > 0 and "--all" in utils.pcs_options):
        usage.node(["standby" if standby else "unstandby"])
        sys.exit(1)

    all_nodes = "--all" in utils.pcs_options
    node_list = [argv[0]] if argv else []
    wait = False
    timeout = None
    if "--wait" in utils.pcs_options:
        wait = True
        timeout = utils.pcs_options["--wait"]

    try:
        if wait:
            lib_pacemaker.ensure_resource_wait_support(utils.cmd_runner())
            valid_timeout = get_valid_timeout_seconds(timeout)
        if standby:
            lib_pacemaker.nodes_standby(
                utils.cmd_runner(), node_list, all_nodes
            )
        else:
            lib_pacemaker.nodes_unstandby(
                utils.cmd_runner(), node_list, all_nodes
            )
        if wait:
            lib_pacemaker.wait_for_resources(utils.cmd_runner(), valid_timeout)
    except LibraryError as e:
        utils.process_library_reports(e.args)

def set_node_utilization(node, argv):
    cib = utils.get_cib_dom()
    node_el = utils.dom_get_node(cib, node)
    if node_el is None:
        if utils.usefile:
            utils.err("Unable to find a node: {0}".format(node))

        for attrs in utils.getNodeAttributesFromPacemaker():
            if attrs.name == node and attrs.type == "remote":
                node_attrs = attrs
                break
        else:
            utils.err("Unable to find a node: {0}".format(node))

        nodes_section_list = cib.getElementsByTagName("nodes")
        if len(nodes_section_list) == 0:
            utils.err("Unable to get nodes section of cib")

        dom = nodes_section_list[0].ownerDocument
        node_el = dom.createElement("node")
        node_el.setAttribute("id", node_attrs.id)
        node_el.setAttribute("type", node_attrs.type)
        node_el.setAttribute("uname", node_attrs.name)
        nodes_section_list[0].appendChild(node_el)

    utils.dom_update_utilization(node_el, prepare_options(argv), "nodes-")
    utils.replace_cib_configuration(cib)

def print_node_utilization(filter_node=None, filter_name=None):
    cib = utils.get_cib_dom()

    node_element_list = cib.getElementsByTagName("node")


    if(
        filter_node
        and
        filter_node not in [
            node_element.getAttribute("uname")
            for node_element in node_element_list
        ]
        and (
            utils.usefile
            or
            filter_node not in [
                node_attrs.name for node_attrs
                in utils.getNodeAttributesFromPacemaker()
            ]
        )
    ):
        utils.err("Unable to find a node: {0}".format(filter_node))

    utilization = {}
    for node_el in node_element_list:
        node = node_el.getAttribute("uname")
        if filter_node is not None and node != filter_node:
            continue
        u = utils.get_utilization_str(node_el, filter_name)
        if u:
            utilization[node] = u
    print("Node Utilization:")
    for node in sorted(utilization):
        print(" {0}: {1}".format(node, utilization[node]))

def node_pacemaker_status():
    try:
        print(json.dumps(
            lib_pacemaker.get_local_node_status(utils.cmd_runner())
        ))
    except LibraryError as e:
        utils.process_library_reports(e.args)

def attribute_show_cmd(filter_node=None, filter_attr=None):
    node_attributes = utils.get_node_attributes(
        filter_node=filter_node,
        filter_attr=filter_attr
    )
    print("Node Attributes:")
    attribute_print(node_attributes)

def attribute_set_cmd(node, argv):
    try:
        attrs = prepare_options(argv)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "node", "attribute")
    for name, value in attrs.items():
        utils.set_node_attribute(name, value, node)

def attribute_print(node_attributes):
    for node in sorted(node_attributes.keys()):
        line_parts = [" " + node + ":"]
        for name, value in sorted(node_attributes[node].items()):
            line_parts.append("{0}={1}".format(name, value))
        print(" ".join(line_parts))

