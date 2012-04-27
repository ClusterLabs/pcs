#!/usr/bin/python

import sys, getopt, os
import usage
import corosync
import resource
import stonith
import prop
import constraint
import utils
import status

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
    elif (command == "start"):
        start_cluster(argv)
    elif (command == "stop"):
        stop_cluster(argv)
    elif (command == "startall"):
        start_cluster_all()
    elif (command == "stopall"):
        stop_cluster_all()
    else:
        usage.main()

def start_cluster(argv):
    print "Starting Cluster"
    output, retval = utils.run(["systemctl", "start","corosync.service"])
    print output
    if retval != 0:
        print "Error: unable to start corosync"
        sys.exit(1)
    output, retval = utils.run(["systemctl", "start", "pacemaker.service"])
    print output
    if retval != 0:
        print "Error: unable to start pacemaker"
        sys.exit(1)

def start_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.startCluster(node)

def stop_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.stopCluster(node)

def stop_cluster(argv):
    print "Stopping Cluster"
    output, retval = utils.run(["systemctl", "stop","pacemaker.service"])
    print output
    if retval != 0:
        print "Error: unable to stop pacemaker"
        sys.exit(1)
    output, retval = utils.run(["systemctl", "stop","corosync.service"])
    print output
    if retval != 0:
        print "Error: unable to stop corosync"
        sys.exit(1)

if __name__ == "__main__":
  main(sys.argv[1:])
