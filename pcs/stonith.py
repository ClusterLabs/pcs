import json

from pcs import (
    resource,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.fencing_topology import target_type_map_cli_to_lib
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import error
from pcs.cli.resource.parse_args import parse_create_simple as parse_create_args
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.common.str_tools import indent
from pcs.lib.errors import LibraryError
import pcs.lib.resource_agent as lib_ra

# pylint: disable=too-many-branches, too-many-statements, protected-access


def stonith_show_cmd(lib, argv, modifiers):
    # TODO remove, deprecated command
    # replaced with 'stonith status' and 'stonith config'
    resource.resource_show(lib, argv, modifiers, stonith=True)
    print_stonith_levels(lib)


def stonith_status_cmd(lib, argv, modifiers):
    resource.resource_status(lib, argv, modifiers, stonith=True)
    print_stonith_levels(lib)


def stonith_config_cmd(lib, argv, modifiers):
    resource.resource_config(lib, argv, modifiers, stonith=True)
    print_stonith_levels(lib)


def print_stonith_levels(lib):
    levels = stonith_level_config_to_str(
        lib.fencing_topology.get_config()
    )
    if levels:
        print("\n".join(indent(levels, 1)))

def stonith_list_available(lib, argv, modifiers):
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
            "No stonith agents available. "
            "Do you have fence agents installed?"
        )

    for agent_info in agent_list:
        name = agent_info["name"]
        shortdesc = agent_info["shortdesc"]
        if shortdesc:
            print("{0} - {1}".format(
                name,
                resource._format_desc(
                    len(name + " - "), shortdesc.replace("\n", " ")
                )
            ))
        else:
            print(name)


def stonith_list_options(lib, argv, modifiers):
    """
    Options:
      * --full - show advanced options
    """
    modifiers.ensure_only_supported("--full")
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = argv[0]

    print(resource._format_agent_description(
        lib.stonith_agent.describe_agent(agent_name),
        stonith=True,
        show_all=modifiers.get("--full"),
    ))

def stonith_create(lib, argv, modifiers):
    """
    Options:
      * --before - specified resource inside a group before which new resource
        will be placed inside the group
      * --after - specified resource inside a group after which new resource
        will be placed inside the group
      * --group - specifies group in which resource will be created
      * --force - allow not existing agent, invalid operations or invalid
        instance attributes
      * --disabled - created reource will be disabled
      * --no-default-ops - do not add default operations
      * --wait
      * -f - CIB file
    """
    modifiers.ensure_only_supported(
        "--before", "--after", "--group", "--force", "--disabled",
        "--no-default-ops", "--wait", "-f",
    )
    if modifiers.is_specified("--before") and modifiers.is_specified("--after"):
        raise error("you cannot specify both --before and --after{0}".format(
            "" if modifiers.is_specified("--group")
            else " and you have to specify --group"
        ))

    if not modifiers.is_specified("--group"):
        if modifiers.is_specified("--before"):
            raise error("you cannot use --before without --group")
        if modifiers.is_specified("--after"):
            raise error("you cannot use --after without --group")

    if len(argv) < 2:
        raise CmdLineInputError()

    stonith_id = argv[0]
    stonith_type = argv[1]

    parts = parse_create_args(argv[2:])

    settings = dict(
        allow_absent_agent=modifiers.get("--force"),
        allow_invalid_operation=modifiers.get("--force"),
        allow_invalid_instance_attributes=modifiers.get("--force"),
        ensure_disabled=modifiers.get("--disabled"),
        use_default_operations=not modifiers.get("--no-default-ops"),
        wait=modifiers.get("--wait"),
    )

    if not modifiers.get("--group"):
        lib.stonith.create(
            stonith_id, stonith_type, parts["op"],
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

        lib.stonith.create_in_group(
            stonith_id, stonith_type, modifiers.get("--group"), parts["op"],
            parts["meta"],
            parts["options"],
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
            **settings
        )

def stonith_level_parse_node(arg):
    """
    Commandline options: no options
    """
    target_type_candidate, target_value_candidate = parse_args.parse_typed_arg(
        arg,
        target_type_map_cli_to_lib.keys(),
        "node"
    )
    target_type = target_type_map_cli_to_lib[target_type_candidate]
    if target_type == TARGET_TYPE_ATTRIBUTE:
        target_value = parse_args.split_option(target_value_candidate)
    else:
        target_value = target_value_candidate
    return target_type, target_value

def stonith_level_normalize_devices(argv):
    """
    Commandline options: no options
    """
    # normalize devices - previously it was possible to delimit devices by both
    # a comma and a space
    return ",".join(argv).split(",")

def stonith_level_add_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow not existing stonith device, allow not existing node
        (target)
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()
    target_type, target_value = stonith_level_parse_node(argv[1])
    lib.fencing_topology.add_level(
        argv[0],
        target_type,
        target_value,
        stonith_level_normalize_devices(argv[2:]),
        force_device=modifiers.get("--force"),
        force_node=modifiers.get("--force"),
    )

def stonith_level_clear_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) > 1:
        raise CmdLineInputError()

    if not argv:
        lib.fencing_topology.remove_all_levels()
        return

    target_type, target_value = stonith_level_parse_node(argv[0])
    # backward compatibility mode
    # Command parameters are: node, stonith-list
    # Both the node and the stonith list are optional. If the node is ommited
    # and the stonith list is present, there is no way to figure it out, since
    # there is no specification of what the parameter is. Hence the pre-lib
    # code tried both. It deleted all levels having the first parameter as
    # either a node or a device list. Since it was only possible to specify
    # node as a target back then, this is enabled only in that case.
    was_error = False
    try:
        lib.fencing_topology.remove_levels_by_params(
            None,
            target_type,
            target_value,
            None,
            # pre-lib code didn't return any error when no level was found
            ignore_if_missing=True
        )
    except LibraryError:
        was_error = True
    if target_type == TARGET_TYPE_NODE:
        try:
            lib.fencing_topology.remove_levels_by_params(
                None,
                None,
                None,
                argv[0].split(","),
                # pre-lib code didn't return any error when no level was found
                ignore_if_missing=True
            )
        except LibraryError:
            was_error = True
    if was_error:
        raise LibraryError()

def stonith_level_config_to_str(config):
    """
    Commandline option: no options
    """
    config_data = dict()
    for level in config:
        if level["target_type"] not in config_data:
            config_data[level["target_type"]] = dict()
        if level["target_value"] not in config_data[level["target_type"]]:
            config_data[level["target_type"]][level["target_value"]] = []
        config_data[level["target_type"]][level["target_value"]].append(level)

    lines = []
    for target_type in [
        TARGET_TYPE_NODE, TARGET_TYPE_REGEXP, TARGET_TYPE_ATTRIBUTE
    ]:
        if not target_type in config_data:
            continue
        for target_value in sorted(config_data[target_type].keys()):
            lines.append("Target: {0}".format(
                "=".join(target_value) if target_type == TARGET_TYPE_ATTRIBUTE
                else target_value
            ))
            level_lines = []
            for target_level in sorted(
                config_data[target_type][target_value],
                key=lambda level: level["level"]
            ):
                level_lines.append("Level {level} - {devices}".format(
                    level=target_level["level"],
                    devices=",".join(target_level["devices"])
                ))
            lines.extend(indent(level_lines))
    return lines

def stonith_level_config_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    lines = stonith_level_config_to_str(lib.fencing_topology.get_config())
    # do not print \n when lines are empty
    if lines:
        print("\n".join(lines))

def stonith_level_remove_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    target_type, target_value, devices = None, None, None
    level = argv[0]
    if len(argv) > 1:
        target_type, target_value = stonith_level_parse_node(argv[1])
    if len(argv) > 2:
        devices = stonith_level_normalize_devices(argv[2:])

    lib.fencing_topology.remove_levels_by_params(
        level,
        target_type,
        target_value,
        devices,
        # backward compatibility mode, see lib command for details
        target_may_be_a_device=True
    )

def stonith_level_verify_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    # raises LibraryError in case of problems, else we don't want to do anything
    lib.fencing_topology.verify()

def stonith_fence(lib, argv, modifiers):
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
        print("Node: %s fenced" % node)

def stonith_confirm(lib, argv, modifiers):
    """
    Options:
      * --force - do not warn user
    """
    del lib
    modifiers.ensure_only_supported("--force")
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to confirm fenced")

    node = argv.pop(0)
    if not modifiers.get("--force"):
        answer = utils.get_terminal_input(
            (
                "WARNING: If node {node} is not powered off or it does"
                + " have access to shared resources, data corruption and/or"
                + " cluster failure may occur. Are you sure you want to"
                + " continue? [y/N] "
            ).format(node=node)
        )
        if answer.lower() not in ["y", "yes"]:
            print("Canceled")
            return
    args = ["stonith_admin", "-C", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to confirm fencing of node '%s'\n" % node + output)
    else:
        print("Node: %s confirmed fenced" % node)


# This is used only by pcsd, will be removed in new architecture
def get_fence_agent_info(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        utils.err("One parameter expected")

    agent = argv[0]
    if not agent.startswith("stonith:"):
        utils.err("Invalid fence agent name")

    runner = utils.cmd_runner()

    try:
        metadata = lib_ra.StonithAgent(runner, agent[len("stonith:"):])
        info = metadata.get_full_info()
        info["name"] = "stonith:{0}".format(info["name"])
        print(json.dumps(info))
    except lib_ra.ResourceAgentError as e:
        process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e)]
        )
    except LibraryError as e:
        process_library_reports(e.args)


def sbd_watchdog_list(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    available_watchdogs = lib.sbd.get_local_available_watchdogs()

    if available_watchdogs:
        print("Available watchdog(s):")
        for watchdog in sorted(available_watchdogs.keys()):
            print("  {}".format(watchdog))
    else:
        print("No available watchdog")

def sbd_watchdog_list_json(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(json.dumps(lib.sbd.get_local_available_watchdogs()))


def sbd_watchdog_test(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) > 1:
        raise CmdLineInputError()
    print(
        "Warning: This operation is expected to force-reboot this system "
        "without following any shutdown procedures."
    )
    if utils.get_terminal_input("Proceed? [no/yes]: ") != "yes":
        return
    watchdog = None
    if len(argv) == 1:
        watchdog = argv[0]
    lib.sbd.test_local_watchdog(watchdog)


def sbd_enable(lib, argv, modifiers):
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --force - allow unknown SBD options
      * --skip-offline - skip offline cluster nodes
      * --no-watchdog-validation - do not validate watchdog
    """
    modifiers.ensure_only_supported(
        "--request-timeout", "--force", "--skip-offline",
        "--no-watchdog-validation",
    )
    options = parse_args.prepare_options(
        argv,
        allowed_repeatable_options=("device", "watchdog")
    )
    default_watchdog, watchdog_dict = _sbd_parse_watchdogs(
        options.get("watchdog", [])
    )
    default_device_list, node_device_dict = _sbd_parse_node_specific_options(
        options.get("device", [])
    )

    lib.sbd.enable_sbd(
        default_watchdog,
        watchdog_dict,
        {
            name: value for name, value in options.items()
            if name not in ("device", "watchdog")
        },
        default_device_list=(
            default_device_list if default_device_list else None
        ),
        node_device_dict=node_device_dict if node_device_dict else None,
        allow_unknown_opts=modifiers.get("--force"),
        ignore_offline_nodes=modifiers.get("--skip-offline"),
        no_watchdog_validation=modifiers.get("--no-watchdog-validation"),
    )

def _sbd_parse_node_specific_options(arg_list):
    """
    Commandline options: no options
    """
    default_option_list = []
    node_specific_option_dict = {}

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


def _sbd_parse_watchdogs(watchdog_list):
    """
    Commandline options: no options
    """
    default_watchdog_list, node_specific_watchdog_dict =\
        _sbd_parse_node_specific_options(watchdog_list)
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
                "Multiple watchdog definitions for node '{node}'".format(
                    node=node
                )
            )
        watchdog_dict[node] = node_watchdog_list[0]

    return default_watchdog, watchdog_dict


def sbd_disable(lib, argv, modifiers):
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --skip-offline - skip offline cluster nodes
    """
    modifiers.ensure_only_supported("--request-timeout", "--skip-offline")
    if argv:
        raise CmdLineInputError()

    lib.sbd.disable_sbd(modifiers.get("--skip-offline"))


def sbd_status(lib, argv, modifiers):
    """
    Options:
      * --request-timeout - HTTP request timeout
      * --full - display SBD device header
    """
    modifiers.ensure_only_supported("--request-timeout", "--full")
    def _bool_to_str(val):
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
        print("{node}: {installed} | {enabled} | {running}".format(
            node=node_status["node"],
            installed=_bool_to_str(status.get("installed")),
            enabled=_bool_to_str(status.get("enabled")),
            running=_bool_to_str(status.get("running"))
        ))
    device_list = lib.sbd.get_local_devices_info(modifiers.get("--full"))
    for device in device_list:
        print()
        print("Messages list on device '{0}':".format(device["device"]))
        print("<unknown>" if device["list"] is None else device["list"])
        if modifiers.get("--full"):
            print()
            print("SBD header on device '{0}':".format(device["device"]))
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
        print("  {node}: {value}".format(node=config["node"], value=value))


def sbd_config(lib, argv, modifiers):
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
        "SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER", "SBD_DEVICE"
    ]
    with_device = False
    for key, val in config.items():
        if key == "SBD_DEVICE":
            with_device = True
        if key in filtered_options:
            continue
        print("{key}={val}".format(key=key, val=val))

    print()
    print("Watchdogs:")
    _print_per_node_option(config_list, "SBD_WATCHDOG_DEV")

    if with_device:
        print()
        print("Devices:")
        _print_per_node_option(config_list, "SBD_DEVICE")


def local_sbd_config(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(json.dumps(lib.sbd.get_local_sbd_config()))


def sbd_setup_block_device(lib, argv, modifiers):
    """
    Options:
      * --force - do not show warning about wiping the devices
    """
    modifiers.ensure_only_supported("--force")
    options = parse_args.prepare_options(
        argv,
        allowed_repeatable_options=("device",)
    )
    device_list = options.get("device", [])
    if not device_list:
        raise CmdLineInputError("No device defined")

    if not modifiers.get("--force"):
        answer = utils.get_terminal_input(
            (
                "WARNING: All current content on device(s) '{device}' will be"
                + " overwritten. Are you sure you want to continue? [y/N] "
            ).format(device="', '".join(device_list))
        )
        if answer.lower() not in ["y", "yes"]:
            print("Canceled")
            return

    lib.sbd.initialize_block_devices(
        device_list,
        {
            name: value for name, value in options.items()
            if name != "device"
        }
    )


def sbd_message(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) != 3:
        raise CmdLineInputError()

    device, node, message = argv
    lib.sbd.set_message(device, node, message)


def stonith_history_show_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) > 1:
        raise CmdLineInputError()

    node = argv[0] if argv else None
    print(lib.stonith.history_get_text(node))


def stonith_history_cleanup_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if len(argv) > 1:
        raise CmdLineInputError()

    node = argv[0] if argv else None
    print(lib.stonith.history_cleanup(node))


def stonith_history_update_cmd(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()

    print(lib.stonith.history_update())
