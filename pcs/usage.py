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
    out += strip_extras(status([],False))
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
    tree["constraint"] = generate_tree(constraint([],False))
    tree["status"] = generate_tree(status([],False))
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
        COMPREPLY=( $(compgen -W "resource cluster stonith property constraint status" -- $cur) )
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
    status      View cluster status
    config      Print full cluster configuration
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
           --group <group name>]
        Create specified resource.  If --clone is used a clone resource is
        created if --master is specified a master/slave resource is created.
        If --group is specified the resource is added to the group named.
        Example: pcs resource create ClusterIP ocf:heartbeat:IPaddr2 \\
                     ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s \\
                     nic=eth2
                 Create a new resource called 'ClusterIP' with IP address
                 192.168.0.99, netmask of 32, monitored everything 30 seconds,
                 on eth2.

    delete <resource id|group id|master id|clone id>
        Deletes the resource, group, master or clone (and all resources within
        the group/master/clone).

    enable <resource id> [--wait[=n]]
        Allow the cluster to start the resource. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resource may
        remain stopped.  If --wait is specified, pcs will wait up to 30 seconds
        (or 'n' seconds) for the resource to start and then return 0 if the
        resource is started, or 1 if the resource has not yet started.

    disable <resource id> [--wait[=n]]
        Attempt to stop the resource if it is running and forbid the cluster
        from starting it again.  Depending on the rest of the configuration
        (constraints, options, failures, etc), the resource may remain
        started.  If --wait is specified, pcs will wait up to 30 seconds (or
        'n' seconds) for the resource to stop and then return 0 if the
        resource is stopped or 1 if the resource has not stopped.

    debug-start <resource id> [--full]
        This command will force the specified resource to start on this node
        ignoring the cluster recommendations and print the output from
        starting the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to start.

    move <resource id> [destination node] [--master]
        Move resource off current node (and optionally onto destination node).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id). 

    ban <resource id> [node] [--master]
        Prevent the resource id specified from running on the node (or on the
        current node it is running on if no node is specified).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id). 

    clear <resource id> [node] [--master]
        Remove constraints created by move and/or ban on the specified
        resource (and node if specified).
        If --master is used the scope of the command is limited to the
        master role and you must use the master id (instead of the resource id). 

    standards
        List available resource agent standards supported by this installation.
        (OCF, LSB, etc.)

    providers
        List available OCF resource agent providers

    agents [standard[:provider]]
        List available agents optionally filtered by standard and provider

    update <resource id> [resource options] [op [<operation action>
           <operation options>]...] [meta <meta operations>...]
        Add/Change options to specified resource, clone or multi-state
        resource.  If an operation (op) is specified it will update the first
        found operation with the same action on the specified resource, if no
        operation with that action exists then a new operation will be created.
        (WARNING: all current options on the update op will be reset if not
        specified) If you want to create multiple monitor operations you should
        use the add_operation & remove_operation commands.

    op add <resource id> <operation action> [operation properties]
        Add operation for specified resource

    op remove <resource id> <operation action> [operation properties]
        Remove specified operation (note: you must specify the exact operation
        properties to properly remove an existing operation).

    op remove <operation id>
        Remove the specified operation id

    op defaults [options]
        Set default values for operations, if no options are passed, lists
        currently configured defaults

    meta <resource id | group id | master id | clone id> <meta options>
        Add specified options to the specified resource, group, master/slave
        or clone.  Meta options should be in the format of name=value, options
        may be removed by setting an option without a value.
        Example: pcs resource meta TestResource failure-timeout=50 stickiness=

    group add <group name> <resource id> [resource id] ... [resource id]
        Add the specified resource to the group, creating the group if it does
        not exist.  If the resource is present in another group it is moved
        to the new group.

    group remove <group name> <resource id> [resource id] ... [resource id]
        Remove the specified resource(s) from the group, removing the group if
        it no resources remain.

    ungroup <group name> [resource id] ... [resource id]
        Remove the group (Note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group

    clone <resource id | group id> [clone options]...
        Setup up the specified resource or group as a clone

    unclone <resource id | group name>
        Remove the clone which contains the specified group or resource (the
        resource or group will not be removed)

    master [<master/slave name>] <resource id | group name> [options]
        Configure a resource or group as a multi-state (master/slave) resource.
        Note: to remove a master you must remove the resource/group it contains.

    manage <resource id> ... [resource n]
        Set resources listed to managed mode (default)

    unmanage <resource id> ... [resource n]
        Set resources listed to unmanaged mode

    defaults [options]
        Set default values for resources, if no options are passed, lists
        currently configured defaults

    cleanup <resource id>
        Cleans up the resource in the lrmd (useful to reset the resource
        status and failcount).  This tells the cluster to forget the
        operation history of a resource and re-detect its current state.
        This can be useful to purge knowledge of past failures that have
        since been resolved.

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

    pcs resource show ClusterIP
      Show options specific to the 'ClusterIP' resource


    pcs resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s 
      Create a new resource called 'ClusterIP' with options

    pcs resource create ClusterIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 nic=eth2 op monitor interval=30s
      Create a new resource called 'ClusterIP' with options

    pcs resource update ClusterIP ip=192.168.0.98 nic=
      Change the ip address of ClusterIP and remove the nic option

    pcs resource delete ClusterIP
      Delete the ClusterIP resource

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
        tokens are stored in ~/.pcs/token).  By default all nodes are also
        authenticated to each other, using --local only authenticates the
        local node (and does not authenticate the remote nodes with each
        other).  Using --force forces re-authentication to occur.

    setup [--start] [--local] [--enable] --name <cluster name> <node1>
                                                               [node2] [..]
        Configure corosync and sync configuration out to listed nodes
        --local will only perform changes on the local node
        --start will also start the cluster on the specified nodes
        --enable will enable corosync and pacemaker on node startup

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
        corosync.conf file

    cib [filename]
        Get the raw xml from the CIB (Cluster Information Base).  If a
        filename is provided, we save the cib to that file, otherwise the cib
        is printed

    cib-push <filename>
        Push the raw xml from <filename> to the CIB (Cluster Information Base)

    edit
        Edit the cib in the editor specified by the $EDITOR environment
        variable and push out any changes upon saving

    node add <node> [--start]
        Add the node to corosync.conf and corosync on all nodes in the cluster
        and sync the new corosync.conf to the new node.  If --start is specified
        also start corosync/pacemaker on the new node

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

    corosync <node>
        Get the corosync.conf from the specified node

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

    list [filter]
        Show list of all available stonith agents (if filter is provided then
        only stonith agents matching the filter will be shown)

    describe <stonith agent>
        Show options for specified stonith agent

    create <stonith id> <stonith device type> [stonith device options]
        Create stonith device with specified type and options

    update <stonith id> [stonith device options]
        Add/Change options to specified stonith id
        
    delete <stonith id>
        Remove stonith id from configuration

    cleanup <stonith id>
        Cleans up the stonith device in the lrmd (useful to reset the 
        status and failcount).  This tells the cluster to forget the
        operation history of a stonith device and re-detect its current state.
        This can be useful to purge knowledge of past failures that have
        since been resolved.

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
    list|show [property] [--all | --defaults]
        List property settings (Default: all properties)
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

    location <resource id> rule [role=master|slave] [score=<score>] <expression>
        Creates a location rule on the specified resource where the expression
        looks like one of the following:
          defined|not_defined <attribute>
          <attribute> lt|gt|lte|gte|eq|ne <value>
          date [start=<start>] [end=<end>] operation=gt|lt|in-range
          date-spec <date spec options>...

    location show [resources|nodes [node id|resource id]...] [--full]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node.  If specific
        nodes or resources are specified then we only show information about
        them

    location add <id> <resource name> <node> <score>
        Add a location constraint with the appropriate id, resource name,
        node name and score. (For more advanced pacemaker usage)

    location remove <id> [<resource name> <node> <score>]
        Remove a location constraint with the appropriate id, resource name,
        node name and score. (For more advanced pacemaker usage)

    order show [--full]
        List all current ordering constraints (if '--full' is specified show
        the internal constraint id's as well).

    order [action] <resource id> then [action] <resource id> [options]
        Add an ordering constraint specifying actions (start,stop,promote,
        demote) and if no action is specified the default action will be
        start.
        Available options are kind=Optional/Mandatory/Serialize and
        symmetrical=true/false

    order set <resource1> <resource2> [resourceN]... [options] [set
              <resourceX> <resourceY> ...]
        Create an ordered set of resources.

    order remove <resource1> [resourceN]...
        Remove resource from any ordering constraint

    colocation show [--full]
        List all current colocation constraints (if '--full' is specified show
        the internal constraint id's as well).

    colocation add [master|slave] <source resource id> with [master|slave]
                   <target resource id> [score] [options]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score force <source resource> to
        run (or not run) with <target resource>. (score defaults to "INFINITY")
        A role can be master or slave (if no role is specified, it defaults to
        'started').

    colocation set <resource1> <resource2> [resourceN]... [setoptions] ...
               [set <resourceX> <resourceY> ...] [setoptions <name>=<value>...]
        Create a colocation constraint with a resource set

    colocation remove <source resource id> <target resource id>
        Remove colocation constraints with <source resource>

    remove [constraint id]...
        Remove constraint(s) or constraint rules with the specified id(s)

    ref [resource]...
        List constraints referencing specified resource

    rule add <constraint id> [<rule type>] [score=<score>] [id=<rule id>]
        <expression|date_expression|date_spec>...
        Add a rule to a constraint, if score is omitted it defaults to
        INFINITY, if id is omitted one is generated from the constraint id.
        The <rule type> should be 'expression' or 'date_expression'

    rule remove <rule id>
        Remove a rule if a rule id is specified, if rule is last rule in its
        constraint, the constraint will be removed
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
    [status]
        View all information about the cluster and resources

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
