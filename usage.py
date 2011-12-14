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


