from __future__ import (
    absolute_import,
    division,
    print_function,
)

import sys
import json

from pcs import (
    usage,
    utils,
)
from pcs.cli.common.errors import (
    CmdLineInputError,
    ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE,
)
from pcs.cli.common.parse_args import prepare_options
from pcs.lib.errors import LibraryError
import pcs.lib.pacemaker.live as lib_pacemaker


def node_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        usage.node()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.node([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "maintenance":
            node_maintenance_cmd(lib, argv_next, modifiers, True)
        elif sub_cmd == "unmaintenance":
            node_maintenance_cmd(lib, argv_next, modifiers, False)
        elif sub_cmd == "standby":
            node_standby_cmd(lib, argv_next, modifiers, True)
        elif sub_cmd == "unstandby":
            node_standby_cmd(lib, argv_next, modifiers, False)
        elif sub_cmd == "attribute":
            node_attribute_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "utilization":
            node_utilization_cmd(lib, argv_next, modifiers)
        # pcs-to-pcsd use only
        elif sub_cmd == "pacemaker-status":
            node_pacemaker_status(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "node", sub_cmd)

def node_attribute_cmd(lib, argv, modifiers):
    if modifiers["name"] and len(argv) > 1:
        raise CmdLineInputError()
    if len(argv) == 0:
        attribute_show_cmd(filter_attr=modifiers["name"])
    elif len(argv) == 1:
        attribute_show_cmd(argv.pop(0), filter_attr=modifiers["name"])
    else:
        attribute_set_cmd(argv.pop(0), argv)

def node_utilization_cmd(lib, argv, modifiers):
    if modifiers["name"] and len(argv) > 1:
        raise CmdLineInputError()
    if len(argv) == 0:
        print_node_utilization(filter_name=modifiers["name"])
    elif len(argv) == 1:
        print_node_utilization(argv.pop(0), filter_name=modifiers["name"])
    else:
        set_node_utilization(argv.pop(0), argv)

def node_maintenance_cmd(lib, argv, modifiers, enable):
    if len(argv) > 0 and modifiers["all"]:
        raise CmdLineInputError(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
    if modifiers["all"]:
        lib.node.maintenance_unmaintenance_all(enable, modifiers["wait"])
    elif argv:
        lib.node.maintenance_unmaintenance_list(enable, argv, modifiers["wait"])
    else:
        lib.node.maintenance_unmaintenance_local(enable, modifiers["wait"])

def node_standby_cmd(lib, argv, modifiers, enable):
    if len(argv) > 0 and modifiers["all"]:
        raise CmdLineInputError(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
    if modifiers["all"]:
        lib.node.standby_unstandby_all(enable, modifiers["wait"])
    elif argv:
        lib.node.standby_unstandby_list(enable, argv, modifiers["wait"])
    else:
        lib.node.standby_unstandby_local(enable, modifiers["wait"])

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

def node_pacemaker_status(lib, argv, modifiers):
    print(json.dumps(
        lib_pacemaker.get_local_node_status(utils.cmd_runner())
    ))

def attribute_show_cmd(filter_node=None, filter_attr=None):
    node_attributes = utils.get_node_attributes(
        filter_node=filter_node,
        filter_attr=filter_attr
    )
    print("Node Attributes:")
    attribute_print(node_attributes)

def attribute_set_cmd(node, argv):
    for name, value in prepare_options(argv).items():
        utils.set_node_attribute(name, value, node)

def attribute_print(node_attributes):
    for node in sorted(node_attributes.keys()):
        line_parts = [" " + node + ":"]
        for name, value in sorted(node_attributes[node].items()):
            line_parts.append("{0}={1}".format(name, value))
        print(" ".join(line_parts))

