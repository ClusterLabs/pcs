#!/usr/bin/python

import sys, getopt, os
import usage
import cluster
import resource
import stonith
import prop
import constraint
import acl
import utils
import status
import settings
import config

usefile = False
filename = ""
def main(argv):
    utils.subprocess_setup()
    global filename, usefile
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
                    
        pcs_short_options = "hf:p:u:V"
        pcs_short_options_with_args = []
        for c in pcs_short_options:
            if c == ":":
                pcs_short_options_with_args.append(prev_char)
            prev_char = c

        pcs_long_options = [
            "debug", "version", "help", "fullhelp",
            "force", "autocorrect", "interactive", "autodelete",
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
    except getopt.GetoptError, err:
        print err
        usage.main()
        sys.exit(1)
    argv = real_argv
    for o, a in pcs_options:
        if not o in utils.pcs_options:
            utils.pcs_options[o] = a
        else:
            # If any options are a list then they've been entered twice which isn't valid
            utils.err("%s can only be used once" % o)
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
            print settings.pcs_version
            sys.exit()
        elif o == "--fullhelp":
            usage.full_usage()
            sys.exit()
        elif o == "--wait":
            utils.pcs_options[o] = waitsecs

    if len(argv) == 0:
        usage.main()
        sys.exit(1)

    command = argv.pop(0)
    if (command == "-h" or command == "help"):
        usage.main()
    elif (command == "resource"):
        resource.resource_cmd(argv)
    elif (command == "cluster"):
        cluster.cluster_cmd(argv)
    elif (command == "stonith"):
        stonith.stonith_cmd(argv)
    elif (command == "property"):
        prop.property_cmd(argv)
    elif (command == "constraint"):
        constraint.constraint_cmd(argv)
    elif (command == "acl"):
        acl.acl_cmd(argv)
    elif (command == "status"):
        status.status_cmd(argv)
    elif (command == "config"):
        config.config_cmd(argv)
    else:
        usage.main()
        sys.exit(1)

if __name__ == "__main__":
  main(sys.argv[1:])
