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
from pcs.cli.common import middleware
from pcs.cli.common import parse_args
from pcs.cli.common.console_report import indent
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def run_with_middleware(func, lib, argv, modificators):
    run = middleware.build(
        utils.get_middleware_corosync_conf_existing(),
    )
    run(func, lib, argv, modificators)

def quorum_cmd(lib, argv, modificators):
    if len(argv) < 1:
        usage.quorum()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "help":
            usage.quorum(argv)
        elif sub_cmd == "config":
            run_with_middleware(quorum_config_cmd, lib, argv_next, modificators)
        elif sub_cmd == "device":
            quorum_device_cmd(lib, argv_next, modificators)
        elif sub_cmd == "update":
            run_with_middleware(quorum_update_cmd, lib, argv_next, modificators)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "quorum", sub_cmd)

def quorum_device_cmd(lib, argv, modificators):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "add":
            run_with_middleware(
                quorum_device_add_cmd, lib, argv_next, modificators
            )
        elif sub_cmd == "remove":
            run_with_middleware(
                quorum_device_remove_cmd, lib, argv_next, modificators
            )
        elif sub_cmd == "update":
            run_with_middleware(
                quorum_device_update_cmd, lib, argv_next, modificators
            )
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "quorum", "device {0}".format(sub_cmd)
        )

def quorum_config_cmd(lib, argv, modificators):
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

    return lines

def quorum_device_add_cmd(lib, argv, modificators):
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

    lib.quorum.add_device(model, model_options, generic_options)

def quorum_device_remove_cmd(lib, argv, modificators):
    if argv:
        raise CmdLineInputError()

    lib.quorum.remove_device()

def quorum_device_update_cmd(lib, argv, modificators):
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

    lib.quorum.update_device(model_options, generic_options)

def quorum_update_cmd(lib, argv, modificators):
    options = parse_args.prepare_options(argv)
    if not options:
        raise CmdLineInputError()

    lib.quorum.set_options(options)
