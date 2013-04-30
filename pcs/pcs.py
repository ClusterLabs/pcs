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
    global filename, usefile
    utils.pcs_options = {}
    modified_argv = []
    real_argv = []
    try:
        # pull out negative number arguments and add them back after getopt
        prev_arg = ""
        for arg in argv:
            if len(arg) > 0 and arg[0] == "-":
                if arg[1:].isdigit() or arg[1:] == "INFINITY":
                    real_argv.append(arg)
                else:
                    modified_argv.append(arg)
            else:
                if prev_arg != "-f" and prev_arg != "-p" and prev_arg != "-u":
                    real_argv.append(arg)
                modified_argv.append(arg)
            prev_arg = arg

        pcs_options, argv = getopt.gnu_getopt(modified_argv, "hf:p:u:", ["local","start","all","clone","cloneopt=","master","force","corosync_conf=", "defaults","debug"])
    except getopt.GetoptError, err:
        print err
        usage.main()
        sys.exit(1)
    argv = real_argv
    for o, a in pcs_options:
        if not o in utils.pcs_options:
            utils.pcs_options[o] = a
        else:
            if type(utils.pcs_options[o]) is list:
                utils.pcs_options[o].append(a)
            else:
                utils.pcs_options[o] = [utils.pcs_options[o], a]
        if o == "-h":
            if len(argv) == 0:
                usage.main()
                sys.exit()
            else:
                argv = [argv[0], "help"]
        elif o == "-f":
            usefile = True
            filename = a
            utils.usefile = usefile
            utils.filename = filename
        elif o == "--corosync_conf":
            settings.corosync_conf_file = a

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
        cluster.print_config()
    else:
        usage.main()
        sys.exit(1)

if __name__ == "__main__":
  main(sys.argv[1:])
