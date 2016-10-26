from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re


examples = ""
def full_usage():
    out = ""
    out += main(False)
    out += strip_extras(resource([],False))
    out += strip_extras(cluster([],False))
    out += strip_extras(stonith([],False))
    out += strip_extras(property([],False))
    out += strip_extras(constraint([],False))
    out += strip_extras(node([],False))
    out += strip_extras(acl([],False))
    out += strip_extras(qdevice([],False))
    out += strip_extras(quorum([],False))
    out += strip_extras(booth([],False))
    out += strip_extras(status([],False))
    out += strip_extras(config([],False))
    out += strip_extras(pcsd([],False))
    out += strip_extras(alert([], False))
    print(out.strip())
    print("Examples:\n" + examples.replace(" \ ",""))

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
    return max(dict_depth(v, depth+1) for k, v in d.items())

def generate_completion_tree_from_usage():
    tree = {}
    tree["resource"] = generate_tree(resource([],False))
    tree["cluster"] = generate_tree(cluster([],False))
    tree["stonith"] = generate_tree(stonith([],False))
    tree["property"] = generate_tree(property([],False))
    tree["acl"] = generate_tree(acl([],False))
    tree["constraint"] = generate_tree(constraint([],False))
    tree["qdevice"] = generate_tree(qdevice([],False))
    tree["quorum"] = generate_tree(quorum([],False))
    tree["status"] = generate_tree(status([],False))
    tree["config"] = generate_tree(config([],False))
    tree["pcsd"] = generate_tree(pcsd([],False))
    tree["node"] = generate_tree(node([], False))
    tree["alert"] = generate_tree(alert([], False))
    tree["booth"] = generate_tree(booth([], False))
    return tree

def generate_tree(usage_txt):
    ignore = True
    ret_hash = {}
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
    -h, --help  Display usage and exit.
    -f file     Perform actions on file instead of active CIB.
    --debug     Print all network traffic and external commands run.
    --version   Print pcs version information.

Commands:
    cluster     Configure cluster options and nodes.
    resource    Manage cluster resources.
    stonith     Configure fence devices.
    constraint  Set resource constraints.
    property    Set pacemaker properties.
    acl         Set pacemaker access control lists.
    qdevice     Manage quorum device provider.
    quorum      Manage cluster quorum settings.
    booth       Manage booth (cluster ticket manager).
    status      View cluster status.
    config      View and manage cluster configuration.
    pcsd        Manage pcs daemon.
    node        Manage cluster nodes.
    alert       Set pacemaker alerts.
"""
# Advanced usage to possibly add later
#  --corosync_conf=<corosync file> Specify alternative corosync.conf file
    if pout:
        print(output)
    else:
        return output


def resource(args = [], pout = True):
    output = """
Usage: pcs resource [commands]...
Manage pacemaker resources

Commands:
    [show [<resource id>] | --full | --groups | --hide-inactive]
        Show all currently configured resources or if a resource is specified
        show the options for the configured resource.  If --full is specified,
        all configured resource options will be displayed.  If --groups is
        specified, only show groups (and their resources).  If --hide-inactive
        is specified, only show active resources.

    list [filter] [--nodesc]
        Show list of all available resource agents (if filter is provided then
        only resource agents matching the filter will be shown). If --nodesc is
        used then descriptions of resource agents are not printed.

    describe [<standard>:[<provider>:]]<type>
        Show options for the specified resource.

    create <resource id> [<standard>:[<provider>:]]<type> [resource options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...]
           [--clone <clone options> | --master <master options> |
           --group <group id> [--before <resource id> | --after <resource id>]
           ] [--disabled] [--wait[=n]]
        Create specified resource.  If --clone is used a clone resource is
        created.  If --master is specified a master/slave resource is created.
        If --group is specified the resource is added to the group named.  You
        can use --before or --after to specify the position of the added
        resource relatively to some resource already existing in the group.
        If --disabled is specified the resource is not started automatically.
        If --wait is specified, pcs will wait up to 'n' seconds for the resource
        to start and then return 0 if the resource is started, or 1 if
        the resource has not yet started.  If 'n' is not specified it defaults
        to 60 minutes.
        Example: Create a new resource called 'VirtualIP' with IP address
            192.168.0.99, netmask of 32, monitored everything 30 seconds,
            on eth2:
            pcs resource create VirtualIP ocf:heartbeat:IPaddr2 \\
                ip=192.168.0.99 cidr_netmask=32 nic=eth2 \\
                op monitor interval=30s

    delete <resource id|group id|master id|clone id>
        Deletes the resource, group, master or clone (and all resources within
        the group/master/clone).

    enable <resource id> [--wait[=n]]
        Allow the cluster to start the resource. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resource may
        remain stopped.  If --wait is specified, pcs will wait up to 'n' seconds
        for the resource to start and then return 0 if the resource is started,
        or 1 if the resource has not yet started.  If 'n' is not specified it
        defaults to 60 minutes.

    disable <resource id> [--wait[=n]]
        Attempt to stop the resource if it is running and forbid the cluster
        from starting it again.  Depending on the rest of the configuration
        (constraints, options, failures, etc), the resource may remain
        started.  If --wait is specified, pcs will wait up to 'n' seconds for
        the resource to stop and then return 0 if the resource is stopped or 1
        if the resource has not stopped.  If 'n' is not specified it defaults
        to 60 minutes.

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

    debug-stop <resource id> [--full]
        This command will force the specified resource to stop on this node
        ignoring the cluster recommendations and print the output from
        stopping the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to stop.

    debug-promote <resource id> [--full]
        This command will force the specified resource to be promoted on this
        node ignoring the cluster recommendations and print the output from
        promoting the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to promote.

    debug-demote <resource id> [--full]
        This command will force the specified resource to be demoted on this
        node ignoring the cluster recommendations and print the output from
        demoting the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to demote.

    debug-monitor <resource id> [--full]
        This command will force the specified resource to be moniored on this
        node  ignoring the cluster recommendations and print the output from
        monitoring the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to be monitored.

    move <resource id> [destination node] [--master] [lifetime=<lifetime>]
         [--wait[=n]]
        Move the resource off the node it is currently running on by creating a
        -INFINITY location constraint to ban the node.  If destination node is
        specified the resource will be moved to that node by creating an
        INFINITY location constraint to prefer the destination node.  If
        --master is used the scope of the command is limited to the master role
        and you must use the master id (instead of the resource id).  If
        lifetime is specified then the constraint will expire after that time,
        otherwise it defaults to infinity and the constraint can be cleared
        manually with 'pcs resource clear' or 'pcs constraint delete'.  If
        --wait is specified, pcs will wait up to 'n' seconds for the resource
        to move and then return 0 on success or 1 on error.  If 'n' is not
        specified it defaults to 60 minutes.
        If you want the resource to preferably avoid running on some nodes but
        be able to failover to them use 'pcs location avoids'.

    ban <resource id> [node] [--master] [lifetime=<lifetime>] [--wait[=n]]
        Prevent the resource id specified from running on the node (or on the
        current node it is running on if no node is specified) by creating a
        -INFINITY location constraint.  If --master is used the scope of the
        command is limited to the master role and you must use the master id
        (instead of the resource id).  If lifetime is specified then the
        constraint will expire after that time, otherwise it defaults to
        infinity and the constraint can be cleared manually with 'pcs resource
        clear' or 'pcs constraint delete'.  If --wait is specified, pcs will
        wait up to 'n' seconds for the resource to move and then return 0
        on success or 1 on error. If 'n' is not specified it defaults to 60
        minutes.
        If you want the resource to preferably avoid running on some nodes but
        be able to failover to them use 'pcs location avoids'.

    clear <resource id> [node] [--master] [--wait[=n]]
        Remove constraints created by move and/or ban on the specified
        resource (and node if specified).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id).
        If --wait is specified, pcs will wait up to 'n' seconds for the
        operation to finish (including starting and/or moving resources if
        appropriate) and then return 0 on success or 1 on error.  If 'n' is not
        specified it defaults to 60 minutes.

    standards
        List available resource agent standards supported by this installation
        (OCF, LSB, etc.).

    providers
        List available OCF resource agent providers.

    agents [standard[:provider]]
        List available agents optionally filtered by standard and provider.

    update <resource id> [resource options] [op [<operation action>
           <operation options>]...] [meta <meta operations>...] [--wait[=n]]
        Add/Change options to specified resource, clone or multi-state
        resource.  If an operation (op) is specified it will update the first
        found operation with the same action on the specified resource, if no
        operation with that action exists then a new operation will be created.
        (WARNING: all existing options on the updated operation will be reset
        if not specified.)  If you want to create multiple monitor operations
        you should use the 'op add' & 'op remove' commands.  If --wait is
        specified, pcs will wait up to 'n' seconds for the changes to take
        effect and then return 0 if the changes have been processed or 1
        otherwise.  If 'n' is not specified it defaults to 60 minutes.

    op add <resource id> <operation action> [operation properties]
        Add operation for specified resource.

    op remove <resource id> <operation action> [<operation properties>...]
        Remove specified operation (note: you must specify the exact operation
        properties to properly remove an existing operation).

    op remove <operation id>
        Remove the specified operation id.

    op defaults [options]
        Set default values for operations, if no options are passed, lists
        currently configured defaults.

    meta <resource id | group id | master id | clone id> <meta options>
         [--wait[=n]]
        Add specified options to the specified resource, group, master/slave
        or clone.  Meta options should be in the format of name=value, options
        may be removed by setting an option without a value.  If --wait is
        specified, pcs will wait up to 'n' seconds for the changes to take
        effect and then return 0 if the changes have been processed or 1
        otherwise.  If 'n' is not specified it defaults to 60 minutes.
        Example: pcs resource meta TestResource failure-timeout=50 stickiness=

    group add <group id> <resource id> [resource id] ... [resource id]
              [--before <resource id> | --after <resource id>] [--wait[=n]]
        Add the specified resource to the group, creating the group if it does
        not exist.  If the resource is present in another group it is moved
        to the new group.  You can use --before or --after to specify
        the position of the added resources relatively to some resource already
        existing in the group.  If --wait is specified, pcs will wait up to 'n'
        seconds for the operation to finish (including moving resources if
        appropriate) and then return 0 on success or 1 on error.  If 'n' is not
        specified it defaults to 60 minutes.

    group remove <group id> <resource id> [resource id] ... [resource id]
          [--wait[=n]]
        Remove the specified resource(s) from the group, removing the group if
        it no resources remain.  If --wait is specified, pcs will wait up to 'n'
        seconds for the operation to finish (including moving resources if
        appropriate) and then return 0 on success or 1 on error.  If 'n' is not
        specified it defaults to 60 minutes.

    ungroup <group id> [resource id] ... [resource id] [--wait[=n]]
        Remove the group (note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group.  If --wait is specified, pcs will wait up to 'n' seconds
        for the operation to finish (including moving resources if appropriate)
        and the return 0 on success or 1 on error.  If 'n' is not specified it
        defaults to 60 minutes.

    clone <resource id | group id> [clone options]... [--wait[=n]]
        Setup up the specified resource or group as a clone.  If --wait is
        specified, pcs will wait up to 'n' seconds for the operation to finish
        (including starting clone instances if appropriate) and then return 0
        on success or 1 on error.  If 'n' is not specified it defaults to 60
        minutes.

    unclone <resource id | group id> [--wait[=n]]
        Remove the clone which contains the specified group or resource (the
        resource or group will not be removed).  If --wait is specified, pcs
        will wait up to 'n' seconds for the operation to finish (including
        stopping clone instances if appropriate) and then return 0 on success
        or 1 on error.  If 'n' is not specified it defaults to 60 minutes.

    master [<master/slave id>] <resource id | group id> [options] [--wait[=n]]
        Configure a resource or group as a multi-state (master/slave) resource.
        If --wait is specified, pcs will wait up to 'n' seconds for the operation
        to finish (including starting and promoting resource instances if
        appropriate) and then return 0 on success or 1 on error.  If 'n' is not
        specified it defaults to 60 minutes.
        Note: to remove a master you must remove the resource/group it contains.

    manage <resource id> ... [resource n]
        Set resources listed to managed mode (default).

    unmanage <resource id> ... [resource n]
        Set resources listed to unmanaged mode.

    defaults [options]
        Set default values for resources, if no options are passed, lists
        currently configured defaults.

    cleanup [<resource id>] [--node <node>]
        Cleans up the resource in the lrmd (useful to reset the resource status
        and failcount).  This tells the cluster to forget the operation history
        of a resource and re-detect its current state.  This can be useful to
        purge knowledge of past failures that have since been resolved.  If a
        resource id is not specified then all resources/stonith devices will be
        cleaned up.  If a node is not specified then resources on all nodes
        will be cleaned up.

    failcount show <resource id> [node]
        Show current failcount for specified resource from all nodes or
        only on specified node.

    failcount reset <resource id> [node]
        Reset failcount for specified resource on all nodes or only on
        specified node.  This tells the cluster to forget how many times
        a resource has failed in the past.  This may allow the resource to
        be started or moved to a more preferred location.

    relocate dry-run [resource1] [resource2] ...
        The same as 'relocate run' but has no effect on the cluster.

    relocate run [resource1] [resource2] ...
        Relocate specified resources to their preferred nodes.  If no resources
        are specified, relocate all resources.
        This command calculates the preferred node for each resource while
        ignoring resource stickiness.  Then it creates location constraints
        which will cause the resources to move to their preferred nodes.  Once
        the resources have been moved the constraints are deleted automatically.
        Note that the preferred node is calculated based on current cluster
        status, constraints, location of resources and other settings and thus
        it might change over time.

    relocate show
        Display current status of resources and their optimal node ignoring
        resource stickiness.

    relocate clear
        Remove all constraints created by the 'relocate run' command.

    utilization [<resource id> [<name>=<value> ...]]
        Add specified utilization options to specified resource. If resource is
        not specified, shows utilization of all resources. If utilization
        options are not specified, shows utilization of specified resource.
        Utilization option should be in format name=value, value has to be
        integer. Options may be removed by setting an option without a value.
        Example: pcs resource utilization TestResource cpu= ram=20

Examples:

    pcs resource show
      Show all resources.

    pcs resource show VirtualIP
      Show options specific to the 'VirtualIP' resource.


    pcs resource create VirtualIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s
      Create a new resource called 'VirtualIP' with options.

    pcs resource create VirtualIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s
      Create a new resource called 'VirtualIP' with options.

    pcs resource update VirtualIP ip=192.168.0.98 nic=
      Change the ip address of VirtualIP and remove the nic option.

    pcs resource delete VirtualIP
      Delete the VirtualIP resource.

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
        print(sub_usage(args, output))
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

    setup [--start [--wait[=<n>]]] [--local] [--enable] --name <cluster name>
            <node1[,node1-altaddr]> [<node2[,node2-altaddr]>] [...]
            [--transport udpu|udp] [--rrpmode active|passive]
            [--addr0 <addr/net> [[[--mcast0 <address>] [--mcastport0 <port>]
                            [--ttl0 <ttl>]] | [--broadcast0]]
            [--addr1 <addr/net> [[[--mcast1 <address>] [--mcastport1 <port>]
                            [--ttl1 <ttl>]] | [--broadcast1]]]]
            [--wait_for_all=<0|1>] [--auto_tie_breaker=<0|1>]
            [--last_man_standing=<0|1> [--last_man_standing_window=<time in ms>]]
            [--ipv6] [--token <timeout>] [--token_coefficient <timeout>]
            [--join <timeout>] [--consensus <timeout>] [--miss_count_const <count>]
            [--fail_recv_const <failures>]
        Configure corosync and sync configuration out to listed nodes.
        --local will only perform changes on the local node,
        --start will also start the cluster on the specified nodes,
        --wait will wait up to 'n' seconds for the nodes to start,
        --enable will enable corosync and pacemaker on node startup,
        --transport allows specification of corosync transport (default: udpu;
            udp for CMAN clusters),
        --rrpmode allows you to set the RRP mode of the system. Currently only
            'passive' is supported or tested (using 'active' is not
            recommended).
        The --wait_for_all, --auto_tie_breaker, --last_man_standing,
            --last_man_standing_window options are all documented in corosync's
            votequorum(5) man page. These options are not supported on CMAN
            clusters.
        --ipv6 will configure corosync to use ipv6 (instead of ipv4). This
            option is not supported on CMAN clusters.
        --token <timeout> sets time in milliseconds until a token loss is
            declared after not receiving a token (default 1000 ms)
        --token_coefficient <timeout> sets time in milliseconds used for clusters
            with at least 3 nodes as a coefficient for real token timeout calculation
            (token + (number_of_nodes - 2) * token_coefficient) (default 650 ms)
            This option is not supported on CMAN clusters.
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

        When using udpu specifying nodes, specify the ring 0 address first
        followed by a ',' and then the ring 1 address.

        Example: pcs cluster setup --name cname nodeA-0,nodeA-1 nodeB-0,nodeB-1

        When using udp, using --addr0 and --addr1 will allow you to configure
        rrp mode for corosync.  It's recommended to use a network (instead of
        IP address) for --addr0 and --addr1 so the same corosync.conf file can
        be used around the cluster.  --mcast0 defaults to 239.255.1.1 and
        --mcast1 defaults to 239.255.2.1, --mcastport0/1 default to 5405 and
        ttl defaults to 1. If --broadcast is specified, --mcast0/1,
        --mcastport0/1 & --ttl0/1 are ignored.

    start [--all] [node] [...] [--wait[=<n>]]
        Start corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are started on the local node.
        If --all is specified then corosync & pacemaker are started on all
        nodes.  If --wait is specified, wait up to 'n' seconds for nodes
        to start.

    stop [--all] [node] [...]
        Stop corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are stopped on the local node.
        If --all is specified then corosync & pacemaker are stopped on all
        nodes.

    kill
        Force corosync and pacemaker daemons to stop on the local node
        (performs kill -9). Note that init system (e.g. systemd) can detect that
        cluster is not running and start it again. If you want to stop cluster
        on a node, run pcs cluster stop on that node.

    enable [--all] [node] [...]
        Configure corosync & pacemaker to run on node boot on specified
        node(s), if node is not specified then corosync & pacemaker are
        enabled on the local node. If --all is specified then corosync &
        pacemaker are enabled on all nodes.

    disable [--all] [node] [...]
        Configure corosync & pacemaker to not run on node boot on specified
        node(s), if node is not specified then corosync & pacemaker are
        disabled on the local node. If --all is specified then corosync &
        pacemaker are disabled on all nodes. Note: this is the default after
        installation.

    remote-node add <hostname> <resource id> [options]
        Enables the specified resource as a remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n').

    remote-node remove <hostname>
        Disables any resources configured to be remote-node resource on the
        specified hostname (hostname should be the same as 'uname -n').

    status
        View current cluster status (an alias of 'pcs status cluster').

    pcsd-status [node] [...]
        Get current status of pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified.

    sync
        Sync corosync configuration to all nodes found from current
        corosync.conf file (cluster.conf on systems running Corosync 1.x).

    cib [filename] [scope=<scope> | --config]
        Get the raw xml from the CIB (Cluster Information Base).  If a filename
        is provided, we save the CIB to that file, otherwise the CIB is
        printed.  Specify scope to get a specific section of the CIB.  Valid
        values of the scope are: configuration, nodes, resources, constraints,
        crm_config, rsc_defaults, op_defaults, status.  --config is the same as
        scope=configuration.  Do not specify a scope if you want to edit
        the saved CIB using pcs (pcs -f <command>).

    cib-push <filename> [scope=<scope> | --config] [--wait[=<n>]]
        Push the raw xml from <filename> to the CIB (Cluster Information Base).
        You can obtain the CIB by running the 'pcs cluster cib' command, which
        is recommended first step when you want to perform desired
        modifications (pcs -f <command>) for the one-off push.
        Specify scope to push a specific section of the CIB.  Valid values
        of the scope are: configuration, nodes, resources, constraints,
        crm_config, rsc_defaults, op_defaults.  --config is the same as
        scope=configuration.  Use of --config is recommended.  Do not specify
        a scope if you need to push the whole CIB or be warned in the case
        of outdated CIB. If --wait is specified wait up to 'n' seconds for
        changes to be applied.
        WARNING: the selected scope of the CIB will be overwritten by the
        current content of the specified file.

    cib-upgrade
        Upgrade the CIB to conform to the latest version of the document schema.

    edit [scope=<scope> | --config]
        Edit the cib in the editor specified by the $EDITOR environment
        variable and push out any changes upon saving.  Specify scope to edit
        a specific section of the CIB.  Valid values of the scope are:
        configuration, nodes, resources, constraints, crm_config, rsc_defaults,
        op_defaults.  --config is the same as scope=configuration.  Use of
        --config is recommended.  Do not specify a scope if you need to edit
        the whole CIB or be warned in the case of outdated CIB.

    node add <node[,node-altaddr]> [--start [--wait[=<n>]]] [--enable]
            [--watchdog=<watchdog-path>]
        Add the node to corosync.conf and corosync on all nodes in the cluster
        and sync the new corosync.conf to the new node.  If --start is
        specified also start corosync/pacemaker on the new node, if --wait is
        sepcified wait up to 'n' seconds for the new node to start.  If --enable
        is specified enable corosync/pacemaker on new node.
        When using Redundant Ring Protocol (RRP) with udpu transport, specify
        the ring 0 address first followed by a ',' and then the ring 1 address.
        Use --watchdog to specify path to watchdog on newly added node, when SBD
        is enabled in cluster.

    node remove <node>
        Shutdown specified node and remove it from pacemaker and corosync on
        all other nodes in the cluster.

    uidgid
        List the current configured uids and gids of users allowed to connect
        to corosync.

    uidgid add [uid=<uid>] [gid=<gid>]
        Add the specified uid and/or gid to the list of users/groups
        allowed to connect to corosync.

    uidgid rm [uid=<uid>] [gid=<gid>]
        Remove the specified uid and/or gid from the list of users/groups
        allowed to connect to corosync.

    corosync [node]
        Get the corosync.conf from the specified node or from the current node
        if node not specified.

    reload corosync
        Reload the corosync configuration on the current node.

    destroy [--all]
        Permanently destroy the cluster on the current node, killing all
        corosync/pacemaker processes removing all cib files and the
        corosync.conf file.  Using --all will attempt to destroy the
        cluster on all nodes configure in the corosync.conf file.
        WARNING: This command permantly removes any cluster configuration that
        has been created. It is recommended to run 'pcs cluster stop' before
        destroying the cluster.

    verify [-V] [filename]
        Checks the pacemaker configuration (cib) for syntax and common
        conceptual errors.  If no filename is specified the check is
        performed on the currently running cluster.  If -V is used
        more verbose output will be printed.

    report [--from "YYYY-M-D H:M:S" [--to "YYYY-M-D" H:M:S"]] dest
        Create a tarball containing everything needed when reporting cluster
        problems.  If --from and --to are not used, the report will include
        the past 24 hours.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def stonith(args = [], pout = True):
    output = """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    [show [stonith id]] [--full]
        Show all currently configured stonith devices or if a stonith id is
        specified show the options for the configured stonith device.  If
        --full is specified all configured stonith options will be displayed.

    list [filter] [--nodesc]
        Show list of all available stonith agents (if filter is provided then
        only stonith agents matching the filter will be shown). If --nodesc is
        used then descriptions of stonith agents are not printed.

    describe <stonith agent>
        Show options for specified stonith agent.

    create <stonith id> <stonith device type> [stonith device options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...]
        Create stonith device with specified type and options.

    update <stonith id> [stonith device options]
        Add/Change options to specified stonith id.

    delete <stonith id>
        Remove stonith id from configuration.

    cleanup [<stonith id>] [--node <node>]
        Cleans up the stonith device in the lrmd (useful to reset the status
        and failcount).  This tells the cluster to forget the operation history
        of a stonith device and re-detect its current state.  This can be
        useful to purge knowledge of past failures that have since been
        resolved.  If a stonith id is not specified then all resources/stonith
        devices will be cleaned up.  If a node is not specified then resources
        on all nodes will be cleaned up.

    level
        Lists all of the fencing levels currently configured.

    level add <level> <node> <devices>
        Add the fencing level for the specified node with a comma separated
        list of devices (stonith ids) to attempt for that node at that level.
        Fence levels are attempted in numerical order (starting with 1) if
        a level succeeds (meaning all devices are successfully fenced in that
        level) then no other levels are tried, and the node is considered
        fenced.

    level remove <level> [node id] [stonith id] ... [stonith id]
        Removes the fence level for the level, node and/or devices specified.
        If no nodes or devices are specified then the fence level is removed.

    level clear [node|stonith id(s)]
        Clears the fence levels on the node (or stonith id) specified or clears
        all fence levels if a node/stonith id is not specified.  If more than
        one stonith id is specified they must be separated by a comma and no
        spaces.  Example: pcs stonith level clear dev_a,dev_b

    level verify
        Verifies all fence devices and nodes specified in fence levels exist.

    fence <node> [--off]
        Fence the node specified (if --off is specified, use the 'off' API
        call to stonith which will turn the node off instead of rebooting it).

    confirm <node> [--force]
        Confirm that the host specified is currently down.  This command
        should ONLY be used when the node specified has already been confirmed
        to be powered off and to have no access to shared resources.

        WARNING: If this node is not actually powered off or it does have
        access to shared resources, data corruption/cluster failure can occur.
        To prevent accidental running of this command, --force or interactive
        user response is required in order to proceed.

    sbd enable [--watchdog=<path>[@<node>]] ... [<SBD_OPTION>=<value>] ...
        Enable SBD in cluster. Default path for watchdog device is
        /dev/watchdog. Allowed SBD options: SBD_WATCHDOG_TIMEOUT (default: 5),
        SBD_DELAY_START (default: no) and SBD_STARTMODE (default: clean).

        WARNING: Cluster has to be restarted in order to apply these changes.

        Example of enabling SBD in cluster with watchdogs on node1 will be
        /dev/watchdog2, on node2 /dev/watchdog1, /dev/watchdog0 on all other
        nodes and watchdog timeout will bet set to 10 seconds:
        pcs stonith sbd enable \\
            --watchdog=/dev/watchdog2@node1 \\
            --watchdog=/dev/watchdog1@node2 \\
            --watchdog=/dev/watchdog0 \\
            SBD_WATCHDOG_TIMEOUT=10

    sbd disable
        Disable SBD in cluster.

        WARNING: Cluster has to be restarted in order to apply these changes.

    sbd status
        Show status of SBD services in cluster.

    sbd config
        Show SBD configuration in cluster.

Examples:
    pcs stonith create MyStonith fence_virt pcmk_host_list=f1
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def property(args = [], pout = True):
    output = """
Usage: pcs property [commands]...
Configure pacemaker properties

Commands:
    [list|show [<property> | --all | --defaults]] | [--all | --defaults]
        List property settings (default: lists configured properties).
        If --defaults is specified will show all property defaults, if --all
        is specified, current configured properties will be shown with unset
        properties and their defaults.
        Run 'man pengine' and 'man crmd' to get a description of the properties.

    set [--force | --node <nodename>] <property>=[<value>]
            [<property>=[<value>] ...]
        Set specific pacemaker properties (if the value is blank then the
        property is removed from the configuration).  If a property is not
        recognized by pcs the property will not be created unless the
        --force is used.  If --node is used a node attribute is set on
        the specified node.
        Run 'man pengine' and 'man crmd' to get a description of the properties.

    unset [--node <nodename>] <property>
        Remove property from configuration (or remove attribute from
        specified node if --node is used).
        Run 'man pengine' and 'man crmd' to get a description of the properties.

Examples:
    pcs property set stonith-enabled=false
"""
    if pout:
        print(sub_usage(args, output))
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
        node and score (default score: INFINITY).

    location <resource id> avoids <node[=score]>...
        Create a location constraint on a resource to avoid the specified
        node and score (default score: INFINITY).

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
        weekdays, yeardays, months, weeks, years, weekyears, moon.
        If score is omitted it defaults to INFINITY. If id is omitted one is
        generated from the resource id. If resource-discovery is omitted it
        defaults to 'always'.

    location [show [resources|nodes [node id|resource id]...] [--full]]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node.  If specific
        nodes or resources are specified then we only show information about
        them.  If --full is specified show the internal constraint id's as well.

    location add <id> <resource id> <node> <score> [resource-discovery=<option>]
        Add a location constraint with the appropriate id, resource id,
        node name and score. (For more advanced pacemaker usage.)

    location remove <id> [<resource id> <node> <score>]
        Remove a location constraint with the appropriate id, resource id,
        node name and score. (For more advanced pacemaker usage.)

    order [show] [--full]
        List all current ordering constraints (if --full is specified show
        the internal constraint id's as well).

    order [action] <resource id> then [action] <resource id> [options]
        Add an ordering constraint specifying actions (start, stop, promote,
        demote) and if no action is specified the default action will be
        start.
        Available options are kind=Optional/Mandatory/Serialize,
        symmetrical=true/false, require-all=true/false and id=<constraint-id>.

    order set <resource1> [resourceN]... [options] [set
              <resourceX> ... [options]]
              [setoptions [constraint_options]]
        Create an ordered set of resources.
        Available options are sequential=true/false, require-all=true/false,
        action=start/promote/demote/stop and role=Stopped/Started/Master/Slave.
        Available constraint_options are id=<constraint-id>,
        kind=Optional/Mandatory/Serialize and symmetrical=true/false.

    order remove <resource1> [resourceN]...
        Remove resource from any ordering constraint

    colocation [show] [--full]
        List all current colocation constraints (if --full is specified show
        the internal constraint id's as well).

    colocation add [master|slave] <source resource id> with [master|slave]
                   <target resource id> [score] [options] [id=constraint-id]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score forces <source resource> to
        run (or not run) with <target resource> (score defaults to "INFINITY").
        A role can be master or slave (if no role is specified, it defaults to
        'started').

    colocation set <resource1> [resourceN]... [options]
               [set <resourceX> ... [options]]
               [setoptions [constraint_options]]
        Create a colocation constraint with a resource set.
        Available options are sequential=true/false, require-all=true/false,
        action=start/promote/demote/stop and role=Stopped/Started/Master/Slave.
        Available constraint_options are id, score, score-attribute and
        score-attribute-mangle.

    colocation remove <source resource id> <target resource id>
        Remove colocation constraints with specified resources.

    ticket [show] [--full]
        List all current ticket constraints (if --full is specified show
        the internal constraint id's as well).

    ticket add <ticket> [<role>] <resource id> [<options>]
               [id=<constraint-id>]
        Create a ticket constraint for <resource id>.
        Available option is loss-policy=fence/stop/freeze/demote.
        A role can be master, slave, started or stopped.

    ticket set <resource1> [<resourceN>]... [<options>]
               [set <resourceX> ... [<options>]]
               setoptions <constraint_options>
        Create a ticket constraint with a resource set.
        Available options are sequential=true/false, require-all=true/false,
        action=start/promote/demote/stop and role=Stopped/Started/Master/Slave.
        Required constraint option is ticket=<ticket>. Optional constraint
        options are id=<constraint-id> and loss-policy=fence/stop/freeze/demote.

    ticket remove <ticket> <resource id>
        Remove all ticket constraints with <ticket> from <resource id>.

    remove [constraint id]...
        Remove constraint(s) or constraint rules with the specified id(s).

    ref <resource>...
        List constraints referencing specified resource.

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
        constraint, the constraint will be removed.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def acl(args = [], pout = True):
    output = """
Usage: pcs acl [commands]...
View and modify current cluster access control lists
Commands:

    [show]
        List all current access control lists.

    enable
        Enable access control lists.

    disable
        Disable access control lists.

    role create <role id> [description=<description>] [((read | write | deny)
                                                (xpath <query> | id <id>))...]
        Create a role with the id and (optional) description specified.
        Each role can also have an unlimited number of permissions
        (read/write/deny) applied to either an xpath query or the id
        of a specific element in the cib.

    role delete <role id>
        Delete the role specified and remove it from any users/groups it was
        assigned to.

    role assign <role id> [to] [user|group] <username/group>
        Assign a role to a user or group already created with 'pcs acl
        user/group create'. If there is user and group with the same id and it
        is not specified which should be used, user will be prioritized. In
        cases like this specify whenever user or group should be used.

    role unassign <role id> [from] [user|group] <username/group>
        Remove a role from the specified user. If there is user and group with
        the same id and it is not specified which should be used, user will be
        prioritized. In cases like this specify whenever user or group should
        be used.

    user create <username> [<role id>]...
        Create an ACL for the user specified and assign roles to the user.

    user delete <username>
        Remove the user specified (and roles assigned will be unassigned for
        the specified user).

    group create <group> [<role id>]...
        Create an ACL for the group specified and assign roles to the group.

    group delete <group>
        Remove the group specified (and roles assigned will be unassigned for
        the specified group).

    permission add <role id> ((read | write | deny) (xpath <query> |
                                                                id <id>))...
        Add the listed permissions to the role specified.

    permission delete <permission id>
        Remove the permission id specified (permission id's are listed in
        parenthesis after permissions in 'pcs acl' output).
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def status(args = [], pout = True):
    output = """
Usage: pcs status [commands]...
View current cluster and resource status
Commands:
    [status] [--full | --hide-inactive]
        View all information about the cluster and resources (--full provides
        more details, --hide-inactive hides inactive resources).

    resources [<resource id> | --full | --groups | --hide-inactive]
        Show all currently configured resources or if a resource is specified
        show the options for the configured resource.  If --full is specified,
        all configured resource options will be displayed.  If --groups is
        specified, only show groups (and their resources).  If --hide-inactive
        is specified, only show active resources.

    groups
        View currently configured groups and their resources.

    cluster
        View current cluster status.

    corosync
        View current membership information as seen by corosync.

    quorum
        View current quorum status.

    qdevice <device model> [--full] [<cluster name>]
        Show runtime status of specified model of quorum device provider.  Using
        --full will give more detailed output.  If <cluster name> is specified,
        only information about the specified cluster will be displayed.

    nodes [corosync|both|config]
        View current status of nodes from pacemaker. If 'corosync' is
        specified, print nodes currently configured in corosync, if 'both'
        is specified, print nodes from both corosync & pacemaker.  If 'config'
        is specified, print nodes from corosync & pacemaker configuration.

    pcsd [<node>] ...
        Show the current status of pcsd on the specified nodes.
        When no nodes are specified, status of all nodes is displayed.

    xml
        View xml version of status (output from crm_mon -r -1 -X).
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def config(args=[], pout=True):
    output = """
Usage: pcs config [commands]...
View and manage cluster configuration

Commands:
    [show]
        View full cluster configuration.

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
            [output-format=corosync.conf|cluster.conf] [dist=<dist>]
        Converts CMAN cluster configuration to Pacemaker cluster configuration.
        Converted configuration will be saved to 'output' file.  To send
        the configuration to the cluster nodes the 'pcs config restore'
        command can be used.  If --interactive is specified you will be
        prompted to solve incompatibilities manually.  If no input is specified
        /etc/cluster/cluster.conf will be used.  You can force to create output
        containing either cluster.conf or corosync.conf using the output-format
        option.  Optionally you can specify output version by setting 'dist'
        option e. g. rhel,6.8 or redhat,7.3 or debian,7 or ubuntu,trusty.  You
        can get the list of supported dist values by running the "clufter
        --list-dists" command.  If 'dist' is not specified, it defaults to this
        node's version if that matches output-format, otherwise redhat,6.7 is
        used for cluster.conf and redhat,7.1 is used for corosync.conf.

    import-cman output=<filename> [input=<filename>] [--interactive]
            output-format=pcs-commands|pcs-commands-verbose [dist=<dist>]
        Converts CMAN cluster configuration to a list of pcs commands which
        recreates the same cluster as Pacemaker cluster when executed.  Commands
        will be saved to 'output' file.  For other options see above.

    export pcs-commands|pcs-commands-verbose [output=<filename>] [dist=<dist>]
        Creates a list of pcs commands which upon execution recreates
        the current cluster running on this node.  Commands will be saved
        to 'output' file or written to stdout if 'output' is not specified.  Use
        pcs-commands to get a simple list of commands, whereas
        pcs-commands-verbose creates a list including comments and debug
        messages.  Optionally specify output version by setting 'dist' option
        e. g. rhel,6.8 or redhat,7.3 or debian,7 or ubuntu,trusty.  You can get
        the list of supported dist values by running the "clufter --list-dists"
        command.  If 'dist' is not specified, it defaults to this node's
        version.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def pcsd(args=[], pout=True):
    output = """
Usage: pcs pcsd [commands]...
Manage pcs daemon

Commands:
    certkey <certificate file> <key file>
        Load custom certificate and key files for use in pcsd.

    sync-certificates
        Sync pcsd certificates to all nodes found from current corosync.conf
        file (cluster.conf on systems running Corosync 1.x).  WARNING: This will
        restart pcsd daemon on the nodes.

    clear-auth [--local] [--remote]
       Removes all system tokens which allow pcs/pcsd on the current system to
       authenticate with remote pcs/pcsd instances and vice-versa.  After this
       command is run this node will need to be re-authenticated with other
       nodes (using 'pcs cluster auth').  Using --local only removes tokens
       used by local pcs (and pcsd if root) to connect to other pcsd instances,
       using --remote clears authentication tokens used by remote systems to
       connect to the local pcsd instance.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def node(args=[], pout=True):
    output = """
Usage: pcs node <command>
Manage cluster nodes

Commands:
    attribute [[<node>] [--name <name>] | <node> <name>=<value> ...]
        Manage node attributes.  If no parameters are specified, show attributes
        of all nodes.  If one parameter is specified, show attributes
        of specified node.  If --name is specified, show specified attribute's
        value from all nodes.  If more parameters are specified, set attributes
        of specified node.  Attributes can be removed by setting an attribute
        without a value.

    maintenance [--all] | [<node>]...
        Put specified node(s) into maintenance mode, if no node or options are
        specified the current node will be put into maintenance mode, if --all
        is specified all nodes will be put into maintenace mode.

    unmaintenance [--all] | [<node>]...
        Remove node(s) from maintenance mode, if no node or options are
        specified the current node will be removed from maintenance mode,
        if --all is specified all nodes will be removed from maintenance mode.

    standby [--all | <node>] [--wait[=n]]
        Put specified node into standby mode (the node specified will no longer
        be able to host resources), if no node or options are specified the
        current node will be put into standby mode, if --all is specified all
        nodes will be put into standby mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be put into standby mode and then return 0 on success or 1 if
        the operation not succeeded yet.  If 'n' is not specified it defaults
        to 60 minutes.

    unstandby [--all | <node>] [--wait[=n]]
        Remove node from standby mode (the node specified will now be able to
        host resources), if no node or options are specified the current node
        will be removed from standby mode, if --all is specified all nodes will
        be removed from standby mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be removed from standby mode and then return 0 on success or 1 if
        the operation not succeeded yet.  If 'n' is not specified it defaults
        to 60 minutes.

    utilization [[<node>] [--name <name>] | <node> <name>=<value> ...]
        Add specified utilization options to specified node.  If node is not
        specified, shows utilization of all nodes.  If --name is specified,
        shows specified utilization value from all nodes. If utilization options
        are not specified, shows utilization of specified node.  Utilization
        option should be in format name=value, value has to be integer.  Options
        may be removed by setting an option without a value.
        Example: pcs node utilization node1 cpu=4 ram=
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def qdevice(args=[], pout=True):
    output = """
Usage: pcs qdevice <command>
Manage quorum device provider on the local host, currently only 'net' model is
supported.

Commands:
    status <device model> [--full] [<cluster name>]
        Show runtime status of specified model of quorum device provider.  Using
        --full will give more detailed output.  If <cluster name> is specified,
        only information about the specified cluster will be displayed.

    setup model <device model> [--enable] [--start]
        Configure specified model of quorum device provider.  Quorum device then
        can be added to clusters by running "pcs quorum device add" command
        in a cluster.  --start will also start the provider.  --enable will
        configure the provider to start on boot.

    destroy <device model>
        Disable and stop specified model of quorum device provider and delete
        its configuration files.

    start <device model>
        Start specified model of quorum device provider.

    stop <device model>
        Stop specified model of quorum device provider.

    kill <device model>
        Force specified model of quorum device provider to stop (performs kill
        -9).  Note that init system (e.g. systemd) can detect that the qdevice
        is not running and start it again.  If you want to stop the qdevice, run
        "pcs qdevice stop" command.

    enable <device model>
        Configure specified model of quorum device provider to start on boot.

    disable <device model>
        Configure specified model of quorum device provider to not start
        on boot.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def quorum(args=[], pout=True):
    output = """
Usage: pcs quorum <command>
Manage cluster quorum settings.

Commands:
    [config]
        Show quorum configuration.

    status
        Show quorum runtime status.

    device add [<generic options>] model <device model> [<model options>]
        Add a quorum device to the cluster.  Quorum device needs to be created
        first by "pcs qdevice setup" command.  It is not possible to use more
        than one quorum device in a cluster simultaneously.  Generic options,
        model and model options are all documented in corosync's
        corosync-qdevice(8) man page.

    device remove
        Remove a quorum device from the cluster.

    device status [--full]
        Show quorum device runtime status.  Using --full will give more detailed
        output.

    device update [<generic options>] [model <model options>]
        Add/Change quorum device options.  Generic options and model options are
        all documented in corosync's corosync-qdevice(8) man page.  Requires
        the cluster to be stopped.

        WARNING: If you want to change "host" option of qdevice model net, use
        "pcs quorum device remove" and "pcs quorum device add" commands
        to set up configuration properly unless old and new host is the same
        machine.

    expected-votes <votes>
        Set expected votes in the live cluster to specified value.  This only
        affects the live cluster, not changes any configuration files.

    unblock [--force]
        Cancel waiting for all nodes when establishing quorum.  Useful in
        situations where you know the cluster is inquorate, but you are
        confident that the cluster should proceed with resource management
        regardless.  This command should ONLY be used when nodes which
        the cluster is waiting for have been confirmed to be powered off and
        to have no access to shared resources.

        WARNING: If the nodes are not actually powered off or they do have
        access to shared resources, data corruption/cluster failure can occur.
        To prevent accidental running of this command, --force or interactive
        user response is required in order to proceed.

    update [auto_tie_breaker=[0|1]] [last_man_standing=[0|1]]
            [last_man_standing_window=[<time in ms>]] [wait_for_all=[0|1]]
        Add/Change quorum options.  At least one option must be specified.
        Options are documented in corosync's votequorum(5) man page.  Requires
        the cluster to be stopped.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output

def booth(args=[], pout=True):
    output = """
Usage: pcs booth <command>
Manage booth (cluster ticket manager)

Commands:
    setup sites <address> <address> [<address>...] [arbitrators <address> ...]
            [--force]
        Write new booth configuration with specified sites and arbitrators.
        Total number of peers (sites and arbitrators) must be odd.  When
        the configuration file already exists, command fails unless --force
        is specified.

    destroy
        Remove booth configuration files.

    ticket add <ticket> [<name>=<value> ...]
        Add new ticket to the current configuration. Ticket options are
        specified in booth manpage.

    ticket remove <ticket>
        Remove the specified ticket from the current configuration.

    config [<node>]
        Show booth configuration from the specified node or from the current
        node if node not specified.

    create ip <address>
        Make the cluster run booth service on the specified ip address as
        a cluster resource.  Typically this is used to run booth site.

    remove
        Remove booth resources created by the "pcs booth create" command.

    restart
        Restart booth resources created by the "pcs booth create" command.

    ticket grant <ticket> [<site address>]
        Grant the ticket for the site specified by address.  Site address which
        has been specified with 'pcs booth create' command is used if
        'site address' is omitted.  Specifying site address is mandatory when
        running this command on an arbitrator.

    ticket revoke <ticket> [<site address>]
        Revoke the ticket for the site specified by address.  Site address which
        has been specified with 'pcs booth create' command is used if
        'site address' is omitted.  Specifying site address is mandatory when
        running this command on an arbitrator.

    status
        Print current status of booth on the local node.

    pull <node>
        Pull booth configuration from the specified node.

    sync [--skip-offline]
        Send booth configuration from the local node to all nodes
        in the cluster.

    enable
        Enable booth arbitrator service.

    disable
        Disable booth arbitrator service.

    start
        Start booth arbitrator service.

    stop
        Stop booth arbitrator service.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output


def alert(args=[], pout=True):
    output = """
Usage: pcs alert <command>
Set pacemaker alerts.

Commands:
    [config|show]
        Show all configured alerts.

    create path=<path> [id=<alert-id>] [description=<description>]
            [options [<option>=<value>]...] [meta [<meta-option>=<value>]...]
        Define an alert handler with specified path. Id will be automatically
        generated if it is not specified.

    update <alert-id> [path=<path>] [description=<description>]
            [options [<option>=<value>]...] [meta [<meta-option>=<value>]...]
        Update existing alert handler with specified id.

    remove <alert-id> ...
        Remove alert handlers with specified ids.

    recipient add <alert-id> value=<recipient-value> [id=<recipient-id>]
            [description=<description>] [options [<option>=<value>]...]
            [meta [<meta-option>=<value>]...]
        Add new recipient to specified alert handler.

    recipient update <recipient-id> [value=<recipient-value>]
            [description=<description>] [options [<option>=<value>]...]
            [meta [<meta-option>=<value>]...]
        Update existing recipient identified by it's id.

    recipient remove <recipient-id> ...
        Remove specified recipients.
"""
    if pout:
        print(sub_usage(args, output))
    else:
        return output


def show(main_usage_name, rest_usage_names):
    usage_map = {
        "acl": acl,
        "alert": alert,
        "cluster": cluster,
        "config": config,
        "constraint": constraint,
        "node": node,
        "pcsd": pcsd,
        "property": property,
        "qdevice": qdevice,
        "quorum": quorum,
        "booth": booth,
        "resource": resource,
        "status": status,
        "stonith": stonith,
    }
    if main_usage_name not in usage_map:
        raise Exception(
            "Bad usage name '{0}' there can be '{1}'"
            .format(main_usage_name,  list(usage_map.keys()))
        )
    usage_map[main_usage_name](rest_usage_names)
