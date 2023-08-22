# pylint: disable=too-many-lines
import json
import re
import sys
import textwrap
import time
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    Tuple,
    cast,
)
from xml.dom.minidom import parseString

import pcs.lib.cib.acl as lib_acl
import pcs.lib.pacemaker.live as lib_pacemaker
import pcs.lib.resource_agent as lib_ra
from pcs import (
    constraint,
    utils,
)
from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common.errors import (
    SEE_MAN_CHANGES,
    CmdLineInputError,
    raise_command_replaced,
)
from pcs.cli.common.output import smart_wrap_text
from pcs.cli.common.parse_args import (
    FUTURE_OPTION,
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
    KeyValueParser,
    group_by_keywords,
    wait_to_timeout,
)
from pcs.cli.common.tools import (
    print_to_stderr,
    timeout_to_seconds_legacy,
)
from pcs.cli.nvset import nvset_dto_list_to_lines
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import (
    deprecation_warning,
    warn,
)
from pcs.cli.resource.output import (
    ResourcesConfigurationFacade,
    resource_agent_metadata_to_text,
    resources_to_cmd,
    resources_to_text,
)
from pcs.cli.resource.parse_args import (
    parse_bundle_create_options,
    parse_bundle_reset_options,
    parse_bundle_update_options,
    parse_clone,
    parse_create_new,
    parse_create_old,
)
from pcs.cli.resource_agent import find_single_agent
from pcs.common import (
    const,
    pacemaker,
    reports,
)
from pcs.common.interface import dto
from pcs.common.pacemaker.defaults import CibDefaultsDto
from pcs.common.pacemaker.resource.list import CibResourcesDto
from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
)
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.common.str_tools import (
    format_list,
    format_list_custom_last_separator,
    format_optional,
)
from pcs.lib.cib.resource import (
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
    _get_nodes_to_validate_against,
    _validate_guest_change,
)
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import get_resource_state
from pcs.lib.pacemaker.values import (
    is_true,
    validate_id,
)
from pcs.settings import (
    pacemaker_wait_timeout_status as PACEMAKER_WAIT_TIMEOUT_STATUS,
)

# pylint: disable=invalid-name
# pylint: disable=too-many-branches
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-statements

RESOURCE_RELOCATE_CONSTRAINT_PREFIX = "pcs-relocate-"


def _check_is_not_stonith(
    lib: Any, resource_id_list: List[str], cmd_to_use: Optional[str] = None
) -> None:
    if lib.resource.is_any_stonith(resource_id_list):
        deprecation_warning(
            reports.messages.ResourceStonithCommandsMismatch(
                "stonith resources"
            ).message
            + format_optional(cmd_to_use, " Please use '{}' instead.")
        )


def _detect_guest_change(
    meta_attributes: Dict[str, str], allow_not_suitable_command: bool
) -> None:
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


def resource_utilization_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    utils.print_warning_if_utilization_attrs_has_no_effect(
        PropertyConfigurationFacade.from_properties_dtos(
            lib.cluster_property.get_properties(),
            lib.cluster_property.get_properties_metadata(),
        )
    )
    if not argv:
        print_resources_utilization()
        return
    resource_id = argv.pop(0)
    _check_is_not_stonith(lib, [resource_id])
    if argv:
        set_resource_utilization(resource_id, argv)
    else:
        print_resource_utilization(resource_id)


def _defaults_set_create_cmd(
    lib_command: Callable[..., Any], argv: Argv, modifiers: InputModifiers
) -> Any:
    modifiers.ensure_only_supported("-f", "--force")

    groups = group_by_keywords(
        argv, set(["meta", "rule"]), implicit_first_keyword="options"
    )
    groups.ensure_unique_keywords()
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)

    lib_command(
        KeyValueParser(groups.get_args_flat("meta")).get_unique(),
        KeyValueParser(groups.get_args_flat("options")).get_unique(),
        nvset_rule=(
            " ".join(groups.get_args_flat("rule"))
            if groups.get_args_flat("rule")
            else None
        ),
        force_flags=force_flags,
    )


def resource_defaults_set_create_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
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
    lib: Any, argv: Argv, modifiers: InputModifiers
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
    lib_command: Callable[[bool], CibDefaultsDto],
    argv: Argv,
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
    lines = nvset_dto_list_to_lines(
        lib_command(not modifiers.get("--no-expire-check")).meta_attributes,
        nvset_label="Meta Attrs",
        with_ids=cast(bool, modifiers.get("--full")),
        include_expired=cast(bool, modifiers.get("--all")),
    )
    if lines:
        print("\n".join(lines))


def resource_defaults_config_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
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
    lib: Any, argv: Argv, modifiers: InputModifiers
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
    lib_command: Callable[..., Any], argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    lib_command(argv)


def resource_defaults_set_remove_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_remove_cmd(
        lib.cib_options.resource_defaults_remove, argv, modifiers
    )


def resource_op_defaults_set_remove_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_remove_cmd(
        lib.cib_options.operation_defaults_remove, argv, modifiers
    )


def _defaults_set_update_cmd(
    lib_command: Callable[..., Any], argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    set_id = argv[0]
    groups = group_by_keywords(argv[1:], set(["meta"]))
    groups.ensure_unique_keywords()
    lib_command(
        set_id, KeyValueParser(groups.get_args_flat("meta")).get_unique()
    )


def resource_defaults_set_update_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    return _defaults_set_update_cmd(
        lib.cib_options.resource_defaults_update, argv, modifiers
    )


def resource_op_defaults_set_update_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
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
    argv: Argv,
    modifiers: InputModifiers,
    deprecated_syntax_used: bool = False,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    del modifiers
    if deprecated_syntax_used:
        deprecation_warning(
            "This command is deprecated and will be removed. "
            "Please use 'pcs resource defaults update' instead."
        )
    return lib.cib_options.resource_defaults_update(
        None, KeyValueParser(argv).get_unique()
    )


def resource_op_defaults_legacy_cmd(
    lib: Any,
    argv: Argv,
    modifiers: InputModifiers,
    deprecated_syntax_used: bool = False,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    del modifiers
    if deprecated_syntax_used:
        deprecation_warning(
            "This command is deprecated and will be removed. "
            "Please use 'pcs resource op defaults update' instead."
        )
    return lib.cib_options.operation_defaults_update(
        None, KeyValueParser(argv).get_unique()
    )


def op_add_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    if not argv:
        raise CmdLineInputError()
    _check_is_not_stonith(lib, [argv[0]], "pcs stonith op add")
    resource_op_add(argv, modifiers)


def resource_op_add(argv: Argv, modifiers: InputModifiers) -> None:
    """
    Commandline options:
      * -f - CIB file
      * --force - allow unknown options
    """
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
    dom = None
    op_properties = utils.convert_args_to_tuples(argv[1:])
    for key, value in op_properties:
        if key == "on-fail" and value == "demote":
            dom = utils.cluster_upgrade_to_version(
                const.PCMK_ON_FAIL_DEMOTE_CIB_VERSION
            )
            break
    if dom is None:
        dom = utils.get_cib_dom()

    # add the requested operation
    utils.replace_cib_configuration(resource_operation_add(dom, res_id, argv))


def op_delete_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    resource_id = argv.pop(0)
    _check_is_not_stonith(lib, [resource_id], "pcs stonith op delete")
    resource_operation_remove(resource_id, argv)


def parse_resource_options(
    argv: Argv,
) -> Tuple[List[str], List[List[str]], List[str]]:
    """
    Commandline options: no options
    """
    ra_values = []
    op_values: List[List[str]] = []
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


def resource_list_available(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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


def resource_list_options(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --full - show advanced
    """
    modifiers.ensure_only_supported("--full")
    if len(argv) != 1:
        raise CmdLineInputError()

    agent_name_str = argv[0]
    agent_name: ResourceAgentNameDto
    if ":" in agent_name_str:
        agent_name = lib.resource_agent.get_structured_agent_name(
            agent_name_str
        )
    else:
        agent_name = find_single_agent(
            lib.resource_agent.get_agents_list().names, agent_name_str
        )
    if agent_name.standard == "stonith":
        deprecation_warning(
            reports.messages.ResourceStonithCommandsMismatch(
                "stonith / fence agents"
            ).message
            + " Please use 'pcs stonith describe' instead."
        )
    print(
        "\n".join(
            smart_wrap_text(
                resource_agent_metadata_to_text(
                    lib.resource_agent.get_agent_metadata(agent_name),
                    lib.resource_agent.get_agent_default_operations(
                        agent_name
                    ).operations,
                    verbose=modifiers.is_specified("--full"),
                )
            )
        )
    )


# Return the string formatted with a line length of terminal width  and indented
def _format_desc(indentation: int, desc: str) -> str:
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


def resource_create(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --agent-validation - use agent self validation of instance attributes
      * --before - specified resource inside a group before which new resource
        will be placed inside the group
      * --after - specified resource inside a group after which new resource
        will be placed inside the group
      * --group - specifies group in which resource will be created
      * --force - allow not existing agent, invalid operations or invalid
        instance attributes, allow not suitable command
      * --disabled - created resource will be disabled
      * --no-default-ops - do not add default operations
      * --wait
      * -f - CIB file
      * --future - enable future cli parser behavior
    """
    modifiers_deprecated = ["--before", "--after", "--group"]
    modifiers.ensure_only_supported(
        *(
            [
                "--agent-validation",
                "--force",
                "--disabled",
                "--no-default-ops",
                "--wait",
                "-f",
                FUTURE_OPTION,
            ]
            + ([] if modifiers.get(FUTURE_OPTION) else modifiers_deprecated)
        )
    )
    if len(argv) < 2:
        raise CmdLineInputError()

    ra_id = argv[0]
    ra_type = argv[1]

    if modifiers.get(FUTURE_OPTION):
        parts = parse_create_new(argv[2:])
    else:
        parts = parse_create_old(
            argv[2:], modifiers.get_subset(*modifiers_deprecated)
        )

    defined_options = set()
    if parts.bundle_id:
        defined_options.add("bundle")
    if parts.clone:
        defined_options.add("clone")
    if parts.promotable:
        defined_options.add("promotable")
    if parts.group:
        defined_options.add("group")
    if len(defined_options) > 1:
        raise CmdLineInputError(
            "you can specify only one of clone, promotable, bundle or {}group".format(
                "" if modifiers.get(FUTURE_OPTION) else "--"
            )
        )

    if parts.group:
        if parts.group.after_resource and parts.group.before_resource:
            raise CmdLineInputError(
                "you cannot specify both 'before' and 'after'"
                if modifiers.get(FUTURE_OPTION)
                else "you cannot specify both --before and --after"
            )

    if parts.promotable and "promotable" in parts.promotable.meta_attrs:
        raise CmdLineInputError(
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
        enable_agent_self_validation=modifiers.get("--agent-validation"),
    )

    if parts.clone:
        lib.resource.create_as_clone(
            ra_id,
            ra_type,
            parts.primitive.operations,
            parts.primitive.meta_attrs,
            parts.primitive.instance_attrs,
            parts.clone.meta_attrs,
            clone_id=parts.clone.clone_id,
            allow_incompatible_clone_meta_attributes=modifiers.get("--force"),
            **settings,
        )
    elif parts.promotable:
        lib.resource.create_as_clone(
            ra_id,
            ra_type,
            parts.primitive.operations,
            parts.primitive.meta_attrs,
            parts.primitive.instance_attrs,
            dict(**parts.promotable.meta_attrs, promotable="true"),
            clone_id=parts.promotable.clone_id,
            allow_incompatible_clone_meta_attributes=modifiers.get("--force"),
            **settings,
        )
    elif parts.bundle_id:
        settings["allow_not_accessible_resource"] = modifiers.get("--force")
        lib.resource.create_into_bundle(
            ra_id,
            ra_type,
            parts.primitive.operations,
            parts.primitive.meta_attrs,
            parts.primitive.instance_attrs,
            parts.bundle_id,
            **settings,
        )
    elif parts.group:
        adjacent_resource_id = None
        put_after_adjacent = False
        if parts.group.after_resource:
            adjacent_resource_id = parts.group.after_resource
            put_after_adjacent = True
        if parts.group.before_resource:
            adjacent_resource_id = parts.group.before_resource
            put_after_adjacent = False

        lib.resource.create_in_group(
            ra_id,
            ra_type,
            parts.group.group_id,
            parts.primitive.operations,
            parts.primitive.meta_attrs,
            parts.primitive.instance_attrs,
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
            **settings,
        )
    else:
        lib.resource.create(
            ra_id,
            ra_type,
            parts.primitive.operations,
            parts.primitive.meta_attrs,
            parts.primitive.instance_attrs,
            **settings,
        )


def _parse_resource_move_ban(
    argv: Argv,
) -> Tuple[str, Optional[str], Optional[str]]:
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


def resource_move_with_constraint(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --promoted
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--promoted", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to move")
    if len(argv) > 3:
        raise CmdLineInputError()
    resource_id, node, lifetime = _parse_resource_move_ban(argv)

    lib.resource.move(
        resource_id,
        node=node,
        master=modifiers.is_specified("--promoted"),
        lifetime=lifetime,
        wait=modifiers.get("--wait"),
    )


def resource_move(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --autodelete - deprecated, not needed anymore
      * --promoted
      * --strict
      * --wait
    """
    modifiers.ensure_only_supported(
        "--autodelete", "--promoted", "--strict", "--wait"
    )

    if not argv:
        raise CmdLineInputError("must specify a resource to move")
    resource_id = argv.pop(0)
    node = None
    if argv:
        node = argv.pop(0)
        if node.startswith("lifetime="):
            deprecation_warning(
                "Option 'lifetime' has been removed. {}".format(
                    SEE_MAN_CHANGES.format("0.11")
                )
            )
    if argv:
        raise CmdLineInputError()

    if modifiers.is_specified("--autodelete"):
        deprecation_warning(
            "Option '--autodelete' is deprecated. There is no need to use it "
            "as its functionality is default now."
        )

    lib.resource.move_autoclean(
        resource_id,
        node=node,
        master=modifiers.is_specified("--promoted"),
        wait_timeout=wait_to_timeout(modifiers.get("--wait")),
        strict=modifiers.get("--strict"),
    )


def resource_ban(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --promoted
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--promoted", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to ban")
    if len(argv) > 3:
        raise CmdLineInputError()
    resource_id, node, lifetime = _parse_resource_move_ban(argv)

    lib.resource.ban(
        resource_id,
        node=node,
        master=modifiers.is_specified("--promoted"),
        lifetime=lifetime,
        wait=modifiers.get("--wait"),
    )


def resource_unmove_unban(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --promoted
      * --wait
    """
    modifiers.ensure_only_supported("-f", "--expired", "--promoted", "--wait")

    if not argv:
        raise CmdLineInputError("must specify a resource to clear")
    if len(argv) > 2:
        raise CmdLineInputError()
    resource_id = argv.pop(0)
    node = argv.pop(0) if argv else None

    lib.resource.unmove_unban(
        resource_id,
        node=node,
        master=modifiers.is_specified("--promoted"),
        expired=modifiers.is_specified("--expired"),
        wait=modifiers.get("--wait"),
    )


def resource_standards(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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


def resource_providers(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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


def resource_agents(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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


def update_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --agent-validation - use agent self validation of instance attributes
      * --wait
      * --force - allow invalid options, do not fail if not possible to get
        agent metadata, allow not suitable command
    """
    if not argv:
        raise CmdLineInputError()
    _check_is_not_stonith(lib, [argv[0]], "pcs stonith update")
    resource_update(argv, modifiers)


# Update a resource, removing any args that are empty and adding/updating
# args that are not empty
def resource_update(args: Argv, modifiers: InputModifiers) -> None:
    """
    Commandline options:
      * -f - CIB file
      * --agent-validation - use agent self validation of instance attributes
      * --wait
      * --force - allow invalid options, do not fail if not possible to get
        agent metadata, allow not suitable command
    """
    modifiers.ensure_only_supported(
        "-f", "--wait", "--force", "--agent-validation"
    )
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
                utils.cluster_upgrade_to_version(
                    const.PCMK_ON_FAIL_DEMOTE_CIB_VERSION
                )
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
                new_args = ["meta"] + ra_values + meta_values
                for op_args in op_values:
                    if op_args:
                        new_args += ["op"] + op_args
                return resource_update_clone(
                    dom, clone, child_id, new_args, wait, wait_timeout
                )
        utils.err("Unable to find resource: %s" % res_id)

    params = utils.convert_args_to_tuples(ra_values)

    try:
        agent_facade = _get_resource_agent_facade(
            _get_resource_agent_name_from_rsc_el(resource)
        )
        report_list = primitive.validate_resource_instance_attributes_update(
            utils.cmd_runner(),
            agent_facade,
            dict(params),
            res_id,
            get_resources(lib_pacemaker.get_cib(cib_xml)),
            force=bool(modifiers.get("--force")),
            enable_agent_self_validation=bool(
                modifiers.get("--agent-validation")
            ),
        )
        if report_list:
            process_library_reports(report_list)
    except lib_ra.ResourceAgentError as e:
        process_library_reports(
            [
                lib_ra.resource_agent_error_to_report_item(
                    e,
                    reports.get_severity(
                        reports.codes.FORCE, bool(modifiers.get("--force"))
                    ),
                )
            ]
        )

    utils.dom_update_instance_attr(resource, params)

    remote_node_name = utils.dom_get_resource_remote_node_name(resource)

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
    meta_options = KeyValueParser(meta_values).get_unique()
    if remote_node_name != guest_node.get_guest_option_value(meta_options):
        _detect_guest_change(
            meta_options,
            bool(modifiers.get("--force")),
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

    get_role = partial(
        pacemaker.role.get_value_for_cib,
        is_latest_supported=utils.isCibVersionSatisfied(
            dom, const.PCMK_NEW_ROLES_CIB_VERSION
        ),
    )
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
                op_role = get_role(v)
                break

        updating_op = None
        updating_op_before = None
        for existing_op in operations.getElementsByTagName("op"):
            if updating_op:
                updating_op_before = existing_op
                break
            existing_op_name = existing_op.getAttribute("name")
            existing_op_role = get_role(existing_op.getAttribute("role"))
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
            print_to_stderr(running_on["message"])
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
            print_to_stderr(running_on["message"])
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
        raise CmdLineInputError()

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
            OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
        ]
        for key, value in op_properties:
            if key not in valid_attrs:
                utils.err(
                    "%s is not a valid op option (use --force to override)"
                    % key
                )
            if key == "role":
                if value not in const.PCMK_ROLES:
                    utils.err(
                        "role must be: {} (use --force to override)".format(
                            format_list_custom_last_separator(
                                const.PCMK_ROLES, " or "
                            )
                        )
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
        if key == OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME:
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
        elif key == "role" and "--force" not in utils.pcs_options:
            op_el.setAttribute(
                key,
                pacemaker.role.get_value_for_cib(
                    val,
                    utils.isCibVersionSatisfied(
                        dom, const.PCMK_NEW_ROLES_CIB_VERSION
                    ),
                ),
            )
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
                    timeout_to_seconds_legacy(op_el.getAttribute("interval")),
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


def resource_operation_remove(res_id: str, argv: Argv) -> None:
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
        # return to let mypy know that resource_el is not None anymore
        return

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


def meta_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - allow not suitable command
      * --wait
      * -f - CIB file
    """
    if not argv:
        raise CmdLineInputError()
    _check_is_not_stonith(lib, [argv[0]], "pcs stonith meta")
    resource_meta(argv, modifiers)


def resource_meta(argv: Argv, modifiers: InputModifiers) -> None:
    """
    Commandline options:
      * --force - allow not suitable command
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "--wait", "-f")
    if len(argv) < 2:
        raise CmdLineInputError()
    res_id = argv.pop(0)
    _detect_guest_change(
        KeyValueParser(argv).get_unique(),
        bool(modifiers.get("--force")),
    )

    dom = utils.get_cib_dom()

    master = utils.dom_get_master(dom, res_id)
    if master:
        resource_el = transform_master_to_clone(master)
    else:
        resource_el = utils.dom_get_any_resource(dom, res_id)
    if resource_el is None:
        raise CmdLineInputError(
            f"unable to find a resource/clone/group: {res_id}"
        )

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    attr_tuples = utils.convert_args_to_tuples(argv)

    if resource_el.tagName == "clone":
        clone_child = utils.dom_elem_get_clone_ms_resource(resource_el)
        if clone_child:
            _check_clone_incompatible_options_child(
                clone_child,
                dict(attr_tuples),
                force=bool(modifiers.get("--force")),
            )

    remote_node_name = utils.dom_get_resource_remote_node_name(resource_el)
    utils.dom_update_meta_attr(resource_el, attr_tuples)

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
            print_to_stderr(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if retval != 0 and output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())


def resource_group_rm_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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


def resource_group_add_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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


def resource_clone(
    lib: Any, argv: Argv, modifiers: InputModifiers, promotable: bool = False
) -> None:
    """
    Options:
      * --wait
      * -f - CIB file
      * --force - allow to clone stonith resource
    """
    modifiers.ensure_only_supported("-f", "--force", "--wait")
    if not argv:
        raise CmdLineInputError()

    res = argv[0]
    _check_is_not_stonith(lib, [res])
    cib_dom = utils.get_cib_dom()

    if modifiers.is_specified("--wait"):
        wait_timeout = utils.validate_wait_get_timeout()

    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)

    cib_dom, clone_id = resource_clone_create(
        cib_dom, argv, promotable=promotable, force_flags=force_flags
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
            print_to_stderr(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())


def _resource_is_ocf(resource_el) -> bool:
    return resource_el.getAttribute("class") == "ocf"


def _get_resource_agent_name_from_rsc_el(
    resource_el,
) -> lib_ra.ResourceAgentName:
    return lib_ra.ResourceAgentName(
        resource_el.getAttribute("class"),
        resource_el.getAttribute("provider"),
        resource_el.getAttribute("type"),
    )


def _get_resource_agent_facade(
    resource_agent: lib_ra.ResourceAgentName,
) -> lib_ra.ResourceAgentFacade:
    return lib_ra.ResourceAgentFacadeFactory(
        utils.cmd_runner(), utils.get_report_processor()
    ).facade_from_parsed_name(resource_agent)


def resource_clone_create(
    cib_dom, argv, update_existing=False, promotable=False, force_flags=()
):
    """
    Commandline options:
      * --force - allow to clone stonith resource
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

    if element.getAttribute("class") == "stonith":
        process_library_reports(
            [
                reports.ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE,
                        is_forced=reports.codes.FORCE in force_flags,
                    ),
                    message=reports.messages.CloningStonithResourcesHasNoEffect(
                        [name]
                    ),
                )
            ]
        )

    parts = parse_clone(argv, promotable=promotable)
    _check_clone_incompatible_options_child(
        element, parts.meta_attrs, force=reports.codes.FORCE in force_flags
    )

    if not update_existing:
        clone_id = parts.clone_id
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

    utils.dom_update_meta_attr(clone, sorted(parts.meta_attrs.items()))

    return cib_dom, clone.getAttribute("id")


def _check_clone_incompatible_options_child(
    child_el,
    clone_meta_attrs: Mapping[str, str],
    force: bool = False,
):
    report_list = []
    if child_el.tagName == "primitive":
        report_list = _check_clone_incompatible_options_primitive(
            child_el, clone_meta_attrs, force=force
        )
    elif child_el.tagName == "group":
        group_id = child_el.getAttribute("id")
        for primitive_el in utils.get_group_children_el_from_el(child_el):
            report_list.extend(
                _check_clone_incompatible_options_primitive(
                    primitive_el,
                    clone_meta_attrs,
                    group_id=group_id,
                    force=force,
                )
            )
    if report_list:
        process_library_reports(report_list)


def _check_clone_incompatible_options_primitive(
    primitive_el,
    clone_meta_attrs: Mapping[str, str],
    group_id: Optional[str] = None,
    force: bool = False,
) -> reports.ReportItemList:
    resource_agent_name = _get_resource_agent_name_from_rsc_el(primitive_el)
    primitive_id = primitive_el.getAttribute("id")
    if not _resource_is_ocf(primitive_el):
        for incompatible_attribute in ("globally-unique", "promotable"):
            if is_true(clone_meta_attrs.get(incompatible_attribute, "0")):
                return [
                    reports.ReportItem.error(
                        reports.messages.ResourceCloneIncompatibleMetaAttributes(
                            incompatible_attribute,
                            resource_agent_name.to_dto(),
                            resource_id=primitive_id,
                            group_id=group_id,
                        )
                    )
                ]
    else:
        try:
            resource_agent_facade = _get_resource_agent_facade(
                resource_agent_name
            )
        except lib_ra.ResourceAgentError as e:
            return [
                lib_ra.resource_agent_error_to_report_item(
                    e, reports.get_severity(reports.codes.FORCE, force)
                )
            ]
        if resource_agent_facade.metadata.ocf_version == "1.1":
            if (
                is_true(clone_meta_attrs.get("promotable", "0"))
                and not resource_agent_facade.metadata.provides_promotability
            ):
                return [
                    reports.ReportItem(
                        reports.get_severity(reports.codes.FORCE, force),
                        reports.messages.ResourceCloneIncompatibleMetaAttributes(
                            "promotable",
                            resource_agent_name.to_dto(),
                            resource_id=primitive_id,
                            group_id=group_id,
                        ),
                    )
                ]
    return []


def resource_clone_master_remove(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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
            print_to_stderr(running_on["message"])
        else:
            msg = []
            if retval == PACEMAKER_WAIT_TIMEOUT_STATUS:
                msg.append("waiting timeout")
            msg.append(running_on["message"])
            if output:
                msg.append("\n" + output)
            utils.err("\n".join(msg).strip())


def resource_remove_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) != 1:
        raise CmdLineInputError()
    resource_id = argv[0]
    _check_is_not_stonith(lib, [resource_id], "pcs stonith delete")
    resource_remove(resource_id)


# TODO move to lib (complete rewrite)
def resource_remove(resource_id, output=True, is_remove_remote_context=False):
    """
    Removes a resource from cluster configuration

    Commandline options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
      * --wait - is supported by resource_disable but waiting for resource to
        stop is handled also in this function

    This function contains at least three bugs:
    1) Input parameter 'output' gets overwritten with output of utilities which
    can cause loose equality checks to suppress output of this function
    2) Callers don't check the return value of this function and in conjunction
    with the previous bug, the command can complete successfully even though the
    resource was not removed
    3) Parameter 'output' is not always correctly propagated to functions that
    support it

    str resource_id -- id of resource to be removed
    bool output -- suppresses output of this and subsequent commands (buggy)
    bool is_remove_remote_context -- is this running on a remote node
    """

    def is_bundle_running(bundle_id):
        roles_with_nodes = get_resource_state(
            lib_pacemaker.get_cluster_status_dom(utils.cmd_runner()),
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
                ".//tag/obj_ref[@id=$id]",
                id=el.get("id", ""),
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
            print_to_stderr("Deleting bundle '{0}'".format(resource_id))
        else:
            print_to_stderr(
                "Deleting bundle '{0}' and its inner resource '{1}'".format(
                    resource_id, primitive_el.getAttribute("id")
                )
            )

        if (
            "--force" not in utils.pcs_options
            and not utils.usefile
            and is_bundle_running(resource_id)
        ):
            print_to_stderr(
                "Stopping bundle '{0}'... ".format(resource_id), end=""
            )
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
            print_to_stderr("Stopped")

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
        print_to_stderr(
            f"Removing group: {resource_id} (and all resources within group)"
        )
        group = utils.get_cib_xpath('//group[@id="' + resource_id + '"]')
        group_dom = parseString(group)
        print_to_stderr(f"Stopping all resources in group: {resource_id}...")
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
        print_to_stderr("Attempting to stop: " + resource_id + "... ", end="")
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
        print_to_stderr("Stopped")

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
            print_to_stderr("Deleting Resource - " + resource_id)
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
            print_to_stderr("Deleting Resource (" + msg + ") - " + resource_id)
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


def resource_group_list(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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


def resource_show(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool = False
) -> None:
    # TODO remove, deprecated command
    # replaced with 'resource status' and 'resource config'
    """
    Options:
      * -f - CIB file
      * --full - print all configured options
      * --groups - print resource groups
      * --hide-inactive - print only active resources
    """
    del lib
    modifiers.ensure_only_supported(
        "-f", "--full", "--groups", "--hide-inactive"
    )
    if modifiers.get("--groups"):
        raise_command_replaced(["pcs resource group list"], pcs_version="0.11")

    keyword = "stonith" if stonith else "resource"
    if modifiers.get("--full") or argv:
        raise_command_replaced([f"pcs {keyword} config"], pcs_version="0.11")

    raise_command_replaced([f"pcs {keyword} status"], pcs_version="0.11")


def resource_status(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool = False
) -> None:
    """
    Options:
      * -f - CIB file
      * --hide-inactive - print only active resources
    """
    del lib
    modifiers.ensure_only_supported("-f", "--hide-inactive")
    if len(argv) > 2:
        raise CmdLineInputError()

    monitor_command = ["crm_mon", "--one-shot"]
    if not modifiers.get("--hide-inactive"):
        monitor_command.append("--inactive")

    resource_or_tag_id = None
    node = None
    crm_mon_err_msg = "unable to get cluster status from crm_mon\n"
    if argv:
        for arg in argv[:]:
            if "=" not in arg:
                resource_or_tag_id = arg
                crm_mon_err_msg = (
                    f"unable to get status of '{resource_or_tag_id}' from crm_"
                    "mon\n"
                )
                monitor_command.extend(
                    [
                        "--include",
                        "none,resources",
                        "--resource",
                        resource_or_tag_id,
                    ]
                )
                argv.remove(arg)
                break
        parser = KeyValueParser(argv)
        parser.check_allowed_keys({"node"})
        node = parser.get_unique().get("node")
        if node == "":
            utils.err("missing value of 'node' option")
        if node:
            monitor_command.extend(["--node", node])

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
    no_active_resources_msg = "No active resources"
    for line in output.split("\n"):
        if line in (
            "  * No active resources",  # pacemaker >= 2.0.3 with --hide-inactive
            "No active resources",  # pacemaker < 2.0.3 with --hide-inactive
        ):
            print(no_active_resources_msg)
            return
        if line in (
            "  * No resources",  # pacemaker >= 2.0.3
            "No resources",  # pacemaker < 2.0.3
        ):
            if resource_or_tag_id and not node:
                utils.err(
                    f"resource or tag id '{resource_or_tag_id}' not found"
                )
            if not node:
                print(no_resources_line)
            else:
                print(no_active_resources_msg)
            return
        if line in (
            "Full List of Resources:",  # pacemaker >= 2.0.3
            "Active Resources:",  # pacemaker >= 2.0.3 with  --hide-inactive
        ):
            in_resources = True
            continue
        if line in (
            "Full list of resources:",  # pacemaker < 2.0.3
            "Active resources:",  # pacemaker < 2.0.3 with --hide-inactive
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


def resource_disable_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --brief - show brief output of --simulate
      * --safe - only disable if no other resource gets stopped or demoted
      * --simulate - do not push the CIB, print its effects
      * --no-strict - allow disable if other resource is affected
      * --wait
    """
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to disable")
    _check_is_not_stonith(lib, argv, "pcs stonith disable")
    resource_disable_common(lib, argv, modifiers)


def resource_disable_common(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Commandline options:
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
    modifiers.ensure_not_incompatible("--safe", {"-f", "--simulate"})
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
        if modifiers.get("--brief"):
            # Brief mode skips simulation output by setting the report processor
            # to ignore info reports which contain crm_simulate output and
            # resource status in this command
            lib.env.report_processor.suppress_reports_of_severity(
                [reports.ReportItemSeverity.INFO]
            )
        lib.resource.disable_safe(
            argv,
            not modifiers.get("--no-strict"),
            modifiers.get("--wait"),
        )
        return
    if modifiers.get("--brief"):
        raise CmdLineInputError(
            "'--brief' cannot be used without '--simulate' or '--safe'"
        )
    lib.resource.disable(argv, modifiers.get("--wait"))


def resource_safe_disable_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
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


def resource_enable_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to enable")
    resources = argv
    _check_is_not_stonith(lib, resources, "pcs stonith enable")
    lib.resource.enable(resources, modifiers.get("--wait"))


# DEPRECATED, moved to pcs.lib.commands.resource
def resource_disable(argv: Argv) -> Optional[bool]:
    """
    Commandline options:
      * -f - CIB file
      * --wait
    """
    if not argv:
        utils.err("You must specify a resource to disable")

    resource = argv[0]
    if not is_managed(resource):
        warn(f"'{resource}' is unmanaged")

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
            print_to_stderr(running_on["message"])
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


def resource_restart(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --wait
    """
    modifiers.ensure_only_supported("--wait")
    if not argv:
        utils.err("You must specify a resource to restart")
    _check_is_not_stonith(lib, [argv[0]])

    dom = utils.get_cib_dom()
    node = None
    resource = argv.pop(0)

    real_res = utils.dom_get_resource_clone_ms_parent(
        dom, resource
    ) or utils.dom_get_resource_bundle_parent(dom, resource)
    if real_res:
        warn(
            (
                "using {resource_id}... (if a resource is a clone or bundle "
                "you must use the clone or bundle name)"
            ).format(resource_id=real_res.getAttribute("id"))
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
        wait = modifiers.get("--wait")
        if wait:
            args.extend(["--timeout", str(wait)])
        else:
            utils.err("You must specify the number of seconds to wait")

    output, retval = utils.run(args)
    if retval != 0:
        utils.err(output)

    print_to_stderr(f"{resource} successfully restarted")


def resource_force_action(
    lib: Any, argv: Argv, modifiers: InputModifiers, action: str
) -> None:
    """
    Options:
      * --force
      * --full - more verbose output
    """
    modifiers.ensure_only_supported("--force", "--full")
    action_command = {
        "debug-start": "--force-start",
        "debug-stop": "--force-stop",
        "debug-promote": "--force-promote",
        "debug-demote": "--force-demote",
        "debug-monitor": "--force-check",
    }

    if action not in action_command:
        raise CmdLineInputError()
    if not argv:
        utils.err("You must specify a resource to {0}".format(action))
    if len(argv) != 1:
        raise CmdLineInputError()

    resource = argv[0]
    _check_is_not_stonith(lib, [resource])
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


def resource_manage_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --monitor - enable monitor operation of specified resources
    """
    modifiers.ensure_only_supported("-f", "--monitor")
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to manage")
    resources = argv
    _check_is_not_stonith(lib, resources)
    lib.resource.manage(resources, with_monitor=modifiers.get("--monitor"))


def resource_unmanage_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --monitor - bisable monitor operation of specified resources
    """
    modifiers.ensure_only_supported("-f", "--monitor")
    if not argv:
        raise CmdLineInputError("You must specify resource(s) to unmanage")
    resources = argv
    _check_is_not_stonith(lib, resources)
    lib.resource.unmanage(resources, with_monitor=modifiers.get("--monitor"))


# moved to pcs.lib.pacemaker.state
def is_managed(resource_id: str) -> bool:
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


def resource_failcount_show(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --full
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--full")

    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parser = KeyValueParser(argv)
    parser.check_allowed_keys({"node", "operation", "interval"})
    parsed_options = parser.get_unique()

    node = parsed_options.get("node")
    operation = parsed_options.get("operation")
    interval = parsed_options.get("interval")
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
        print("\n".join(result_lines))
        return

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
            if modifiers.get("--full"):
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
                        failcount, dummy_last_failure = __aggregate_failures(
                            interval_failures
                        )
                        result_lines.append(
                            f"    {current_operation} {current_interval}ms: "
                            f"{failcount}"
                        )
            else:
                failcount, dummy_last_failure = __aggregate_failures(
                    node_failures
                )
                result_lines.append(f"  {current_node}: {failcount}")
    print("\n".join(result_lines))


def __aggregate_failures(failure_list):
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


def resource_cleanup(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported("--strict")
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parser = KeyValueParser(argv)
    parser.check_allowed_keys({"node", "operation", "interval"})
    parsed_options = parser.get_unique()

    print_to_stderr(
        lib_pacemaker.resource_cleanup(
            utils.cmd_runner(),
            resource=resource,
            node=parsed_options.get("node"),
            operation=parsed_options.get("operation"),
            interval=parsed_options.get("interval"),
            strict=bool(modifiers.get("--strict")),
        )
    )


def resource_refresh(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - do refresh even though it may be time consuming
    """
    del lib
    modifiers.ensure_only_supported(
        "--force",
        "--strict",
        # The hint is defined to print error messages which point users to the
        # changes section in pcs manpage.
        # To be removed in the next significant version.
        hint_syntax_changed=modifiers.is_specified("--full"),
    )
    resource = argv.pop(0) if argv and "=" not in argv[0] else None
    parser = KeyValueParser(argv)
    parser.check_allowed_keys({"node"})
    parsed_options = parser.get_unique()
    print_to_stderr(
        lib_pacemaker.resource_refresh(
            utils.cmd_runner(),
            resource=resource,
            node=parsed_options.get("node"),
            strict=bool(modifiers.get("--strict")),
            force=bool(modifiers.get("--force")),
        )
    )


def resource_relocate_show_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    resource_relocate_show(utils.get_cib_dom())


def resource_relocate_dry_run_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        _check_is_not_stonith(lib, argv)
    resource_relocate_run(utils.get_cib_dom(), argv, dry=True)


def resource_relocate_run_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        _check_is_not_stonith(lib, argv)
    resource_relocate_run(utils.get_cib_dom(), argv, dry=False)


def resource_relocate_clear_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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
            role=f" role={const.PCMK_ROLE_PROMOTED_PRIMARY}",
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
        print_to_stderr(resource_relocate_location_to_str(location))
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
            new_constraint.setAttribute(
                "role",
                pacemaker.role.get_value_for_cib(
                    const.PCMK_ROLE_PROMOTED_PRIMARY,
                    utils.isCibVersionSatisfied(
                        cib_dom, const.PCMK_NEW_ROLES_CIB_VERSION
                    ),
                ),
            )
        elif "start_on_node" in location:
            new_constraint.setAttribute("node", location["start_on_node"])
        constraint_el.appendChild(new_constraint)
    if not anything_changed:
        return
    if not dry:
        utils.replace_cib_configuration(cib_dom)

    # wait for resources to move
    print_to_stderr("\nWaiting for resources to move...\n")
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
                print_to_stderr("Removing constraint {0}".format(location_id))
                location_el.parentNode.removeChild(location_el)
    return cib_dom


def set_resource_utilization(resource_id: str, argv: Argv) -> None:
    """
    Commandline options:
      * -f - CIB file
    """
    cib = utils.get_cib_dom()
    resource_el = utils.dom_get_resource(cib, resource_id)
    if resource_el is None:
        utils.err("Unable to find a resource: {0}".format(resource_id))
    utils.dom_update_utilization(resource_el, KeyValueParser(argv).get_unique())
    utils.replace_cib_configuration(cib)


def print_resource_utilization(resource_id: str) -> None:
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


def print_resources_utilization() -> None:
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


# deprecated
# This is used only by pcsd, will be removed in new architecture
def get_resource_agent_info(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        utils.err("One parameter expected")
    print(json.dumps(lib.resource_agent.describe_agent(argv[0])))


def resource_bundle_create_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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
        parts.container_type,
        container_options=parts.container,
        network_options=parts.network,
        port_map=parts.port_map,
        storage_map=parts.storage_map,
        meta_attributes=parts.meta_attrs,
        force_options=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        wait=modifiers.get("--wait"),
    )


def resource_bundle_reset_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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
        container_options=parts.container,
        network_options=parts.network,
        port_map=parts.port_map,
        storage_map=parts.storage_map,
        meta_attributes=parts.meta_attrs,
        force_options=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        wait=modifiers.get("--wait"),
    )


def resource_bundle_update_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
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
        container_options=parts.container,
        network_options=parts.network,
        port_map_add=parts.port_map_add,
        port_map_remove=parts.port_map_remove,
        storage_map_add=parts.storage_map_add,
        storage_map_remove=parts.storage_map_remove,
        meta_attributes=parts.meta_attrs,
        force_options=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    config_common(lib, argv, modifiers, stonith=False)


def config_common(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool
) -> None:
    """
    Options:
      * -f - CIB file
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported("-f", output_format_supported=True)
    resources_facade = (
        ResourcesConfigurationFacade.from_resources_dto(
            lib.resource.get_configured_resources()
        )
        .filter_stonith(stonith)
        .filter_resources(argv)
    )
    output_format = modifiers.get_output_format()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = ";\n".join(
            " \\\n".join(cmd) for cmd in resources_to_cmd(resources_facade)
        )
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(
            dto.to_dict(
                CibResourcesDto(
                    primitives=resources_facade.primitives,
                    clones=resources_facade.clones,
                    groups=resources_facade.groups,
                    bundles=resources_facade.bundles,
                )
            )
        )
    else:
        output = "\n".join(smart_wrap_text(resources_to_text(resources_facade)))
    if output:
        print(output)
