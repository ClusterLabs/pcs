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
import stonith
import constraint
import settings
import socket
import tempfile
import datetime
import threading
import commands

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
        print ""
        print "PCSD Status:"
        cluster_gui_status([],True)
    elif (sub_cmd == "pcsd-status"):
        cluster_gui_status(argv)
    elif (sub_cmd == "certkey"):
        cluster_certkey(argv)
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
    elif (sub_cmd == "kill"):
        kill_cluster(argv)
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
    elif (sub_cmd == "remote-node"):
        cluster_remote_node(argv)
    elif (sub_cmd == "cib"):
        get_cib(argv)
    elif (sub_cmd == "cib-push"):
        cluster_push(argv)
    elif (sub_cmd == "edit"):
        cluster_edit(argv)
    elif (sub_cmd == "node"):
        cluster_node(argv)
    elif (sub_cmd == "localnode"):
        cluster_localnode(argv)
    elif (sub_cmd == "uidgid"):
        cluster_uidgid(argv)
    elif (sub_cmd == "corosync"):
        cluster_get_corosync_conf(argv)
    elif (sub_cmd == "reload"):
        cluster_reload(argv)
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
    if len(argv) > 1:
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
        if status[0] == 3 or "--force" in utils.pcs_options:
            if username == None:
                sys.stdout.write('Username: ')
                sys.stdout.flush()
                username = raw_input("")
            if password == None:
                if sys.stdout.isatty():
                    password = getpass.getpass("Password: ")
                else:
                    sys.stdout.write('Password: ')
                    sys.stdout.flush()
                    password = raw_input("")
            utils.updateToken(node,nodes,username,password)
            print "%s: Authorized" % (node)
        elif status[0] == 0:
            print node + ": Already authorized"
        else:
            utils.err("Unable to communicate with %s" % (node))


# If no arguments get current cluster node status, otherwise get listed
# nodes status
def cluster_gui_status(argv,dont_exit = False):
    bad_nodes = False
    if len(argv) == 0:
        nodes = utils.getNodesFromCorosyncConf()
        if len(nodes) == 0:
            utils.err("no nodes found in corosync.conf")
        bad_nodes = check_nodes(nodes, "  ")
    else:
        bad_nodes = check_nodes(argv, "  ")
    if bad_nodes and not dont_exit:
        sys.exit(1)

def cluster_certkey(argv):
    if len(argv) != 2:
        usage.cluster(["certkey"])
        exit(1)

    certfile = argv[0]
    keyfile = argv[1]

    try:
        with open(certfile, 'r') as myfile:
            cert = myfile.read()
    except IOError as e:
        utils.err(e)

    try:
        with open(keyfile, 'r') as myfile:
            key = myfile.read()
    except IOError as e:
        utils.err(e)

    if not "--force" in utils.pcs_options and (os.path.exists(settings.pcsd_cert_location) or os.path.exists(settings.pcsd_key_location)):
        utils.err("certificate and/or key already exists, your must use --force to overwrite")

    try:
        try:
            os.chmod(settings.pcsd_cert_location, 0700)
        except OSError: # If the file doesn't exist, we don't care
            pass

        try:
            os.chmod(settings.pcsd_key_location, 0700)
        except OSError: # If the file doesn't exist, we don't care
            pass

        with os.fdopen(os.open(settings.pcsd_cert_location, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0700), 'wb') as myfile:
            myfile.write(cert)

        with os.fdopen(os.open(settings.pcsd_key_location, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0700), 'wb') as myfile:
            myfile.write(key)

    except IOError as e:
        utils.err(e)

    print "Certificate and key updated, you may need to restart pcsd (service pcsd restart) for new settings to take effect"

# Check and see if pcsd is running on the nodes listed
def check_nodes(nodes, prefix = ""):
    bad_nodes = False
    for node in nodes:
        status = utils.checkAuthorization(node)
        if status[0] == 0:
            print prefix + node + ": Online"
        elif status[0] == 3:
            print prefix + node + ": Unable to authenticate"
            bad_nodes = True
        else:
            print prefix + node + ": Offline"
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
        if "--enable" in utils.pcs_options:
            enable_cluster(argv[1:])
        return
    elif not returnConfig and not "--local" in utils.pcs_options and fedora_config:
        sync(argv)
        if "--enable" in utils.pcs_options:
            enable_cluster(argv[1:])
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

        two_node_section = ""
        if len(nodes) == 2:
            two_node_section = "two_node: 1"

        corosync_config = corosync_config.replace("@@nodes", new_nodes_section)
        corosync_config = corosync_config.replace("@@cluster_name",cluster_name)
        corosync_config = corosync_config.replace("@@two_node",two_node_section)
        if returnConfig:
            return corosync_config

        utils.setCorosyncConf(corosync_config)
    else:
        if os.path.exists("/etc/cluster/cluster.conf") and not "--force" in utils.pcs_options:
            print "Error: /etc/cluster/cluster.conf already exists, use --force to overwrite"
            sys.exit(1)
        output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", "/etc/cluster/cluster.conf", "--createcluster", cluster_name])
        if retval != 0:
            print output
            utils.err("error creating cluster: %s" % cluster_name)
        output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", "/etc/cluster/cluster.conf", "--addfencedev", "pcmk-redirect", "agent=fence_pcmk"])
        if retval != 0:
            print output
            utils.err("error creating fence dev: %s" % cluster_name)

        if len(nodes) == 2:
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--setcman", "two_node=1", "expected_votes=1"])
            if retval != 0:
                print output
                utils.err("error adding node: %s" % node)

        for node in nodes:
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--addnode", node])
            if retval != 0:
                print output
                utils.err("error adding node: %s" % node)
            output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", "/etc/cluster/cluster.conf", "--addmethod", "pcmk-method", node])
            if retval != 0:
                print output
                utils.err("error adding fence method: %s" % node)
            output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", "/etc/cluster/cluster.conf", "--addfenceinst", "pcmk-redirect", node, "pcmk-method", "port="+node])
            if retval != 0:
                print output
                utils.err("error adding fence instance: %s" % node)

    if "--start" in utils.pcs_options:
        start_cluster([])
    if "--enable" in utils.pcs_options:
        enable_cluster([])

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
        failure = False
        errors = ""
        for node in argv:
            (retval, err) =  utils.startCluster(node)
            if retval != 0:
                failure = True
                errors = errors + err+"\n"
        if failure:
            utils.err("unable to start all nodes\n" + errors.rstrip())
        return

    print "Starting Cluster..."
    if utils.is_rhel6():
#   Verify that CMAN_QUORUM_TIMEOUT is set, if not, then we set it to 0
        retval, output = commands.getstatusoutput('source /etc/sysconfig/cman ; [ -z "$CMAN_QUORUM_TIMEOUT" ]')
        if retval == 0:
            with open("/etc/sysconfig/cman", "a") as cman_conf_file:
                cman_conf_file.write("\nCMAN_QUORUM_TIMEOUT=0\n")

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
    threads = {}
    for node in utils.getNodesFromCorosyncConf():
        threads[node] = StartClusterThread(node)
        threads[node].start()

    for thread in threads.values():
        thread.join()

def stop_cluster_all():
    threads = {}
    for node in utils.getNodesFromCorosyncConf():
        threads[node] = StopClusterThread(node)
        threads[node].start()

    for thread in threads.values():
        thread.join()

def node_standby(argv,standby=True):
    # If we didn't specify any arguments, use the current node name
    if len(argv) == 0 and "--all" not in utils.pcs_options:
        p = subprocess.Popen(["uname","-n"], stdout=subprocess.PIPE)
        cur_node = p.stdout.readline().rstrip()
        argv = [cur_node]

    nodes = utils.getNodesFromPacemaker()

    if "--all" not in utils.pcs_options:
        nodeFound = False
        for node in nodes:
            if node == argv[0]:
                nodeFound = True
                break

        if not nodeFound:
            utils.err("node '%s' does not appear to exist in configuration" % argv[0])

        if standby:
            utils.run(["crm_standby", "-v", "on", "-N", node])
        else:
            utils.run(["crm_standby", "-D", "-N", node])
    else:
        for node in nodes:
            if standby:
                utils.run(["crm_standby", "-v", "on", "-N", node])
            else:
                utils.run(["crm_standby", "-D", "-N", node])

def enable_cluster(argv):
    if len(argv) > 0:
        failure = False
        errors = ""
        for node in argv:
            (retval, err) = utils.enableCluster(node)
            if retval != 0:
                failure = True
                errors = errors + err+"\n"
        if failure:
            utils.err("unable to enable all nodes\n" + errors.rstrip())
        return

    utils.enableServices()

def disable_cluster(argv):
    if len(argv) > 0:
        failure = False
        errors = ""
        for node in argv:
            (retval, err) = utils.disableCluster(node)
            if retval != 0:
                failure = True
                errors = errors + err+"\n"
        if failure:
            utils.err("unable to disable all nodes\n" + errors.rstrip())
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
        failure = False
        errors = ""
        for node in argv:
            (retval, err) = utils.stopCluster(node)
            if retval != 0:
                failure = True
                errors = errors + err+"\n"
        if failure:
            utils.err("unable to stop all nodes\n" + errors.rstrip())
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

def kill_cluster(argv):
    daemons = ["crmd", "pengine", "attrd", "lrmd", "stonithd", "cib", "pacemakerd", "corosync"]
    output, retval = utils.run(["killall", "-9"] + daemons)
#    if retval != 0:
#        print "Error: unable to execute killall -9"
#        print output
#        sys.exit(1)

def cluster_push(argv):
    if len(argv) == 1:
        filename = argv[0]
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
            cluster_push([tempcib.name])

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
    elif argv[0] in ["remove","delete"]:
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
    elif argv[0] in ["remove","delete"]:
        node = argv[1]
        success = utils.removeNodeFromCorosync(node)
        if success:
            print "%s: successfully removed!" % node
        else:
            utils.err("unable to remove %s" % node)
    else:
        usage.cluster()
        exit(1)

def cluster_uidgid_rhel6(argv, silent_list = False):
    if not os.path.isfile("/etc/cluster/cluster.conf"):
        utils.err("the /etc/cluster/cluster.conf file doesn't exist on this machine, create a cluster before running this command")

    if len(argv) == 0:
        found = False
        output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--lsmisc"])
        if retval != 0:
            utils.err("error running ccs\n" + output)
        lines = output.split('\n')
        for line in lines:
            if line.startswith('UID/GID: '):
                print line
                found = True
        if not found and not silent_list:
            print "No uidgids configured in cluster.conf"
        return
    
    command = argv.pop(0)
    uid=""
    gid=""
    if (command == "add" or command == "rm") and len(argv) > 0:
        for arg in argv:
            if arg.find('=') == -1:
                utils.err("uidgid options must be of the form uid=<uid> gid=<gid>")

            (k,v) = arg.split('=',1)
            if k != "uid" and k != "gid":
                utils.err("%s is not a valid key, you must use uid or gid" %k)

            if k == "uid":
                uid = v
            if k == "gid":
                gid = v
        if uid == "" and gid == "":
            utils.err("you must set either uid or gid")

        if command == "add":
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--setuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to add uidgid\n" + output.rstrip())
        elif command == "rm":
            output, retval = utils.run(["/usr/sbin/ccs", "-f", "/etc/cluster/cluster.conf", "--rmuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to remove uidgid\n" + output.rstrip())
         
    else:
        usage.cluster(["uidgid"])
        exit(1)

def cluster_uidgid(argv, silent_list = False):
    if utils.is_rhel6():
        cluster_uidgid_rhel6(argv, silent_list)
        return

    if len(argv) == 0:
        found = False
        uid_gid_files = os.listdir(settings.corosync_uidgid_dir)
        for ug_file in uid_gid_files:
            uid_gid_dict = utils.read_uid_gid_file(ug_file)
            if "uid" in uid_gid_dict or "gid" in uid_gid_dict:
                line = "UID/GID: uid="
                if "uid" in uid_gid_dict:
                    line += uid_gid_dict["uid"]
                line += " gid="
                if "gid" in uid_gid_dict:
                    line += uid_gid_dict["gid"]

                print line
                found = True
        if not found and not silent_list:
            print "No uidgids configured in cluster.conf"
        return

    command = argv.pop(0)
    uid=""
    gid=""

    if (command == "add" or command == "rm") and len(argv) > 0:
        for arg in argv:
            if arg.find('=') == -1:
                utils.err("uidgid options must be of the form uid=<uid> gid=<gid>")

            (k,v) = arg.split('=',1)
            if k != "uid" and k != "gid":
                utils.err("%s is not a valid key, you must use uid or gid" %k)

            if k == "uid":
                uid = v
            if k == "gid":
                gid = v
        if uid == "" and gid == "":
            utils.err("you must set either uid or gid")

        if command == "add":
            utils.write_uid_gid_file(uid,gid)
        elif command == "rm":
            retval = utils.remove_uid_gid_file(uid,gid)
            if retval == False:
                utils.err("no uidgid files with uid=%s and gid=%s found" % (uid,gid))
         
    else:
        usage.cluster(["uidgid"])
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

def cluster_reload(argv):
    if len(argv) != 1 or argv[0] != "corosync":
        usage.cluster(["reload"])
        exit(1)

    output, retval = utils.reloadCorosync()
    if retval != 0 or "invalid option" in output:
        utils.err(output.rstrip())
    print "Corosync reloaded"

def print_config():
    print "Cluster Name: %s" % utils.getClusterName()
    status.nodes_status(["config"])
    print ""
    print ""
    print "Resources: "
    utils.pcs_options["--all"] = 1
    utils.pcs_options["--full"] = 1
    resource.resource_show([])
    print ""
    print "Stonith Devices: "
    resource.resource_show([], True)
    print "Fencing Levels: "
    print ""
    stonith.stonith_level_show()
    constraint.location_show([])
    constraint.order_show([])
    constraint.colocation_show([])
    print ""
    del utils.pcs_options["--all"]
    prop.list_property([])
    cluster_uidgid([], True)

# Completely tear down the cluster & remove config files
# Code taken from cluster-clean script in pacemaker
def cluster_destroy(argv):
    if "--all" in utils.pcs_options:
        threads = {}
        for node in utils.getNodesFromCorosyncConf():
            threads[node] = DestroyClusterThread(node)
            threads[node].start()

        for thread in threads.values():
            thread.join()
    else:
        print "Shutting down pacemaker/corosync services..."
        print os.system("service pacemaker stop")
        print os.system("service corosync stop")
        print "Killing any remaining services..."
        os.system("killall -q -9 corosync aisexec heartbeat pacemakerd ccm stonithd ha_logd lrmd crmd pengine attrd pingd mgmtd cib fenced dlm_controld gfs_controld")
        utils.disableServices()

        print "Removing all cluster configuration files..."
        if utils.is_rhel6():
            os.system("rm /etc/cluster/cluster.conf")
        else:
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
    stonith.stonith_level_verify()
    return retval

def cluster_report(argv):
    if len(argv) != 1:
        usage.cluster(["report"])
        sys.exit(1)

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

def cluster_remote_node(argv):
    if len(argv) < 1:
        usage.cluster(["remote-node"])
        sys.exit(1)

    command = argv.pop(0)
    if command == "add":
        if len(argv) < 2:
            usage.cluster(["remote-node"])
            sys.exit(1)
        hostname = argv.pop(0)
        rsc = argv.pop(0)
        if not utils.is_resource(rsc):
            utils.err("unable to find resource '%s'" % rsc)
        resource.resource_update(rsc, ["meta", "remote-node="+hostname] + argv)

    elif command in ["remove","delete"]:
        if len(argv) < 1:
            usage.cluster(["remote-node"])
            sys.exit(1)
        hostname = argv.pop(0)
        dom = utils.get_cib_dom()
        nvpairs = dom.getElementsByTagName("nvpair")
        nvpairs_to_remove = []
        for nvpair in nvpairs:
            if nvpair.getAttribute("name") == "remote-node" and nvpair.getAttribute("value") == hostname:
                for np in nvpair.parentNode.getElementsByTagName("nvpair"):
                    if np.getAttribute("name").startswith("remote-"):
                        nvpairs_to_remove.append(np)

        if len(nvpairs_to_remove) == 0:
            utils.err("unable to remove: cannot find remote-node '%s'" % hostname)

        for nvpair in nvpairs_to_remove[:]:
            nvpair.parentNode.removeChild(nvpair)
        utils.replace_cib_configuration(dom)
    else:
        usage.cluster(["remote-node"])
        sys.exit(1)

class StopClusterThread (threading.Thread):
    def __init__ (self,node):
        self.node = node
        threading.Thread.__init__(self)
        self.output = ""

    def run(self):
        utils.stopCluster(self.node)

class StartClusterThread (threading.Thread):
    def __init__ (self,node):
        self.node = node
        threading.Thread.__init__(self)
        self.output = ""

    def run(self):
        utils.startCluster(self.node)

class DestroyClusterThread (threading.Thread):
    def __init__ (self,node):
        self.node = node
        threading.Thread.__init__(self)
        self.output = ""

    def run(self):
        utils.destroyCluster(self.node)


