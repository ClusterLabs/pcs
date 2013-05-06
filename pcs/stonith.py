import sys
import resource
#import sys
#import xml.dom.minidom
#from xml.dom.minidom import getDOMImplementation
from xml.dom.minidom import parseString
import usage
import utils
import re
import glob
import os

def stonith_cmd(argv):
    if len(argv) == 0:
        argv = ["show"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.stonith(argv)
    elif (sub_cmd == "list"):
        stonith_list_available(argv)
    elif (sub_cmd == "describe"):
        if len(argv) == 1:
            stonith_list_options(argv[0])
        else:
            usage.stonith()
            sys.exit(1)
    elif (sub_cmd == "create"):
        if len(argv) < 2:
            usage.stonith()
            sys.exit(1)
        stn_id = argv.pop(0)
        stn_type = "stonith:"+argv.pop(0)
        st_values = []
        op_values = []
        op_args = False
        for arg in argv:
            if op_args:
                op_values.append(arg)
            else:
                if arg == "op":
                    op_args = True
                else:
                    st_values.append(arg)
        
        resource.resource_create(stn_id, stn_type, st_values, op_values)
    elif (sub_cmd == "update"):
        stn_id = argv.pop(0)
        resource.resource_update(stn_id,argv)
    elif (sub_cmd == "delete"):
        if len(argv) > 0:
            stn_id = argv.pop(0)
            resource.resource_remove(stn_id)
        else:
            usage.stonith()
            sys.exit(1)
    elif (sub_cmd == "show"):
        resource.resource_show(argv, True)
    elif (sub_cmd == "fence"):
        stonith_fence(argv)
    elif (sub_cmd == "confirm"):
        stonith_confirm(argv)
    else:
        usage.stonith()
        sys.exit(1)

def stonith_list_available(argv):
    if len(argv) != 0:
        filter_string = argv[0]
    else:
        filter_string = ""

    bad_fence_devices = ["kdump_send", "legacy", "na", "nss_wrapper",
            "pcmk", "vmware_helper", "ack_manual", "virtd"]
    fence_devices = sorted(glob.glob(utils.fence_bin + "fence_*"))
    for bfd in bad_fence_devices:
        try:
            fence_devices.remove(utils.fence_bin + "fence_"+bfd)
        except ValueError:
            continue

    for fd in fence_devices:
        if fd.count(filter_string) == 0:
            continue
        metadata = utils.get_stonith_metadata(fd)
        if metadata == False:
            print >> sys.stderr, "Error: no metadata for %s" % fd
            continue
        fd = fd[10:]
        try:
            dom = parseString(metadata)
        except Exception:
            print >> sys.stderr, "Error: unable to parse metadata for fence agent: %s" % (fd)
            continue
        ra = dom.documentElement
        shortdesc = ra.getAttribute("shortdesc")

        sd = ""
        if len(shortdesc) > 0:
            sd = " - " +  resource.format_desc(fd.__len__() + 3, shortdesc)
        print fd + sd

def stonith_list_options(stonith_agent):
    metadata = utils.get_stonith_metadata(utils.fence_bin + stonith_agent)
    if not metadata:
        utils.err("unable to get metadata for %s" % stonith_agent)
    print "Stonith options for: %s" % stonith_agent
    dom = parseString(metadata)
    params = dom.documentElement.getElementsByTagName("parameter")
    for param in params:
        name = param.getAttribute("name")
        if param.getAttribute("required") == "1":
            name += " (required)"
        desc = param.getElementsByTagName("shortdesc")[0].firstChild.nodeValue.strip().replace("\n", "")
        indent = name.__len__() + 4
        desc = resource.format_desc(indent, desc)
        print "  " + name + ": " + desc

def stonith_fence(argv):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to fence")

    node = argv.pop(0)
    if "--off" in utils.pcs_options:
        args = ["stonith_admin", "-F", node]
    else:
        args = ["stonith_admin", "-B", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to fence '%s'\n" % node + output)
    else:
        print "Node: %s fenced" % node

def stonith_confirm(argv):
    if len(argv) != 1:
        utils.err("must specify one (and only one) node to confirm fenced")

    node = argv.pop(0)
    args = ["stonith_admin", "-C", node]
    output, retval = utils.run(args)

    if retval != 0:
        utils.err("unable to confirm fencing of node '%s'\n" % node + output)
    else:
        print "Node: %s confirmed fenced" % node
