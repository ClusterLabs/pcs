#!/usr/bin/python

import sys, getopt, os
import usage
import cluster
import resource
import stonith
import prop
import constraint
import utils
import status
import settings

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
            if arg == "--cloneopt":
                new_argv.append("clone")
            elif arg.startswith("--cloneopt="):
                new_argv.append("clone")
                new_argv.append(arg.split('=',1)[1])
            else:
                new_argv.append(arg)
        argv = new_argv

        # we want to support optional arguments for --wait, so if an argument
        # is specified with --wait (ie. --wait=30) then we use them
        waitsecs = "30"
        new_argv = []
        for arg in argv:
            if arg.startswith("--wait="):
                tempsecs = arg.replace("--wait=","")
                if len(tempsecs) > 0 and tempsecs.isdigit():
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

        pcs_long_options = ["local","start","all","clone","master","force","corosync_conf=", "defaults","debug","version","help","fullhelp","off","from=","to=", "name=", "wait", "group=","groups","full","enable","node=","nodesc","transport=", "addr0=","addr1=","bcast0=","bcast1=","mcast0=","mcast1=","mcastport0=","mcastport1=","ttl0=","ttl1=","rrpmode=", "broadcast0", "broadcast1","wait_for_all=","auto_tie_breaker=","last_man_standing=", "last_man_standing_window=","no-default-ops","ipv6","token=", "consensus=", "miss_count_const=", "fail_recv_const=","join=", "disabled"]
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
    elif (command == "status"):
        status.status_cmd(argv)
    elif (command == "config"):
        if "--help" in utils.pcs_options or "-h" in utils.pcs_options or (len(argv) > 0 and argv[0] == "help"):
            usage.main()
        else:
            cluster.print_config()
    else:
        usage.main()
        sys.exit(1)

if __name__ == "__main__":
  main(sys.argv[1:])
