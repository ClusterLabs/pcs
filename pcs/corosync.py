import subprocess
import re
import usage

COROSYNC_CONFIG_TEMPLATE = "corosync.conf.template"
COROSYNC_CONFIG_FEDORA_TEMPLATE = "corosync.conf.fedora.template"
COROSYNC_CONFIG_FILE = "/etc/corosync/corosync.conf"

def corosync_cmd(argv):
    if len(argv) == 0:
        usage.corosync()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.corosync()
    elif (sub_cmd == "configure"):
        corosync_configure(argv)
    else:
        usage.corosync()

def corosync_configure(argv):
    fedora_config = False
    if len(argv) == 0:
        bindnetaddr = get_local_network()
        mcastaddr = "226.94.1.1"
        mcastport = "5405"
    elif argv[0] == "fedora":
        nodes = argv[1:]
        fedora_config = True
    elif len(argv) == 3:
        bindnetaddr = argv.pop(0)
        mcastaddr = argv.pop(0)
        mcastport = argv.pop(0)
    else:
        usage.corosync()
        exit(1)

    if fedora_config == True:
        f = open(COROSYNC_CONFIG_FEDORA_TEMPLATE, 'r')
    else:
        f = open(COROSYNC_CONFIG_TEMPLATE, 'r')

    corosync_config = f.read()
    f.close()

    if fedora_config == True:
        i = 1
        new_nodes_section = ""
        for node in nodes:
            new_nodes_section += "  node {\n"
            new_nodes_section += "        ring0_addr: %s\n" % (node)
            new_nodes_section += "        nodeid: %d\n" % (i)
            new_nodes_section += "       }\n"
            i = i+1

        corosync_config = corosync_config.replace("@@nodes", new_nodes_section)
    else:
        corosync_config = corosync_config.replace("@@bindnetaddr",bindnetaddr)
        corosync_config = corosync_config.replace("@@mcastaddr",mcastaddr)
        corosync_config = corosync_config.replace("@@mcastport",mcastport)
    print corosync_config

    try:
        f = open(COROSYNC_CONFIG_FILE,'w')
        f.write(corosync_config)
        f.close()
    except IOError:
        print "ERROR: Unable to write corosync configuration file, try running as root."
        exit(1)


def get_local_network():
    args = ["/sbin/ip", "route"]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    iproute_out = p.stdout.read()
    network_addr = re.search(r"^([0-9\.]+)", iproute_out)
    if network_addr:
        return network_addr.group(1)
    else:
        print "ERROR: Unable to determine network address, is interface up?"
        exit(1)
