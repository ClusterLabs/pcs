#!/usr/bin/python

import sys
import subprocess
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation

def main(argv):
    command = argv.pop(0)
    print command
    if (command == "resource"):
#        create_xml_string("primitive", [("myoptions", "abcd"),("2ndOptions", "xxx")])
        resource_create_cmd(argv)

def resource_create_cmd(argv):
    sub_cmd = argv.pop(0)
    if (sub_cmd == "create"):
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

# Create a resource using crm_resource
# ra_class, ra_type & ra_provider must all contain valid info
def resource_create(ra_id, ra_type, ra_values, op_values):
    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = get_full_ra_type(ra_type)
    primitive_values.insert(0,("id",ra_id))
    xml_resource_string = create_xml_string("primitive", primitive_values, instance_attributes)
    args = ["cibadmin"]
    args = args  + ["-o", "resources", "-C", "-X", xml_resource_string]
    output = subprocess.call(args)
    print output

def convert_args_to_instance_variables(ra_values, ra_id):
    tuples = convert_args_to_tuples(ra_values)
    ivs = []
    attribute_id = ra_id + "-instance_attributes"
    for (a,b) in tuples:
        ivs.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("instance_attributes", [[("id"),(attribute_id)]], ivs)
    print ret
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

    print "Tag:"
    print tag
    print "Options:"
    print options
    print "Children:"
    print children
    print "XX"
    for option in options:
        print option
        print option.__class__
        element.setAttribute(option[0],option[1])

    for child in children:
        print "CHILD"
        print child
        element.appendChild(create_xml_element(child[0], child[1], child[2]))

    print element.toprettyxml()
    return element

if __name__ == "__main__":
  main(sys.argv[1:])
