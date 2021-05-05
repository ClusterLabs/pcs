# pylint: disable=too-many-lines
import sys
from xml.dom.minidom import parseString
import re
import textwrap
import time
import json

from typing import (
    Any,
    Callable,
    cast,
    List,
    Sequence,
)

from pcs import (
    usage,
    utils,
    constraint,
)
from pcs.common.str_tools import format_list
from pcs.settings import (
    pacemaker_wait_timeout_status as PACEMAKER_WAIT_TIMEOUT_STATUS,
)
from pcs.cli.common.errors import CmdLineInputError, raise_command_replaced
from pcs.cli.common.parse_args import (
    group_by_keywords,
    prepare_options,
    prepare_options_allowed,
    InputModifiers,
)
from pcs.cli.nvset import nvset_dto_list_to_lines
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import error, warn
from pcs.cli.resource.parse_args import (
    parse_bundle_create_options,
    parse_bundle_reset_options,
    parse_bundle_update_options,
    parse_clone as parse_clone_args,
    parse_create as parse_create_args,
)
from pcs.common import reports
from pcs.common.str_tools import indent
import pcs.lib.cib.acl as lib_acl
from pcs.lib.cib.resource import (
    bundle,
    guest_node,
    primitive,
)
from pcs.lib.cib.resource.common import (
    find_one_resource,
    find_resources_to_delete,
)
from pcs.lib.cib.tools import (
    get_resources,
    get_tags,
)
from pcs.lib.commands.resource import (
    _validate_guest_change,
    _get_nodes_to_validate_against,
)
from pcs.lib.errors import LibraryError
import pcs.lib.pacemaker.live as lib_pacemaker
from pcs.lib.pacemaker.state import (
    get_cluster_state_dom,
    get_resource_state,
)
from pcs.lib.pacemaker.values import validate_id, timeout_to_seconds
import pcs.lib.resource_agent as lib_ra

# pylint: disable=invalid-name
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-statements

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
    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = _get_nodes_to_validate_against(env, cib)
    if env.report_processor.report_list(
        report_list
        + _validate_guest_change(
            cib,
            existing_nodes_names,
            existing_nodes_addrs,
            meta_attributes,
            allow_not_suitable_command,
            detect_remove=True,
        )
    ).has_errors:
        raise LibraryError()


def resource_utilization_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if not argv:
        print_resources_utilization()
    elif len(argv) == 1:
        print_resource_utilization(argv.pop(0))
    else:
        set_resource_utilization(argv.pop(0), argv)


def _defaults_set_create_cmd(
    lib_command: Callable[..., Any],
    argv: Sequence[str],
    modifiers: InputModifiers,
):
    modifiers.ensure_only_supported("-f", "--force")

    groups = group_by_keywords(
        argv,
        set(["meta", "rule"]),
        implicit_first_group_key="options",
        keyword_repeat_allowed=False,
    )
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)

    lib_command(
        prepare_options(groups["meta"]),
        prepare_options(groups["options"]),
        nvset_rule=(" ".join(groups["rule"]) if groups["rule"] else None),
        force_flags=force_flags,
    )


def resource_defaults_set_create_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    return _defaults_set_create_cmd(
        lib.cib_options.resource_defaults_create, argv, modifiers
    )


def resource_op_defaults_set_create_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    return _defaults_set_create_cmd(
        lib.cib_options.operation_defaults_create, argv, modifiers
    )


def _defaults_config_cmd(
    lib_command: Callable[..., Any],
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --all - display all nvsets including the ones with expired rules
      * --full - verbose output
      * --no-expire-check -- disable evaluating whether rules are expired
    """
    if argv:
        raise CmdLineInputError()
    modifiers.ensure_only_supported(
        "-f", "--all", "--full", "--no-expire-check"
    )
    print(
        "\n".join(
            nvset_dto_list_to_lines(
                lib_command(not modifiers.get("--no-expire-check")),
                with_ids=cast(bool, modifiers.get("--full")),
                include_expired=cast(bool, modifiers.get("--all")),
                text_if_empty="No defaults set",
            )
        )
    )


def resource_defaults_config_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --full - verbose output
    """
    return _defaults_config_cmd(
        lib.cib_options.resource_defaults_config, argv, modifiers
    )


def resource_op_defaults_config_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --full - verbose output
    """
    return _defaults_config_cmd(
        lib.cib_options.operation_defaults_config, argv, modifiers
    )


def _defaults_set_remove_cmd(
    lib_command: Callable[..., Any],
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    lib_command(argv)


def resource_defaults_set_remove_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_remove_cmd(
        lib.cib_options.resource_defaults_remove, argv, modifiers
    )


def resource_op_defaults_set_remove_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_remove_cmd(
        lib.cib_options.operation_defaults_remove, argv, modifiers
    )


def _defaults_set_update_cmd(
    lib_command: Callable[..., Any],
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    set_id = argv[0]
    groups = group_by_keywords(
        argv[1:],
        set(["meta"]),
        keyword_repeat_allowed=False,
    )
    lib_command(
        set_id,
        prepare_options(groups["meta"]),
    )


def resource_defaults_set_update_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_update_cmd(
        lib.cib_options.resource_defaults_update, argv, modifiers
    )


def resource_op_defaults_set_update_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_update_cmd(
        lib.cib_options.operation_defaults_update, argv, modifiers
    )


def resource_defaults_legacy_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
    deprecated_syntax_used: bool = False,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    del modifiers
    if deprecated_syntax_used:
        warn(
            "This command is deprecated and will be removed. "
            "Please use 'pcs resource defaults update' instead."
        )
    return lib.cib_options.resource_defaults_update(None, prepare_options(argv))


def resource_op_defaults_legacy_cmd(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
    deprecated_syntax_used: bool = False,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    del modifiers
    if deprecated_syntax_used:
        warn(
            "This command is deprecated and will be removed. "
            "Please use 'pcs resource op defaults update' instead."
        )
    return lib.cib_options.operation_defaults_update(
        None, prepare_options(argv)
    )


def resource_op_add_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    del lib
    modifiers.ensure_only_supported("-f", "--force")
    if not argv:
        raise CmdLineInputError()
    res_id = argv.pop(0)

    # Check if we need to upgrade cib schema.
    # To do that, argv must be parsed, which is duplication of parsing in
    # resource_operation_add. But we need to upgrade the cib first before
    # calling that function. Hopefully, this will be fixed in the new pcs
    # architecture.

    # argv[0] is an operation name
    op_properties = utils.convert_args_to_tuples(argv[1:])
    for key, value in op_properties:
        if key == "on-fail" and value == "demote":
            utils.checkAndUpgradeCIB(3, 4, 0)
            break

    # add the requested operation
    utils.replace_cib_configuration(
        resource_operation_add(utils.get_cib_dom(), res_id, argv)
    )


def resource_op_delete_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
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
                elif "=" not in arg and op_values[-1]:
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
            print(
                "{0} - {1}".format(
                    name,
                    _format_desc(
                        len(name + " - "), shortdesc.replace("\n", " ")
                    ),
                )
            )
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

    print(
        _format_agent_description(
            lib.resource_agent.describe_agent(agent_name),
            show_all=modifiers.get("--full"),
        )
    )


def _format_agent_description(description, stonith=False, show_all=False):
    """
    Commandline options: no options
    """
    output = []

    if description.get("name") and description.get("shortdesc"):
        output.append(
            "{0} - {1}".format(
                description["name"],
                _format_desc(
                    len(description["name"] + " - "), description["shortdesc"]
                ),
            )
        )
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
            param_title = " ".join(
                filter(
                    None,
                    [
                        param.get("name"),
                        # only show deprecated if not showing deprecated by
                        "(deprecated)"
                        if show_all
                        and param_deprecated
                        and not param_deprecated_by
                        else None,
                        "(deprecated by {0})".format(
                            ", ".join(param_deprecated_by)
                        )
                        if show_all and param_deprecated_by
                        else None,
                        "(obsoletes {0})".format(param_obsoletes)
                        if show_all and param_obsoletes
                        else None,
                        "(required)" if param.get("required", False) else None,
                        "(unique)" if param.get("unique", False) else None,
                    ],
                )
            )
            param_desc = param.get("longdesc", "").replace("\n", " ")
            if not param_desc:
                param_desc = param.get("shortdesc", "").replace("\n", " ")
                if not param_desc:
                    param_desc = "No description available"
            if param.get("pcs_deprecated_warning"):
                param_desc += " WARNING: " + param["pcs_deprecated_warning"]
            output_params.append(
                "  {0}: {1}".format(
                    param_title, _format_desc(len(param_title) + 4, param_desc)
                )
            )
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
            parts.extend(
                [
                    "{0}={1}".format(name, value)
                    for name, value in sorted(action.items())
                    if name != "name"
                ]
            )
            output_actions.append(" ".join(parts))
        if output_actions:
            output.append("")
            output.append("Default operations:")
            output.extend(output_actions)

    return "\n".join(output)


# Return the string formatted with a line length of terminal width  and indented
def _format_desc(indentation, desc):
    """
    Commandline options: no options
    """
    desc = " ".join(desc.split())
    dummy_rows, columns = utils.getTerminalSize()
    columns = max(int(columns), 40)
    afterindent = columns - indentation
    if afterindent < 1:
        afterindent = columns

    output = ""
    first = True
    for line in textwrap.wrap(desc, afterindent):
        if not first:
            output += " " * indentation
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
        "--before",
        "--after",
        "--group",
        "--force",
        "--disabled",
        "--no-default-ops",
        "--wait",
        "-f",
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
    if (
        len(set(defined_options).intersection(set(parts_sections + ["group"])))
        > 1
    ):
        raise error(
            "you can specify only one of {0} or --group".format(
                ", ".join(parts_sections)
            )
        )

    if "bundle" in parts and len(parts["bundle"]) != 1:
        raise error("you have to specify exactly one bundle")

    if modifiers.is_specified("--before") and modifiers.is_specified("--after"):
        raise error(
            "you cannot specify both --before and --after{0}".format(
                ""
                if modifiers.is_specified("--group")
                else " and you have to specify --group"
            )
        )

    if not modifiers.is_specified("--group"):
        if modifiers.is_specified("--before"):
            raise error("you cannot use --before without --group")
        if modifiers.is_specified("--after"):
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

    clone_id = parts.get("clone_id", None)
    if "clone" in parts:
        lib.resource.create_as_clone(
            ra_id,
            ra_type,
            parts["op"],
            parts["meta"],
            parts["options"],
            parts["clone"],
            clone_id=clone_id,
            **settings,
        )
    elif "promotable" in parts:
        lib.resource.create_as_clone(
            ra_id,
            ra_type,
            parts["op"],
            parts["meta"],
            parts["options"],
            dict(**parts["promotable"], promotable="true"),
            clone_id=clone_id,
            **settings,
        )
    elif "bundle" in parts:
        settings["allow_not_accessible_resource"] = modifiers.get("--force")
        lib.resource.create_into_bundle(
            ra_id,
            ra_type,
            parts["op"],
            parts["meta"],
            parts["options"],
            parts["bundle"][0],
            **settings,
        )

    elif not modifiers.is_specified("--group"):
        lib.resource.create(
            ra_id,
            ra_type,
            parts["op"],
            parts["meta"],
            parts["options"],
            **settings,
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
            ra_id,
            ra_type,
            modifiers.get("--group"),
            parts["op"],
            parts["meta"],
            parts["options"],
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
            **settings,
        )


def _parse_resource_move_ban(argv):
    resource_id = argv.pop(0)
    node = None
    lifetime = None
    while argv:
        arg = argv.pop(0)
        if arg.startswith("lifetime="):
            if lifetime:
                raise CmdLineInputError()
            lifetime = arg.split("=")[1]
            if lifetime and lifetime[0].isdigit():
                lifetime = "P" + lifetime
        elif not node:
            node = arg
        else:
            raise CmdLineInputError()
    return resource_id, node, lifetime


def resource_move(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --master
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--master", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to move")
    if len(argv) > 3:
        raise CmdLineInputError()
    resource_id, node, lifetime = _parse_resource_move_ban(argv)

    lib.resource.move(
        resource_id,
        node=node,
        master=modifiers.is_specified("--master"),
        lifetime=lifetime,
        wait=modifiers.get("--wait"),
    )


def resource_ban(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --master
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--master", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to ban")
    if len(argv) > 3:
        raise CmdLineInputError()
    resource_id, node, lifetime = _parse_resource_move_ban(argv)

    lib.resource.ban(
        resource_id,
        node=node,
        master=modifiers.is_specified("--master"),
        lifetime=lifetime,
        wait=modifiers.get("--wait"),
    )


def resource_unmove_unban(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --master
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--expired", "--master", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to clear")
    if len(argv) > 2:
        raise CmdLineInputError()
    resource_id = argv.pop(0)
    node = argv.pop(0) if argv else None

    lib.resource.unmove_unban(
        resource_id,
        node=node,
        master=modifiers.is_specified("--master"),
        expired=modifiers.is_specified("--expired"),
        wait=modifiers.get("--wait"),
    )


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
        utils.err(
            "No agents found{0}".format(
                " for {0}".format(argv[0]) if argv else ""
            )
        )


# Update a resource, removing any args that are empty and adding/updating
# args that are not empty
def resource_update(lib, args, modifiers, deal_with_guest_change=True):
    """
    Options:
      * -f - CIB file
      * --wait
      * --force - allow invalid options, do not fail if not possible to get
        agent metadata, allow not suitable command
    """
    del lib
    modifiers.ensure_only_supported("-f", "--wait", "--force")
    if len(args) < 2:
        raise CmdLineInputError()
    res_id = args.pop(0)

    # Extract operation arguments
    ra_values, op_values, meta_values = parse_resource_options(args)

    wait = False
    wait_timeout = None
    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()
        wait = True

    # Check if we need to upgrade cib schema.
    # To do that, argv must be parsed, which is duplication of parsing below.
    # But we need to upgrade the cib first before calling that function.
    # Hopefully, this will be fixed in the new pcs architecture.

    cib_upgraded = False
    for op_argv in op_values:
        if cib_upgraded:
            break
        if len(op_argv) < 2:
            continue
        # argv[0] is an operation name
        op_vars = utils.convert_args_to_tuples(op_argv[1:])
        for k, v in op_vars:
            if k == "on-fail" and v == "demote":
                utils.checkAndUpgradeCIB(3, 4, 0)
                cib_upgraded = True
                break

    cib_xml = utils.get_cib()
    dom = utils.get_cib_dom(cib_xml=cib_xml)

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
                ).full_name,
            )
        report_list = primitive.validate_resource_instance_attributes_update(
            metadata,
            dict(params),
            res_id,
            get_resources(lib_pacemaker.get_cib(cib_xml)),
            force=modifiers.get("--force"),
        )
        if report_list:
            process_library_reports(report_list)
    except lib_ra.ResourceAgentError as e:
        severity = (
            reports.ReportItemSeverity.WARNING
            if modifiers.get("--force")
            else reports.ReportItemSeverity.ERROR
        )
        process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e, severity)]
        )
    except LibraryError as e:
        process_library_reports(e.args)

    utils.dom_update_instance_attr(resource, params)

    remote_node_name = utils.dom_get_resource_remote_node_name(resource)

    if remote_node_name == guest_node.get_guest_option_value(
        prepare_options(meta_values)
    ):
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
        resource, utils.convert_args_to_tuples(meta_values)
    )

    operations = resource.getElementsByTagName("operations")
    if not operations:
        operations = dom.createElement("operations")
        resource.appendChild(operations)
    else:
        operations = operations[0]

    for op_argv in op_values:
        if not op_argv:
            continue

        op_name = op_argv[0]
        if op_name.find("=") != -1:
            utils.err(
                "%s does not appear to be a valid operation action" % op_name
            )

        if len(op_argv) < 2:
            continue

        op_role = ""
        op_vars = utils.convert_args_to_tuples(op_argv[1:])

        for k, v in op_vars:
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
            dom,
            res_id,
            op_argv,
            validate_strict=False,
            before_op=updating_op_before,
        )

    utils.replace_cib_configuration(dom)

    if (
        remote_node_name
        and remote_node_name
        != utils.dom_get_resource_remote_node_name(resource)
    ):
        # if the resource was a remote node and it is not anymore, (or its name
        # changed) we need to tell pacemaker about it
        output, retval = utils.run(
            ["crm_node", "--force", "--remove", remote_node_name]
        )

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
    return None


def resource_update_clone(dom, clone, res_id, args, wait, wait_timeout):
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
    if not argv:
        usage.resource(["op"])
        sys.exit(1)

    res_el = utils.dom_get_resource(dom, res_id)
    if not res_el:
        utils.err("Unable to find resource: %s" % res_id)

    op_name = argv.pop(0)
    op_properties = utils.convert_args_to_tuples(argv)

    if "=" in op_name:
        utils.err("%s does not appear to be a valid operation action" % op_name)
    if "--force" not in utils.pcs_options:
        valid_attrs = [
            "id",
            "name",
            "interval",
            "description",
            "start-delay",
            "interval-origin",
            "timeout",
            "enabled",
            "record-pending",
            "role",
            "on-fail",
            "OCF_CHECK_LEVEL",
        ]
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

    op_properties.sort(key=lambda a: a[0])
    op_properties.insert(0, ("name", op_name))

    generate_id = True
    for name, value in op_properties:
        if name == "id":
            op_id = value
            generate_id = False
            id_valid, id_error = utils.validate_xml_id(value, "operation id")
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
    if not operations:
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
                    timeout_to_seconds(op_el.getAttribute("interval"), True),
                    res_id,
                    "\n".join(
                        [operation_to_string(op) for op in duplicate_op_list]
                    ),
                )
            )
        if validate_strict and "--force" not in utils.pcs_options:
            duplicate_op_list = utils.operation_exists_by_name(
                operations, op_el
            )
            if duplicate_op_list:
                msg = (
                    "operation {action} already specified for {res}"
                    + ", use --force to override:\n{op}"
                )
                utils.err(
                    msg.format(
                        action=op_el.getAttribute("name"),
                        res=res_id,
                        op="\n".join(
                            [
                                operation_to_string(op)
                                for op in duplicate_op_list
                            ]
                        ),
                    )
                )

    operations.insertBefore(op_el, before_op)
    return dom


def resource_operation_remove(res_id, argv):
    """
    Commandline options:
      * -f - CIB file
    """
    # if no args, then we're removing an operation id

    # Do not ever remove an operations element, even if it is empty. There may
    # be ACLs set in pacemaker which allow "write" for op elements (adding,
    # changing and removing) but not operations elements. In such a case,
    # removing an operations element would cause the whole change to be
    # rejected by pacemaker with a "permission denied" message.
    # https://bugzilla.redhat.com/show_bug.cgi?id=1642514

    dom = utils.get_cib_dom()
    if not argv:
        for operation in dom.getElementsByTagName("op"):
            if operation.getAttribute("id") == res_id:
                parent = operation.parentNode
                parent.removeChild(operation)
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
    if not argv:
        remove_all = True

    op_properties = utils.convert_args_to_tuples(argv)
    op_properties.append(("name", op_name))
    found_match = False
    for op in resource_el.getElementsByTagName("op"):
        temp_properties = []
        for attrName in op.attributes.keys():
            if attrName == "id":
                continue
            temp_properties.append(
                tuple([attrName, op.attributes.get(attrName).nodeValue])
            )

        if remove_all and op.attributes["name"].value == op_name:
            found_match = True
            parent = op.parentNode
            parent.removeChild(op)
        elif not set(op_properties) ^ set(temp_properties):
            found_match = True
            parent = op.parentNode
            parent.removeChild(op)
            break

    if not found_match:
        utils.err("Unable to find operation matching: %s" % original_argv)

    utils.replace_cib_configuration(dom)


def resource_meta(lib, argv, modifiers):
    """
    Options:
      * --force - allow not suitable command
      * --wait
      * -f - CIB file
    """
    del lib
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
        and remote_node_name
        != utils.dom_get_resource_remote_node_name(resource_el)
    ):
        # if the resource was a remote node and it is not anymore, (or its name
        # changed) we need to tell pacemaker about it
        output, retval = utils.run(
            ["crm_node", "--force", "--remove", remote_node_name]
        )

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


def resource_group_rm_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("--wait", "-f")
    if not argv:
        raise CmdLineInputError()
    group_name = argv.pop(0)
    resource_ids = argv

    cib_dom = resource_group_rm(utils.get_cib_dom(), group_name, resource_ids)

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
    resource_names = argv
    adjacent_name = None
    after_adjacent = True
    if modifiers.is_specified("--after") and modifiers.is_specified("--before"):
        raise CmdLineInputError("you cannot specify both --before and --after")
    if modifiers.is_specified("--after"):
        adjacent_name = modifiers.get("--after")
        after_adjacent = True
    elif modifiers.is_specified("--before"):
        adjacent_name = modifiers.get("--before")
        after_adjacent = False

    lib.resource.group_add(
        group_name,
        resource_names,
        adjacent_resource_id=adjacent_name,
        put_after_adjacent=after_adjacent,
        wait=modifiers.get("--wait"),
    )


def resource_clone(lib, argv, modifiers, promotable=False):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f", "--wait")
    if not argv:
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

    resources_el = cib_dom.getElementsByTagName("resources")[0]
    element = utils.dom_get_resource(resources_el, name) or utils.dom_get_group(
        resources_el, name
    )
    if not element:
        utils.err("unable to find group or resource: %s" % name)

    if element.parentNode.tagName == "bundle":
        utils.err("cannot clone bundle resource")

    if not update_existing:
        if utils.dom_get_resource_clone(
            cib_dom, name
        ) or utils.dom_get_resource_masterslave(cib_dom, name):
            utils.err("%s is already a clone resource" % name)

        if utils.dom_get_group_clone(
            cib_dom, name
        ) or utils.dom_get_group_masterslave(cib_dom, name):
            utils.err("cannot clone a group that has already been cloned")
    else:
        if element.parentNode.tagName != "clone":
            utils.err("%s is not currently a clone" % name)
        clone = element.parentNode

    # If element is currently in a group and it's the last member, we get rid
    # of the group
    if (
        element.parentNode.tagName == "group"
        and element.parentNode.getElementsByTagName("primitive").length <= 1
    ):
        element.parentNode.parentNode.removeChild(element.parentNode)

    parts = parse_clone_args(argv, promotable=promotable)
    if not update_existing:
        clone_id = parts["clone_id"]
        if clone_id is not None:
            report_list = []
            validate_id(clone_id, reporter=report_list)
            if report_list:
                raise CmdLineInputError("invalid id '{}'".format(clone_id))
            if utils.does_id_exist(cib_dom, clone_id):
                raise CmdLineInputError(
                    "id '{}' already exists".format(clone_id),
                )
        else:
            clone_id = utils.find_unique_id(cib_dom, name + "-clone")
        clone = cib_dom.createElement("clone")
        clone.setAttribute("id", clone_id)
        clone.appendChild(element)
        resources_el.appendChild(clone)

    utils.dom_update_meta_attr(clone, sorted(parts["meta"].items()))

    return cib_dom, clone.getAttribute("id")


def resource_clone_master_remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --wait
    """
    del lib
    modifiers.ensure_only_supported("-f", "--wait")
    if len(argv) != 1:
        raise CmdLineInputError()

    name = argv.pop()
    dom = utils.get_cib_dom()
    resources_el = dom.documentElement.getElementsByTagName("resources")[0]

    # get the resource no matter if user entered a clone or a cloned resource
    resource = (
        utils.dom_get_resource(resources_el, name)
        or utils.dom_get_group(resources_el, name)
        or utils.dom_get_clone_ms_resource(resources_el, name)
    )
    if not resource:
        utils.err("could not find resource: %s" % name)
    resource_id = resource.getAttribute("id")
    clone = utils.dom_get_resource_clone_ms_parent(resources_el, resource_id)
    if not clone:
        utils.err("'%s' is not a clone resource" % name)

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    # if user requested uncloning a resource contained in a cloned group
    # remove the resource from the group and leave the clone itself alone
    # unless the resource is the last one in the group
    clone_child = utils.dom_get_clone_ms_resource(
        resources_el, clone.getAttribute("id")
    )
    if (
        clone_child.tagName == "group"
        and resource.tagName != "group"
        and len(clone_child.getElementsByTagName("primitive")) > 1
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


def resource_remove_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
    """
    del lib
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
        roles_with_nodes = get_resource_state(
            get_cluster_state_dom(
                lib_pacemaker.get_cluster_status_xml(utils.cmd_runner())
            ),
            bundle_id,
        )
        return bool(roles_with_nodes)

    # if the resource is referenced in tags then exit with an error message
    cib_xml = utils.get_cib()
    xml_etree = lib_pacemaker.get_cib(cib_xml)
    resource_el, dummy_report_list = find_one_resource(
        get_resources(xml_etree), resource_id
    )
    if resource_el is not None:
        tag_obj_ref_list = []
        for el in find_resources_to_delete(resource_el):
            xpath_result = get_tags(xml_etree).xpath(
                './/tag/obj_ref[@id="{0}"]'.format(el.get("id", "")),
            )
            if xpath_result:
                tag_obj_ref_list.extend(xpath_result)
        if tag_obj_ref_list:
            tag_id_list = sorted(
                {
                    obj_ref.getparent().get("id", "")
                    for obj_ref in tag_obj_ref_list
                }
            )
            utils.err(
                "Unable to remove resource '{resource}' because it is "
                "referenced in {tags}: {tag_id_list}".format(
                    resource=resource_id,
                    tags="tags" if len(tag_id_list) > 1 else "the tag",
                    tag_id_list=format_list(tag_id_list),
                )
            )

    dom = utils.get_cib_dom(cib_xml)
    # if resource is a clone or a master, work with its child instead
    cloned_resource = utils.dom_get_clone_ms_resource(dom, resource_id)
    if cloned_resource:
        resource_id = cloned_resource.getAttribute("id")

    bundle_el = utils.dom_get_bundle(dom, resource_id)
    if bundle_el is not None:
        primitive_el = utils.dom_get_resource_bundle(bundle_el)
        if primitive_el is None:
            print("Deleting bundle '{0}'".format(resource_id))
        else:
            print(
                "Deleting bundle '{0}' and its inner resource '{1}'".format(
                    resource_id, primitive_el.getAttribute("id")
                )
            )

        if (
            "--force" not in utils.pcs_options
            and not utils.usefile
            and is_bundle_running(resource_id)
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
                    "(re-run with --force to force deletion)" % resource_id
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
            "cibadmin",
            "-o",
            "resources",
            "-D",
            "--xpath",
            "//bundle[@id='{0}']".format(resource_id),
        ]
        dummy_cmdoutput, retVal = utils.run(args)
        if retVal != 0:
            utils.err("Unable to remove resource '{0}'".format(resource_id))
        return True

    if utils.does_exist('//group[@id="' + resource_id + '"]'):
        print(f"Removing group: {resource_id} (and all resources within group)")
        group = utils.get_cib_xpath('//group[@id="' + resource_id + '"]')
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
            for res in group_dom.documentElement.getElementsByTagName(
                "primitive"
            ):
                res_id = res.getAttribute("id")
                if utils.resource_running_on(res_id, state)["is_running"]:
                    stopped = False
                    break
            if not stopped:
                msg = [
                    "Unable to stop group: %s before deleting "
                    "(re-run with --force to force deletion)" % resource_id
                ]
                if retval != 0 and output:
                    msg.append("\n" + output)
                utils.err("\n".join(msg).strip())
        for res in group_dom.documentElement.getElementsByTagName("primitive"):
            resource_remove(res.getAttribute("id"))
        sys.exit(0)

    # now we know resource is not a group, a clone, a master nor a bundle
    # because of the conditions above
    if not utils.does_exist(
        '//resources/descendant::primitive[@id="' + resource_id + '"]'
    ):
        utils.err("Resource '{0}' does not exist.".format(resource_id))

    group_xpath = '//group/primitive[@id="' + resource_id + '"]/..'
    group = utils.get_cib_xpath(group_xpath)
    num_resources_in_group = 0

    if group != "":
        num_resources_in_group = len(
            parseString(group).documentElement.getElementsByTagName("primitive")
        )

    if (
        "--force" not in utils.pcs_options
        and not utils.usefile
        and utils.resource_running_on(resource_id)["is_running"]
    ):
        sys.stdout.write("Attempting to stop: " + resource_id + "... ")
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
                "(re-run with --force to force deletion)" % resource_id
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

    if group == "" or num_resources_in_group > 1:
        master_xpath = f'//master/primitive[@id="{resource_id}"]/..'
        clone_xpath = f'//clone/primitive[@id="{resource_id}"]/..'
        if utils.get_cib_xpath(clone_xpath) != "":
            args = ["cibadmin", "-o", "resources", "-D", "--xpath", clone_xpath]
        elif utils.get_cib_xpath(master_xpath) != "":
            args = [
                "cibadmin",
                "-o",
                "resources",
                "-D",
                "--xpath",
                master_xpath,
            ]
        else:
            args = [
                "cibadmin",
                "-o",
                "resources",
                "-D",
                "--xpath",
                f"//primitive[@id='{resource_id}']",
            ]
        if output is True:
            print("Deleting Resource - " + resource_id)
        output, retVal = utils.run(args)
        if retVal != 0:
            utils.err(
                f"unable to remove resource: {resource_id}, it may still be "
                "referenced in constraints."
            )
    else:
        top_master_xpath = (
            f'//master/group/primitive[@id="{resource_id}"]/../..'
        )
        top_clone_xpath = f'//clone/group/primitive[@id="{resource_id}"]/../..'
        top_master = utils.get_cib_xpath(top_master_xpath)
        top_clone = utils.get_cib_xpath(top_clone_xpath)
        if top_master != "":
            to_remove_xpath = top_master_xpath
            msg = "and group and M/S"
            to_remove_dom = parseString(top_master).getElementsByTagName(
                "master"
            )
            to_remove_id = to_remove_dom[0].getAttribute("id")
            utils.replace_cib_configuration(
                remove_resource_references(
                    utils.get_cib_dom(),
                    to_remove_dom[0]
                    .getElementsByTagName("group")[0]
                    .getAttribute("id"),
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
                    to_remove_dom[0]
                    .getElementsByTagName("group")[0]
                    .getAttribute("id"),
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
        if output is True:
            print("Deleting Resource (" + msg + ") - " + resource_id)
        dummy_cmdoutput, retVal = utils.run(args)
        if retVal != 0:
            if output is True:
                utils.err(
                    "Unable to remove resource '%s' (do constraints exist?)"
                    % (resource_id)
                )
            return False
    if remote_node_name and not utils.usefile:
        if not is_remove_remote_context:
            warn(
                "This command is not sufficient for removing remote and guest "
                "nodes. To complete the removal, remove pacemaker authkey and "
                "stop and disable pacemaker_remote on the node(s) manually."
            )
        output, retval = utils.run(["crm_resource", "--wait"])
        output, retval = utils.run(
            ["crm_node", "--force", "--remove", remote_node_name]
        )
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
    for obj_ref in dom.getElementsByTagName("obj_ref"):
        if obj_ref.getAttribute("id") == resource_id:
            tag = obj_ref.parentNode
            tag.removeChild(obj_ref)
            if tag.getElementsByTagName("obj_ref").length == 0:
                remove_resource_references(
                    dom,
                    tag.getAttribute("id"),
                    output=output,
                )
                tag.parentNode.removeChild(tag)
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
                utils.err(
                    "Resource '%s' does not exist in group '%s'"
                    % (resource_id, group_name)
                )

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
        and res_in_group > 1
        and len(resources_to_move) == res_in_group
    ):
        utils.err("Cannot remove all resources from a cloned group")
    target_node = group_match.parentNode
    if is_cloned_group and res_in_group > 1:
        target_node = dom.getElementsByTagName("resources")[0]
    for resource in resources_to_move:
        resource.parentNode.removeChild(resource)
        target_node.appendChild(resource)

    if not group_match.getElementsByTagName("primitive"):
        group_match.parentNode.removeChild(group_match)
        remove_resource_references(dom, group_name, output=True)

    return cib_dom


def resource_group_list(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    group_xpath = "//group"
    group_xml = utils.get_cib_xpath(group_xpath)

    # If no groups exist, we silently return
    if group_xml == "":
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


def resource_show(lib, argv, modifiers, stonith=False):
    # TODO remove, deprecated command
    # replaced with 'resource status' and 'resource config'
    """
    Options:
      * -f - CIB file
      * --full - print all configured options
      * --groups - print resource groups
      * --hide-inactive - print only active resources
    """
    modifiers.ensure_only_supported(
        "-f", "--full", "--groups", "--hide-inactive"
    )
    mutually_exclusive_opts = ("--full", "--groups", "--hide-inactive")
    specified_modifiers = [
        opt for opt in mutually_exclusive_opts if modifiers.is_specified(opt)
    ]
    if (len(specified_modifiers) > 1) or (argv and specified_modifiers):
        utils.err(
            "you can specify only one of resource id, {0}".format(
                ", ".join(mutually_exclusive_opts)
            )
        )

    if modifiers.get("--groups"):
        warn(
            "This command is deprecated and will be removed. "
            "Please use 'pcs resource group list' instead."
        )
        resource_group_list(lib, argv, modifiers.get_subset("-f"))
        return

    if modifiers.get("--full") or argv:
        warn(
            "This command is deprecated and will be removed. "
            "Please use 'pcs {} config' instead.".format(
                "stonith" if stonith else "resource"
            )
        )
        resource_config(lib, argv, modifiers.get_subset("-f"), stonith=stonith)
        return

    warn(
        "This command is deprecated and will be removed. "
        "Please use 'pcs {} status' instead.".format(
            "stonith" if stonith else "resource"
        )
    )
    resource_status(
        lib,
        argv,
        modifiers.get_subset("-f", "--hide-inactive"),
        stonith=stonith,
    )


def resource_status(lib, argv, modifiers, stonith=False):
    """
    Options:
      * -f - CIB file
      * --hide-inactive - print only active resources
    """
    del lib
    modifiers.ensure_only_supported("-f", "--hide-inactive")
    if len(argv) > 1:
        raise CmdLineInputError()

    monitor_command = ["crm_mon", "--one-shot"]
    if not modifiers.get("--hide-inactive"):
        monitor_command.append("--inactive")
    if argv:
        resource_or_tag_id = argv[0]
        crm_mon_err_msg = (
            f"unable to get status of '{resource_or_tag_id}' from crm_mon\n"
        )
        monitor_command.extend(
            ["--include", "none,resources", "--resource", resource_or_tag_id]
        )
    else:
        resource_or_tag_id = None
        crm_mon_err_msg = "unable to get cluster status from crm_mon\n"

    output, retval = utils.run(monitor_command)
    if retval != 0:
        utils.err(crm_mon_err_msg + output.rstrip())
    preg = re.compile(r".*(stonith:.*)")
    resources_header = False
    in_resources = False
    has_resources = False
    no_resources_line = (
        "NO stonith devices configured"
        if stonith
        else "NO resources configured"
    )
    for line in output.split("\n"):
        if line == "No active resources":  # some old pacemaker
            print(line)
            return
        if line in (
            "  * No resources",  # pacemaker >= 2.0.3
            "No resources",  # pacemaker < 2.0.3
        ):
            if resource_or_tag_id:
                utils.err(
                    f"resource or tag id '{resource_or_tag_id}' not found"
                )
            print(no_resources_line)
            return
        if line == "Full List of Resources:":  # pacemaker >= 2.0.3
            in_resources = True
            continue
        if line in (
            "Full list of resources:",  # pacemaker < 2.0.3
            "Active resources:",  # some old pacemaker
        ):
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
            if resource_or_tag_id:
                has_resources = True
                print(line)
                continue
            if not preg.match(line) and not stonith:
                has_resources = True
                print(line)
            elif preg.match(line) and stonith:
                has_resources = True
                print(line)


def _resource_stonith_lines(resource_el, only_stonith):
    is_stonith = (
        "class" in resource_el.attrib
        and resource_el.attrib["class"] == "stonith"
    )
    if (only_stonith and is_stonith) or (not only_stonith and not is_stonith):
        return resource_node_lines(resource_el)
    return []


def resource_config(lib, argv, modifiers, stonith=False):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")

    root = utils.get_cib_etree()
    resources = root.find(".//resources")
    if not argv:
        for resource in resources:
            lines = _resource_stonith_lines(resource, only_stonith=stonith)
            if lines:
                print("\n".join(indent(lines, indent_step=1)))
        return

    for resource_id in argv:
        resource_found = False
        for resource in resources.findall(str(".//*")):
            if "id" in resource.attrib and resource.attrib["id"] == resource_id:
                lines = _resource_stonith_lines(resource, only_stonith=stonith)
                if lines:
                    print("\n".join(indent(lines, indent_step=1)))
                    resource_found = True
                    break
        if not resource_found:
            utils.err(f"unable to find resource '{resource_id}'")


def resource_disable_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --brief - show brief output of --simulate
      * --safe - only disable if no other resource gets stopped or demoted
      * --simulate - do not push the CIB, print its effects
      * --no-strict - allow disable if other resource is affected
      * --wait
    """
    modifiers.ensure_only_supported(
        "-f", "--brief", "--safe", "--simulate", "--no-strict", "--wait"
    )
    modifiers.ensure_not_mutually_exclusive("-f", "--simulate", "--wait")
    modifiers.ensure_not_incompatible("--simulate", {"-f", "--safe", "--wait"})
    modifiers.ensure_not_incompatible("--safe", {"-f", "--simulate", "--brief"})
    modifiers.ensure_not_incompatible("--no-strict", {"-f"})

    if not argv:
        raise CmdLineInputError("You must specify resource(s) to disable")

    if modifiers.get("--simulate"):
        result = lib.resource.disable_simulate(
            argv, not modifiers.get("--no-strict")
        )
        if modifiers.get("--brief"):
            # if the result is empty, printing it would produce a new line,
            # which is not wanted
            if result["other_affected_resource_list"]:
                print("\n".join(result["other_affected_resource_list"]))
            return
        print(result["plaintext_simulated_status"])
        return
    if modifiers.get("--safe") or modifiers.get("--no-strict"):
        lib.resource.disable_safe(
            argv,
            not modifiers.get("--no-strict"),
            modifiers.get("--wait"),
        )
        return
    lib.resource.disable(argv, modifiers.get("--wait"))


def resource_safe_disable_cmd(
    lib: Any, argv: List[str], modifiers: InputModifiers
) -> None:
    """
    Options:
      * --brief - show brief output of --simulate
      * --force - skip checks for safe resource disable
      * --no-strict - allow disable if other resource is affected
      * --simulate - do not push the CIB, print its effects
      * --wait
    """
    modifiers.ensure_only_supported(
        "--brief", "--force", "--no-strict", "--simulate", "--wait"
    )
    modifiers.ensure_not_incompatible("--force", {"--no-strict", "--simulate"})
    custom_options = {}
    if modifiers.get("--force"):
        warn(
            "option '--force' is specified therefore checks for disabling "
            "resource safely will be skipped"
        )
    elif not modifiers.get("--simulate"):
        custom_options["--safe"] = True
    resource_disable_cmd(
        lib,
        argv,
        modifiers.get_subset(
            "--wait", "--no-strict", "--simulate", "--brief", **custom_options
        ),
    )


def resource_enable_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to enable")
    resources = argv
    lib.resource.enable(resources, modifiers.get("--wait"))


# DEPRECATED, moved to pcs.lib.commands.resource
def resource_disable(argv):
    """
    Commandline options:
      * -f - CIB file
      * --wait
    """
    if not argv:
        utils.err("You must specify a resource to disable")

    resource = argv[0]
    if not is_managed(resource):
        print("Warning: '%s' is unmanaged" % resource)

    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout()

    args = [
        "crm_resource",
        "-r",
        argv[0],
        "-m",
        "-p",
        "target-role",
        "-v",
        "Stopped",
    ]
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
        msg = []
        if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
            msg.append("waiting timeout")
        else:
            msg.append(
                "unable to stop: '%s', please check logs for failure "
                "information" % resource
            )
        msg.append(running_on["message"])
        if retval != 0 and output:
            msg.append("\n" + output)
        utils.err("\n".join(msg).strip())
    return None


def resource_restart(lib, argv, modifiers):
    """
    Options:
      * --wait
    """
    del lib
    modifiers.ensure_only_supported("--wait")
    if not argv:
        utils.err("You must specify a resource to restart")

    dom = utils.get_cib_dom()
    node = None
    resource = argv.pop(0)

    real_res = utils.dom_get_resource_clone_ms_parent(
        dom, resource
    ) or utils.dom_get_resource_bundle_parent(dom, resource)
    if real_res:
        print(
            (
                "Warning: using %s... (if a resource is a clone or bundle you "
                "must use the clone or bundle name)"
            )
            % real_res.getAttribute("id")
        )
        resource = real_res.getAttribute("id")

    args = ["crm_resource", "--restart", "--resource", resource]
    if argv:
        node = argv.pop(0)
        if not (
            utils.dom_get_clone(dom, resource)
            or utils.dom_get_master(dom, resource)
            or utils.dom_get_bundle(dom, resource)
        ):
            utils.err(
                "can only restart on a specific node for a clone or bundle "
                "resource"
            )
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


def resource_force_action(lib, argv, modifiers, action=None):
    """
    Options:
      * --force
      * --full - more verbose output
    """
    del lib
    modifiers.ensure_only_supported("--force", "--full")
    if action is None:
        raise CmdLineInputError()
    if not argv:
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
        or utils.dom_get_bundle(dom, resource)
    ):
        utils.err(
            "unable to find a resource/clone/group/bundle: {0}".format(resource)
        )
    bundle_el = utils.dom_get_bundle(dom, resource)
    if bundle_el:
        bundle_resource = utils.dom_get_resource_bundle(bundle_el)
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
            (
                "unable to {0} a group, try one of the group's resource(s) "
                "({1})"
            ).format(action, ",".join(group_resources))
        )
    if utils.dom_get_clone(dom, resource) or utils.dom_get_master(
        dom, resource
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
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to manage")
    resources = argv
    lib.resource.manage(resources, with_monitor=modifiers.get("--monitor"))


def resource_unmanage_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --monitor - bisable monitor operation of specified resorces
    """
    modifiers.ensure_only_supported("-f", "--monitor")
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to unmanage")
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
    return False  # pylint does not know utils.err raises


def resource_failcount(lib, argv, modifiers):
    """
    Options:
      * --full
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--full")
    if not argv:
        raise CmdLineInputError()

    command = argv.pop(0)
    # Print error messages which point users to the changes section in pcs
    # manpage.
    # To be removed in the next significant version.
    if command == "reset":
        raise_command_replaced("pcs resource cleanup")

    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options_allowed(
        argv, {"node", "operation", "interval"}
    )
    node = parsed_options.get("node")
    operation = parsed_options.get("operation")
    interval = parsed_options.get("interval")

    if command == "show":
        print(
            resource_failcount_show(
                lib,
                resource,
                node,
                operation,
                interval,
                modifiers.get("--full"),
            )
        )
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
        node=node, resource=resource, operation=operation, interval=interval
    )


def resource_failcount_show(lib, resource, node, operation, interval, full):
    """
    Commandline options:
      * -f - CIB file
    """
    result_lines = []
    failures_data = lib.resource.get_failcounts(
        resource=resource, node=node, operation=operation, interval=interval
    )

    if not failures_data:
        result_lines.append(
            __headline_resource_failures(
                True, resource, node, operation, interval
            )
        )
        return "\n".join(result_lines)

    resource_list = sorted({fail["resource"] for fail in failures_data})
    for current_resource in resource_list:
        result_lines.append(
            __headline_resource_failures(
                False, current_resource, node, operation, interval
            )
        )
        resource_failures = [
            fail
            for fail in failures_data
            if fail["resource"] == current_resource
        ]
        node_list = sorted({fail["node"] for fail in resource_failures})
        for current_node in node_list:
            node_failures = [
                fail
                for fail in resource_failures
                if fail["node"] == current_node
            ]
            if full:
                result_lines.append(f"  {current_node}:")
                operation_list = sorted(
                    {fail["operation"] for fail in node_failures}
                )
                for current_operation in operation_list:
                    operation_failures = [
                        fail
                        for fail in node_failures
                        if fail["operation"] == current_operation
                    ]
                    interval_list = sorted(
                        {fail["interval"] for fail in operation_failures},
                        # pacemaker's definition of infinity
                        key=lambda x: 1000000 if x == "INFINITY" else x,
                    )
                    for current_interval in interval_list:
                        interval_failures = [
                            fail
                            for fail in operation_failures
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


def resource_node_lines(node):
    """
    Commandline options: no options
    """
    simple_types = {
        "clone": "Clone",
        "group": "Group",
        "primitive": "Resource",
    }
    lines = []
    if node.tag in simple_types.keys():
        lines.append(
            f"{simple_types[node.tag]}: {node.attrib['id']}"
            + _get_attrs(node, " (", ")")
        )
        lines.extend(
            indent(
                _instance_vars_lines(node)
                + _meta_vars_lines(node)
                + _operations_lines(node),
                indent_step=1,
            )
        )
        for child in node:
            lines.extend(indent(resource_node_lines(child), indent_step=1))
        return lines
    if node.tag == "master":
        lines.append(
            f"Clone: {node.attrib['id']}" + _get_attrs(node, " (", ")")
        )
        lines.extend(
            indent(
                _instance_vars_lines(node)
                + _meta_vars_lines(node, extra_vars_dict={"promotable": "true"})
                + _operations_lines(node),
                indent_step=1,
            )
        )
        for child in node:
            lines.extend(indent(resource_node_lines(child), indent_step=1))
        return lines
    if node.tag == "bundle":
        lines.append(
            f"Bundle: {node.attrib['id']}" + _get_attrs(node, " (", ")")
        )
        lines.extend(
            indent(
                _bundle_container_strings(node)
                + _bundle_network_strings(node)
                + _bundle_mapping_strings(
                    "Port Mapping:",
                    node.findall("network/port-mapping"),
                )
                + _bundle_mapping_strings(
                    "Storage Mapping:",
                    node.findall("storage/storage-mapping"),
                )
                + _meta_vars_lines(node),
                indent_step=1,
            )
        )
        for child in node:
            lines.extend(indent(resource_node_lines(child), indent_step=1))
        return lines
    return lines


def _bundle_container_strings(bundle_el):
    """
    Commandline options: no options
    """
    lines = []
    for container_type in bundle.GENERIC_CONTAINER_TYPES:
        container_list = bundle_el.findall(container_type)
        for container_el in container_list:
            lines.append(
                container_el.tag.capitalize()
                + _get_attrs(container_el, ": ", "")
            )
    return lines


def _bundle_network_strings(bundle_el):
    """
    Commandline options: no options
    """
    lines = []
    network_list = bundle_el.findall("network")
    for network_el in network_list:
        attrs_string = _get_attrs(network_el)
        if attrs_string:
            lines.append("Network: " + attrs_string)
    return lines


def _bundle_mapping_strings(first_line, map_items):
    """
    Commandline options: no options
    """
    map_lines = [
        _get_attrs(item, "", " ") + "(" + item.attrib["id"] + ")"
        for item in map_items
    ]
    if map_lines:
        return [first_line] + indent(map_lines, indent_step=1)
    return []


def _nvpairs_strings(node, parent_tag, extra_vars_dict=None):
    """
    Commandline options: no options
    """
    # In the new architecture, this is implemented in pcs.cli.nvset.
    key_val = {
        nvpair.attrib["name"]: nvpair.attrib["value"]
        for nvpair in node.findall(f"{parent_tag}/nvpair")
    }
    if extra_vars_dict:
        key_val.update(extra_vars_dict)
    strings = []
    for name, value in sorted(key_val.items()):
        if " " in value:
            value = f'"{value}"'
        strings.append(f"{name}={value}")
    return strings


def _instance_vars_lines(node):
    """
    Commandline options: no options
    """
    nvpairs = _nvpairs_strings(node, "instance_attributes")
    return ["Attributes: " + " ".join(nvpairs)] if nvpairs else []


def _meta_vars_lines(node, extra_vars_dict=None):
    """
    Commandline options: no options
    """
    nvpairs = _nvpairs_strings(
        node, "meta_attributes", extra_vars_dict=extra_vars_dict
    )
    return ["Meta Attrs: " + " ".join(nvpairs)] if nvpairs else []


def _operations_lines(node):
    """
    Commandline options: no options
    """
    op_lines = []
    for op in node.findall("operations/op"):
        parts = []
        parts.append(op.attrib["name"])
        parts.extend(
            [
                f"{name}={value}"
                for name, value in sorted(op.attrib.items())
                if name not in {"id", "name"}
            ]
        )
        parts.extend(_nvpairs_strings(op, "./"))
        parts.append(f"({op.attrib['id']})")
        op_lines.append(" ".join(parts))
    if not op_lines:
        return op_lines
    label = "Operations: "
    return [label + op_lines[0]] + indent(op_lines[1:], indent_step=len(label))


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


def _get_attrs(node, prepend_string="", append_string=""):
    """
    Commandline options: no options
    """
    output = ""
    for attr, val in sorted(node.attrib.items()):
        if attr in ["id"]:
            continue
        if " " in val:
            val = '"' + val + '"'
        output += attr + "=" + val + " "
    if output != "":
        return prepend_string + output.rstrip() + append_string
    return output.rstrip()


def resource_cleanup(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported("--strict")
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options_allowed(
        argv, {"node", "operation", "interval"}
    )
    print(
        lib_pacemaker.resource_cleanup(
            utils.cmd_runner(),
            resource=resource,
            node=parsed_options.get("node"),
            operation=parsed_options.get("operation"),
            interval=parsed_options.get("interval"),
            strict=modifiers.get("--strict"),
        )
    )


def resource_refresh(lib, argv, modifiers):
    """
    Options:
      * --full - refresh a resource on all nodes
      * --force - do refresh even though it may be time consuming
    """
    del lib
    # TODO deprecated
    # remove --full, see rhbz#1759269
    # --full previously did what --strict was supposed to do (set --force
    # flag for crm_resource). It was misnamed '--full' because we thought it
    # was meant to be doing something else than what the --force in
    # crm_resource actualy did.
    modifiers.ensure_only_supported("--force", "--full", "--strict")
    if modifiers.is_specified("--full"):
        sys.stderr.write("Warning: '--full' has been deprecated\n")
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parsed_options = prepare_options_allowed(argv, {"node"})
    print(
        lib_pacemaker.resource_refresh(
            utils.cmd_runner(),
            resource=resource,
            node=parsed_options.get("node"),
            strict=(modifiers.get("--strict") or modifiers.get("--full")),
            force=modifiers.get("--force"),
        )
    )


def resource_relocate_show_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    resource_relocate_show(utils.get_cib_dom())


def resource_relocate_dry_run_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    resource_relocate_run(utils.get_cib_dom(), argv, dry=True)


def resource_relocate_run_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    resource_relocate_run(utils.get_cib_dom(), argv, dry=False)


def resource_relocate_clear_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
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
    cib_dom = cib_dom.cloneNode(True)  # do not change the original cib
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
                + res_el.getElementsByTagName("group")
                + res_el.getElementsByTagName("primitive")
            )
            updated_resources.update(
                [el.getAttribute("id") for el in res_and_children]
            )
            for res_or_child in res_and_children:
                meta_attributes = utils.dom_prepare_child_element(
                    res_or_child,
                    "meta_attributes",
                    res_or_child.getAttribute("id") + "-meta_attributes",
                )
                utils.dom_update_nv_pair(
                    meta_attributes,
                    "resource-stickiness",
                    "0",
                    meta_attributes.getAttribute("id") + "-",
                )
    # resources don't exist
    if resources:
        resources_not_found = set(resources) - resources_found
        if resources_not_found:
            for res_id in resources_not_found:
                utils.err(
                    "unable to find a resource/clone/group: {0}".format(res_id),
                    False,
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
        val
        for val in locations.values()
        if val["id"] in updated_resources
        or val["id_for_constraint"] in updated_resources
    ]


def resource_relocate_show(cib_dom):
    """
    Commandline options: no options
    """
    updated_cib, dummy_updated_resources = resource_relocate_set_stickiness(
        cib_dom
    )
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
    message = (
        "Creating location constraint: {res} prefers {node}=INFINITY{role}"
    )
    if "start_on_node" in location:
        return message.format(
            res=location["id_for_constraint"],
            node=location["start_on_node"],
            role="",
        )
    if "promote_on_node" in location:
        return message.format(
            res=location["id_for_constraint"],
            node=location["promote_on_node"],
            role=" role=Master",
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
    was_error = False
    anything_changed = False
    if not dry and utils.usefile:
        utils.err("This command cannot be used with -f")

    # create constraints
    cib_dom, constraint_el = constraint.getCurrentConstraints(cib_dom)
    for location in resource_relocate_get_locations(cib_dom, resources):
        if not ("start_on_node" in location or "promote_on_node" in location):
            continue
        anything_changed = True
        print(resource_relocate_location_to_str(location))
        constraint_id = utils.find_unique_id(
            cib_dom,
            RESOURCE_RELOCATE_CONSTRAINT_PREFIX + location["id_for_constraint"],
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
            was_error = True
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                utils.err("waiting timeout", False)
            else:
                utils.err(output, False)

    # remove constraints
    resource_relocate_clear(cib_dom)
    if not dry:
        utils.replace_cib_configuration(cib_dom)

    if was_error:
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
def get_resource_agent_info(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        utils.err("One parameter expected")

    agent = argv[0]

    runner = utils.cmd_runner()

    try:
        metadata = lib_ra.ResourceAgent(runner, agent)
        print(json.dumps(metadata.get_full_info()))
    except lib_ra.ResourceAgentError as e:
        process_library_reports([lib_ra.resource_agent_error_to_report_item(e)])


def resource_bundle_create_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * --disabled - create as a stopped bundle
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--disabled", "--wait", "-f")
    if not argv:
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


def resource_bundle_reset_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options
      * --disabled - create as a stopped bundle
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--disabled", "--wait", "-f")
    if not argv:
        raise CmdLineInputError()

    bundle_id = argv[0]
    parts = parse_bundle_reset_options(argv[1:])
    lib.resource.bundle_reset(
        bundle_id,
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
    if not argv:
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
