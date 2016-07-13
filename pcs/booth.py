from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import usage
from pcs import utils
from pcs.cli.booth import command
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError


def booth_cmd(lib, argv, modifiers):
    """
    routes booth command
    """
    if len(argv) < 1:
        usage.booth()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "config":
            command.config_show(lib, argv_next, modifiers)
        elif sub_cmd == "setup":
            command.config_setup(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "booth", sub_cmd)
