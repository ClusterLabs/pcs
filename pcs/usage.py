examples = ""
def full_usage():
    global examples
    out = ""
    out += main(False)
    out += strip_extras(resource(False))
    out += strip_extras(cluster(False))
    out += strip_extras(stonith(False))
    out += strip_extras(property(False))
    out += strip_extras(constraint(False))
    out += strip_extras(status(False))
    print out.strip()
    print "Examples:\n" + examples.replace(" \ ","")

def strip_extras(text):
    global examples
    ret = ""
    ret_ex = ""
    group_name = text.split(" ")[2]
    in_commands = False
    in_examples = False
    in_com = False
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
                        minicmd = "    " + group_name + " " + line.lstrip() + "  "
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
    resource    Manage cluster resources
    cluster     Configure cluster options and nodes
    stonith     Configure fence devices
    property    Set pacemaker properties
    constraint  Set resource constraints
    status      View cluster status
    config      Print full cluster configuration
"""
# Advanced usage to possibly add later
#  --corosync_conf=<corosync file> Specify alternative corosync.conf file
    if pout:
        print output
    else:
        return output
                                                    

def resource(pout = True):
    output = """
Usage: pcs resource [commands]...
Manage pacemaker resources

Commands:
    show [resource id] [--all]
        Show all currently configured resources or if a resource is specified
        show the options for the configured resource.  If --all is specified
        all configured resource options will be displayed

    start <resource id>
        Start resource specified by resource_id

    stop <resource id>
        Stop resource specified by resource_id

    move <resource id> [destination node]
        Move resource off current node (and optionally onto destination node

    unmove <resource id>
        Remove constraints created by the move command and allow the resource
        to move back to its original location

    list
        Show list of all available resources

    list <class|provider|type>
        Show available resources filtered by specified type, class or provider

    describe <class:provider:type|type>
        Show options for the specified resource

    create <resource id> <class:provider:type|type> [resource options]
           [op <operation type> <operation options> [<operation type>
           <operation options>]...] [meta <meta options>...]
        Create specified resource.  If --clone is specified a clone resource
        is created (with options specified by
        --cloneopt <clone_option>=<value>), if --master is specified a
        master/slave resource is created.

    standards
        List available resource agent standards

    providers
        List available resource agent providers

    agents [standard[:provider]]
        List available agents optionally filtered by standard and provider

    update <resource id> [resource options] [op [<operation name>
           <operation options>]...] [meta <meta operations>...]
        Add/Change options to specified resource, clone or multi-state
        resource.  If an operation (op) is specified it will update the first
        found operation with the same name on the specified resource, if no
        operation with that name exists then a new operation will be created
        If you want to create multiple monitor operations you should use the
        add_operation & remove_operation commands.

    add_operation <resource id> <operation name> [operation properties]
        Add operation for specified resource

    remove_operation <resource id> <operation name> [operation properties]
        Remove specified operation (note: you must specify the exeact operation
        properties to properly remove an existing operation).

    meta <resource/group/master/clone id> <meta options>
        Add (or remove with option= ) specified options to the specified
        resource, group, master/slave or clone.

    delete <resource id | master/slave id>
        Delete the specified resource or master/slave resource (including any
        constraints referencing the resource)

    group add <group name> <resource_id>...
        Add the specified resource to the group (creating the group if it does
        not exist

    group remove_resource <group name> <resource_id> ...
        Remove the specified resource from the group (removing the group if
        it does not have any other resources)

    group list
        List all currently configured resource groups

    clone <resource id | group name> [clone options]...
        Setup up the specified resource or group as a clone

    unclone <resource id | group name>
        Remove the clone which contains the specified group or resource (the
        resource or group will not be removed)

    master [<master/slave name>] <resource id | group name> [options]
        Configure a resource or group as a multi-state (master/slave) resource

    unmaster <resource id | group name>
        Remove the master which contains the specified group or resource (the
        resource or group will not be removed)

    manage <resource 1> [resource 2] ...
        Set resources listed to managed mode (default)

    unmanage <resource 1> [resource 2] ...
        Set resources listed to unmanaged mode

    rsc defaults [options]
        Set default values for resources, if no options are passed, lists
        currently configured defaults

    op defaults [options]
        Set default values for operations, if no options are passed, lists
        currently configured defaults

    cleanup <resource id>
        Cleans up the resource in the lrmd (useful to reset the resource
        status and failcount)

    failcount show <resource> [node]
        Show current failcount for specified resource from all nodes or
        only on specified node

    failcount reset <resource> [node]
        Reset failcount for specified resource on all nodes or only on
        specified node

Examples:
    pcs resource show

    pcs resource show ClusterIP

    pcs resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource create ClusterIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource update ClusterIP ip=192.168.0.98 cidr_netmask=

    pcs resource delete ClusterIP
"""
    if pout:
        print output
    else:
        return output

def cluster(pout = True):
    output = """
Usage: pcs cluster [commands]...
Configure cluster for use with pacemaker

Commands:
    auth [node] [...] [-u username] [-p password]
        Authenticate pcs to pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified (authorization
        tokens are stored in ~/.pcs/token)

    setup [--start] [--local] <cluster name> <node1> [node2] [...]
        Configure corosync and sync configuration out to listed nodes
        --local will only perform changes on the local node
        --start will also start the cluster on the specified nodes

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

    force_stop
        Force corosync and pacemaker daemons to stop on the local node
        (performs kill -9).

    enable [--all] [node] [...]
        Configure corosync & pacemaker to run on startup on specified node(s),
        if node is not specified then corosync & pacemaker are enabled on the
        local node. If --all is specified then corosync & pacemaker are enabled
        on all nodes.

    disable [--all] [node] [...]
        Configure corosync & pacemaker to not run on startup on specified
        node(s), if node is not specified then corosync & pacemaker are disabled
        on the local node. If --all is specified then corosync & pacemaker are
        disabled on all nodes.

    standby <node>
        Put specified node into standby mode (the node specified will no longer
        be able to host resources
    
    unstandby <node>
        Remove node from standby mode (the node specified will now be able to
        host resources

    status
        View current cluster status (an alias of 'pcs status cluster')

    pcsd-status [node] [...]
        Get current status of pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified

    token <node>
        Get authorization token for specified node

    sync
        Sync corosync configuration to all nodes found from current
        corosync.conf file

    cib [filename]
        Get the raw xml from the CIB (Cluster Information Base).  If a
        filename is provided, we save the cib to that file, otherwise the cib
        is printed

    push cib <filename>
        Push the raw xml from <filename> to the CIB (Cluster Information Base)

    edit
        Edit the cib in the editor specified by the $EDITOR environment
        variable and push out any changes upon saving

    node add <node>
        Add the node to corosync.conf and corosync on all nodes in the cluster
        and sync the new corosync.conf to the new node

    localnode add <node>
        Add the specified node to corosync.conf and corosync only on this node

    node remove <node>
        Shutdown specified node and remove it from pacemaker and corosync on
        all other nodes in the cluster

    localnode remove <node>
        Remove the specified node from corosync.conf & corosync on local node

    pacemaker remove <node>
        Remove specified node from running pacemaker configuration

    corosync <node>
        Get the corosync.conf from the specified node

    destroy
        Permanently destroy the cluster, killing all corosync/pacemaker
        processes removing all cib files and corosync.conf file.
        WARNING: This command permantly removes any cluster configuration that
        has been created. It is recommended to run 'pcs cluster stop' before
        destroying the cluster.
"""
    if pout:
        print output
    else:
        return output

def stonith(pout = True):
    output = """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    show [stonith_id]
        Show all currently configured stonith devices or if a stonith_id is
        specified show the options for the configured stonith device.  If
        --all is specified all configured stonith options will be displayed

    list [filter]
        Show list of all available stonith agents (if filter is provided then
        only stonith agents matching the filter will be shown)

    describe <stonith agent>
        Show options for specified stonith agent

    create <stonith_id> <stonith device type> [stonith device options]
        Create stonith device with specified type and options

    update <stonith_id> [stonith device options]
        Add/Change options to specified resource_id
        
    delete <stonith_id>
        Remove stonith_id from configuration

    fence <node> [--off]
        Fence the node specified (if --off is specified, use the 'off' API
        call to stonith which will turn the node off instead of rebooting it)

    confirm <node>
        Confirm that the host specified is currently down
        WARNING: if this node is not actually down data corruption/cluster
        failure can occur.

Examples:
    pcs stonith create MyStonith ssh hostlist="f1" op monitor interval=30s
"""
    if pout:
        print output
    else:
        return output

def property(pout = True):
    output = """
Usage: pcs property <properties>...
Configure pacemaker properties

Commands:
    [list|show [property]] [--all | --defaults]
        List property settings (Default: all properties)
        If --defaults is specified will show all property defaults, if --all
        is specified, current configured properties will be shown with unset
        properties and their defaults

    set [--force] <property>=[<value>]
        Set specific pacemaker properties (if the value is blank then the
        property is removed from the configuration).  If a property is not
        recognized by pcs the property will not be created unless the
        '--force' is used.

    unset <property>
        Remove property from configuration

Examples:
    pcs property set stonith-enabled=false
"""
    if pout:
        print output
    else:
        return output

def constraint(pout = True):
    output = """
Usage: pcs constraint [constraints]...
Manage resource constraints

Commands:
    [list|show]
        List all current location, order and colocation constraints

    all
        List all current location, order and colocation constraints with ids

    location <rsc> prefers <node[=score]>...
        Create a location constraint on a resource to prefer the specified
        node and score (default score: INFINITY)

    location <rsc> avoids <node[=score]>...
        Create a location constraint on a resource to avoid the specified
        node and score (default score: INFINITY)

    location [show resources|nodes [specific nodes|resources]]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node.  If specific
        nodes or resources are specified then we only show information about
        them

    location add <id> <resource name> <node> <score>
        Add a location constraint with the appropriate id, resource name,
          node name and score. (For more advanced pacemaker usage)

    location rm <id> [<resource name> <node> <score>]
        Remove a location constraint with the appropriate id, resource name,
          node name and score. (For more advanced pacemaker usage)

    order [show [all]]
        List all current ordering constraints (if 'all' is specified show
        the internal constraint id's as well).

    order [action] <first rsc> then [action] <then rsc> [options]
        Add an ordering constraint specifying actions (start,stop,promote,
        demote) and if no action is specified the default action will be
        start.
        Available options are kind=Optional/Mandatory/Serialize and
        symmetrical=true/false

    order list <resource1> <resource2> [resourceN]...
        Require that resource be started in the order specified

    order rm <resource1> [resourceN]...
        Remove resource from any order list

    order add <rsc1> <rsc2> [symmetrical|nonsymmetrical] [options]...
        Specify that rsc1 should start before rsc2 and specify if
        resources will be stopped in the reverse order they were started
        (symmetrical) or not (nonsymmetrical).  Default is symmetrical.
        (For more advance pacemaker usage)
        Options are specified by option_name=option_value

    colocation [show [all]]
        List all current colocation constraints (if 'all' is specified show
        the internal constraint id's as well).

    colocation add <source resource> <target resource> [score] [options]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score force <source resource> to
        run (or not run) on <target resource>. (score defaults to "INFINITY")

    colocation rm <source resource> <target resource>
        Remove colocation constraints with <source resource>

    rm [constraint id]...
        Remove constraint(s) with the specified id(s)

    ref [resource]...
        List constraints referencing specified resource
"""
    if pout:
        print output
    else:
        return output

def status(pout = True):
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
        View current corosync status

    nodes [corosync|both|config]
        View current status of nodes from pacemaker. If 'corosync' is
        specified, print nodes currently configured in corosync, if 'both'
        is specified, print nodes from both corosync & pacemaker.  If 'config'
        is specified, print nodes from corosync & pacemaker configuration.

    actions
        View failed actions

    pcsd <node> ...
        Show the current status of pcsd on the specified nodes

    xml
        View xml version of status (output from crm_mon -r -1 -X)
"""
    if pout:
        print output
    else:
        return output
