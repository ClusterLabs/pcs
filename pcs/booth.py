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
from pcs.resource import resource_create, resource_remove, resource_restart


def booth_cmd(lib, argv, modifiers):
    """
    routes booth command
    """
    if len(argv) < 1:
        usage.booth()
        sys.exit(1)

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "help":
            usage.booth(argv)
        elif sub_cmd == "config":
            command.config_show(lib, argv_next, modifiers)
        elif sub_cmd == "setup":
            command.config_setup(lib, argv_next, modifiers)
        elif sub_cmd == "destroy":
            command.config_destroy(lib, argv_next, modifiers)
        elif sub_cmd == "ticket":
            if len(argv_next) < 1:
                raise CmdLineInputError()
            if argv_next[0] == "add":
                command.config_ticket_add(lib, argv_next[1:], modifiers)
            elif argv_next[0] == "remove":
                command.config_ticket_remove(lib, argv_next[1:], modifiers)
            elif argv_next[0] == "grant":
                command.ticket_grant(lib, argv_next[1:], modifiers)
            elif argv_next[0] == "revoke":
                command.ticket_revoke(lib, argv_next[1:], modifiers)
            else:
                raise CmdLineInputError()
        elif sub_cmd == "create":
            command.get_create_in_cluster(resource_create, resource_remove)(
                lib, argv_next, modifiers
            )
        elif sub_cmd == "remove":
            command.get_remove_from_cluster(resource_remove)(
                lib, argv_next, modifiers
            )
        elif sub_cmd == "restart":
            command.get_restart(resource_restart)(lib, argv_next, modifiers)
        elif sub_cmd == "sync":
            command.sync(lib, argv_next, modifiers)
        elif sub_cmd == "pull":
            command.pull(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            command.enable(lib, argv_next, modifiers)
        elif sub_cmd == "disable":
            command.disable(lib, argv_next, modifiers)
        elif sub_cmd == "start":
            command.start(lib, argv_next, modifiers)
        elif sub_cmd == "stop":
            command.stop(lib, argv_next, modifiers)
        elif sub_cmd == "status":
            command.status(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "booth", sub_cmd)
