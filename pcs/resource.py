import sys
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import usage
import utils
import re

def resource_cmd(argv):
    if len(argv) == 0:
        argv = ["show"]

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
        resource_remove(res_id)
    elif (sub_cmd == "list" or sub_cmd == "show"):
        resource_show(argv)
    elif (sub_cmd == "group"):
        resource_group(argv)
    else:
        usage.resource()


# Create a resource using cibadmin
# ra_class, ra_type & ra_provider must all contain valid info
def resource_create(ra_id, ra_type, ra_values, op_values):
    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = get_full_ra_type(ra_type)
    primitive_values.insert(0,("id",ra_id))
    op_attributes = convert_args_to_operations(op_values, ra_id)
    xml_resource_string = create_xml_string("primitive", primitive_values, instance_attributes + op_attributes)
    args = ["cibadmin"]
    args = args  + ["-o", "resources", "-C", "-X", xml_resource_string]
    output,retval = utils.run(args)
    print output

def convert_args_to_operations(op_values, ra_id):
    if len(op_values) == 0:
        return []
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

def resource_group(argv):
    if (len(argv) == 0):
        usage.resource()
        sys.exit(1)

    group_cmd = argv.pop(0)
    if (group_cmd == "add"):
        if (len(argv) < 2):
            usage.resource()
            sys.exit(1)
        group_name = argv.pop(0)
        resource_group_add(group_name, argv)
    elif (group_cmd == "remove_resource"):
        if (len(argv) < 2):
            usage.resource()
            sys.exit(1)
        group_name = argv.pop(0)
        resource_group_rm(group_name, argv)
    elif (group_cmd == "list"):
        print "NYI"

    else:
        usage.resource()
        sys.exit(1)

# Removes a resource and if it's the last resource in a group, remove the group
def resource_remove(resource_id, output = True):
    group = utils.get_cib_xpath('//resources/group/primitive[@id="'+resource_id+'"]/..')
    num_resources_in_group = 0

    if (group != ""):
        num_resources_in_group = len(parseString(group).documentElement.getElementsByTagName("primitive"))

    if (group == "" or num_resources_in_group > 1):
        args = ["cibadmin", "-o", "resources", "-D", "--xpath", "//primitive[@id='"+resource_id+"']"]
        if output == True:
            print "Deleting Resource - " + resource_id,
        output,retVal = utils.run(args)
        if retVal != 0:
            return False
    else:
        args = ["cibadmin", "-o", "resources", "-D", "--xml-text", group]
        if output == True:
            print "Deleting Resource (and group) - " + resource_id,
        output,retVal = utils.run(args)
        if retVal != 0:
            return False
    return True

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(group_name, resource_ids):
    resource_id = resource_ids[0]
    group_xpath = "//group[@id='"+group_name+"']"
    group_xml = utils.get_cib_xpath(group_xpath)
    if group_xml == "":
        print "ERROR: Group '%s' does not exist" % group_name
        sys.exit(1)

    for resource_id in resource_ids:
        element = parseString(group_xml).documentElement
        resource_xml = utils.get_cib_xpath("//group[@id='"+group_name+"']/primitive[@id='"+resource_id+"']")
        if resource_xml == "":
            print "ERROR Resource '%s' does not exist in group '%s'" % (resource_id, group_name)
            sys.exit(1)

        if not resource_remove(resource_id, False):
            print "Unable to move resource"
            sys.exit(1)
        output, retval = utils.add_to_cib("resources", resource_xml)
        if retval != 0:
            print "ERROR: Unable to re-add resource"
            print output
            sys.exit(1)
    return True


def resource_group_add(group_name, resource_ids):
    group_xpath = "//group[@id='"+group_name+"']"
    group_xml = utils.get_cib_xpath(group_xpath)
    if (group_xml == ""):
        impl = getDOMImplementation()
        newdoc = impl.createDocument(None, "group", None)
        element = newdoc.documentElement
        element.setAttribute("id", group_name)
        xml_resource_string = element.toxml()
    else:
        element = parseString(group_xml).documentElement

    resources_to_move = ""
    for resource_id in resource_ids:
        # If resource already exists in group then we skip
        if (utils.get_cib_xpath("//group[@id='"+group_name+"']/primitive[@id='"+resource_id+"']") != ""):
            print resource_id + " already exists in " + group_name + "\n"
            continue

        args = ["cibadmin", "-o", "resources", "-Q", "--xpath", "//primitive[@id='"+resource_id+"']"]
        output,retVal = utils.run(args)
        if (retVal != 0):
            print "Bad resource: " + resource_id
            continue
        resources_to_move = resources_to_move + output
        resource_remove(resource_id,False)

    if (resources_to_move != ""):
        resources_to_move = "<resources>" + resources_to_move + "</resources>"
        resource_children = parseString(resources_to_move).documentElement
        for child in resource_children.childNodes:
            element.appendChild(child)
        xml_resource_string = element.toprettyxml()
        
        args = ["cibadmin", "-o", "resources", "-c", "-M", "-X", xml_resource_string]
        output,retval = utils.run(args)
        if retVal != 0:
            print output,
    else:
        print "No resources to add.\n"
        sys.exit(1)

def resource_show(argv):
    if len(argv) == 0:    
        args = ["crm_resource","-L"]
        output,retval = utils.run(args)
        print output,
        return

    preg = re.compile(r'.*<primitive',re.DOTALL)
    for arg in argv:
        args = ["crm_resource","-r",arg,"-q"]
        output,retval = utils.run(args)
        if retval != 0:
            print "Error: unable to find resource '"+arg+"'"
            sys.exit(1)
        output = preg.sub("<primitive", output)
        dom = parseString(output)
        doc = dom.documentElement
        print "Resource:", arg
        for nvpair in doc.getElementsByTagName("nvpair"):
            print "  " + nvpair.getAttribute("name") + ": " + nvpair.getAttribute("value")
