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
from pcs.lib.errors import LibraryError

def qdevice_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        usage.qdevice()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "help":
            usage.qdevice(argv)
        elif sub_cmd == "setup":
            qdevice_setup_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "destroy":
            qdevice_destroy_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "start":
            qdevice_start_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "stop":
            qdevice_stop_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            qdevice_enable_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "disable":
            qdevice_disable_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "qdevice", sub_cmd)

def qdevice_setup_cmd(lib, argv, modifiers):
    if len(argv) != 2:
        raise CmdLineInputError()
    if argv[0] != "model":
        raise CmdLineInputError()
    model = argv[1]
    lib.qdevice.setup(model, modifiers["enable"], modifiers["start"])

def qdevice_destroy_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.destroy(model)

def qdevice_start_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.start(model)

def qdevice_stop_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.stop(model)

def qdevice_enable_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.enable(model)

def qdevice_disable_cmd(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    model = argv[0]
    lib.qdevice.disable(model)
