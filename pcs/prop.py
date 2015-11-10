from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
from xml.dom.minidom import parseString
import xml.etree.ElementTree as ET

import usage
import utils
import settings

def property_cmd(argv):
    if len(argv) == 0:
        argv = ["list"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.property(argv)
    elif (sub_cmd == "set"):
        set_property(argv)
    elif (sub_cmd == "unset"):
        unset_property(argv)
    elif (sub_cmd == "list" or sub_cmd == "show"):
        list_property(argv)
    else:
        usage.property()
        sys.exit(1)

def set_property(argv):
    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            print("Invalid Property: " + arg)
            continue
        if "--node" in utils.pcs_options:
            utils.set_node_attribute(args[0], args[1], utils.pcs_options["--node"])
        elif ("--force" in utils.pcs_options) or utils.is_valid_property(args[0]):
            if not args[0]:
                utils.err("property name cannot be empty")
            utils.set_cib_property(args[0],args[1])
        else:
            utils.err("unknown cluster property: '%s', (use --force to override)" % args[0])

def unset_property(argv):
    if len(argv) < 1:
        usage.property()
        sys.exit(1)

    if "--node" in utils.pcs_options:
        for arg in argv:
            utils.set_node_attribute(arg, "",utils.pcs_options["--node"])
    else:
        for arg in argv:
            utils.set_cib_property(arg, "")

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
    (output, retVal) = utils.run([settings.pengine_binary, "metadata"])
    if retVal != 0:
        utils.err("unable to get pengine metadata\n"+output)
    pe_root = ET.fromstring(output)

    (output, retVal) = utils.run([settings.crmd_binary, "metadata"])
    if retVal != 0:
        utils.err("unable to get crmd metadata\n"+output)
    crmd_root = ET.fromstring(output)
    
    (output, retVal) = utils.run([settings.cib_binary, "metadata"])
    if retVal != 0:
        utils.err("unable to get cib metadata\n"+output)
    cib_root = ET.fromstring(output)

    parameters = {}
    for root in [pe_root, crmd_root, cib_root]:
        for param in root.getiterator('parameter'):
            name = param.attrib["name"]
            content = param.find("content")
            if content is not None:
                default = content.attrib["default"]
            else:
                default = ""

            parameters[name] =  default
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

