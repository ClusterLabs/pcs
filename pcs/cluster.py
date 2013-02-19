import os
import subprocess
import re
import usage
import urllib2
import utils
import sys
import getpass
import status
import prop
import resource
import constraint
import settings
import socket
import tempfile

pcs_dir = os.path.dirname(os.path.realpath(__file__))
COROSYNC_CONFIG_TEMPLATE = pcs_dir + "/corosync.conf.template"
COROSYNC_CONFIG_FEDORA_TEMPLATE = pcs_dir + "/corosync.conf.fedora.template"
COROSYNC_CONFIG_FILE = settings.corosync_conf_file

def cluster_cmd(argv):
    if len(argv) == 0:
        usage.cluster()
        exit(1)

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.cluster()
    elif (sub_cmd == "setup"):
        corosync_setup(argv)
    elif (sub_cmd == "sync"):
        sync_nodes(utils.getNodesFromCorosyncConf(),utils.getCorosyncConf())
    elif (sub_cmd == "status"):
        status.cluster_status(argv)
    elif (sub_cmd == "pcsd-status"):
        cluster_gui_status(argv)
    elif (sub_cmd == "auth"):
        cluster_auth(argv)
    elif (sub_cmd == "token"):
        cluster_token(argv)
    elif (sub_cmd == "start"):
        if "--all" in utils.pcs_options:
            start_cluster_all()
        else:
            start_cluster(argv)
    elif (sub_cmd == "stop"):
        if "--all" in utils.pcs_options:
            stop_cluster_all()
        else:
            stop_cluster(argv)
    elif (sub_cmd == "force_stop"):
        force_stop_cluster(argv)
    elif (sub_cmd == "standby"):
        node_standby(argv)
    elif (sub_cmd == "unstandby"):
        node_standby(argv, False)
    elif (sub_cmd == "enable"):
        if "--all" in utils.pcs_options:
            enable_cluster_all()
        else:
            enable_cluster(argv)
    elif (sub_cmd == "disable"):
        if "--all" in utils.pcs_options:
            disable_cluster_all()
        else:
            disable_cluster(argv)
    elif (sub_cmd == "cib"):
        get_cib(argv)
    elif (sub_cmd == "push"):
        cluster_push(argv)
    elif (sub_cmd == "edit"):
        cluster_edit(argv)
    elif (sub_cmd == "node"):
        cluster_node(argv)
    elif (sub_cmd == "localnode"):
        cluster_localnode(argv)
    elif (sub_cmd == "corosync"):
        cluster_get_corosync_conf(argv)
    else:
        usage.cluster()
        sys.exit(1)

# Create config and then send it to all of the nodes and start
# corosync & pacemaker on the nodes
# partial_argv is an array of args passed to corosync configure sync_start
def sync_start(partial_argv):
    argv = partial_argv[:]
    nodes = partial_argv[1:]
    config = corosync_setup(argv,True)
    for node in nodes:
        utils.setCorosyncConfig(node,config)
        utils.startCluster(node)

def sync(partial_argv):
    argv = partial_argv[:]
    nodes = partial_argv[1:]
    config = corosync_setup(argv,True)
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
    if "-u" in utils.pcs_options:
        username = utils.pcs_options["-u"]
    else:
        username = None

    if "-p" in utils.pcs_options:
        password = utils.pcs_options["-p"]
    else:
        password = None

    for node in nodes:
        status = utils.checkStatus(node)
        if status[0] == 0:
            print node + ": Already authorized"
        elif status[0] == 3:
            if username == None:
                username = raw_input("Username: ")
            if password == None:
                password = getpass.getpass("Password: ")
            utils.updateToken(node,username,password)
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

# Check and see if pcsd is running on the nodes listed
def check_nodes(nodes):
    for node in nodes:
        status = utils.checkStatus(node)
        if status[0] == 0:
            print node + ": Online"
        elif status[0] == 3:
            print node + ": Unable to authenticate"
        else:
            print node + ": Offline"
    
def corosync_setup(argv,returnConfig=False):
    fedora_config = not utils.is_rhel6()
    if len(argv) < 2:
        usage.cluster()
        exit(1)
    if not returnConfig and "--start" in utils.pcs_options and not "--local" in utils.pcs_options and fedora_config:
        sync_start(argv)
        return
    elif not returnConfig and not "--local" in utils.pcs_options and fedora_config:
        sync(argv)
        return
    else:
        nodes = argv[1:]
        cluster_name = argv[0]

# Verify that all nodes are resolvable otherwise problems may occur
    for node in nodes:
        try:
            socket.gethostbyname(node)
        except socket.error:
            print "Warning: Unable to resolve hostname: %s" % node

    if fedora_config == True:
        f = open(COROSYNC_CONFIG_FEDORA_TEMPLATE, 'r')

        corosync_config = f.read()
        f.close()

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

        utils.setCorosyncConf(corosync_config)
    else:
        output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", "/etc/cluster/cluster.conf", "--createcluster", cluster_name])
        if retval != 0:
            print output
            print "Error creating cluster:", cluster_name
            sys.exit(1)
        for node in nodes:
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--addnode", node])
            if retval != 0:
                print output
                print "Error adding node:", node
                sys.exit(1)

    if "--start" in utils.pcs_options:
        start_cluster([])

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
    if len(argv) > 0:
        for node in argv:
            utils.startCluster(node)
            return

    print "Starting Cluster..."
    if utils.is_rhel6():
        output, retval = utils.run(["service", "cman","start"])
        if retval != 0:
            print output
            print "Error: unable to start cman"
            sys.exit(1)
    else:
        output, retval = utils.run(["service", "corosync","start"])
        if retval != 0:
            print output
            print "Error: unable to start corosync"
            sys.exit(1)
    output, retval = utils.run(["service", "pacemaker", "start"])
    if retval != 0:
        print output
        print "Error: unable to start pacemaker"
        sys.exit(1)

def start_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.startCluster(node)

def stop_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.stopCluster(node)

def node_standby(argv,standby=True):
    if len(argv) == 0:
        usage.cluster()
        sys.exit(1)

    if standby:
        utils.run(["crm_standby", "-v", "on", "-N", argv[0]])
    else:
        utils.run(["crm_standby", "-D", "-N", argv[0]])

def enable_cluster(argv):
    if len(argv) > 0:
        for node in argv:
            utils.enableCluster(node)
            return

    utils.enableServices()

def disable_cluster(argv):
    if len(argv) > 0:
        for node in argv:
            utils.disableCluster(node)
            return

    utils.disableServices()

def enable_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.enableCluster(node)

def disable_cluster_all():
    for node in utils.getNodesFromCorosyncConf():
        utils.disableCluster(node)

def stop_cluster(argv):
    if len(argv) > 0:
        for node in argv:
            utils.stopCluster(node)
            return

    print "Stopping Cluster..."
    output, retval = utils.run(["service", "pacemaker","stop"])
    if retval != 0:
        print output,
        print "Error: unable to stop pacemaker"
        sys.exit(1)
    if utils.is_rhel6():
        output, retval = utils.run(["service", "cman","stop"])
        if retval != 0:
            print output,
            print "Error: unable to stop cman"
            sys.exit(1)
    else:
        output, retval = utils.run(["service", "corosync","stop"])
        if retval != 0:
            print output,
            print "Error: unable to stop corosync"
            sys.exit(1)

def force_stop_cluster(argv):
    daemons = ["crmd", "pengine", "attrd", "lrmd", "stonithd", "cib", "pacemakerd", "corosync"]
    output, retval = utils.run(["killall", "-9"] + daemons)
#    if retval != 0:
#        print "Error: unable to execute killall -9"
#        print output
#        sys.exit(1)

def cluster_push(argv):
    if len(argv) == 2 and argv[0] == "cib":
        filename = argv[1]
    else:
        print argv
        #usage.cluster()
        sys.exit(1)
    output, retval = utils.run(["cibadmin", "--replace", "--xml-file", filename])
    if retval != 0:
        print output,
        sys.exit(1)
    else:
        print "CIB updated"

def cluster_edit(argv):
    if 'EDITOR' in os.environ:
        editor = os.environ['EDITOR']
        tempcib = tempfile.NamedTemporaryFile('w+b',-1,".pcs")
        cib = utils.get_cib()
        tempcib.write(cib)
        tempcib.flush()
        subprocess.call([editor, tempcib.name])

        tempcib.seek(0)
        newcib = "".join(tempcib.readlines())
        if newcib == cib:
            print "CIB not updated, no changes detected"
        else:
            cluster_push(["cib",tempcib.name])

    else:
        print "Error: $EDITOR environment variable is not set"
        sys.exit(1)

def get_cib(argv):
    if len(argv) == 0:
        print utils.get_cib(),
    else:
        filename = argv[0]
        f = open(filename, 'w')
        output = utils.get_cib()
        if output != "":
            f.write(utils.get_cib())
        else:
            print "Error: No data in the CIB"
            sys.exit(1)

def cluster_node(argv):
    if len(argv) != 2:
        usage.cluster();
        sys.exit(1)

    if argv[0] == "add":
        add_node = True
    elif argv[0] == "remove":
        add_node = False
    else:
        usage.cluster();
        sys.exit(1)

    node = argv[1]
    status,output = utils.checkStatus(node)
    if status == 2:
        print "Error: pcsd is not running on %s" % node
        sys.exit(1)
    elif status == 3:
        print "Error: %s is not yet authenticated (try pcs cluster auth %s)" % (node, node)
        sys.exit(1)

    if add_node == True:
        corosync_conf = None
        for my_node in utils.getNodesFromCorosyncConf():
            retval, output = utils.addLocalNode(my_node,node)
            if retval != 0:
                print "Error: unable to add %s on %s - %s" % (node,my_node,output.strip())
            else:
                print "%s: Corosync updated" % my_node
                corosync_conf = output
        if corosync_conf != None:
            utils.setCorosyncConfig(node, corosync_conf)
            utils.startCluster(node)
        else:
            print "Error: Unable to update any nodes"
            sys.exit(1)
    else:
        nodesRemoved = False
        output, retval = utils.run(["crm_node", "--force","-R", node])

        for my_node in utils.getNodesFromCorosyncConf():
            retval, output = utils.removeLocalNode(my_node,node)
            if retval != 0:
                print "Error: unable to remove %s on %s - %s" % (node,my_node,output.strip())
            else:
                if output[0] == 0:
                    print "%s: Corosync updated" % my_node
                    nodesRemoved = True
                else:
                    print "%s: Error executing command occured: %s" % (my_node, "".join(output[1]))
        if nodesRemoved == False:
            print "Error: Unable to update any nodes"
            sys.exit(1)

def cluster_localnode(argv):
    if len(argv) != 2:
        usage.cluster()
        exit(1)
    elif argv[0] == "add":
        node = argv[1]
        success = utils.addNodeToCorosync(node)
        if success:
            print "%s: successfully added!" % node
        else:
            print "Error: unable to add %s" % node
            sys.exit(1)
    elif argv[0] == "remove":
        node = argv[1]
        success = utils.removeNodeFromCorosync(node)
        if success:
            print "%s: successfully removed!" % node
        else:
            print "Error: unable to remove %s" % node
            sys.exit(1)
    else:
        usage.cluster()
        exit(1)

def cluster_get_corosync_conf(argv):
    if len(argv) != 1:
        usage.cluster()
        exit(1)

    node = argv[0]
    retval, output = utils.getCorosyncConfig(node)
    print output

def print_config():
    print "Cluster Name: %s" % utils.getClusterName()
    status.nodes_status(["config"])
    print ""
    print ""
    print "Resources: "
    utils.pcs_options["--all"] = 1
    resource.resource_show([])
    print ""
    constraint.location_show([])
    constraint.order_show([])
    constraint.colocation_show([])
    print ""
    prop.list_property([])
