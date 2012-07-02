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

usefile = False
filename = ""
def main(argv):
    global filename, usefile, pcs_options
    try:
        pcs_options, argv = getopt.getopt(argv, "hf:p")
    except getopt.GetoptError, err:
        usage.main()
        sys.exit(1)

    for o, a in pcs_options:
        if o == "-h":
            usage.main()
            sys.exit()
        elif o == "-f":
            usefile = True
            filename = a
            utils.usefile = usefile
            utils.filename = filename

    if len(argv) == 0:
        usage.main()
        exit(1)

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
    elif (command == "add"):
        argv.insert(0,"create")
        resource.resource_cmd(argv)
    elif (command == "set"):
        argv.insert(0,"set")
        prop.property_cmd(argv)
    else:
        usage.main()

if __name__ == "__main__":
  main(sys.argv[1:])
