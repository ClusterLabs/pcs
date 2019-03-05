import getopt
import os
import sys
import logging

from pcs import (
    settings,
    usage,
    utils,
)

from pcs.cli.common import (
    capabilities,
    completion,
    errors,
    parse_args,
    routing,
)
from pcs.cli.routing import (
    acl,
    alert,
    booth,
    client,
    cluster,
    config,
    constraint,
    host,
    node,
    pcsd,
    prop,
    qdevice,
    quorum,
    resource,
    status,
    stonith,
)
from pcs.lib.errors import LibraryError


def non_root_run(argv_cmd):
    """
    This function will run commands which has to be run as root for users which
    are not root. If it required to run such command as root it will do that by
    sending it to the local pcsd and then it will exit.
    """
    # specific commands need to be run under root account, pass them to pcsd
    # don't forget to allow each command in pcsd.rb in "post /run_pcs do"
    root_command_list = [
        ['cluster', 'auth', '...'],
        ['cluster', 'corosync', '...'],
        ['cluster', 'destroy', '...'],
        ['cluster', 'disable', '...'],
        ['cluster', 'enable', '...'],
        ['cluster', 'node', '...'],
        ['cluster', 'pcsd-status', '...'],
        ['cluster', 'start', '...'],
        ['cluster', 'stop', '...'],
        ['cluster', 'sync', '...'],
        # ['config', 'restore', '...'], # handled in config.config_restore
        ['host', 'auth', '...'],
        ['host', 'deauth', '...'],
        ['pcsd', 'deauth', '...'],
        ['pcsd', 'sync-certificates'],
        ["quorum", "device", "status", "..."],
        ["quorum", "status", "..."],
        ['status', 'corosync', '...'],
        ['status', 'quorum', '...'],
        ['status', 'pcsd', '...'],
    ]
    orig_argv = argv_cmd[:]
    for root_cmd in root_command_list:
        if (
            (argv_cmd == root_cmd)
            or
            (
                root_cmd[-1] == "..."
                and
                argv_cmd[:len(root_cmd)-1] == root_cmd[:-1]
            )
        ):
            # handle interactivity of 'pcs cluster auth'
            if argv_cmd[0:2] in [["cluster", "auth"], ["host", "auth"]]:
                if "-u" not in utils.pcs_options:
                    username = utils.get_terminal_input('Username: ')
                    orig_argv.extend(["-u", username])
                if "-p" not in utils.pcs_options:
                    password = utils.get_terminal_password()
                    orig_argv.extend(["-p", password])

            # call the local pcsd
            err_msgs, exitcode, std_out, std_err = utils.call_local_pcsd(
                orig_argv
            )
            if err_msgs:
                for msg in err_msgs:
                    utils.err(msg, False)
                sys.exit(1)
            if std_out.strip():
                print(std_out)
            if std_err.strip():
                sys.stderr.write(std_err)
            sys.exit(exitcode)

logging.basicConfig()
usefile = False
filename = ""
def main(argv=None):
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements, global-statement
    if completion.has_applicable_environment(os.environ):
        print(completion.make_suggestions(
            os.environ,
            usage.generate_completion_tree_from_usage()
        ))
        sys.exit()

    argv = argv if argv else sys.argv[1:]
    utils.subprocess_setup()
    global filename, usefile
    utils.pcs_options = {}

    # we want to support optional arguments for --wait, so if an argument
    # is specified with --wait (ie. --wait=30) then we use them
    waitsecs = None
    new_argv = []
    for arg in argv:
        if arg.startswith("--wait="):
            tempsecs = arg.replace("--wait=", "")
            if tempsecs:
                waitsecs = tempsecs
                arg = "--wait"
        new_argv.append(arg)
    argv = new_argv

    try:
        pcs_options, dummy_argv = getopt.gnu_getopt(
            parse_args.filter_out_non_option_negative_numbers(argv),
            parse_args.PCS_SHORT_OPTIONS,
            parse_args.PCS_LONG_OPTIONS,
        )
    except getopt.GetoptError as err:
        print(err)
        usage.main()
        sys.exit(1)
    argv = parse_args.filter_out_options(argv)

    full = False
    for option, dummy_value in pcs_options:
        if option == "--full":
            full = True
            break

    for opt, val in pcs_options:
        if not opt in utils.pcs_options:
            utils.pcs_options[opt] = val
        else:
            # If any options are a list then they've been entered twice which
            # isn't valid
            utils.err("%s can only be used once" % opt)

        if opt in ("-h", "--help"):
            if  not argv:
                usage.main()
                sys.exit()
            else:
                argv = [argv[0], "help"] + argv[1:]
        elif opt == "-f":
            usefile = True
            filename = val
            utils.usefile = usefile
            utils.filename = filename
        elif opt == "--corosync_conf":
            settings.corosync_conf_file = val
        elif opt == "--version":
            print(settings.pcs_version)
            if full:
                print(" ".join(
                    sorted([
                        feat["id"]
                        for feat in capabilities.get_pcs_capabilities()
                    ])
                ))
            sys.exit()
        elif opt == "--fullhelp":
            usage.full_usage()
            sys.exit()
        elif opt == "--wait":
            utils.pcs_options[opt] = waitsecs
        elif opt == "--request-timeout":
            request_timeout_valid = False
            try:
                timeout = int(val)
                if timeout > 0:
                    utils.pcs_options[opt] = timeout
                    request_timeout_valid = True
            except ValueError:
                pass
            if not request_timeout_valid:
                utils.err(
                    (
                        "'{0}' is not a valid --request-timeout value, use "
                        "a positive integer"
                    ).format(val)
                )

    logger = logging.getLogger("pcs")
    logger.propagate = 0
    logger.handlers = []

    if (os.getuid() != 0) and (argv and argv[0] != "help") and not usefile:
        non_root_run(argv)
    cmd_map = {
        "resource": resource.resource_cmd,
        "cluster": cluster.cluster_cmd,
        "stonith": stonith.stonith_cmd,
        "property": prop.property_cmd,
        "constraint": constraint.constraint_cmd,
        "acl": acl.acl_cmd,
        "status": status.status_cmd,
        "config": config.config_cmd,
        "pcsd": pcsd.pcsd_cmd,
        "node": node.node_cmd,
        "quorum": quorum.quorum_cmd,
        "qdevice": qdevice.qdevice_cmd,
        "alert": alert.alert_cmd,
        "booth": booth.booth_cmd,
        "host": host.host_cmd,
        "client": client.client_cmd,
        "help": lambda lib, argv, modifiers: usage.main(),
    }
    try:
        routing.create_router(cmd_map, [])(
            utils.get_library_wrapper(), argv, utils.get_input_modifiers()
        )
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except errors.CmdLineInputError:
        if argv and argv[0] in cmd_map:
            usage.show(argv[0], [])
        else:
            usage.main()
        sys.exit(1)
