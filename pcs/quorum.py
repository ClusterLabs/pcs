from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import (
    usage,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
import pcs.cli.common.parse_args as parse_args
from pcs.lib.commands import quorum as lib_quorum
from pcs.lib.errors import LibraryError


def quorum_cmd(argv):
    if len(argv) < 1:
        usage.quorum()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "help":
            usage.quorum(argv)
        elif sub_cmd == "config":
            quorum_config_cmd(argv_next)
        elif sub_cmd == "device":
            quorum_device_cmd(argv_next)
        elif sub_cmd == "update":
            quorum_update_cmd(argv_next)
        else:
            raise CmdLineInputError()

    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "quorum", sub_cmd)

def quorum_device_cmd(argv):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "add":
            quorum_device_add_cmd(argv_next)
        elif sub_cmd == "remove":
            quorum_device_remove_cmd(argv_next)
        elif sub_cmd == "update":
            quorum_device_update_cmd(argv_next)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "quorum", "device {0}".format(sub_cmd)
        )

def quorum_config_cmd(argv):
    if argv:
        raise CmdLineInputError()
    config = lib_quorum.get_config(utils.get_lib_env())
    print(quorum_config_to_str(config))

def quorum_config_to_str(config, indent=""):
    lines = []

    lines.append("{i}Options:".format(i=indent))
    if "options" in config and config["options"]:
        for name, value in sorted(config["options"].items()):
            lines.append("{i} {n}: {v}".format(i=indent, n=name, v=value))

    if "device" in config and config["device"]:
        lines.append("{i}Device:".format(i=indent))
        for name, value in sorted(
            config["device"].get("generic_options", {}).items()
        ):
            lines.append("{i} {n}: {v}".format(i=indent, n=name, v=value))
        lines.append(
            "{i} Model: {m}".format(
                i=indent, m=config["device"].get("model", "")
            )
        )
        for name, value in sorted(
            config["device"].get("model_options", {}).items()
        ):
            lines.append("{i}  {n}: {v}".format(i=indent, n=name, v=value))

    return "\n".join(lines)

def quorum_device_add_cmd(argv):
    # we expect "model" keyword once, followed by the actual model value
    options_lists = parse_args.split_list(argv, "model")
    if len(options_lists) != 2:
        raise CmdLineInputError()
    # check if model value was specified
    if not options_lists[1] or "=" in options_lists[1][0]:
        raise CmdLineInputError()
    generic_options = parse_args.prepare_options(options_lists[0])
    model = options_lists[1][0]
    model_options = parse_args.prepare_options(options_lists[1][1:])

    if "model" in generic_options:
        raise CmdLineInputError(
            "Model cannot be specified in generic options"
        )

    lib_env = utils.get_lib_env()
    lib_quorum.add_device(lib_env, model, model_options, generic_options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

def quorum_device_remove_cmd(argv):
    if argv:
        raise CmdLineInputError()

    lib_env = utils.get_lib_env()
    lib_quorum.remove_device(lib_env)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

def quorum_device_update_cmd(argv):
    # we expect "model" keyword once
    options_lists = parse_args.split_list(argv, "model")
    if len(options_lists) == 1:
        generic_options = parse_args.prepare_options(options_lists[0])
        model_options = dict()
    elif len(options_lists) == 2:
        generic_options = parse_args.prepare_options(options_lists[0])
        model_options = parse_args.prepare_options(options_lists[1])
    else:
        raise CmdLineInputError()

    if "model" in generic_options:
        raise CmdLineInputError(
            "Model cannot be specified in generic options"
        )

    lib_env = utils.get_lib_env()
    lib_quorum.update_device(lib_env, model_options, generic_options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

def quorum_update_cmd(argv):
    options = parse_args.prepare_options(argv)
    if not options:
        raise CmdLineInputError()

    lib_env = utils.get_lib_env()
    lib_quorum.set_options(lib_env, options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )
