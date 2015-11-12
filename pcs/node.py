from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

import usage
import utils


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
    elif sub_cmd == "utilization":
        if len(argv) == 0:
            print_nodes_utilization()
        elif len(argv) == 1:
            print_node_utilization(argv.pop(0))
        else:
            set_node_utilization(argv.pop(0), argv)
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
                    "Node '%s' does not appear to exist in configuration" %
                    argv[0],
                    False
                )
                failed_count += 1
            else:
                nodes.append(node)
    else:
        nodes.append("")

    for node in nodes:
        node = ["-N", node] if node else []
        output, retval = utils.run(
            ["crm_attribute", "-t", "nodes", "-n", "maintenance"] + action +
            node
        )
        if retval != 0:
            node_name = ("node '%s'" % node) if argv else "current node"
            failed_count += 1
            if on:
                utils.err(
                    "Unable to put %s to maintenance mode.\n%s" %
                    (node_name, output),
                    False
                )
            else:
                utils.err(
                    "Unable to remove %s from maintenance mode.\n%s" %
                    (node_name, output),
                    False
                )
    if failed_count > 0:
        sys.exit(1)

def set_node_utilization(node, argv):
    cib = utils.get_cib_dom()
    node_el = utils.dom_get_node(cib, node)
    if node_el is None:
        utils.err("Unable to find a node: {0}".format(node))

    utils.dom_update_utilization(
        node_el, utils.convert_args_to_tuples(argv), "nodes-"
    )
    utils.replace_cib_configuration(cib)

def print_node_utilization(node):
    cib = utils.get_cib_dom()
    node_el = utils.dom_get_node(cib, node)
    if node_el is None:
        utils.err("Unable to find a node: {0}".format(node))
    utilization = utils.get_utilization_str(node_el)

    print("Node Utilization:")
    print(" {0}: {1}".format(node, utilization))

def print_nodes_utilization():
    cib = utils.get_cib_dom()
    utilization = {}
    for node_el in cib.getElementsByTagName("node"):
        u = utils.get_utilization_str(node_el)
        if u:
           utilization[node_el.getAttribute("uname")] = u
    print("Node Utilization:")
    for node in sorted(utilization):
        print(" {0}: {1}".format(node, utilization[node]))
