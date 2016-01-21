from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import json
from xml.dom.minidom import parseString

import usage
import utils

def property_cmd(argv):
    if len(argv) == 0:
        argv = ["list"]

    sub_cmd = argv.pop(0)
    if sub_cmd == "help":
        usage.property(argv)
    elif sub_cmd == "set":
        set_property(argv)
    elif sub_cmd == "unset":
        unset_property(argv)
    elif sub_cmd == "list" or sub_cmd == "show":
        list_property(argv)
    elif sub_cmd == "get_cluster_properties_definition":
        print(json.dumps(utils.get_cluster_properties_definition()))
    else:
        usage.property()
        sys.exit(1)


def set_property(argv):
    if not argv:
        usage.property(['set'])
        sys.exit(1)

    prop_def_dict = utils.get_cluster_properties_definition()
    nodes_attr = "--node" in utils.pcs_options
    failed = False
    forced = "--force" in utils.pcs_options
    properties = {}
    for arg in argv:
        args = arg.split('=')
        if len(args) != 2:
            utils.err("invalid property format: '{0}'".format(arg), False)
            failed = True
        elif not args[0]:
            utils.err("empty property name: '{0}'".format(arg), False)
            failed = True
        elif nodes_attr or forced or args[1].strip() == "":
            properties[args[0]] = args[1]
        else:
            try:
                if utils.is_valid_cluster_property(
                    prop_def_dict, args[0], args[1]
                ):
                    properties[args[0]] = args[1]
                else:
                    utils.err(
                        "invalid value of property: '{0}', (use --force to "
                        "override)".format(arg),
                        False
                    )
                    failed = True
            except utils.UnknownPropertyException:
                utils.err(
                    "unknown cluster property: '{0}', (use --force to "
                    "override)".format(args[0]),
                    False
                )
                failed = True

    if failed:
        sys.exit(1)

    if nodes_attr:
        for prop, value in properties.items():
            utils.set_node_attribute(prop, value, utils.pcs_options["--node"])
    else:
        cib_dom = utils.get_cib_dom()
        for prop, value in properties.items():
            utils.set_cib_property(prop, value, cib_dom)
        utils.replace_cib_configuration(cib_dom)


def unset_property(argv):
    if len(argv) < 1:
        usage.property()
        sys.exit(1)

    if "--node" in utils.pcs_options:
        for arg in argv:
            utils.set_node_attribute(arg, "",utils.pcs_options["--node"])
    else:
        cib_dom = utils.get_cib_dom()
        for arg in argv:
            utils.set_cib_property(arg, "", cib_dom)
        utils.replace_cib_configuration(cib_dom)

def list_property(argv):
    print_all = False
    if len(argv) == 0:
        print_all = True

    if "--all" in utils.pcs_options or "--defaults" in utils.pcs_options:
        if len(argv) != 0:
            utils.err("you cannot specify a property when using --all or --defaults")
        properties = get_default_properties()
    else:
        properties = {}

    if "--defaults" not in utils.pcs_options:
        properties = get_set_properties(
            None if print_all else argv[0],
            properties
        )

    print("Cluster Properties:")
    for prop,val in sorted(properties.items()):
        print(" " + prop + ": " + val)

    node_attributes = utils.get_node_attributes()
    if node_attributes:
        print("Node Attributes:")
        for node in sorted(node_attributes):
            line_parts = [" " + node + ":"]
            for attr in node_attributes[node]:
                line_parts.append(attr)
            print(" ".join(line_parts))

def get_default_properties():
    parameters = {}
    prop_def_dict = utils.get_cluster_properties_definition()
    for name, prop in prop_def_dict.items():
        parameters[name] = prop["default"]
    return parameters

def get_set_properties(prop_name=None, defaults=None):
    properties = {} if defaults is None else dict(defaults)
    (output, retVal) = utils.run(["cibadmin","-Q","--scope", "crm_config"])
    if retVal != 0:
        utils.err("unable to get crm_config\n"+output)
    dom = parseString(output)
    de = dom.documentElement
    crm_config_properties = de.getElementsByTagName("nvpair")
    for prop in crm_config_properties:
        if prop_name is None or (prop_name == prop.getAttribute("name")):
            properties[prop.getAttribute("name")] = prop.getAttribute("value")
    return properties

