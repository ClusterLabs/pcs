import sys
import os
import time
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import usage
import utils
import re
import textwrap
import xml.etree.ElementTree as ET
import tempfile
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
        ra_values, op_values, meta_values, clone_opts = parse_resource_options(
            argv, with_clone=True
        )
        resource_create(res_id, res_type, ra_values, op_values, meta_values, clone_opts)
    elif (sub_cmd == "move"):
        resource_move(argv)
    elif (sub_cmd == "ban"):
        resource_move(argv,False,True)
    elif (sub_cmd == "clear"):
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
        utils.err("add_operation has been deprecated, please use 'op add'")
    elif (sub_cmd == "remove_operation"):
        utils.err("remove_operation has been deprecated, please use 'op remove'")
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
    elif (sub_cmd == "ungroup"):
        resource_group(["remove"] + argv)
    elif (sub_cmd == "clone"):
        resource_clone(argv)
    elif (sub_cmd == "unclone"):
        resource_clone_master_remove(argv)
    elif (sub_cmd == "master"):
        resource_master(argv)
    elif (sub_cmd == "enable"):
        resource_enable(argv)
    elif (sub_cmd == "disable"):
        resource_disable(argv)
    elif (sub_cmd == "restart"):
        resource_restart(argv)
    elif (sub_cmd == "debug-start"):
        resource_force_start(argv)
    elif (sub_cmd == "manage"):
        resource_manage(argv, True)
    elif (sub_cmd == "unmanage"):
        resource_manage(argv, False)
    elif (sub_cmd == "failcount"):
        resource_failcount(argv)
    elif (sub_cmd == "op"):
        if len(argv) < 1:
            usage.resource(["op"])
            sys.exit(1)
        op_subcmd = argv.pop(0)
        if op_subcmd == "defaults":
            if len(argv) == 0:
                show_defaults("op_defaults")
            else:
                set_default("op_defaults", argv)
        elif op_subcmd == "add":
            if len(argv) == 0:
                usage.resource(["op"])
                sys.exit(1)
            else:
                res_id = argv.pop(0)
                utils.replace_cib_configuration(
                    resource_operation_add(utils.get_cib_dom(), res_id, argv)
                )
        elif op_subcmd in ["remove","delete"]:
            if len(argv) == 0:
                usage.resource(["op"])
                sys.exit(1)
            else:
                res_id = argv.pop(0)
                resource_operation_remove(res_id, argv)
    elif (sub_cmd == "defaults"):
        if len(argv) == 0:
            show_defaults("rsc_defaults")
        else:
            set_default("rsc_defaults", argv)
    elif (sub_cmd == "cleanup"):
        if len(argv) == 0:
            resource_cleanup_all()
        else:
            res_id = argv.pop(0)
            resource_cleanup(res_id)
    elif (sub_cmd == "history"):
        resource_history(argv)
    else:
        usage.resource()
        sys.exit(1)

def parse_resource_options(argv, with_clone=False):
    ra_values = []
    op_values = []
    meta_values = []
    clone_opts = []
    op_args = False
    meta_args = False
    clone_args = False
    for arg in argv:
        if arg == "op":
            op_args = True
            meta_args = False
            op_values.append([])
        elif arg == "meta":
            meta_args = True
            op_args = False
        elif with_clone and arg == "clone":
            utils.pcs_options["--clone"] = ""
            clone_args = True
            op_args = False
            meta_args = False
        else:
            if clone_args:
                if "=" in arg:
                    clone_opts.append(arg)
            elif op_args:
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
    if with_clone:
        return ra_values, op_values, meta_values, clone_opts
    return ra_values, op_values, meta_values

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

            if "--nodesc" in utils.pcs_options:
                ret += full_res_name + "\n"
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
    if utils.is_systemctl():
        agents, retval = utils.run(["systemctl", "list-unit-files", "--full"])
        agents = agents.split("\n")

    for agent in agents:
        match = re.search(r'^([\S]*)\.service',agent)
        if match:
            ret += "systemd:" + match.group(1) + "\n"

    if not ret:
        utils.err(
            "No resource agents available. "
            "Do you have resource agents installed?"
        )
    if filter_string != "":
        rlines = ret.split("\n")
        found = False
        for rline in rlines:
            if rline.lower().find(filter_string.lower()) != -1:
                print rline
                found = True
        if not found:
            utils.err("No resource agents matching the filter.")
    else:
        print ret,


def resource_list_options(resource):
    found_resource = False
    resource = get_full_ra_type(resource,True)
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
            short_desc = ""
            long_desc = ""
            dom = parseString(metadata)
            long_descs = dom.documentElement.getElementsByTagName("longdesc")
            for ld in long_descs:
                if ld.parentNode.tagName == "resource-agent" and ld.firstChild:
                    long_desc = ld.firstChild.data.strip()
                    break

            short_descs = dom.documentElement.getElementsByTagName("shortdesc")
            for sd in short_descs:
                if sd.parentNode.tagName == "resource-agent" and sd.firstChild:
                    short_desc = sd.firstChild.data.strip()
                    break
            
            title_1 = "ocf:%s:%s" % (provider, resource)
            if short_desc:
                title_1 += " - " + format_desc(len(title_1 + " - "), short_desc)
            print title_1
            print 
            if long_desc:
                print long_desc
                print

            params = dom.documentElement.getElementsByTagName("parameter")
            if len(params) > 0:
                print "Resource options:"
            for param in params:
                name = param.getAttribute("name")
                if param.getAttribute("required") == "1":
                    name += " (required)"
                desc = ""
                longdesc_els = param.getElementsByTagName("longdesc")
                if longdesc_els and longdesc_els[0].firstChild:
                    desc = longdesc_els[0].firstChild.nodeValue.strip().replace("\n", "")
                if not desc:
                    desc = "No description available"
                indent = name.__len__() + 4
                desc = format_desc(indent, desc)
                print "  " + name + ": " + desc
        except xml.parsers.expat.ExpatError as e:
            utils.err("Unable to parse xml for '%s': %s" % (resource, e))

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
def resource_create(ra_id, ra_type, ra_values, op_values, meta_values=[], clone_opts=[]):
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        if "--disabled" in utils.pcs_options:
            utils.err("Cannot use '--wait' together with '--disabled'")
        if "target-role=Stopped" in meta_values:
            utils.err("Cannot use '--wait' together with 'target-role=Stopped'")

    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait = True
        if utils.pcs_options["--wait"] is not None:
            wait_timeout = utils.pcs_options["--wait"]
            if not wait_timeout.isdigit():
                utils.err(
                    "%s is not a valid number of seconds to wait"
                    % wait_timeout
                )

    ra_id_valid, ra_id_error = utils.validate_xml_id(ra_id, 'resource name')
    if not ra_id_valid:
        utils.err(ra_id_error)

    dom = utils.get_cib_dom()

    # If we're not using --force, try to change the case of ra_type to match any
    # installed resources
    if not "--force" in utils.pcs_options:
        new_ra_type = utils.is_valid_resource(ra_type, True)
        if new_ra_type != True and new_ra_type != False:
            ra_type = new_ra_type

    if not utils.is_valid_resource(ra_type) and not ("--force" in utils.pcs_options):
        utils.err ("Unable to create resource '%s', it is not installed on this system (use --force to override)" % ra_type)

    if utils.does_exist('//resources/descendant::primitive[@id="'+ra_id+'"]'):
        utils.err("unable to create resource/fence device '%s', '%s' already exists on this system" % (ra_id,ra_id))


    for op_val in op_values:
        if len(op_val) < 2:
            utils.err(
                "When using 'op' you must specify an operation name"
                + " and at least one option"
            )
        if '=' in op_val[0]:
            utils.err(
                "When using 'op' you must specify an operation name after 'op'"
            )

    # If the user specifies an operation value and we find a similar one in
    # the default operations we remove if from the default operations
    op_values_agent = []
    if "--no-default-ops" not in utils.pcs_options: 
        default_op_values = utils.get_default_op_values(ra_type)
        for def_op in default_op_values:
            match = False
            for op in op_values:
                if op[0] != def_op[0]:
                    continue
                match = True
            if match == False:
                op_values_agent.append(def_op)

    # find duplicate operations defined in agent and make them unique
    action_intervals = dict()
    for op in op_values_agent:
        if len(op) < 1:
            continue
        op_action = op[0]
        if op_action not in action_intervals:
            action_intervals[op_action] = set()
        for key, op_setting in enumerate(op):
            if key == 0:
                continue
            match = re.match("interval=(.+)", op_setting)
            if match:
                interval = utils.get_timeout_seconds(match.group(1))
                if interval is not None:
                    if interval in action_intervals[op_action]:
                        old_interval = interval
                        while interval in action_intervals[op_action]:
                            interval += 1
                        op[key] = "interval=%s" % interval
                        print (
                            ("Warning: changing a %s operation interval from %s"
                                + " to %s to make the operation unique")
                            % (op_action, old_interval, interval)
                        )
                    action_intervals[op_action].add(interval)

    is_monitor_present = False
    for op in op_values_agent + op_values:
        if len(op) > 0:
            if op[0] == "monitor":
                is_monitor_present = True
                break
    if not is_monitor_present:
        op_values.append(['monitor'])

    op_values_all = op_values_agent + op_values

    if "--disabled" in utils.pcs_options:
        meta_values = [
            meta for meta in meta_values if not meta.startswith("target-role=")
        ]
        meta_values.append("target-role=Stopped")

    if wait and wait_timeout is None:
        for op in op_values_all:
            if op[0] == "start":
                for op_setting in op[1:]:
                    match = re.match("timeout=(.+)", op_setting)
                    if match:
                        wait_timeout = utils.get_timeout_seconds(match.group(1))
        if wait_timeout is None:
            wait_timeout = utils.get_default_op_timeout()

# If it's a master all meta values go to the master
    master_meta_values = []
    if "--master" in utils.pcs_options:
        master_meta_values = meta_values
        meta_values = []

    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = get_full_ra_type(ra_type)
    primitive_values.insert(0,("id",ra_id))
    meta_attributes = convert_args_to_meta_attrs(meta_values, ra_id)
    if not "--force" in utils.pcs_options and utils.does_resource_have_options(ra_type):
        params = convert_args_to_tuples(ra_values)
        bad_opts, missing_req_opts = utils.validInstanceAttributes(ra_id, params , get_full_ra_type(ra_type, True))
        if len(bad_opts) != 0:
            utils.err ("resource option(s): '%s', are not recognized for resource type: '%s' (use --force to override)" \
                    % (", ".join(bad_opts), get_full_ra_type(ra_type, True)))
        if len(missing_req_opts) != 0:
            utils.err(
                "missing required option(s): '%s' for resource type: %s"
                    " (use --force to override)"
                % (", ".join(missing_req_opts), get_full_ra_type(ra_type, True))
            )

    resource_elem = create_xml_element("primitive", primitive_values, instance_attributes + meta_attributes)
    dom.getElementsByTagName("resources")[0].appendChild(resource_elem)
    # Do not validate default operations defined by a resource agent
    # User did not entered them so we will not confuse him/her with their errors
    for op in op_values_agent:
        dom = resource_operation_add(dom, ra_id, op, validate=False)
    for op in op_values:
        dom = resource_operation_add(dom, ra_id, op, validate=True)

    expected_instances = 1
    if "--clone" in utils.pcs_options or len(clone_opts) > 0:
        dom = resource_clone_create(dom, [ra_id] + clone_opts)
        expected_instances = utils.count_expected_resource_instances(
            utils.dom_get_clone(dom, ra_id + "-clone"),
            len(utils.getNodesFromPacemaker())
        )
        if "--group" in utils.pcs_options:
            print "Warning: --group ignored when creating a clone"
        if "--master" in utils.pcs_options:
            print "Warning: --master ignored when creating a clone"
    elif "--master" in utils.pcs_options:
        dom = resource_master_create(dom, [ra_id] + master_meta_values)
        expected_instances = utils.count_expected_resource_instances(
            utils.dom_get_master(dom, ra_id + "-master"),
            len(utils.getNodesFromPacemaker())
        )
        if "--group" in utils.pcs_options:
            print "Warning: --group ignored when creating a master"
    elif "--group" in utils.pcs_options:
        groupname = utils.pcs_options["--group"]
        dom = resource_group_add(dom, groupname, [ra_id])

    utils.replace_cib_configuration(dom)

    if wait:
        running, message = utils.is_resource_started(
            ra_id, int(wait_timeout), count=expected_instances
        )
        if running:
            print message
        else:
            utils.err(
                "unable to start: '%s', please check logs for failure "
                    "information\n%s"
                % (ra_id, message)
            )

def resource_move(argv,clear=False,ban=False):
    other_options = []
    if len(argv) == 0:
        utils.err ("must specify resource to move/unmove")

    resource_id = argv.pop(0)

    if (clear and len(argv) > 1) or len(argv) > 2:
        usage.resource()
        sys.exit(1)

    dest_node = None
    lifetime = None
    while argv:
        arg = argv.pop(0)
        if arg.startswith("lifetime="):
            if lifetime:
                usage.resource()
                sys.exit(1)
            lifetime = arg.split("=")[1]
            if lifetime and lifetime[0].isdigit():
                lifetime = "P" + lifetime
        elif not dest_node:
            dest_node = arg
        else:
            usage.resource()
            sys.exit(1)

    if clear and lifetime:
        usage.resource()
        sys.exit(1)

    dom = utils.get_cib_dom()
    if (
        not utils.dom_get_resource(dom, resource_id)
        and
        not utils.dom_get_group(dom, resource_id)
        and
        not utils.dom_get_master(dom, resource_id)
        and
        not utils.dom_get_clone(dom, resource_id)
    ):
        utils.err("%s is not a valid resource" % resource_id)

    if (
        not clear and not ban
        and
        (
            utils.dom_get_clone(dom, resource_id)
            or
            utils.dom_get_resource_clone(dom, resource_id)
            or
            utils.dom_get_group_clone(dom, resource_id)
        )
    ):
        utils.err("cannot move cloned resources")

    if (
        not clear and not ban
        and
        "--master" not in utils.pcs_options
        and
        (
            utils.dom_get_resource_masterslave(dom, resource_id)
            or
            utils.dom_get_group_masterslave(dom, resource_id)
        )
    ):
        master = utils.dom_get_resource_clone_ms_parent(dom, resource_id)
        utils.err(
            "to move Master/Slave resources you must use --master "
                "and the master id (%s)"
            % master.getAttribute("id")
        )

    if (
        "--master" in utils.pcs_options
        and
        not utils.dom_get_master(dom, resource_id)
    ):
        master_clone = utils.dom_get_resource_clone_ms_parent(dom, resource_id)
        if master_clone and master_clone.tagName == "master":
            utils.err(
                "when specifying --master you must use the master id (%s)"
                % master_clone.getAttribute("id")
            )
        else:
            utils.err("when specifying --master you must use the master id")

    wait = False
    if "--wait" in utils.pcs_options and not clear:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        if not utils.is_resource_started(resource_id, 0)[0]:
            print "Warning: Cannot use '--wait' on non-running resources"
        else:
            wait = True
    if wait:
        timeout = utils.pcs_options["--wait"]
        if timeout is None:
            timeout = (
                utils.get_resource_op_timeout(dom, resource_id, "stop")
                +
                utils.get_resource_op_timeout(dom, resource_id, "start")
            )
        elif not timeout.isdigit():
            utils.err("You must specify the number of seconds to wait")
        allowed_nodes = set()
        banned_nodes = set()
        if dest_node and ban:
            banned_nodes = set([dest_node])
        elif dest_node:
            allowed_nodes = set([dest_node])
        else:
            state = utils.getClusterState()
            running_on = utils.resource_running_on(resource_id)
            banned_nodes = set(
                running_on["nodes_master"] + running_on["nodes_started"]
            )

    if "--wait" in utils.pcs_options and clear:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        wait = True
        timeout = utils.pcs_options["--wait"]
        if timeout and not timeout.isdigit():
            utils.err("You must specify the number of seconds to wait")
        try:
            tmp_cib = tempfile.NamedTemporaryFile("w+b", -1, ".pcs")
            tmp_cib.write(utils.get_cib_dom().toxml())
            tmp_cib.seek(0)
        except EnvironmentError as e:
            utils.err("Unable to determine what to wait for:\n%s" % e)
        utils.usefile = True
        utils.filename = tmp_cib.name

    if "--master" in utils.pcs_options:
        other_options.append("--master")
    if lifetime is not None:
        other_options.append("--lifetime=%s" % lifetime)
    if clear:
        if dest_node:
            output,ret = utils.run(["crm_resource", "--resource", resource_id, "--clear", "--host", dest_node] + other_options)
        else:
            output,ret = utils.run(["crm_resource", "--resource", resource_id, "--clear"] + other_options)
    else:
        if dest_node == None:
            if ban:
                output,ret = utils.run(["crm_resource", "--resource", resource_id, "--ban"] + other_options)
            else:
                output,ret = utils.run(["crm_resource", "--resource", resource_id, "--move"] + other_options)
        else:
            if ban:
                output,ret = utils.run(["crm_resource", "--resource", resource_id, "--ban", "--node", dest_node] + other_options)
            else:
                output,ret = utils.run(["crm_resource", "--resource", resource_id, "--move", "--node", dest_node] + other_options)
    if ret != 0:
        if "Resource '"+resource_id+"' not moved: active in 0 locations." in output:
            utils.err("You must specify a node when moving/banning a stopped resource")
        utils.err ("error moving/banning/clearing resource\n" + output)

    if wait and not clear:
        success, message = utils.is_resource_started(
            resource_id, int(timeout), allowed_nodes=allowed_nodes,
            banned_nodes=banned_nodes
        )
        if success:
            print message
        else:
            utils.err("Unable to start '%s'\n%s" % (resource_id, message))

    if wait and clear:
        utils.usefile = False
        utils.filename = ""
        try:
            tmp_cib.seek(0)
            tmp_cib_dom = parseString(tmp_cib.read())
        except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
            utils.err("Unable to determine what to wait for:\n%s" % e)
        except xml.etree.ElementTree.ParseError as e:
            utils.err("Unable to determine what to wait for:\n%s" % e)
        output, transitions_dom, new_cib_dom = utils.simulate_cib(tmp_cib_dom)
        op_list = utils.get_operations_from_transitions(transitions_dom)
        my_op_list = [op for op in op_list if op[0] == resource_id]

        utils.replace_cib_configuration(tmp_cib_dom)

        if my_op_list:
            utils.wait_for_primitive_ops_to_process(my_op_list, timeout)
        else:
            print utils.resource_running_on(resource_id)["message"]

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
    ra_values, op_values, meta_values = parse_resource_options(args)

    wait = False
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        wait = True

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
                    return resource_update_clone_master(
                        dom, clone, "clone", a.getAttribute("id"), args, wait
                    )

        master = None
        for m in dom.getElementsByTagName("master"):
            if m.getAttribute("id") == res_id:
                master = r 
                break

        if master:
            return resource_update_clone_master(
                dom, master, "master", res_id, args, wait
            )

        utils.err ("Unable to find resource: %s" % res_id)

    if wait:
        node_count = len(utils.getNodesFromPacemaker())
        status_old = utils.get_resource_status_for_wait(
            dom, resource, node_count
        )

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
        bad_opts, missing_req_opts = utils.validInstanceAttributes(res_id, params, resource_type)
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
        if len(element) < 1:
            continue

        op_name = element[0]
        if op_name.find('=') != -1:
            utils.err("%s does not appear to be a valid operation action" % op_name)

        if len(element) < 2:
            continue

        op_role = ""
        op_vars = convert_args_to_tuples(element[1:])

        for k,v in op_vars:
            if k == "role":
                op_role = v
                break

        updating_op = None
        updating_op_before = None
        for existing_op in operations.getElementsByTagName("op"):
            if updating_op:
                updating_op_before = existing_op
                break
            existing_op_name = existing_op.getAttribute("name")
            existing_op_role = existing_op.getAttribute("role")
            if existing_op_role == op_role and existing_op_name == op_name:
                updating_op = existing_op
                continue

        if updating_op:
            updating_op.parentNode.removeChild(updating_op)
        dom = resource_operation_add(
            dom, res_id, element, before_op=updating_op_before
        )

    if len(instance_attributes.getElementsByTagName("nvpair")) == 0:
        instance_attributes.parentNode.removeChild(instance_attributes)

    if wait:
        status_new = utils.get_resource_status_for_wait(
            dom, resource, node_count
        )
        wait_for_start, wait_for_stop = utils.get_resource_wait_decision(
            status_old, status_new
        )
        if wait_for_start or wait_for_stop:
            timeout = utils.pcs_options["--wait"]
            if timeout is None:
                timeout = utils.get_resource_op_timeout(
                    dom, res_id, "start" if wait_for_start else "stop"
                )
            elif not timeout.isdigit():
                utils.err("You must specify the number of seconds to wait")
        else:
            timeout = 0

    utils.replace_cib_configuration(dom)

    if wait:
        if wait_for_start or wait_for_stop:
            success, message = utils.is_resource_started(
                res_id, int(timeout), wait_for_stop,
                count=status_new["instances"]
            )
            if success:
                print message
            else:
                utils.err("Unable to start '%s'\n%s" % (res_id, message))
        else:
            print utils.resource_running_on(res_id)["message"]

def resource_update_clone_master(dom, clone, clone_type, res_id, args, wait):
    if wait:
        node_count = len(utils.getNodesFromPacemaker())
        status_old = utils.get_resource_status_for_wait(dom, clone, node_count)

    if clone_type == "clone":
        dom = resource_clone_create(dom, [res_id] + args, True)
    elif clone_type == "master":
        dom = resource_master_create(dom, [res_id] + args, True)

    if wait:
        status_new = utils.get_resource_status_for_wait(dom, clone, node_count)
        wait_for_start, wait_for_stop = utils.get_resource_wait_decision(
            status_old, status_new
        )
        if wait_for_start or wait_for_stop:
            timeout = utils.pcs_options["--wait"]
            if timeout is None:
                timeout = utils.get_resource_op_timeout(
                    dom, res_id, "start" if wait_for_start else "stop"
                )
            elif not timeout.isdigit():
                utils.err("You must specify the number of seconds to wait")
        else:
            timeout = 0

    dom = utils.replace_cib_configuration(dom)

    if wait:
        if wait_for_start or wait_for_stop:
            success, message = utils.is_resource_started(
                clone.getAttribute("id"), int(timeout), wait_for_stop,
                count=status_new["instances"]
            )
            if success:
                print message
            else:
                utils.err(
                    "Unable to start '%s'\n%s"
                    % (clone.getAttribute("id"), message)
                )
        else:
            print utils.resource_running_on(clone.getAttribute("id"))["message"]

    return dom

def resource_operation_add(dom, res_id, argv, validate=True, before_op=None):
    if len(argv) < 1:
        usage.resource(["op"])
        sys.exit(1)

    res_el = utils.dom_get_resource(dom, res_id)
    if not res_el:
        utils.err ("Unable to find resource: %s" % res_id)

    op_name = argv.pop(0)
    op_properties = convert_args_to_tuples(argv)

    if validate:
        if "=" in op_name:
            utils.err(
                "%s does not appear to be a valid operation action" % op_name
            )
    if validate and "--force" not in utils.pcs_options:
        valid_attrs = ["id", "name", "interval", "description", "start-delay",
            "interval-origin", "timeout", "enabled", "record-pending", "role",
            "requires", "on-fail", "OCF_CHECK_LEVEL"]
        valid_roles = ["Stopped", "Started", "Slave", "Master"]
        for key, value in op_properties:
            if key not in valid_attrs:
                utils.err(
                    "%s is not a valid op option (use --force to override)"
                    % key
                )
            if key == "role":
                if value not in valid_roles:
                    utils.err(
                        "role must be: %s or %s (use --force to override)"
                        % (", ".join(valid_roles[:-1]), valid_roles[-1])
                    )

    interval = None
    for key, val in op_properties:
        if key == "interval":
            interval = val
            break
    if not interval:
        interval = "60s" if op_name == "monitor" else "0s"
        op_properties.append(("interval", interval))

    op_properties.sort(key=lambda a:a[0])
    op_properties.insert(0, ("name", op_name))

    op_id = "%s-%s-interval-%s" % (res_id, op_name, interval)
    op_id = utils.find_unique_id(dom, op_id)
    op_el = dom.createElement("op")
    op_el.setAttribute("id", op_id)
    for key, val in op_properties:
        if key == "OCF_CHECK_LEVEL":
            attrib_el = dom.createElement("instance_attributes")
            attrib_el.setAttribute(
                "id", utils.find_unique_id(dom, "params-" + op_id)
            )
            op_el.appendChild(attrib_el)
            nvpair_el = dom.createElement("nvpair")
            nvpair_el.setAttribute("name", key)
            nvpair_el.setAttribute("value", val)
            nvpair_el.setAttribute(
                "id", utils.find_unique_id(dom, "-".join((op_id, key, val)))
            )
            attrib_el.appendChild(nvpair_el)
        else:
            op_el.setAttribute(key, val)

    operations = res_el.getElementsByTagName("operations")
    if len(operations) == 0:
        operations = dom.createElement("operations")
        res_el.appendChild(operations)
    else:
        operations = operations[0]
        if validate:
            duplicate_op = utils.operation_exists(operations, op_el)
            if duplicate_op:
                utils.err(
                    "operation %s with interval %ss already specified for %s:\n%s"
                    % (
                        op_el.getAttribute("name"),
                        utils.get_timeout_seconds(
                            op_el.getAttribute("interval"), True
                        ),
                        res_id,
                        operation_to_string(duplicate_op)
                    )
                )

    operations.insertBefore(op_el, before_op)
    return dom

def resource_operation_remove(res_id, argv):
# if no args, then we're removing an operation id
    dom = utils.get_cib_dom()
    if len(argv) == 0:
        for operation in dom.getElementsByTagName("op"):
            if operation.getAttribute("id") == res_id:
                parent = operation.parentNode
                parent.removeChild(operation)
                if len(parent.getElementsByTagName("op")) == 0:
                    parent.parentNode.removeChild(parent)
                utils.replace_cib_configuration(dom)
                return
        utils.err("unable to find operation id: %s" % res_id)

    original_argv = " ".join(argv)

    op_name = argv.pop(0)
    resource_found = False

    for resource in dom.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == res_id:
            resource_found = True
            break

    if not resource_found:
        utils.err("Unable to find resource: %s" % res_id)

    remove_all = False
    if len(argv) == 0:
        remove_all = True

    op_properties = convert_args_to_tuples(argv)
    op_properties.append(('name', op_name))
    found_match = False
    for op in resource.getElementsByTagName("op"):
        temp_properties = []
        for attrName in op.attributes.keys():
            if attrName == "id":
                continue
            temp_properties.append((attrName,op.attributes.get(attrName).nodeValue))

        if remove_all and op.attributes["name"].value == op_name:
            found_match = True
            parent = op.parentNode
            parent.removeChild(op)
            if len(parent.getElementsByTagName("op")) == 0:
                parent.parentNode.removeChild(parent)
        elif len(set(op_properties) ^ set(temp_properties)) == 0:
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

    wait = False
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        wait = True
        node_count = len(utils.getNodesFromPacemaker())
        status_old = utils.get_resource_status_for_wait(dom, elem, node_count)

    update_meta_attributes(
        meta_attributes,
        convert_args_to_tuples(argv),
        res_id + "-meta_attributes-"
    )

    if wait:
        status_new = utils.get_resource_status_for_wait(dom, elem, node_count)
        wait_for_start, wait_for_stop = utils.get_resource_wait_decision(
            status_old, status_new
        )
        if wait_for_start or wait_for_stop:
            timeout = utils.pcs_options["--wait"]
            if timeout is None:
                timeout = utils.get_resource_op_timeout(
                    dom, res_id, "start" if wait_for_start else "stop"
                )
            elif not timeout.isdigit():
                utils.err("You must specify the number of seconds to wait")
        else:
            timeout = 0

    utils.replace_cib_configuration(dom)

    if wait:
        if wait_for_start or wait_for_stop:
            success, message = utils.is_resource_started(
                res_id, int(timeout), wait_for_stop, count=status_new["instances"]
            )
            if success:
                print message
            else:
                utils.err("Unable to start '%s'\n%s" % (res_id, message))
        else:
            print utils.resource_running_on(res_id)["message"]

def update_meta_attributes(meta_attributes, meta_attrs, id_prefix):
    dom = meta_attributes.ownerDocument
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
            ma.setAttribute("id", id_prefix + key)
            ma.setAttribute("name", key)
            ma.setAttribute("value", val)
            meta_attributes.appendChild(ma)
    return meta_attributes

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
        if ra_val.count("=") != 0:
            split_val = ra_val.split("=", 1)
            ret.append((split_val[0],split_val[1]))
    return ret

# Passed a resource type (ex. ocf:heartbeat:IPaddr2 or IPaddr2) and returns
# a list of tuples mapping the types to xml attributes
def get_full_ra_type(ra_type, return_string = False):
    if (ra_type.count(":") == 0):
        if os.path.isfile("/usr/lib/ocf/resource.d/heartbeat/%s" % ra_type):
            ra_type = "ocf:heartbeat:" + ra_type
        elif os.path.isfile("/usr/lib/ocf/resource.d/pacemaker/%s" % ra_type):
            ra_type = "ocf:pacemaker:" + ra_type
        else:
            ra_type = "ocf:heartbeat:" + ra_type

    
    if return_string:
        return ra_type

    ra_def = ra_type.split(":")
    # If len = 2 then we're creating a fence device
    if len(ra_def) == 2:
        return([("class",ra_def[0]),("type",ra_def[1])])
    else:
        return([("class",ra_def[0]),("type",ra_def[2]),("provider",ra_def[1])])


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
        usage.resource("group")
        sys.exit(1)

    group_cmd = argv.pop(0)
    if (group_cmd == "add"):
        if (len(argv) < 2):
            usage.resource("group")
            sys.exit(1)
        group_name = argv.pop(0)
        resource_ids = argv
        cib = resource_group_add(utils.get_cib_dom(), group_name, resource_ids)

        wait = False
        if "--wait" in utils.pcs_options:
            if utils.usefile:
                utils.err("Cannot use '-f' together with '--wait'")
            wait = True
            timeout = utils.pcs_options["--wait"]
            if timeout and not timeout.isdigit():
                utils.err("You must specify the number of seconds to wait")
            output, transitions_dom, new_cib_dom = utils.simulate_cib(cib)
            op_list = utils.get_operations_from_transitions(transitions_dom)
            my_op_list = [op for op in op_list if op[0] in resource_ids]

        utils.replace_cib_configuration(cib)

        if wait:
            if my_op_list:
                utils.wait_for_primitive_ops_to_process(my_op_list, timeout)
            print utils.resource_running_on(group_name)["message"]

    elif (group_cmd == "list"):
        resource_group_list(argv)
    elif (group_cmd in ["remove","delete"]):
        if (len(argv) < 1):
            usage.resource("group")
            sys.exit(1)
        group_name = argv.pop(0)
        resource_ids = argv

        cib_dom, removed_resources = resource_group_rm(
            utils.get_cib_dom(), group_name, resource_ids
        )

        wait = False
        if "--wait" in utils.pcs_options:
            if utils.usefile:
                utils.err("Cannot use '-f' together with '--wait'")
            wait = True
            timeout = utils.pcs_options["--wait"]
            if timeout and not timeout.isdigit():
                utils.err("You must specify the number of seconds to wait")
            output, transitions_dom, new_cib_dom = utils.simulate_cib(cib_dom)
            op_list = utils.get_operations_from_transitions(transitions_dom)
            my_op_list = [op for op in op_list if op[0] in removed_resources]

        utils.replace_cib_configuration(cib_dom)

        if wait:
            if my_op_list:
                utils.wait_for_primitive_ops_to_process(my_op_list, timeout)
    else:
        usage.resource()
        sys.exit(1)

def resource_clone(argv):
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)

    res = argv[0]
    cib_dom = utils.get_cib_dom()

    wait = False
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        if not utils.is_resource_started(res, 0)[0]:
            print "Warning: Cannot use '--wait' on non-running resources"
        else:
            wait = True
    if wait:
        wait_op = "start"
        for arg in argv:
            if arg.lower() == "target-role=stopped":
                wait_op = "stop"
        timeout = utils.pcs_options["--wait"]
        if timeout is None:
            timeout = utils.get_resource_op_timeout(cib_dom, res, wait_op)
        elif not timeout.isdigit():
            utils.err("You must specify the number of seconds to wait")

    cib_dom = resource_clone_create(cib_dom, argv)
    cib_dom = constraint.constraint_resource_update(res, cib_dom)
    utils.replace_cib_configuration(cib_dom)

    if wait:
        count = utils.count_expected_resource_instances(
            utils.dom_get_clone(cib_dom, res + "-clone"),
            len(utils.getNodesFromPacemaker())
        )
        success, message = utils.is_resource_started(
            res, int(timeout), wait_op == "stop", count=count
        )
        if success:
            print message
        else:
            utils.err(
                "Unable to %s clones of '%s'\n%s"
                % (wait_op, res, message)
            )

def resource_clone_create(cib_dom, argv, update_existing=False):
    name = argv.pop(0)

    re = cib_dom.getElementsByTagName("resources")[0]
    element = utils.dom_get_resource(re, name) or utils.dom_get_group(re, name)
    if not element:
        utils.err("unable to find group or resource: %s" % name)

    if not update_existing:
        if utils.dom_get_resource_clone(cib_dom, name):
            utils.err("%s is already a clone resource" % name)

        if utils.dom_get_group_clone(cib_dom, name):
            utils.err("cannot clone a group that has already been cloned")

    if utils.dom_get_resource_masterslave(cib_dom, name):
        utils.err("%s is already a master/slave resource" % name)

    # If element is currently in a group and it's the last member, we get rid of the group
    if element.parentNode.tagName == "group" and element.parentNode.getElementsByTagName("primitive").length <= 1:
        element.parentNode.parentNode.removeChild(element.parentNode)

    meta = None
    if update_existing:
        if element.parentNode.tagName != "clone":
            utils.err("%s is not currently a clone" % name)
        clone = element.parentNode
        for child in clone.childNodes:
            if (
                child.nodeType == child.ELEMENT_NODE
                and
                child.tagName == "meta_attributes"
            ):
                meta = child
                break
    else:
        clone = cib_dom.createElement("clone")
        clone.setAttribute("id",name + "-clone")
        clone.appendChild(element)
        re.appendChild(clone)
    if meta is None:
        meta = cib_dom.createElement("meta_attributes")
        meta.setAttribute("id",name + "-clone-meta")
        clone.appendChild(meta)

    update_meta_attributes(meta, convert_args_to_tuples(argv), name + "-")

    return cib_dom

def resource_clone_master_remove(argv):
    if len(argv) != 1:
        usage.resource()
        sys.exit(1)

    name = argv.pop()
    dom = utils.get_cib_dom()
    re = dom.documentElement.getElementsByTagName("resources")[0]

    found = False
    resource = (
        utils.dom_get_resource(re, name)
        or
        utils.dom_get_group(re, name)
        or
        utils.dom_get_clone_ms_resource(re, name)
    )
    if not resource:
        utils.err("could not find resource: %s" % name)
    clone = resource.parentNode
    resource_id = resource.getAttribute("id")
    clone_id = clone.getAttribute("id")

    wait = False
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        if not utils.is_resource_started(resource_id, 0)[0]:
            print "Warning: Cannot use '--wait' on non-running resources"
        else:
            wait = True
    if wait:
        timeout = utils.pcs_options["--wait"]
        if timeout is None:
            timeout = utils.get_resource_op_timeout(dom, resource_id, "stop")
        elif not timeout.isdigit():
            utils.err("You must specify the number of seconds to wait")

    constraint.remove_constraints_containing(
        clone.getAttribute("id"), passed_dom=dom
    )
    clone.parentNode.appendChild(resource)
    clone.parentNode.removeChild(clone)
    utils.replace_cib_configuration(dom)

    if wait:
        running, message = utils.is_resource_started(
            resource_id, int(timeout), count=1
        )
        if running:
            print message
        else:
            utils.err(
                "Unable to start single instance of '%s'\n%s"
                % (resource_id, message)
            )

def resource_master(argv):
    non_option_args_count = 0
    for arg in argv:
        if arg.find("=") == -1:
            non_option_args_count += 1
    if non_option_args_count < 1:
        usage.resource()
        sys.exit(1)
    if non_option_args_count == 1:
        res_id = argv[0]
        master_id = res_id + "-master"
    else:
        master_id = argv.pop(0)
        res_id = argv[0]
    cib_dom = utils.get_cib_dom()

    wait = False
    if "--wait" in utils.pcs_options:
        if utils.usefile:
            utils.err("Cannot use '-f' together with '--wait'")
        if not utils.is_resource_started(res_id, 0)[0]:
            print "Warning: Cannot use '--wait' on non-running resources"
        else:
            wait = True
    if wait:
        wait_op = "promote"
        for arg in argv:
            if arg.lower() == "target-role=stopped":
                wait_op = "stop"
        timeout = utils.pcs_options["--wait"]
        if timeout is None:
            timeout = utils.get_resource_op_timeout(cib_dom, res_id, wait_op)
        elif not timeout.isdigit():
            utils.err("You must specify the number of seconds to wait")

    cib_dom = resource_master_create(cib_dom, argv, False, master_id)
    cib_dom = constraint.constraint_resource_update(res_id, cib_dom)
    utils.replace_cib_configuration(cib_dom)

    if wait:
        count = utils.count_expected_resource_instances(
            utils.dom_get_master(cib_dom, master_id),
            len(utils.getNodesFromPacemaker())
        )
        success, message = utils.is_resource_started(
            res_id, int(timeout), wait_op == "stop", count=count
        )
        if success:
            print message
        else:
            utils.err("unable to %s '%s'\n%s" % (wait_op, res_id, message))

def resource_master_create(dom, argv, update=False, master_id=None):
    if update:
        master_id = argv.pop(0)
    elif not master_id:
        master_id = argv[0] + "-master"

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

        if utils.is_resource_clone(rg_id):
            utils.err("%s is already a clone resource" % rg_id)

        if utils.is_resource_masterslave(rg_id):
            utils.err("%s is already a master/slave resource" % rg_id)

        resources = dom.getElementsByTagName("resources")[0]
        rg_found = False
        for resource in (resources.getElementsByTagName("primitive") +
            resources.getElementsByTagName("group")):
            if resource.getAttribute("id") == rg_id:
                rg_found = True
                break
        if not rg_found:
            utils.err("Unable to find resource or group with id %s" % rg_id)
        # If the resource elements parent is a group, and it's the last
        # element in the group, we remove the group
        if resource.parentNode.tagName == "group" and resource.parentNode.getElementsByTagName("primitive").length <= 1:
            resource.parentNode.parentNode.removeChild(resource.parentNode)
        
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

        update_meta_attributes(
            meta,
            convert_args_to_tuples(argv),
            meta.getAttribute("id") + "-"
        )
        if len(meta.getElementsByTagName("nvpair")) == 0:
            master_element.removeChild(meta)
    return dom

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
            constraint.remove_constraints_containing(resource_id, constraints_element)
    master.parentNode.removeChild(master)
    print "Removing Master - " + master_id
    utils.replace_cib_configuration(dom)

def resource_remove(resource_id, output = True):
    dom = utils.get_cib_dom()
    cloned_resource = utils.dom_get_clone_ms_resource(dom, resource_id)
    if cloned_resource:
        resource_id = cloned_resource.getAttribute("id")

    if utils.does_exist('//group[@id="'+resource_id+'"]'):
        print "Removing group: " + resource_id + " (and all resources within group)"
        group = utils.get_cib_xpath('//group[@id="'+resource_id+'"]')
        group_dom = parseString(group)
        print "Stopping all resources in group: %s..." % resource_id
        resource_disable([resource_id])
        for res in group_dom.documentElement.getElementsByTagName("primitive"):
            res_id = res.getAttribute("id")
            if not "--force" in utils.pcs_options and not utils.usefile and not utils.is_resource_started(res_id, 15, True)[0]:
                utils.err("Unable to stop group: %s before deleting (re-run with --force to force deletion)" % resource_id)
        for res in group_dom.documentElement.getElementsByTagName("primitive"):
            resource_remove(res.getAttribute("id"))
        sys.exit(0)

    group_xpath = '//group/primitive[@id="'+resource_id+'"]/..'
    group = utils.get_cib_xpath(group_xpath)
    num_resources_in_group = 0

    if not utils.does_exist('//resources/descendant::primitive[@id="'+resource_id+'"]'):
        if utils.does_exist('//resources/master[@id="'+resource_id+'"]'):
            return resource_master_remove([resource_id])

        utils.err("Resource does not exist.")

    if (group != ""):
        num_resources_in_group = len(parseString(group).documentElement.getElementsByTagName("primitive"))

    if not "--force" in utils.pcs_options and not utils.usefile and not utils.is_resource_started(resource_id, 0, True)[0]:
        sys.stdout.write("Attempting to stop: "+ resource_id + "...")
        sys.stdout.flush()
        resource_disable([resource_id])
        if not utils.is_resource_started(resource_id, 15, True)[0]:
            utils.err("Unable to stop: %s before deleting (re-run with --force to force deletion)" % resource_id)
        print "Stopped"

    constraint.remove_constraints_containing(resource_id,output)
    resource_el = utils.dom_get_resource(dom, resource_id)
    if resource_el:
        remote_node = utils.dom_get_resource_remote_node_name(resource_el)
        if remote_node:
            dom = constraint.remove_constraints_containing_node(
                dom, remote_node, output
            )
            utils.replace_cib_configuration(dom)
            dom = utils.get_cib_dom()

    if (group == "" or num_resources_in_group > 1):
        master_xpath = '//master/primitive[@id="'+resource_id+'"]/..'
        clone_xpath = '//clone/primitive[@id="'+resource_id+'"]/..'
        if utils.get_cib_xpath(clone_xpath) != "":
            args = ["cibadmin", "-o", "resources", "-D", "--xpath", clone_xpath]
        elif utils.get_cib_xpath(master_xpath) != "":
            args = ["cibadmin", "-o", "resources", "-D", "--xpath", master_xpath]
        else:
            args = ["cibadmin", "-o", "resources", "-D", "--xpath", "//primitive[@id='"+resource_id+"']"]
        if output == True:
            print "Deleting Resource - " + resource_id
        output,retVal = utils.run(args)
        if retVal != 0:
            utils.err("unable to remove resource: %s, it may still be referenced in constraints." % resource_id)
    else:
        top_master_xpath = '//master/group/primitive[@id="'+resource_id+'"]/../..'
        top_clone_xpath = '//clone/group/primitive[@id="'+resource_id+'"]/../..'
        top_master = utils.get_cib_xpath(top_master_xpath)
        top_clone = utils.get_cib_xpath(top_clone_xpath)
        if top_master != "":
            to_remove_xpath = top_master_xpath
            msg = "and group and M/S"
            to_remove_dom = parseString(top_master).getElementsByTagName("master")
            to_remove_id = to_remove_dom[0].getAttribute("id")
            constraint.remove_constraints_containing(to_remove_dom[0].getElementsByTagName("group")[0].getAttribute("id"))
        elif top_clone != "":
            to_remove_xpath = top_clone_xpath
            msg = "and group and clone"
            to_remove_dom = parseString(top_clone).getElementsByTagName("clone")
            to_remove_id = to_remove_dom[0].getAttribute("id")
            constraint.remove_constraints_containing(to_remove_dom[0].getElementsByTagName("group")[0].getAttribute("id"))
        else:
            to_remove_xpath = group_xpath
            msg = "and group"
            to_remove_dom = parseString(group).getElementsByTagName("group")
            to_remove_id = to_remove_dom[0].getAttribute("id")

        constraint.remove_constraints_containing(to_remove_id,output)

        args = ["cibadmin", "-o", "resources", "-D", "--xpath", to_remove_xpath]
        if output == True:
            print "Deleting Resource ("+msg+") - " + resource_id
        cmdoutput,retVal = utils.run(args)
        if retVal != 0:
            if output == True:
                utils.err("Unable to remove resource '%s' (do constraints exist?)" % (resource_id))
            return False
    return True

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(cib_dom, group_name, resource_ids):
    dom = cib_dom.getElementsByTagName("configuration")[0]
    group_match = None

    all_resources = False
    if len(resource_ids) == 0:
        all_resources = True

    for group in dom.getElementsByTagName("group"):
        if group.getAttribute("id") == group_name:
            group_match = group
            break

    if not group_match:
        utils.err("Group '%s' does not exist" % group_name)

    if group_match.parentNode.tagName == "master" and group_match.getElementsByTagName("primitive").length > 1:
        utils.err("Groups that have more than one resource and are master/slave resources cannot be removed.  The group may be deleted with 'pcs resource delete %s'." % group_name)

    resources_to_move = []
    resources_to_move_id = []

    if all_resources:
        for resource in group_match.getElementsByTagName("primitive"):
            resources_to_move.append(resource)
    else:
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
        resources_to_move_id.append(resource.getAttribute("id"))
        parent = resource.parentNode
        resource.parentNode.removeChild(resource)
        parent.parentNode.appendChild(resource)

    constraint.remove_constraints_containing(group_name, True, passed_dom=dom)

    if len(group_match.getElementsByTagName("primitive")) == 0:
        group_match.parentNode.removeChild(group_match)

    return cib_dom, resources_to_move_id

def resource_group_add(cib_dom, group_name, resource_ids):
    resources_element = cib_dom.getElementsByTagName("resources")[0]

    name_valid, name_error = utils.validate_xml_id(group_name, 'group name')
    if not name_valid:
        utils.err(name_error)

    mygroup = utils.dom_get_group(resources_element, group_name)
    if not mygroup:
        if utils.dom_get_resource(resources_element, group_name):
            utils.err("'%s' is already a resource" % group_name)
        if utils.dom_get_clone(resources_element, group_name):
            utils.err("'%s' is already a clone resource" % group_name)
        if utils.dom_get_master(resources_element, group_name):
            utils.err("'%s' is already a master/slave resource" % group_name)
        mygroup = cib_dom.createElement("group")
        mygroup.setAttribute("id", group_name)
        resources_element.appendChild(mygroup)

    after = before = None
    if "--after" in utils.pcs_options and "--before" in utils.pcs_options:
        utils.err("you cannot specify both --before and --after")
    if "--after" in utils.pcs_options:
        after = utils.dom_get_resource(mygroup, utils.pcs_options["--after"])
        if not after:
            utils.err(
                "there is no resource '%s' in the group '%s'"
                % (utils.pcs_options["--after"], group_name)
            )
    if "--before" in utils.pcs_options:
        before = utils.dom_get_resource(mygroup, utils.pcs_options["--before"])
        if not before:
            utils.err(
                "there is no resource '%s' in the group '%s'"
                % (utils.pcs_options["--before"], group_name)
            )

    resources_to_move = []
    for resource_id in resource_ids:
        if (
            utils.dom_get_resource(mygroup, resource_id)
            and not after and not before
        ):
            utils.err(resource_id + " already exists in " + group_name)
        if after and after.getAttribute("id") == resource_id:
            utils.err("cannot put resource after itself")
        if before and before.getAttribute("id") == resource_id:
            utils.err("cannot put resource before itself")

        resource_found = False
        for resource in resources_element.getElementsByTagName("primitive"):
            if resource.nodeType == xml.dom.minidom.Node.TEXT_NODE:
                continue
            if resource.getAttribute("id") == resource_id:
                if resource.parentNode.tagName == "master":
                    utils.err("cannot group master/slave resources")
                if resource.parentNode.tagName == "clone":
                    utils.err("cannot group clone resources")
                resources_to_move.append(resource)
                resource_found = True
                break

        if resource_found == False:
            utils.err("Unable to find resource: " + resource_id)
            continue

    if resources_to_move:
        for resource in resources_to_move:
            oldParent = resource.parentNode
            if after and after.nextSibling:
                mygroup.insertBefore(resource, after.nextSibling)
                after = resource
            elif before:
                mygroup.insertBefore(resource, before)
            else:
                mygroup.appendChild(resource)
            if oldParent.tagName == "group" and len(oldParent.getElementsByTagName("primitive")) == 0:
                oldParent.parentNode.removeChild(oldParent)
        return cib_dom
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
    if "--groups" in utils.pcs_options:
        resource_group_list(argv)
        return

    if "--full" in utils.pcs_options:
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
        output, retval = utils.run(["crm_mon", "-1", "-r"])
        if retval != 0:
            utils.err("unable to get cluster status from crm_mon\n"+output.rstrip())
        preg = re.compile(r'.*(stonith:.*)')
        resources_header = False
        in_resources = False
        has_resources = False
        for line in output.split('\n'):
            if line == "Full list of resources:":
                resources_header = True
                continue
            if line == "":
                if resources_header:
                    resources_header = False
                    in_resources = True
                elif in_resources:
                    if not has_resources:
                        if not stonith:
                            print "NO resources configured"
                        else:
                            print "NO stonith devices configured"
                    return
                continue
            if in_resources:
                if not preg.match(line) and not stonith:
                    has_resources = True
                    print line
                elif preg.match(line) and stonith:
                    has_resources = True
                    print line
        return

    preg = re.compile(r'.*xml:\n',re.DOTALL)
    root = utils.get_cib_etree()
    resources = root.find(".//resources")
    resource_found = False
    for arg in argv:
        for child in resources.findall(".//*"):
            if "id" in child.attrib and child.attrib["id"] == arg and ((stonith and utils.is_stonith_resource(arg)) or (not stonith and not utils.is_stonith_resource(arg))):
                print_node(child,1)
                resource_found = True
                break
        if not resource_found:
            utils.err("unable to find resource '"+arg+"'")
        resource_found = False

def resource_disable(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to disable")

    resource = argv[0]
    if not is_managed(resource):
        print "Warning: '%s' is unmanaged" % resource

    if "--wait" in utils.pcs_options:
        cib_dom = utils.get_cib_dom()
        resource_wait = utils.dom_get_clone_ms_resource(cib_dom, resource)
        if resource_wait is not None and resource_wait.tagName == "primitive":
            resource_wait = resource_wait.getAttribute("id")
        else:
            resource_wait = resource
        wait = utils.pcs_options["--wait"]
        if wait is None:
            wait = utils.get_resource_op_timeout(cib_dom, resource_wait, "stop")
        elif not wait.isdigit():
            utils.err("%s is not a valid number of seconds to wait" % wait)
            sys.exit(1)

    args = ["crm_resource", "-r", argv[0], "-m", "-p", "target-role", "-v", "Stopped"]
    output, retval = utils.run(args)
    if retval != 0:
        utils.err(output)

    if "--wait" in utils.pcs_options:
        did_stop, message = utils.is_resource_started(
            resource_wait, int(wait), True
        )
        if did_stop:
            print message
            return True
        else:
            utils.err(
                "unable to stop: '%s', please check logs for failure "
                    "information\n%s"
                % (resource, message)
            )

def resource_enable(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to enable")

    resource = argv[0]
    if not is_managed(resource):
        print "Warning: '%s' is unmanaged" % resource

    if "--wait" in utils.pcs_options:
        cib_dom = utils.get_cib_dom()
        resource_wait = utils.dom_get_clone_ms_resource(cib_dom, resource)
        if resource_wait is not None and resource_wait.tagName == "primitive":
            resource_wait = resource_wait.getAttribute("id")
        else:
            resource_wait = resource
        wait = utils.pcs_options["--wait"]
        if wait is None:
            wait = utils.get_resource_op_timeout(cib_dom, resource_wait, "start")
        elif not wait.isdigit():
            utils.err("%s is not a valid number of seconds to wait" % wait)
            sys.exit(1)

    args = ["crm_resource", "-r", resource, "-m", "-d", "target-role"]
    output, retval = utils.run(args)
    if retval != 0:
        utils.err (output)

    if "--wait" in utils.pcs_options:
        did_start, message = utils.is_resource_started(resource_wait, int(wait))
        if did_start:
            print message
            return True
        else:
            utils.err(
                "unable to start: '%s', please check logs for failure "
                    "information\n%s"
                % (resource, message)
            )

def resource_restart(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to restart")

    dom = utils.get_cib_dom()
    node = None
    resource = argv.pop(0)

    real_res = utils.dom_get_resource_clone_ms_parent(dom, resource)
    if real_res:
        print "Warning: using %s... (if a resource is a clone or master/slave you must use the clone or master/slave name" % real_res.getAttribute("id")
        resource = real_res.getAttribute("id")

    args = ["crm_resource", "--restart", "--resource", resource]
    if len(argv) > 0:
        node = argv.pop(0)
        if not utils.dom_get_clone(dom,resource) and not utils.dom_get_master(dom,resource):
            utils.err("can only restart on a specific node for a clone or master/slave resource")
        args.extend(["--node", node])

    if "--wait" in utils.pcs_options:
        if utils.pcs_options["--wait"]:
            args.extend(["--timeout", utils.pcs_options["--wait"]])
        else:
            utils.err("You must specify the number of seconds to wait")

    output, retval = utils.run(args)
    if retval != 0:
        utils.err(output)

    print "%s successfully restarted" % resource

def resource_force_start(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to debug-start")

    resource = argv[0]

    if utils.is_group(resource):
        group_resources = utils.get_group_children(resource)
        utils.err("unable to debug-start a group, try one of the group's resource(s) (%s)" % ",".join(group_resources))

    dom = utils.get_cib_dom()

    if utils.dom_get_clone(dom, resource):
        clone_resource = utils.dom_get_clone_ms_resource(dom, resource)
        utils.err("unable to debug-start a clone, try the clone's resource: %s" % clone_resource.getAttribute("id"))

    if utils.dom_get_master(dom, resource):
        master_resource = utils.dom_get_clone_ms_resource(dom, resource)
        utils.err("unable to debug-start a master, try the master's resource: %s" % master_resource.getAttribute("id"))

    args = ["crm_resource", "-r", resource, "--force-start"]
    if "--full" in utils.pcs_options:
        args = args + ["-V"]

    output, retval = utils.run(args)
    print output,
    sys.exit(retval)

def resource_manage(argv, set_managed):
    if len(argv) == 0:
        usage.resource()
        sys.exit(1)

    for resource in argv:
        if not utils.does_exist("(//primitive|//group|//master|//clone)[@id='"+resource+"']"):
            utils.err("%s doesn't exist." % resource)

    dom = utils.get_cib_dom()
    for resource in argv:
        isGroup = False
        isResource = False
        for el in dom.getElementsByTagName("group") + dom.getElementsByTagName("master") + dom.getElementsByTagName("clone"):
            if el.getAttribute("id") == resource:
                group = el
                isGroup = True
                break

        if isGroup:
            res_to_manage = []
            for el in group.getElementsByTagName("primitive"):
                res_to_manage.append(el.getAttribute("id"))
        else:
            for el in dom.getElementsByTagName("primitive"):
                if el.getAttribute("id") == resource:
                    isResource = True
                    break

        if not set_managed:
            if isResource:
                (output, retval) =  utils.set_unmanaged(resource)
            elif isGroup:
                for res in res_to_manage:
                    (output, retval) =  utils.set_unmanaged(res)
                    retval = 0
            else:
                utils.err("unable to find resource/group: %s")

            if retval != 0:
                utils.err("error attempting to unmanage resource: %s" % output)
        else:
            xpath = "(//primitive|//group)[@id='"+resource+"']/meta_attributes/nvpair[@name='is-managed']" 
            utils.run(["cibadmin", "-D", "--xpath", xpath])
            if isGroup:
                for res in res_to_manage:
                    xpath = "(//primitive|//group)[@id='"+res+"']/meta_attributes/nvpair[@name='is-managed']" 
                    utils.run(["cibadmin", "-D", "--xpath", xpath])

def is_managed(resource_id):
    state_dom = utils.getClusterState()
    for resource_el in state_dom.getElementsByTagName("resource"):
        if resource_el.getAttribute("id") in [resource_id, resource_id + ":0"]:
            if resource_el.getAttribute("managed") == "false":
                return False
            return True
    for resource_el in state_dom.getElementsByTagName("group"):
        if resource_el.getAttribute("id") in [resource_id, resource_id + ":0"]:
            for primitive_el in resource_el.getElementsByTagName("resource"):
                if primitive_el.getAttribute("managed") == "false":
                    return False
            return True
    for resource_el in state_dom.getElementsByTagName("clone"):
        if resource_el.getAttribute("id") == resource_id:
            if resource_el.getAttribute("managed") == "false":
                return False
            for primitive_el in resource_el.getElementsByTagName("resource"):
                if primitive_el.getAttribute("managed") == "false":
                    return False
            return True
    utils.err("unable to find a resource/clone/master/group: %s" % resource_id)

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


def show_defaults(def_type, indent=""):
    dom = utils.get_cib_dom()
    defs = dom.getElementsByTagName(def_type)
    if len(defs) > 0:
        defs = defs[0]
    else:
        print indent + "No defaults set"
        return

    foundDefault = False
    for d in defs.getElementsByTagName("nvpair"):
        print indent + d.getAttribute("name") + ": " + d.getAttribute("value")
        foundDefault = True

    if not foundDefault:
        print indent + "No defaults set"

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
        for child in op.findall(".//nvpair"):
            output += child.get("name") + "=" + child.get("value") + " "

        output += "(" + op.attrib["id"] + ")"
        output += "\n"

    output = output.rstrip()
    if output != "":
        print spaces + " Operations: " + output

def operation_to_string(op_el):
    parts = []
    parts.append(op_el.getAttribute("name"))
    for name, value in op_el.attributes.items():
        if name in ["id", "name"]:
            continue
        parts.append(name + "=" + value)
    for nvpair in op_el.getElementsByTagName("nvpair"):
        parts.append(
            nvpair.getAttribute("name") + "=" + nvpair.getAttribute("value")
        )
    parts.append("(" + op_el.getAttribute("id") + ")")
    return " ".join(parts)

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
        utils.err("Unable to cleanup resource: %s" % res_id + "\n" + output)
    else:
        print "Resource: %s successfully cleaned up" % res_id

def resource_cleanup_all():
    (output, retval) = utils.run(["crm_resource", "-C"])
    if retval != 0:
        utils.err("Unexpected error occured. 'crm_resource -C' err_code: %s\n%s" % (retval, output))
    else:
        print "All resources/stonith devices successfully cleaned up"

def resource_history(args):
    dom = utils.get_cib_dom()
    resources = {}
    calls = {}
    lrm_res = dom.getElementsByTagName("lrm_resource")
    for res in lrm_res:
        res_id = res.getAttribute("id")
        if res_id not in resources:
            resources[res_id] = {}
        for rsc_op in res.getElementsByTagName("lrm_rsc_op"):
            resources[res_id][rsc_op.getAttribute("call-id")] = [res_id, rsc_op]
    
    for res in sorted(resources):
        print "Resource: %s" % res
        for cid in sorted(resources[res]):
            (last_date,retval) = utils.run(["date","-d", "@" + resources[res][cid][1].getAttribute("last-rc-change")])
            last_date = last_date.rstrip()
            rc_code = resources[res][cid][1].getAttribute("rc-code")
            operation = resources[res][cid][1].getAttribute("operation") 
            if rc_code != "0":
                print "  Failed on %s" % last_date
            elif operation == "stop":
                print "  Stopped on node xx on %s" % last_date
            elif operation == "start":
                print "  Started on node xx %s" % last_date

