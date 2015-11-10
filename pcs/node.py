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
