from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
import xml.dom.minidom
from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import re
import textwrap
import time
import json

from pcs import (
    usage,
    utils,
    constraint,
)
from pcs.settings import pacemaker_wait_timeout_status as \
    PACEMAKER_WAIT_TIMEOUT_STATUS
import pcs.lib.cib.acl as lib_acl
import pcs.lib.pacemaker as lib_pacemaker
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import prepare_options
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker_values import timeout_to_seconds
import pcs.lib.resource_agent as lib_ra


RESOURCE_RELOCATE_CONSTRAINT_PREFIX = "pcs-relocate-"

def resource_cmd(argv):
    if len(argv) < 1:
        sub_cmd, argv_next = "show", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    lib = utils.get_library_wrapper()
    modifiers = utils.get_modificators()

    try:
        if sub_cmd == "help":
            usage.resource(argv)
        elif sub_cmd == "list":
            resource_list_available(lib, argv_next, modifiers)
        elif sub_cmd == "describe":
            resource_list_options(lib, argv_next, modifiers)
        elif sub_cmd == "create":
            if len(argv_next) < 2:
                usage.resource(["create"])
                sys.exit(1)
            res_id = argv_next.pop(0)
            res_type = argv_next.pop(0)
            ra_values, op_values, meta_values, clone_opts = parse_resource_options(
                argv_next, with_clone=True
            )
            resource_create(
                res_id, res_type, ra_values, op_values, meta_values, clone_opts,
                group=utils.pcs_options.get("--group", None)
            )
        elif sub_cmd == "move":
            resource_move(argv_next)
        elif sub_cmd == "ban":
            resource_move(argv_next, False, True)
        elif sub_cmd == "clear":
            resource_move(argv_next, True)
        elif sub_cmd == "standards":
            resource_standards(lib, argv_next, modifiers)
        elif sub_cmd == "providers":
            resource_providers(lib, argv_next, modifiers)
        elif sub_cmd == "agents":
            resource_agents(lib, argv_next, modifiers)
        elif sub_cmd == "update":
            if len(argv_next) == 0:
                usage.resource(["update"])
                sys.exit(1)
            res_id = argv_next.pop(0)
            resource_update(res_id, argv_next)
        elif sub_cmd == "add_operation":
            utils.err("add_operation has been deprecated, please use 'op add'")
        elif sub_cmd == "remove_operation":
            utils.err("remove_operation has been deprecated, please use 'op remove'")
        elif sub_cmd == "meta":
            if len(argv_next) < 2:
                usage.resource(["meta"])
                sys.exit(1)
            res_id = argv_next.pop(0)
            resource_meta(res_id, argv_next)
        elif sub_cmd == "delete":
            if len(argv_next) == 0:
                usage.resource(["delete"])
                sys.exit(1)
            res_id = argv_next.pop(0)
            resource_remove(res_id)
        elif sub_cmd == "show":
            resource_show(argv_next)
        elif sub_cmd == "group":
            resource_group(argv_next)
        elif sub_cmd == "ungroup":
            resource_group(["remove"] + argv_next)
        elif sub_cmd == "clone":
            resource_clone(argv_next)
        elif sub_cmd == "unclone":
            resource_clone_master_remove(argv_next)
        elif sub_cmd == "master":
            resource_master(argv_next)
        elif sub_cmd == "enable":
            resource_enable(argv_next)
        elif sub_cmd == "disable":
            resource_disable(argv_next)
        elif sub_cmd == "restart":
            resource_restart(argv_next)
        elif sub_cmd == "debug-start":
            resource_force_action(sub_cmd, argv_next)
        elif sub_cmd == "debug-stop":
            resource_force_action(sub_cmd, argv_next)
        elif sub_cmd == "debug-promote":
            resource_force_action(sub_cmd, argv_next)
        elif sub_cmd == "debug-demote":
            resource_force_action(sub_cmd, argv_next)
        elif sub_cmd == "debug-monitor":
            resource_force_action(sub_cmd, argv_next)
        elif sub_cmd == "manage":
            resource_manage(argv_next, True)
        elif sub_cmd == "unmanage":
            resource_manage(argv_next, False)
        elif sub_cmd == "failcount":
            resource_failcount(argv_next)
        elif sub_cmd == "op":
            if len(argv_next) < 1:
                usage.resource(["op"])
                sys.exit(1)
            op_subcmd = argv_next.pop(0)
            if op_subcmd == "defaults":
                if len(argv_next) == 0:
                    show_defaults("op_defaults")
                else:
                    set_default("op_defaults", argv_next)
            elif op_subcmd == "add":
                if len(argv_next) == 0:
                    usage.resource(["op"])
                    sys.exit(1)
                else:
                    res_id = argv_next.pop(0)
                    utils.replace_cib_configuration(
                        resource_operation_add(
                            utils.get_cib_dom(), res_id, argv_next
                        )
                    )
            elif op_subcmd in ["remove", "delete"]:
                if len(argv_next) == 0:
                    usage.resource(["op"])
                    sys.exit(1)
                else:
                    res_id = argv_next.pop(0)
                    resource_operation_remove(res_id, argv_next)
        elif sub_cmd == "defaults":
            if len(argv_next) == 0:
                show_defaults("rsc_defaults")
            else:
                set_default("rsc_defaults", argv_next)
        elif sub_cmd == "cleanup":
            resource_cleanup(argv_next)
        elif sub_cmd == "history":
            resource_history(argv_next)
        elif sub_cmd == "relocate":
            resource_relocate(argv_next)
        elif sub_cmd == "utilization":
            if len(argv_next) == 0:
                print_resources_utilization()
            elif len(argv_next) == 1:
                print_resource_utilization(argv_next.pop(0))
            else:
                set_resource_utilization(argv_next.pop(0), argv_next)
        elif sub_cmd == "get_resource_agent_info":
            get_resource_agent_info(argv_next)
        else:
            usage.resource()
            sys.exit(1)
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "resource", sub_cmd)

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


def resource_list_available(lib, argv, modifiers):
    if len(argv) > 1:
        raise CmdLineInputError()

    search = argv[0] if argv else None
    agent_list = lib.resource_agent.list_agents(modifiers["describe"], search)

    if not agent_list:
        if search:
            utils.err("No resource agents matching the filter.")
        utils.err(
            "No resource agents available. "
            "Do you have resource agents installed?"
        )

    for agent_info in agent_list:
        name = agent_info["name"]
        shortdesc = agent_info["shortdesc"]
        if shortdesc:
            print("{0} - {1}".format(
                name,
                _format_desc(len(name + " - "), shortdesc.replace("\n", " "))
            ))
        else:
            print(name)


def resource_list_options(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = argv[0]

    print(_format_agent_description(
        lib.resource_agent.describe_agent(agent_name)
    ))


def _format_agent_description(description, stonith=False):
    output = []

    if description.get("name") and description.get("shortdesc"):
        output.append("{0} - {1}".format(
            description["name"],
            _format_desc(
                len(description["name"] + " - "),
                description["shortdesc"]
            )
        ))
    elif description.get("name"):
        output.append(description["name"])
    elif description.get("shortdesc"):
        output.append(description["shortdesc"])

    if description.get("longdesc"):
        output.append("")
        output.append(description["longdesc"])

    if description.get("parameters"):
        output_params = []
        for param in description["parameters"]:
            if param.get("advanced", False):
                continue
            param_title = " ".join(filter(None, [
                param.get("name"),
                "(required)" if param.get("required", False) else None
            ]))
            param_desc = param.get("longdesc", "").replace("\n", " ")
            if not param_desc:
                param_desc = param.get("shortdesc", "").replace("\n", " ")
                if not param_desc:
                    param_desc = "No description available"
            output_params.append("  {0}: {1}".format(
                param_title,
                _format_desc(len(param_title) + 4, param_desc)
            ))
        if output_params:
            output.append("")
            if stonith:
                output.append("Stonith options:")
            else:
                output.append("Resource options:")
            output.extend(output_params)

    if description.get("actions"):
        output_actions = []
        for action in utils.filter_default_op_from_actions(
            description["actions"]
        ):
            parts = ["  {0}:".format(action.get("name", ""))]
            parts.extend([
                "{0}={1}".format(name, value)
                for name, value in sorted(action.items())
                if name != "name"
            ])
            output_actions.append(" ".join(parts))
        if output_actions:
            output.append("")
            output.append("Default operations:")
            output.extend(output_actions)

    return "\n".join(output)


# Return the string formatted with a line length of terminal width  and indented
def _format_desc(indent, desc):
    desc = " ".join(desc.split())
    dummy_rows, columns = utils.getTerminalSize()
    columns = int(columns)
    if columns < 40:
        columns = 40
    afterindent = columns - indent
    if afterindent < 1:
        afterindent = columns

    output = ""
    first = True
    for line in textwrap.wrap(desc, afterindent):
        if not first:
            output += " " * indent
        output += line
        output += "\n"
        first = False

    return output.rstrip()

# Create a resource using cibadmin
# ra_class, ra_type & ra_provider must all contain valid info
def resource_create(
    ra_id, ra_type, ra_values, op_values, meta_values=[], clone_opts=[],
    group=None
):
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()
        if "--disabled" in utils.pcs_options:
            utils.err("Cannot use '--wait' together with '--disabled'")
        do_not_run = ["target-role=stopped"]
        if (
            "--master" in utils.pcs_options or "--clone" in utils.pcs_options
            or
            clone_opts
        ):
            do_not_run.extend(["clone-max=0", "clone-node-max=0"])
        for opt in meta_values + clone_opts:
            if opt.lower() in do_not_run:
                utils.err("Cannot use '--wait' together with '%s'" % opt)

    ra_id_valid, ra_id_error = utils.validate_xml_id(ra_id, 'resource name')
    if not ra_id_valid:
        utils.err(ra_id_error)


    try:
        if ":" in ra_type:
            full_agent_name = ra_type
            if full_agent_name.startswith("stonith:"):
                # Maybe we can just try to get a metadata object and if it fails
                # then we know the agent is not valid. Then the is_valid_agent
                # method can be completely removed.
                is_valid_agent = lib_ra.StonithAgent(
                    utils.cmd_runner(),
                    full_agent_name[len("stonith:"):]
                ).is_valid_metadata()
            else:
                is_valid_agent = lib_ra.ResourceAgent(
                    utils.cmd_runner(),
                    full_agent_name
                ).is_valid_metadata()
            if not is_valid_agent:
                if "--force" not in utils.pcs_options:
                    utils.err("Unable to create resource '{0}', it is not installed on this system (use --force to override)".format(full_agent_name))
                elif not full_agent_name.startswith("stonith:"):
                    # stonith is covered in stonith.stonith_create
                    if not re.match("^[^:]+(:[^:]+){1,2}$", full_agent_name):
                        utils.err(
                            "Invalid resource agent name '{0}'".format(
                                full_agent_name
                            )
                        )
                    print(
                        "Warning: '{0}' is not installed or does not provide valid metadata".format(
                            full_agent_name
                        )
                    )
        else:
            full_agent_name = lib_ra.guess_exactly_one_resource_agent_full_name(
                utils.cmd_runner(),
                ra_type
            ).get_name()
            print("Creating resource '{0}'".format(full_agent_name))
    except lib_ra.ResourceAgentError as e:
        utils.process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e)]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)
    agent_name_parts = split_resource_agent_name(full_agent_name)


    dom = utils.get_cib_dom()

    if utils.does_id_exist(dom, ra_id):
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
        default_op_values = utils.get_default_op_values(full_agent_name)
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
                interval = timeout_to_seconds(match.group(1))
                if interval is not None:
                    if interval in action_intervals[op_action]:
                        old_interval = interval
                        while interval in action_intervals[op_action]:
                            interval += 1
                        op[key] = "interval=%s" % interval
                        print(
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

    if "--disabled" in utils.pcs_options:
        meta_values = [
            meta for meta in meta_values if not meta.startswith("target-role=")
        ]
        meta_values.append("target-role=Stopped")

# If it's a master all meta values go to the master
    master_meta_values = []
    if "--master" in utils.pcs_options:
        master_meta_values = meta_values
        meta_values = []

    instance_attributes = convert_args_to_instance_variables(ra_values,ra_id)
    primitive_values = agent_name_parts[:]
    primitive_values.insert(0,("id",ra_id))
    meta_attributes = convert_args_to_meta_attrs(meta_values, ra_id)
    if "--force" not in utils.pcs_options:
        params = utils.convert_args_to_tuples(ra_values)
        bad_opts, missing_req_opts = [], []
        try:
            if full_agent_name.startswith("stonith:"):
                metadata = lib_ra.StonithAgent(
                    utils.cmd_runner(),
                    full_agent_name[len("stonith:"):]
                )
            else:
                metadata = lib_ra.ResourceAgent(
                    utils.cmd_runner(),
                    full_agent_name
                )
            bad_opts, missing_req_opts = metadata.validate_parameters_values(
                dict(params)
            )
        except lib_ra.ResourceAgentError as e:
            utils.process_library_reports(
                [lib_ra.resource_agent_error_to_report_item(e)]
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        if len(bad_opts) != 0:
            utils.err ("resource option(s): '%s', are not recognized for resource type: '%s' (use --force to override)" \
                    % (", ".join(sorted(bad_opts)), full_agent_name))
        if len(missing_req_opts) != 0:
            utils.err(
                "missing required option(s): '%s' for resource type: %s"
                    " (use --force to override)"
                % (", ".join(missing_req_opts), full_agent_name)
            )

    resource_elem = create_xml_element("primitive", primitive_values, instance_attributes + meta_attributes)
    dom.getElementsByTagName("resources")[0].appendChild(resource_elem)
    # Do not validate default operations defined by a resource agent
    # User did not entered them so we will not confuse him/her with their errors
    for op in op_values_agent:
        dom = resource_operation_add(dom, ra_id, op, validate=False)
    for op in op_values:
        dom = resource_operation_add(
            dom, ra_id, op, validate=True, validate_strict=False
        )

    if "--clone" in utils.pcs_options or len(clone_opts) > 0:
        dom, dummy_clone_id = resource_clone_create(dom, [ra_id] + clone_opts)
        if group:
            print("Warning: --group ignored when creating a clone")
        if "--master" in utils.pcs_options:
            print("Warning: --master ignored when creating a clone")
    elif "--master" in utils.pcs_options:
        dom, dummy_master_id = resource_master_create(
            dom, [ra_id] + master_meta_values
        )
        if group:
            print("Warning: --group ignored when creating a master")
    elif group:
        dom = resource_group_add(dom, group, [ra_id])

    utils.replace_cib_configuration(dom)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(ra_id)
        if retval == 0 and running_on["is_running"]:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            else:
                msg.append(
                    "unable to start: '%s', please check logs for failure "
                    "information"
                    % ra_id
                )
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

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

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()
        if not clear:
            running_on = utils.resource_running_on(resource_id)
            was_running = running_on["is_running"]
            allowed_nodes = set()
            banned_nodes = set()
            if dest_node and ban: # ban, node specified
                banned_nodes = set([dest_node])
            elif dest_node: # move, node specified
                allowed_nodes = set([dest_node])
            else: # move or ban, node not specified
                banned_nodes = set(
                    running_on["nodes_master"] + running_on["nodes_started"]
                )

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
    else:
        warning_re = re.compile(
            r"WARNING: Creating rsc_location constraint '([^']+)' "
            + r"with a score of -INFINITY for resource ([\S]+) on (.+)."
        )
        for line in output.split("\n"):
            warning_match = warning_re.search(line)
            if warning_match:
                warning_constraint = warning_match.group(1)
                warning_resource = warning_match.group(2)
                warning_node = warning_match.group(3)
                warning_action = "running"
                if "--master" in utils.pcs_options:
                    warning_action = "being promoted"
                print(("Warning: Creating location constraint {0} with a score "
                    + "of -INFINITY for resource {1} on node {2}.").format(
                        warning_constraint, warning_resource, warning_node
                    ))
                print(("This will prevent {0} from {1} on {2} until the "
                    + "constraint is removed. This will be the case even if {3}"
                    + " is the last node in the cluster.").format(
                        warning_resource, warning_action, warning_node,
                        warning_node
                    ))

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(resource_id)
        running_nodes = running_on["nodes_started"] + running_on["nodes_master"]
        error = retval != 0
        if ban and (
            not banned_nodes.isdisjoint(running_nodes)
            or
            (was_running and not running_nodes)
        ):
            error = True
        if (
            not ban and not clear and was_running # running resource moved
            and (
                not running_nodes
                or
                (allowed_nodes and allowed_nodes.isdisjoint(running_nodes))
           )
        ):
            error = True
        if not error:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())


def resource_standards(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    standards = lib.resource_agent.list_standards()

    if standards:
        print("\n".join(standards))
    else:
        utils.err("No standards found")


def resource_providers(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    providers = lib.resource_agent.list_ocf_providers()

    if providers:
        print("\n".join(providers))
    else:
        utils.err("No OCF providers found")


def resource_agents(lib, argv, modifiers):
    if len(argv) > 1:
        raise CmdLineInputError()

    standard = argv[0] if argv else None

    agents = lib.resource_agent.list_agents_for_standard_and_provider(standard)

    if agents:
        print("\n".join(agents))
    else:
        utils.err("No agents found{0}".format(
            " for {0}".format(argv[0]) if argv else ""
        ))


# Update a resource, removing any args that are empty and adding/updating
# args that are not empty
def resource_update(res_id,args):
    dom = utils.get_cib_dom()

# Extract operation arguments
    ra_values, op_values, meta_values = parse_resource_options(args)

    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()
        wait = True

    resource = utils.dom_get_resource(dom, res_id)
    if not resource:
        clone = utils.dom_get_clone(dom, res_id)
        if clone:
            clone_child = utils.dom_elem_get_clone_ms_resource(clone)
            if clone_child:
                child_id = clone_child.getAttribute("id")
                return resource_update_clone_master(
                    dom, clone, "clone", child_id, args, wait, wait_timeout
                )
        master = utils.dom_get_master(dom, res_id)
        if master:
            return resource_update_clone_master(
                dom, master, "master", res_id, args, wait, wait_timeout
            )
        utils.err("Unable to find resource: %s" % res_id)

    instance_attributes = resource.getElementsByTagName("instance_attributes")
    if len(instance_attributes) == 0:
        instance_attributes = dom.createElement("instance_attributes")
        instance_attributes.setAttribute("id", res_id + "-instance_attributes")
        resource.appendChild(instance_attributes)
    else:
        instance_attributes = instance_attributes[0]

    params = utils.convert_args_to_tuples(ra_values)
    if "--force" not in utils.pcs_options and (resource.getAttribute("class") == "ocf" or resource.getAttribute("class") == "stonith"):
        resClass = resource.getAttribute("class")
        resProvider = resource.getAttribute("provider")
        resType = resource.getAttribute("type")
        if resProvider == "":
            resource_type = resClass + ":" + resType
        else:
            resource_type = resClass + ":" + resProvider + ":" + resType
        bad_opts = []
        try:
            if resource_type.startswith("stonith:"):
                metadata = lib_ra.StonithAgent(
                    utils.cmd_runner(),
                    resource_type[len("stonith:"):]
                )
            else:
                metadata = lib_ra.ResourceAgent(
                    utils.cmd_runner(),
                    resource_type
                )
            bad_opts, _ = metadata.validate_parameters_values(dict(params))
        except lib_ra.ResourceAgentError as e:
            utils.process_library_reports(
                [lib_ra.resource_agent_error_to_report_item(e)]
            )
        except LibraryError as e:
            utils.process_library_reports(e.args)
        if len(bad_opts) != 0:
            utils.err ("resource option(s): '%s', are not recognized for resource type: '%s' (use --force to override)" \
                    % (", ".join(sorted(bad_opts)), utils.getResourceType(resource)))


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

    remote_node_name = utils.dom_get_resource_remote_node_name(resource)
    utils.dom_update_meta_attr(
        resource,
        utils.convert_args_to_tuples(meta_values)
    )

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
        op_vars = utils.convert_args_to_tuples(element[1:])

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
            dom, res_id, element, validate_strict=False,
            before_op=updating_op_before
        )

    if len(instance_attributes.getElementsByTagName("nvpair")) == 0:
        instance_attributes.parentNode.removeChild(instance_attributes)

    utils.replace_cib_configuration(dom)

    if (
        remote_node_name
        and
        remote_node_name != utils.dom_get_resource_remote_node_name(resource)
    ):
        # if the resource was a remote node and it is not anymore, (or its name
        # changed) we need to tell pacemaker about it
        output, retval = utils.run([
            "crm_node", "--force", "--remove", remote_node_name
        ])

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(res_id)
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

def resource_update_clone_master(
    dom, clone, clone_type, res_id, args, wait, wait_timeout
):
    if clone_type == "clone":
        dom, dummy_clone_id = resource_clone_create(dom, [res_id] + args, True)
    elif clone_type == "master":
        dom, dummy_master_id = resource_master_create(dom, [res_id] + args, True)

    utils.replace_cib_configuration(dom)

    if wait:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(clone.getAttribute("id"))
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

    return dom

def resource_operation_add(
    dom, res_id, argv, validate=True, validate_strict=True, before_op=None
):
    if len(argv) < 1:
        usage.resource(["op"])
        sys.exit(1)

    res_el = utils.dom_get_resource(dom, res_id)
    if not res_el:
        utils.err ("Unable to find resource: %s" % res_id)

    op_name = argv.pop(0)
    op_properties = utils.convert_args_to_tuples(argv)

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
            duplicate_op_list = utils.operation_exists(operations, op_el)
            if duplicate_op_list:
                utils.err(
                    "operation %s with interval %ss already specified for %s:\n%s"
                    % (
                        op_el.getAttribute("name"),
                        timeout_to_seconds(
                            op_el.getAttribute("interval"), True
                        ),
                        res_id,
                        "\n".join([
                            operation_to_string(op) for op in duplicate_op_list
                        ])
                    )
                )
            if validate_strict and "--force" not in utils.pcs_options:
                duplicate_op_list = utils.operation_exists_by_name(
                    operations, op_el
                )
                if duplicate_op_list:
                    msg = ("operation {action} already specified for {res}"
                        + ", use --force to override:\n{op}")
                    utils.err(msg.format(
                        action=op_el.getAttribute("name"),
                        res=res_id,
                        op="\n".join([
                            operation_to_string(op) for op in duplicate_op_list
                        ])
                    ))

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

    op_properties = utils.convert_args_to_tuples(argv)
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
    resource_el = utils.dom_get_any_resource(dom, res_id)

    if resource_el is None:
        utils.err("unable to find a resource/clone/master/group: %s" % res_id)

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    remote_node_name = utils.dom_get_resource_remote_node_name(resource_el)
    utils.dom_update_meta_attr(resource_el, utils.convert_args_to_tuples(argv))

    utils.replace_cib_configuration(dom)

    if (
        remote_node_name
        and
        remote_node_name != utils.dom_get_resource_remote_node_name(resource_el)
    ):
        # if the resource was a remote node and it is not anymore, (or its name
        # changed) we need to tell pacemaker about it
        output, retval = utils.run([
            "crm_node", "--force", "--remove", remote_node_name
        ])

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(res_id)
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

def convert_args_to_meta_attrs(meta_attrs, ra_id):
    if len(meta_attrs) == 0:
        return []

    meta_vars = []
    tuples = utils.convert_args_to_tuples(meta_attrs)
    attribute_id = ra_id + "-meta_attributes"
    for (a,b) in tuples:
        meta_vars.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("meta_attributes", [[("id"), (attribute_id)]], meta_vars)
    return [ret]

def convert_args_to_instance_variables(ra_values, ra_id):
    tuples = utils.convert_args_to_tuples(ra_values)
    ivs = []
    attribute_id = ra_id + "-instance_attributes"
    for (a,b) in tuples:
        ivs.append(("nvpair",[("name",a),("value",b),("id",attribute_id+"-"+a)],[]))
    ret = ("instance_attributes", [[("id"),(attribute_id)]], ivs)
    return [ret]

def split_resource_agent_name(full_agent_name):
    match = re.match(
        "^(?P<standard>[^:]+)(:(?P<provider>[^:]+))?:(?P<type>[^:]+)$",
        full_agent_name
    )
    if not match:
        utils.err(
            "Invalid resource agent name '{0}'".format(
                full_agent_name
            )
        )
    parts = [
        ("class", match.group("standard")),
        ("type", match.group("type")),
    ]
    if match.group("provider"):
        parts.append(
            ("provider", match.group("provider"))
        )
    return parts


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

        if "--wait" in utils.pcs_options:
            wait_timeout = utils.validate_wait_get_timeout()

        utils.replace_cib_configuration(cib)

        if "--wait" in utils.pcs_options:
            args = ["crm_resource", "--wait"]
            if wait_timeout:
                args.extend(["--timeout=%s" % wait_timeout])
            output, retval = utils.run(args)
            running_on = utils.resource_running_on(group_name)
            if retval == 0:
                print(running_on["message"])
            else:
                msg = []
                if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                    msg.append("waiting timeout")
                if output:
                    msg.append("\n" + output)
                utils.err("\n".join(msg).strip())

    elif (group_cmd == "list"):
        resource_group_list(argv)
    elif (group_cmd in ["remove","delete"]):
        if (len(argv) < 1):
            usage.resource("group")
            sys.exit(1)
        group_name = argv.pop(0)
        resource_ids = argv

        cib_dom = resource_group_rm(
            utils.get_cib_dom(), group_name, resource_ids
        )

        if "--wait" in utils.pcs_options:
            wait_timeout = utils.validate_wait_get_timeout()

        utils.replace_cib_configuration(cib_dom)

        if "--wait" in utils.pcs_options:
            args = ["crm_resource", "--wait"]
            if wait_timeout:
                args.extend(["--timeout=%s" % wait_timeout])
            output, retval = utils.run(args)
            if retval != 0:
                msg = []
                if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                    msg.append("waiting timeout")
                if output:
                    msg.append("\n" + output)
                utils.err("\n".join(msg).strip())

    else:
        usage.resource()
        sys.exit(1)

def resource_clone(argv):
    if len(argv) < 1:
        usage.resource()
        sys.exit(1)

    res = argv[0]
    cib_dom = utils.get_cib_dom()

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    cib_dom, clone_id = resource_clone_create(cib_dom, argv)
    cib_dom = constraint.constraint_resource_update(res, cib_dom)
    utils.replace_cib_configuration(cib_dom)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(clone_id)
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

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

    if update_existing:
        if element.parentNode.tagName != "clone":
            utils.err("%s is not currently a clone" % name)
        clone = element.parentNode
    else:
        clone = cib_dom.createElement("clone")
        clone.setAttribute("id", utils.find_unique_id(cib_dom, name + "-clone"))
        clone.appendChild(element)
        re.appendChild(clone)

    generic_values, op_values, meta_values = parse_resource_options(argv)
    if op_values:
        utils.err("op settings must be changed on base resource, not the clone")
    final_meta = prepare_options(generic_values + meta_values)
    utils.dom_update_meta_attr(clone, sorted(final_meta.items()))

    return cib_dom, clone.getAttribute("id")

def resource_clone_master_remove(argv):
    if len(argv) != 1:
        usage.resource()
        sys.exit(1)

    name = argv.pop()
    dom = utils.get_cib_dom()
    re = dom.documentElement.getElementsByTagName("resources")[0]

    # get the resource no matter if user entered a clone or a cloned resource
    resource = (
        utils.dom_get_resource(re, name)
        or
        utils.dom_get_group(re, name)
        or
        utils.dom_get_clone_ms_resource(re, name)
    )
    if not resource:
        utils.err("could not find resource: %s" % name)
    resource_id = resource.getAttribute("id")
    clone = utils.dom_get_resource_clone_ms_parent(re, resource_id)
    if not clone:
        utils.err("'%s' is not a clone resource" % name)

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    # if user requested uncloning a resource contained in a cloned group
    # remove the resource from the group and leave the clone itself alone
    # unless the resource is the last one in the group
    clone_child = utils.dom_get_clone_ms_resource(re, clone.getAttribute("id"))
    if (
        clone_child.tagName == "group"
        and
        resource.tagName != "group"
        and
        len(clone_child.getElementsByTagName("primitive")) > 1
    ):
        resource_group_rm(dom, clone_child.getAttribute("id"), [resource_id])
    else:
        remove_resource_references(dom, clone.getAttribute("id"))
        clone.parentNode.appendChild(resource)
        clone.parentNode.removeChild(clone)
    utils.replace_cib_configuration(dom)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(resource_id)
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

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
        master_id = None
    else:
        master_id = argv.pop(0)
        res_id = argv[0]
    cib_dom = utils.get_cib_dom()

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    cib_dom, master_id = resource_master_create(cib_dom, argv, False, master_id)
    cib_dom = constraint.constraint_resource_update(res_id, cib_dom)
    utils.replace_cib_configuration(cib_dom)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(master_id)
        if retval == 0:
            print(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

def resource_master_create(dom, argv, update=False, master_id=None):
    master_id_autogenerated = False
    if update:
        master_id = argv.pop(0)
    elif not master_id:
        master_id = argv[0] + "-master"
        master_id_autogenerated = True

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
        if not master_id_autogenerated and utils.does_id_exist(dom, master_id):
            utils.err("%s already exists in the cib" % master_id)

        if utils.dom_get_resource_clone(dom, rg_id):
            utils.err("%s is already a clone resource" % rg_id)

        if utils.dom_get_resource_masterslave(dom, rg_id):
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
        if master_id_autogenerated:
            master_element.setAttribute(
                "id", utils.find_unique_id(dom, master_id)
            )
        else:
            master_element.setAttribute("id", master_id)
        resource.parentNode.removeChild(resource)
        master_element.appendChild(resource)
        resources.appendChild(master_element)

    if len(argv) > 0:
        generic_values, op_values, meta_values = parse_resource_options(argv)
        if op_values:
            utils.err("op settings must be changed on base resource, not the master")
        final_meta = prepare_options(generic_values + meta_values)
        utils.dom_update_meta_attr(master_element, list(final_meta.items()))

    return dom, master_element.getAttribute("id")

def resource_remove(resource_id, output = True):
    dom = utils.get_cib_dom()
    # if resource is a clone or a master, work with its child instead
    cloned_resource = utils.dom_get_clone_ms_resource(dom, resource_id)
    if cloned_resource:
        resource_id = cloned_resource.getAttribute("id")

    if utils.does_exist('//group[@id="'+resource_id+'"]'):
        print("Removing group: " + resource_id + " (and all resources within group)")
        group = utils.get_cib_xpath('//group[@id="'+resource_id+'"]')
        group_dom = parseString(group)
        print("Stopping all resources in group: %s..." % resource_id)
        resource_disable([resource_id])
        if "--force" not in utils.pcs_options and not utils.usefile:
            output, retval = utils.run(["crm_resource", "--wait"])
            if retval != 0 and "unrecognized option '--wait'" in output:
                output = ""
                retval = 0
                for res in reversed(
                    group_dom.documentElement.getElementsByTagName("primitive")
                ):
                    res_id = res.getAttribute("id")
                    res_stopped = False
                    for _ in range(15):
                        time.sleep(1)
                        if not utils.resource_running_on(res_id)["is_running"]:
                            res_stopped = True
                            break
                    if not res_stopped:
                        break
            stopped = True
            state = utils.getClusterState()
            for res in group_dom.documentElement.getElementsByTagName("primitive"):
                res_id = res.getAttribute("id")
                if utils.resource_running_on(res_id, state)["is_running"]:
                    stopped = False
                    break
            if not stopped:
                msg = [
                    "Unable to stop group: %s before deleting "
                    "(re-run with --force to force deletion)"
                    % resource_id
                ]
                if retval != 0 and output:
                    msg.append("\n" + output)
                utils.err("\n".join(msg).strip())
        for res in group_dom.documentElement.getElementsByTagName("primitive"):
            resource_remove(res.getAttribute("id"))
        sys.exit(0)

    # now we know resource is not a group, a clone nor a master
    # because of the conditions above
    if not utils.does_exist('//resources/descendant::primitive[@id="'+resource_id+'"]'):
        utils.err("Resource '{0}' does not exist.".format(resource_id))

    group_xpath = '//group/primitive[@id="'+resource_id+'"]/..'
    group = utils.get_cib_xpath(group_xpath)
    num_resources_in_group = 0

    if (group != ""):
        num_resources_in_group = len(parseString(group).documentElement.getElementsByTagName("primitive"))

    if (
        "--force" not in utils.pcs_options
        and
        not utils.usefile
        and
        utils.resource_running_on(resource_id)["is_running"]
    ):
        sys.stdout.write("Attempting to stop: "+ resource_id + "...")
        sys.stdout.flush()
        resource_disable([resource_id])
        output, retval = utils.run(["crm_resource", "--wait"])
        if retval != 0 and "unrecognized option '--wait'" in output:
            output = ""
            retval = 0
            for _ in range(15):
                time.sleep(1)
                if not utils.resource_running_on(resource_id)["is_running"]:
                    break
        if utils.resource_running_on(resource_id)["is_running"]:
            msg = [
                "Unable to stop: %s before deleting "
                "(re-run with --force to force deletion)"
                % resource_id
            ]
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())
        print("Stopped")

    utils.replace_cib_configuration(
        remove_resource_references(utils.get_cib_dom(), resource_id, output)
    )
    dom = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(dom, resource_id)
    remote_node_name = None
    if resource_el:
        remote_node_name = utils.dom_get_resource_remote_node_name(resource_el)
        if remote_node_name:
            dom = constraint.remove_constraints_containing_node(
                dom, remote_node_name, output
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
            print("Deleting Resource - " + resource_id)
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
            utils.replace_cib_configuration(
                remove_resource_references(
                    utils.get_cib_dom(),
                    to_remove_dom[0].getElementsByTagName("group")[0].getAttribute("id")
                )
            )
        elif top_clone != "":
            to_remove_xpath = top_clone_xpath
            msg = "and group and clone"
            to_remove_dom = parseString(top_clone).getElementsByTagName("clone")
            to_remove_id = to_remove_dom[0].getAttribute("id")
            utils.replace_cib_configuration(
                remove_resource_references(
                    utils.get_cib_dom(),
                    to_remove_dom[0].getElementsByTagName("group")[0].getAttribute("id")
                )
            )
        else:
            to_remove_xpath = group_xpath
            msg = "and group"
            to_remove_dom = parseString(group).getElementsByTagName("group")
            to_remove_id = to_remove_dom[0].getAttribute("id")

        utils.replace_cib_configuration(
            remove_resource_references(
                utils.get_cib_dom(), to_remove_id, output
            )
        )

        args = ["cibadmin", "-o", "resources", "-D", "--xpath", to_remove_xpath]
        if output == True:
            print("Deleting Resource ("+msg+") - " + resource_id)
        dummy_cmdoutput,retVal = utils.run(args)
        if retVal != 0:
            if output == True:
                utils.err("Unable to remove resource '%s' (do constraints exist?)" % (resource_id))
            return False
    if remote_node_name and not utils.usefile:
        output, retval = utils.run([
            "crm_node", "--force", "--remove", remote_node_name
        ])
    return True

def stonith_level_rm_device(cib_dom, stn_id):
    topology_el_list = cib_dom.getElementsByTagName("fencing-topology")
    if not topology_el_list:
        return cib_dom
    topology_el = topology_el_list[0]
    for level_el in topology_el.getElementsByTagName("fencing-level"):
        device_list = level_el.getAttribute("devices").split(",")
        if stn_id in device_list:
            new_device_list = [dev for dev in device_list if dev != stn_id]
            if new_device_list:
                level_el.setAttribute("devices", ",".join(new_device_list))
            else:
                level_el.parentNode.removeChild(level_el)
    if not topology_el.getElementsByTagName("fencing-level"):
        topology_el.parentNode.removeChild(topology_el)
    return cib_dom


def remove_resource_references(
    dom, resource_id, output=False, constraints_element=None
):
    constraint.remove_constraints_containing(
        resource_id, output, constraints_element, dom
    )
    stonith_level_rm_device(dom, resource_id)
    lib_acl.dom_remove_permissions_referencing(dom, resource_id)
    return dom

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(cib_dom, group_name, resource_ids):
    dom = cib_dom.getElementsByTagName("configuration")[0]

    all_resources = len(resource_ids) == 0

    group_match = utils.dom_get_group(dom, group_name)
    if not group_match:
        utils.err("Group '%s' does not exist" % group_name)

    if group_match.parentNode.tagName == "master" and group_match.getElementsByTagName("primitive").length > 1:
        utils.err("Groups that have more than one resource and are master/slave resources cannot be removed.  The group may be deleted with 'pcs resource delete %s'." % group_name)

    resources_to_move = []

    if all_resources:
        for resource in group_match.getElementsByTagName("primitive"):
            resources_to_move.append(resource)
    else:
        for resource_id in resource_ids:
            resource = utils.dom_get_resource(group_match, resource_id)
            if resource:
                resources_to_move.append(resource)
            else:
                utils.err("Resource '%s' does not exist in group '%s'" % (resource_id, group_name))

    if group_match.parentNode.tagName in ["clone", "master"]:
        res_in_group = len(group_match.getElementsByTagName("primitive"))
        if (
            res_in_group > 1
            and
            (all_resources or (len(resources_to_move) == res_in_group))
        ):
            utils.err("Cannot remove more than one resource from cloned group")

    target_node = group_match.parentNode
    if (
        target_node.tagName in ["clone", "master"]
        and
        len(group_match.getElementsByTagName("primitive")) > 1
    ):
        target_node = dom.getElementsByTagName("resources")[0]
    for resource in resources_to_move:
        resource.parentNode.removeChild(resource)
        target_node.appendChild(resource)

    if len(group_match.getElementsByTagName("primitive")) == 0:
        group_match.parentNode.removeChild(group_match)
        remove_resource_references(dom, group_name, output=True)

    return cib_dom

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
            if (
                oldParent.tagName == "group"
                and
                len(oldParent.getElementsByTagName("primitive")) == 0
            ):
                if oldParent.parentNode.tagName in ["clone", "master"]:
                    oldParent.parentNode.parentNode.removeChild(
                        oldParent.parentNode
                    )
                else:
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
        line_parts = [e.getAttribute("id") + ":"]
        for resource in e.getElementsByTagName("primitive"):
            line_parts.append(resource.getAttribute("id"))
        print(" ".join(line_parts))

def resource_show(argv, stonith=False):
    mutually_exclusive_opts = ("--full", "--groups", "--hide-inactive")
    modifiers = [
        key for key in utils.pcs_options if key in mutually_exclusive_opts
    ]
    if (len(modifiers) > 1) or (argv and modifiers):
        utils.err(
            "you can specify only one of resource id, {0}".format(
                ", ".join(mutually_exclusive_opts)
            )
        )

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
        monitor_command = ["crm_mon", "--one-shot"]
        if "--hide-inactive" not in utils.pcs_options:
            monitor_command.append('--inactive')
        output, retval = utils.run(monitor_command)
        if retval != 0:
            utils.err("unable to get cluster status from crm_mon\n"+output.rstrip())
        preg = re.compile(r'.*(stonith:.*)')
        resources_header = False
        in_resources = False
        has_resources = False
        no_resources_line = (
            "NO stonith devices configured" if stonith
            else "NO resources configured"
        )
        for line in output.split('\n'):
            if line == "No active resources":
                print(line)
                return
            if line == "No resources":
                print(no_resources_line)
                return
            if line in ("Full list of resources:", "Active resources:"):
                resources_header = True
                continue
            if line == "":
                if resources_header:
                    resources_header = False
                    in_resources = True
                elif in_resources:
                    if not has_resources:
                        print(no_resources_line)
                    return
                continue
            if in_resources:
                if not preg.match(line) and not stonith:
                    has_resources = True
                    print(line)
                elif preg.match(line) and stonith:
                    has_resources = True
                    print(line)
        return

    root = utils.get_cib_etree()
    resources = root.find(".//resources")
    resource_found = False
    for arg in argv:
        for child in resources.findall(str(".//*")):
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
        print("Warning: '%s' is unmanaged" % resource)

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    args = ["crm_resource", "-r", argv[0], "-m", "-p", "target-role", "-v", "Stopped"]
    output, retval = utils.run(args)
    if retval != 0:
        utils.err(output)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(resource)
        if retval == 0 and not running_on["is_running"]:
            print(running_on["message"])
            return True
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            else:
                msg.append(
                    "unable to stop: '%s', please check logs for failure "
                    "information"
                    % resource
                )
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

def resource_enable(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to enable")

    resource = argv[0]
    cib_dom = utils.get_cib_dom()

    resource_clone = (
        utils.dom_get_clone(cib_dom, resource)
        or
        utils.dom_get_master(cib_dom, resource)
    )
    if resource_clone:
        resource_main = utils.dom_elem_get_clone_ms_resource(resource_clone)
    else:
        resource_main = (
            utils.dom_get_resource(cib_dom, resource)
            or
            utils.dom_get_group(cib_dom, resource)
        )
        if not resource_main:
            utils.err(
                "unable to find a resource/clone/master/group: {0}".format(
                    resource
                )
            )
        resource_clone = utils.dom_elem_get_resource_clone_ms_parent(
            resource_main
        )
    resources_to_enable = [resource_main.getAttribute("id")]
    if resource_clone:
        resources_to_enable.append(resource_clone.getAttribute("id"))

    for res in resources_to_enable:
        if not is_managed(res):
            print("Warning: '{0}' is unmanaged".format(res))

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    for res in resources_to_enable:
        args = ["crm_resource", "-r", res, "-m", "-d", "target-role"]
        output, retval = utils.run(args)
        if retval != 0:
            utils.err (output)

    if "--wait" in utils.pcs_options:
        args = ["crm_resource", "--wait"]
        if wait_timeout:
            args.extend(["--timeout=%s" % wait_timeout])
        output, retval = utils.run(args)
        running_on = utils.resource_running_on(resource)
        if retval == 0 and running_on["is_running"]:
            print(running_on["message"])
            return True
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            else:
                msg.append(
                    "unable to start: '%s', please check logs for failure "
                    "information"
                    % resource
                )
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())

def resource_restart(argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to restart")

    dom = utils.get_cib_dom()
    node = None
    resource = argv.pop(0)

    real_res = utils.dom_get_resource_clone_ms_parent(dom, resource)
    if real_res:
        print("Warning: using %s... (if a resource is a clone or master/slave you must use the clone or master/slave name" % real_res.getAttribute("id"))
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

    print("%s successfully restarted" % resource)

def resource_force_action(action, argv):
    if len(argv) < 1:
        utils.err("You must specify a resource to {0}".format(action))
    if len(argv) != 1:
        usage.resource([action])
        sys.exit(1)

    action_command = {
        "debug-start": "--force-start",
        "debug-stop": "--force-stop",
        "debug-promote": "--force-promote",
        "debug-demote": "--force-demote",
        "debug-monitor": "--force-check",
    }

    if action not in action_command:
        usage.resource(["debug-"])
        sys.exit(1)

    resource = argv[0]
    dom = utils.get_cib_dom()

    if not utils.dom_get_any_resource(dom, resource):
        utils.err(
            "unable to find a resource/clone/master/group: {0}".format(resource)
        )
    if utils.dom_get_group(dom, resource):
        group_resources = utils.get_group_children(resource)
        utils.err(
            "unable to {0} a group, try one of the group's resource(s) ({1})".format(
                action, ",".join(group_resources)
            )
        )
    if utils.dom_get_clone(dom, resource):
        clone_resource = utils.dom_get_clone_ms_resource(dom, resource)
        utils.err(
            "unable to {0} a clone, try the clone's resource: {1}".format(
                action, clone_resource.getAttribute("id")
            )
        )
    if utils.dom_get_master(dom, resource):
        master_resource = utils.dom_get_clone_ms_resource(dom, resource)
        utils.err(
            "unable to {0} a master, try the master's resource: {1}".format(
                action, master_resource.getAttribute("id")
            )
        )

    args = ["crm_resource", "-r", resource, action_command[action]]
    if "--full" in utils.pcs_options:
        args.append("-V")
    if "--force" in utils.pcs_options:
        args.append("--force")
    output, retval = utils.run(args)

    if "doesn't support group resources" in output:
        utils.err("groups are not supported")
        sys.exit(retval)
    if "doesn't support stonith resources" in output:
        utils.err("stonith devices are not supported")
        sys.exit(retval)

    print(output, end="")
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
            # Remove the meta attribute from the id specified (and all children)
            xpath = "(//primitive|//group|//clone|//master)[@id='"+resource+"']//meta_attributes/nvpair[@name='is-managed']"
            utils.run(["cibadmin", "-d", "--xpath", xpath, "--force"])
            # Remove the meta attribute from the parent of the id specified, if the parent is a clone or master
            xpath = "(//master|//clone)[(group|primitive)[@id='"+resource+"']]/meta_attributes/nvpair[@name='is-managed']"
            utils.run(["cibadmin", "-D", "--xpath", xpath])
            if isGroup:
                for res in res_to_manage:
                    xpath = "(//primitive|//group|//clone|//master)[@id='"+res+"']/meta_attributes/nvpair[@name='is-managed']"
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
                    output_dict[ta_node] = " " + ta_node + ": " + nvp.getAttribute("value")
                break

    if resource_command == "reset":
        if fail_counts_removed == 0:
            print("No failcounts needed resetting")
    if resource_command == "show":
        output = []
        for key in sorted(output_dict.keys()):
            output.append(output_dict[key])


        if not output:
            if all_nodes:
                print("No failcounts for %s" % resource)
            else:
                print("No failcounts for %s on %s" % (resource,node))
        else:
            if all_nodes:
                print("Failcounts for %s" % resource)
            else:
                print("Failcounts for %s on %s" % (resource,node))
            print("\n".join(output))


def show_defaults(def_type, indent=""):
    dom = utils.get_cib_dom()
    defs = dom.getElementsByTagName(def_type)
    if len(defs) > 0:
        defs = defs[0]
    else:
        print(indent + "No defaults set")
        return

    foundDefault = False
    for d in defs.getElementsByTagName("nvpair"):
        print(indent + d.getAttribute("name") + ": " + d.getAttribute("value"))
        foundDefault = True

    if not foundDefault:
        print(indent + "No defaults set")

def set_default(def_type, argv):
    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            print("Invalid Property: " + arg)
            continue
        utils.setAttribute(def_type, args[0], args[1], exit_on_error=True)

def print_node(node, tab = 0):
    spaces = " " * tab
    if node.tag == "group":
        print(spaces + "Group: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
    if node.tag == "clone":
        print(spaces + "Clone: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
    if node.tag == "primitive":
        print(spaces + "Resource: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_utilization_string(node, spaces)
        print_operations(node, spaces)
    if node.tag == "master":
        print(spaces + "Master: " + node.attrib["id"] + get_attrs(node, ' (', ')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)

def print_utilization_string(element, spaces):
    output = []
    mvars = element.findall("utilization/nvpair")
    for mvar in mvars:
        output.append(mvar.attrib["name"] + "=" + mvar.attrib["value"])
    if output:
        print(spaces + " Utilization: " + " ".join(output))

def print_instance_vars_string(node, spaces):
    output = []
    ivars = node.findall(str("instance_attributes/nvpair"))
    for ivar in ivars:
        name = ivar.attrib["name"]
        value = ivar.attrib["value"]
        if " " in value:
            value = '"' + value + '"'
        output.append(name + "=" + value)
    if output:
        print(spaces + " Attributes: " + " ".join(output))

def print_meta_vars_string(node, spaces):
    output = ""
    mvars = node.findall(str("meta_attributes/nvpair"))
    for mvar in mvars:
        output += mvar.attrib["name"] + "=" + mvar.attrib["value"] + " "
    if output != "":
        print(spaces + " Meta Attrs: " + output)

def print_operations(node, spaces):
    indent = len(spaces) + len(" Operations: ")
    output = ""
    ops = node.findall(str("operations/op"))
    first = True
    for op in ops:
        if not first:
            output += ' ' * indent
        else:
            first = False
        output += op.attrib["name"] + " "
        for attr,val in sorted(op.attrib.items()):
            if attr in ["id","name"] :
                continue
            output += attr + "=" + val + " "
        for child in op.findall(str(".//nvpair")):
            output += child.get("name") + "=" + child.get("value") + " "

        output += "(" + op.attrib["id"] + ")"
        output += "\n"

    output = output.rstrip()
    if output != "":
        print(spaces + " Operations: " + output)

def operation_to_string(op_el):
    parts = []
    parts.append(op_el.getAttribute("name"))
    for name, value in sorted(op_el.attributes.items()):
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

def resource_cleanup(argv):
    resource = None
    node = None

    if len(argv) > 1:
        raise CmdLineInputError()
    if argv:
        resource = argv[0]
    if "--node" in utils.pcs_options:
        node = utils.pcs_options["--node"]
    force = "--force" in utils.pcs_options

    print(lib_pacemaker.resource_cleanup(
        utils.cmd_runner(), resource, node, force
    ))

def resource_history(args):
    dom = utils.get_cib_dom()
    resources = {}
    lrm_res = dom.getElementsByTagName("lrm_resource")
    for res in lrm_res:
        res_id = res.getAttribute("id")
        if res_id not in resources:
            resources[res_id] = {}
        for rsc_op in res.getElementsByTagName("lrm_rsc_op"):
            resources[res_id][rsc_op.getAttribute("call-id")] = [res_id, rsc_op]

    for res in sorted(resources):
        print("Resource: %s" % res)
        for cid in sorted(resources[res]):
            (last_date, dummy_retval) = utils.run(["date","-d", "@" + resources[res][cid][1].getAttribute("last-rc-change")])
            last_date = last_date.rstrip()
            rc_code = resources[res][cid][1].getAttribute("rc-code")
            operation = resources[res][cid][1].getAttribute("operation")
            if rc_code != "0":
                print("  Failed on %s" % last_date)
            elif operation == "stop":
                print("  Stopped on node xx on %s" % last_date)
            elif operation == "start":
                print("  Started on node xx %s" % last_date)

def resource_relocate(argv):
    if len(argv) < 1:
        usage.resource(["relocate"])
        sys.exit(1)
    cmd = argv.pop(0)
    if cmd == "show":
        if argv:
            usage.resource(["relocate show"])
            sys.exit(1)
        resource_relocate_show(utils.get_cib_dom())
    elif cmd == "dry-run":
        resource_relocate_run(utils.get_cib_dom(), argv, True)
    elif cmd == "run":
        resource_relocate_run(utils.get_cib_dom(), argv, False)
    elif cmd == "clear":
        if argv:
            usage.resource(["relocate clear"])
            sys.exit(1)
        utils.replace_cib_configuration(
            resource_relocate_clear(utils.get_cib_dom())
        )
    else:
        usage.resource(["relocate"])
        sys.exit(1)

def resource_relocate_set_stickiness(cib_dom, resources=None):
    resources = [] if resources is None else resources
    cib_dom = cib_dom.cloneNode(True) # do not change the original cib
    resources_found = set()
    updated_resources = set()
    # set stickiness=0
    for tagname in ("master", "clone", "group", "primitive"):
        for res_el in cib_dom.getElementsByTagName(tagname):
            if resources and res_el.getAttribute("id") not in resources:
                continue
            resources_found.add(res_el.getAttribute("id"))
            res_and_children = (
                [res_el]
                +
                res_el.getElementsByTagName("group")
                +
                res_el.getElementsByTagName("primitive")
            )
            updated_resources.update(
                [el.getAttribute("id") for el in res_and_children]
            )
            for res_or_child in res_and_children:
                meta_attributes = utils.dom_prepare_child_element(
                    res_or_child,
                    "meta_attributes",
                    res_or_child.getAttribute("id") + "-meta_attributes"
                )
                utils.dom_update_nv_pair(
                    meta_attributes,
                    "resource-stickiness",
                    "0",
                    meta_attributes.getAttribute("id") + "-"
                )
    # resources don't exist
    if resources:
        resources_not_found = set(resources) - resources_found
        if resources_not_found:
            for res_id in resources_not_found:
                utils.err(
                    "unable to find a resource/clone/master/group: {0}".format(
                        res_id
                    ),
                    False
                )
            sys.exit(1)
    return cib_dom, updated_resources

def resource_relocate_get_locations(cib_dom, resources=None):
    resources = [] if resources is None else resources
    updated_cib, updated_resources = resource_relocate_set_stickiness(
        cib_dom, resources
    )
    dummy_simout, transitions, new_cib = utils.simulate_cib(updated_cib)
    operation_list = utils.get_operations_from_transitions(transitions)
    locations = utils.get_resources_location_from_operations(
        new_cib, operation_list
    )
    # filter out non-requested resources
    if not resources:
        return list(locations.values())
    return [
        val for val in locations.values()
        if val["id"] in updated_resources
            or val["id_for_constraint"] in updated_resources
    ]

def resource_relocate_show(cib_dom):
    updated_cib, dummy_updated_resources = resource_relocate_set_stickiness(cib_dom)
    simout, dummy_transitions, dummy_new_cib = utils.simulate_cib(updated_cib)
    in_status = False
    in_status_resources = False
    in_transitions = False
    for line in simout.split("\n"):
        if line.strip() == "Current cluster status:":
            in_status = True
            in_status_resources = False
            in_transitions = False
        elif line.strip() == "Transition Summary:":
            in_status = False
            in_status_resources = False
            in_transitions = True
            print()
        elif line.strip() == "":
            if in_status:
                in_status = False
                in_status_resources = True
                in_transitions = False
            else:
                in_status = False
                in_status_resources = False
                in_transitions = False
        if in_status or in_status_resources or in_transitions:
            print(line)

def resource_relocate_location_to_str(location):
    message = "Creating location constraint: {res} prefers {node}=INFINITY{role}"
    if "start_on_node" in location:
        return message.format(
            res=location["id_for_constraint"], node=location["start_on_node"],
            role=""
        )
    if "promote_on_node" in location:
        return message.format(
            res=location["id_for_constraint"], node=location["promote_on_node"],
            role=" role=Master"
        )
    return ""

def resource_relocate_run(cib_dom, resources=None, dry=True):
    resources = [] if resources is None else resources
    error = False
    anything_changed = False
    if not dry:
        utils.check_pacemaker_supports_resource_wait()
        if utils.usefile:
            utils.err("This command cannot be used with -f")

    # create constraints
    cib_dom, constraint_el = constraint.getCurrentConstraints(cib_dom)
    for location in resource_relocate_get_locations(cib_dom, resources):
        if not("start_on_node" in location or "promote_on_node" in location):
            continue
        anything_changed = True
        print(resource_relocate_location_to_str(location))
        constraint_id = utils.find_unique_id(
            cib_dom,
            RESOURCE_RELOCATE_CONSTRAINT_PREFIX + location["id_for_constraint"]
        )
        new_constraint = cib_dom.createElement("rsc_location")
        new_constraint.setAttribute("id", constraint_id)
        new_constraint.setAttribute("rsc", location["id_for_constraint"])
        new_constraint.setAttribute("score", "INFINITY")
        if "promote_on_node" in location:
            new_constraint.setAttribute("node", location["promote_on_node"])
            new_constraint.setAttribute("role", "Master")
        elif "start_on_node" in location:
            new_constraint.setAttribute("node", location["start_on_node"])
        constraint_el.appendChild(new_constraint)
    if not anything_changed:
        return
    if not dry:
        utils.replace_cib_configuration(cib_dom)

    # wait for resources to move
    print()
    print("Waiting for resources to move...")
    print()
    if not dry:
        output, retval = utils.run(["crm_resource", "--wait"])
        if retval != 0:
            error = True
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                utils.err("waiting timeout", False)
            else:
                utils.err(output, False)

    # remove constraints
    resource_relocate_clear(cib_dom)
    if not dry:
        utils.replace_cib_configuration(cib_dom)

    if error:
        sys.exit(1)

def resource_relocate_clear(cib_dom):
    for constraint_el in cib_dom.getElementsByTagName("constraints"):
        for location_el in constraint_el.getElementsByTagName("rsc_location"):
            location_id = location_el.getAttribute("id")
            if location_id.startswith(RESOURCE_RELOCATE_CONSTRAINT_PREFIX):
                print("Removing constraint {0}".format(location_id))
                location_el.parentNode.removeChild(location_el)
    return cib_dom

def set_resource_utilization(resource_id, argv):
    cib = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(cib, resource_id)
    if resource_el is None:
        utils.err("Unable to find a resource: {0}".format(resource_id))
    utils.dom_update_utilization(resource_el, prepare_options(argv))
    utils.replace_cib_configuration(cib)

def print_resource_utilization(resource_id):
    cib = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(cib, resource_id)
    if resource_el is None:
        utils.err("Unable to find a resource: {0}".format(resource_id))
    utilization = utils.get_utilization_str(resource_el)

    print("Resource Utilization:")
    print(" {0}: {1}".format(resource_id, utilization))

def print_resources_utilization():
    cib = utils.get_cib_dom()
    utilization = {}
    for resource_el in cib.getElementsByTagName("primitive"):
        u = utils.get_utilization_str(resource_el)
        if u:
            utilization[resource_el.getAttribute("id")] = u

    print("Resource Utilization:")
    for resource in sorted(utilization):
        print(" {0}: {1}".format(resource, utilization[resource]))


def get_resource_agent_info(argv):
# This is used only by pcsd, will be removed in new architecture
    if len(argv) != 1:
        utils.err("One parameter expected")

    agent = argv[0]

    runner = utils.cmd_runner()

    try:
        metadata = lib_ra.ResourceAgent(runner, agent)
        print(json.dumps(metadata.get_full_info()))
    except lib_ra.ResourceAgentError as e:
        utils.process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e)]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)
