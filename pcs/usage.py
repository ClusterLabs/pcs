def main():
    print """
Usage: pcs [-f file] [-h] [commands]...
Control and configure pacemaker and corosync.

Options:
    -h          Display usage and exit
    -f file     Perform actions on file instead of active CIB

Commands:
    add <resource id> <provider:class:type|type> [resource options]
    set <property>=<value>

    node        Manage nodes (NOT YET IMPLEMENTED)
    resource    Manage cluster resources
    cluster     Configure cluster options
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
    resource [list|show] [resource_id]
    resource start <resource id>
    resource stop <resource id>
    resource create <resource id> <provider:class:type|type> [resource options]
    resource update <resource id> [resource options]
    resource delete <resource id>
    resource group add <group name> <resource id>...
    resource group remove_resource <group name> <resource id> ...
    resource group list

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
    start       Start corosync & pacemaker
    stop        Stop corosync & pacemaker
    startall    Start corosync & pacemaker on all nodes
    stopall     Stop corosync & pacemaker on all nodes

    gui-status [node] [...]
        Get current status of pcs-gui on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified

    auth [node] [...]
        Authenticate pcs to pcs-gui on nodes specified, or on all nodes
        configured in corosync.conf if no nodes are specified (authorization
        tokens are stored in ~/.pcs/token)

    token <node>
        Get authorization token for specified node

    sync
        Sync corosync configuration to all nodes found from current
        corosync.conf file

    configure <cluster name> <node1 ip> [node2 ip] [...]
        Configure corosync with <cluster name> and specified nodes

    configure sync <cluster name> <node1 ip> [node2 ip] [...]
        Configure corosync and sync configuration out to listed nodes

    configure sync_start <cluster name> <node1 ip> [node2 ip] [...]
        Configure corosync and sync configuration out to listed nodes and
        start corosync and pacemaker services on the nodes
"""

def stonith():
    print """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    stonith [list|show] [stonith_id]
    stonith create <stonith_id> <fence device type> [fence device options]
    stonith update <stonith_id> [fence device options]
    stonith delete <stonith_id>

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

    order [show]
        List all current ordering constraints.

    order list <resource1> <resource2> [resourceN]...
        Require that resource be started in the order specified

    order rm <resource1> [resourceN]...
        Remove resource from any order list

    order add <resource1> <resource2> <score> [symmetrical|nonsymmetrical]
        Specify that resource1 should start before rsource2 with the specified
        score and specify if resources will be stopped in the reverse order
        they were started (symmetrical) or not (nonsymmetrical).  Default is
        symmetrical.  (For more advance pacemaker usage)

    colocation add <source resource> <target resource> [score]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score force <source resource> to
        run (or not run) on <target resource>. (score defaults to "INFINITY")

    colocation rm <source resource> <target resource>
        Remove colocation constraints with <source resource>
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

    status nodes [corosync]
        View current status of nodes from pacemaker, or if corosync is
        specified, print nodes currently configured in corosync

    status actions
        View failed actions

    status xml
        View xml version of status (output from crm_mon -r -1 -X)
"""
