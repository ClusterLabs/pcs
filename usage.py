def main():
    print """
Usage: ccs [-f file] [-h] [commands]...
Control and configure pacemaker and corosync.

Options:
    -h          Display usage and exit
    -f file     Perform actions on file instead of active CIB

Commands:
    node        Manage nodes (NOT YET IMPLEMENTED)
    resource    Manage cluster resources
    corosync    Configure corosync
    property    Set pacemaker properties
    constraint  Set resource constraints
"""

def resource():
    print """Usage: ccs resource [commands]...
Manage pacemaker resources
Commands:
    resource create <resource id> <provider:class:type|type> [resource options]
    resource delete <resource id>
    resource list
    resource group add <group name> <resource id>...
    resource group remove_resource <group name> <resource id> ...
    resource group delete <group name>
    resource group list

Examples:
    ccs resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    ccs resource create ClusterIP IPaddr2 ip=192.168.0.99 \\
               cidr_netmask=32 op monitor interval=30s

    ccs resource delete ClusterIP

    ccs resource list
"""

def corosync():
    print """
Usage: ccs corosync [commands]...
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
Usage: ccs property <properties>...
Configure pacemaker properties

Commands:
    set <property>=<value>
        Set specific pacemaker properties

Examples:
    ccs property set stonith-enabled=false
"""

def constraint():
    print """
Usage: ccs constraint [constraints]...
Manage resource constraints

Commands:
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
"""
