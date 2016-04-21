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
from pcs.cli.common.errors import CmdLineInputError, ErrorWithMessage
from pcs.cli.common.parse_args import prepare_options, MissingOptionValue
from pcs.lib.commands import quorum as lib_quorum
from pcs.lib.errors import LibraryError

class ModelSpecifiedMoreThanOnce(Exception):
    pass


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
    except ErrorWithMessage as e:
        utils.err(e.message)
    except CmdLineInputError:
        usage.quorum(argv)
        sys.exit(1)

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
    except ModelSpecifiedMoreThanOnce:
        utils.err("Model can be specified only once")

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
    model, model_options, generic_options = prepare_device_options(argv)
    if not model:
        raise MissingOptionValue("model")

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
    model, model_options, generic_options = prepare_device_options(argv)
    if model:
        raise CmdLineInputError()

    lib_env = utils.get_lib_env()
    lib_quorum.update_device(lib_env, model_options, generic_options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

def quorum_update_cmd(argv):
    options = prepare_options(argv)
    if not options:
        raise CmdLineInputError()

    lib_env = utils.get_lib_env()
    lib_quorum.set_options(lib_env, options)
    if "--corosync_conf" in utils.pcs_options:
        utils.setCorosyncConf(
            lib_env.get_corosync_conf(),
            utils.pcs_options["--corosync_conf"]
        )

def prepare_device_options(argv):
    generic_argv = []
    model_argv = []
    model = None
    in_model = False
    in_model_options = False

    for arg in argv:
        if in_model:
            if "=" in arg:
                model_argv.append(arg)
            else:
                model = arg
            in_model = False
            in_model_options = True
        elif arg.lower() == "model":
            if in_model_options:
                raise ModelSpecifiedMoreThanOnce()
            in_model = True
        elif in_model_options:
            model_argv.append(arg)
        else:
            generic_argv.append(arg)

    generic_options = prepare_options(generic_argv)
    model_options = prepare_options(model_argv)
    return model, model_options, generic_options
