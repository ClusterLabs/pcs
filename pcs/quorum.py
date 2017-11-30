from __future__ import (
    absolute_import,
    division,
    print_function,
)

import sys

from pcs import (
    stonith,
    usage,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.console_report import indent
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def quorum_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        sub_cmd, argv_next = "config", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.quorum([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "config":
            quorum_config_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "expected-votes":
            quorum_expected_votes_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "status":
            quorum_status_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "device":
            quorum_device_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "unblock":
            # TODO switch to new architecture
            quorum_unblock_cmd(argv_next)
        elif sub_cmd == "update":
            quorum_update_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "quorum", sub_cmd)

def quorum_device_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "add":
            quorum_device_add_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "heuristics":
            quorum_device_heuristics_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "remove":
            quorum_device_remove_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "status":
            quorum_device_status_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "update":
            quorum_device_update_cmd(lib, argv_next, modifiers)
        else:
            sub_cmd = ""
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "quorum", "device {0}".format(sub_cmd)
        )

def quorum_device_heuristics_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "remove":
            quorum_device_heuristics_remove_cmd(lib, argv_next, modifiers)
        else:
            sub_cmd = ""
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "quorum", "device heuristics {0}".format(sub_cmd)
        )


def quorum_config_cmd(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()
    config = lib.quorum.get_config()
    print("\n".join(quorum_config_to_str(config)))

def quorum_config_to_str(config):
    lines = []

    lines.append("Options:")
    if "options" in config and config["options"]:
        lines.extend(indent([
            "{n}: {v}".format(n=name, v=value)
            for name, value in sorted(config["options"].items())
        ]))

    if "device" in config and config["device"]:
        lines.append("Device:")
        lines.extend(indent([
            "{n}: {v}".format(n=name, v=value)
            for name, value in sorted(
                config["device"].get("generic_options", {}).items()
            )
        ]))

        model_settings = [
            "Model: {m}".format(m=config["device"].get("model", ""))
        ]
        model_settings.extend(indent([
            "{n}: {v}".format(n=name, v=value)
            for name, value in sorted(
                config["device"].get("model_options", {}).items()
            )
        ]))
        lines.extend(indent(model_settings))

        heuristics_options = config["device"].get("heuristics_options", {})
        if heuristics_options:
            heuristics_settings = ["Heuristics:"]
            heuristics_settings.extend(indent([
                "{n}: {v}".format(n=name, v=value)
                for name, value in sorted(heuristics_options.items())
            ]))
            lines.extend(indent(heuristics_settings))

    return lines

def quorum_expected_votes_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.quorum.set_expected_votes_live(argv[0])

def quorum_status_cmd(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()
    print(lib.quorum.status())

def quorum_update_cmd(lib, argv, modifiers):
    options = parse_args.prepare_options(argv)
    if not options:
        raise CmdLineInputError()

    lib.quorum.set_options(
        options,
        skip_offline_nodes=modifiers["skip_offline_nodes"],
        force=modifiers["force"]
    )

def _parse_quorum_device_groups(arg_list):
    keyword_list = ["model", "heuristics"]
    groups = parse_args.group_by_keywords(
        arg_list,
        set(keyword_list),
        implicit_first_group_key="generic",
        keyword_repeat_allowed=False,
        only_found_keywords=True
    )
    for keyword in keyword_list:
        if keyword not in groups:
            continue
        if len(groups[keyword]) == 0:
            raise CmdLineInputError(
                "No {0} options specified".format(keyword)
            )
    return groups

def quorum_device_add_cmd(lib, argv, modifiers):
    groups = _parse_quorum_device_groups(argv)
    model_and_model_options = groups.get("model", [])
    # we expect "model" keyword once, followed by the actual model value
    if not model_and_model_options or "=" in model_and_model_options[0]:
        raise CmdLineInputError()

    generic_options = parse_args.prepare_options(groups.get("generic", []))
    model = model_and_model_options[0]
    model_options = parse_args.prepare_options(model_and_model_options[1:])
    heuristics_options = parse_args.prepare_options(
        groups.get("heuristics", [])
    )

    if "model" in generic_options:
        raise CmdLineInputError("Model cannot be specified in generic options")

    lib.quorum.add_device(
        model,
        model_options,
        generic_options,
        heuristics_options,
        force_model=modifiers["force"],
        force_options=modifiers["force"],
        skip_offline_nodes=modifiers["skip_offline_nodes"]
    )

def quorum_device_remove_cmd(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    lib.quorum.remove_device(
        skip_offline_nodes=modifiers["skip_offline_nodes"]
    )

def quorum_device_status_cmd(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()
    print(lib.quorum.status_device(modifiers["full"]))

def quorum_device_update_cmd(lib, argv, modifiers):
    groups = _parse_quorum_device_groups(argv)
    if not groups:
        raise CmdLineInputError()
    generic_options = parse_args.prepare_options(groups.get("generic", []))
    model_options = parse_args.prepare_options(groups.get("model", []))
    heuristics_options = parse_args.prepare_options(
        groups.get("heuristics", [])
    )

    if "model" in generic_options:
        raise CmdLineInputError("Model cannot be specified in generic options")

    lib.quorum.update_device(
        model_options,
        generic_options,
        heuristics_options,
        force_options=modifiers["force"],
        skip_offline_nodes=modifiers["skip_offline_nodes"]
    )

def quorum_device_heuristics_remove_cmd(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()
    lib.quorum.remove_device_heuristics()

# TODO switch to new architecture, move to lib
def quorum_unblock_cmd(argv):
    if len(argv) > 0:
        usage.quorum(["unblock"])
        sys.exit(1)

    if utils.is_rhel6():
        utils.err("operation is not supported on CMAN clusters")

    output, retval = utils.run(
        ["corosync-cmapctl", "-g", "runtime.votequorum.wait_for_all_status"]
    )
    if retval != 0:
        utils.err("unable to check quorum status")
    if output.split("=")[-1].strip() != "1":
        utils.err("cluster is not waiting for nodes to establish quorum")

    unjoined_nodes = (
        set(utils.getNodesFromCorosyncConf())
        -
        set(utils.getCorosyncActiveNodes())
    )
    if not unjoined_nodes:
        utils.err("no unjoined nodes found")
    if "--force" not in utils.pcs_options:
        answer = utils.get_terminal_input(
            (
                "WARNING: If node(s) {nodes} are not powered off or they do"
                + " have access to shared resources, data corruption and/or"
                + " cluster failure may occur. Are you sure you want to"
                + " continue? [y/N] "
            ).format(nodes=", ".join(unjoined_nodes))
        )
        if answer.lower() not in ["y", "yes"]:
            print("Canceled")
            return
    for node in unjoined_nodes:
        stonith.stonith_confirm([node], skip_question=True)

    output, retval = utils.run(
        ["corosync-cmapctl", "-s", "quorum.cancel_wait_for_all", "u8", "1"]
    )
    if retval != 0:
        utils.err("unable to cancel waiting for nodes")
    print("Quorum unblocked")

    startup_fencing = utils.get_set_properties().get("startup-fencing", "")
    utils.set_cib_property(
        "startup-fencing",
        "false" if startup_fencing.lower() != "false" else "true"
    )
    utils.set_cib_property("startup-fencing", startup_fencing)
    print("Waiting for nodes canceled")
