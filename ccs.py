#!/usr/bin/python

import sys, getopt, os
import usage
import corosync
import resource
import utils

usefile = False
filename = ""
def main(argv):
    global filename, usefile
    try:
        opts, argv = getopt.getopt(argv, "hf:")
    except getopt.GetoptError, err:
        usage.main()
        sys.exit(1)

    for o, a in opts:
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
    elif (command == "corosync"):
        corosync.corosync_cmd(argv)
    else:
        usage.main()


if __name__ == "__main__":
  main(sys.argv[1:])
