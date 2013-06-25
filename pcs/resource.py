import sys
import os
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import usage
import utils
import re
import textwrap
import xml.etree.ElementTree as ET
import constraint

def resource_cmd(argv):
    if len(argv) == 0:
        argv = ["show"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.resource(argv)
    elif (sub_cmd == "list"):
        resource_list_available(argv)
    elif (sub_cmd == "describe"):
        if len(argv) == 1:
            resource_list_options(argv[0])
        else:
            usage.resource()
            sys.exit(1)
    elif (sub_cmd == "create"):
        if len(argv) < 2:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        res_type = argv.pop(0)
        ra_values = []
        op_values = [[]]
        meta_values=[]
        op_args = False
        meta_args = False
        for arg in argv:
            if arg == "op":
                op_args = True
                meta_args = False
            elif arg == "meta":
                meta_args = True
                op_args = False
            else:
                if op_args:
                    if arg == "op":
                        op_values.append([])
                    elif "=" not in arg and len(op_values[-1]) != 0:
                        op_values.append([])
                        op_values[-1].append(arg)
                    else:
                        op_values[-1].append(arg)
                elif meta_args:
                    if "=" in arg:
                        meta_values.append(arg)
                else:
                    ra_values.append(arg)
    
        resource_create(res_id, res_type, ra_values, op_values, meta_values)
    elif (sub_cmd == "move"):
        resource_move(argv)
    elif (sub_cmd == "unmove"):
        resource_move(argv,True)
    elif (sub_cmd == "standards"):
        resource_standards()
    elif (sub_cmd == "providers"):
        resource_providers()
    elif (sub_cmd == "agents"):
        resource_agents(argv)
    elif (sub_cmd == "update"):
        if len(argv) == 0:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_update(res_id,argv)
    elif (sub_cmd == "add_operation"):
        if len(argv) == 0:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_operation_add(res_id,argv)
    elif (sub_cmd == "remove_operation"):
        if len(argv) == 0:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_operation_remove(res_id,argv)
    elif (sub_cmd == "meta"):
        if len(argv) < 2:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_meta(res_id,argv)
    elif (sub_cmd == "delete"):
        if len(argv) == 0:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_remove(res_id)
    elif (sub_cmd == "show"):
        resource_show(argv)
    elif (sub_cmd == "group"):
        resource_group(argv)
    elif (sub_cmd == "clone"):
        resource_clone(argv)
    elif (sub_cmd == "unclone"):
        resource_clone_master_remove(argv)
    elif (sub_cmd == "master"):
        resource_master(argv)
    elif (sub_cmd == "unmaster"):
        resource_clone_master_remove(argv)
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
    elif (sub_cmd == "failcount"):
        resource_failcount(argv)
    elif (sub_cmd == "rsc" or sub_cmd == "op"):
        if len(argv) < 1:
            usage.resource()
            sys.exit(1)
        rsc_subcmd = argv.pop(0)
        if (sub_cmd == "rsc" and rsc_subcmd == "defaults"):
            if len(argv) == 0:
                show_defaults("rsc_defaults")
            else:
                set_default("rsc_defaults", argv)
        elif (sub_cmd == "op" and rsc_subcmd == "defaults"):
            if len(argv) == 0:
                show_defaults("op_defaults")
            else:
                set_default("op_defaults", argv)
        else:
            usage.resource()
            sys.exit(1)
    elif (sub_cmd == "cleanup"):
        if len(argv) < 1:
            usage.resource()
            sys.exit(1)
        res_id = argv.pop(0)
        resource_cleanup(res_id)
    else:
        usage.resource()
        sys.exit(1)

# List available resources
# TODO make location more easily configurable
def resource_list_available(argv):
    ret = ""
    if len(argv) != 0:
        filter_string = argv[0]
    else:
        filter_string = ""

# ocf agents
    os.environ['OCF_ROOT'] = "/usr/lib/ocf/"
    providers = sorted(os.listdir("/usr/lib/ocf/resource.d"))
    for provider in providers:
        resources = sorted(os.listdir("/usr/lib/ocf/resource.d/" + provider))
        for resource in resources:
            if resource.startswith(".") or resource == "ocf-shellfuncs":
                continue
            full_res_name = "ocf:" + provider + ":" + resource
            if full_res_name.lower().count(filter_string.lower()) == 0:
                continue
            metadata = utils.get_metadata("/usr/lib/ocf/resource.d/" + provider + "/" + resource)
            if metadata == False:
                continue
            sd = ""
            try:
                dom = parseString(metadata)
                shortdesc = dom.documentElement.getElementsByTagName("shortdesc")
                if len(shortdesc) > 0:
                    sd = " - " +  format_desc(full_res_name.__len__() + 3, shortdesc[0].firstChild.nodeValue.strip().replace("\n", " "))
            except xml.parsers.expat.ExpatError:
                sd = ""
            finally:
                ret += full_res_name + sd + "\n"
# lsb agents
    lsb_dir = "/etc/init.d/"
    agents = sorted(os.listdir(lsb_dir))
    for agent in agents:
        if os.access(lsb_dir + agent, os.X_OK):
            ret += "lsb:" + agent + "\n"
# systemd agents
    agents, retval = utils.run(["systemctl", "list-unit-files", "--full"])
    agents = agents.split("\n")

    for agent in agents:
        match = re.search(r'^([\S]*)\.service',agent)
        if match:
            ret += "systemd:" + match.group(1) + "\n"

    if filter_string != "":
        rlines = ret.split("\n")
        for rline in rlines:
            if rline.lower().find(filter_string.lower()) != -1:
                print rline
    else:
        print ret,


def resource_list_options(resource):
    found_resource = False
    if "ocf:" in resource:
        resource_split = resource.split(":",3)
        providers = [resource_split[1]]
        resource = resource_split[2]
    else:
        providers = sorted(os.listdir("/usr/lib/ocf/resource.d"))
    for provider in providers:
        metadata = utils.get_metadata("/usr/lib/ocf/resource.d/" + provider + "/" + resource)
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
                desc = param.getElementsByTagName("longdesc")[0].firstChild.nodeValue.strip().replace("\n", " ")
                indent = name.__len__() + 4
                desc = format_desc(indent, desc)
                print "  " + name + ": " + desc
        except xml.parsers.expat.ExpatError:
            utils.err ("Unable to parse xml for: %s" % (resource))
        break

    if not found_resource:
        utils.err ("Unable to find resource: %s" % resource)

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

# Create a resource using cibadmin
# ra_class, ra_type & ra_provider must all contain valid info
def resource_create(ra_id, ra_type, ra_values, op_values, meta_values=[]):
    if not utils.is_valid_resource(ra_type) and not ("--force" in utils.pcs_options):
        utils.err ("Unable to create resource '%s', it is not installed on this system (use --force to override)" % ra_type)

    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = get_full_ra_type(ra_type)
    primitive_values.insert(0,("id",ra_id))
    op_attributes = convert_args_to_operations(op_values, ra_id)
    meta_attributes = convert_args_to_meta_attrs(meta_values, ra_id)
    if not "--force" in utils.pcs_options and utils.does_resource_have_options(ra_type):
        params = convert_args_to_tuples(ra_values)
        bad_opts = utils.validInstanceAttributes(ra_id, params , get_full_ra_type(ra_type, True))
        if len(bad_opts) != 0:
            utils.err ("resource option(s): '%s', are not recognized for resource type: '%s' (use --force to override)" \
                    % (", ".join(bad_opts), get_full_ra_type(ra_type, True)))
    xml_resource_string = create_xml_string("primitive", primitive_values, instance_attributes + op_attributes + meta_attributes)
    args = ["cibadmin"]
    args = args  + ["-o", "resources", "-C", "-X", xml_resource_string]
    output,retval = utils.run(args)
    if retval != 0:
        utils.err ("Unable to create resource/fence device\n" + output)

    if "--clone" in utils.pcs_options:
        clone_opts = []
        if "--cloneopt" in utils.pcs_options:
            clone_opts = utils.pcs_options["--cloneopt"]
            if type(clone_opts) != list:
                clone_opts = [clone_opts]
        resource_clone_create([ra_id] + clone_opts)
    elif "--master" in utils.pcs_options:
        resource_master_create([ra_id+"-master",ra_id])


def resource_move(argv,unmove=False):
    if len(argv) == 0:
        utils.err ("must specify resource to move/unmove")

    resource_id = argv.pop(0)

    if len(argv) >= 1:
        dest_node = argv.pop(0)
    else:
        dest_node = None

    if unmove:
        output,ret = utils.run(["crm_resource", "--resource", resource_id, "--un-move"])
    else:
        if dest_node == None:
            output,ret = utils.run(["crm_resource", "--resource", resource_id, "--move"])
        else:
            output,ret = utils.run(["crm_resource", "--resource", resource_id, "--move", "--node", dest_node])
    if ret != 0:
        utils.err ("error moving/unmoving resource\n" + output)

def resource_standards(return_output=False):
    output, retval = utils.run(["crm_resource","--list-standards"], True)
    # Return value is ignored because it contains the number of standards
    # returned, not an error code
    output = output.strip()
    if return_output == True:
        return output
    print output

def resource_providers():
    output, retval = utils.run(["crm_resource","--list-ocf-providers"],True)
    # Return value is ignored because it contains the number of providers
    # returned, not an error code
    print output.strip()

def resource_agents(argv):
    if len(argv) > 1:
        usage.resource()
        sys.exit(1)
    elif len(argv) == 1:
        standards = [argv[0]]
    else:
        output = resource_standards(True)
        standards = output.split('\n')

    for s in standards:
        output, retval = utils.run(["crm_resource", "--list-agents", s])
        preg = re.compile(r'\d+ agents found for standard.*$', re.MULTILINE)
        output = preg.sub("", output)
        output = output.strip()
        print output

# Update a resource, removing any args that are empty and adding/updating
# args that are not empty
def resource_update(res_id,args):
    dom = utils.get_cib_dom()

# Extract operation arguments
    op_args = False
    meta_args = False
    ra_values = []
    op_values = []
    meta_values = []
    for arg in args:
        if arg == "op":
            op_args = True
            meta_args = False
            op_values.append([])
        elif arg == "meta":
            meta_args = True
            op_args = False
        else:
            if op_args:
                if arg == "op":
                    op_values.append([])
                elif "=" not in arg and len(op_values[-1]) != 0:
                    op_values.append([])
                    op_values[-1].append(arg)
                else:
                    op_values[-1].append(arg)
            elif meta_args:
                if "=" in arg:
                    meta_values.append(arg)
            else:
                ra_values.append(arg)

    resource = None
    for r in dom.getElementsByTagName("primitive"):
        if r.getAttribute("id") == res_id:
            resource = r
            break

    if not resource:
        clone = None
        for c in dom.getElementsByTagName("clone"):
            if c.getAttribute("id") == res_id:
                clone = r
                break

        if clone:
            for a in c.childNodes:
                if a.localName == "primitive" or a.localName == "group":
                    return resource_clone_create([a.getAttribute("id")] + args, True)

        master = None
        for m in dom.getElementsByTagName("master"):
            if m.getAttribute("id") == res_id:
                master = r 
                break

        if master:
            return resource_master_create([res_id] + args, True)

        utils.err ("Unable to find resource: %s" % res_id)

    instance_attributes = resource.getElementsByTagName("instance_attributes")
    if len(instance_attributes) == 0:
        instance_attributes = dom.createElement("instance_attributes")
        instance_attributes.setAttribute("id", res_id + "-instance_attributes")
        resource.appendChild(instance_attributes)
    else:
        instance_attributes = instance_attributes[0]
    
    params = convert_args_to_tuples(ra_values)
    if not "--force" in utils.pcs_options and (resource.getAttribute("class") == "ocf" or resource.getAttribute("class") == "stonith"):
        resClass = resource.getAttribute("class")
        resProvider = resource.getAttribute("provider")
        resType = resource.getAttribute("type")
        if resProvider == "":
            resource_type = resClass + ":" + resType
        else:
            resource_type = resClass + ":" + resProvider + ":" + resType
        bad_opts = utils.validInstanceAttributes(res_id, params, resource_type)
        if len(bad_opts) != 0:
            utils.err ("resource option(s): '%s', are not recognized for resource type: '%s' (use --force to override)" \
                    % (", ".join(bad_opts), utils.getResourceType(resource)))


    for (key,val) in params:
        ia_found = False
        for ia in instance_attributes.getElementsByTagName("nvpair"):
            if ia.getAttribute("name") == key:
                ia_found = True
                if val == "":
                    instance_attributes.removeChild(ia)
                else:
                    ia.setAttribute("value", val)
                break
        if not ia_found:
            ia = dom.createElement("nvpair")
            ia.setAttribute("id", res_id + "-instance_attributes-" + key)
            ia.setAttribute("name", key)
            ia.setAttribute("value", val)
            instance_attributes.appendChild(ia)

    meta_attributes = resource.getElementsByTagName("meta_attributes")
    if len(meta_attributes) == 0:
        meta_attributes = dom.createElement("meta_attributes")
        meta_attributes.setAttribute("id", res_id + "-meta_attributes")
        resource.appendChild(meta_attributes)
    else:
        meta_attributes = meta_attributes[0]
    
    meta_attrs = convert_args_to_tuples(meta_values)
    for (key,val) in meta_attrs:
        meta_found = False
        for ma in meta_attributes.getElementsByTagName("nvpair"):
            if ma.getAttribute("name") == key:
                meta_found = True
                if val == "":
                    meta_attributes.removeChild(ma)
                else:
                    ma.setAttribute("value", val)
                break
        if not meta_found:
            ma = dom.createElement("nvpair")
            ma.setAttribute("id", res_id + "-meta_attributes-" + key)
            ma.setAttribute("name", key)
            ma.setAttribute("value", val)
            meta_attributes.appendChild(ma)

    operations = resource.getElementsByTagName("operations")
    if len(operations) == 0:
        operations = dom.createElement("operations")
        resource.appendChild(operations)
    else:
        operations = operations[0]

    for element in op_values:
        if len(element) <= 1:
            continue
        op_name = element.pop(0)
        op = dom.createElement("op")
        for existing_op in operations.getElementsByTagName("op"):
            if existing_op.getAttribute("name") == op_name:
                op = existing_op
                for key in op.attributes.keys():
                    op.removeAttribute(key)
                break

        op.setAttribute("name",op_name)
        op_id = res_id + "-" + op_name
        op_vars = convert_args_to_tuples(element)
        for (key,val) in op_vars:
            op.setAttribute(key,val)
            op_id += "-" + key + "-" + val
        op.setAttribute("id", op_id)
        operations.appendChild(op)
        
    if len(instance_attributes.getElementsByTagName("nvpair")) == 0:
        instance_attributes.parentNode.removeChild(instance_attributes)

    utils.replace_cib_configuration(dom)

def resource_operation_add(res_id, argv):
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)

    op_name = argv.pop(0)
    dom = utils.get_cib_dom()
    resource_found = False

    for resource in dom.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == res_id:
            resource_found = True
            break

    if not resource_found:
        utils.err ("Unable to find resource: %s" % res_id)

    op_properties = convert_args_to_tuples(argv)
    op_properties.sort(key=lambda a:a[0])
    op_properties.insert(0,('name', op_name))
    found_match = False

    op = dom.createElement("op")
    op_id = res_id + "-"
    for prop in op_properties:
        op.setAttribute(prop[0], prop[1])
        op_id += prop[0] + "-" + prop[1] + "-"
    op_id = op_id[:-1]
    op_id = utils.find_unique_id(dom, op_id)
    op.setAttribute("id", op_id)

    operations = resource.getElementsByTagName("operations")
    if len(operations) == 0:
        operations = dom.createElement("operations")
        resource.appendChild(operations)
    else:
        operations = operations[0]

    if utils.operation_exists(operations,op):
        utils.err ("identical operation already exists for %s" % res_id)

    operations.appendChild(op)
    utils.replace_cib_configuration(dom)

def resource_operation_remove(res_id, argv):
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)

    original_argv = " ".join(argv)

    op_name = argv.pop(0)
    dom = utils.get_cib_dom()
    resource_found = False

    for resource in dom.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == res_id:
            resource_found = True
            break

    if not resource_found:
        utils.err("Unable to find resource: %s" % res_id)

    op_properties = convert_args_to_tuples(argv)
    op_properties.append(('name', op_name))
    found_match = False
    for op in resource.getElementsByTagName("op"):
        temp_properties = []
        for attrName in op.attributes.keys():
            if attrName == "id":
                continue
            temp_properties.append((attrName,op.attributes.get(attrName).nodeValue))

        if len(set(op_properties) ^ set(temp_properties)) == 0:
            found_match = True
            parent = op.parentNode
            parent.removeChild(op)
            if len(parent.getElementsByTagName("op")) == 0:
                parent.parentNode.removeChild(parent)
            break

    if not found_match:
        utils.err ("Unable to find operation matching: %s" % original_argv)

    utils.replace_cib_configuration(dom)

def resource_meta(res_id, argv):
    dom = utils.get_cib_dom()
    allowed_elements = ["primitive","group","clone","master"]
    elems = []
    element_found = False
    for ae in allowed_elements:
        elems = elems + dom.getElementsByTagName(ae)
    for elem in elems:
        if elem.getAttribute("id") == res_id:
            element_found = True
            break

    if not element_found:
        utils.err("unable to find a resource/clone/master/group: %s" % res_id)

    # Make sure we only check direct children for meta_attributes
    meta_attributes = []
    for child in elem.childNodes:
        if child.nodeType == child.ELEMENT_NODE and child.tagName == "meta_attributes":
            meta_attributes.append(child)

    if len(meta_attributes) == 0:
        meta_attributes = dom.createElement("meta_attributes")
        meta_attributes.setAttribute("id", res_id + "-meta_attributes")
        elem.appendChild(meta_attributes)
    else:
        meta_attributes = meta_attributes[0]

    meta_attrs = convert_args_to_tuples(argv)
    for (key,val) in meta_attrs:
        meta_found = False
        for ma in meta_attributes.getElementsByTagName("nvpair"):
            if ma.getAttribute("name") == key:
                meta_found = True
                if val == "":
                    meta_attributes.removeChild(ma)
                else:
                    ma.setAttribute("value", val)
                break
        if not meta_found:
            ma = dom.createElement("nvpair")
            ma.setAttribute("id", res_id + "-meta_attributes-" + key)
            ma.setAttribute("name", key)
            ma.setAttribute("value", val)
            meta_attributes.appendChild(ma)

    utils.replace_cib_configuration(dom)

# Takes in a resource id and an array of arrays with operation values starting
# with the operation name, followed by options
# sample op_values = ["monitor", "interval=5s"]
def convert_args_to_operations(op_values_list, ra_id):
    ret = []
    ret_ops = []
    for op_values in op_values_list:
        if len(op_values) == 0:
            return []
        if '=' in op_values[0]:
            utils.err("When using 'op' you must specify an operation name after 'op'")
        if len(op_values) < 2:
            utils.err("When using 'op' you must specify an operation name and at least one option")
        op_name = op_values.pop(0)
        tuples = convert_args_to_tuples(op_values)
        op_attrs = []
        for (a,b) in tuples:
            op_attrs.append((a,b))

        op_attrs.append(("id",ra_id+"-"+op_name+"-"+a+"-"+b))
        op_attrs.append((a,b))
        op_attrs.append(("name",op_name))
        ops = ("op",op_attrs,[])
        ret_ops.append(ops)
    ret = [("operations", [], ret_ops)]
    return ret

def convert_args_to_meta_attrs(meta_attrs, ra_id):
    if len(meta_attrs) == 0:
        return []

    meta_vars = []
    tuples = convert_args_to_tuples(meta_attrs)
    attribute_id = ra_id + "-meta_attributes"
    for (a,b) in tuples:
        meta_vars.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("meta_attributes", [[("id"), (attribute_id)]], meta_vars)
    return [ret]

def convert_args_to_instance_variables(ra_values, ra_id):
    tuples = convert_args_to_tuples(ra_values)
    ivs = []
    attribute_id = ra_id + "-instance_attributes"
    for (a,b) in tuples:
        ivs.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("instance_attributes", [[("id"),(attribute_id)]], ivs)
    return [ret]

# Passed an array of strings ["a=b","c=d"], return array of tuples
# [("a","b"),("c","d")]
def convert_args_to_tuples(ra_values):
    ret = []
    for ra_val in ra_values:
        if ra_val.count("=") == 1:
            split_val = ra_val.split("=")
            ret.append((split_val[0],split_val[1]))
    return ret

# Passed a resource type (ex. ocf:heartbeat:IPaddr2 or IPaddr2) and returns
# a list of tuples mapping the types to xml attributes
def get_full_ra_type(ra_type, return_string = False):
    if (ra_type.count(":") == 0):
        ra_type = "ocf:heartbeat:" + ra_type
    
    if return_string:
        return ra_type

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
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)
    res = argv[0]
    resource_clone_create(argv)
    constraint.constraint_resource_update(res)

def resource_clone_create(argv, update = False):
    name = argv.pop(0)
    element = None
    dom = utils.get_cib_dom()
    re = dom.documentElement.getElementsByTagName("resources")[0]
    for res in re.getElementsByTagName("primitive") + re.getElementsByTagName("group"):
        if res.getAttribute("id") == name:
            element = res
            break

    if element == None:
        utils.err("unable to find group or resource: %s" % name)

    if update == True:
        if element.parentNode.tagName != "clone":
            utils.err("%s is not currently a clone" % name)
        clone = element.parentNode
        for ma in clone.getElementsByTagName("meta_attributes"):
            clone.removeChild(ma)
    else:
        for c in re.getElementsByTagName("clone"):
            if c.getAttribute("id") == name + "-clone":
                utils.err("clone already exists for: %s" % name)
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
        utils.err("unable to create clone\n" + output)

def resource_clone_master_remove(argv):
    if len(argv) != 1:
        usage.resource()
        sys.exit(1)

    name = argv.pop()
    dom = utils.get_cib_dom()
    re = dom.documentElement.getElementsByTagName("resources")[0]

    found = False
    for res in re.getElementsByTagName("primitive") + re.getElementsByTagName("group"):
        if res.getAttribute("id") == name:
            clone = res.parentNode
            if clone.tagName != "clone" and clone.tagName != "master":
                utils.err("%s is not in a clone or master/slave" % name)
            clone.parentNode.appendChild(res)
            clone.parentNode.removeChild(clone)
            found = True
            break

    if found == False:
        utils.err("could not find resource or group: %s" % name)

    xml_resource_string = re.toxml()
    args = ["cibadmin", "-o", "resources", "-R", "-X", xml_resource_string]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to remove clone\n" + output)
    
def resource_master(argv):
    resource_master_create(argv)

def resource_master_create(argv, update=False):
    non_option_args_count = 0
    for arg in argv:
        if arg.find("=") == -1:
            non_option_args_count += 1
    
    if (non_option_args_count < 1):
        usage.resource()
        sys.exit(1)

    dom = utils.get_cib_dom()
    if non_option_args_count == 1 and not update:
        argv.insert(0,argv[0]+"-master")

    master_id = argv.pop(0)

    if (update):
        master_found = False
        for master in dom.getElementsByTagName("master"):
            if master.getAttribute("id") == master_id:
                master_element = master
                master_found = True
                break
        if not master_found:
            utils.err("Unable to find multi-state resource with id %s" % master_id)
    else:
        rg_id = argv.pop(0)
        if utils.does_id_exist(dom, master_id):
            utils.err("%s already exists in the cib" % master_id)
        resources = dom.getElementsByTagName("resources")[0]
        rg_found = False
        for resource in (resources.getElementsByTagName("primitive") +
            resources.getElementsByTagName("group")):
            if resource.getAttribute("id") == rg_id:
                rg_found = True
                break
        if not rg_found:
            utils.err("Unable to find resource or group with id %s" % rg_id)
        master_element = dom.createElement("master")
        master_element.setAttribute("id", master_id)
        resource.parentNode.removeChild(resource)
        master_element.appendChild(resource)
        resources.appendChild(master_element)

    if len(argv) > 0:
        meta = None
        for child in master_element.childNodes:
            if child.nodeType != xml.dom.Node.ELEMENT_NODE:
                continue
            if child.tagName == "meta_attributes":
                meta = child
        if meta == None:
            meta = dom.createElement("meta_attributes")
            meta.setAttribute("id", master_id + "-meta_attributes")
            master_element.appendChild(meta)

        for arg in convert_args_to_tuples(argv):
            for nvpair in meta.getElementsByTagName("nvpair"):
                if nvpair.getAttribute("name") == arg[0]:
                    meta.removeChild(nvpair)
                    break
            if arg[1] == "":
                continue
            nvpair = dom.createElement("nvpair")
            nvpair.setAttribute("id", meta.getAttribute("id") + "-" + arg[0])
            nvpair.setAttribute("name", arg[0])
            nvpair.setAttribute("value", arg[1])
            meta.appendChild(nvpair)
        if len(meta.getElementsByTagName("nvpair")) == 0:
            master_element.removeChild(meta)
    utils.replace_cib_configuration(dom)
    if not update:
        constraint.constraint_resource_update(rg_id)

def resource_master_remove(argv):
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)

    dom = utils.get_cib_dom()
    master_id = argv.pop(0)

    master_found = False
# Check to see if there's a resource/group with the master_id if so, we remove the parent
    for rg in (dom.getElementsByTagName("primitive") + dom.getElementsByTagName("group")):
        if rg.getAttribute("id") == master_id and rg.parentNode.tagName == "master":
            master_id = rg.parentNode.getAttribute("id")

    resources_to_cleanup = []
    for master in dom.getElementsByTagName("master"):
        if master.getAttribute("id") == master_id:
            childNodes = master.getElementsByTagName("primitive")
            for child in childNodes:
                resources_to_cleanup.append(child.getAttribute("id"))
            master_found = True
            break

    if not master_found:
            utils.err("Unable to find multi-state resource with id %s" % master_id)

    constraints_element = dom.getElementsByTagName("constraints")
    if len(constraints_element) > 0:
        constraints_element = constraints_element[0]
        constraints = []
        for resource_id in resources_to_cleanup:
            constraints = constraints + constraint.find_constraints_containing(resource_id)
        for c in constraints:
            print "Removing Constraint - " + c
            constraint.constraint_rm([c], True, constraints_element)
    master.parentNode.removeChild(master)
    print "Removing Master - " + master_id
    utils.replace_cib_configuration(dom)

def resource_remove(resource_id, output = True):
    group = utils.get_cib_xpath('//group/primitive[@id="'+resource_id+'"]/..')
    num_resources_in_group = 0
    master = utils.get_cib_xpath('//master/primitive[@id="'+resource_id+'"]/..')
    clone = utils.get_cib_xpath('//clone/primitive[@id="'+resource_id+'"]/..')

    if not utils.does_exist('//resources/descendant::primitive[@id="'+resource_id+'"]'):
        if utils.does_exist('//resources/master[@id="'+resource_id+'"]'):
            return resource_master_remove([resource_id])

        utils.err("Resource does not exist.")

    if (group != ""):
        num_resources_in_group = len(parseString(group).documentElement.getElementsByTagName("primitive"))

    constraints = constraint.find_constraints_containing(resource_id)
    for c in constraints:
        if output == True:
            print "Removing Constraint - " + c
        constraint.constraint_rm([c])

    if (group == "" or num_resources_in_group > 1):
        if clone != "":
            args = ["cibadmin", "-o", "resources", "-D", "--xml-text", clone]
        elif master != "":
            args = ["cibadmin", "-o", "resources", "-D", "--xml-text", master]
        else:
            args = ["cibadmin", "-o", "resources", "-D", "--xpath", "//primitive[@id='"+resource_id+"']"]
        if output == True:
            print "Deleting Resource - " + resource_id
        output,retVal = utils.run(args)
        if retVal != 0:
            utils.err("unable to remove resource: %s, it may still be referenced in constraints." % resource_id)
    else:
        top_master = utils.get_cib_xpath('//master/group/primitive[@id="'+resource_id+'"]/../..')
        if top_master != "":
            to_remove = top_master
            msg = "and group and M/S"
        else:
            to_remove = group
            msg = "and group"
        args = ["cibadmin", "-o", "resources", "-D", "--xml-text", to_remove]
        if output == True:
            print "Deleting Resource ("+msg+") - " + resource_id
        cmdoutput,retVal = utils.run(args)
        if retVal != 0:
            if output == True:
                utils.err("Unable to remove resource '%s' (do constraints exist?)" % (resource_id))
            return False
    return True

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(group_name, resource_ids):
    resource_id = resource_ids[0]
    dom = utils.get_cib_dom()
    dom = dom.getElementsByTagName("configuration")[0]
    group_match = None

    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_name:
            group_match = group
            break

    if not group_match:
        utils.err("Group '%s' does not exist" % group_name)

    resources_to_move = []
    for resource_id in resource_ids:
        found_resource = False
        for resource in group_match.getElementsByTagName("primitive"):
            if resource.getAttribute("id") == resource_id:
                found_resource = True
                resources_to_move.append(resource)
                break
        if not found_resource:
            utils.err("Resource '%s' does not exist in group '%s'" % (resource_id, group_name))

    for resource in resources_to_move:
        parent = resource.parentNode
        resource.parentNode.removeChild(resource)
        parent.parentNode.appendChild(resource)

    if len(group_match.getElementsByTagName("primitive")) == 0:
        group_match.parentNode.removeChild(group_match)

    utils.replace_cib_configuration(dom)

    return True


def resource_group_add(group_name, resource_ids):
    dom = utils.get_cib_dom()
    top_element = dom.documentElement
    resources_element = top_element.getElementsByTagName("resources")[0]
    group_found = False

    for resource in top_element.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == group_name:
            utils.err("Error: %s is already a resource" % group_name)

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
        utils.err("No resources to add.")

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

def resource_show(argv, stonith=False):
    if "--all" in utils.pcs_options:
        root = utils.get_cib_etree()
        resources = root.find(".//resources")
        for child in resources:
            if stonith and "class" in child.attrib and child.attrib["class"] == "stonith":
                print_node(child,1)
            elif not stonith and \
                    ((not "class" in child.attrib) or (child.attrib["class"] != "stonith")):
                print_node(child,1)
        return

    if len(argv) == 0:    
        args = ["crm_resource","-L"]
        output,retval = utils.run(args)
        if retval != 0:
            utils.err("unable to get resource list from crm_resource\n"+output.rstrip())
        preg = re.compile(r'.*(stonith:.*)')
        for line in output.split('\n'):
            if line == "":
                continue
            if not preg.match(line) and not stonith:
                print line
            elif preg.match(line) and stonith:
                print line
        return

    preg = re.compile(r'.*xml:\n',re.DOTALL)
    root = utils.get_cib_etree()
    resources = root.find(".//resources")
    resource_found = False
    for arg in argv:
        for child in resources.findall(".//*"):
            if "id" in child.attrib and child.attrib["id"] == arg:
                print_node(child,1)
                resource_found = True
                break
        if not resource_found:
            utils.err("unable to find resource '"+arg+"'")
        resource_found = False

def resource_stop(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to stop")

    args = ["crm_resource", "-r", argv[0], "-m", "-p", "target-role", "-v", "Stopped"]
    output, retval = utils.run(args)
    if retval != 0:
        print output,
        return False
    else:
        return True

def resource_start(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to start")

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
        if not utils.does_exist("(//primitive|//group|//master|//clone)[@id='"+resource+"']"):
            utils.err("%s doesn't exist." % resource)
        exists = utils.does_exist("(//primitive|//group|//master|//clone)[@id='"+resource+"']/meta_attributes/nvpair[@name='is-managed']")
        if set_managed and not exists:
            utils.err("%s is already managed" % resource)
        elif not set_managed and exists:
            utils.err("%s is already unmanaged" % resource)

    for resource in argv:
        if not set_managed:
            (output, retval) =  utils.set_unmanaged(resource)
            if retval != 0:
                utils.err("error attempting to unmanage resource: %s" % output)
        else:
            xpath = "(//primitive|//group)[@id='"+resource+"']/meta_attributes/nvpair[@name='is-managed']" 
            my_xml = utils.get_cib_xpath(xpath)
            utils.remove_from_cib(my_xml)

def resource_failcount(argv):
    if len(argv) < 2:
        usage.resource()
        sys.exit(1)

    resource_command = argv.pop(0)
    resource = argv.pop(0)
    if resource_command != "show" and resource_command != "reset":
        usage.resource()
        sys.exit(1)

    if len(argv) > 0:
        node = argv.pop(0) 
        all_nodes = False
    else:
        all_nodes = True

    dom = utils.get_cib_dom()
    output_dict = {}
    trans_attrs = dom.getElementsByTagName("transient_attributes")
    fail_counts_removed = 0
    for ta in trans_attrs:
        ta_node = ta.parentNode.getAttribute("uname")
        if not all_nodes and ta_node != node:
            continue
        for nvp in ta.getElementsByTagName("nvpair"):
            if nvp.getAttribute("name") == ("fail-count-" + resource):
                if resource_command == "reset":
                    (output, retval) = utils.run(["crm_attribute", "-N",
                        ta_node, "-n", nvp.getAttribute("name"), "-t",
                        "status", "-D"])
                    if retval != 0:
                        utils.err("Unable to remove failcounts from %s on %s\n" % (resource,ta_node) + output)
                    fail_counts_removed = fail_counts_removed + 1
                else:
                    output_dict[ta_node] = " " + ta_node + ": " + nvp.getAttribute("value") + "\n"
                break

    if resource_command == "reset":
        if fail_counts_removed == 0:
            print "No failcounts needed resetting"
    if resource_command == "show":
        output = ""
        for key in sorted(output_dict.iterkeys()):
            output += output_dict[key]


        if output == "":
            if all_nodes:
                print "No failcounts for %s" % resource
            else:
                print "No failcounts for %s on %s" % (resource,node)
        else:
            if all_nodes:
                print "Failcounts for %s" % resource
            else:
                print "Failcounts for %s on %s" % (resource,node)
            print output,


def show_defaults(def_type):
    dom = utils.get_cib_dom()
    defs = dom.getElementsByTagName(def_type)
    if len(defs) > 0:
        defs = defs[0]
    else:
        print "No defaults set"
        return

    foundDefault = False
    for d in defs.getElementsByTagName("nvpair"):
        print d.getAttribute("name") + ": " + d.getAttribute("value")
        foundDefault = True

    if not foundDefault:
        print "No defaults set"

def set_default(def_type, argv):
    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            print "Invalid Property: " + arg
            continue
        utils.setAttribute(def_type, args[0], args[1])

def print_node(node, tab = 0):
    spaces = " " * tab
    if node.tag == "group":
        print spaces + "Group: " + node.attrib["id"] + get_attrs(node,' (',')')
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
    if node.tag == "clone":
        print spaces + "Clone: " + node.attrib["id"] + get_attrs(node,' (',')')
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
    if node.tag == "primitive":
        print spaces + "Resource: " + node.attrib["id"] + get_attrs(node,' (',')')
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
    if node.tag == "master":
        print spaces + "Master: " + node.attrib["id"] + get_attrs(node, ' (', ')')
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)

def print_instance_vars_string(node, spaces):
    output = ""
    ivars = node.findall("instance_attributes/nvpair")
    for ivar in ivars:
        name = ivar.attrib["name"]
        value = ivar.attrib["value"]
        if value.find(" ") != -1:
            value = '"' + value + '"'
        output += name + "=" + value + " "
    if output != "":
        print spaces + " Attributes: " + output

def print_meta_vars_string(node, spaces):
    output = ""
    mvars = node.findall("meta_attributes/nvpair")
    for mvar in mvars:
        output += mvar.attrib["name"] + "=" + mvar.attrib["value"] + " "
    if output != "":
        print spaces + " Meta Attrs: " + output

def print_operations(node, spaces):
    indent = len(spaces) + len(" Operations: ")
    output = ""
    ops = node.findall("operations/op")
    first = True
    for op in ops:
        if not first:
            output += ' ' * indent
        else:
            first = False
        output += op.attrib["name"] + " "
        for attr,val in op.attrib.items():
            if attr in ["id","name"] :
                continue
            output += attr + "=" + val + " "
        output += "(" + op.attrib["id"] + ")"
        output += "\n"

    output = output.rstrip()
    if output != "":
        print spaces + " Operations: " + output

def get_attrs(node, prepend_string = "", append_string = ""):
    output = ""
    for attr,val in sorted(node.attrib.items()):
        if attr in ["id"]:
            continue
        output += attr + "=" + val + " "
    if output != "":
        return prepend_string + output.rstrip() + append_string
    else:
        return output.rstrip()

def resource_cleanup(res_id):
    (output, retval) = utils.run(["crm_resource", "-C", "-r", res_id])
    if retval != 0:
        utils.err("Unable to cleanup resource: %s" % res_id + output)
    else:
        print "Resource: %s successfully cleaned up" % res_id
