import re

# pylint: disable=too-many-lines, too-many-branches, global-statement

examples = ""


def full_usage():
    out = ""
    out += main(False)
    out += strip_extras(resource([], False))
    out += strip_extras(cluster([], False))
    out += strip_extras(stonith([], False))
    out += strip_extras(property([], False))
    out += strip_extras(constraint([], False))
    out += strip_extras(node([], False))
    out += strip_extras(acl([], False))
    out += strip_extras(qdevice([], False))
    out += strip_extras(quorum([], False))
    out += strip_extras(booth([], False))
    out += strip_extras(status([], False))
    out += strip_extras(config([], False))
    out += strip_extras(pcsd([], False))
    out += strip_extras(host([], False))
    out += strip_extras(alert([], False))
    out += strip_extras(client([], False))
    out += strip_extras(dr([], False))
    out += strip_extras(tag([], False))
    print(out.strip())
    print("Examples:\n" + examples.replace(r" \ ", ""))


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
    if not args:
        return output
    args_str = " ".join(args)

    ret = ""
    lines = output.split("\n")
    begin_printing = False
    usage = re.sub(r"\[commands\]", args_str, lines[1])
    for line in lines:
        if (
            begin_printing
            and re.match("^    [^ ]", line)
            and not re.match("^    " + args_str, line)
        ):
            begin_printing = False
        if not re.match("^ ", line) and not re.match("^$", line):
            begin_printing = False
        if re.match("^    " + args_str, line):
            begin_printing = True

        if begin_printing:
            ret += line + "\n"

    if ret.strip() != "":
        return "\n" + usage + "\n" + ret.rstrip() + "\n"
    return sub_usage([" ".join(args_str.split()[:-1])], output)


def dict_depth(d, depth=0):
    # pylint: disable=invalid-name
    if not isinstance(d, dict) or not d:
        return depth
    return max(dict_depth(v, depth + 1) for k, v in d.items())


def generate_completion_tree_from_usage():
    tree = {}
    tree["resource"] = generate_tree(resource([], False))
    tree["cluster"] = generate_tree(cluster([], False))
    tree["stonith"] = generate_tree(stonith([], False))
    tree["property"] = generate_tree(property([], False))
    tree["acl"] = generate_tree(acl([], False))
    tree["constraint"] = generate_tree(constraint([], False))
    tree["qdevice"] = generate_tree(qdevice([], False))
    tree["quorum"] = generate_tree(quorum([], False))
    tree["status"] = generate_tree(status([], False))
    tree["config"] = generate_tree(config([], False))
    tree["pcsd"] = generate_tree(pcsd([], False))
    tree["host"] = generate_tree(host([], False))
    tree["node"] = generate_tree(node([], False))
    tree["alert"] = generate_tree(alert([], False))
    tree["booth"] = generate_tree(booth([], False))
    tree["client"] = generate_tree(client([], False))
    tree["dr"] = generate_tree(dr([], False))
    tree["tag"] = generate_tree(tag([], False))
    return tree


def generate_tree(usage_txt):
    ignore = True
    ret_hash = {}
    for line in usage_txt.split("\n"):
        if line.startswith("Commands:"):
            ignore = False
            continue

        if line.startswith("Examples:"):
            break

        if ignore:
            continue

        if re.match(r"^    \w", line):
            args = line.split()
            arg = args.pop(0)
            if not arg in ret_hash:
                ret_hash[arg] = {}
            cur_hash = ret_hash[arg]
            for arg in args:
                if arg.startswith("[") or arg.startswith("<"):
                    break
                if not arg in cur_hash:
                    cur_hash[arg] = {}
                cur_hash = cur_hash[arg]
    return ret_hash


def main(pout=True):
    output = """
Usage: pcs [-f file] [-h] [commands]...
Control and configure pacemaker and corosync.

Options:
    -h, --help         Display usage and exit.
    -f file            Perform actions on file instead of active CIB.
                       Commands supporting the option use the initial state of
                       the specified file as their input and then overwrite the
                       file with the state reflecting the requested
                       operation(s).
                       A few commands only use the specified file in read-only
                       mode since their effect is not a CIB modification.
    --debug            Print all network traffic and external commands run.
    --version          Print pcs version information. List pcs capabilities if
                       --full is specified.
    --request-timeout  Timeout for each outgoing request to another node in
                       seconds. Default is 60s.
    --force            Override checks and errors, the exact behavior depends on
                       the command. WARNING: Using the --force option is
                       strongly discouraged unless you know what you are doing.

Commands:
    cluster     Configure cluster options and nodes.
    resource    Manage cluster resources.
    stonith     Manage fence devices.
    constraint  Manage resource constraints.
    property    Manage pacemaker properties.
    acl         Manage pacemaker access control lists.
    qdevice     Manage quorum device provider on the local host.
    quorum      Manage cluster quorum settings.
    booth       Manage booth (cluster ticket manager).
    status      View cluster status.
    config      View and manage cluster configuration.
    pcsd        Manage pcs daemon.
    host        Manage hosts known to pcs/pcsd.
    node        Manage cluster nodes.
    alert       Manage pacemaker alerts.
    client      Manage pcsd client configuration.
    dr          Manage disaster recovery configuration.
    tag         Manage pacemaker tags.
"""
    # Advanced usage to possibly add later
    #  --corosync_conf=<corosync file> Specify alternative corosync.conf file
    if pout:
        print(output)
        return None
    return output


def resource(args=(), pout=True):
    output = """
Usage: pcs resource [commands]...
Manage pacemaker resources

Commands:
    [status [<resource id | tag id>] [node=<node>] [--hide-inactive]]
        Show status of all currently configured resources. If --hide-inactive
        is specified, only show active resources. If a resource or tag id is
        specified, only show status of the specified resource or resources in
        the specified tag. If node is specified, only show status of resources
        configured for the specified node.

    config [<resource id>]...
        Show options of all currently configured resources or if resource ids
        are specified show the options for the specified resource ids.

    list [filter] [--nodesc]
        Show list of all available resource agents (if filter is provided then
        only resource agents matching the filter will be shown). If --nodesc is
        used then descriptions of resource agents are not printed.

    describe [<standard>:[<provider>:]]<type> [--full]
        Show options for the specified resource. If --full is specified, all
        options including advanced and deprecated ones are shown.

    create <resource id> [<standard>:[<provider>:]]<type> [resource options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...]
           [clone [<clone id>] [<clone options>] |
           promotable [<clone id>] [<promotable options>] |
           --group <group id> [--before <resource id> | --after <resource id>] |
           bundle <bundle id>] [--disabled] [--no-default-ops] [--wait[=n]]
        Create specified resource. If clone is used a clone resource is
        created. If promotable is used a promotable clone resource is created.
        If --group is specified the resource is added to the group named. You
        can use --before or --after to specify the position of the added
        resource relatively to some resource already existing in the group. If
        bundle is used, the resource will be created inside of the specified
        bundle. If --disabled is specified the resource is not started
        automatically. If --no-default-ops is specified, only monitor
        operations are created for the resource and all other operations use
        default settings. If --wait is specified, pcs will wait up to 'n'
        seconds for the resource to start and then return 0 if the resource is
        started, or 1 if the resource has not yet started. If 'n' is not
        specified it defaults to 60 minutes.
        Example: Create a new resource called 'VirtualIP' with IP address
            192.168.0.99, netmask of 32, monitored everything 30 seconds,
            on eth2:
            pcs resource create VirtualIP ocf:heartbeat:IPaddr2 \\
                ip=192.168.0.99 cidr_netmask=32 nic=eth2 \\
                op monitor interval=30s

    delete <resource id|group id|bundle id|clone id>
        Deletes the resource, group, bundle or clone (and all resources within
        the group/bundle/clone).

    remove <resource id|group id|bundle id|clone id>
        Deletes the resource, group, bundle or clone (and all resources within
        the group/bundle/clone).

    enable <resource id | tag id>... [--wait[=n]]
        Allow the cluster to start the resources. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resources may
        remain stopped. If --wait is specified, pcs will wait up to 'n' seconds
        for the resources to start and then return 0 if the resources are
        started, or 1 if the resources have not yet started. If 'n' is not
        specified it defaults to 60 minutes.

    disable <resource id | tag id>... [--safe [--brief] [--no-strict]]
            [--simulate [--brief]] [--wait[=n]]
        Attempt to stop the resources if they are running and forbid the
        cluster from starting them again. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resources may
        remain started.
        If --safe is specified, no changes to the cluster configuration will be
        made if other than specified resources would be affected in any way. If
        --brief is also specified, only errors are printed.
        If --no-strict is specified, no changes to the cluster configuration
        will be made if other than specified resources would get stopped or
        demoted. Moving resources between nodes is allowed.
        If --simulate is specified, no changes to the cluster configuration
        will be made and the effect of the changes will be printed instead. If
        --brief is also specified, only a list of affected resources will be
        printed.
        If --wait is specified, pcs will wait up to 'n' seconds for the
        resources to stop and then return 0 if the resources are stopped or 1
        if the resources have not stopped. If 'n' is not specified it defaults
        to 60 minutes.

    safe-disable <resource id | tag id>... [--brief] [--no-strict] 
            [--simulate [--brief]] [--wait[=n]] [--force]
        Attempt to stop the resources if they are running and forbid the
        cluster from starting them again. Depending on the rest of the
        configuration (constraints, options, failures, etc), the resources may
        remain started. No changes to the cluster configuration will be
        made if other than specified resources would be affected in any way.
        If --brief is specified, only errors are printed.
        If --no-strict is specified, no changes to the cluster configuration
        will be made if other than specified resources would get stopped or
        demoted. Moving resources between nodes is allowed.
        If --simulate is specified, no changes to the cluster configuration
        will be made and the effect of the changes will be printed instead. If
        --brief is also specified, only a list of affected resources will be
        printed.
        If --wait is specified, pcs will wait up to 'n' seconds for the
        resources to stop and then return 0 if the resources are stopped or 1
        if the resources have not stopped. If 'n' is not specified it defaults
        to 60 minutes.
        If --force is specified, checks for safe disable will be skipped.

    restart <resource id> [node] [--wait=n]
        Restart the resource specified. If a node is specified and if the
        resource is a clone or bundle it will be restarted only on the node
        specified. If --wait is specified, then we will wait up to 'n' seconds
        for the resource to be restarted and return 0 if the restart was
        successful or 1 if it was not.

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
        This command will force the specified resource to be monitored on this
        node  ignoring the cluster recommendations and print the output from
        monitoring the resource.  Using --full will give more detailed output.
        This is mainly used for debugging resources that fail to be monitored.

    move <resource id> [destination node] [--master]
            [[lifetime=<lifetime>] | [--autodelete [--strict]]] [--wait[=n]]
        Move the resource off the node it is currently running on by creating
        a -INFINITY location constraint to ban the node. If destination node is
        specified the resource will be moved to that node by creating
        an INFINITY location constraint to prefer the destination node. If
        --master is used the scope of the command is limited to the master role
        and you must use the promotable clone id (instead of the resource id).

        If lifetime is specified then the constraint will expire after that
        time, otherwise it defaults to infinity and the constraint can be
        cleared manually with 'pcs resource clear' or 'pcs constraint delete'.
        Lifetime is expected to be specified as ISO 8601 duration (see
        https://en.wikipedia.org/wiki/ISO_8601#Durations).

        If --autodelete is specified, a constraint needed for moving the
        resource will be automatically removed once the resource is running on
        it's new location. The command will fail in case it is not possible to
        verify that the resource will not be moved after deleting the
        constraint. If --strict is specified, the command will also fail if
        other resources would be affected.
        NOTE: This feature is still being worked on and thus may be changed in
        future.

        If --wait is specified, pcs will wait up to 'n' seconds for the
        resource to move and then return 0 on success or 1 on error. If 'n' is
        not specified it defaults to 60 minutes.

        If you want the resource to preferably avoid running on some nodes but
        be able to failover to them use 'pcs constraint location avoids'.

    ban <resource id> [node] [--master] [lifetime=<lifetime>] [--wait[=n]]
        Prevent the resource id specified from running on the node (or on the
        current node it is running on if no node is specified) by creating
        a -INFINITY location constraint. If --master is used the scope of the
        command is limited to the master role and you must use the promotable
        clone id (instead of the resource id).

        If lifetime is specified then the constraint will expire after that
        time, otherwise it defaults to infinity and the constraint can be
        cleared manually with 'pcs resource clear' or 'pcs constraint delete'.
        Lifetime is expected to be specified as ISO 8601 duration (see
        https://en.wikipedia.org/wiki/ISO_8601#Durations).

        If --wait is specified, pcs will wait up to 'n' seconds for the
        resource to move and then return 0 on success or 1 on error. If 'n' is
        not specified it defaults to 60 minutes.

        If you want the resource to preferably avoid running on some nodes but
        be able to failover to them use 'pcs constraint location avoids'.

    clear <resource id> [node] [--master] [--expired] [--wait[=n]]
        Remove constraints created by move and/or ban on the specified
        resource (and node if specified).
        If --master is used the scope of the command is limited to the master
        role and you must use the master id (instead of the resource id).
        If --expired is specified, only constraints with expired lifetimes will
        be removed.
        If --wait is specified, pcs will wait up to 'n' seconds for the
        operation to finish (including starting and/or moving resources if
        appropriate) and then return 0 on success or 1 on error. If 'n' is not
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

    op delete <resource id> <operation action> [<operation properties>...]
        Remove specified operation (note: you must specify the exact operation
        properties to properly remove an existing operation).

    op delete <operation id>
        Remove the specified operation id.

    op remove <resource id> <operation action> [<operation properties>...]
        Remove specified operation (note: you must specify the exact operation
        properties to properly remove an existing operation).

    op remove <operation id>
        Remove the specified operation id.

    op defaults [config] [--all] [--full] [--no-expire-check]
        List currently configured default values for operations. If --all is
        specified, also list expired sets of values. If --full is specified,
        also list ids. If --no-expire-check is specified, do not evaluate
        whether sets of values are expired.

    op defaults <name>=<value>...
        Set default values for operations.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    op defaults set create [<set options>] [meta [<name>=<value>]...]
            [rule [<expression>]]
        Create a new set of default values for resource operations. You may
        specify a rule describing resources and / or operations to which the set
        applies.

        Set options are: id, score

        Expression looks like one of the following:
          op <operation name> [interval=<interval>]
          resource [<standard>]:[<provider>]:[<type>]
          defined|not_defined <node attribute>
          <node attribute> lt|gt|lte|gte|eq|ne [string|integer|number|version]
              <value>
          date gt|lt <date>
          date in_range [<date>] to <date>
          date in_range <date> to duration <duration options>
          date-spec <date-spec options>
          <expression> and|or <expression>
          (<expression>)

        You may specify all or any of 'standard', 'provider' and 'type' in
        a resource expression. For example: 'resource ocf::' matches all
        resources of 'ocf' standard, while 'resource ::Dummy' matches all
        resources of 'Dummy' type regardless of their standard and provider.

        Dates are expected to conform to ISO 8601 format.

        Duration options are: hours, monthdays, weekdays, yearsdays, months,
        weeks, years, weekyears, moon. Value for these options is an integer.

        Date-spec options are: hours, monthdays, weekdays, yearsdays, months,
        weeks, years, weekyears, moon. Value for these options is an integer or
        a range written as integer-integer.

        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    op defaults set delete [<set id>]...
        Delete specified options sets.

    op defaults set remove [<set id>]...
        Delete specified options sets.

    op defaults set update <set id> [meta [<name>=<value>]...]
        Add, remove or change values in specified set of default values for
        resource operations.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    op defaults update <name>=<value>...
        Set default values for operations. This is a simplified command useful
        for cases when you only manage one set of default values.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    meta <resource id | group id | clone id> <meta options>
         [--wait[=n]]
        Add specified options to the specified resource, group or clone. Meta
        options should be in the format of name=value, options may be removed
        by setting an option without a value. If --wait is specified, pcs will
        wait up to 'n' seconds for the changes to take effect and then return 0
        if the changes have been processed or 1 otherwise. If 'n' is not
        specified it defaults to 60 minutes.
        Example: pcs resource meta TestResource failure-timeout=50 stickiness=

    group list
        Show all currently configured resource groups and their resources.

    group add <group id> <resource id> [resource id] ... [resource id]
              [--before <resource id> | --after <resource id>] [--wait[=n]]
        Add the specified resource to the group, creating the group
        if it does not exist. If the resource is present in another group 
        it is moved to the new group. If the group remains empty after move,
        it is deleted (for cloned groups, the clone is deleted as well). 
        The delete operation may fail in case the group is referenced
        within the configuration, e.g. by constraints. In that case, use 
        'pcs resource ungroup' command prior to moving all resources 
        out of the group. 

        You can use --before or --after to specify the position
        of the added resources relatively to some resource already existing
        in the group. By adding resources to a group they are already in and
        specifying --after or --before you can move the resources in the group.

        If --wait is specified, pcs will wait up to 'n' seconds for the
        operation to finish (including moving resources if appropriate) and
        then return 0 on success or 1 on error. If 'n' is not specified 
        it defaults to 60 minutes.

    group delete <group id> [resource id]... [--wait[=n]]
        Remove the group (note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group.  If --wait is specified, pcs will wait up to 'n' seconds
        for the operation to finish (including moving resources if appropriate)
        and the return 0 on success or 1 on error.  If 'n' is not specified it
        defaults to 60 minutes.

    group remove <group id> [resource id]... [--wait[=n]]
        Remove the group (note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group.  If --wait is specified, pcs will wait up to 'n' seconds
        for the operation to finish (including moving resources if appropriate)
        and the return 0 on success or 1 on error.  If 'n' is not specified it
        defaults to 60 minutes.

    ungroup <group id> [resource id]... [--wait[=n]]
        Remove the group (note: this does not remove any resources from the
        cluster) or if resources are specified, remove the specified resources
        from the group.  If --wait is specified, pcs will wait up to 'n' seconds
        for the operation to finish (including moving resources if appropriate)
        and the return 0 on success or 1 on error.  If 'n' is not specified it
        defaults to 60 minutes.

    clone <resource id | group id> [<clone id>] [clone options]... [--wait[=n]]
        Set up the specified resource or group as a clone. If --wait is
        specified, pcs will wait up to 'n' seconds for the operation to finish
        (including starting clone instances if appropriate) and then return 0
        on success or 1 on error. If 'n' is not specified it defaults to 60
        minutes.

    promotable <resource id | group id> [<clone id>] [clone options]...
            [--wait[=n]]
        Set up the specified resource or group as a promotable clone. This is
        an alias for 'pcs resource clone <resource id> promotable=true'.

    unclone <clone id | resource id | group id> [--wait[=n]]
        Remove the specified clone or the clone which contains the specified
        group or resource (the resource or group will not be removed). If
        --wait is specified, pcs will wait up to 'n' seconds for the operation
        to finish (including stopping clone instances if appropriate) and then
        return 0 on success or 1 on error. If 'n' is not specified it defaults
        to 60 minutes.

    bundle create <bundle id> container <container type> [<container options>]
            [network <network options>] [port-map <port options>]...
            [storage-map <storage options>]... [meta <meta options>]
            [--disabled] [--wait[=n]]
        Create a new bundle encapsulating no resources. The bundle can be used
        either as it is or a resource may be put into it at any time.
        If --disabled is specified, the bundle is not started automatically.
        If --wait is specified, pcs will wait up to 'n' seconds for the bundle
        to start and then return 0 on success or 1 on error. If 'n' is not
        specified it defaults to 60 minutes.

    bundle reset <bundle id> [container <container options>]
            [network <network options>] [port-map <port options>]...
            [storage-map <storage options>]... [meta <meta options>]
            [--disabled] [--wait[=n]]
        Configure specified bundle with given options. Unlike bundle update,
        this command resets the bundle according given options - no previous
        options are kept. Resources inside the bundle are kept as they are.
        If --disabled is specified, the bundle is not started automatically.
        If --wait is specified, pcs will wait up to 'n' seconds for the bundle
        to start and then return 0 on success or 1 on error. If 'n' is not
        specified it defaults to 60 minutes.

    bundle update <bundle id> [container <container options>]
            [network <network options>]
            [port-map (add <port options>) | (delete | remove <id>...)]...
            [storage-map (add <storage options>) | (delete | remove <id>...)]...
            [meta <meta options>]
            [--wait[=n]]
        Add, remove or change options to specified bundle. If you wish to update
        a resource encapsulated in the bundle, use the 'pcs resource update'
        command instead and specify the resource id. If --wait is specified,
        pcs will wait up to 'n' seconds for the operation to finish (including
        moving resources if appropriate) and then return 0 on success or 1 on
        error. If 'n' is not specified it defaults to 60 minutes.

    manage <resource id | tag id>... [--monitor]
        Set resources listed to managed mode (default). If --monitor is
        specified, enable all monitor operations of the resources.

    unmanage <resource id | tag id>... [--monitor]
        Set resources listed to unmanaged mode. When a resource is in unmanaged
        mode, the cluster is not allowed to start nor stop the resource. If
        --monitor is specified, disable all monitor operations of the
        resources.

    defaults [config] [--all] [--full] [--no-expire-check]
        List currently configured default values for resources. If --all is
        specified, also list expired sets of values. If --full is specified,
        also list ids. If --no-expire-check is specified, do not evaluate
        whether sets of values are expired.

    defaults <name>=<value>...
        Set default values for resources.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    defaults set create [<set options>] [meta [<name>=<value>]...]
            [rule [<expression>]]
        Create a new set of default values for resources. You may specify a rule
        describing resources to which the set applies.

        Set options are: id, score

        Expression looks like one of the following:
          resource [<standard>]:[<provider>]:[<type>]
          date gt|lt <date>
          date in_range [<date>] to <date>
          date in_range <date> to duration <duration options>
          date-spec <date-spec options>
          <expression> and|or <expression>
          (<expression>)

        You may specify all or any of 'standard', 'provider' and 'type' in
        a resource expression. For example: 'resource ocf::' matches all
        resources of 'ocf' standard, while 'resource ::Dummy' matches all
        resources of 'Dummy' type regardless of their standard and provider.

        Dates are expected to conform to ISO 8601 format.

        Duration options are: hours, monthdays, weekdays, yearsdays, months,
        weeks, years, weekyears, moon. Value for these options is an integer.

        Date-spec options are: hours, monthdays, weekdays, yearsdays, months,
        weeks, years, weekyears, moon. Value for these options is an integer or
        a range written as integer-integer.

        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    defaults set delete [<set id>]...
        Delete specified options sets.

    defaults set remove [<set id>]...
        Delete specified options sets.

    defaults set update <set id> [meta [<name>=<value>]...]
        Add, remove or change values in specified set of default values for
        resources.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    defaults update <name>=<value>...
        Set default values for resources. This is a simplified command useful
        for cases when you only manage one set of default values.
        NOTE: Defaults do not apply to resources which override them with their
        own defined values.

    cleanup [<resource id>] [node=<node>] [operation=<operation>
            [interval=<interval>]] [--strict]
        Make the cluster forget failed operations from history of the resource
        and re-detect its current state. This can be useful to purge knowledge
        of past failures that have since been resolved.
        If the named resource is part of a group, or one numbered instance of a
        clone or bundled resource, the clean-up applies to the whole collective
        resource unless --strict is given.
        If a resource id is not specified then all resources / stonith devices
        will be cleaned up.
        If a node is not specified then resources / stonith devices on all
        nodes will be cleaned up.

    refresh [<resource id>] [node=<node>] [--strict]
        Make the cluster forget the complete operation history (including
        failures) of the resource and re-detect its current state. If you are
        interested in forgetting failed operations only, use the 'pcs resource
        cleanup' command.
        If the named resource is part of a group, or one numbered instance of a
        clone or bundled resource, the refresh applies to the whole collective
        resource unless --strict is given.
        If a resource id is not specified then all resources / stonith devices
        will be refreshed.
        If a node is not specified then resources / stonith devices on all
        nodes will be refreshed.

    failcount show [<resource id>] [node=<node>] [operation=<operation>
            [interval=<interval>]] [--full]
        Show current failcount for resources, optionally filtered by a resource,
        node, operation and its interval. If --full is specified do not sum
        failcounts per resource and node. Use 'pcs resource cleanup' or 'pcs
        resource refresh' to reset failcounts.

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

    relations <resource id> [--full]
        Display relations of a resource specified by its id with other resources
        in a tree structure. Supported types of resource relations are:
        ordering constraints, ordering set constraints, relations defined by
        resource hierarchy (clones, groups, bundles). If --full is used, more
        verbose output will be printed.

Examples:

    pcs resource config
      Show all resources.

    pcs resource config VirtualIP
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
        return None
    return output


def cluster(args=(), pout=True):
    output = """
Usage: pcs cluster [commands]...
Configure cluster for use with pacemaker

Commands:
    setup <cluster name> (<node name> [addr=<node address>]...)...
            [transport knet|udp|udpu
                [<transport options>] [link <link options>]...
                [compression <compression options>] [crypto <crypto options>]
            ] [totem <totem options>] [quorum <quorum options>]
            ([--enable] [--start [--wait[=<n>]]] [--no-keys-sync])
            | [--corosync_conf <path>]
        Create a cluster from the listed nodes and synchronize cluster
        configuration files to them. If --corosync_conf is specified, do not
        connect to other nodes and save corosync.conf to the specified path; see
        'Local only mode' below for details.

        Nodes are specified by their names and optionally their addresses. If
        no addresses are specified for a node, pcs will configure corosync to
        communicate with that node using an address provided in 'pcs host auth'
        command. Otherwise, pcs will configure corosync to communicate with the
        node using the specified addresses.

        Transport knet:
        This is the default transport. It allows configuring traffic encryption
        and compression as well as using multiple addresses (links) for nodes.
        Transport options are:
            ip_version, knet_pmtud_interval, link_mode
        Link options are:
            link_priority, linknumber, mcastport, ping_interval,
            ping_precision, ping_timeout, pong_count, transport (udp or sctp)
            Each 'link' followed by options sets options for one link in the
            order the links are defined by nodes' addresses. You can set link
            options for a subset of links using a linknumber. See examples
            below.
        Compression options are:
            level, model, threshold
        Crypto options are:
            cipher, hash, model
            By default, encryption is enabled with cipher=aes256 and
            hash=sha256. To disable encryption, set cipher=none and hash=none.

        Transports udp and udpu:
        These transports are limited to one address per node. They do not
        support traffic encryption nor compression.
        Transport options are:
            ip_version, netmtu
        Link options are:
            bindnetaddr, broadcast, mcastaddr, mcastport, ttl

        Totem and quorum can be configured regardless of used transport.
        Totem options are:
            block_unlisted_ips, consensus, downcheck, fail_recv_const,
            heartbeat_failures_allowed, hold, join, max_messages,
            max_network_delay, merge, miss_count_const, send_join,
            seqno_unchanged_const, token, token_coefficient, token_retransmit,
            token_retransmits_before_loss_const, window_size
        Quorum options are:
            auto_tie_breaker, last_man_standing, last_man_standing_window,
            wait_for_all

        Transports and their options, link, compression, crypto and totem
        options are all documented in corosync.conf(5) man page; knet link
        options are prefixed 'knet_' there, compression options are prefixed
        'knet_compression_' and crypto options are prefixed 'crypto_'. Quorum
        options are documented in votequorum(5) man page.

        --enable will configure the cluster to start on nodes boot.
        --start will start the cluster right after creating it.
        --wait will wait up to 'n' seconds for the cluster to start.
        --no-keys-sync will skip creating and distributing pcsd SSL certificate
            and key and corosync and pacemaker authkey files. Use this if you
            provide your own certificates and keys.

        Local only mode:
        By default, pcs connects to all specified nodes to verify they can be
        used in the new cluster and to send cluster configuration files to them.
        If this is not what you want, specify --corosync_conf option followed by
        a file path. Pcs will save corosync.conf to the specified file and will
        not connect to cluster nodes. These are the task pcs skips in that case:
        * make sure the nodes are not running or configured to run a cluster
          already
        * make sure cluster packages are installed on all nodes and their
          versions are compatible
        * make sure there are no cluster configuration files on any node (run
          'pcs cluster destroy' and remove pcs_settings.conf file on all nodes)
        * synchronize corosync and pacemaker authkeys, /etc/corosync/authkey
          and /etc/pacemaker/authkey respectively, and the corosync.conf file
        * authenticate the cluster nodes against each other ('pcs cluster auth'
          or 'pcs host auth' command)
        * synchronize pcsd certificates (so that pcs web UI can be used in an HA
          mode)

        Examples:
        Create a cluster with default settings:
            pcs cluster setup newcluster node1 node2
        Create a cluster using two links:
            pcs cluster setup newcluster \\
                node1 addr=10.0.1.11 addr=10.0.2.11 \\
                node2 addr=10.0.1.12 addr=10.0.2.12
        Set link options for all links. Link options are matched to the links
            in order. The first link (link 0) has sctp transport, the second
            link (link 1) has mcastport 55405:
            pcs cluster setup newcluster \\
                node1 addr=10.0.1.11 addr=10.0.2.11 \\
                node2 addr=10.0.1.12 addr=10.0.2.12 \\
                transport knet link transport=sctp link mcastport=55405
        Set link options for the second and fourth links only. Link options are
            matched to the links based on the linknumber option (the first link
            is link 0):
            pcs cluster setup newcluster \\
                node1 \\
                addr=10.0.1.11 addr=10.0.2.11 addr=10.0.3.11 addr=10.0.4.11 \\
                node2 \\
                addr=10.0.1.12 addr=10.0.2.12 addr=10.0.3.12 addr=10.0.4.12 \\
                transport knet \\
                link linknumber=3 mcastport=55405 \\
                link linknumber=1 transport=sctp
        Create a cluster using udp transport with a non-default port:
            pcs cluster setup newcluster node1 node2 \\
                transport udp link mcastport=55405

    config [show] [--output-format <cmd|json|text>] [--corosync_conf <path>]
        Show cluster configuration. There are 3 formats of output available:
        'cmd', 'json' and 'text', default is 'text'. Format 'text' is a human
        friendly output. Format 'cmd' prints a cluster setup command which
        recreates a cluster with the same configuration. Format 'json' is a
        machine oriented output with cluster configuration. If --corosync_conf
        is specified, configuration file specified by <path> is used instead of
        the current cluster configuration.

    config update [transport <transport options>]
            [compression <compression options>] [crypto <crypto options>]
            [totem <totem options>] [--corosync_conf <path>]
        Update cluster configuration. If --corosync_conf is specified, update
        cluster configuration in file specified by <path>. All options are
        documented in corosync.conf(5) man page. There are different transport
        options for transport types. Compression and crypto options are only
        available for knet transport. Totem options can be set regardless of
        the transport type.

        Transport options for knet transport are:
            ip_version, knet_pmtud_interval, link_mode
        Transport options for udp and updu transports are:
            ip_version, netmtu
        Compression options are:
            level, model, threshold
        Crypto options are:
            cipher, hash, model
        Totem options are:
            block_unlisted_ips, consensus, downcheck, fail_recv_const,
            heartbeat_failures_allowed, hold, join, max_messages,
            max_network_delay, merge, miss_count_const, send_join,
            seqno_unchanged_const, token, token_coefficient, token_retransmit,
            token_retransmits_before_loss_const, window_size

    authkey corosync [<path>]
       Generate a new corosync authkey and distribute it to all cluster nodes.
       If <path> is specified, do not generate a key and use key from the file.

    start [--all | <node>... ] [--wait[=<n>]] [--request-timeout=<seconds>]
        Start a cluster on specified node(s). If no nodes are specified then
        start a cluster on the local node. If --all is specified then start
        a cluster on all nodes. If the cluster has many nodes then the start
        request may time out. In that case you should consider setting
        --request-timeout to a suitable value. If --wait is specified, pcs
        waits up to 'n' seconds for the cluster to get ready to provide
        services after the cluster has successfully started.

    stop [--all | <node>... ] [--request-timeout=<seconds>]
        Stop a cluster on specified node(s). If no nodes are specified then
        stop a cluster on the local node. If --all is specified then stop
        a cluster on all nodes. If the cluster is running resources which take
        long time to stop then the stop request may time out before the cluster
        actually stops. In that case you should consider setting
        --request-timeout to a suitable value.

    kill
        Force corosync and pacemaker daemons to stop on the local node
        (performs kill -9). Note that init system (e.g. systemd) can detect that
        cluster is not running and start it again. If you want to stop cluster
        on a node, run pcs cluster stop on that node.

    enable [--all | <node>... ]
        Configure cluster to run on node boot on specified node(s). If node is
        not specified then cluster is enabled on the local node. If --all is
        specified then cluster is enabled on all nodes.

    disable [--all | <node>... ]
        Configure cluster to not run on node boot on specified node(s). If node
        is not specified then cluster is disabled on the local node. If --all
        is specified then cluster is disabled on all nodes.

    auth [-u <username>] [-p <password>]
        Authenticate pcs/pcsd to pcsd on nodes configured in the local cluster.

    status
        View current cluster status (an alias of 'pcs status cluster').

    sync
        Sync cluster configuration (files which are supported by all
        subcommands of this command) to all cluster nodes.

    sync corosync
        Sync corosync configuration to all nodes found from current
        corosync.conf file.

    cib [filename] [scope=<scope> | --config]
        Get the raw xml from the CIB (Cluster Information Base). If a filename
        is provided, we save the CIB to that file, otherwise the CIB is
        printed. Specify scope to get a specific section of the CIB. Valid
        values of the scope are: acls, alerts, configuration, constraints,
        crm_config, fencing-topology, nodes, op_defaults, resources,
        rsc_defaults, tags. --config is the same as scope=configuration. Do not
        specify a scope if you want to edit the saved CIB using pcs (pcs -f
        <command>).

    cib-push <filename> [--wait[=<n>]]
            [diff-against=<filename_original> | scope=<scope> | --config]
        Push the raw xml from <filename> to the CIB (Cluster Information Base).
        You can obtain the CIB by running the 'pcs cluster cib' command, which
        is recommended first step when you want to perform desired
        modifications (pcs -f <command>) for the one-off push.
        If diff-against is specified, pcs diffs contents of filename against
        contents of filename_original and pushes the result to the CIB.
        Specify scope to push a specific section of the CIB. Valid values of
        the scope are: acls, alerts, configuration, constraints, crm_config,
        fencing-topology, nodes, op_defaults, resources, rsc_defaults, tags.
        --config is the same as scope=configuration. Use of --config is
        recommended. Do not specify a scope if you need to push the whole CIB
        or be warned in the case of outdated CIB.
        If --wait is specified wait up to 'n' seconds for changes to be applied.
        WARNING: the selected scope of the CIB will be overwritten by the
        current content of the specified file.
        Example:
            pcs cluster cib > original.xml
            cp original.xml new.xml
            pcs -f new.xml constraint location apache prefers node2
            pcs cluster cib-push new.xml diff-against=original.xml

    cib-upgrade
        Upgrade the CIB to conform to the latest version of the document schema.

    edit [scope=<scope> | --config]
        Edit the cib in the editor specified by the $EDITOR environment
        variable and push out any changes upon saving. Specify scope to edit a
        specific section of the CIB. Valid values of the scope are: acls,
        alerts, configuration, constraints, crm_config, fencing-topology,
        nodes, op_defaults, resources, rsc_defaults, tags. --config is the same
        as scope=configuration. Use of --config is recommended. Do not specify
        a scope if you need to edit the whole CIB or be warned in the case of
        outdated CIB.

    node add <node name> [addr=<node address>]... [watchdog=<watchdog path>]
            [device=<SBD device path>]... [--start [--wait[=<n>]]] [--enable]
            [--no-watchdog-validation]
        Add the node to the cluster and synchronize all relevant configuration
        files to the new node. This command can only be run on an existing
        cluster node.

        The new node is specified by its name and optionally its addresses. If
        no addresses are specified for the node, pcs will configure corosync to
        communicate with the node using an address provided in 'pcs host auth'
        command. Otherwise, pcs will configure corosync to communicate with the
        node using the specified addresses.

        Use 'watchdog' to specify a path to a watchdog on the new node, when
        SBD is enabled in the cluster. If SBD is configured with shared storage,
        use 'device' to specify path to shared device(s) on the new node.

        If --start is specified also start cluster on the new node, if --wait
        is specified wait up to 'n' seconds for the new node to start. If
        --enable is specified configure cluster to start on the new node on
        boot. If --no-watchdog-validation is specified, validation of watchdog
        will be skipped.

        WARNING: By default, it is tested whether the specified watchdog is
                 supported. This may cause a restart of the system when
                 a watchdog with no-way-out-feature enabled is present. Use
                 --no-watchdog-validation to skip watchdog validation.

    node delete <node name> [<node name>]...
        Shutdown specified nodes and remove them from the cluster.

    node remove <node name> [<node name>]...
        Shutdown specified nodes and remove them from the cluster.

    node add-remote <node name> [<node address>] [options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...] [--wait[=<n>]]
        Add the node to the cluster as a remote node. Sync all relevant
        configuration files to the new node. Start the node and configure it to
        start the cluster on boot.
        Options are port and reconnect_interval. Operations and meta
        belong to an underlying connection resource (ocf:pacemaker:remote).
        If node address is not specified for the node, pcs will configure
        pacemaker to communicate with the node using an address provided in
        'pcs host auth' command. Otherwise, pcs will configure pacemaker to
        communicate with the node using the specified addresses.
        If --wait is specified, wait up to 'n' seconds for the node to start.

    node delete-remote <node identifier>
        Shutdown specified remote node and remove it from the cluster.
        The node-identifier can be the name of the node or the address of the
        node.

    node remove-remote <node identifier>
        Shutdown specified remote node and remove it from the cluster.
        The node-identifier can be the name of the node or the address of the
        node.

    node add-guest <node name> <resource id> [options] [--wait[=<n>]]
        Make the specified resource a guest node resource. Sync all relevant
        configuration files to the new node. Start the node and configure it to
        start the cluster on boot.
        Options are remote-addr, remote-port and remote-connect-timeout.
        If remote-addr is not specified for the node, pcs will configure
        pacemaker to communicate with the node using an address provided in
        'pcs host auth' command. Otherwise, pcs will configure pacemaker to
        communicate with the node using the specified addresses.
        If --wait is specified, wait up to 'n' seconds for the node to start.

    node delete-guest <node identifier>
        Shutdown specified guest node and remove it from the cluster.
        The node-identifier can be the name of the node or the address of the
        node or id of the resource that is used as the guest node.

    node remove-guest <node identifier>
        Shutdown specified guest node and remove it from the cluster.
        The node-identifier can be the name of the node or the address of the
        node or id of the resource that is used as the guest node.

    node clear <node name>
        Remove specified node from various cluster caches. Use this if a
        removed node is still considered by the cluster to be a member of the
        cluster.

    link add <node_name>=<node_address>... [options <link options>]
        Add a corosync link. One address must be specified for each cluster
        node. If no linknumber is specified, pcs will use the lowest available
        linknumber.
        Link options (documented in corosync.conf(5) man page) are:
            link_priority, linknumber, mcastport, ping_interval,
            ping_precision, ping_timeout, pong_count, transport (udp or sctp)

    link delete <linknumber> [<linknumber>]...
        Remove specified corosync links.

    link remove <linknumber> [<linknumber>]...
        Remove specified corosync links.

    link update <linknumber> [<node_name>=<node_address>...]
            [options <link options>]
        Change node addresses / link options of an existing corosync link. Use
        this if you cannot add / remove links which is the preferred way.
        Link options (documented in corosync.conf(5) man page) are:
        for knet transport:
            link_priority, mcastport, ping_interval, ping_precision,
            ping_timeout, pong_count, transport (udp or sctp)
        for udp and udpu transports:
            bindnetaddr, broadcast, mcastaddr, mcastport, ttl

    uidgid
        List the current configured uids and gids of users allowed to connect
        to corosync.

    uidgid add [uid=<uid>] [gid=<gid>]
        Add the specified uid and/or gid to the list of users/groups
        allowed to connect to corosync.

    uidgid delete [uid=<uid>] [gid=<gid>]
        Remove the specified uid and/or gid from the list of users/groups
        allowed to connect to corosync.

    uidgid remove [uid=<uid>] [gid=<gid>]
        Remove the specified uid and/or gid from the list of users/groups
        allowed to connect to corosync.

    corosync [node]
        Get the corosync.conf from the specified node or from the current node
        if node not specified.

    reload corosync
        Reload the corosync configuration on the current node.

    destroy [--all]
        Permanently destroy the cluster on the current node, killing all
        cluster processes and removing all cluster configuration files. Using
        --all will attempt to destroy the cluster on all nodes in the local
        cluster.
        WARNING: This command permanently removes any cluster configuration that
        has been created. It is recommended to run 'pcs cluster stop' before
        destroying the cluster.

    verify [--full] [-f <filename>]
        Checks the pacemaker configuration (CIB) for syntax and common
        conceptual errors. If no filename is specified the check is performed
        on the currently running cluster. If --full is used more verbose output
        will be printed.

    report [--from "YYYY-M-D H:M:S" [--to "YYYY-M-D H:M:S"]] <dest>
        Create a tarball containing everything needed when reporting cluster
        problems.  If --from and --to are not used, the report will include
        the past 24 hours.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def stonith(args=(), pout=True):
    output = """
Usage: pcs stonith [commands]...
Configure fence devices for use with pacemaker

Commands:
    [status [<resource id | tag id>] [node=<node>] [--hide-inactive]]
        Show status of all currently configured stonith devices. If
        --hide-inactive is specified, only show active stonith devices. If a
        resource or tag id is specified, only show status of the specified
        resource or resources in the specified tag. If node is specified, only
        show status of resources configured for the specified node.

    config [<stonith id>]...
        Show options of all currently configured stonith devices or if stonith
        ids are specified show the options for the specified stonith device ids.

    list [filter] [--nodesc]
        Show list of all available stonith agents (if filter is provided then
        only stonith agents matching the filter will be shown). If --nodesc is
        used then descriptions of stonith agents are not printed.

    describe <stonith agent> [--full]
        Show options for specified stonith agent. If --full is specified, all
        options including advanced and deprecated ones are shown.

    create <stonith id> <stonith device type> [stonith device options]
           [op <operation action> <operation options> [<operation action>
           <operation options>]...] [meta <meta options>...]
           [--group <group id> [--before <stonith id> | --after <stonith id>]]
           [--disabled] [--wait[=n]]
        Create stonith device with specified type and options.
        If --group is specified the stonith device is added to the group named.
        You can use --before or --after to specify the position of the added
        stonith device relatively to some stonith device already existing in the
        group.
        If --disabled is specified the stonith device is not used.
        If --wait is specified, pcs will wait up to 'n' seconds for the stonith
        device to start and then return 0 if the stonith device is started, or 1
        if the stonith device has not yet started.  If 'n' is not specified it
        defaults to 60 minutes.
        Example: Create a device for nodes node1 and node2
            pcs stonith create MyFence fence_virt pcmk_host_list=node1,node2
        Example: Use port p1 for node n1 and ports p2 and p3 for node n2
            pcs stonith create MyFence fence_virt 'pcmk_host_map=n1:p1;n2:p2,p3'

    update <stonith id> [stonith device options]
        Add/Change options to specified stonith id.

    update-scsi-devices <stonith id> (set <device-path> [<device-path>...])
            | (add <device-path> [<device-path>...] delete|remove <device-path>
            [device-path>...])
        Update scsi fencing devices without affecting other resources. You must
        specify either list of set devices or at least one device for add or
        delete/remove devices. Stonith resource must be running on one cluster
        node. Each device will be unfenced on each cluster node running
        cluster. Supported fence agents: fence_scsi.

    delete <stonith id>
        Remove stonith id from configuration.

    remove <stonith id>
        Remove stonith id from configuration.

    enable <stonith id>... [--wait[=n]]
        Allow the cluster to use the stonith devices. If --wait is specified,
        pcs will wait up to 'n' seconds for the stonith devices to start and
        then return 0 if the stonith devices are started, or 1 if the stonith
        devices have not yet started. If 'n' is not specified it defaults to 60
        minutes.

    disable <stonith id>... [--wait[=n]]
        Attempt to stop the stonith devices if they are running and disallow
        the cluster to use them. If --wait is specified, pcs will wait up to
        'n' seconds for the stonith devices to stop and then return 0 if the
        stonith devices are stopped or 1 if the stonith devices have not
        stopped. If 'n' is not specified it defaults to 60 minutes.

    cleanup [<stonith id>] [--node <node>] [--strict]
        Make the cluster forget failed operations from history of the stonith
        device and re-detect its current state. This can be useful to purge
        knowledge of past failures that have since been resolved.
        If the named stonith device is part of a group, or one numbered
        instance of a clone or bundled resource, the clean-up applies to the
        whole collective resource unless --strict is given.
        If a stonith id is not specified then all resources / stonith devices
        will be cleaned up.
        If a node is not specified then resources / stonith devices on all
        nodes will be cleaned up.

    refresh [<stonith id>] [--node <node>] [--strict]
        Make the cluster forget the complete operation history (including
        failures) of the stonith device and re-detect its current state. If you
        are interested in forgetting failed operations only, use the 'pcs
        stonith cleanup' command.
        If the named stonith device is part of a group, or one numbered
        instance of a clone or bundled resource, the refresh applies to the
        whole collective resource unless --strict is given.
        If a stonith id is not specified then all resources / stonith devices
        will be refreshed.
        If a node is not specified then resources / stonith devices on all
        nodes will be refreshed.

    level [config]
        Lists all of the fencing levels currently configured.

    level add <level> <target> <stonith id> [stonith id]...
        Add the fencing level for the specified target with the list of stonith
        devices to attempt for that target at that level. Fence levels are
        attempted in numerical order (starting with 1). If a level succeeds
        (meaning all devices are successfully fenced in that level) then no
        other levels are tried, and the target is considered fenced.
        Target may be a node name <node_name> or %<node_name> or
        node%<node_name>, a node name regular expression regexp%<node_pattern>
        or a node attribute value attrib%<name>=<value>.

    level delete <level> [target <target>] [stonith <stonith id>...]
        Removes the fence level for the level, target and/or devices specified.
        If no target or devices are specified then the fence level is removed.
        Target may be a node name <node_name> or %<node_name> or
        node%<node_name>, a node name regular expression regexp%<node_pattern>
        or a node attribute value attrib%<name>=<value>.

    level remove <level> [target <target>] [stonith <stonith id>...]
        Removes the fence level for the level, target and/or devices specified.
        If no target or devices are specified then the fence level is removed.
        Target may be a node name <node_name> or %<node_name> or
        node%<node_name>, a node name regular expression regexp%<node_pattern>
        or a node attribute value attrib%<name>=<value>.

    level clear [target <target> | stonith <stonith id>...]
        Clears the fence levels on the target (or stonith id) specified or
        clears all fence levels if a target/stonith id is not specified.
        Target may be a node name <node_name> or %<node_name> or
        node%<node_name>, a node name regular expression regexp%<node_pattern>
        or a node attribute value attrib%<name>=<value>.
        Example: pcs stonith level clear stonith dev_a dev_b

    level verify
        Verifies all fence devices and nodes specified in fence levels exist.

    fence <node> [--off]
        Fence the node specified (if --off is specified, use the 'off' API
        call to stonith which will turn the node off instead of rebooting it).

    confirm <node> [--force]
        Confirm to the cluster that the specified node is powered off. This
        allows the cluster to recover from a situation where no stonith device
        is able to fence the node. This command should ONLY be used after
        manually ensuring that the node is powered off and has no access to
        shared resources.

        WARNING: If this node is not actually powered off or it does have
        access to shared resources, data corruption/cluster failure can occur.
        To prevent accidental running of this command, --force or interactive
        user response is required in order to proceed.

        NOTE: It is not checked if the specified node exists in the cluster
        in order to be able to work with nodes not visible from the local
        cluster partition.

    history [show [<node>]]
        Show fencing history for the specified node or all nodes if no node
        specified.

    history cleanup [<node>]
        Cleanup fence history of the specified node or all nodes if no node
        specified.

    history update
        Update fence history from all nodes.

    sbd enable [watchdog=<path>[@<node>]]... [device=<path>[@<node>]]...
               [<SBD_OPTION>=<value>]... [--no-watchdog-validation]
        Enable SBD in cluster. Default path for watchdog device is
        /dev/watchdog. Allowed SBD options: SBD_WATCHDOG_TIMEOUT (default: 5),
        SBD_DELAY_START (default: no), SBD_STARTMODE (default: always) and
        SBD_TIMEOUT_ACTION. SBD options are documented in sbd(8) man page. It
        is possible to specify up to 3 devices per node.
        If --no-watchdog-validation is specified, validation of watchdogs will
        be skipped.


        WARNING: Cluster has to be restarted in order to apply these changes.
        WARNING: By default, it is tested whether the specified watchdog is
                 supported. This may cause a restart of the system when
                 a watchdog with no-way-out-feature enabled is present. Use
                 --no-watchdog-validation to skip watchdog validation.

        Example of enabling SBD in cluster with watchdogs on node1 will be
        /dev/watchdog2, on node2 /dev/watchdog1, /dev/watchdog0 on all other
        nodes, device /dev/sdb on node1, device /dev/sda on all other nodes and
        watchdog timeout will bet set to 10 seconds:
        pcs stonith sbd enable \\
            watchdog=/dev/watchdog2@node1 \\
            watchdog=/dev/watchdog1@node2 \\
            watchdog=/dev/watchdog0 \\
            device=/dev/sdb@node1 \\
            device=/dev/sda \\
            SBD_WATCHDOG_TIMEOUT=10

    sbd disable
        Disable SBD in cluster.

        WARNING: Cluster has to be restarted in order to apply these changes.

    sbd device setup device=<path> [device=<path>]...
                     [watchdog-timeout=<integer>] [allocate-timeout=<integer>]
                     [loop-timeout=<integer>] [msgwait-timeout=<integer>]
        Initialize SBD structures on device(s) with specified timeouts.

        WARNING: All content on device(s) will be overwritten.

    sbd device message <device-path> <node> <message-type>
        Manually set a message of the specified type on the device for the node.
        Possible message types (they are documented in sbd(8) man page): test,
        reset, off, crashdump, exit, clear

    sbd status [--full]
        Show status of SBD services in cluster and local device(s) configured.
        If --full is specified, also dump of SBD headers on device(s)
        will be shown.

    sbd config
        Show SBD configuration in cluster.

    sbd watchdog list
        Show all available watchdog devices on the local node.

        WARNING: Listing available watchdogs may cause a restart of the system
                 when a watchdog with no-way-out-feature enabled is present.

    sbd watchdog test [<watchdog-path>]
        This operation is expected to force-reboot the local system without
        following any shutdown procedures using a watchdog. If no watchdog is
        specified, available watchdog will be used if only one watchdog device
        is available on the local system.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def property(args=(), pout=True):
    # pylint: disable=redefined-builtin
    output = """
Usage: pcs property [commands]...
Configure pacemaker properties

Commands:
    [config|list|show [<property> | --all | --defaults]] | [--all | --defaults]
        List property settings (default: lists configured properties).
        If --defaults is specified will show all property defaults, if --all
        is specified, current configured properties will be shown with unset
        properties and their defaults.
        See pacemaker-controld(7) and pacemaker-schedulerd(7) man pages for
        a description of the properties.

    set <property>=[<value>] ... [--force]
        Set specific pacemaker properties (if the value is blank then the
        property is removed from the configuration).  If a property is not
        recognized by pcs the property will not be created unless the
        --force is used.
        See pacemaker-controld(7) and pacemaker-schedulerd(7) man pages for
        a description of the properties.

    unset <property> ...
        Remove property from configuration.
        See pacemaker-controld(7) and pacemaker-schedulerd(7) man pages for
        a description of the properties.

Examples:
    pcs property set stonith-enabled=false
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def constraint(args=(), pout=True):
    output = """
Usage: pcs constraint [constraints]...
Manage resource constraints

Commands:
    [config | list | show] [--all] [--full]
        List all current constraints that are not expired. If --all
        is specified also show expired constraints. If --full is specified
        also list the constraint ids.

    location <resource> prefers <node>[=<score>] [<node>[=<score>]]...
        Create a location constraint on a resource to prefer the specified node
        with score (default score: INFINITY). Resource may be either a resource
        id <resource_id> or %<resource_id> or resource%<resource_id>, or a
        resource name regular expression regexp%<resource_pattern>.

    location <resource> avoids <node>[=<score>] [<node>[=<score>]]...
        Create a location constraint on a resource to avoid the specified node
        with score (default score: INFINITY). Resource may be either a resource
        id <resource_id> or %<resource_id> or resource%<resource_id>, or a
        resource name regular expression regexp%<resource_pattern>.

    location <resource> rule [id=<rule id>] [resource-discovery=<option>]
             [role=master|slave] [constraint-id=<id>]
             [score=<score> | score-attribute=<attribute>] <expression>
        Creates a location constraint with a rule on the specified resource
        where expression looks like one of the following:
          defined|not_defined <node attribute>
          <node attribute> lt|gt|lte|gte|eq|ne [string|integer|number|version]
              <value>
          date gt|lt <date>
          date in_range <date> to <date>
          date in_range <date> to duration <duration options>...
          date-spec <date spec options>...
          <expression> and|or <expression>
          ( <expression> )
        where duration options and date spec options are: hours, monthdays,
        weekdays, yeardays, months, weeks, years, weekyears, moon.
        Resource may be either a resource id <resource_id> or %<resource_id> or
        resource%<resource_id>, or a resource name regular expression
        regexp%<resource_pattern>. If score is omitted it defaults to INFINITY.
        If id is omitted one is generated from the resource id. If
        resource-discovery is omitted it defaults to 'always'.

    location [config | show [resources [<resource>...]] | [nodes [<node>...]]]
            [--all] [--full]
        List all the current location constraints that are not expired. If
        'resources' is specified, location constraints are displayed per
        resource (default). If 'nodes' is specified, location constraints are
        displayed per node. If specific nodes or resources are specified then
        we only show information about them. Resource may be either a resource
        id <resource_id> or %<resource_id> or resource%<resource_id>, or a
        resource name regular expression regexp%<resource_pattern>. If --full
        is specified show the internal constraint id's. If --all is
        specified show the expired constraints.

    location add <id> <resource> <node> <score> [resource-discovery=<option>]
        Add a location constraint with the appropriate id for the specified
        resource, node name and score. Resource may be either a resource id
        <resource_id> or %<resource_id> or resource%<resource_id>, or a
        resource name regular expression regexp%<resource_pattern>.

    location delete <id>
        Remove a location constraint with the appropriate id.

    location remove <id>
        Remove a location constraint with the appropriate id.

    order [config | show] [--full]
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
        Available options are sequential=true/false, require-all=true/false and
        action=start/promote/demote/stop. Available constraint_options are
        id=<constraint-id>, kind=Optional/Mandatory/Serialize and
        symmetrical=true/false.

    order delete <resource1> [resourceN]...
        Remove resource from any ordering constraint

    order remove <resource1> [resourceN]...
        Remove resource from any ordering constraint

    colocation [config | show] [--full]
        List all current colocation constraints (if --full is specified show
        the internal constraint id's as well).

    colocation add [<role>] <source resource id> with [<role>]
                   <target resource id> [score] [options] [id=constraint-id]
        Request <source resource> to run on the same node where pacemaker has
        determined <target resource> should run.  Positive values of score
        mean the resources should be run on the same node, negative values
        mean the resources should not be run on the same node.  Specifying
        'INFINITY' (or '-INFINITY') for the score forces <source resource> to
        run (or not run) with <target resource> (score defaults to "INFINITY").
        A role can be: 'Master', 'Slave', 'Started', 'Stopped' (if no role is
        specified, it defaults to 'Started').

    colocation set <resource1> [resourceN]... [options]
               [set <resourceX> ... [options]]
               [setoptions [constraint_options]]
        Create a colocation constraint with a resource set.
        Available options are sequential=true/false and
        role=Stopped/Started/Master/Slave. Available constraint_options are id
        and either of: score, score-attribute, score-attribute-mangle.

    colocation delete <source resource id> <target resource id>
        Remove colocation constraints with specified resources.

    colocation remove <source resource id> <target resource id>
        Remove colocation constraints with specified resources.

    ticket [config | show] [--full]
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
        Available options are role=Stopped/Started/Master/Slave. Required
        constraint option is ticket=<ticket>. Optional constraint options are
        id=<constraint-id> and loss-policy=fence/stop/freeze/demote.

    ticket delete <ticket> <resource id>
        Remove all ticket constraints with <ticket> from <resource id>.

    ticket remove <ticket> <resource id>
        Remove all ticket constraints with <ticket> from <resource id>.

    delete <constraint id>...
        Remove constraint(s) or constraint rules with the specified id(s).

    remove <constraint id>...
        Remove constraint(s) or constraint rules with the specified id(s).

    ref <resource>...
        List constraints referencing specified resource.

    rule add <constraint id> [id=<rule id>] [role=master|slave]
             [score=<score>|score-attribute=<attribute>] <expression>
        Add a rule to a location constraint specified by 'constraint id' where
        the expression looks like one of the following:
          defined|not_defined <node attribute>
          <node attribute> lt|gt|lte|gte|eq|ne [string|integer|number|version]
              <value>
          date gt|lt <date>
          date in_range <date> to <date>
          date in_range <date> to duration <duration options>...
          date-spec <date spec options>...
          <expression> and|or <expression>
          ( <expression> )
        where duration options and date spec options are: hours, monthdays,
        weekdays, yeardays, months, weeks, years, weekyears, moon.
        If score is omitted it defaults to INFINITY. If id is omitted, one is
        generated from the constraint id.

    rule delete <rule id>
        Remove a rule from its location constraint and if it's the last rule,
        the constraint will also be removed.

    rule remove <rule id>
        Remove a rule from its location constraint and if it's the last rule,
        the constraint will also be removed.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def acl(args=(), pout=True):
    output = """
Usage: pcs acl [commands]...
View and modify current cluster access control lists
Commands:

    [config | show]
        List all current access control lists.

    enable
        Enable access control lists.

    disable
        Disable access control lists.

    role create <role id> [description=<description>]
            [((read | write | deny) (xpath <query> | id <id>))...]
        Create a role with the id and (optional) description specified. Each
        role can also have an unlimited number of permissions (read/write/deny)
        applied to either an xpath query or the id of a specific element in the
        CIB.

        Permissions are applied to the selected XML element's entire XML
        subtree (all elements enclosed within it). Write permission grants the
        ability to create, modify, or remove the element and its subtree, and
        also the ability to create any "scaffolding" elements (enclosing
        elements that do not have attributes other than an ID). Permissions for
        more specific matches (more deeply nested elements) take precedence
        over more general ones. If multiple permissions are configured for the
        same match (for example, in different roles applied to the same user),
        any deny permission takes precedence, then write, then lastly read.

        An xpath may include an attribute expression to select only elements
        that match the expression, but the permission still applies to the
        entire element (and its subtree), not to the attribute alone. For
        example, using the xpath "//*[@name]" to give write permission would
        allow changes to the entirety of all elements that have a "name"
        attribute and everything enclosed by those elements. There is no way
        currently to give permissions for just one attribute of an element.
        That is to say, you can not define an ACL that allows someone to read
        just the dc-uuid attribute of the cib tag - that would select the cib
        element and give read access to the entire CIB.

    role delete <role id>
        Delete the role specified and remove it from any users/groups it was
        assigned to.

    role remove <role id>
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

    user remove <username>
        Remove the user specified (and roles assigned will be unassigned for
        the specified user).

    group create <group> [<role id>]...
        Create an ACL for the group specified and assign roles to the group.

    group delete <group>
        Remove the group specified (and roles assigned will be unassigned for
        the specified group).

    group remove <group>
        Remove the group specified (and roles assigned will be unassigned for
        the specified group).

    permission add <role id>
            ((read | write | deny) (xpath <query> | id <id>))...
        Add the listed permissions to the role specified. Permissions are
        applied to either an xpath query or the id of a specific element in the
        CIB.

        Permissions are applied to the selected XML element's entire XML
        subtree (all elements enclosed within it). Write permission grants the
        ability to create, modify, or remove the element and its subtree, and
        also the ability to create any "scaffolding" elements (enclosing
        elements that do not have attributes other than an ID). Permissions for
        more specific matches (more deeply nested elements) take precedence
        over more general ones. If multiple permissions are configured for the
        same match (for example, in different roles applied to the same user),
        any deny permission takes precedence, then write, then lastly read.

        An xpath may include an attribute expression to select only elements
        that match the expression, but the permission still applies to the
        entire element (and its subtree), not to the attribute alone. For
        example, using the xpath "//*[@name]" to give write permission would
        allow changes to the entirety of all elements that have a "name"
        attribute and everything enclosed by those elements. There is no way
        currently to give permissions for just one attribute of an element.
        That is to say, you can not define an ACL that allows someone to read
        just the dc-uuid attribute of the cib tag - that would select the cib
        element and give read access to the entire CIB.

    permission delete <permission id>
        Remove the permission id specified (permission id's are listed in
        parenthesis after permissions in 'pcs acl' output).

    permission remove <permission id>
        Remove the permission id specified (permission id's are listed in
        parenthesis after permissions in 'pcs acl' output).
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def status(args=(), pout=True):
    output = """
Usage: pcs status [commands]...
View current cluster and resource status
Commands:
    [status] [--full] [--hide-inactive]
        View all information about the cluster and resources (--full provides
        more details, --hide-inactive hides inactive resources).

    resources [<resource id | tag id>] [node=<node>] [--hide-inactive]
        Show status of all currently configured resources. If --hide-inactive
        is specified, only show active resources.  If a resource or tag id is
        specified, only show status of the specified resource or resources in
        the specified tag. If node is specified, only show status of resources
        configured for the specified node.

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

    booth
        Print current status of booth on the local node.

    nodes [corosync | both | config]
        View current status of nodes from pacemaker. If 'corosync' is
        specified, view current status of nodes from corosync instead. If
        'both' is specified, view current status of nodes from both corosync &
        pacemaker. If 'config' is specified, print nodes from corosync &
        pacemaker configuration.

    pcsd [<node>]...
        Show current status of pcsd on nodes specified, or on all nodes
        configured in the local cluster if no nodes are specified.

    xml
        View xml version of status (output from crm_mon -r -1 -X).
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def config(args=(), pout=True):
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

    checkpoint diff <checkpoint_number> <checkpoint_number>
        Show differences between the two specified checkpoints. Use checkpoint
        number 'live' to compare a checkpoint to the current live configuration.

    checkpoint restore <checkpoint_number>
        Restore cluster configuration to specified checkpoint.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def pcsd(args=(), pout=True):
    output = """
Usage: pcs pcsd [commands]...
Manage pcs daemon

Commands:
    certkey <certificate file> <key file>
        Load custom certificate and key files for use in pcsd.

    status [<node>]...
        Show current status of pcsd on nodes specified, or on all nodes
        configured in the local cluster if no nodes are specified.

    sync-certificates
        Sync pcsd certificates to all nodes in the local cluster.

    deauth [<token>]...
       Delete locally stored authentication tokens used by remote systems to
       connect to the local pcsd instance. If no tokens are specified all
       tokens will be deleted. After this command is run other nodes will need
       to re-authenticate against this node to be able to connect to it.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def host(args=(), pout=True):
    output = """
Usage: pcs host [commands]...
Manage hosts known to pcs/pcsd

Commands:
    auth (<host name> [addr=<address>[:<port>]])... [-u <username>]
            [-p <password>]
        Authenticate local pcs/pcsd against pcsd on specified hosts. It is
        possible to specify an address and a port via which pcs/pcsd will
        communicate with each host. If an address is not specified a host name
        will be used. If a port is not specified 2224 will be used.

    deauth [<host name>]...
       Delete authentication tokens which allow pcs/pcsd on the current system
       to connect to remote pcsd instances on specified host names. If the
       current system is a member of a cluster, the tokens will be deleted from
       all nodes in the cluster. If no host names are specified all tokens will
       be deleted. After this command is run this node will need to
       re-authenticate against other nodes to be able to connect to them.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def node(args=(), pout=True):
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

    maintenance [--all | <node>...] [--wait[=n]]
        Put specified node(s) into maintenance mode, if no nodes or options are
        specified the current node will be put into maintenance mode, if --all
        is specified all nodes will be put into maintenance mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be put into maintenance mode and then return 0 on success or 1 if
        the operation not succeeded yet. If 'n' is not specified it defaults
        to 60 minutes.

    unmaintenance [--all | <node>...] [--wait[=n]]
        Remove node(s) from maintenance mode, if no nodes or options are
        specified the current node will be removed from maintenance mode,
        if --all is specified all nodes will be removed from maintenance mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be removed from maintenance mode and then return 0 on success or 1 if
        the operation not succeeded yet. If 'n' is not specified it defaults
        to 60 minutes.

    standby [--all | <node>...] [--wait[=n]]
        Put specified node(s) into standby mode (the node specified will no
        longer be able to host resources), if no nodes or options are specified
        the current node will be put into standby mode, if --all is specified
        all nodes will be put into standby mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be put into standby mode and then return 0 on success or 1 if
        the operation not succeeded yet. If 'n' is not specified it defaults
        to 60 minutes.

    unstandby [--all | <node>...] [--wait[=n]]
        Remove node(s) from standby mode (the node specified will now be able to
        host resources), if no nodes or options are specified the current node
        will be removed from standby mode, if --all is specified all nodes will
        be removed from standby mode.
        If --wait is specified, pcs will wait up to 'n' seconds for the node(s)
        to be removed from standby mode and then return 0 on success or 1 if
        the operation not succeeded yet. If 'n' is not specified it defaults
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
        return None
    return output


def qdevice(args=(), pout=True):
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
        return None
    return output


def quorum(args=(), pout=True):
    output = """
Usage: pcs quorum <command>
Manage cluster quorum settings.

Commands:
    [config]
        Show quorum configuration.

    status
        Show quorum runtime status.

    device add [<generic options>] model <device model> [<model options>]
            [heuristics <heuristics options>]
        Add a quorum device to the cluster. Quorum device should be configured
        first with "pcs qdevice setup". It is not possible to use more than one
        quorum device in a cluster simultaneously.
        Currently the only supported model is 'net'. It requires model options
        'algorithm' and 'host' to be specified. Options are documented in
        corosync-qdevice(8) man page; generic options are 'sync_timeout' and
        'timeout', for model net options check the quorum.device.net section,
        for heuristics options see the quorum.device.heuristics section. Pcs
        automatically creates and distributes TLS certificates and sets the
        'tls' model option to the default value 'on'.
        Example: pcs quorum device add model net algorithm=lms \\
            host=qnetd.internal.example.com

    device heuristics delete
        Remove all heuristics settings of the configured quorum device.

    device heuristics remove
        Remove all heuristics settings of the configured quorum device.

    device delete
        Remove a quorum device from the cluster.

    device remove
        Remove a quorum device from the cluster.

    device status [--full]
        Show quorum device runtime status.  Using --full will give more detailed
        output.

    device update [<generic options>] [model <model options>]
            [heuristics <heuristics options>]
        Add/Change quorum device options. Requires the cluster to be stopped.
        Model and options are all documented in corosync-qdevice(8) man page;
        for heuristics options check the quorum.device.heuristics subkey
        section, for model options check the quorum.device.<device model> subkey
        sections.

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
        return None
    return output


def booth(args=(), pout=True):
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

    ticket delete <ticket>
        Remove the specified ticket from the current configuration.

    ticket remove <ticket>
        Remove the specified ticket from the current configuration.

    config [<node>]
        Show booth configuration from the specified node or from the current
        node if node not specified.

    create ip <address>
        Make the cluster run booth service on the specified ip address as
        a cluster resource.  Typically this is used to run booth site.

    delete
        Remove booth resources created by the "pcs booth create" command.

    remove
        Remove booth resources created by the "pcs booth create" command.

    restart
        Restart booth resources created by the "pcs booth create" command.

    ticket grant <ticket> [<site address>]
        Grant the ticket to the site specified by the address, hence to the
        booth formation this site is a member of. When this specification is
        omitted, site address that has been specified with 'pcs booth create'
        command is used. Specifying site address is therefore mandatory when
        running this command at a host in an arbitrator role.
        Note that the ticket must not be already granted in given booth
        formation; for an ad-hoc (and, in the worst case, abrupt, for a lack of
        a direct atomicity) change of this preference baring direct
        interventions at the sites, the ticket needs to be revoked first, only
        then it can be granted at another site again.

    ticket revoke <ticket> [<site address>]
        Revoke the ticket in the booth formation as identified with one of its
        member sites specified by the address. When this specification is
        omitted, site address that has been specified with a prior 'pcs booth
        create' command is used. Specifying site address is therefore mandatory
        when running this command at a host in an arbitrator role.

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
        return None
    return output


def alert(args=(), pout=True):
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
        Update an existing alert handler with specified id.

    delete <alert-id> ...
        Remove alert handlers with specified ids.

    remove <alert-id> ...
        Remove alert handlers with specified ids.

    recipient add <alert-id> value=<recipient-value> [id=<recipient-id>]
            [description=<description>] [options [<option>=<value>]...]
            [meta [<meta-option>=<value>]...]
        Add new recipient to specified alert handler.

    recipient update <recipient-id> [value=<recipient-value>]
            [description=<description>] [options [<option>=<value>]...]
            [meta [<meta-option>=<value>]...]
        Update an existing recipient identified by its id.

    recipient delete <recipient-id> ...
        Remove specified recipients.

    recipient remove <recipient-id> ...
        Remove specified recipients.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def client(args=(), pout=True):
    output = """
Usage: pcs client <command>
Manage pcsd client configuration.

Commands:
    local-auth [<pcsd-port>] [-u <username>] [-p <password>]
        Authenticate current user to local pcsd. This is required to run some
        pcs commands which may require permissions of root user such as 'pcs
        cluster start'.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def tag(args=(), pout=True):
    output = """
Usage: pcs tag <command>
Manage pacemaker tags.

Commands:
    [config|list [<tag id>...]]
        Display configured tags.

    create <tag id> <id> [<id>]...
        Create a tag containing the specified ids.

    delete <tag id>...
        Delete specified tags.

    remove <tag id>...
        Delete specified tags.

    update <tag id> [add <id> [<id>]... [--before <id> | --after <id>]]
            [remove <id> [<id>]...]
        Update a tag using the specified ids. Ids can be added, removed or
        moved in a tag. You can use --before or --after to specify the position
        of the added ids relatively to some id already existing in the tag. By
        adding ids to a tag they are already in and specifying --after or
        --before you can move the ids in the tag.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def dr(args=(), pout=True):
    output = """
Usage: pcs dr <command>
Manage disaster recovery configuration.

Commands:
    config
        Display disaster-recovery configuration from the local node.

    status [--full] [--hide-inactive]
        Display status of the local and the remote site cluster (--full
        provides more details, --hide-inactive hides inactive resources).

    set-recovery-site <recovery site node>
        Set up disaster-recovery with the local cluster being the primary site.
        The recovery site is defined by a name of one of its nodes.

    destroy
        Permanently destroy disaster-recovery configuration on all sites.
"""
    if pout:
        print(sub_usage(args, output))
        return None
    return output


def show(main_usage_name, rest_usage_names):
    usage_map = {
        "acl": acl,
        "alert": alert,
        "booth": booth,
        "client": client,
        "cluster": cluster,
        "config": config,
        "constraint": constraint,
        "dr": dr,
        "host": host,
        "node": node,
        "pcsd": pcsd,
        "property": property,
        "qdevice": qdevice,
        "quorum": quorum,
        "resource": resource,
        "status": status,
        "stonith": stonith,
        "tag": tag,
    }
    if main_usage_name not in usage_map:
        raise Exception(
            "Bad usage name '{0}' there can be '{1}'".format(
                main_usage_name, list(usage_map.keys())
            )
        )
    usage_map[main_usage_name](rest_usage_names)
