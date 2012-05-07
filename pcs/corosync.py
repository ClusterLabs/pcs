import os
import subprocess
import re
import usage
import urllib2
import utils

pcs_dir = os.path.dirname(os.path.realpath(__file__))
COROSYNC_CONFIG_TEMPLATE = pcs_dir + "/corosync.conf.template"
COROSYNC_CONFIG_FEDORA_TEMPLATE = pcs_dir + "/corosync.conf.fedora.template"
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
    elif (sub_cmd == "sync"):
        sync_nodes(utils.getNodesFromCorosyncConf(),utils.getCorosyncConf())
    else:
        usage.corosync()

# Create config and then send it to all of the nodes and start
# corosync & pacemaker on the nodes
# partial_argv is an array of args passed to corosync configure sync_start
def sync_start(partial_argv):
    argv = partial_argv[:]
    nodes = partial_argv[1:]
    config = corosync_configure(argv,True)
    for node in nodes:
        utils.setCorosyncConfig(node,config)
        utils.startCluster(node)

def sync(partial_argv):
    argv = partial_argv[:]
    nodes = partial_argv[1:]
    config = corosync_configure(argv,True)
    sync_nodes(nodes,config)

def sync_nodes(nodes,config):
    for node in nodes:
        utils.setCorosyncConfig(node,config)
    
def corosync_configure(argv,returnConfig=False):
    fedora_config = True
    if len(argv) > 1:
        nodes = argv[1:]
        cluster_name = argv[0]
    elif argv[0] == "sync" and len(argv) > 2:
        sync(argv[1:])
        return
    elif argv[0] == "sync_start" and len(argv) > 2:
        sync_start(argv[1:])
        return
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
        corosync_config = corosync_config.replace("@@cluster_name",cluster_name)

    if returnConfig:
        return corosync_config

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
