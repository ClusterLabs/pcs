from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json
import sys

from pcs import (
    resource,
    usage,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.console_report import indent, error
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.fencing_topology import target_type_map_cli_to_lib
from pcs.cli.resource.parse_args import parse_create_simple as parse_create_args
from pcs.common import report_codes
from pcs.common.fencing_topology import (
    TARGET_TYPE_NODE,
    TARGET_TYPE_REGEXP,
    TARGET_TYPE_ATTRIBUTE,
)
from pcs.lib import sbd
from pcs.lib.errors import LibraryError
import pcs.lib.resource_agent as lib_ra

def stonith_cmd(argv):
    if len(argv) < 1:
        sub_cmd, argv_next = "show", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    lib = utils.get_library_wrapper()
    modifiers = utils.get_modifiers()

    try:
        if sub_cmd == "help":
            usage.stonith([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "list":
            stonith_list_available(lib, argv_next, modifiers)
        elif sub_cmd == "describe":
            stonith_list_options(lib, argv_next, modifiers)
        elif sub_cmd == "create":
            stonith_create(lib, argv_next, modifiers)
        elif sub_cmd == "update":
            if len(argv_next) > 1:
                stn_id = argv_next.pop(0)
                resource.resource_update(stn_id, argv_next)
            else:
                raise CmdLineInputError()
        elif sub_cmd == "delete":
            if len(argv_next) == 1:
                stn_id = argv_next.pop(0)
                resource.resource_remove(stn_id)
            else:
                raise CmdLineInputError()
        elif sub_cmd == "show":
            resource.resource_show(argv_next, True)
            levels = stonith_level_config_to_str(
                lib.fencing_topology.get_config()
            )
            if levels:
                print("\n".join(indent(levels, 1)))
        elif sub_cmd == "level":
            stonith_level_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "fence":
            stonith_fence(argv_next)
        elif sub_cmd == "cleanup":
            resource.resource_cleanup(argv_next)
        elif sub_cmd == "refresh":
            resource.resource_refresh(argv_next)
        elif sub_cmd == "confirm":
            stonith_confirm(argv_next)
        elif sub_cmd == "get_fence_agent_info":
            get_fence_agent_info(argv_next)
        elif sub_cmd == "sbd":
            sbd_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            resource.resource_enable_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "disable":
            resource.resource_disable_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "stonith", sub_cmd)

def stonith_level_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        sub_cmd, argv_next = "config", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "add":
            stonith_level_add_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "clear":
            stonith_level_clear_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "config":
            stonith_level_config_cmd(lib, argv_next, modifiers)
        elif sub_cmd in ["remove", "delete"]:
            stonith_level_remove_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "verify":
            stonith_level_verify_cmd(lib, argv_next, modifiers)
        else:
            sub_cmd = ""
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "stonith", "level {0}".format(sub_cmd)
        )

def stonith_list_available(lib, argv, modifiers):
    if len(argv) > 1:
        raise CmdLineInputError()

    search = argv[0] if argv else None
    agent_list = lib.stonith_agent.list_agents(modifiers["describe"], search)

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
    if len(argv) != 1:
        raise CmdLineInputError()
    agent_name = argv[0]

    print(resource._format_agent_description(
        lib.stonith_agent.describe_agent(agent_name),
        stonith=True,
        show_advanced=modifiers["full"]
    ))

def stonith_create(lib, argv, modifiers):
    if modifiers["before"] and modifiers["after"]:
        raise error("you cannot specify both --before and --after{0}".format(
            "" if modifiers["group"] else " and you have to specify --group"
        ))

    if not modifiers["group"]:
        if modifiers["before"]:
            raise error("you cannot use --before without --group")
        elif modifiers["after"]:
            raise error("you cannot use --after without --group")

    if len(argv) < 2:
        usage.stonith(["create"])
        sys.exit(1)

    stonith_id = argv[0]
    stonith_type = argv[1]

    parts = parse_create_args(argv[2:])

    settings = dict(
        allow_absent_agent=modifiers["force"],
        allow_invalid_operation=modifiers["force"],
        allow_invalid_instance_attributes=modifiers["force"],
        ensure_disabled=modifiers["disabled"],
        use_default_operations=not modifiers["no-default-ops"],
        wait=modifiers["wait"],
    )

    if not modifiers["group"]:
        lib.stonith.create(
            stonith_id, stonith_type, parts["op"],
            parts["meta"],
            parts["options"],
            **settings
        )
    else:
        adjacent_resource_id = None
        put_after_adjacent = False
        if modifiers["after"]:
            adjacent_resource_id = modifiers["after"]
            put_after_adjacent = True
        if modifiers["before"]:
            adjacent_resource_id = modifiers["before"]
            put_after_adjacent = False

        lib.stonith.create_in_group(
            stonith_id, stonith_type, modifiers["group"], parts["op"],
            parts["meta"],
            parts["options"],
            adjacent_resource_id=adjacent_resource_id,
            put_after_adjacent=put_after_adjacent,
            **settings
        )

def stonith_level_parse_node(arg):
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
    # normalize devices - previously it was possible to delimit devices by both
    # a comma and a space
    return ",".join(argv).split(",")

def stonith_level_add_cmd(lib, argv, modifiers):
    if len(argv) < 3:
        raise CmdLineInputError()
    target_type, target_value = stonith_level_parse_node(argv[1])
    lib.fencing_topology.add_level(
        argv[0],
        target_type,
        target_value,
        stonith_level_normalize_devices(argv[2:]),
        force_device=modifiers["force"],
        force_node=modifiers["force"]
    )

def stonith_level_clear_cmd(lib, argv, modifiers):
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
    report_item_list = []
    try:
        lib.fencing_topology.remove_levels_by_params(
            None,
            target_type,
            target_value,
            None,
            # pre-lib code didn't return any error when no level was found
            ignore_if_missing=True
        )
    except LibraryError as e:
        report_item_list.extend(e.args)
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
        except LibraryError as e:
            report_item_list.extend(e.args)
    if report_item_list:
        raise LibraryError(*report_item_list)

def stonith_level_config_to_str(config):
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
    if len(argv) > 0:
        raise CmdLineInputError()
    lines = stonith_level_config_to_str(lib.fencing_topology.get_config())
    # do not print \n when lines are empty
    if lines:
        print("\n".join(lines))

def stonith_level_remove_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()
    target_type, target_value, devices = None, None, None
    level = argv[0]
    if len(argv) > 1:
        target_type, target_value = stonith_level_parse_node(argv[1])
    if len(argv) > 2:
        devices = stonith_level_normalize_devices(argv[2:])

    try:
        lib.fencing_topology.remove_levels_by_params(
            level,
            target_type,
            target_value,
            devices
        )
    except LibraryError as e:
        # backward compatibility mode
        # Command parameters are: level, node, stonith, stonith...
        # Both the node and the stonith list are optional. If the node is
        # ommited and the stonith list is present, there is no way to figure it
        # out, since there is no specification of what the parameter is. Hence
        # the pre-lib code tried both. First it assumed the first parameter is
        # a node. If that fence level didn't exist, it assumed the first
        # parameter is a device. Since it was only possible to specify node as
        # a target back then, this is enabled only in that case.
        if target_type != TARGET_TYPE_NODE:
            raise e
        level_not_found = False
        for report_item in e.args:
            if (
                report_item.code
                ==
                report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST
            ):
                level_not_found = True
                break
        if not level_not_found:
            raise e
        target_and_devices = [target_value]
        if devices:
            target_and_devices.extend(devices)
        try:
            lib.fencing_topology.remove_levels_by_params(
                level,
                None,
                None,
                target_and_devices
            )
        except LibraryError as e_second:
            raise LibraryError(*(e.args + e_second.args))

def stonith_level_verify_cmd(lib, argv, modifiers):
    if len(argv) > 0:
        raise CmdLineInputError()
    # raises LibraryError in case of problems, else we don't want to do anything
    lib.fencing_topology.verify()

def stonith_fence(argv):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to fence")

    node = argv.pop(0)
    if "--off" in utils.pcs_options:
        args = ["stonith_admin", "-F", node]
    else:
        args = ["stonith_admin", "-B", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to fence '%s'\n" % node + output)
    else:
        print("Node: %s fenced" % node)

def stonith_confirm(argv, skip_question=False):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to confirm fenced")

    node = argv.pop(0)
    if not skip_question and "--force" not in utils.pcs_options:
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


def get_fence_agent_info(argv):
# This is used only by pcsd, will be removed in new architecture
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
        utils.process_library_reports(
            [lib_ra.resource_agent_error_to_report_item(e)]
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)


def sbd_cmd(lib, argv, modifiers):
    if len(argv) == 0:
        raise CmdLineInputError()
    cmd = argv.pop(0)
    try:
        if cmd == "enable":
            sbd_enable(lib, argv, modifiers)
        elif cmd == "disable":
            sbd_disable(lib, argv, modifiers)
        elif cmd == "status":
            sbd_status(lib, argv, modifiers)
        elif cmd == "config":
            sbd_config(lib, argv, modifiers)
        elif cmd == "local_config_in_json":
            local_sbd_config(lib, argv, modifiers)
        elif cmd == "device":
            sbd_device_cmd(lib, argv, modifiers)
        elif cmd == "watchdog":
            sbd_watchdog_cmd(lib, argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "stonith", "sbd {0}".format(cmd)
        )


def sbd_watchdog_cmd(lib, argv, modifiers):
    if len(argv) == 0:
        raise CmdLineInputError()
    cmd = argv.pop(0)
    try:
        if cmd == "list":
            sbd_watchdog_list(lib, argv, modifiers)
        elif cmd == "list_json":
            sbd_watchdog_list_json(lib, argv, modifiers)
        elif cmd == "test":
            sbd_watchdog_test(lib, argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "stonith", "sbd watchdog {0}".format(cmd)
        )


def sbd_watchdog_list(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    available_watchdogs = lib.sbd.get_local_available_watchdogs()
    supported_watchdog_list = [
        wd for wd, wd_info in available_watchdogs.items()
        if wd_info["caution"] is None
    ]
    unsupported_watchdog_list = [
        wd for wd in available_watchdogs
        if wd not in supported_watchdog_list
    ]

    if supported_watchdog_list:
        print("Supported watchdog(s):")
        for watchdog in supported_watchdog_list:
            print("  {}".format(watchdog))

    if unsupported_watchdog_list:
        print("Unsupported watchdog(s):")
        for watchdog in unsupported_watchdog_list:
            print("  {}".format(watchdog))


def sbd_watchdog_list_json(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()
    print(json.dumps(lib.sbd.get_local_available_watchdogs()))


def sbd_watchdog_test(lib, argv, modifiers):
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


def sbd_device_cmd(lib, argv, modifiers):
    if len(argv) == 0:
        raise CmdLineInputError()
    cmd = argv.pop(0)
    try:
        if cmd == "setup":
            sbd_setup_block_device(lib, argv, modifiers)
        elif cmd == "message":
            sbd_message(lib, argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "stonith", "sbd device {0}".format(cmd)
        )


def sbd_enable(lib, argv, modifiers):
    sbd_cfg = parse_args.prepare_options(argv)
    default_watchdog, watchdog_dict = _sbd_parse_watchdogs(
        modifiers["watchdog"]
    )
    default_device_list, node_device_dict = _sbd_parse_node_specific_options(
        modifiers["device"]
    )

    lib.sbd.enable_sbd(
        default_watchdog,
        watchdog_dict,
        sbd_cfg,
        default_device_list=(
            default_device_list if default_device_list else None
        ),
        node_device_dict=node_device_dict if node_device_dict else None,
        allow_unknown_opts=modifiers["force"],
        ignore_offline_nodes=modifiers["skip_offline_nodes"],
        no_watchdog_validation=modifiers["no_watchdog_validation"],
    )

def _sbd_parse_node_specific_options(arg_list):
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
    default_watchdog_list, node_specific_watchdog_dict =\
        _sbd_parse_node_specific_options(watchdog_list)
    if not default_watchdog_list:
        default_watchdog = None
    elif len(default_watchdog_list) == 1:
        default_watchdog = default_watchdog_list[0]
    else:
        raise CmdLineInputError("Multiple watchdog definitions.")

    watchdog_dict = {}
    for node, watchdog_list in node_specific_watchdog_dict.items():
        if len(watchdog_list) > 1:
            raise CmdLineInputError(
                "Multiple watchdog definitions for node '{node}'".format(
                    node=node
                )
            )
        watchdog_dict[node] = watchdog_list[0]

    return default_watchdog, watchdog_dict


def sbd_disable(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    lib.sbd.disable_sbd(modifiers["skip_offline_nodes"])


def sbd_status(lib, argv, modifiers):
    def _bool_to_str(val):
        if val is None:
            return "N/A"
        return "YES" if val else " NO"

    if argv:
        raise CmdLineInputError()

    status_list = lib.sbd.get_cluster_sbd_status()
    if not len(status_list):
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
    device_list = lib.sbd.get_local_devices_info(modifiers["full"])
    for device in device_list:
        print()
        print("Messages list on device '{0}':".format(device["device"]))
        print("<unknown>" if device["list"] is None else device["list"])
        if modifiers["full"]:
            print()
            print("SBD header on device '{0}':".format(device["device"]))
            print("<unknown>" if device["dump"] is None else device["dump"])

def _print_per_node_option(config_list, config_option):
    unknown_value = "<unknown>"
    for config in config_list:
        value = unknown_value
        if config["config"] is not None:
            value = config["config"].get(config_option, unknown_value)
        print("  {node}: {value}".format(node=config["node"], value=value))


def sbd_config(lib, argv, modifiers):
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
    print(json.dumps(lib.sbd.get_local_sbd_config()))


def sbd_setup_block_device(lib, argv, modifiers):
    device_list = modifiers["device"]
    if not device_list:
        raise CmdLineInputError("No device defined")
    options = parse_args.prepare_options(argv)

    if not modifiers["force"]:
        answer = utils.get_terminal_input(
            (
                "WARNING: All current content on device(s) '{device}' will be"
                + " overwritten. Are you sure you want to continue? [y/N] "
            ).format(device="', '".join(device_list))
        )
        if answer.lower() not in ["y", "yes"]:
            print("Canceled")
            return
    lib.sbd.initialize_block_devices(device_list, options)


def sbd_message(lib, argv, modifiers):
    if len(argv) != 3:
        raise CmdLineInputError()

    device, node, message = argv
    lib.sbd.set_message(device, node, message)
