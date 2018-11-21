from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs import settings, utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError


def client_cmd(lib, argv, modifiers):
    if not argv:
        utils.exit_on_cmdline_input_errror(None, "client", "")

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "local-auth":
            local_auth_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "client", sub_cmd)


def local_auth_cmd(lib, argv, modifiers):
    if len(argv) > 1:
        raise CmdLineInputError()
    port = argv[0] if argv else settings.pcsd_default_port
    username, password = utils.get_user_and_pass()
    utils.auth_nodes_do(
        {"localhost": port}, username, password, force=True, local=True
    )
