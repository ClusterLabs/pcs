# pylint: disable=too-many-lines
import sys
import xml.dom.minidom
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
from pcs.cli.common.console_report import error, warn
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import prepare_options
from pcs.cli.resource.parse_args import (
    parse_bundle_create_options,
    parse_bundle_update_options,
    parse_create as parse_create_args,
)
import pcs.lib.cib.acl as lib_acl
from pcs.lib.cib.resource import (
    bundle,
    guest_node,
)
from pcs.lib.commands.resource import(
    _validate_guest_change,
    _get_nodes_to_validate_against,
)
from pcs.lib.errors import LibraryError, ReportItemSeverity
import pcs.lib.pacemaker.live as lib_pacemaker
from pcs.lib.pacemaker.state import (
    get_cluster_state_dom,
    _get_primitive_roles_with_nodes,
    _get_primitives_for_state_check,
)
from pcs.lib.pacemaker.values import (
    is_true as is_pacemaker_true,
    timeout_to_seconds,
)
import pcs.lib.resource_agent as lib_ra

# pylint: disable=len-as-condition, too-many-branches, too-many-statements, too-many-locals, line-too-long, singleton-comparison, bad-whitespace, redefined-outer-name, invalid-name, unused-argument, too-many-boolean-expressions, inconsistent-return-statements, superfluous-parens, too-many-nested-blocks, no-else-return

RESOURCE_RELOCATE_CONSTRAINT_PREFIX = "pcs-relocate-"

def _detect_guest_change(meta_attributes, allow_not_suitable_command):
    """
    Commandline options:
      * -f - CIB file
    """
    if not guest_node.is_node_name_in_options(meta_attributes):
        return

    env = utils.get_lib_env()
    cib = env.get_cib()
    existing_nodes_names, existing_nodes_addrs = _get_nodes_to_validate_against(
        env,
        cib
    )
    env.report_processor.process_list(
        _validate_guest_change(
            cib,
            existing_nodes_names,
            existing_nodes_addrs,
            meta_attributes,
            allow_not_suitable_command,
            detect_remove=True,
        )
    )

def resource_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        sub_cmd, argv_next = "status", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.resource([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "list":
            resource_list_available(lib, argv_next, modifiers)
        elif sub_cmd == "describe":
            resource_list_options(lib, argv_next, modifiers)
        elif sub_cmd == "create":
            resource_create(lib, argv_next, modifiers)
        elif sub_cmd == "move":
            resource_move(lib, argv_next, modifiers)
        elif sub_cmd == "ban":
            resource_move(lib, argv_next, modifiers, ban=True)
        elif sub_cmd == "clear":
            resource_move(lib, argv_next, modifiers, clear=True)
        elif sub_cmd == "standards":
            resource_standards(lib, argv_next, modifiers)
        elif sub_cmd == "providers":
            resource_providers(lib, argv_next, modifiers)
        elif sub_cmd == "agents":
            resource_agents(lib, argv_next, modifiers)
        elif sub_cmd == "update":
            resource_update(lib, argv_next, modifiers)
        elif sub_cmd == "meta":
            resource_meta(lib, argv_next, modifiers)
        elif sub_cmd in {"delete", "remove"}:
            resource_remove_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "status":
            resource_status(lib, argv_next, modifiers)
        elif sub_cmd == "config":
            resource_config(lib, argv_next, modifiers)
        elif sub_cmd == "group":
            resource_group(lib, argv_next, modifiers)
        elif sub_cmd == "ungroup":
            resource_group(lib, ["remove"] + argv_next, modifiers)
        elif sub_cmd == "clone":
            resource_clone(lib, argv_next, modifiers)
        elif sub_cmd == "promotable":
            resource_clone(lib, argv_next, modifiers, promotable=True)
        elif sub_cmd == "unclone":
            resource_clone_master_remove(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            resource_enable_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "disable":
            resource_disable_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "restart":
            resource_restart(lib, argv_next, modifiers)
        elif sub_cmd in (
            "debug-start", "debug-stop", "debug-promote", "debug-demote",
            "debug-monitor",
        ):
            resource_force_action(lib, [sub_cmd] + argv_next, modifiers)
        elif sub_cmd == "manage":
            resource_manage_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "unmanage":
            resource_unmanage_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "failcount":
            resource_failcount(lib, argv_next, modifiers)
        elif sub_cmd == "op":
            if len(argv_next) < 1:
                raise CmdLineInputError()
            op_subcmd = argv_next.pop(0)
            try:
                if op_subcmd == "defaults":
                    resource_op_defaults_cmd(lib, argv_next, modifiers)
                elif op_subcmd == "add":
                    resource_op_add_cmd(lib, argv_next, modifiers)
                elif op_subcmd in ["remove", "delete"]:
                    resource_op_delete_cmd(lib, argv_next, modifiers)
                else:
                    raise CmdLineInputError()
            except CmdLineInputError as e:
                utils.exit_on_cmdline_input_errror(
                    e, "resource", f"op {op_subcmd}"
                )
        elif sub_cmd == "defaults":
            resource_defaults_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "cleanup":
            resource_cleanup(lib, argv_next, modifiers)
        elif sub_cmd == "refresh":
            resource_refresh(lib, argv_next, modifiers)
        elif sub_cmd == "relocate":
            resource_relocate(lib, argv_next, modifiers)
        elif sub_cmd == "utilization":
            # pylint: disable=pointless-string-statement
            """
            Options:
              * -f - CIB file
            """
            modifiers.ensure_only_supported("-f")
            if len(argv_next) == 0:
                print_resources_utilization()
            elif len(argv_next) == 1:
                print_resource_utilization(argv_next.pop(0))
            else:
                set_resource_utilization(argv_next.pop(0), argv_next)
        elif sub_cmd == "get_resource_agent_info":
            get_resource_agent_info(lib, argv_next, modifiers)
        elif sub_cmd == "bundle":
            resource_bundle_cmd(lib, argv_next, modifiers)
        else:
            sub_cmd = ""
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "resource", sub_cmd)

def resource_defaults_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) == 0:
        show_defaults("rsc_defaults")
    else:
        lib.cib_options.set_resources_defaults(
            prepare_options(argv)
        )


def resource_op_defaults_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) == 0:
        show_defaults("op_defaults")
    else:
        lib.cib_options.set_operations_defaults(
            prepare_options(argv)
        )

def resource_op_add_cmd(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) == 0:
        raise CmdLineInputError()
    else:
        res_id = argv.pop(0)
        utils.replace_cib_configuration(
            resource_operation_add(
                utils.get_cib_dom(), res_id, argv
            )
        )

def resource_op_delete_cmd(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) == 0:
        raise CmdLineInputError()
    else:
        res_id = argv.pop(0)
        resource_operation_remove(res_id, argv)

def parse_resource_options(argv):
    """
    Commandline options: no options
    """
    ra_values = []
    op_values = []
    meta_values = []
    op_args = False
    meta_args = False
    for arg in argv:
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
    return ra_values, op_values, meta_values


def resource_list_available(lib, argv, modifiers):
    """
    Options:
      * --nodesc - don't display description
    """
    modifiers.ensure_only_supported("--nodesc")
    if len(argv) > 1:
        raise CmdLineInputError()

    search = argv[0] if argv else None
    agent_list = lib.resource_agent.list_agents(
        not modifiers.get("--nodesc"), search
    )

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
    """
    Options:
      * --full - show advanced
    """
    modifiers.ensure_only_supported("--full")
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = argv[0]

    print(_format_agent_description(
        lib.resource_agent.describe_agent(agent_name),
        show_all=modifiers.get("--full")
    ))


def _format_agent_description(description, stonith=False, show_all=False):
    """
    Commandline options: no options
    """
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
            # Do not show advanced options, for exmaple
            # pcmk_(reboot|off|list|monitor|status)_(action|timeout|retries)
            # for stonith agents
            if not show_all and param.get("advanced", False):
                continue
            if not show_all and param.get("deprecated", False):
                continue
            param_obsoletes = param.get("obsoletes", None)
            param_deprecated = param.get("deprecated", False)
            param_deprecated_by = param.get("deprecated_by", [])
            param_title = " ".join(filter(None, [
                param.get("name"),
                # only show deprecated if not showing deprecated by
                "(deprecated)"
                    if show_all and param_deprecated and not param_deprecated_by
                    else None
                ,
                "(deprecated by {0})".format(", ".join(param_deprecated_by))
                    if show_all and param_deprecated_by
                    else None
                ,
                "(obsoletes {0})".format(param_obsoletes)
                    if show_all and param_obsoletes
                    else None
                ,
                "(required)" if param.get("required", False) else None,
            ]))
            param_desc = param.get("longdesc", "").replace("\n", " ")
            if not param_desc:
                param_desc = param.get("shortdesc", "").replace("\n", " ")
                if not param_desc:
                    param_desc = "No description available"
            if param.get("pcs_deprecated_warning"):
                param_desc += " WARNING: " + param["pcs_deprecated_warning"]
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
        for action in description["default_actions"]:
            parts = ["  {0}:".format(action.get("name", ""))]
            parts.extend([
                u"{0}={1}".format(name, value)
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
    """
    Commandline options: no options
    """
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

def resource_create(lib, argv, modifiers):
    """
    Options:
      * --before - specified resource inside a group before which new resource
        will be placed inside the group
      * --after - specified resource inside a group after which new resource
        will be placed inside the group
      * --group - specifies group in which resource will be created
      * --force - allow not existing agent, invalid operations or invalid
        instance attributes, allow not suitable command
      * --disabled - created reource will be disabled
      * --no-default-ops - do not add default operations
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported(
        "--before", "--after", "--group", "--force", "--disabled",
        "--no-default-ops", "--wait", "-f",
    )
    if len(argv) < 2:
        raise CmdLineInputError()

    ra_id = argv[0]
    ra_type = argv[1]

    parts = parse_create_args(argv[2:])

    parts_sections = ["clone", "promotable", "bundle"]
    defined_options = [opt for opt in parts_sections if opt in parts]
    if modifiers.is_specified("--group"):
        defined_options.append("group")
    if len(
        set(defined_options).intersection(set(parts_sections + ["group"]))
    ) > 1:
        raise error(
            "you can specify only one of {0} or --group".format(
                ", ".join(parts_sections)
            )
        )

    if "bundle" in parts and len(parts["bundle"]) != 1:
        raise error("you have to specify exactly one bundle")

    if modifiers.is_specified("--before") and modifiers.is_specified("--after"):
        raise error("you cannot specify both --before and --after{0}".format(
            "" if modifiers.is_specified("--group")
            else " and you have to specify --group"
        ))

    if not modifiers.is_specified("--group"):
        if modifiers.is_specified("--before"):
            raise error("you cannot use --before without --group")
        elif modifiers.is_specified("--after"):
            raise error("you cannot use --after without --group")

    if "promotable" in parts and "promotable" in parts["promotable"]:
        raise error(
            "you cannot specify both promotable option and promotable keyword"
        )

    settings = dict(
        allow_absent_agent=modifiers.get("--force"),
        allow_invalid_operation=modifiers.get("--force"),
        allow_invalid_instance_attributes=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        use_default_operations=not modifiers.get("--no-default-ops"),
        wait=modifiers.get("--wait"),
        allow_not_suitable_command=modifiers.get("--force"),
    )

    if "clone" in parts:
        lib.resource.create_as_clone(
            ra_id, ra_type, parts["op"],
            parts["meta"],
            parts["options"],
            parts["clone"],
            **settings
        )
    elif "promotable" in parts:
        lib.resource.create_as_clone(
            ra_id, ra_type, parts["op"],
            parts["meta"],
            parts["options"],
            dict(**parts["promotable"], promotable="true"),
            **settings
        )
    elif "bundle" in parts:
        settings["allow_not_accessible_resource"] = modifiers.get("--force")
        lib.resource.create_into_bundle(
            ra_id, ra_type, parts["op"],
            parts["meta"],
            parts["options"],
            parts["bundle"][0],
            **settings
        )

    elif not modifiers.is_specified("--group"):
        lib.resource.create(
            ra_id, ra_type, parts["op"],
            parts["meta"],
            parts["options"],
            **settings
        )
    else:
        adjacent_resource_id = None
        put_after_adjacent = False
        if modifiers.get("--after"):
            adjacent_resource_id = modifiers.get("--after")
            put_after_adjacent = True
        if modifiers.get("--before"):
            adjacent_resource_id = modifiers.get("--before")
            put_after_adjacent = False

        lib.resource.create_in_group(
            ra_id, ra_type, modifiers.get("--group"), parts["op"],
            parts["meta"],
            parts["options"],
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
            **settings
        )

def resource_move(dummy_lib, argv, modifiers, clear=False, ban=False):
    """
    Options:
      * -f - CIB file
      * --master
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--master", "--wait")
    move = not clear and not ban
    other_options = []
    if len(argv) == 0:
        if clear:
            msg = "must specify a resource to clear"
        elif ban:
            msg = "must specify a resource to ban"
        else:
            msg = "must specify a resource to move"
        utils.err(msg)

    resource_id = argv.pop(0)

    if (clear and len(argv) > 1) or len(argv) > 2:
        if clear:
            usage.resource(["clear"])
        elif ban:
            usage.resource(["ban"])
        else:
            usage.resource(["move"])
        sys.exit(1)

    dest_node = None
    lifetime = None
    while argv:
        arg = argv.pop(0)
        if arg.startswith("lifetime="):
            if lifetime:
                raise CmdLineInputError()
            lifetime = arg.split("=")[1]
            if lifetime and lifetime[0].isdigit():
                lifetime = "P" + lifetime
        elif not dest_node:
            dest_node = arg
        else:
            raise CmdLineInputError()

    if clear and lifetime:
        raise CmdLineInputError()

    dom = utils.get_cib_dom()
    resource_element = (
        utils.dom_get_any_resource(dom, resource_id)
        or
        utils.dom_get_bundle(dom, resource_id)
    )
    if not resource_element:
        utils.err("%s is not a valid resource" % resource_id)

    is_clone = False
    is_in_clone = False
    is_promotable_clone = False
    is_in_promotable_clone = False
    promotable_clone_id = None
    if utils.dom_get_bundle(dom, resource_id):
        is_clone = True
    elif utils.dom_get_clone(dom, resource_id):
        is_clone = True
        meta_promotable = utils.dom_get_meta_attr_value(
            resource_element, "promotable"
        )
        if meta_promotable is not None and is_pacemaker_true(meta_promotable):
            is_promotable_clone = True
            promotable_clone_id = resource_id
    elif utils.dom_get_master(dom, resource_id):
        is_clone = True
        is_promotable_clone = True
        promotable_clone_id = resource_id
    elif (
        utils.dom_get_resource_clone(dom, resource_id)
        or
        utils.dom_get_group_clone(dom, resource_id)
    ):
        is_in_clone = True
        parent = utils.dom_get_resource_clone_ms_parent(dom, resource_id)
        meta_promotable = utils.dom_get_meta_attr_value(parent, "promotable")
        if meta_promotable is not None and is_pacemaker_true(meta_promotable):
            is_in_promotable_clone = True
            promotable_clone_id = parent.getAttribute("id")
    elif (
        utils.dom_get_resource_masterslave(dom, resource_id)
        or
        utils.dom_get_group_masterslave(dom, resource_id)
    ):
        is_in_clone = True
        parent = utils.dom_get_resource_clone_ms_parent(dom, resource_id)
        is_in_promotable_clone = True
        promotable_clone_id = parent.getAttribute("id")

    if (
        move
        and
        (is_clone or is_in_clone)
        and not
        (is_promotable_clone or is_in_promotable_clone)
    ):
        utils.err("cannot move cloned resources")
    if (
        move
        and
        not modifiers.is_specified("--master")
        and
        (is_promotable_clone or is_in_promotable_clone)
    ):
        utils.err(
            "to move promotable clone resources you must use --master "
                "and the clone id (%s)"
            % promotable_clone_id
        )
    if modifiers.is_specified("--master") and not is_promotable_clone:
        if promotable_clone_id:
            utils.err(
                "when specifying --master you must use the promotable clone id (%s)"
                % promotable_clone_id
            )
        else:
            utils.err("when specifying --master you must use the promotable clone id")

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()
        allowed_nodes = set()
        banned_nodes = set()
        if not clear:
            running_on = utils.resource_running_on(resource_id)
            was_running = running_on["is_running"]
            if dest_node and ban: # ban, node specified
                banned_nodes = set([dest_node])
            elif dest_node: # move, node specified
                allowed_nodes = set([dest_node])
            else: # move or ban, node not specified
                banned_nodes = set(
                    running_on["nodes_master"] + running_on["nodes_started"]
                )

    if modifiers.is_specified("--master"):
        other_options.append("--master")
    if lifetime is not None:
        other_options.append("--lifetime=%s" % lifetime)

    if clear:
        if dest_node:
            # both --host and --node works, but --host is deprecated
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
        if "Resource '"+resource_id+"' not moved: active in 0 locations" in output:
            utils.err("You must specify a node when moving/banning a stopped resource")
        new_lines = ["error moving/banning/clearing resource"]
        for line in output.split("\n"):
            if not line.strip():
                continue
            line = line.replace(
                "--ban --master --node <name>",
                f"pcs resource ban {resource_id} <node> --master"
            )
            line = line.replace(
                "--ban --node <name>",
                f"pcs resource ban {resource_id} <node>"
            )
            new_lines.append(line)
        print("\n".join(new_lines))
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
                if modifiers.is_specified("--master"):
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

    if modifiers.is_specified("--wait"):
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
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    standards = lib.resource_agent.list_standards()

    if standards:
        print("\n".join(standards))
    else:
        utils.err("No standards found")


def resource_providers(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    providers = lib.resource_agent.list_ocf_providers()

    if providers:
        print("\n".join(providers))
    else:
        utils.err("No OCF providers found")


def resource_agents(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
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
def resource_update(dummy_lib, args, modifiers, deal_with_guest_change=True):
    """
    Options:
      * -f - CIB file
      * --wait
      * --force - allow invalid options, do not fail if not possible to get
        agent metadata, allow not suitable command
    """
    modifiers.ensure_only_supported("-f", "--wait", "--force")
    if len(args) < 2:
        raise CmdLineInputError()
    res_id = args.pop(0)
    dom = utils.get_cib_dom()

# Extract operation arguments
    ra_values, op_values, meta_values = parse_resource_options(args)

    wait = False
    wait_timeout = None
    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()
        wait = True

    resource = utils.dom_get_resource(dom, res_id)
    if not resource:
        clone = utils.dom_get_clone(dom, res_id)
        master = utils.dom_get_master(dom, res_id)
        if clone or master:
            if master:
                clone = transform_master_to_clone(master)
            clone_child = utils.dom_elem_get_clone_ms_resource(clone)
            if clone_child:
                child_id = clone_child.getAttribute("id")
                return resource_update_clone(
                    dom, clone, child_id, args, wait, wait_timeout
                )
        utils.err("Unable to find resource: %s" % res_id)

    instance_attributes = resource.getElementsByTagName("instance_attributes")
    if len(instance_attributes) == 0:
        instance_attributes = dom.createElement("instance_attributes")
        instance_attributes.setAttribute("id", res_id + "-instance_attributes")
        resource.appendChild(instance_attributes)
        current_params = {}
    else:
        instance_attributes = instance_attributes[0]
        current_params = {
            ia.getAttribute("name"): ia.getAttribute("value")
            for ia in instance_attributes.getElementsByTagName("nvpair")
        }

    params = utils.convert_args_to_tuples(ra_values)

    resClass = resource.getAttribute("class")
    resProvider = resource.getAttribute("provider")
    resType = resource.getAttribute("type")
    try:
        if resClass == "stonith":
            metadata = lib_ra.StonithAgent(utils.cmd_runner(), resType)
        else:
            metadata = lib_ra.ResourceAgent(
                utils.cmd_runner(),
                lib_ra.ResourceAgentName(
                    resClass, resProvider, resType
                ).full_name
            )
        report_list = metadata.validate_parameters_update(
            current_params,
            dict(params),
            force=modifiers.get("--force")
        )
        if report_list:
            utils.process_library_reports(report_list)
    except lib_ra.ResourceAgentError as e:
        severity = (
            ReportItemSeverity.WARNING if modifiers.get("--force")
            else ReportItemSeverity.ERROR
        )
        utils.process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e, severity)]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)

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

    if remote_node_name == guest_node.get_guest_option_value(prepare_options(meta_values)):
        deal_with_guest_change = False

    # The "remote-node" meta attribute makes sense (and causes creation of
    # inner pacemaker resource) only for primitive. The meta attribute
    # "remote-node" has no special meaining for clone/master. So there is no
    # need for checking this attribute in clone/master.
    #
    # It is ok to not to check it until this point in this function:
    # 1) Only master/clone element is updated if the parameter "res_id" is an id
    # of the clone/master element. In that case another function is called and
    # the code path does not reach this point.
    # 2) No persistent changes happened until this line if the parameter
    # "res_id" is an id of the primitive.
    if deal_with_guest_change:
        _detect_guest_change(
            prepare_options(meta_values),
            modifiers.get("--force"),
        )

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

    if modifiers.is_specified("--wait"):
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

def resource_update_clone(
    dom, clone, res_id, args, wait, wait_timeout
):
    """
    Commandline options:
      * -f - CIB file
    """
    dom, dummy_clone_id = resource_clone_create(
        dom, [res_id] + args, update_existing=True
    )

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

def transform_master_to_clone(master_element):
    # create a new clone element with the same id
    dom = master_element.ownerDocument
    clone_element = dom.createElement("clone")
    clone_element.setAttribute("id", master_element.getAttribute("id"))
    # place it next to the master element
    master_element.parentNode.insertBefore(clone_element, master_element)
    # move all master's children to the clone
    while master_element.firstChild:
        clone_element.appendChild(master_element.firstChild)
    # remove the master
    master_element.parentNode.removeChild(master_element)
    # set meta to make the clone promotable
    utils.dom_update_meta_attr(clone_element, [("promotable", "true")])
    return clone_element

def resource_operation_add(
    dom, res_id, argv, validate_strict=True, before_op=None
):
    """
    Commandline options:
      * --force
    """
    if len(argv) < 1:
        usage.resource(["op"])
        sys.exit(1)

    res_el = utils.dom_get_resource(dom, res_id)
    if not res_el:
        utils.err ("Unable to find resource: %s" % res_id)

    op_name = argv.pop(0)
    op_properties = utils.convert_args_to_tuples(argv)

    if "=" in op_name:
        utils.err(
            "%s does not appear to be a valid operation action" % op_name
        )
    if "--force" not in utils.pcs_options:
        valid_attrs = ["id", "name", "interval", "description", "start-delay",
            "interval-origin", "timeout", "enabled", "record-pending", "role",
            "on-fail", "OCF_CHECK_LEVEL"]
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

    generate_id = True
    for name, value in op_properties:
        if name == "id":
            op_id = value
            generate_id = False
            id_valid, id_error = utils.validate_xml_id(value, 'operation id')
            if not id_valid:
                utils.err(id_error)
            if utils.does_id_exist(dom, value):
                utils.err(
                    "id '%s' is already in use, please specify another one"
                    % value
                )
    if generate_id:
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
    """
    Commandline options:
      * -f - CIB file
    """
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
    resource_el = None

    for resource in dom.getElementsByTagName("primitive"):
        if resource.getAttribute("id") == res_id:
            resource_el = resource
            break

    if not resource_el:
        utils.err("Unable to find resource: %s" % res_id)

    remove_all = False
    if len(argv) == 0:
        remove_all = True

    op_properties = utils.convert_args_to_tuples(argv)
    op_properties.append(('name', op_name))
    found_match = False
    for op in resource_el.getElementsByTagName("op"):
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

def resource_meta(dummy_lib, argv, modifiers):
    """
    Options:
      * --force - allow not suitable command
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--wait", "-f")
    if len(argv) < 2:
        raise CmdLineInputError()
    res_id = argv.pop(0)
    _detect_guest_change(
        prepare_options(argv),
        modifiers.get("--force"),
    )

    dom = utils.get_cib_dom()

    master = utils.dom_get_master(dom, res_id)
    if master:
        resource_el = transform_master_to_clone(master)
    else:
        resource_el = utils.dom_get_any_resource(dom, res_id)
    if resource_el is None:
        utils.err("unable to find a resource/clone/group: %s" % res_id)

    if modifiers.is_specified("--wait"):
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

    if modifiers.is_specified("--wait"):
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


def resource_group(lib, argv, modifiers):
    if len(argv) == 0:
        raise CmdLineInputError()

    group_cmd = argv.pop(0)
    try:
        if (group_cmd == "add"):
            resource_group_add_cmd(lib, argv, modifiers)
        elif (group_cmd == "list"):
            resource_group_list(lib, argv, modifiers)
        elif (group_cmd in ["remove", "delete"]):
            resource_group_rm_cmd(lib, argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "resource", f"group {group_cmd}")

def resource_group_rm_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if len(argv) < 1:
        raise CmdLineInputError()
    group_name = argv.pop(0)
    resource_ids = argv

    cib_dom = resource_group_rm(
        utils.get_cib_dom(), group_name, resource_ids
    )

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    utils.replace_cib_configuration(cib_dom)

    if modifiers.is_specified("--wait"):
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

def resource_group_add_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
      * --after - place a resource in a group after the specified resource in
        the group
      * --before - place a resource in a group before the specified resource in
        the group
    """
    modifiers.ensure_only_supported("--wait", "-f", "--after", "--before")
    if len(argv) < 2:
        raise CmdLineInputError()
    group_name = argv.pop(0)
    resource_ids = argv
    cib = resource_group_add(utils.get_cib_dom(), group_name, resource_ids)

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    utils.replace_cib_configuration(cib)

    if modifiers.is_specified("--wait"):
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

def resource_clone(dummy_lib, argv, modifiers, promotable=False):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--wait")
    if len(argv) < 1:
        raise CmdLineInputError()

    res = argv[0]
    cib_dom = utils.get_cib_dom()

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    cib_dom, clone_id = resource_clone_create(
        cib_dom, argv, promotable=promotable
    )
    cib_dom = constraint.constraint_resource_update(res, cib_dom)
    utils.replace_cib_configuration(cib_dom)

    if modifiers.is_specified("--wait"):
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

def resource_clone_create(
    cib_dom, argv, update_existing=False, promotable=False
):
    """
    Commandline options: no options
    """
    name = argv.pop(0)

    re = cib_dom.getElementsByTagName("resources")[0]
    element = utils.dom_get_resource(re, name) or utils.dom_get_group(re, name)
    if not element:
        utils.err("unable to find group or resource: %s" % name)

    if element.parentNode.tagName == "bundle":
        utils.err("cannot clone bundle resource")

    if not update_existing:
        if (
            utils.dom_get_resource_clone(cib_dom, name)
            or
            utils.dom_get_resource_masterslave(cib_dom, name)
        ):
            utils.err("%s is already a clone resource" % name)

        if (
            utils.dom_get_group_clone(cib_dom, name)
            or
            utils.dom_get_group_masterslave(cib_dom, name)
        ):
            utils.err("cannot clone a group that has already been cloned")

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
    if promotable:
        if "promotable" in final_meta:
            utils.err(
                "you cannot specify both promotable option and promotable "
                "keyword"
            )
        else:
            final_meta["promotable"] = "true"
    utils.dom_update_meta_attr(clone, sorted(final_meta.items()))

    return cib_dom, clone.getAttribute("id")

def resource_clone_master_remove(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--wait")
    if len(argv) != 1:
        raise CmdLineInputError()

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

    if modifiers.is_specified("--wait"):
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

    if modifiers.is_specified("--wait"):
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

def resource_remove_cmd(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) != 1:
        raise CmdLineInputError()
    resource_remove(argv[0])

def resource_remove(resource_id, output=True, is_remove_remote_context=False):
    """
    Commandline options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
      * --wait - is supported by resource_disable but waiting for resource to
        stop is handled also in this function
    """
    def is_bundle_running(bundle_id):
        roles_with_nodes = _get_primitive_roles_with_nodes(
            _get_primitives_for_state_check(
                get_cluster_state_dom(
                    lib_pacemaker.get_cluster_status_xml(utils.cmd_runner())
                ),
                bundle_id,
                expected_running=True
            )
        )
        return True if roles_with_nodes else False

    dom = utils.get_cib_dom()
    # if resource is a clone or a master, work with its child instead
    cloned_resource = utils.dom_get_clone_ms_resource(dom, resource_id)
    if cloned_resource:
        resource_id = cloned_resource.getAttribute("id")

    bundle = utils.dom_get_bundle(dom, resource_id)
    if bundle is not None:
        primitive_el = utils.dom_get_resource_bundle(bundle)
        if primitive_el is None:
            print("Deleting bundle '{0}'".format(resource_id))
        else:
            print(
                "Deleting bundle '{0}' and its inner resource '{1}'".format(
                    resource_id,
                    primitive_el.getAttribute("id")
                )
            )

        if (
            "--force" not in utils.pcs_options
            and
            not utils.usefile
            and
            is_bundle_running(resource_id)
        ):
            sys.stdout.write("Stopping bundle '{0}'... ".format(resource_id))
            sys.stdout.flush()
            lib = utils.get_library_wrapper()
            lib.resource.disable([resource_id], False)
            output, retval = utils.run(["crm_resource", "--wait"])
            # pacemaker which supports bundles supports --wait as well
            if is_bundle_running(resource_id):
                msg = [
                    "Unable to stop: %s before deleting "
                    "(re-run with --force to force deletion)"
                    % resource_id
                ]
                if retval != 0 and output:
                    msg.append("\n" + output)
                utils.err("\n".join(msg).strip())
            print("Stopped")

        if primitive_el is not None:
            resource_remove(primitive_el.getAttribute("id"))
        utils.replace_cib_configuration(
            remove_resource_references(utils.get_cib_dom(), resource_id, output)
        )
        args = [
            "cibadmin", "-o", "resources", "-D", "--xpath",
            "//bundle[@id='{0}']".format(resource_id)
        ]
        dummy_cmdoutput, retVal = utils.run(args)
        if retVal != 0:
            utils.err("Unable to remove resource '{0}'".format(resource_id))
        return True

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

    # now we know resource is not a group, a clone, a master nor a bundle
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
        sys.stdout.write("Attempting to stop: "+ resource_id + "... ")
        sys.stdout.flush()
        lib = utils.get_library_wrapper()
        # we are not using wait from disable command, because if wait is not
        # supported in pacemaker, we don't want error message but we try to
        # simulate wait by waiting for resource to stop
        lib.resource.disable([resource_id], False)
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
        if not is_remove_remote_context:
            warn(
                "This command is not sufficient for removing remote and guest "
                "nodes. To complete the removal, remove pacemaker authkey and "
                "stop and disable pacemaker_remote on the node(s) manually."
            )
        output, retval = utils.run(["crm_resource", "--wait"])
        output, retval = utils.run([
            "crm_node", "--force", "--remove", remote_node_name
        ])
    return True

# moved to pcs.lib.cib.fencing_topology.remove_device_from_all_levels
def stonith_level_rm_device(cib_dom, stn_id):
    """
    Commandline options: no options
    """
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
    """
    Commandline options: no options
    NOTE: -f - will be used only if dom will be None
    """
    constraint.remove_constraints_containing(
        resource_id, output, constraints_element, dom
    )
    stonith_level_rm_device(dom, resource_id)
    lib_acl.dom_remove_permissions_referencing(dom, resource_id)
    return dom

# This removes a resource from a group, but keeps it in the config
def resource_group_rm(cib_dom, group_name, resource_ids):
    """
    Commandline options: no options
    """
    dom = cib_dom.getElementsByTagName("configuration")[0]

    all_resources = len(resource_ids) == 0

    group_match = utils.dom_get_group(dom, group_name)
    if not group_match:
        utils.err("Group '%s' does not exist" % group_name)


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

    # If the group is in a clone, we don't delete the clone as there may be
    # constraints associated with it which the user may want to keep. However,
    # there may be several resources in the group. In that case there is no way
    # to figure out which one of them should stay in the clone. So we forbid
    # removing all resources from a cloned group unless there is just one
    # resource.
    # This creates an inconsistency:
    # - consider a cloned group with two resources
    # - move one resource from the group - it becomes a primitive
    # - move the last resource from the group - it stays in the clone
    # So far there has been no request to change this behavior. Unless there is
    # a request / reason to change it, we'll keep it that way.
    is_cloned_group = group_match.parentNode.tagName in ["clone", "master"]
    res_in_group = len(group_match.getElementsByTagName("primitive"))
    if (
        is_cloned_group
        and
        res_in_group > 1
        and
        len(resources_to_move) == res_in_group
    ):
        utils.err("Cannot remove all resources from a cloned group")

    target_node = group_match.parentNode
    if is_cloned_group and res_in_group > 1:
        target_node = dom.getElementsByTagName("resources")[0]
    for resource in resources_to_move:
        resource.parentNode.removeChild(resource)
        target_node.appendChild(resource)

    if len(group_match.getElementsByTagName("primitive")) == 0:
        group_match.parentNode.removeChild(group_match)
        remove_resource_references(dom, group_name, output=True)

    return cib_dom

def resource_group_add(cib_dom, group_name, resource_ids):
    """
    Commandline options:
      * --after - place a resource in a group after the specified resource in
        the group
      * --before - place a resource in a group before the specified resource in
        the group
    """
    resources_element = cib_dom.getElementsByTagName("resources")[0]

    name_valid, name_error = utils.validate_xml_id(group_name, 'group name')
    if not name_valid:
        utils.err(name_error)

    mygroup = utils.dom_get_group(resources_element, group_name)
    if not mygroup:
        if utils.dom_get_resource(resources_element, group_name):
            utils.err("'%s' is already a resource" % group_name)
        if (
            utils.dom_get_clone(resources_element, group_name)
            or
            utils.dom_get_master(resources_element, group_name)
        ):
            utils.err("'%s' is already a clone resource" % group_name)
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
                if resource.parentNode.tagName in ["clone", "master"]:
                    utils.err("cannot group clone resources")
                if resource.parentNode.tagName == "bundle":
                    utils.err("cannot group bundle resources")
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

def resource_group_list(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
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


def resource_status(lib, argv, modifiers, stonith=False):
    """
    Options:
      * -f - CIB file
      * --hide-inactive - print only active resources
    """
    modifiers.ensure_only_supported("-f", "--hide-inactive")
    if argv:
        raise CmdLineInputError()

    monitor_command = ["crm_mon", "--one-shot"]
    if not modifiers.get("--hide-inactive"):
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


def _print_resource_stonith(resource_el, only_stonith):
    is_stonith = (
        "class" in resource_el.attrib
        and
        resource_el.attrib["class"] == "stonith"
    )
    if (only_stonith and is_stonith) or (not only_stonith and not is_stonith):
        print_node(resource_el, 1)
        return True
    return False


def resource_config(lib, argv, modifiers, stonith=False):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")

    root = utils.get_cib_etree()
    resources = root.find(".//resources")
    if not argv:
        for resource in resources:
            _print_resource_stonith(resource, only_stonith=stonith)
        return

    for resource_id in argv:
        resource_found = False
        for resource in resources.findall(str(".//*")):
            if "id" in resource.attrib and resource.attrib["id"] == resource_id:
                if _print_resource_stonith(resource, only_stonith=stonith):
                    resource_found = True
                    break
        if not resource_found:
            utils.err(f"unable to find resource '{resource_id}'")


def resource_disable_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if len(argv) < 1:
        utils.err("You must specify resource(s) to disable")
    resources = argv
    lib.resource.disable(resources, modifiers.get("--wait"))

def resource_enable_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if len(argv) < 1:
        utils.err("You must specify resource(s) to enable")
    resources = argv
    lib.resource.enable(resources, modifiers.get("--wait"))

#DEPRECATED, moved to pcs.lib.commands.resource
def resource_disable(argv):
    """
    Commandline options:
      * -f - CIB file
      * --wait
    """
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

def resource_restart(dummy_lib, argv, modifiers):
    """
    Options:
      * --wait
    """
    modifiers.ensure_only_supported("--wait")
    if len(argv) < 1:
        utils.err("You must specify a resource to restart")

    dom = utils.get_cib_dom()
    node = None
    resource = argv.pop(0)

    real_res = (
        utils.dom_get_resource_clone_ms_parent(dom, resource)
        or
        utils.dom_get_resource_bundle_parent(dom, resource)
    )
    if real_res:
        print("Warning: using %s... (if a resource is a clone or bundle you must use the clone or bundle name)" % real_res.getAttribute("id"))
        resource = real_res.getAttribute("id")

    args = ["crm_resource", "--restart", "--resource", resource]
    if len(argv) > 0:
        node = argv.pop(0)
        if not (
            utils.dom_get_clone(dom, resource)
            or
            utils.dom_get_master(dom, resource)
            or
            utils.dom_get_bundle(dom, resource)
        ):
            utils.err("can only restart on a specific node for a clone or bundle resource")
        args.extend(["--node", node])

    if modifiers.is_specified("--wait"):
        if modifiers.get("--wait"):
            args.extend(["--timeout", modifiers.get("--wait")])
        else:
            utils.err("You must specify the number of seconds to wait")

    output, retval = utils.run(args)
    if retval != 0:
        utils.err(output)

    print("%s successfully restarted" % resource)

def resource_force_action(dummy_lib, argv, modifiers):
    """
    Options:
      * --force
      * --full - more verbose output
    """
    modifiers.ensure_only_supported("--force", "--full")
    if len(argv) < 1:
        raise CmdLineInputError()
    action = argv.pop(0)
    if len(argv) < 1:
        utils.err("You must specify a resource to {0}".format(action))
    if len(argv) != 1:
        raise CmdLineInputError()

    action_command = {
        "debug-start": "--force-start",
        "debug-stop": "--force-stop",
        "debug-promote": "--force-promote",
        "debug-demote": "--force-demote",
        "debug-monitor": "--force-check",
    }

    if action not in action_command:
        raise CmdLineInputError()

    resource = argv[0]
    dom = utils.get_cib_dom()

    if not (
        utils.dom_get_any_resource(dom, resource)
        or
        utils.dom_get_bundle(dom, resource)
    ):
        utils.err(
            "unable to find a resource/clone/group/bundle: {0}".format(
                resource
            )
        )
    bundle = utils.dom_get_bundle(dom, resource)
    if bundle:
        bundle_resource = utils.dom_get_resource_bundle(bundle)
        if bundle_resource:
            utils.err(
                "unable to {0} a bundle, try the bundle's resource: {1}".format(
                    action, bundle_resource.getAttribute("id")
                )
            )
        else:
            utils.err("unable to {0} a bundle".format(action))
    if utils.dom_get_group(dom, resource):
        group_resources = utils.get_group_children(resource)
        utils.err(
            "unable to {0} a group, try one of the group's resource(s) ({1})".format(
                action, ",".join(group_resources)
            )
        )
    if (
        utils.dom_get_clone(dom, resource)
        or
        utils.dom_get_master(dom, resource)
    ):
        clone_resource = utils.dom_get_clone_ms_resource(dom, resource)
        utils.err(
            "unable to {0} a clone, try the clone's resource: {1}".format(
                action, clone_resource.getAttribute("id")
            )
        )

    args = ["crm_resource", "-r", resource, action_command[action]]
    if modifiers.get("--full"):
        # set --verbose twice to get a reasonable amount of debug messages
        args.extend(["--verbose"] * 2)
    if modifiers.get("--force"):
        args.append("--force")
    output, retval = utils.run(args)

    if "doesn't support group resources" in output:
        utils.err("groups are not supported")
        sys.exit(retval)
    if "doesn't support stonith resources" in output:
        utils.err("stonith devices are not supported")
        sys.exit(retval)

    print(output.rstrip())
    sys.exit(retval)

def resource_manage_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --monitor - enable monitor operation of specified resorces
    """
    modifiers.ensure_only_supported("-f", "--monitor")
    if len(argv) < 1:
        utils.err("You must specify resource(s) to manage")
    resources = argv
    lib.resource.manage(resources, with_monitor=modifiers.get("--monitor"))

def resource_unmanage_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --monitor - bisable monitor operation of specified resorces
    """
    modifiers.ensure_only_supported("-f", "--monitor")
    if len(argv) < 1:
        utils.err("You must specify resource(s) to unmanage")
    resources = argv
    lib.resource.unmanage(resources, with_monitor=modifiers.get("--monitor"))

# moved to pcs.lib.pacemaker.state
def is_managed(resource_id):
    # pylint: disable=too-many-return-statements
    """
    Commandline options:
      * -f - CIB file
    """
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
    utils.err("unable to find a resource/clone/group: %s" % resource_id)

def resource_failcount(lib, argv, modifiers):
    """
    Options:
      * --full
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--full")
    if len(argv) < 1:
        raise CmdLineInputError()

    command = argv.pop(0)

    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options(argv)
    unknown_options = (
        set(parsed_options.keys()) - {"node", "operation", "interval"}
    )
    if unknown_options:
        raise CmdLineInputError(
            "Unknown options '{}'".format("', '".join(sorted(unknown_options)))
        )
    node = parsed_options.get("node")
    operation = parsed_options.get("operation")
    interval = parsed_options.get("interval")

    if command == "show":
        print(resource_failcount_show(
            lib, resource, node, operation, interval, modifiers.get("--full")
        ))
        return

    raise CmdLineInputError()

def __agregate_failures(failure_list):
    """
    Commandline options: no options
    """
    last_failure = 0
    fail_count = 0
    for failure in failure_list:
        # infinity is a maximal value and cannot be increased
        if fail_count != "INFINITY":
            if failure["fail_count"] == "INFINITY":
                fail_count = failure["fail_count"]
            else:
                fail_count += failure["fail_count"]
        last_failure = max(last_failure, failure["last_failure"])
    return fail_count, last_failure

def __headline_resource_failures(empty, resource, node, operation, interval):
    """
    Commandline options: no options
    """
    headline_parts = []
    if empty:
        headline_parts.append("No failcounts")
    else:
        headline_parts.append("Failcounts")
    if operation:
        headline_parts.append("for operation '{operation}'")
        if interval:
            headline_parts.append("with interval '{interval}'")
    if resource:
        headline_parts.append("of" if operation else "for")
        headline_parts.append("resource '{resource}'")
    if node:
        headline_parts.append("on node '{node}'")
    return " ".join(headline_parts).format(
        node=node, resource=resource, operation=operation,
        interval=interval
    )

def resource_failcount_show(lib, resource, node, operation, interval, full):
    """
    Commandline options:
      * -f - CIB file
    """
    result_lines = []
    failures_data = lib.resource.get_failcounts(
        resource=resource,
        node=node,
        operation=operation,
        interval=interval
    )

    if not failures_data:
        result_lines.append(__headline_resource_failures(
            True, resource, node, operation, interval
        ))
        return "\n".join(result_lines)

    resource_list = sorted({fail["resource"] for fail in failures_data})
    for current_resource in resource_list:
        result_lines.append(__headline_resource_failures(
            False, current_resource, node, operation, interval
        ))
        resource_failures = [
            fail for fail in failures_data
            if fail["resource"] == current_resource
        ]
        node_list = sorted({fail["node"] for fail in resource_failures})
        for current_node in node_list:
            node_failures = [
                fail for fail in resource_failures
                if fail["node"] == current_node
            ]
            if full:
                result_lines.append(f"  {current_node}:")
                operation_list = sorted({
                    fail["operation"] for fail in node_failures
                })
                for current_operation in operation_list:
                    operation_failures = [
                        fail for fail in node_failures
                        if fail["operation"] == current_operation
                    ]
                    interval_list = sorted(
                        {fail["interval"] for fail in operation_failures},
                        # pacemaker's definition of infinity
                        key=lambda x: 1000000 if x == "INFINITY" else x
                    )
                    for current_interval in interval_list:
                        interval_failures = [
                            fail for fail in operation_failures
                            if fail["interval"] == current_interval
                        ]
                        failcount, dummy_last_failure = __agregate_failures(
                            interval_failures
                        )
                        result_lines.append(
                            f"    {current_operation} {current_interval}ms: "
                            f"{failcount}"
                        )
            else:
                failcount, dummy_last_failure = __agregate_failures(
                    node_failures
                )
                result_lines.append(f"  {current_node}: {failcount}")
    return "\n".join(result_lines)

def show_defaults(def_type, indent=""):
    """
    Commandline options:
      * -f - CIB file
    """
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

def print_node(node, tab = 0):
    """
    Commandline options: no options
    """
    spaces = " " * tab
    if node.tag == "group":
        print(spaces + "Group: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
        return
    if node.tag == "clone":
        print(spaces + "Clone: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
        return
    if node.tag == "primitive":
        print(spaces + "Resource: " + node.attrib["id"] + get_attrs(node,' (',')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces)
        print_utilization_string(node, spaces)
        print_operations(node, spaces)
        return
    if node.tag == "master":
        print(spaces + "Clone: " + node.attrib["id"] + get_attrs(node, ' (', ')'))
        print_instance_vars_string(node, spaces)
        print_meta_vars_string(node, spaces, dict(promotable="true"))
        print_operations(node, spaces)
        for child in node:
            print_node(child, tab + 1)
        return
    if node.tag == "bundle":
        print(spaces + "Bundle: " + node.attrib["id"] + get_attrs(node, ' (', ')'))
        print_bundle_container(node, spaces + " ")
        print_bundle_network(node, spaces + " ")
        print_bundle_mapping(
            "Port Mapping:",
            node.findall("network/port-mapping"),
            spaces + " "
        )
        print_bundle_mapping(
            "Storage Mapping:",
            node.findall("storage/storage-mapping"),
            spaces + " "
        )
        print_meta_vars_string(node, spaces)
        for child in node:
            print_node(child, tab + 1)
        return

def print_bundle_container(bundle_el, spaces):
    """
    Commandline options: no options
    """
    for container_type in bundle.GENERIC_CONTAINER_TYPES:
        container_list = bundle_el.findall(container_type)
        for container_el in container_list:
            print(
                spaces
                +
                container_el.tag.capitalize()
                +
                get_attrs(container_el, ": ", "")
            )

def print_bundle_network(bundle_el, spaces):
    """
    Commandline options: no options
    """
    network_list = bundle_el.findall("network")
    for network_el in network_list:
        attrs_string = get_attrs(network_el)
        if attrs_string:
            print(spaces + "Network: " + attrs_string)

def print_bundle_mapping(first_line, map_items, spaces):
    """
    Commandline options: no options
    """
    map_lines = [
        spaces + " " + get_attrs(item, "", " ") + "(" + item.attrib["id"] + ")"
        for item in map_items
    ]
    if map_lines:
        print(spaces + first_line)
        print("\n".join(map_lines))

def print_utilization_string(element, spaces):
    """
    Commandline options: no options
    """
    output = []
    mvars = element.findall("utilization/nvpair")
    for mvar in mvars:
        output.append(mvar.attrib["name"] + "=" + mvar.attrib["value"])
    if output:
        print(spaces + " Utilization: " + " ".join(output))

def print_instance_vars_string(node, spaces):
    """
    Commandline options: no options
    """
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

def print_meta_vars_string(node, spaces, extra_vars_dict=None):
    """
    Commandline options: no options
    """
    meta = {
        mvar.attrib["name"]: mvar.attrib["value"]
        for mvar in node.findall(str("meta_attributes/nvpair"))
    }
    if extra_vars_dict:
        meta.update(extra_vars_dict)
    pairs = [f'{name}={value}' for name, value in sorted(meta.items())]
    if pairs:
        print(spaces + " Meta Attrs: " + " ".join(pairs))

def print_operations(node, spaces):
    """
    Commandline options: no options
    """
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
    """
    Commandline options: no options
    """
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
    """
    Commandline options: no options
    """
    output = ""
    for attr,val in sorted(node.attrib.items()):
        if attr in ["id"]:
            continue
        if " " in val:
            val = '"' + val + '"'
        output += attr + "=" + val + " "
    if output != "":
        return prepend_string + output.rstrip() + append_string
    return output.rstrip()

def resource_cleanup(dummy_lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options(argv)
    unknown_options = (
        set(parsed_options.keys()) - {"node", "operation", "interval"}
    )
    if unknown_options:
        raise CmdLineInputError(
            "Unknown options '{}'".format("', '".join(sorted(unknown_options)))
        )
    print(lib_pacemaker.resource_cleanup(
        utils.cmd_runner(),
        resource=resource,
        node=parsed_options.get("node"),
        operation=parsed_options.get("operation"),
        interval=parsed_options.get("interval"),
    ))

def resource_refresh(dummy_lib, argv, modifiers):
    """
    Options:
      * --full - refresh a resource on all nodes
      * --force - do refresh even though it may be time consuming
    """
    modifiers.ensure_only_supported("--force", "--full")
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options(argv)
    unknown_options = (set(parsed_options.keys()) - {"node"})
    if unknown_options:
        raise CmdLineInputError(
            "Unknown options '{}'".format("', '".join(sorted(unknown_options)))
        )
    print(lib_pacemaker.resource_refresh(
        utils.cmd_runner(),
        resource=resource,
        node=parsed_options.get("node"),
        full=modifiers.get("--full"),
        force=modifiers.get("--force"),
    ))

def resource_relocate(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()
    cmd = argv.pop(0)
    try:
        if cmd == "show":
            resource_relocate_show_cmd(lib, argv, modifiers)
        elif cmd == "dry-run":
            resource_relocate_dry_run_cmd(lib, argv, modifiers)
        elif cmd == "run":
            resource_relocate_run_cmd(lib, argv, modifiers)
        elif cmd == "clear":
            resource_relocate_clear_cmd(lib, argv, modifiers)
        else:
            cmd = ""
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "resource", "relocate {0}".format(cmd)
        )

def resource_relocate_show_cmd(dummy_lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    resource_relocate_show(utils.get_cib_dom())

def resource_relocate_dry_run_cmd(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    resource_relocate_run(utils.get_cib_dom(), argv, dry=True)

def resource_relocate_run_cmd(dummy_lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    resource_relocate_run(utils.get_cib_dom(), argv, dry=False)

def resource_relocate_clear_cmd(dummy_lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    utils.replace_cib_configuration(
        resource_relocate_clear(utils.get_cib_dom())
    )

def resource_relocate_set_stickiness(cib_dom, resources=None):
    """
    Commandline options: no options
    """
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
                    "unable to find a resource/clone/group: {0}".format(
                        res_id
                    ),
                    False
                )
            sys.exit(1)
    return cib_dom, updated_resources

def resource_relocate_get_locations(cib_dom, resources=None):
    """
    Commandline options:
      * --force - allow constraint on any resource, may not have any effective
        as an invalid constraint is ignored anyway
    """
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
    """
    Commandline options: no options
    """
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
    """
    Commandline options: no options
    """
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
    """
    Commandline options:
      * -f - CIB file, explicitly forbids -f if dry is False
      * --force - allow constraint on any resource, may not have any effective
        as an invalid copnstraint is ignored anyway
    """
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
    """
    Commandline options: no options
    """
    for constraint_el in cib_dom.getElementsByTagName("constraints"):
        for location_el in constraint_el.getElementsByTagName("rsc_location"):
            location_id = location_el.getAttribute("id")
            if location_id.startswith(RESOURCE_RELOCATE_CONSTRAINT_PREFIX):
                print("Removing constraint {0}".format(location_id))
                location_el.parentNode.removeChild(location_el)
    return cib_dom

def set_resource_utilization(resource_id, argv):
    """
    Commandline options:
      * -f - CIB file
    """
    cib = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(cib, resource_id)
    if resource_el is None:
        utils.err("Unable to find a resource: {0}".format(resource_id))
    utils.dom_update_utilization(resource_el, prepare_options(argv))
    utils.replace_cib_configuration(cib)

def print_resource_utilization(resource_id):
    """
    Commandline options:
      * -f - CIB file
    """
    cib = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(cib, resource_id)
    if resource_el is None:
        utils.err("Unable to find a resource: {0}".format(resource_id))
    utilization = utils.get_utilization_str(resource_el)

    print("Resource Utilization:")
    print(" {0}: {1}".format(resource_id, utilization))

def print_resources_utilization():
    """
    Commandline options:
      * -f - CIB file
    """
    cib = utils.get_cib_dom()
    utilization = {}
    for resource_el in cib.getElementsByTagName("primitive"):
        u = utils.get_utilization_str(resource_el)
        if u:
            utilization[resource_el.getAttribute("id")] = u

    print("Resource Utilization:")
    for resource in sorted(utilization):
        print(" {0}: {1}".format(resource, utilization[resource]))


# This is used only by pcsd, will be removed in new architecture
def get_resource_agent_info(dummy_lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
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

def resource_bundle_cmd(lib, argv, modifiers):
    try:
        if len(argv) < 1:
            sub_cmd = ""
            raise CmdLineInputError()
        sub_cmd, argv_next = argv[0], argv[1:]

        if sub_cmd == "create":
            resource_bundle_create_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "update":
            resource_bundle_update_cmd(lib, argv_next, modifiers)
        else:
            sub_cmd = ""
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "resource", "bundle {0}".format(sub_cmd)
        )

def resource_bundle_create_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * --disabled - create as a stopped bundle
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--disabled", "--wait", "-f")
    if len(argv) < 1:
        raise CmdLineInputError()

    bundle_id = argv[0]
    parts = parse_bundle_create_options(argv[1:])
    lib.resource.bundle_create(
        bundle_id,
        parts["container_type"],
        container_options=parts["container"],
        network_options=parts["network"],
        port_map=parts["port_map"],
        storage_map=parts["storage_map"],
        meta_attributes=parts["meta"],
        force_options=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        wait=modifiers.get("--wait"),
    )

def resource_bundle_update_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--wait", "-f")
    if len(argv) < 1:
        raise CmdLineInputError()

    bundle_id = argv[0]
    parts = parse_bundle_update_options(argv[1:])
    lib.resource.bundle_update(
        bundle_id,
        container_options=parts["container"],
        network_options=parts["network"],
        port_map_add=parts["port_map_add"],
        port_map_remove=parts["port_map_remove"],
        storage_map_add=parts["storage_map_add"],
        storage_map_remove=parts["storage_map_remove"],
        meta_attributes=parts["meta"],
        force_options=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )
