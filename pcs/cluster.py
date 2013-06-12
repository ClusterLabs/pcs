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
import datetime

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
        usage.cluster(argv)
    elif (sub_cmd == "setup"):
        if "--name" in utils.pcs_options:
            corosync_setup([utils.pcs_options["--name"]] + argv)
        else:
            utils.err("A cluster name (--name <name>) is required to setup a cluster")
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
    elif (sub_cmd == "destroy"):
        cluster_destroy(argv)
    elif (sub_cmd == "verify"):
        cluster_verify(argv)
    elif (sub_cmd == "report"):
        cluster_report(argv)
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
    if len(argv) >= 1:
        utils.err("Must specify only one node")
    elif len(argv) == 0:
        utils.err("Must specify a node to get authorization token from")

    node = argv[0]
    tokens = utils.readTokens()
    if node in tokens:
        print tokens[node]
    else:
        utils.err("No authorization token for: %s" % (node))

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
        status = utils.checkAuthorization(node)
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
    bad_nodes = False
    if len(argv) == 0:
        nodes = utils.getNodesFromCorosyncConf()
        if len(nodes) == 0:
            utils.err("no nodes found in corosync.conf")
        bad_nodes = check_nodes(nodes)
    else:
        bad_nodes = check_nodes(argv)
    if bad_nodes:
        sys.exit(1)

# Check and see if pcsd is running on the nodes listed
def check_nodes(nodes):
    bad_nodes = False
    for node in nodes:
        status = utils.checkAuthorization(node)
        if status[0] == 0:
            print node + ": Online"
        elif status[0] == 3:
            print node + ": Unable to authenticate"
            bad_nodes = True
        else:
            print node + ": Offline"
            bad_nodes = True
    return bad_nodes
    
def corosync_setup(argv,returnConfig=False):
    fedora_config = not utils.is_rhel6()
    failure = False
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
            failure = True

    if failure:
        utils.err("Unable to resolve all hostnames.")

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
            utils.err("error creating cluster: %s" % cluster_name)
        for node in nodes:
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--addnode", node])
            if retval != 0:
                print output
                utils.err("error adding node: %s" % node)

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
        utils.err("unable to determine network address, is interface up?")

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
            utils.err("unable to start cman")
    else:
        output, retval = utils.run(["service", "corosync","start"])
        if retval != 0:
            print output
            utils.err("unable to start corosync")
    output, retval = utils.run(["service", "pacemaker", "start"])
    if retval != 0:
        print output
        utils.err("unable to start pacemaker")

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
        utils.err("unable to stop pacemaker")
    if utils.is_rhel6():
        output, retval = utils.run(["service", "cman","stop"])
        if retval != 0:
            print output,
            utils.err("unable to stop cman")
    else:
        output, retval = utils.run(["service", "corosync","stop"])
        if retval != 0:
            print output,
            utils.err("unable to stop corosync")

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
        usage.cluster()
        sys.exit(1)
    output, retval = utils.run(["cibadmin", "--replace", "--xml-file", filename])
    if retval != 0:
        utils.err("unable to push cib\n" + output)
    else:
        print "CIB updated"

def cluster_edit(argv):
    if 'EDITOR' in os.environ:
        editor = os.environ['EDITOR']
        tempcib = tempfile.NamedTemporaryFile('w+b',-1,".pcs")
        cib = utils.get_cib()
        tempcib.write(cib)
        tempcib.flush()
        try:
            subprocess.call([editor, tempcib.name])
        except OSError:
            utils.err("unable to open file with $EDITOR: " + editor)

        tempcib.seek(0)
        newcib = "".join(tempcib.readlines())
        if newcib == cib:
            print "CIB not updated, no changes detected"
        else:
            cluster_push(["cib",tempcib.name])

    else:
        utils.err("$EDITOR environment variable is not set")

def get_cib(argv):
    if len(argv) == 0:
        print utils.get_cib(),
    else:
        filename = argv[0]
        try:
            f = open(filename, 'w')
            output = utils.get_cib()
            if output != "":
                    f.write(utils.get_cib())
            else:
                utils.err("No data in the CIB")
        except IOError as e:
            utils.err("Unable to write to file '%s', %s" % (filename, e.strerror))

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
    status,output = utils.checkAuthorization(node)
    if status == 2:
        utils.err("pcsd is not running on %s" % node)
    elif status == 3:
        utils.err("%s is not yet authenticated (try pcs cluster auth %s)" % (node, node))

    if add_node == True:
        corosync_conf = None
        for my_node in utils.getNodesFromCorosyncConf():
            retval, output = utils.addLocalNode(my_node,node)
            if retval != 0:
                print >> sys.stderr, "Error: unable to add %s on %s - %s" % (node,my_node,output.strip())
            else:
                print "%s: Corosync updated" % my_node
                corosync_conf = output
        if corosync_conf != None:
            utils.setCorosyncConfig(node, corosync_conf)
            if "--start" in utils.pcs_options:
                utils.startCluster(node)
        else:
            utils.err("Unable to update any nodes")
    else:
        nodesRemoved = False
        stop_cluster([node])
        output, retval = utils.run(["crm_node", "--force","-R", node])

        for my_node in utils.getNodesFromCorosyncConf():
            retval, output = utils.removeLocalNode(my_node,node)
            if retval != 0:
                print >> sys.stderr, "Error: unable to remove %s on %s - %s" % (node,my_node,output.strip())
            else:
                if output[0] == 0:
                    print "%s: Corosync updated" % my_node
                    nodesRemoved = True
                else:
                    print >> sys.stderr, "%s: Error executing command occured: %s" % (my_node, "".join(output[1]))
        if nodesRemoved == False:
            utils.err("Unable to update any nodes")

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
            utils.err("unable to add %s" % node)
    elif argv[0] == "remove":
        node = argv[1]
        success = utils.removeNodeFromCorosync(node)
        if success:
            print "%s: successfully removed!" % node
        else:
            utils.err("unable to remove %s" % node)
    else:
        usage.cluster()
        exit(1)

def cluster_get_corosync_conf(argv):
    if len(argv) != 1:
        usage.cluster()
        exit(1)

    node = argv[0]
    retval, output = utils.getCorosyncConfig(node)
    if retval != 0:
        utils.err(output)
    else:
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
    del utils.pcs_options["--all"]
    prop.list_property([])

# Completely tear down the cluster & remove config files
# Code taken from cluster-clean script in pacemaker
def cluster_destroy(argv):
    print "Killing all active corosync/pacemaker processes"
    os.system("killall -q -9 corosync aisexec heartbeat pacemakerd ccm stonithd ha_logd lrmd crmd pengine attrd pingd mgmtd cib fenced dlm_controld gfs_controld")
    os.system("service pacemaker stop")
    os.system("service corosync stop")

    print "Removing all cluster configuration files"
    os.system("rm /etc/corosync/corosync.conf")
    state_files = ["cib.xml*", "cib-*", "core.*", "hostcache", "cts.*",
            "pe*.bz2","cib.*"]
    for name in state_files:
        os.system("find /var/lib -name '"+name+"' -exec rm -f \{\} \;")

def cluster_verify(argv):
    nofilename = True
    if len(argv) == 1:
        filename = argv.pop(0)
        nofilename = False
    elif len(argv) > 1:
        usage.cluster("verify")
    
    options = []
    if "-V" in utils.pcs_options:
        options.append("-V")
    if nofilename:
        options.append("--live-check")
    else:
        options.append("--xml-file")
        options.append(filename)

    output, retval = utils.run([settings.crm_verify] + options)

    if output != "":
        print output
    return retval

def cluster_report(argv):
    if len(argv) != 1:
        usage.cluster(["report"])

    outfile = argv[0]
    dest_outfile = outfile + ".tar.bz2"
    if os.path.exists(dest_outfile):
        if "--force" not in utils.pcs_options:
            utils.err(dest_outfile + " already exists, use --force to overwrite")
        else:
            try:
                os.remove(dest_outfile)
            except OSError, e:
                utils.err("Unable to remove " + dest_outfile + ": " + e.strerror)
    crm_report_opts = []

    crm_report_opts.append("-f")
    if "--from" in utils.pcs_options:
        crm_report_opts.append(utils.pcs_options["--from"])
        if "--to" in utils.pcs_options:
            crm_report_opts.append("-t")
            crm_report_opts.append(utils.pcs_options["--to"])
    else:
        yesterday = datetime.datetime.now() - datetime.timedelta(1)
        crm_report_opts.append(yesterday.strftime("%Y-%m-%d %H:%M"))

    crm_report_opts.append(outfile)
    output, retval = utils.run([settings.crm_report] + crm_report_opts)
    newoutput = ""
    for line in output.split("\n"):
        if line.startswith("cat:") or line.startswith("grep") or line.startswith("grep") or line.startswith("tail"):
            continue
        if "We will attempt to remove" in line:
            continue
        if "-p option" in line:
            continue
        if "However, doing" in line:
            continue
        if "to diagnose" in line:
            continue
        newoutput = newoutput + line + "\n"
    if retval != 0:
        utils.err(newoutput)
    print newoutput
