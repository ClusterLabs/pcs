from __future__ import (
    absolute_import,
    division,
    print_function,
)

import sys

from pcs import usage
from pcs import utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def host_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        utils.exit_on_cmdline_input_errror(None, "host", "")
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.host([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "deauth":
            deauth_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "host", sub_cmd)

def deauth_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        remove_hosts = utils.read_known_hosts_file().keys()
    else:
        remove_hosts = argv
    output, retval = utils.run_pcsdcli(
        'remove_known_hosts',
        {'host_names': remove_hosts}
    )
    if retval == 0 and output['status'] == 'access_denied':
        utils.err('Access denied')
    if retval == 0 and output['status'] == 'ok' and output['data']:
        failed = False
        # The except statement below catches all exceptions including SystemExit
        # so we cannot instruct utils.err to raise it.
        try:
            if output["data"]["hosts_not_found"]:
                utils.err("Following hosts were not found: '{hosts}'".format(
                    hosts="', '".join(output["data"]["hosts_not_found"])
                ), False)
                failed = True
            if not output['data']['sync_successful']:
                utils.err(
                    "Some nodes had a newer known-hosts than the local node. "
                        + "Local node's known-hosts were updated. "
                        + "Please repeat the action if needed.",
                    False
                )
                failed = True
            if output['data']['sync_nodes_err']:
                utils.err(
                    (
                        "Unable to synchronize and save known-hosts on nodes: {0}. "
                        + "Are they authorized?"
                    ).format(
                        ", ".join(output['data']['sync_nodes_err'])
                    ),
                    False
                )
                failed = True
        except:
            utils.err('Unable to communicate with pcsd')
        if failed:
            sys.exit(1)
        return
    utils.err('Unable to communicate with pcsd')
