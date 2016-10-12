from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import getopt
import os
import sys
import logging
logging.basicConfig()

from pcs import (
    acl,
    booth,
    cluster,
    config,
    constraint,
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

from pcs.cli.common import completion


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
    modified_argv = []
    real_argv = []
    try:
        # we change --cloneopt to "clone" for backwards compatibility
        new_argv = []
        for arg in argv:
            if arg == "--cloneopt" or arg == "--clone":
                new_argv.append("clone")
            elif arg.startswith("--cloneopt="):
                new_argv.append("clone")
                new_argv.append(arg.split('=',1)[1])
            else:
                new_argv.append(arg)
        argv = new_argv

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

        # h = help, f = file,
        # p = password (cluster auth), u = user (cluster auth),
        # V = verbose (cluster verify)
        pcs_short_options = "hf:p:u:V"
        pcs_long_options = [
            "debug", "version", "help", "fullhelp",
            "force", "skip-offline", "autocorrect", "interactive", "autodelete",
            "all", "full", "groups", "local", "wait", "config",
            "start", "enable", "disabled", "off",
            "pacemaker", "corosync",
            "no-default-ops", "defaults", "nodesc",
            "clone", "master", "name=", "group=", "node=",
            "from=", "to=", "after=", "before=",
            "transport=", "rrpmode=", "ipv6",
            "addr0=", "bcast0=", "mcast0=", "mcastport0=", "ttl0=", "broadcast0",
            "addr1=", "bcast1=", "mcast1=", "mcastport1=", "ttl1=", "broadcast1",
            "wait_for_all=", "auto_tie_breaker=", "last_man_standing=",
            "last_man_standing_window=",
            "token=", "token_coefficient=", "consensus=", "join=",
            "miss_count_const=", "fail_recv_const=",
            "corosync_conf=", "cluster_conf=",
            "booth-conf=", "booth-key=",
            "remote", "watchdog=",
            #in pcs status - do not display resorce status on inactive node
            "hide-inactive",
        ]
        # pull out negative number arguments and add them back after getopt
        prev_arg = ""
        for arg in argv:
            if len(arg) > 0 and arg[0] == "-":
                if arg[1:].isdigit() or arg[1:].startswith("INFINITY"):
                    real_argv.append(arg)
                else:
                    modified_argv.append(arg)
            else:
                # If previous argument required an argument, then this arg
                # should not be added back in
                if not prev_arg or (not (prev_arg[0] == "-" and prev_arg[1:] in pcs_short_options) and not (prev_arg[0:2] == "--" and (prev_arg[2:] + "=") in pcs_long_options)):
                    real_argv.append(arg)
                modified_argv.append(arg)
            prev_arg = arg

        pcs_options, argv = getopt.gnu_getopt(modified_argv, pcs_short_options, pcs_long_options)
    except getopt.GetoptError as err:
        print(err)
        usage.main()
        sys.exit(1)
    argv = real_argv
    for o, a in pcs_options:
        if not o in utils.pcs_options:
            if o == "--watchdog":
                a = [a]
            utils.pcs_options[o] = a
        else:
            # If any options are a list then they've been entered twice which isn't valid
            if o != "--watchdog":
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
            sys.exit()
        elif o == "--fullhelp":
            usage.full_usage()
            sys.exit()
        elif o == "--wait":
            utils.pcs_options[o] = waitsecs

    if len(argv) == 0:
        usage.main()
        sys.exit(1)

    # create a dummy logger
    # we do not have a log file for cli (yet), but library requires a logger
    logger = logging.getLogger("old_cli")
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
            utils.get_modificators()
        ),
        "status": status.status_cmd,
        "config": config.config_cmd,
        "pcsd": pcsd.pcsd_cmd,
        "node": node.node_cmd,
        "quorum": lambda argv: quorum.quorum_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modificators()
        ),
        "qdevice": lambda argv: qdevice.qdevice_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modificators()
        ),
        "alert": lambda args: alert.alert_cmd(
            utils.get_library_wrapper(),
            args,
            utils.get_modificators()
        ),
        "booth": lambda argv: booth.booth_cmd(
            utils.get_library_wrapper(),
            argv,
            utils.get_modificators()
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
        ['cluster', 'setup', '...'],
        ['cluster', 'start', '...'],
        ['cluster', 'stop', '...'],
        ['cluster', 'sync', '...'],
        # ['config', 'restore', '...'], # handled in config.config_restore
        ['pcsd', 'sync-certificates'],
        ['status', 'nodes', 'corosync-id'],
        ['status', 'nodes', 'pacemaker-id'],
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
            if argv_cmd[0:2] == ["cluster", "auth"]:
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
