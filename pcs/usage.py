def main():
    print """
Usage: pcs [-f file] [-h] [commands]...
Control and configure pacemaker and corosync.

Options:
    -h          Display usage and exit
    -f file     Perform actions on file instead of active CIB

Commands:
    add <resource id> <class:provider:type|type> [resource options]
    set <property>=<value>

    resource    Manage cluster resources
    cluster     Configure cluster options and nodes
    stonith     Configure fence devices
    property    Set pacemaker properties
    constraint  Set resource constraints
    status      View cluster status
"""

def resource():
    print """
Usage: pcs resource [commands]...
Manage pacemaker resources
Commands:
    [list|show] [resource_id]
        List all currently configured resources

    start <resource_id>
        Start resource specified by resource_id

    stop <resource id>
        Stop resource specified by resource_id

    create
        Show list of all available resources

    create <class:provider:type|type>
        Show options for specified resource

    create <resource id> <class:provider:type|type> [resource options]
        Create specified resource

    standards
        List available resource agent standards

    providers
        List available resource agent providers

    agents [standard[:provider]]
        List available agents optionally filtered by standard and provider

    update <resource id> [resource options]
        Add/Change options to specified resource

    add_operation <resource id> <operation name> [operation properties]
        Add operation for specified resource

    remove_operation <resource id> <operation name> [operation properties]
        Remove specified operation (note: you must specify the exeact operation
        properties to properly remove an existing operation).

    delete <resource id>
        Delete the specified resource

    group add <group name> <resource_id>...
        Add the specified resource to the group (creating the group if it does
        not exist

    group remove_resource <group name> <resource_id> ...
        Remove the specified resource from the group (removing the group if
        it does not have any other resources)

    group list
        List all currently configured resource groups

    clone create <resource id | group name> [clone options]...
        Setup up the specified resource or group as a clone

    clone update <resource id | group name> [clone options]...
        Update the clone containing the resource or group replacing all
        current options with the new options

    clone remove <resource id | group name>
        Remove the clone which contains the specified group or resource (the
        resource or group will not be removed)

    master create <master/slave name> <group or resource> [options]
        Configure a resource or group as a multi-state (master/slave) resource

    master update <master/slave name> [options]
        Update a multi-state (master/slave) resource options

    master remove <master/slave name>|<resource/group>
        Set resource/group specified as a normal (non-multi-state) resource
        or group.  If a master/slave name is specified, the resource/group it
        containts will be converted to a normal resource.

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

Examples:
    pcs resource list

    pcs resource list ClusterIP

    pcs resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource create ClusterIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource update ClusterIP ip=192.168.0.98 cidr_netmask=

    pcs resource delete ClusterIP
"""

def cluster():
    print """
Usage: pcs cluster [commands]...
Configure cluster for use with pacemaker

Commands:
    start [node] [...]
        Start corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are started on the local node.

    stop [node] [...]
        Stop corosync & pacemaker on specified node(s), if a node is not
        specified then corosync & pacemaker are started on the local node.

    enable [node] [...]
        Configure corosync & pacemaker to run on startup on specified node(s),
        if node is not specified then corosync & pacemaker are enabled on the
        local node.

    disable [node] [...]
        Configure corosync & pacemaker to not run on startup on specified
        node(s), if node is not specified then corosync & pacemaker are disabled
        on the local node.

    standby <node>
        Put specified node into standby mode (the node specified will no longer
        be able to host resources
    
    unstandby <node>
        Remove node from standby mode (the node specified will now be able to
        host resources

    startall    Start corosync & pacemaker on all nodes
    stopall     Stop corosync & pacemaker on all nodes
    enableall   Configure corosync & pacemaker to run on startup on all nodes
    disableall  Configure corosync & pacemaker to not run on startup on all
                nodes

    gui-status [node] [...]
        Get current status of pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified

    auth [node] [...]
        Authenticate pcs to pcsd on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified (authorization
        tokens are stored in ~/.pcs/token)

    token <node>
        Get authorization token for specified node

    sync
        Sync corosync configuration to all nodes found from current
        corosync.conf file

    configure [--start] [--local] <cluster name> <node1 ip> [node2 ip] [...]
        Configure corosync and sync configuration out to listed nodes
        --local will only perform changes on the local node
        --start will also start the cluster on the specified nodes

    cib
        Get the raw xml from the CIB (Cluster Information Base)

    push cib <filename>
        Push the raw xml from <filename> to the CIB (Cluster Information Base)

    node add <node ip/name>
        Add the node to corosync.conf and corosync on all nodes in the cluster
        and sync the new corosync.conf to the new node

    localnode add <node ip/name>
        Add the specified node to corosync.conf and corosync only on this node

    node remove <node ip/name>
        Shutdown specified node and remove it from pacemaker and corosync on
        all other nodes in the cluster

    localnode remove <node ip/name>
        Remove the specified node from corosync.conf & corosync on local node

    pacemaker remove <node ip/name>
        Remove specified node from running pacemaker configuration

    get_conf <node ip/name>
        Get the corosync.conf from the specified node
"""

def stonith():
    print """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    [list|show] [stonith_id]
    create
        Show list of all available stonith agents

    create <stonith agent>
        Show options for specified stonith agent

    create <stonith_id> <stonith device type> [stonith device options]
        Create stonith device with specified type and options

    update <stonith_id> [stonith device options]
        Add/Change options to specified resource_id
        
    delete <stonith_id>
        Remove stonith_id from configuration

Examples:
    pcs stonith create MyStonith ssh hostlist="f1" op monitor interval=30s
"""

def property():
    print """
Usage: pcs property <properties>...
Configure pacemaker properties

Commands:
    [list|show [property]]
        List property settings (Default: all properties)

    set <property>=[<value>]
        Set specific pacemaker properties (if the value is blank then the
        property is removed from the configuration)

Examples:
    pcs property set stonith-enabled=false
"""

def constraint():
    print """
Usage: pcs constraint [constraints]...
Manage resource constraints

Commands:
    [list|show]
        List all current location, order and colocation constraints

    all
        List all current location, order and colocation constraints with ids

    location [show resources|nodes [specific nodes|resources]]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node.  If specific
        nodes or resources are specified then we only show information about
        them

    location force <resource name> [on] <node>
        Force the resource named to always run on the node specified

    location force <resource name> off <node>
        Force the resource named to never run on the specified node

    location forcerm <resource name> [on] <node>
        Remove the constraint forcing the resource named to always run on the
        node specified

    location forcerm <resource name> off <node>
        Remove the constraint forcing the resource named to never run on the
        node specified

    location add <id> <resource name> <node> <score>
        Add a location constraint with the appropriate id, resource name,
          node name and score. (For more advanced pacemaker usage)

    location rm <id> [<resource name> <node> <score>]
        Remove a location constraint with the appropriate id, resource name,
          node name and score. (For more advanced pacemaker usage)

    order [show [all]]
        List all current ordering constraints (if 'all' is specified show
        the internal constraint id's as well).

    order list <resource1> <resource2> [resourceN]...
        Require that resource be started in the order specified

    order rm <resource1> [resourceN]...
        Remove resource from any order list

    order add <resource1> <resource2> <score> [symmetrical|nonsymmetrical]
        Specify that resource1 should start before rsource2 with the specified
        score and specify if resources will be stopped in the reverse order
        they were started (symmetrical) or not (nonsymmetrical).  Default is
        symmetrical.  (For more advance pacemaker usage)

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

    rm [constraint id]
        Remove constraint with the specified id
"""

def status():
    print """
Usage: pcs status [commands]...
View current cluster and resource status
Commands:
    status
        View all information about the cluster and resources

    status resources
        View current status of cluster resources

    status cluster
        View current cluster status

    status corosync
        View current corosync status

    status nodes [corosync]
        View current status of nodes from pacemaker, or if corosync is
        specified, print nodes currently configured in corosync

    status actions
        View failed actions

    status xml
        View xml version of status (output from crm_mon -r -1 -X)
"""
