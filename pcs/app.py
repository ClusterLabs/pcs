import getopt
import os
import sys
import logging

from pcs import (
    acl,
    booth,
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
    settings,
    status,
    stonith,
    usage,
    utils,
    alert,
)

from pcs.cli.common import (
    capabilities,
    completion,
    parse_args,
)


logging.basicConfig()
usefile = False
filename = ""
def main(argv=None):
    if completion.has_applicable_environment(os.environ):
        print(completion.make_suggestions(
            os.environ,
            usage.generate_completion_tree_from_usage()
        ))
        sys.exit()

    argv = argv if argv else sys.argv[1:]
    utils.subprocess_setup()
    global filename, usefile
    orig_argv = argv[:]
    utils.pcs_options = {}

    argv = parse_args.upgrade_args(argv)

    # we want to support optional arguments for --wait, so if an argument
    # is specified with --wait (ie. --wait=30) then we use them
    waitsecs = None
    new_argv = []
    for arg in argv:
        if arg.startswith("--wait="):
            tempsecs = arg.replace("--wait=","")
            if len(tempsecs) > 0:
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

    for o, a in pcs_options:
        if not o in utils.pcs_options:
            if o in ["--watchdog", "--device"]:
                a = [a]
            utils.pcs_options[o] = a
        else:
            # If any options are a list then they've been entered twice which isn't valid
            if o not in ["--watchdog", "--device"]:
                utils.err("%s can only be used once" % o)
            else:
                utils.pcs_options[o].append(a)

        if o == "-h" or o == "--help":
            if len(argv) == 0:
                usage.main()
                sys.exit()
            else:
                argv = [argv[0], "help" ] + argv[1:]
        elif o == "-f":
            usefile = True
            filename = a
            utils.usefile = usefile
            utils.filename = filename
        elif o == "--corosync_conf":
            settings.corosync_conf_file = a
        elif o == "--cluster_conf":
            settings.cluster_conf_file = a
        elif o == "--version":
            print(settings.pcs_version)
            if full:
                print(" ".join(
                    sorted([
                        feat["id"]
                        for feat in capabilities.get_pcs_capabilities()
                    ])
                ))
            sys.exit()
        elif o == "--fullhelp":
            usage.full_usage()
            sys.exit()
        elif o == "--wait":
            utils.pcs_options[o] = waitsecs
        elif o == "--request-timeout":
            request_timeout_valid = False
            try:
                timeout = int(a)
                if timeout > 0:
                    utils.pcs_options[o] = timeout
                    request_timeout_valid = True
            except ValueError:
                pass
            if not request_timeout_valid:
                utils.err(
                    (
                        "'{0}' is not a valid --request-timeout value, use "
                        "a positive integer"
                    ).format(a)
                )

    if len(argv) == 0:
        usage.main()
        sys.exit(1)

    # create a dummy logger
    # we do not have a log file for cli (yet), but library requires a logger
    logger = logging.getLogger("pcs")
    logger.propagate = 0
    logger.handlers = []

    command = argv.pop(0)
    if (command == "-h" or command == "help"):
        usage.main()
        return
    cmd_map = {
        "resource": resource.resource_cmd,
        "cluster": cluster.cluster_cmd,
        "stonith": stonith.stonith_cmd,
        "property": prop.property_cmd,
        "constraint": constraint.constraint_cmd,
        "acl": lambda argv: acl.acl_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "status": lambda argv: status.status_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "config": config.config_cmd,
        "pcsd": lambda argv: pcsd.pcsd_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "node": lambda argv: node.node_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "quorum": lambda argv: quorum.quorum_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "qdevice": lambda argv: qdevice.qdevice_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "alert": lambda args: alert.alert_cmd(
            utils.get_library_wrapper(),
            args,
            utils.get_modifiers()
        ),
        "booth": lambda argv: booth.booth_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
        "host": lambda argv: host.host_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modifiers()
        ),
    }
    if command not in cmd_map:
        usage.main()
        sys.exit(1)
    # root can run everything directly, also help can be displayed,
    # working on a local file also do not need to run under root
    if (os.getuid() == 0) or (argv and argv[0] == "help") or usefile:
        cmd_map[command](argv)
        return
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
        ['status', 'pcsd', '...'],
    ]
    argv_cmd = argv[:]
    argv_cmd.insert(0, command)
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
                orig_argv, True
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
            return
    cmd_map[command](argv)
