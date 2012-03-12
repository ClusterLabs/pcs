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
    corosync    Configure corosync
    property    Set pacemaker properties
    constraint  Set resource constraints
    status      View pacemaker status
"""

def resource():
    print """
Usage: pcs resource [commands]...
Manage pacemaker resources
Commands:
    resource create <resource id> <provider:class:type|type> [resource options]
    resource delete <resource id>
    resource [list|show] [resource_id]
    resource group add <group name> <resource id>...
    resource group remove_resource <group name> <resource id> ...
    resource group list

Examples:
    pcs resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource create ClusterIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    pcs resource delete ClusterIP

    pcs resource list ClusterIP

    pcs resource list
"""

def corosync():
    print """
Usage: pcs corosync [commands]...
Configure corosync for use with pacemaker

Commands:
    configure [<bindnetaddr> <mcastaddr> <mcastport>]
        Configure corosync for use with pacemaker. If no options
        are specified the following values are used:
        bindnetaddr: (first local interface network address)
        mcastaddr:   226.94.1.1
        mcastport:   5405
"""

def property():
    print """
Usage: pcs property <properties>...
Configure pacemaker properties

Commands:
    [list|show [property]]
        List property settings (Default: all properties)

    set <property>=<value>
        Set specific pacemaker properties

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

    location [show resources|nodes]
        List all the current location constraints, if 'resources' is specified
        location constraints are displayed per resource (default), if 'nodes'
        is specified location constraints are displayed per node. 

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

    status nodes
        View current status of nodes

    status actions
        View failed actions
"""
