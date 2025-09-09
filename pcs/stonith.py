import json
from typing import (
    Any,
    Optional,
)

from pcs import (
    resource,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
    ensure_unique_args,
)
from pcs.cli.fencing_topology import target_type_map_cli_to_lib
from pcs.cli.reports.output import (
    print_to_stderr,
)
from pcs.cli.resource.output import resource_agent_metadata_to_text
from pcs.cli.resource.parse_args import (
    parse_primitive as parse_primitive_resource,
)
from pcs.cli.stonith.common import check_is_stonith
from pcs.cli.stonith.levels.output import stonith_level_config_to_text
from pcs.common import reports
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE
from pcs.common.pacemaker.resource.list import (
    get_all_resources_ids,
    get_stonith_resources_ids,
)
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.common.str_tools import (
    format_list,
    format_plural,
    indent,
)


def stonith_status_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    resource.resource_status(lib, argv[:], modifiers, stonith=True)
    if not argv:
        _print_stonith_levels(lib)


def _print_stonith_levels(lib: Any) -> None:
    lines = stonith_level_config_to_text(lib.fencing_topology.get_config_dto())
    if lines:
        print("\nFencing Levels:")
        print("\n".join(indent(lines)))


def stonith_list_available(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --nodesc - do not show description of the agents
    """
    modifiers.ensure_only_supported("--nodesc")
    if len(argv) > 1:
        raise CmdLineInputError()

    search = argv[0] if argv else None
    agent_list = lib.stonith_agent.list_agents(
        describe=not modifiers.get("--nodesc"),
        search=search,
    )

    if not agent_list:
        if search:
            utils.err("No stonith agents matching the filter.")
        utils.err(
            "No stonith agents available. Do you have fence agents installed?"
        )

    for agent_info in agent_list:
        name = agent_info["type"]
        shortdesc = agent_info["shortdesc"]
        if shortdesc:
            print(
                "{0} - {1}".format(
                    name,
                    # pylint: disable=protected-access
                    resource._format_desc(  # noqa: SLF001
                        len(name + " - "), shortdesc.replace("\n", " ")
                    ),
                )
            )
        else:
            print(name)


def stonith_list_options(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --full - show advanced options
    """
    modifiers.ensure_only_supported("--full")
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = ResourceAgentNameDto("stonith", None, argv[0])
    print(
        "\n".join(
            resource_agent_metadata_to_text(
                lib.resource_agent.get_agent_metadata(agent_name),
                lib.resource_agent.get_agent_default_operations(
                    agent_name
                ).operations,
                verbose=modifiers.is_specified("--full"),
            )
        )
    )


def stonith_create(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - allow not existing agent, invalid operations or invalid
        instance attributes
      * --disabled - created resource will be disabled
      * --no-default-ops - do not add default operations
      * --agent-validation - use agent self validation of instance attributes
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported(
        "--force",
        "--disabled",
        "--no-default-ops",
        "--agent-validation",
        "--wait",
        "-f",
        hint_syntax_changed="0.12",
    )

    if len(argv) < 2:
        raise CmdLineInputError()

    stonith_id = argv[0]
    stonith_type = argv[1]

    parts = parse_primitive_resource(argv[2:])

    settings = dict(
        allow_absent_agent=modifiers.get("--force"),
        allow_invalid_operation=modifiers.get("--force"),
        allow_invalid_instance_attributes=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        use_default_operations=not modifiers.get("--no-default-ops"),
        wait=modifiers.get("--wait"),
        enable_agent_self_validation=modifiers.get("--agent-validation"),
    )

    lib.stonith.create(
        stonith_id,
        stonith_type,
        parts.operations,
        parts.meta_attrs,
        parts.instance_attrs,
        **settings,
    )


def _stonith_level_parse_node(arg):
    """
    Commandline options: no options
    """
    target_type_candidate, target_value_candidate = parse_args.parse_typed_arg(
        arg, target_type_map_cli_to_lib.keys(), "node"
    )
    target_type = target_type_map_cli_to_lib[target_type_candidate]
    if target_type == TARGET_TYPE_ATTRIBUTE:
        target_value = parse_args.split_option(target_value_candidate)
    else:
        target_value = target_value_candidate
    return target_type, target_value


def _stonith_level_parse_target_and_stonith(argv: Argv):
    target_type, target_value, devices = None, None, None
    allowed_keywords = {"target", "stonith"}
    missing_target_value, missing_stonith_value = False, False
    groups = parse_args.group_by_keywords(argv, allowed_keywords)
    if groups.has_keyword("target"):
        if len(groups.get_args_flat("target")) > 1:
            raise CmdLineInputError("At most one target can be specified")
        if groups.get_args_flat("target"):
            target_type, target_value = _stonith_level_parse_node(
                groups.get_args_flat("target")[0]
            )
        else:
            missing_target_value = True
    if groups.has_keyword("stonith"):
        if groups.get_args_flat("stonith"):
            devices = groups.get_args_flat("stonith")
        else:
            missing_stonith_value = True

    if missing_target_value and missing_stonith_value:
        raise CmdLineInputError("Missing value after 'target' and 'stonith'")
    if missing_target_value:
        raise CmdLineInputError("Missing value after 'target'")
    if missing_stonith_value:
        raise CmdLineInputError("Missing value after 'stonith'")

    return target_type, target_value, devices


def stonith_level_add_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow not existing stonith device, allow not existing node
        (target)
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()

    level = argv[0]

    # KeyValueParser supports only key value arguments, so we will only filter
    # out those by looking for "=" to also include mistyped or missing keys
    kvpairs = [arg for arg in argv[2:] if "=" in arg]
    for kvpair in kvpairs:
        argv.remove(kvpair)
    parser = KeyValueParser(kvpairs)
    parser.check_allowed_keys(["id"])
    level_id = parser.get_unique().get("id")
    target_type, target_value = _stonith_level_parse_node(argv[1])
    stonith_devices = argv[2:]
    check_is_stonith(lib, stonith_devices)

    lib.fencing_topology.add_level(
        level,
        target_type,
        target_value,
        stonith_devices,
        level_id=level_id,
        force_device=modifiers.get("--force"),
        force_node=modifiers.get("--force"),
    )


def stonith_level_clear_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")

    if not argv:
        lib.fencing_topology.remove_all_levels()
        return

    (target_type, target_value, devices) = (
        _stonith_level_parse_target_and_stonith(argv)
    )
    if devices is not None and target_value is not None:
        raise CmdLineInputError(
            "Only one of 'target' and 'stonith' can be used"
        )
    lib.fencing_topology.remove_levels_by_params(
        None,
        target_type,
        target_value,
        devices,
    )


def stonith_level_remove_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv or len(argv) < 1:
        raise CmdLineInputError()

    level = argv[0]
    target_type, target_value, devices = (
        _stonith_level_parse_target_and_stonith(argv[1:])
    )

    lib.fencing_topology.remove_levels_by_params(
        level,
        target_type,
        target_value,
        devices,
    )


def stonith_level_verify_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    # raises LibraryError in case of problems, else we don't want to do anything
    lib.fencing_topology.verify()


def stonith_fence(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --off - use off action of fence agent
    """
    del lib
    modifiers.ensure_only_supported("--off")
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to fence")

    node = argv.pop(0)
    if modifiers.get("--off"):
        args = ["stonith_admin", "-F", node]
    else:
        args = ["stonith_admin", "-B", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to fence '%s'\n" % node + output)
    else:
        print_to_stderr(f"Node: {node} fenced")


def stonith_confirm(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - required for confirming that fencing happened - DEPRECATED
      * --yes - required for confirming that fencing happened
    """
    del lib
    modifiers.ensure_only_supported("--force", "--yes")
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to confirm fenced")

    node = argv.pop(0)
    if not utils.get_continue_confirmation(
        f"If node '{node}' is not powered off or it does have access to shared "
        "resources, data corruption and/or cluster failure may occur",
        bool(modifiers.get("--yes")),
        bool(modifiers.get("--force")),
    ):
        return
    args = ["stonith_admin", "-C", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to confirm fencing of node '%s'\n" % node + output)
    else:
        print("Node: %s confirmed fenced" % node)


# This is used only by pcsd, will be removed in new architecture
def get_fence_agent_info(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        utils.err("One parameter expected")

    agent_name = argv[0]
    if not agent_name.startswith("stonith:"):
        utils.err("Invalid fence agent name")
    print(
        json.dumps(
            lib.stonith_agent.describe_agent(agent_name[len("stonith:") :])
        )
    )


def sbd_watchdog_list(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    available_watchdogs = lib.sbd.get_local_available_watchdogs()

    if available_watchdogs:
        key_label = {
            "identity": "Identity",
            "driver": "Driver",
        }
        lines = []
        for watchdog in sorted(available_watchdogs.keys()):
            lines += [watchdog]
            for key, label in key_label.items():
                value = available_watchdogs[watchdog].get(key)
                if value:
                    lines += indent([f"{label}: {value}"])
        print("Available watchdog(s):\n" + "\n".join(indent(lines)))
    else:
        print_to_stderr("No available watchdog")


def sbd_watchdog_list_json(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(json.dumps(lib.sbd.get_local_available_watchdogs()))


def sbd_watchdog_test(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - required for testing the watchdog - DEPRECATED
      * --yes - required for testing the watchdog
    """
    modifiers.ensure_only_supported("--force", "--yes")
    if len(argv) > 1:
        raise CmdLineInputError()
    if not utils.get_continue_confirmation(
        "This operation is expected to force-reboot this system without "
        "following any shutdown procedures",
        bool(modifiers.get("--yes")),
        bool(modifiers.get("--force")),
    ):
        return
    watchdog = None
    if len(argv) == 1:
        watchdog = argv[0]
    lib.sbd.test_local_watchdog(watchdog)


def sbd_enable(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --force - allow unknown SBD options
      * --skip-offline - skip offline cluster nodes
      * --no-watchdog-validation - do not validate watchdog
    """
    modifiers.ensure_only_supported(
        "--request-timeout",
        "--force",
        "--skip-offline",
        "--no-watchdog-validation",
    )
    parser = KeyValueParser(argv, repeatable=("device", "watchdog"))
    repeatable_options = parser.get_repeatable()
    default_watchdog, watchdog_dict = _sbd_parse_watchdogs(
        repeatable_options.get("watchdog", [])
    )
    default_device_list, node_device_dict = _sbd_parse_node_specific_options(
        repeatable_options.get("device", [])
    )

    lib.sbd.enable_sbd(
        default_watchdog,
        watchdog_dict,
        parser.get_unique(),
        default_device_list=(
            default_device_list if default_device_list else None
        ),
        node_device_dict=node_device_dict if node_device_dict else None,
        allow_unknown_opts=modifiers.get("--force"),
        ignore_offline_nodes=modifiers.get("--skip-offline"),
        no_watchdog_validation=modifiers.get("--no-watchdog-validation"),
    )


def _sbd_parse_node_specific_options(
    arg_list: Argv,
) -> tuple[list[str], dict[str, list[str]]]:
    """
    Commandline options: no options
    """
    default_option_list = []
    node_specific_option_dict: dict[str, list[str]] = {}

    for arg in arg_list:
        if "@" in arg:
            option, node_name = arg.rsplit("@", 1)
            if node_name in node_specific_option_dict:
                node_specific_option_dict[node_name].append(option)
            else:
                node_specific_option_dict[node_name] = [option]
        else:
            default_option_list.append(arg)

    return default_option_list, node_specific_option_dict


def _sbd_parse_watchdogs(
    watchdog_list: list[str],
) -> tuple[Optional[str], dict[str, str]]:
    """
    Commandline options: no options
    """
    (
        default_watchdog_list,
        node_specific_watchdog_dict,
    ) = _sbd_parse_node_specific_options(watchdog_list)
    if not default_watchdog_list:
        default_watchdog = None
    elif len(default_watchdog_list) == 1:
        default_watchdog = default_watchdog_list[0]
    else:
        raise CmdLineInputError("Multiple watchdog definitions.")

    watchdog_dict = {}
    for node, node_watchdog_list in node_specific_watchdog_dict.items():
        if len(node_watchdog_list) > 1:
            raise CmdLineInputError(
                f"Multiple watchdog definitions for node '{node}'"
            )
        watchdog_dict[node] = node_watchdog_list[0]

    return default_watchdog, watchdog_dict


def sbd_disable(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --skip-offline - skip offline cluster nodes
      * --force - override validation errors
    """
    modifiers.ensure_only_supported(
        "--request-timeout", "--skip-offline", "--force"
    )
    if argv:
        raise CmdLineInputError()

    force_flags = set()
    if modifiers.is_specified("--force"):
        force_flags.add(reports.codes.FORCE)
    if modifiers.is_specified("--skip-offline"):
        force_flags.add(reports.codes.SKIP_OFFLINE_NODES)

    lib.sbd.disable_sbd(modifiers.get("--skip-offline"), force_flags)


def sbd_status(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --full - display SBD device header
    """
    modifiers.ensure_only_supported("--request-timeout", "--full")

    def _bool_to_str(val: Optional[bool]) -> str:
        if val is None:
            return "N/A"
        return "YES" if val else " NO"

    if argv:
        raise CmdLineInputError()

    status_list = lib.sbd.get_cluster_sbd_status()
    if not status_list:
        utils.err("Unable to get SBD status from any node.")

    print("SBD STATUS")
    print("<node name>: <installed> | <enabled> | <running>")
    for node_status in status_list:
        status = node_status["status"]
        print(
            "{node}: {installed} | {enabled} | {running}".format(
                node=node_status["node"],
                installed=_bool_to_str(status.get("installed")),
                enabled=_bool_to_str(status.get("enabled")),
                running=_bool_to_str(status.get("running")),
            )
        )
    device_list = lib.sbd.get_local_devices_info(modifiers.get("--full"))
    for device in device_list:
        print()
        print(f"Messages list on device '{device['device']}':")
        print("<unknown>" if device["list"] is None else device["list"])
        if modifiers.get("--full"):
            print()
            print(f"SBD header on device '{device['device']}':")
            print("<unknown>" if device["dump"] is None else device["dump"])


def _print_per_node_option(config_list, config_option):
    """
    Commandline options: no options
    """
    unknown_value = "<unknown>"
    for config in config_list:
        value = unknown_value
        if config["config"] is not None:
            value = config["config"].get(config_option, unknown_value)
        print(f"  {config['node']}: {value}")


def sbd_config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported("--request-timeout")
    if argv:
        raise CmdLineInputError()

    config_list = lib.sbd.get_cluster_sbd_config()

    if not config_list:
        utils.err("No config obtained.")

    config = config_list[0]["config"]

    filtered_options = [
        "SBD_WATCHDOG_DEV",
        "SBD_OPTS",
        "SBD_PACEMAKER",
        "SBD_DEVICE",
    ]
    with_device = False
    for key, val in config.items():
        if key == "SBD_DEVICE":
            with_device = True
        if key in filtered_options:
            continue
        print(f"{key}={val}")

    print()
    print("Watchdogs:")
    _print_per_node_option(config_list, "SBD_WATCHDOG_DEV")

    if with_device:
        print()
        print("Devices:")
        _print_per_node_option(config_list, "SBD_DEVICE")


def local_sbd_config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(json.dumps(lib.sbd.get_local_sbd_config()))


def sbd_setup_block_device(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - required for wiping specified storage devices - DEPRECATED
      * --yes - required for wiping specified storage devices
    """
    modifiers.ensure_only_supported("--force", "--yes")
    parser = KeyValueParser(argv, repeatable=("device",))
    repeatable_options = parser.get_repeatable()
    device_list = repeatable_options.get("device", [])
    if not device_list:
        raise CmdLineInputError("No device defined")

    if not utils.get_continue_confirmation(
        f"All current content on device(s) {format_list(device_list)} will be "
        "overwritten",
        bool(modifiers.get("--yes")),
        bool(modifiers.get("--force")),
    ):
        return

    lib.sbd.initialize_block_devices(device_list, parser.get_unique())


def sbd_message(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 3:
        raise CmdLineInputError()

    device, node, message = argv
    lib.sbd.set_message(device, node, message)


def stonith_history_show_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) > 1:
        raise CmdLineInputError()

    node = argv[0] if argv else None
    print(lib.stonith.history_get_text(node))


def stonith_history_cleanup_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) > 1:
        raise CmdLineInputError()

    node = argv[0] if argv else None
    print_to_stderr(lib.stonith.history_cleanup(node))


def stonith_history_update_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    print_to_stderr(lib.stonith.history_update())


def stonith_update_scsi_devices(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --request-timeout - timeout for HTTP requests
      * --skip-offline - skip unreachable nodes
    """
    modifiers.ensure_only_supported("--request-timeout", "--skip-offline")
    force_flags = []
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    if len(argv) < 2:
        raise CmdLineInputError()
    stonith_id = argv[0]
    parsed_args = parse_args.group_by_keywords(
        argv[1:], ["set", "add", "remove", "delete"]
    )
    parsed_args.ensure_unique_keywords()
    cmd_exception = CmdLineInputError(
        show_both_usage_and_message=True,
        hint=(
            "You must specify either list of set devices or at least one device"
            " for add or delete/remove devices"
        ),
    )
    if parsed_args.has_keyword("set") and (
        parsed_args.has_keyword("add")
        or parsed_args.has_keyword("remove")
        or parsed_args.has_keyword("delete")
    ):
        raise cmd_exception
    if parsed_args.has_keyword("set"):
        if not parsed_args.get_args_flat("set"):
            raise cmd_exception
        lib.stonith.update_scsi_devices(
            stonith_id,
            parsed_args.get_args_flat("set"),
            force_flags=force_flags,
        )
    else:
        for key in ("add", "remove", "delete"):
            if parsed_args.has_empty_keyword(key):
                raise cmd_exception
        lib.stonith.update_scsi_devices_add_remove(
            stonith_id,
            parsed_args.get_args_flat("add"),
            (
                parsed_args.get_args_flat("delete")
                + parsed_args.get_args_flat("remove")
            ),
            force_flags=force_flags,
        )


def delete_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - don't stop a resource before its deletion
    """
    modifiers.ensure_only_supported("-f", "--force")
    if not argv:
        raise CmdLineInputError()
    ensure_unique_args(argv)

    resources_to_remove = set(argv)
    resources_dto = lib.resource.get_configured_resources()
    missing_ids = resources_to_remove - get_all_resources_ids(resources_dto)
    if missing_ids:
        raise CmdLineInputError(
            "Unable to find stonith {resource}: {id_list}".format(
                resource=format_plural(missing_ids, "resource"),
                id_list=format_list(missing_ids),
            )
        )

    non_stonith_ids = resources_to_remove - get_stonith_resources_ids(
        resources_dto
    )
    if non_stonith_ids:
        raise CmdLineInputError(
            (
                "This command cannot remove {resource}: {id_list}. Use 'pcs "
                "resource remove' instead."
            ).format(
                resource=format_plural(non_stonith_ids, "resource"),
                id_list=format_list(non_stonith_ids),
            )
        )

    force_flags = set()
    if modifiers.is_specified("--force"):
        force_flags.add(reports.codes.FORCE)

    lib.cib.remove_elements(resources_to_remove, force_flags)


def enable_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--wait", "-f")
    if not argv:
        raise CmdLineInputError(
            "You must specify stonith resource(s) to enable"
        )
    resources = argv
    check_is_stonith(lib, resources, "pcs resource enable")
    lib.resource.enable(resources, modifiers.get("--wait"))


def disable_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force
      * --wait
    """
    if not argv:
        raise CmdLineInputError(
            "You must specify stonith resource(s) to disable"
        )
    check_is_stonith(lib, argv, "pcs resource disable")
    modifiers.ensure_only_supported(
        "-f", "--force", "--wait", hint_syntax_changed="0.12"
    )
    resource.resource_disable_common(lib, argv, modifiers)


def update_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --wait
      * --force - allow invalid options, do not fail if not possible to get
        agent metadata, allow not suitable command
    """
    if not argv:
        raise CmdLineInputError()
    check_is_stonith(lib, [argv[0]], "pcs resource update")
    resource.resource_update(argv, modifiers)


def op_add_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --force - allow unknown options
    """
    if not argv:
        raise CmdLineInputError()
    check_is_stonith(lib, [argv[0]], "pcs resource op add")
    resource.resource_op_add(argv, modifiers)


def op_delete_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    check_is_stonith(lib, [argv[0]], "pcs resource op delete")
    resource.resource_operation_remove(argv[0], argv[1:])
