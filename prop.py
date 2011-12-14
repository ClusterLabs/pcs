import sys
import usage
import utils

def property_cmd(argv):
    if len(argv) == 0:
        usage.property()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.property()
    elif (sub_cmd == "set"):
        set_property(argv)
    else:
        usage.property()
        sys.exit(1)

def set_property(argv):
    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            print "Invalid Property: " + arg
            continue
        utils.set_cib_property(args[0],args[1])

