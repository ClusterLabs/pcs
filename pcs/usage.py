import re

examples = ""
def full_usage():
    global examples
    out = ""
    out += main(False)
    out += strip_extras(resource([],False))
    out += strip_extras(cluster([],False))
    out += strip_extras(stonith([],False))
    out += strip_extras(property([],False))
    out += strip_extras(constraint([],False))
    out += strip_extras(acl([],False))
    out += strip_extras(status([],False))
    out += strip_extras(config([],False))
    print out.strip()
    print "Examples:\n" + examples.replace(" \ ","")

def strip_extras(text):
    global examples
    ret = ""
    group_name = text.split(" ")[2]
    in_commands = False
    in_examples = False
    lines = text.split("\n")
    minicmd = ""

    ret += group_name.title() + ":\n"
    for line in lines:
        if not in_commands:
            if line == "Commands:":
                in_commands = True
                continue
        if not in_examples:
            if line == "Examples:":
                in_examples = True
                continue
        if not in_examples and not in_commands:
            continue
        if len(line) >= 4:
            if line[0:4] == "    ":
                if line[4:8] != "    ":
                    if in_examples:
                        minicmd = line.lstrip() + "  "
                    else:
                        minicmd = "    " + " " + line.lstrip() + "  "
                else:
                    minicmd += line.lstrip() + " "
            else:
                if in_commands:
                    break
        else:
            if in_examples:
                examples += minicmd + "\n\n"
            else:
                ret += minicmd + "\n"
            minicmd = ""
    return ret

# Print only output for items that match the args
# For now we only look at the first arg
# If no args, then we return the full output

def sub_usage(args, output):
    if len(args) == 0:
        return output

    ret = ""
    lines = output.split('\n')
    begin_printing = False
    usage = re.sub("\[commands\]", args[0], lines[1])
    for line in lines:
        if begin_printing == True and re.match("^    [^ ]",line) and not re.match("^    " + args[0], line):
            begin_printing = False
        if not re.match("^ ",line) and not re.match("^$",line):
            begin_printing = False
        if re.match("^    " + args[0], line):
            begin_printing = True

        if begin_printing:
            ret += line + "\n"

    if ret != "":
        return "\n" + usage + "\n" + ret.rstrip() + "\n"
    else:
        return output
    
def dict_depth(d, depth=0):
    if not isinstance(d, dict) or not d:
        return depth
    return max(dict_depth(v, depth+1) for k, v in d.iteritems())

def sub_gen_code(level,item,prev_level=[],spaces=""):
    out = ""

    if dict_depth(item) <= level:
        return ""

    out += 'case "${cur' + str(level) + '}" in\n'
    next_level = []
    for key,val in item.items():
        if len(val) == 0:
            continue
        values = " ".join(val.keys())
        values = values.replace("|"," ")
        out += "  " + key + ")\n"
        if len(val) > 0 and level != 1:
            out += sub_gen_code(level-1,item[key],[] ,spaces + "  ")
        else:
            out += "    " + 'COMPREPLY=($(compgen -W "' + values + '" -- ${cur}))\n'
            out += "    return 0\n"
        out += "    ;;\n"
    out += "  *)\n"
    out += "  ;;\n"
    out += 'esac\n'
    temp = out.split('\n')
    new_out = ""
    for l in temp:
        new_out += spaces + l + "\n"
    return new_out


def sub_generate_bash_completion():
    tree = {}
    tree["resource"] = generate_tree(resource([],False))
    tree["cluster"] = generate_tree(cluster([],False))
    tree["stonith"] = generate_tree(stonith([],False))
    tree["property"] = generate_tree(property([],False))
    tree["acl"] = generate_tree(acl([],False))
    tree["constraint"] = generate_tree(constraint([],False))
    tree["status"] = generate_tree(status([],False))
    tree["config"] = generate_tree(config([],False))
    print """
    _pcs()
    {
    local cur cur1 cur2 cur3
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    if [ "$COMP_CWORD" -gt "0" ]; then cur1="${COMP_WORDS[COMP_CWORD-1]}";fi
    if [ "$COMP_CWORD" -gt "1" ]; then cur2="${COMP_WORDS[COMP_CWORD-2]}";fi
    if [ "$COMP_CWORD" -gt "2" ]; then cur3="${COMP_WORDS[COMP_CWORD-3]}";fi

    """
    print sub_gen_code(3,tree,[])
    print sub_gen_code(2,tree,[])
    print sub_gen_code(1,tree,[])
    print """
    if [ $COMP_CWORD -eq 1 ]; then
        COMPREPLY=( $(compgen -W "resource cluster stonith property acl constraint status config" -- $cur) )
    fi
    return 0

    }
    complete -F _pcs pcs
    """


def generate_tree(usage_txt):
    ignore = True
    ret_hash = {}
    cur_stack = []
    for l in usage_txt.split('\n'):
        if l.startswith("Commands:"):
            ignore = False
            continue

        if l.startswith("Examples:"):
            break

        if ignore == True:
            continue
        
        if re.match("^    \w",l):
            args = l.split()
            arg = args.pop(0)
            if not arg in ret_hash:
                ret_hash[arg] = {}
            cur_hash = ret_hash[arg]
            for arg in args:
                if arg.startswith('[') or arg.startswith('<'):
                    break
                if not arg in cur_hash:
                    cur_hash[arg] = {}
                cur_hash = cur_hash[arg]
    return ret_hash

def main(pout=True):
    output =  """
Usage: pcs [-f file] [-h] [commands]...
Control and configure pacemaker and corosync.

Options:
    -h, --help  Display usage and exit
    -f file     Perform actions on file instead of active CIB
    --debug     Print all network traffic and external commands run
    --version   Print pcs version information

Commands:
    cluster     Configure cluster options and nodes
    resource    Manage cluster resources
    stonith     Configure fence devices
    constraint  Set resource constraints
    property    Set pacemaker properties
    acl         Set pacemaker access control lists
    status      View cluster status
    config      View and manage cluster configuration
"""
# Advanced usage to possibly add later
#  --corosync_conf=<corosync file> Specify alternative corosync.conf file
    if pout:
        print output
    else:
        return output
                                                    

def resource(args = [], pout = True):
    output = """
Usage: pcs resource [commands]...
Manage pacemaker resources

Commands:
    show [resource id] [--full] [--groups]
        Show all currently configured resources or if a resource is specified
        show the options for the configured resource.  If --full is specified
        all configured resource options will be displayed.  If --groups is
        specified, only show groups (and their resources).


    list [<standard|provider|type>] [--nodesc]
        Show list of all available resources, optionally filtered by specified
        type, standard or provider.  If --nodesc is used then descriptions
        of resources are not printed.

    describe <standard:provider:type|type>
        Show options for the specified resource

    create <resource id> <standard:provider:type|type> [resource options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...]
           [--clone <clone options> | --master <master options> |
           --group <group name> [--before <resource id> | --after <resource id>]
           ] [--disabled] [--wait[=n]]
        Create specified resource.  If --clone is used a clone resource is
        created if --master is specified a master/slave resource is created.
        If --group is specified the resource is added to the group named.  You
        can use --before or --after to specify the position of the added
        resource relatively to some resource already existing in the group.
        If --disabled is specified the resource is not started automatically.
        If --wait is specified, pcs will wait up to 'n' seconds for the resource
        to start and then return 0 if the resource is started, or 1 if the
        resource has not yet started. If 'n' is not specified, default resource
        timeout will be used.
        Example: pcs resource create VirtualIP ocf:heartbeat:IPaddr2 \\
                     ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s \\
                     nic=eth2
                 Create a new resource called 'VirtualIP' with IP address
                 192.168.0.99, netmask of 32, monitored everything 30 seconds,
                 on eth2.

    delete <resource id|group id|master id|clone id>
        Deletes the resource, group, master or clone (and all resources within
        the group/master/clone).

    enable <resource id> [--wait[=n]]
        Allow the cluster to start the resource. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resource may
        remain stopped.  If --wait is specified, pcs will wait up to 'n' seconds
        (or resource timeout seconds) for the resource to start and then return
        0 if the resource is started, or 1 if the resource has not yet started.

    disable <resource id> [--wait[=n]]
        Attempt to stop the resource if it is running and forbid the cluster
        from starting it again.  Depending on the rest of the configuration
        (constraints, options, failures, etc), the resource may remain
        started.  If --wait is specified, pcs will wait up to 'n' seconds (or
        resource timeout seconds) for the resource to stop and then return 0
        if the resource is stopped or 1 if the resource has not stopped.

    restart <resource id> [node] [--wait=n]
        Restart the resource specified. If a node is specified and if the
        resource is a clone or master/slave it will be restarted only on
        the node specified.  If --wait is specified, then we will wait
        up to 'n' seconds for the resource to be restarted and return 0 if
        the restart was successful or 1 if it was not.

    debug-start <resource id> [--full]
        This command will force the specified resource to start on this node
        ignoring the cluster recommendations and print the output from
        starting the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to start.

    move <resource id> [destination node] [--master] [lifetime=<lifetime>]
         [--wait[=n]]
        Move resource off current node (and optionally onto destination node).
        If --master is used the scope of the command is limited to the master
        role and you must use the master id (instead of the resource id).
        If lifetime is not specified it defaults to infinite.  If --wait is
        specified, pcs will wait up to 'n' seconds for the resource to start
        on destination node and then return 0 if the resource is started, or 1
        if the resource has not yet started.  If 'n' is not specified, default
        resource timeout will be used.

    ban <resource id> [node] [--master] [lifetime=<lifetime>] [--wait[=n]]
        Prevent the resource id specified from running on the node (or on the
        current node it is running on if no node is specified).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id).
        If lifetime is not specified it defaults to infinite.  If --wait is
        specified, pcs will wait up to 'n' seconds for the resource to start
        on different node and then return 0 if the resource is started, or 1
        if the resource has not yet started.  If 'n' is not specified, default
        resource timeout will be used.

    clear <resource id> [node] [--master] [--wait=n]
        Remove constraints created by move and/or ban on the specified
        resource (and node if specified).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id).
        If --wait is specified, pcs will wait up to 'n' seconds for resources
        to start / move depending on the effect of removing the constraints and
        then return 0 if resources are started on target nodes, or 1 if
        resources have not yet started / moved.  If clear has no effect, pcs
        will return 0.

    standards
        List available resource agent standards supported by this installation.
        (OCF, LSB, etc.)

    providers
        List available OCF resource agent providers

    agents [standard[:provider]]
        List available agents optionally filtered by standard and provider

    update <resource id> [resource options] [op [<operation action>
           <operation options>]...] [meta <meta operations>...] [--wait[=n]]
        Add/Change options to specified resource, clone or multi-state
        resource.  If an operation (op) is specified it will update the first
        found operation with the same action on the specified resource, if no
        operation with that action exists then a new operation will be created.
        (WARNING: all current options on the update op will be reset if not
        specified) If you want to create multiple monitor operations you should
        use the add_operation & remove_operation commands.  If --wait is
        specified, pcs will wait up to 'n' seconds for the changes to take
        effect and then return 0 if the changes have been processed or 1
        otherwise.  If 'n' is not specified, default resource timeout will
        be used.

    op add <resource id> <operation action> [operation properties]
        Add operation for specified resource

    op remove <resource id> <operation action> [<operation properties>...]
        Remove specified operation (note: you must specify the exact operation
        properties to properly remove an existing operation).

    op remove <operation id>
        Remove the specified operation id

    op defaults [options]
        Set default values for operations, if no options are passed, lists
        currently configured defaults

    meta <resource id | group id | master id | clone id> <meta options>
         [--wait[=n]]
        Add specified options to the specified resource, group, master/slave
        or clone.  Meta options should be in the format of name=value, options
        may be removed by setting an option without a value.  If --wait is
        specified, pcs will wait up to 'n' seconds for the changes to take
        effect and then return 0 if the changes have been processed or 1
        otherwise.  If 'n' is not specified, default resource timeout will
        be used.
        Example: pcs resource meta TestResource failure-timeout=50 stickiness=

    group add <group name> <resource id> [resource id] ... [resource id]
              [--before <resource id> | --after <resource id>] [--wait[=n]]
        Add the specified resource to the group, creating the group if it does
        not exist.  If the resource is present in another group it is moved
        to the new group.  You can use --before or --after to specify
        the position of the added resources relatively to some resource already
        existing in the group.  If --wait is specified, pcs will wait up to 'n'
        seconds for resources to move depending on the effect of grouping and
        then return 0 if the resources are moved, or 1 if the resources have not
        yet moved.  If 'n' is not specified, default resource timeout will
        be used.

    group remove <group name> <resource id> [resource id] ... [resource id]
          [--wait[=n]]
        Remove the specified resource(s) from the group, removing the group if
        it no resources remain.  If --wait is specified, pcs will wait up to 'n'
        seconds for specified resources to move depending of the effect
        of ungrouping and the return 0 if resources are moved to target nodes,
        or 1 if resources have not yet moved.  If 'n' is not specified, default
        resource timeout will be used.

    ungroup <group name> [resource id] ... [resource id] [--wait[=n]]
        Remove the group (Note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group.  If --wait is specified, pcs will wait up to 'n' seconds
        for specified resources (all group resources if no resource specified)
        to move depending of the effect of ungrouping and the return 0 if
        resources are moved to target nodes, or 1 if resources have not yet
        moved.  If 'n' is not specified, default resource timeout will be used.

    clone <resource id | group id> [clone options]... [--wait[=n]]
        Setup up the specified resource or group as a clone.  If --wait is
        specified, pcs will wait up to 'n' seconds for the resource clones
        to start and then return 0 if the clones are started, or 1 if
        the clones has not yet started.  If 'n' is not specified, default
        resource timeout will be used.

    unclone <resource id | group name> [--wait[=n]]
        Remove the clone which contains the specified group or resource (the
        resource or group will not be removed).  If --wait is specified, pcs
        will wait up to 'n' seconds for the resource clones to stop and then
        return 0 if the resource is running as one instance, or 1 if
        the resource clones has not yet stopped.  If 'n' is not specified,
        default resource timeout will be used.

    master [<master/slave name>] <resource id | group name> [options]
           [--wait[=n]]
        Configure a resource or group as a multi-state (master/slave) resource.
        If --wait is specified, pcs will wait up to 'n' seconds for the resource
        to be promoted and then return 0 if the resource is promoted, or 1 if
        the resource has not yet been promoted.  If 'n' is not specified,
        default resource timeout will be used.
        Note: to remove a master you must remove the resource/group it contains.

    manage <resource id> ... [resource n]
        Set resources listed to managed mode (default)

    unmanage <resource id> ... [resource n]
        Set resources listed to unmanaged mode

    defaults [options]
        Set default values for resources, if no options are passed, lists
        currently configured defaults

    cleanup [<resource id>]
        Cleans up the resource in the lrmd (useful to reset the resource
        status and failcount).  This tells the cluster to forget the
        operation history of a resource and re-detect its current state.
        This can be useful to purge knowledge of past failures that have
        since been resolved. If a resource id is not specified then all
        resources/stonith devices will be cleaned up.

    failcount show <resource id> [node]
        Show current failcount for specified resource from all nodes or
        only on specified node

    failcount reset <resource id> [node]
        Reset failcount for specified resource on all nodes or only on
        specified node.  This tells the cluster to forget how many times
        a resource has failed in the past.  This may allow the resource to
        be started or moved to a more preferred location.

Examples:

    pcs resource show
      Show all resources

    pcs resource show VirtualIP
      Show options specific to the 'VirtualIP' resource


    pcs resource create VirtualIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s 
      Create a new resource called 'VirtualIP' with options

    pcs resource create VirtualIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s
      Create a new resource called 'VirtualIP' with options

    pcs resource update VirtualIP ip=192.168.0.98 nic=
      Change the ip address of VirtualIP and remove the nic option

    pcs resource delete VirtualIP
      Delete the VirtualIP resource

Notes:
    Starting resources on a cluster is (almost) always done by pacemaker and
    not directly from pcs.  If your resource isn't starting, it's usually
    due to either a misconfiguration of the resource (which you debug in
    the system log), or constraints preventing the resource from starting or
    the resource being disabled.  You can use 'pcs resource debug-start' to
    test resource configuration, but it should *not* normally be used to start
    resources in a cluster.

"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def cluster(args = [], pout = True):
    output = """
Usage: pcs cluster [commands]...
Configure cluster for use with pacemaker

Commands:
    auth [node] [...] [-u username] [-p password] [--force] [--local]
        Authenticate pcs to pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified (authorization
        tokens are stored in ~/.pcs/tokens or /var/lib/pcsd/tokens for root).
        By default all nodes are also authenticated to each other, using
        --local only authenticates the local node (and does not authenticate
        the remote nodes with each other).  Using --force forces
        re-authentication to occur.

    setup [--start] [--local] [--enable] --name <cluster name> <node1[,node1-altaddr]>
            [node2[,node2-altaddr]] [..] [--transport <udpu|udp>] [--rrpmode active|passive]
            [--addr0 <addr/net> [[[--mcast0 <address>] [--mcastport0 <port>]
                            [--ttl0 <ttl>]] | [--broadcast0]]
            [--addr1 <addr/net> [[[--mcast1 <address>] [--mcastport1 <port>]
                            [--ttl1 <ttl>]] | [--broadcast1]]]]
            [--wait_for_all=<0|1>] [--auto_tie_breaker=<0|1>]
            [--last_man_standing=<0|1> [--last_man_standing_window=<time in ms>]]
            [--ipv6] [--token <timeout>] [--token_coefficient <timeout>]
            [--join <timeout>] [--consensus <timeout>] [--miss_count_const <count>]
            [--fail_recv_const <failures>]
        Configure corosync and sync configuration out to listed nodes
        --local will only perform changes on the local node
        --start will also start the cluster on the specified nodes
        --enable will enable corosync and pacemaker on node startup
        --transport allows specification of corosync transport (default: udpu)
        --rrpmode allows you to set the RRP mode of the system. Currently only
            'passive' is supported or tested (using 'active' is not
            recommended)
        The --wait_for_all, --auto_tie_breaker, --last_man_standing,
        --last_man_standing_window options are all documented in corosync's
        votequorum(5) man page.
        --ipv6 will configure corosync to use ipv6 (instead of ipv4)
        --token <timeout> sets time in milliseconds until a token loss is
            declared after not receiving a token (default 1000 ms)
        --token_coefficient <timeout> sets time in milliseconds used for clusters
            with at least 3 nodes as a coefficient for real token timeout calculation
            (token + (number_of_nodes - 2) * token_coefficient) (default 650 ms)
        --join <timeout> sets time in milliseconds to wait for join messages
            (default 50 ms)
        --consensus <timeout> sets time in milliseconds to wait for consensus
            to be achieved before starting a new round of membership configuration
            (default 1200 ms)
        --miss_count_const <count> sets the maximum number of times on
            receipt of a token a message is checked for retransmission before
            a retransmission occurs (default 5 messages)
        --fail_recv_const <failures> specifies how many rotations of the token
            without receiving any messages when messages should be received
            may occur before a new configuration is formed (default 2500 failures)

        Configuring Redundant Ring Protocol (RRP)

        When using udpu (the default) specifying nodes, specify the ring 0
        address first followed by a ',' and then the ring 1 address.

        Example: pcs cluster setup --name cname nodeA-0,nodeA-1 nodeB-0,nodeB-1

        When using udp, using --addr0 and --addr1 will allow you to configure
        rrp mode for corosync.  It's recommended to use a network (instead of
        IP address) for --addr0 and --addr1 so the same corosync.conf file can
        be used around the cluster.  --mcast0 defaults to 239.255.1.1 and
        --mcast1 defaults to 239.255.2.1, --mcastport0/1 default to 5405 and
        ttl defaults to 1. If --broadcast is specified, --mcast0/1,
        --mcastport0/1 & --ttl0/1 are ignored.

    start [--all] [node] [...]
        Start corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are started on the local node.
        If --all is specified then corosync & pacemaker are started on all
        nodes.

    stop [--all] [node] [...]
        Stop corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are stopped on the local node.
        If --all is specified then corosync & pacemaker are stopped on all
        nodes.

    kill
        Force corosync and pacemaker daemons to stop on the local node
        (performs kill -9).

    enable [--all] [node] [...]
        Configure corosync & pacemaker to run on node boot on specified
        node(s), if node is not specified then corosync & pacemaker are
        enabled on the local node. If --all is specified then corosync &
        pacemaker are enabled on all nodes.

    disable [--all] [node] [...]
        Configure corosync & pacemaker to not run on node boot on specified
        node(s), if node is not specified then corosync & pacemaker are
        disabled on the local node. If --all is specified then corosync &
        pacemaker are disabled on all nodes. (Note: this is the default after
        installation)

    standby [<node>] | --all
        Put specified node into standby mode (the node specified will no longer
        be able to host resources), if no node or options are specified the
        current node will be put into standby mode, if --all is specified all
        nodes will be put into standby mode.
    
    unstandby [<node>] | --all
        Remove node from standby mode (the node specified will now be able to
        host resources), if no node or options are specified the current node
        will be removed from standby mode, if --all is specified all nodes will
        be removed from standby mode.

    remote-node add <hostname> <resource id> [options]
        Enables the specified resource as a remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n')
    
    remote-node remove <hostname>
        Disables any resources configured to be remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n')

    status
        View current cluster status (an alias of 'pcs status cluster')

    pcsd-status [node] [...]
        Get current status of pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified

    certkey <certificate file> <key file>
        Load custom certificate and key files for use in pcsd

    sync
        Sync corosync configuration to all nodes found from current
        corosync.conf file (cluster.conf on systems running Corosync 1.x)

    quorum unblock
        Cancel waiting for all nodes when establishing quorum.  Useful in
        situations where you know the cluster is inquorate, but you are
        confident that the cluster should proceed with resource management
        regardless.

    cib [filename] [scope=<scope> | --config]
        Get the raw xml from the CIB (Cluster Information Base).  If a
        filename is provided, we save the cib to that file, otherwise the cib
        is printed.  Specify scope to get a specific section of the CIB.  Valid
        values of the scope are: configuration, nodes, resources, constraints,
        crm_config, rsc_defaults, op_defaults, status.  --config is the same
        as scope=configuration.  Use of --config is recommended.  Do not specify
        a scope if you need to get the whole CIB or be warned in the case
        of outdated CIB on cib-push.


    cib-push <filename> [scope=<scope> | --config]
        Push the raw xml from <filename> to the CIB (Cluster Information Base).
        Specify scope to push a specific section of the CIB.  Valid values
        of the scope are: configuration, nodes, resources, constraints,
        crm_config, rsc_defaults, op_defaults.  --config is the same as
        scope=configuration.  Use of --config is recommended.  Do not specify
        a scope if you need to push the whole CIB or be warned in the case
        of outdated CIB.

    cib-upgrade
        Upgrade the cib to the latest version

    edit [scope=<scope> | --config]
        Edit the cib in the editor specified by the $EDITOR environment
        variable and push out any changes upon saving.  Specify scope to edit
        a specific section of the CIB.  Valid values of the scope are:
        configuration, nodes, resources, constraints, crm_config, rsc_defaults,
        op_defaults.  --config is the same as scope=configuration.  Use of
        --config is recommended.  Do not specify a scope if you need to edit
        the whole CIB or be warned in the case of outdated CIB.

    node add <node[,node-altaddr]> [--start] [--enable]
        Add the node to corosync.conf and corosync on all nodes in the cluster
        and sync the new corosync.conf to the new node.  If --start is specified
        also start corosync/pacemaker on the new node, if --enable is specified
        enable corosync/pacemaker on new node.
        When using Redundant Ring Protocol (RRP) with udpu transport, specify
        the ring 0 address first followed by a ',' and then the ring 1 address.

    node remove <node>
        Shutdown specified node and remove it from pacemaker and corosync on
        all other nodes in the cluster

    uidgid
        List the current configured uids and gids of users allowed to connect
        to corosync

    uidgid add [uid=<uid>] [gid=<gid>]
        Add the specified uid and/or gid to the list of users/groups
        allowed to connect to corosync

    uidgid rm [uid=<uid>] [gid=<gid>]
        Remove the specified uid and/or gid from the list of users/groups
        allowed to connect to corosync

    corosync [node]
        Get the corosync.conf from the specified node or from the current node
        if node not specified

    reload corosync
        Reload the corosync configuration on the current node

    destroy [--all]
        Permanently destroy the cluster on the current node, killing all
        corosync/pacemaker processes removing all cib files and the
        corosync.conf file.  Using '--all' will attempt to destroy the
        cluster on all nodes configure in the corosync.conf file
        WARNING: This command permantly removes any cluster configuration that
        has been created. It is recommended to run 'pcs cluster stop' before
        destroying the cluster.

    verify [-V] [filename]
        Checks the pacemaker configuration (cib) for syntax and common
        conceptual errors.  If no filename is specified the check is
        performmed on the currently running cluster.  If '-V' is used
        more verbose output will be printed

    report [--from "YYYY-M-D H:M:S" [--to "YYYY-M-D" H:M:S"]] dest
        Create a tarball containing everything needed when reporting cluster
        problems.  If '--from' and '--to' are not used, the report will include
        the past 24 hours
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def stonith(args = [], pout = True):
    output = """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    show [stonith id] [--full]
        Show all currently configured stonith devices or if a stonith id is
        specified show the options for the configured stonith device.  If
        --full is specified all configured stonith options will be displayed

    list [filter] [--nodesc]
        Show list of all available stonith agents (if filter is provided then
        only stonith agents matching the filter will be shown). If --nodesc is
        used then descriptions of stonith agents are not printed.

    describe <stonith agent>
        Show options for specified stonith agent

    create <stonith id> <stonith device type> [stonith device options]
        Create stonith device with specified type and options

    update <stonith id> [stonith device options]
        Add/Change options to specified stonith id
        
    delete <stonith id>
        Remove stonith id from configuration

    cleanup [<stonith id>]
        Cleans up the stonith device in the lrmd (useful to reset the 
        status and failcount).  This tells the cluster to forget the
        operation history of a stonith device and re-detect its current state.
        This can be useful to purge knowledge of past failures that have
        since been resolved. If a stonith id is not specified then all
        resources/stonith devices will be cleaned up.

    level
        Lists all of the fencing levels currently configured

    level add <level> <node> <devices>
        Add the fencing level for the specified node with a comma separated
        list of devices (stonith ids) to attempt for that node at that level.
        Fence levels are attempted in numerical order (starting with 1) if
        a level succeeds (meaning all devices are successfully fenced in that
        level) then no other levels are tried, and the node is considered
        fenced.

    level remove <level> [node id] [stonith id] ... [stonith id]
        Removes the fence level for the level, node and/or devices specified
        If no nodes or devices are specified then the fence level is removed

    level clear [node|stonith id(s)]
        Clears the fence levels on the node (or stonith id) specified or clears
        all fence levels if a node/stonith id is not specified.  If more than
        one stonith id is specified they must be separated by a comma and no
        spaces.  Example: pcs stonith level clear dev_a,dev_b

    level verify
        Verifies all fence devices and nodes specified in fence levels exist

    fence <node> [--off]
        Fence the node specified (if --off is specified, use the 'off' API
        call to stonith which will turn the node off instead of rebooting it)

    confirm <node>
        Confirm that the host specified is currently down
        WARNING: if this node is not actually down data corruption/cluster
        failure can occur.

Examples:
    pcs stonith create MyStonith fence_virt pcmk_host_list=f1
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def property(args = [], pout = True):
    output = """
Usage: pcs property <properties>...
Configure pacemaker properties

Commands:
    list|show [<property> | --all | --defaults]
        List property settings (default: lists configured properties)
        If --defaults is specified will show all property defaults, if --all
        is specified, current configured properties will be shown with unset
        properties and their defaults

    set [--force] [--node <nodename>] <property>=[<value>]
        Set specific pacemaker properties (if the value is blank then the
        property is removed from the configuration).  If a property is not
        recognized by pcs the property will not be created unless the
        '--force' is used.  If --node is used a node attribute is set on
        the specified node.

    unset [--node <nodename>] <property>
        Remove property from configuration (or remove attribute from
        specified node if --node is used).

Examples:
    pcs property set stonith-enabled=false
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def constraint(args = [], pout = True):
    output = """
Usage: pcs constraint [constraints]...
Manage resource constraints

Commands:
    [list|show] --full
        List all current location, order and colocation constraints, if --full
        is specified also list the constraint ids.

    location <resource id> prefers <node[=score]>...
        Create a location constraint on a resource to prefer the specified
        node and score (default score: INFINITY)

    location <resource id> avoids <node[=score]>...
        Create a location constraint on a resource to avoid the specified
        node and score (default score: INFINITY)

    location <resource id> rule [id=<rule id>] [resource-discovery=<option>]
             [role=master|slave] [constraint-id=<id>]
             [score=<score>|score-attribute=<attribute>] <expression>
        Creates a location rule on the specified resource where the expression
        looks like one of the following:
          defined|not_defined <attribute>
          <attribute> lt|gt|lte|gte|eq|ne [string|integer|version] <value>
          date gt|lt <date>
          date in_range <date> to <date>
          date in_range <date> to duration <duration options>...
          date-spec <date spec options>...
          <expression> and|or <expression>
          ( <expression> )
        where duration options and date spec options are: hours, monthdays,
        weekdays, yeardays, months, weeks, years, weekyears, moon
        If score is omitted it defaults to INFINITY. If id is omitted one is
        generated from the resource id. If resource-discovery is omitted it
        defaults to 'always'.

    location show [resources|nodes [node id|resource id]...] [--full]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node.  If specific
        nodes or resources are specified then we only show information about
        them

    location add <id> <resource name> <node> <score> [resource-discovery=<option>]
        Add a location constraint with the appropriate id, resource name,
        node name and score. (For more advanced pacemaker usage)

    location remove <id> [<resource name> <node> <score>]
        Remove a location constraint with the appropriate id, resource name,
        node name and score. (For more advanced pacemaker usage)

    order show [--full]
        List all current ordering constraints (if '--full' is specified show
        the internal constraint id's as well).

    order [action] <resource id> then [action] <resource id> [options]
        Add an ordering constraint specifying actions (start, stop, promote,
        demote) and if no action is specified the default action will be
        start.
        Available options are kind=Optional/Mandatory/Serialize,
        symmetrical=true/false and id=<constraint-id>.

    order set <resource1> <resource2> [resourceN]... [options] [set
              <resourceX> <resourceY> ... [options]]
              [setoptions [constraint_options]]
        Create an ordered set of resources.
        Available options are sequential=true/false, require-all=true/false,
        action=start/promote/demote/stop and role=Stopped/Started/Master/Slave.
        Available constraint_options are id=<constraint-id>,
        kind=Optional/Mandatory/Serialize and symmetrical=true/false.

    order remove <resource1> [resourceN]...
        Remove resource from any ordering constraint

    colocation show [--full]
        List all current colocation constraints (if '--full' is specified show
        the internal constraint id's as well).

    colocation add [master|slave] <source resource id> with [master|slave]
                   <target resource id> [score] [options] [id=constraint-id]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score force <source resource> to
        run (or not run) with <target resource>. (score defaults to "INFINITY")
        A role can be master or slave (if no role is specified, it defaults to
        'started').

    colocation set <resource1> <resource2> [resourceN]... [options]
               [set <resourceX> <resourceY> ... [options]]
               [setoptions [constraint_options]]
        Create a colocation constraint with a resource set.
        Available options are sequential=true/false, require-all=true/false,
        action=start/promote/demote/stop and role=Stopped/Started/Master/Slave.
        Available constraint_options are id, score, score-attribute and
        score-attribute-mangle.

    colocation remove <source resource id> <target resource id>
        Remove colocation constraints with <source resource>

    remove [constraint id]...
        Remove constraint(s) or constraint rules with the specified id(s)

    ref <resource>...
        List constraints referencing specified resource

    rule add <constraint id> [id=<rule id>] [role=master|slave]
             [score=<score>|score-attribute=<attribute>] <expression>
        Add a rule to a constraint where the expression looks like one of
        the following:
          defined|not_defined <attribute>
          <attribute> lt|gt|lte|gte|eq|ne [string|integer|version] <value>
          date gt|lt <date>
          date in_range <date> to <date>
          date in_range <date> to duration <duration options>...
          date-spec <date spec options>...
          <expression> and|or <expression>
          ( <expression> )
        where duration options and date spec options are: hours, monthdays,
        weekdays, yeardays, months, weeks, years, weekyears, moon
        If score is ommited it defaults to INFINITY. If id is ommited one is
        generated from the constraint id.

    rule remove <rule id>
        Remove a rule if a rule id is specified, if rule is last rule in its
        constraint, the constraint will be removed
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def acl(args = [], pout = True):
    output = """
Usage: pcs acl [commands]...
View and modify current cluster access control lists
Commands:

    [show]
        List all current access control lists

    enable
        Enable access control lists

    disable
        Disable access control lists

    role create <role name> [description=<description>] [((read | write | deny)
                                                (xpath <query> | id <id>))...]
        Create a role with the name and (optional) description specified.
        Each role can also have an unlimited number of permissions
        (read/write/deny) applied to either an xpath query or the id
        of a specific element in the cib

    role delete <role name>
        Delete the role specified and remove it from any users/groups it was
        assigned to

    role assign <role name> [to] <username/group>
        Assign a role to a user or group already created with 'pcs acl
        user/group create'

    role unassign <role name> [from] <username/group>
        Remove a role from the specified user

    user create <username> <role name> [<role name>]...
        Create an ACL for the user specified and assign roles to the user

    user delete <username>
        Remove the user specified (and roles assigned will be unassigned for
        the specified user)

    group create <group> <role name> [<role name>]...
        Create an ACL for the group specified and assign roles to the group

    group delete <group>
        Remove the group specified (and roles assigned will be unassigned for
        the specified group)

    permission add <role name> ((read | write | deny) (xpath <query> |
                                                                id <id>))...
        Add the listed permissions to the role specified

    permission delete <permission id>
        Remove the permission id specified (permission id's are listed in
        parenthesis after permissions in 'pcs acl' output)
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def status(args = [], pout = True):
    output = """
Usage: pcs status [commands]...
View current cluster and resource status
Commands:
    [status] [--full]
        View all information about the cluster and resources (--full provides
        more details)

    resources
        View current status of cluster resources

    groups
        View currently configured groups and their resources

    cluster
        View current cluster status

    corosync
        View current membership information as seen by corosync

    nodes [corosync|both|config]
        View current status of nodes from pacemaker. If 'corosync' is
        specified, print nodes currently configured in corosync, if 'both'
        is specified, print nodes from both corosync & pacemaker.  If 'config'
        is specified, print nodes from corosync & pacemaker configuration.

    pcsd <node> ...
        Show the current status of pcsd on the specified nodes

    xml
        View xml version of status (output from crm_mon -r -1 -X)
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output

def config(args=[], pout=True):
    output = """
Usage: pcs config [commands]...
View and manage cluster configuration

Commands:
    [show]
        View full cluster configuration

    backup [filename]
        Creates the tarball containing the cluster configuration files.
        If filename is not specified the standard output will be used.

    restore [--local] [filename]
        Restores the cluster configuration files on all nodes from the backup.
        If filename is not specified the standard input will be used.
        If --local is specified only the files on the current node will
        be restored.

    checkpoint
        List all available configuration checkpoints.

    checkpoint view <checkpoint_number>
        Show specified configuration checkpoint.

    checkpoint restore <checkpoint_number>
        Restore cluster configuration to specified checkpoint.

    import-cman output=<filename> [input=<filename>] [--interactive]
            [output-format=corosync.conf|cluster.conf]
        Converts CMAN cluster configuration to Pacemaker cluster configuration.
        Converted configuration will be saved to 'output' file.  To send
        the configuration to the cluster nodes the 'pcs config restore'
        command can be used.  If --interactive is specified you will be
        prompted to solve incompatibilities manually.  If no input is specified
        /etc/cluster/cluster.conf will be used.  You can force to create output
        containing either cluster.conf or corosync.conf using the output-format
        option.
"""
    if pout:
        print sub_usage(args, output)
    else:
        return output
