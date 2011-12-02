import subprocess
import re
import usage

COROSYNC_CONFIG_TEMPLATE = "corosync.conf.template"
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

def corosync_configure(argv):
    if len(argv) == 3:
        bindnetaddr = argv.pop(0)
        mcastaddr = argv.pop(0)
        mcastport = argv.pop(0)
    elif len(argv) == 0:
        bindnetaddr = get_local_network()
        mcastaddr = "226.94.1.1"
        mcastport = "5405"
    else:
        usage.corosync()
        exit(1)

    f = open(COROSYNC_CONFIG_TEMPLATE, 'r')
    corosync_config = f.read()
    f.close()

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
    network_addr = re.search(r"\n([0-9\.]+)", iproute_out)
    if network_addr:
        return network_addr.group(1)
    else:
        print "ERROR: Unable to determine network address, is interface up?"
        exit(1)
