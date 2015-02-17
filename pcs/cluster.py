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
import commands
import json
import xml.dom.minidom
import threading

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
    elif (sub_cmd == "token-nodes"):
        cluster_token_nodes(argv)
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
    elif (sub_cmd == "cib-upgrade"):
        cluster_upgrade()
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
    elif (sub_cmd == "quorum"):
        if argv and argv[0] == "unblock":
            cluster_quorum_unblock(argv[1:])
        else:
            usage.cluster(["quorum"])
            sys.exit(1)
    else:
        usage.cluster()
        sys.exit(1)

# Create config and then send it to all of the nodes and start
# corosync & pacemaker on the nodes
# partial_argv is an array of args passed to corosync configure sync_start
def sync_start(partial_argv, nodes):
    argv = partial_argv[:]
    config = corosync_setup(argv,True)
    for node in nodes:
        utils.setCorosyncConfig(node,config)
    print "Starting cluster on nodes: " + ", ".join(nodes) + "..."
    start_cluster_nodes(nodes)

def sync(partial_argv,nodes):
    argv = partial_argv[:]
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

def cluster_token_nodes(argv):
    print "\n".join(sorted(utils.readTokens().keys()))

def auth_nodes(nodes):
    if "-u" in utils.pcs_options:
        username = utils.pcs_options["-u"]
    else:
        username = None

    if "-p" in utils.pcs_options:
        password = utils.pcs_options["-p"]
    else:
        password = None

    set_nodes = set(nodes)
    failed_count = 0
    for node in nodes:
        status = utils.checkAuthorization(node)
        need_auth = status[0] == 3 or "--force" in utils.pcs_options
        mutually_authorized = False
        if status[0] == 0:
            try:
                auth_status = json.loads(status[1])
                if auth_status["success"]:
                    if set_nodes == set(auth_status["node_list"]):
                        mutually_authorized = True
            except ValueError, KeyError:
                pass
        if need_auth or not mutually_authorized:
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
            if not utils.updateToken(node,nodes,username,password):
                failed_count += 1
                continue
            print "%s: Authorized" % (node)
        elif mutually_authorized:
            print node + ": Already authorized"
        else:
            utils.err("Unable to communicate with %s" % (node), False)
            failed_count += 1

    if failed_count > 0:
        sys.exit(failed_count)


# If no arguments get current cluster node status, otherwise get listed
# nodes status
def cluster_gui_status(argv,dont_exit = False):
    bad_nodes = False
    if len(argv) == 0:
        nodes = utils.getNodesFromCorosyncConf()
        if len(nodes) == 0:
            if utils.is_rhel6():
                utils.err("no nodes found in cluster.conf")
            else:
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
    pm_nodes = utils.getPacemakerNodesID(True)
    cs_nodes = utils.getCorosyncNodesID(True)
    for node in nodes:
        status = utils.checkAuthorization(node)

        if node not in pm_nodes.values():
            for n_id, n in cs_nodes.items():
                if node == n and n_id in pm_nodes:
                    real_node_name = pm_nodes[n_id]
                    if real_node_name == "(null)":
                        real_node_name = "*Unknown*"
                    node = real_node_name +  " (" + node + ")"
                    break

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
    primary_nodes = []

    # If node contains a ',' we only care about the first address
    for node in argv[1:]:
        if "," in node:
            primary_nodes.append(node.split(',')[0])
        else:
            primary_nodes.append(node)

    if len(argv) < 2:
        usage.cluster()
        exit(1)

    if not returnConfig and "--start" in utils.pcs_options and not "--local" in utils.pcs_options:# and fedora_config:
        sync_start(argv, primary_nodes)
        if "--enable" in utils.pcs_options:
            enable_cluster(primary_nodes)
        return
    elif not returnConfig and not "--local" in utils.pcs_options:# and fedora_config:
        sync(argv, primary_nodes)
        if "--enable" in utils.pcs_options:
            enable_cluster(primary_nodes)
        return
    else:
        nodes = argv[1:]
        cluster_name = argv[0]

# Verify that all nodes are resolvable otherwise problems may occur
    udpu_rrp = False
    node_addr_list = []
    for node in nodes:
        addr_list = utils.parse_multiring_node(node)
        if addr_list[1]:
            udpu_rrp = True
        node_addr_list.extend(addr_list)
    for node_addr in node_addr_list:
        if node_addr:
            try:
                socket.getaddrinfo(node_addr, None)
            except socket.error:
                print "Warning: Unable to resolve hostname: %s" % node_addr
                failure = True

    if udpu_rrp:
        for node in nodes:
            if "," not in node:
                utils.err("if one node is configured for RRP, all nodes must configured for RRP")

    if failure and "--force" not in utils.pcs_options:
        utils.err("Unable to resolve all hostnames (use --force to override).")

    transport = "udp" if utils.is_rhel6() else "udpu"
    if "--transport" in utils.pcs_options:
        transport = utils.pcs_options["--transport"]
        if (
            transport not in ("udp", "udpu")
            and
            "--force" not in utils.pcs_options
        ):
            utils.err(
                "unknown transport '%s', use --force to override" % transport
            )

    if transport == "udpu" and utils.is_rhel6():
        print("Warning: Using udpu transport on a CMAN cluster, "
            + "cluster restart is required after node add or remove")
    if (
        transport == "udpu"
        and
        ("--addr0" in utils.pcs_options or "--addr1" in utils.pcs_options)
    ):
        utils.err("--addr0 and --addr1 can only be used with --transport=udp")

    rrpmode = None
    if "--rrpmode" in utils.pcs_options or udpu_rrp or "--addr0" in utils.pcs_options:
        rrpmode = "passive"
        if "--rrpmode" in utils.pcs_options:
            rrpmode = utils.pcs_options["--rrpmode"]
        if rrpmode == "active" and "--force" not in utils.pcs_options:
            utils.err("using a RRP mode of 'active' is not supported or tested, use --force to override")
        elif rrpmode != "passive" and "--force" not in utils.pcs_options:
            utils.err("%s is an unknown RRP mode, use --force to override" % rrpmode)

    if fedora_config == True:
        if os.path.exists(settings.corosync_conf_file) and not "--force" in utils.pcs_options:
            utils.err("%s already exists, use --force to overwrite" % settings.corosync_conf_file)
        if not ("--corosync_conf" in utils.pcs_options and "--local" in utils.pcs_options):
            cib_path = os.path.join(settings.cib_dir, "cib.xml")
            if os.path.exists(cib_path) and not "--force" in utils.pcs_options:
                utils.err("%s already exists, use --force to overwrite" % cib_path)
        if "--corosync_conf" not in utils.pcs_options:
            cluster_destroy([])

        f = open(COROSYNC_CONFIG_FEDORA_TEMPLATE, 'r')

        corosync_config = f.read()
        f.close()

        i = 1
        new_nodes_section = ""
        for node in nodes:
            new_nodes_section += "  node {\n"
            if udpu_rrp:
                new_nodes_section += "        ring0_addr: %s\n" % (node.split(",")[0])
                new_nodes_section += "        ring1_addr: %s\n" % (node.split(",")[1])
            else:
                new_nodes_section += "        ring0_addr: %s\n" % (node)
            new_nodes_section += "        nodeid: %d\n" % (i)
            new_nodes_section += "       }\n"
            i = i+1

        two_node_section = ""
        if len(nodes) == 2:
            two_node_section = "two_node: 1"

        quorum_options = ""
        if "--wait_for_all" in utils.pcs_options:
            quorum_options += "wait_for_all: " + utils.pcs_options["--wait_for_all"] + "\n"
        if "--auto_tie_breaker" in utils.pcs_options:
            quorum_options += "auto_tie_breaker: " + utils.pcs_options["--auto_tie_breaker"] + "\n"
        if "--last_man_standing" in utils.pcs_options:
            quorum_options += "last_man_standing: " + utils.pcs_options["--last_man_standing"] + "\n"
        if "--last_man_standing_window" in utils.pcs_options:
            quorum_options += "last_man_standing_window: " + utils.pcs_options["--last_man_standing_window"] + "\n"

        ir = ""

        if rrpmode:
            ir += "rrp_mode: " + rrpmode + "\n"

        if transport == "udp":

            if "--addr0" in utils.pcs_options:
                ir += utils.generate_rrp_corosync_config(0)

                if "--addr1" in utils.pcs_options:
                    ir += utils.generate_rrp_corosync_config(1)
        if "--ipv6" in utils.pcs_options:
            ip_version = "ip_version: ipv6\n"
        else:
            ip_version = ""


        totem_options = ""
        if "--token" in utils.pcs_options:
            totem_options += "token: " + utils.pcs_options["--token"] + "\n"
        if "--token_coefficient" in utils.pcs_options:
            totem_options += "token_coefficient: " + utils.pcs_options["--token_coefficient"] + "\n"
        if "--join" in utils.pcs_options:
            totem_options += "join: " + utils.pcs_options["--join"] + "\n"
        if "--consensus" in utils.pcs_options:
            totem_options += "consensus: " + utils.pcs_options["--consensus"] + "\n"
        if "--miss_count_const" in utils.pcs_options:
            totem_options += "miss_count_const: " + utils.pcs_options["--miss_count_const"] + "\n"
        if "--fail_recv_const" in utils.pcs_options:
            totem_options += "fail_recv_const: " + utils.pcs_options["--fail_recv_const"] + "\n"

        corosync_config = corosync_config.replace("@@nodes", new_nodes_section)
        corosync_config = corosync_config.replace("@@cluster_name",cluster_name)
        corosync_config = corosync_config.replace("@@quorum_options\n",quorum_options)
        corosync_config = corosync_config.replace("@@two_node",two_node_section)
        corosync_config = corosync_config.replace("@@transport",transport)
        corosync_config = corosync_config.replace("@@interfaceandrrpmode\n",ir)
        corosync_config = corosync_config.replace("@@ip_version\n",ip_version)
        corosync_config = corosync_config.replace("@@totem_options\n",totem_options)
        if returnConfig:
            return corosync_config

        utils.setCorosyncConf(corosync_config)
    else:
        broadcast = (
            ("--broadcast0" in utils.pcs_options)
            or
            ("--broadcast1" in utils.pcs_options)
        )
        if broadcast:
            transport = "udpb"
            if "--broadcast0" not in utils.pcs_options:
                print("Warning: Enabling broadcast for ring 0 "
                    + "as CMAN does not support broadcast in only one ring")
            if "--broadcast1" not in utils.pcs_options:
                print("Warning: Enabling broadcast for ring 1 "
                    + "as CMAN does not support broadcast in only one ring")

        cluster_conf_location = settings.cluster_conf_file
        if returnConfig:
            cc_temp = tempfile.NamedTemporaryFile('w+b', -1, ".pcs")
            cluster_conf_location = cc_temp.name

        if os.path.exists(cluster_conf_location) and not "--force" in utils.pcs_options and not returnConfig:
            print "Error: %s already exists, use --force to overwrite" % cluster_conf_location
            sys.exit(1)
        output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", cluster_conf_location, "--createcluster", cluster_name])
        if retval != 0:
            print output
            utils.err("error creating cluster: %s" % cluster_name)
        output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", cluster_conf_location, "--addfencedev", "pcmk-redirect", "agent=fence_pcmk"])
        if retval != 0:
            print output
            utils.err("error creating fence dev: %s" % cluster_name)

        cman_opts = []
        cman_opts.append("transport=" + transport)
        cman_opts.append("broadcast=" + ("yes" if broadcast else "no"))
        if len(nodes) == 2:
            cman_opts.append("two_node=1")
            cman_opts.append("expected_votes=1")
        output, retval = utils.run(
            ["/usr/sbin/ccs", "-f", cluster_conf_location, "--setcman"]
            + cman_opts
        )
        if retval != 0:
            print output
            utils.err("error setting cman options")

        for node in nodes:
            if udpu_rrp:
                node0, node1 = node.split(",")
            elif "--addr1" in utils.pcs_options:
                node0 = node
                node1 = utils.pcs_options["--addr1"]
            else:
                node0 = node
                node1 = None
            output, retval = utils.run(["/usr/sbin/ccs", "-f", cluster_conf_location, "--addnode", node0])
            if retval != 0:
                print output
                utils.err("error adding node: %s" % node0)
            if node1:
                output, retval = utils.run([
                    "/usr/sbin/ccs", "-f", cluster_conf_location,
                    "--addalt", node0, node1
                ])
                if retval != 0:
                    print output
                    utils.err(
                        "error adding alternative address for node: %s" % node0
                    )
            output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", cluster_conf_location, "--addmethod", "pcmk-method", node0])
            if retval != 0:
                print output
                utils.err("error adding fence method: %s" % node0)
            output, retval = utils.run(["/usr/sbin/ccs", "-i", "-f", cluster_conf_location, "--addfenceinst", "pcmk-redirect", node0, "pcmk-method", "port="+node0])
            if retval != 0:
                print output
                utils.err("error adding fence instance: %s" % node0)

        if not broadcast:
            for interface in ("0", "1"):
                if "--addr" + interface not in utils.pcs_options:
                    continue
                mcastaddr = "239.255.1.1" if interface == "0" else "239.255.2.1"
                mcast_options = []
                if "--mcast" + interface in utils.pcs_options:
                    mcastaddr = utils.pcs_options["--mcast" + interface]
                mcast_options.append(mcastaddr)
                if "--mcastport" + interface in utils.pcs_options:
                    mcast_options.append(
                        "port=" + utils.pcs_options["--mcastport" + interface]
                    )
                if "--ttl" + interface in utils.pcs_options:
                    mcast_options.append(
                        "ttl=" + utils.pcs_options["--ttl" + interface]
                    )
                output, retval = utils.run(
                    ["/usr/sbin/ccs", "-f", cluster_conf_location,
                    "--setmulticast" if interface == "0" else "--setaltmulticast"]
                    + mcast_options
                )
                if retval != 0:
                    print output
                    utils.err("error adding ring%s settings" % interface)

        totem_options = []
        if "--token" in utils.pcs_options:
            totem_options.append("token=" + utils.pcs_options["--token"])
        if "--join" in utils.pcs_options:
            totem_options.append("join=" + utils.pcs_options["--join"])
        if "--consensus" in utils.pcs_options:
            totem_options.append(
                "consensus=" + utils.pcs_options["--consensus"]
            )
        if "--miss_count_const" in utils.pcs_options:
            totem_options.append(
                "miss_count_const=" + utils.pcs_options["--miss_count_const"]
            )
        if "--fail_recv_const" in utils.pcs_options:
            totem_options.append(
                "fail_recv_const=" + utils.pcs_options["--fail_recv_const"]
            )
        if rrpmode:
            totem_options.append("rrp_mode=" + rrpmode)
        if totem_options:
            output, retval = utils.run(
                ["/usr/sbin/ccs", "-f", cluster_conf_location, "--settotem"]
                + totem_options
            )
            if retval != 0:
                print output
                utils.err("error setting totem options")

        if "--wait_for_all" in utils.pcs_options:
            print "Warning: --wait_for_all"\
                " ignored as it is not supported on CMAN clusters"
        if "--auto_tie_breaker" in utils.pcs_options:
            print "Warning: --auto_tie_breaker"\
                " ignored as it is not supported on CMAN clusters"
        if "--last_man_standing" in utils.pcs_options:
            print "Warning: --last_man_standing"\
                " ignored as it is not supported on CMAN clusters"
        if "--last_man_standing_window" in utils.pcs_options:
            print "Warning: --last_man_standing_window"\
                " ignored as it is not supported on CMAN clusters"
        if "--token_coefficient" in utils.pcs_options:
            print "Warning: --token_coefficient"\
                " ignored as it is not supported on CMAN clusters"
        if "--ipv6" in utils.pcs_options:
            print "Warning: --ipv6"\
                " ignored as it is not supported on CMAN clusters"

        if returnConfig:
            cc_temp.seek(0)
            cluster_conf_data = cc_temp.read()
            cc_temp.close()
            return cluster_conf_data


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
        start_cluster_nodes(argv)
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
    start_cluster_nodes(utils.getNodesFromCorosyncConf())

def start_cluster_nodes(nodes):
    threads = dict()
    for node in nodes:
        threads[node] = NodeStartThread(node)
    error_list = utils.run_node_threads(threads)
    if error_list:
        utils.err("unable to start all nodes\n" + "\n".join(error_list))

def stop_cluster_all():
    stop_cluster_nodes(utils.getNodesFromCorosyncConf())

def stop_cluster_nodes(nodes):
    all_nodes = utils.getNodesFromCorosyncConf()
    unknown_nodes = set(nodes) - set(all_nodes)
    if unknown_nodes:
        utils.err(
            "nodes '%s' do not appear to exist in configuration"
            % "', '".join(unknown_nodes)
        )

    stopping_all = set(nodes) >= set(all_nodes)
    if not "--force" in utils.pcs_options and not stopping_all:
        error_list = []
        for node in nodes:
            retval, data = utils.get_remote_quorumtool_output(node)
            if retval != 0:
                error_list.append(node + ": " + data)
                continue
            # we are sure whether we are on cman cluster or not because only
            # nodes from a local cluster can be stopped (see nodes validation
            # above)
            if utils.is_rhel6():
                quorum_info = utils.parse_cman_quorum_info(data)
            else:
                quorum_info = utils.parse_quorumtool_output(data)
            if quorum_info:
                if not quorum_info["quorate"]:
                    continue
                if utils.is_node_stop_cause_quorum_loss(
                    quorum_info, local=False, node_list=nodes
                ):
                    utils.err(
                        "Stopping the node(s) will cause a loss of the quorum"
                        + ", use --force to override"
                    )
                else:
                    # We have the info, no need to print errors
                    error_list = []
                    break
            if not utils.is_node_offline_by_quorumtool_output(data):
                error_list.append("Unable to get quorum status")
            # else the node seems to be stopped already
        if error_list:
            utils.err(
                "Unable to determine whether stopping the nodes will cause "
                + "a loss of the quorum, use --force to override\n"
                + "\n".join(error_list)
            )

    threads = dict()
    for node in nodes:
        threads[node] = NodeStopPacemakerThread(node)
    error_list = utils.run_node_threads(threads)
    if error_list:
        utils.err("unable to stop all nodes\n" + "\n".join(error_list))

    threads = dict()
    for node in nodes:
        threads[node] = NodeStopCorosyncThread(node)
    error_list = utils.run_node_threads(threads)
    if error_list:
        utils.err("unable to stop all nodes\n" + "\n".join(error_list))

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
        enable_cluster_nodes(argv)
        return

    utils.enableServices()

def disable_cluster(argv):
    if len(argv) > 0:
        disable_cluster_nodes(argv)
        return

    utils.disableServices()

def enable_cluster_all():
    enable_cluster_nodes(utils.getNodesFromCorosyncConf())

def disable_cluster_all():
    disable_cluster_nodes(utils.getNodesFromCorosyncConf())

def enable_cluster_nodes(nodes):
    error_list = utils.map_for_error_list(utils.enableCluster, nodes)
    if len(error_list) > 0:
        utils.err("unable to enable all nodes\n" + "\n".join(error_list))

def disable_cluster_nodes(nodes):
    error_list = utils.map_for_error_list(utils.disableCluster, nodes)
    if len(error_list) > 0:
        utils.err("unable to disable all nodes\n" + "\n".join(error_list))

def destroy_cluster(argv):
    if len(argv) > 0:
        # stop pacemaker and resources while cluster is still quorate
        threads = dict()
        for node in argv:
            threads[node] = NodeStopPacemakerThread(node)
        error_list = utils.run_node_threads(threads)
        # proceed with destroy regardless of errors
        # destroy will stop any remaining cluster daemons
        threads = dict()
        for node in argv:
            threads[node] = NodeDestroyThread(node)
        error_list = utils.run_node_threads(threads)
        if error_list:
            utils.err("unable to destroy cluster\n" + "\n".join(error_list))

def stop_cluster(argv):
    if len(argv) > 0:
        stop_cluster_nodes(argv)
        return

    if not "--force" in utils.pcs_options:
        if utils.is_rhel6():
            output_status, retval = utils.run(["cman_tool", "status"])
            output_nodes, retval = utils.run([
                "cman_tool", "nodes", "-F", "id,type,votes,name"
            ])
            if output_status == output_nodes:
                # when both commands return the same error
                output = output_status
            else:
                output = output_status + "\n---Votes---\n" + output_nodes
            quorum_info = utils.parse_cman_quorum_info(output)
        else:
            output, retval = utils.run(["corosync-quorumtool", "-p", "-s"])
            # retval is 0 on success if node is not in partition with quorum
            # retval is 1 on error OR on success if node has quorum
            quorum_info = utils.parse_quorumtool_output(output)
        if quorum_info:
            if utils.is_node_stop_cause_quorum_loss(quorum_info, local=True):
                utils.err(
                    "Stopping the node will cause a loss of the quorum"
                    + ", use --force to override"
                )
        elif not utils.is_node_offline_by_quorumtool_output(output):
            utils.err(
                "Unable to determine whether stopping the node will cause "
                + "a loss of the quorum, use --force to override"
            )
        # else the node seems to be stopped already, proceed to be sure

    stop_all = (
        "--pacemaker" not in utils.pcs_options
        and
        "--corosync" not in utils.pcs_options
    )
    if stop_all or "--pacemaker" in utils.pcs_options:
        stop_cluster_pacemaker()
    if stop_all or "--corosync" in utils.pcs_options:
        stop_cluster_corosync()

def stop_cluster_pacemaker():
    print "Stopping Cluster (pacemaker)...",
    output, retval = utils.run(["service", "pacemaker","stop"])
    if retval != 0:
        print output,
        utils.err("unable to stop pacemaker")

def stop_cluster_corosync():
    if utils.is_rhel6():
        print "Stopping Cluster (cman)...",
        output, retval = utils.run(["service", "cman","stop"])
        if retval != 0:
            print output,
            utils.err("unable to stop cman")
    else:
        print "Stopping Cluster (corosync)...",
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
    if len(argv) > 2:
        usage.cluster(["cib-push"])
        sys.exit(1)

    filename = None
    scope = None
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope" and "--config" not in utils.pcs_options:
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            else:
                usage.cluster(["cib-push"])
                sys.exit(1)
    if "--config" in utils.pcs_options:
        scope = "configuration"
    if not filename:
        usage.cluster(["cib-push"])
        sys.exit(1)

    try:
        new_cib_dom = xml.dom.minidom.parse(filename)
        if scope and not new_cib_dom.getElementsByTagName(scope):
            utils.err(
                "unable to push cib, scope '%s' not present in new cib"
                % scope
            )
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        utils.err("unable to parse new cib: %s" % e)

    command = ["cibadmin", "--replace", "--xml-file", filename]
    if scope:
        command.append("--scope=%s" % scope)
    output, retval = utils.run(command)
    if retval != 0:
        utils.err("unable to push cib\n" + output)
    else:
        print "CIB updated"

def cluster_upgrade():
    output, retval = utils.run(["cibadmin", "--upgrade", "--force"])
    if retval != 0:
        utils.err("unable to upgrade cluster: %s" % output)
    print "Cluster CIB has been upgraded to latest version"

def cluster_edit(argv):
    if 'EDITOR' in os.environ:
        if len(argv) > 1:
            usage.cluster(["edit"])
            sys.exit(1)

        scope = None
        scope_arg = ""
        for arg in argv:
            if "=" not in arg:
                usage.cluster(["edit"])
                sys.exit(1)
            else:
                arg_name, arg_value = arg.split("=", 1)
                if arg_name == "scope" and "--config" not in utils.pcs_options:
                    if not utils.is_valid_cib_scope(arg_value):
                        utils.err("invalid CIB scope '%s'" % arg_value)
                    else:
                        scope_arg = arg
                        scope = arg_value
                else:
                    usage.cluster(["edit"])
                    sys.exit(1)
        if "--config" in utils.pcs_options:
            scope = "configuration"
            # Leave scope_arg empty as cluster_push will pick up a --config
            # option from utils.pcs_options
            scope_arg = ""

        editor = os.environ['EDITOR']
        tempcib = tempfile.NamedTemporaryFile('w+b',-1,".pcs")
        cib = utils.get_cib(scope)
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
            cluster_push(filter(None, [tempcib.name, scope_arg]))

    else:
        utils.err("$EDITOR environment variable is not set")

def get_cib(argv):
    if len(argv) > 2:
        usage.cluster(["cib"])
        sys.exit(1)

    filename = None
    scope = None
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope" and "--config" not in utils.pcs_options:
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            else:
                usage.cluster(["cib"])
                sys.exit(1)
    if "--config" in utils.pcs_options:
        scope = "configuration"

    if not filename:
        print utils.get_cib(scope),
    else:
        try:
            f = open(filename, 'w')
            output = utils.get_cib(scope)
            if output != "":
                    f.write(output)
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
    node0, node1 = utils.parse_multiring_node(node)

    if not node0:
        utils.err("missing ring 0 address of the node")
    status,output = utils.checkAuthorization(node0)
    if status == 2:
        utils.err("pcsd is not running on %s" % node0)
    elif status == 3:
        utils.err(
            "%s is not yet authenticated (try pcs cluster auth %s)"
            % (node0, node0)
        )

    if add_node == True:
        need_ring1_address = utils.need_ring1_address(utils.getCorosyncConf())
        if not node1 and need_ring1_address:
            utils.err(
                "cluster is configured for RRP, "
                "you have to specify ring 1 address for the node"
            )
        elif node1 and not need_ring1_address:
            utils.err(
                "cluster is not configured for RRP, "
                "you must not specify ring 1 address for the node"
            )
        corosync_conf = None
        (canAdd, error) =  utils.canAddNodeToCluster(node0)
        if not canAdd:
            utils.err("Unable to add '%s' to cluster: %s" % (node0, error))

        for my_node in utils.getNodesFromCorosyncConf():
            retval, output = utils.addLocalNode(my_node, node0, node1)
            if retval != 0:
                print >> sys.stderr, "Error: unable to add %s on %s - %s" % (node0, my_node, output.strip())
            else:
                print "%s: Corosync updated" % my_node
                corosync_conf = output
        if corosync_conf != None:
            utils.setCorosyncConfig(node0, corosync_conf)
            if "--enable" in utils.pcs_options:
                utils.enableCluster(node0)
            if "--start" in utils.pcs_options or utils.is_rhel6():
                # always start new node on cman cluster
                # otherwise it will get fenced
                utils.startCluster(node0)
        else:
            utils.err("Unable to update any nodes")
        output, retval = utils.reloadCorosync()
        if utils.is_cman_with_udpu_transport():
            print("Warning: Using udpu transport on a CMAN cluster, "
                + "cluster restart is required to apply node addition")
    else:
        nodesRemoved = False
        c_nodes = utils.getNodesFromCorosyncConf()
        destroy_cluster([node0])
        for my_node in c_nodes:
            if my_node == node0:
                continue
            retval, output = utils.removeLocalNode(my_node, node0)
            if retval != 0:
                print >> sys.stderr, "Error: unable to remove %s on %s - %s" % (node0,my_node,output.strip())
            else:
                if output[0] == 0:
                    print "%s: Corosync updated" % my_node
                    nodesRemoved = True
                else:
                    print >> sys.stderr, "%s: Error executing command occured: %s" % (my_node, "".join(output[1]))
        if nodesRemoved == False:
            utils.err("Unable to update any nodes")

        output, retval = utils.reloadCorosync()
        output, retval = utils.run(["crm_node", "--force", "-R", node0])
        if utils.is_cman_with_udpu_transport():
            print("Warning: Using udpu transport on a CMAN cluster, "
                + "cluster restart is required to apply node removal")

def cluster_localnode(argv):
    if len(argv) != 2:
        usage.cluster()
        exit(1)
    elif argv[0] == "add":
        node = argv[1]
        if not utils.is_rhel6():
            success = utils.addNodeToCorosync(node)
        else:
            success = utils.addNodeToClusterConf(node)

        if success:
            print "%s: successfully added!" % node
        else:
            utils.err("unable to add %s" % node)
    elif argv[0] in ["remove","delete"]:
        node = argv[1]
        if not utils.is_rhel6():
            success = utils.removeNodeFromCorosync(node)
        else:
            success = utils.removeNodeFromClusterConf(node)

        if success:
            print "%s: successfully removed!" % node
        else:
            utils.err("unable to remove %s" % node)
    else:
        usage.cluster()
        exit(1)

def cluster_uidgid_rhel6(argv, silent_list = False):
    if not os.path.isfile(settings.cluster_conf_file):
        utils.err("the file doesn't exist on this machine, create a cluster before running this command" % settings.cluster_conf_file)

    if len(argv) == 0:
        found = False
        output, retval = utils.run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--lsmisc"])
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
            output, retval = utils.run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--setuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to add uidgid\n" + output.rstrip())
        elif command == "rm":
            output, retval = utils.run(["/usr/sbin/ccs", "-f", settings.cluster_conf_file, "--rmuidgid", "uid="+uid, "gid="+gid])
            if retval != 0:
                utils.err("unable to remove uidgid\n" + output.rstrip())

        # If we make a change, we sync out the changes to all nodes unless we're using -f
        if not utils.usefile:
            sync_nodes(utils.getNodesFromCorosyncConf(), utils.getCorosyncConf())
         
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
    if utils.is_rhel6():
        utils.err("corosync.conf is not supported on CMAN clusters")

    if len(argv) > 1:
        usage.cluster()
        exit(1)

    if len(argv) == 0:
        print utils.getCorosyncConf()
        return

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

# Completely tear down the cluster & remove config files
# Code taken from cluster-clean script in pacemaker
def cluster_destroy(argv):
    if "--all" in utils.pcs_options:
        destroy_cluster(utils.getNodesFromCorosyncConf())
    else:
        print "Shutting down pacemaker/corosync services..."
        os.system("service pacemaker stop")
        os.system("service corosync stop")
        print "Killing any remaining services..."
        os.system("killall -q -9 corosync aisexec heartbeat pacemakerd ccm stonithd ha_logd lrmd crmd pengine attrd pingd mgmtd cib fenced dlm_controld gfs_controld")
        utils.disableServices()

        print "Removing all cluster configuration files..."
        if utils.is_rhel6():
            os.system("rm -f /etc/cluster/cluster.conf")
        else:
            os.system("rm -f /etc/corosync/corosync.conf")
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
        dom = constraint.remove_constraints_containing_node(dom, hostname)
        utils.replace_cib_configuration(dom)
    else:
        usage.cluster(["remote-node"])
        sys.exit(1)

def cluster_quorum_unblock(argv):
    if len(argv) > 0:
        usage.cluster(["quorum", "unblock"])
        sys.exit(1)

    if utils.is_rhel6():
        utils.err("operation is not supported on CMAN clusters")

    output, retval = utils.run(
        ["corosync-cmapctl", "-g", "runtime.votequorum.wait_for_all_status"]
    )
    if retval != 0:
        utils.err("unable to check quorum status")
    if output.split("=")[-1].strip() != "1":
        utils.err("cluster is not waiting for nodes to establish quorum")

    unjoined_nodes = (
        set(utils.getNodesFromCorosyncConf())
        -
        set(utils.getCorosyncActiveNodes())
    )
    if not unjoined_nodes:
        utils.err("no unjoined nodes found")
    for node in unjoined_nodes:
        stonith.stonith_confirm([node])

    output, retval = utils.run(
        ["corosync-cmapctl", "-s", "quorum.cancel_wait_for_all", "u8", "1"]
    )
    if retval != 0:
        utils.err("unable to cancel waiting for nodes")
    print "Quorum unblocked"

    startup_fencing = prop.get_set_properties().get("startup-fencing", "")
    utils.set_cib_property(
        "startup-fencing",
        "false" if startup_fencing.lower() != "false" else "true"
    )
    utils.set_cib_property("startup-fencing", startup_fencing)
    print "Waiting for nodes cancelled"

class NodeActionThread(threading.Thread):
    def __init__(self, node):
        super(NodeActionThread, self).__init__()
        self.node = node
        self.retval = 0
        self.output = ""

class NodeStartThread(NodeActionThread):
    def run(self):
        self.retval, self.output = utils.startCluster(self.node, quiet=True)

class NodeStopPacemakerThread(NodeActionThread):
    def run(self):
        self.retval, self.output = utils.stopCluster(
            self.node, quiet=True, pacemaker=True, corosync=False
        )

class NodeStopCorosyncThread(NodeActionThread):
    def run(self):
        self.retval, self.output = utils.stopCluster(
            self.node, quiet=True, pacemaker=False, corosync=True
        )

class NodeDestroyThread(NodeActionThread):
    def run(self):
        self.retval, self.output = utils.destroyCluster(self.node, quiet=True)

