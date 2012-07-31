import sys
import os
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import usage
import utils
import re
import textwrap
import xml.etree.ElementTree

def resource_cmd(argv):
    if len(argv) == 0:
        argv = ["show"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.resource()
    elif (sub_cmd == "create"):
        if len(argv) == 0:
            resource_list_available()
        elif len(argv) == 1:
            resource_list_options(argv[0])
        else:
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
    elif (sub_cmd == "update"):
        res_id = argv.pop(0)
        resource_update(res_id,argv)
    elif (sub_cmd == "delete"):
        res_id = argv.pop(0)
        resource_remove(res_id)
    elif (sub_cmd == "list" or sub_cmd == "show"):
        resource_show(argv)
    elif (sub_cmd == "group"):
        resource_group(argv)
    elif (sub_cmd == "clone"):
        resource_clone(argv)
    elif (sub_cmd == "start"):
        resource_start(argv)
    elif (sub_cmd == "stop"):
        resource_stop(argv)
    elif (sub_cmd == "restart"):
# Need to have a wait in here to make sure the stop registers
        print "Not Yet Implemented"
#        if resource_stop(argv):
#            resource_start(argv)
    elif (sub_cmd == "manage"):
        resource_manage(argv, True)
    elif (sub_cmd == "unmanage"):
        resource_manage(argv, False)
    else:
        usage.resource()


# List available resources
# TODO make location more easily configurable
def resource_list_available():
    os.environ['OCF_ROOT'] = "/usr/lib/ocf/"
    providers = sorted(os.listdir("/usr/lib/ocf/resource.d"))
    for provider in providers:
        resources = sorted(os.listdir("/usr/lib/ocf/resource.d/" + provider))
        for resource in resources:
            if resource.startswith(".") or resource == "ocf-shellfuncs":
                continue
            metadata = get_metadata("/usr/lib/ocf/resource.d/" + provider + "/" + resource)
            if metadata == False:
                continue
            sd = ""
            full_res_name = "ocf:" + provider + ":" + resource
            try:
                dom = parseString(metadata)
                shortdesc = dom.documentElement.getElementsByTagName("shortdesc")
                if len(shortdesc) > 0:
                    sd = " - " +  format_desc(full_res_name.__len__() + 3, shortdesc[0].firstChild.nodeValue.strip().replace("\n", ""))
            except xml.parsers.expat.ExpatError:
                sd = ""
            finally:
                print full_res_name + sd

def resource_list_options(resource):
    found_resource = False
    if "ocf:" in resource:
        resource_split = resource.split(":",3)
        providers = [resource_split[1]]
        resource = resource_split[2]
    else:
        providers = sorted(os.listdir("/usr/lib/ocf/resource.d"))
    for provider in providers:
        metadata = get_metadata("/usr/lib/ocf/resource.d/" + provider + "/" + resource)
        if metadata == False:
            continue
        else:
            found_resource = True
        
        try:
            print "Resource options for: %s" % resource
            dom = parseString(metadata)
            params = dom.documentElement.getElementsByTagName("parameter")
            for param in params:
                name = param.getAttribute("name")
                if param.getAttribute("required") == "1":
                    name += " (required)"
                desc = param.getElementsByTagName("longdesc")[0].firstChild.nodeValue.strip().replace("\n", "")
                indent = name.__len__() + 4
                desc = format_desc(indent, desc)
                print "  " + name + ": " + desc
        except xml.parsers.expat.ExpatError:
            print "Unable to parse xml for: %s" % (resource)
        break

    if not found_resource:
        print "Unable to find resource: %s" % resource
        sys.exit(1)

# Return the string formatted with a line length of 79 and indented
def format_desc(indent, desc):
    desc = " ".join(desc.split())
    rows, columns = utils.getTerminalSize()
    columns = int(columns)
    if columns < 40: columns = 40
    afterindent = columns - indent
    output = ""
    first = True

    for line in textwrap.wrap(desc, afterindent):
        if not first:
            for i in range(0,indent):
                output += " "
        output += line
        output += "\n"
        first = False

    return output.rstrip()

def get_metadata(resource_agent_script):
    os.environ['OCF_ROOT'] = "/usr/lib/ocf/"
    if (not os.path.isfile(resource_agent_script)) or (not os.access(resource_agent_script, os.X_OK)):
        return False

    (metadata, retval) = utils.run([resource_agent_script, "meta-data"])
    if retval == 0:
        return metadata
    else:
        return False

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
    if retval != 0:
        print "ERROR: Unable to create resource/fence device"
        print output.split('\n')[0]
        sys.exit(1)

# Update a resource, removing any args that are empty and adding/updating
# args that are not empty
def resource_update(res_id,args):
    params = convert_args_to_tuples(args)
    for (key,val) in params:
        if val == "":
            output,retval = utils.run(["crm_resource", "-r", res_id, "-d",
                key])
            if retval != 0:
                print "Error: Unable to remove '%s' from '%s'" % (key,res_id)
                sys.exit(1)
        else:
            output,retval = utils.run(["crm_resource", "-r", res_id, "-p",
                key,"-v",val])
            if retval != 0:
                print "Error: Unable to add '%s' from '%s'" % (key,res_id)
                sys.exit(1)

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
    # If len = 2 then we're creating a fence device
    if len(ra_def) == 2:
        return([("class",ra_def[0]),("type",ra_def[1])])
    else:
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
        resource_group_list(argv)

    else:
        usage.resource()
        sys.exit(1)

def resource_clone(argv):
    if len(argv) < 2:
        usage.resource()
        sys.exit(1)

    sub_cmd = argv.pop(0)
    if sub_cmd == "create":
        resource_clone_create(argv)
    elif sub_cmd == "update":
        resource_clone_create(argv,True)
    elif sub_cmd == "remove":
        resource_clone_remove(argv)
    else:
        usage.resource()
        sys.exit(1)

def resource_clone_create(argv, update = False):
    name = argv.pop(0)
    element = None
    dom = xml.dom.minidom.parseString(utils.get_cib())
    re = dom.documentElement.getElementsByTagName("resources")[0]
    for res in re.getElementsByTagName("primitive") + re.getElementsByTagName("group"):
        if res.getAttribute("id") == name:
            element = res
            break

    if element == None:
        print "Error: unable to find group or resource: %s" % name
        sys.exit(1)

    if update == True:
        if element.parentNode.tagName != "clone":
            print "Error: %s is not currently a clone" % name
            sys.exit(1)
        clone = element.parentNode
        for ma in clone.getElementsByTagName("meta_attributes"):
            clone.removeChild(ma)
    else:
        for c in re.getElementsByTagName("clone"):
            if c.getAttribute("id") == name + "-clone":
                print "Error: clone already exists for: %s" % name
                sys.exit(1)
        clone = dom.createElement("clone")
        clone.setAttribute("id",name + "-clone")
        clone.appendChild(element)
        re.appendChild(clone)

    meta = dom.createElement("meta_attributes")
    meta.setAttribute("id",name + "-clone-meta")
    args = convert_args_to_tuples(argv)
    for arg in args:
        nvpair = dom.createElement("nvpair")
        nvpair.setAttribute("id", name+"-"+arg[0])
        nvpair.setAttribute("name", arg[0])
        nvpair.setAttribute("value", arg[1])
        meta.appendChild(nvpair)
    clone.appendChild(meta)
    xml_resource_string = re.toxml()
    args = ["cibadmin", "-o", "resources", "-R", "-X", xml_resource_string]
    output, retval = utils.run(args)

    if retval != 0:
        print output
        sys.exit(1)

def resource_clone_remove(argv):
    if len(argv) != 1:
        usage.resource()
        sys.exit(1)

    name = argv.pop()
    dom = xml.dom.minidom.parseString(utils.get_cib())
    re = dom.documentElement.getElementsByTagName("resources")[0]

    found = False
    for res in re.getElementsByTagName("primitive") + re.getElementsByTagName("group"):
        if res.getAttribute("id") == name:
            clone = res.parentNode
            if clone.tagName != "clone":
                print "Error: %s is not in a clone" % name
                sys.exit(1)
            clone.parentNode.appendChild(res)
            clone.parentNode.removeChild(clone)
            found = True
            break

    if found == False:
        print "Error: could not find resource or group: %s" % name
        sys.exit(1)

    xml_resource_string = re.toxml()
    args = ["cibadmin", "-o", "resources", "-R", "-X", xml_resource_string]
    output, retval = utils.run(args)

    if retval != 0:
        print output
        sys.exit(1)
    
# Also performs a 'cleanup' to remove it completely
def resource_remove(resource_id, output = True):
    group = utils.get_cib_xpath('//resources/group/primitive[@id="'+resource_id+'"]/..')
    num_resources_in_group = 0

    if not utils.does_exist('//resources/descendant::primitive[@id="'+resource_id+'"]'):
        print "Error: Resource does not exist."
        sys.exit(1)

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
            print "Deleting Resource (and group) - " + resource_id
        cmdoutput,retVal = utils.run(args)
        if retVal != 0:
            if output == True:
                print "ERROR: Unable to remove resource '%s' (do constraints exist?)" % (resource_id)
            return False
    args = ["crm_resource","-C","-r",resource_id]
    cmdoutput, retVal = utils.run(args)
# We don't currently check output because the resource may have already been
# properly cleaned up
    return True

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(group_name, resource_ids):
    resource_id = resource_ids[0]
    dom = parseString(utils.get_cib())
    dom = dom.getElementsByTagName("configuration")[0]
    group_match = None

    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_name:
            group_match = group

    if not group_match:
        print "ERROR: Group '%s' does not exist" % group_name
        sys.exit(1)

    resources_to_move = []
    for resource_id in resource_ids:
        found_resource = False
        for resource in group.getElementsByTagName("primitive"):
            if resource.getAttribute("id") == resource_id:
                found_resource = True
                resources_to_move.append(resource)
                break
        if not found_resource:
            print "ERROR Resource '%s' does not exist in group '%s'" % (resource_id, group_name)
            sys.exit(1)

    for resource in resources_to_move:
        parent = resource.parentNode
        resource.parentNode.removeChild(resource)
        parent.parentNode.appendChild(resource)

    output, retval = utils.run(["cibadmin", "--replace", "-o", "configuration", "-X", dom.toxml()])

    if retval != 0:
        print "ERROR: Unable to re-add resource"
        print output
        sys.exit(1)
    return True


def resource_group_add(group_name, resource_ids):
    out = utils.get_cib()
    dom = xml.dom.minidom.parseString(out)
    top_element = dom.documentElement
    resources_element = top_element.getElementsByTagName("resources")[0]
    group_found = False

    for resource in top_element.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == group_name:
            print "Error: %s is already a resource" % group_name
            sys.exit(1)

    for group in top_element.getElementsByTagName("group"):
        if group.getAttribute("id") == group_name:
            group_found = True
            mygroup = group

    if group_found == False:
        mygroup = dom.createElement("group")
        mygroup.setAttribute("id", group_name)
        resources_element.appendChild(mygroup)


    resources_to_move = []
    for resource_id in resource_ids:
        already_exists = False
        for resource in mygroup.getElementsByTagName("primitive"):
            # If resource already exists in group then we skip
            if resource.getAttribute("id") == resource_id:
                print resource_id + " already exists in " + group_name + "\n"
                already_exists = True
                break
        if already_exists == True:
            continue

        resource_found = False
        for resource in resources_element.getElementsByTagName("primitive"):
            if resource.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                continue
            if resource.getAttribute("id") == resource_id:
                resources_to_move.append(resource)
                resource_found = True
                break

        if resource_found == False:
            print "Unable to find resource: " + resource_id
            continue

    if resources_to_move:
        for resource in resources_to_move:
            oldParent = resource.parentNode
            mygroup.appendChild(resource)
            if oldParent.tagName == "group" and len(oldParent.getElementsByTagName("primitive")) == 0:
                oldParent.parentNode.removeChild(oldParent)
        
        xml_resource_string = resources_element.toxml()
        args = ["cibadmin", "-o", "resources", "-R", "-X", xml_resource_string]
        output,retval = utils.run(args)
        if retval != 0:
            print output,
    else:
        print "Error: No resources to add."
        sys.exit(1)

def resource_group_list(argv):
    group_xpath = "//group"
    group_xml = utils.get_cib_xpath(group_xpath)

    # If no groups exist, we silently return
    if (group_xml == ""):
        return

    element = parseString(group_xml).documentElement
    # If there is more than one group returned it's wrapped in an xpath-query
    # element
    if element.tagName == "xpath-query":
        elements = element.getElementsByTagName("group")
    else:
        elements = [element]

    for e in elements:
        print e.getAttribute("id") + ":",
        for resource in e.getElementsByTagName("primitive"):
            print resource.getAttribute("id"),
        print ""

def resource_show(argv):
    if len(argv) == 0:    
        args = ["crm_resource","-L"]
        output,retval = utils.run(args)
        preg = re.compile(r'.*(stonith:.*)')
        for line in output.split('\n'):
            if not preg.match(line) and line != "":
                print line
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

def resource_stop(argv):
    args = ["crm_resource", "-r", argv[0], "-m", "-p", "target-role", "-v", "Stopped"]
    output, retval = utils.run(args)
    if retval != 0:
        print output,
        return False
    else:
        return True

def resource_start(argv):
    args = ["crm_resource", "-r", argv[0], "-m", "-d", "target-role"]
    output, retval = utils.run(args)
    if retval != 0:
        print output,
        return False
    else:
        return True

def resource_manage(argv, set_managed):
    if len(argv) == 0:
        usage.resource()
        sys.exit(1)

    for resource in argv:
        if not utils.does_exist("//primitive[@id='"+resource+"']"):
            print "Error: %s doesn't exist." % resource
            sys.exit(1)
        exists =  utils.does_exist("//primitive[@id='"+resource+"']/meta_attributes/nvpair[@name='is-managed']")
        if set_managed and not exists:
            print "Error: %s is already managed" % resource
            sys.exit(1)
        elif not set_managed and exists:
            print "Error: %s is already unmanaged" % resource
            sys.exit(1)

    for resource in argv:
        if not set_managed:
            (output, retval) =  utils.set_unmanaged(resource)
            if retval != 0:
                print "Error attempting to unmanage resource: %s" % output
                sys.exit(1)
        else:
            xpath = "//primitive[@id='"+resource+"']/meta_attributes/nvpair[@name='is-managed']" 
            my_xml = utils.get_cib_xpath(xpath)
            utils.remove_from_cib(my_xml)
