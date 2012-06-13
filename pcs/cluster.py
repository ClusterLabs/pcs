import os
import subprocess
import re
import usage
import urllib2
import utils
import sys

pcs_dir = os.path.dirname(os.path.realpath(__file__))
COROSYNC_CONFIG_TEMPLATE = pcs_dir + "/corosync.conf.template"
COROSYNC_CONFIG_FEDORA_TEMPLATE = pcs_dir + "/corosync.conf.fedora.template"
COROSYNC_CONFIG_FILE = "/etc/corosync/corosync.conf"

def cluster_cmd(argv):
    if len(argv) == 0:
        usage.cluster()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.cluster()
    elif (sub_cmd == "configure"):
        corosync_configure(argv)
    elif (sub_cmd == "sync"):
        sync_nodes(utils.getNodesFromCorosyncConf(),utils.getCorosyncConf())
    elif (sub_cmd == "gui-status"):
        cluster_gui_status(argv)
    elif (sub_cmd == "auth"):
        cluster_auth(argv)
    elif (sub_cmd == "token"):
        cluster_token(argv)
    elif (sub_cmd == "start"):
        start_cluster(argv)
    elif (sub_cmd == "stop"):
        stop_cluster(argv)
    elif (sub_cmd == "startall"):
        start_cluster_all()
    elif (sub_cmd == "stopall"):
        stop_cluster_all()
    elif (sub_cmd == "cib"):
        get_cib()
    else:
        usage.cluster()

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

def cluster_auth(argv):
    if len(argv) == 0:
        auth_nodes(utils.getNodesFromCorosyncConf())
    else:
        auth_nodes(argv)

def cluster_token(argv):
    if len(argv) != 1:
        print "ERROR: Must specify only one node"
        sys.exit(1)
    node = argv[0]
    tokens = utils.readTokens()
    if node in tokens:
        print tokens[node]
    else:
        print "ERROR: No authorization token for: %s" % (node)
        sys.exit(1)

def auth_nodes(nodes):
    for node in nodes:
        status = utils.checkStatus(node)
        if status[0] == 0:
            print node + ": Already authorized"
        elif status[0] == 3:
            utils.updateToken(node)
            print "%s: Authorized" % (node)
        else:
            print "Unable to communicate with %s" % (node)
            exit(1)


# If no arguments get current cluster node status, otherwise get listed
# nodes status
def cluster_gui_status(argv):
    if len(argv) == 0:
        check_nodes(utils.getNodesFromCorosyncConf())
    else:
        check_nodes(argv)

# Check and see if pcs-gui is running on the nodes listed
def check_nodes(nodes):
    for node in nodes:
        status = utils.checkStatus(node)
        if status[0] == 0:
            print node + ": Online"
        elif status[0] == 3:
            print node + ": Unable to authenticate"
        else:
            print node + ": Offline"
    
def corosync_configure(argv,returnConfig=False):
    fedora_config = True
    if len(argv) == 0:
        usage.cluster()
        exit(1)
    elif argv[0] == "sync" and len(argv) > 2:
        sync(argv[1:])
        return
    elif argv[0] == "sync_start" and len(argv) > 2:
        sync_start(argv[1:])
        return
    elif len(argv) > 1:
        nodes = argv[1:]
        cluster_name = argv[0]
    else:
        usage.cluster()
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

def get_cib():
    output, retval = utils.run(["cibadmin", "-l", "-Q"])
    if retval != 0:
        print "Error: unable to get cib"
        sys.exit(1)
    print output,
