#!/usr/bin/python

import sys, getopt, os
import subprocess
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
import usage
import corosync
import utils

usefile = False
filename = ""
def main(argv):
    global filename, usefile
    try:
        opts, argv = getopt.getopt(argv, "hf:")
    except getopt.GetoptError, err:
        usage.main()
        sys.exit(1)

    for o, a in opts:
        if o == "-h":
            usage.main()
            sys.exit()
        elif o == "-f":
            usefile = True
            filename = a

    if len(argv) == 0:
        usage.main()
        exit(1)

    command = argv.pop(0)
    if (command == "-h"):
        usage.main()
    if (command == "resource"):
        resource_cmd(argv)
    if (command == "corosync"):
        corosync.corosync_cmd(argv)

def resource_cmd(argv):
    if len(argv) == 0:
        usage.resource()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.resource()
    elif (sub_cmd == "create"):
        res_id = argv.pop(0)
        res_type = argv.pop(0)
        ra_values = []
        op_values = []
        op_args = False
        for arg in argv:
            if op_args:
                op_values.append(arg)
            else:
                if arg == "op":
                    op_args = True
                else:
                    ra_values.append(arg)
        
        resource_create(res_id, res_type, ra_values, op_values)
    elif (sub_cmd == "delete"):
        res_id = argv.pop(0)
        args = ["crm_resource","--resource", res_id, "-t","primitive","-D"]
        output = utils.run(args, usefile, filename)
        print output,
    elif (sub_cmd == "list"):
        args = ["crm_resource","-L"]
        output = utils.run(args, usefile, filename)
        print output,


# Create a resource using crm_resource
# ra_class, ra_type & ra_provider must all contain valid info
def resource_create(ra_id, ra_type, ra_values, op_values):
    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = get_full_ra_type(ra_type)
    primitive_values.insert(0,("id",ra_id))
    op_attributes = convert_args_to_operations(op_values, ra_id)
    xml_resource_string = create_xml_string("primitive", primitive_values, instance_attributes + op_attributes)
    args = ["cibadmin"]
    args = args  + ["-o", "resources", "-C", "-X", xml_resource_string]
    output = subprocess.call(args)

def convert_args_to_operations(op_values, ra_id):
    op_name = op_values.pop(0)
    tuples = convert_args_to_tuples(op_values)
    op_attrs = []
    for (a,b) in tuples:
        op_attrs.append((a,b))

    op_attrs.append(("id",ra_id+"-"+a+"-"+b))
    op_attrs.append((a,b))
    op_attrs.append(("name",op_name))
    ops = [(("op",op_attrs,[]))]
    ret = ("operations", [], ops)
    return [ret]
        
def convert_args_to_instance_variables(ra_values, ra_id):
    tuples = convert_args_to_tuples(ra_values)
    ivs = []
    attribute_id = ra_id + "-instance_attributes"
    for (a,b) in tuples:
        ivs.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("instance_attributes", [[("id"),(attribute_id)]], ivs)
    return [ret]

def convert_args_to_tuples(ra_values):
    ret = []
    for ra_val in ra_values:
        if ra_val.count("=") == 1:
            split_val = ra_val.split("=")
            ret.append((split_val[0],split_val[1]))
    return ret

# Passed a resource type (ex. ocf:heartbeat:IPaddr2 or IPaddr2) and returns
# a list of tuples mapping the types to xml attributes
def get_full_ra_type(ra_type):
    if (ra_type.count(":") == 0):
        return ([("class","ocf"),("type",ra_type),("provider","heartbeat")])
    
    ra_def = ra_type.split(":")
    return([("class",ra_def[0]),("type",ra_def[2]),("provider",ra_def[1])])


def create_xml_string(tag, options, children = []):
    element = create_xml_element(tag,options, children).toxml()
    return element

def create_xml_element(tag, options, children = []):
    impl = getDOMImplementation()
    newdoc = impl.createDocument(None, tag, None)
    element = newdoc.documentElement

    for option in options:
        element.setAttribute(option[0],option[1])

    for child in children:
        element.appendChild(create_xml_element(child[0], child[1], child[2]))

    print element.toprettyxml()
    return element

if __name__ == "__main__":
  main(sys.argv[1:])
