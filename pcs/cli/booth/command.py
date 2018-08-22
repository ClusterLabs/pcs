from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import group_by_keywords, prepare_options


def config_setup(lib, arg_list, modifiers):
    """
    create booth config

    Options:
      * --force - overwrite existing
      * --booth-conf - booth config file
      * --booth-key - booth authkey file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported(
        "--force", "--booth-conf", "--booth-key", "--name",
    )
    peers = group_by_keywords(
        arg_list,
        set(["sites", "arbitrators"]),
        keyword_repeat_allowed=False
    )
    if "sites" not in peers or not peers["sites"]:
        raise CmdLineInputError()

    booth_config = []
    for site in peers["sites"]:
        booth_config.append({"key": "site", "value": site, "details": []})
    for arbitrator in peers["arbitrators"]:
        booth_config.append({
            "key": "arbitrator",
            "value": arbitrator,
            "details": [],
        })

    lib.booth.config_setup(
        booth_config, overwrite_existing=modifiers.get("--force")
    )

def config_destroy(lib, arg_list, modifiers):
    """
    destroy booth config

    Options:
      --force - ignore config load issues
      --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--force", "--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_destroy(
        ignore_config_load_problems=modifiers.get("--force")
    )


def config_show(lib, arg_list, modifiers):
    """
    print booth config

    Options:
      * --name - name of a booth instace
      * --booth-conf - booth config file, effective only when no node is
        specified
      * --booth-key - booth auth key file, not required by the command (just
        from middleware)
      * --request-timeout - HTTP timeout for getting config from remote host
    """
    modifiers.ensure_only_supported(
        "--name", "--booth-conf", "--request-timeout", "--booth-key"
    )
    if len(arg_list) > 1:
        raise CmdLineInputError()
    node = None if not arg_list else arg_list[0]

    print(lib.booth.config_text(node_name=node).rstrip())


def config_ticket_add(lib, arg_list, modifiers):
    """
    add ticket to current configuration

    Options:
      * --force - ignore config load issues
      * --booth-conf - booth config file
      * --booth-key - booth auth key file, not required by the command (just
        from middleware)
      * --name - name of a booth instace
    """
    modifiers.ensure_only_supported(
        "--force", "--booth-conf", "--name", "--booth-key"
    )
    if not arg_list:
        raise CmdLineInputError
    lib.booth.config_ticket_add(
        arg_list[0],
        prepare_options(arg_list[1:]),
        allow_unknown_options=modifiers.get("--force")
    )

def config_ticket_remove(lib, arg_list, modifiers):
    """
    add ticket to current configuration

    Options:
      * --booth-conf - booth config file
      * --booth-key - booth auth key file, not required by the command (just
        from middleware)
      * --name - name of a booth instace
    """
    modifiers.ensure_only_supported("--booth-conf", "--name", "--booth-key")
    if len(arg_list) != 1:
        raise CmdLineInputError
    lib.booth.config_ticket_remove(arg_list[0])

def _ticket_operation(lib_call, arg_list):
    """
    Commandline options:
      * --name - name of a booth instance
      * -f - CIB file
    """
    site_ip = None
    if len(arg_list) == 2:
        site_ip = arg_list[1]
    elif len(arg_list) != 1:
        raise CmdLineInputError()

    ticket = arg_list[0]
    lib_call(ticket, site_ip)

def ticket_revoke(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--name")
    _ticket_operation(lib.booth.ticket_revoke, arg_list)

def ticket_grant(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--name")
    _ticket_operation(lib.booth.ticket_grant, arg_list)

def create_in_cluster(lib, arg_list, modifiers):
    """
    Options:
      * --force - allows to create booth resource even if its agent is not
        installed
      * -f - CIB file
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--force", "-f", "--name")
    if len(arg_list) != 2 or arg_list[0] != "ip":
        raise CmdLineInputError()
    lib.booth.create_in_cluster(
        ip=arg_list[1],
        allow_absent_resource_agent=modifiers.get("--force")
    )

def get_remove_from_cluster(resource_remove):
    #TODO resource_remove is provisional hack until resources are not moved to
    #lib
    def remove_from_cluster(lib, arg_list, modifiers):
        """
        Options:
          * --force - allow remove of multiple
          * -f - CIB file
          * --name - name of a booth instance
        """
        modifiers.ensure_only_supported("--force", "-f", "--name")
        if arg_list:
            raise CmdLineInputError()

        lib.booth.remove_from_cluster(
            resource_remove,
            allow_remove_multiple=modifiers.get("--force"),
        )

    return remove_from_cluster

def get_restart(resource_restart):
    #TODO resource_restart is provisional hack until resources are not moved to
    #lib
    def restart(lib, arg_list, modifiers):
        """
        Options:
          * --force - allow multiple
          * -f - CIB file
          * --name - name of a booth instance
        """
        modifiers.ensure_only_supported("--force", "-f", "--name")
        if arg_list:
            raise CmdLineInputError()

        lib.booth.restart(
            resource_restart,
            allow_multiple=modifiers.get("--force"),
        )

    return restart

def sync(lib, arg_list, modifiers):
    """
    Options:
      * --skip-offline - skip offline nodes
      * --name - name of a booth instance
      * --booth-conf - booth config file
      * --booth-key - booth authkey file
      * --request-timeout - HTTP timeout for file ditribution
    """
    modifiers.ensure_only_supported(
        "--skip-offline", "--name", "--booth-conf", "--booth-key",
        "--request-timeout",
    )
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_sync(skip_offline_nodes=modifiers.get("--skip-offline"))


def enable(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.enable()


def disable(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.disable()


def start(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.start()


def stop(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    lib.booth.stop()


def pull(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of a booth instance
      * --request-timeout - HTTP timeout for file ditribution
    """
    modifiers.ensure_only_supported("--name", "--request-timeout")
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.pull(arg_list[0])


def status(lib, arg_list, modifiers):
    """
    Options:
      * --name - name of booth instance
    """
    modifiers.ensure_only_supported("--name")
    if arg_list:
        raise CmdLineInputError()
    booth_status = lib.booth.status()
    if booth_status.get("ticket"):
        print("TICKETS:")
        print(booth_status["ticket"])
    if booth_status.get("peers"):
        print("PEERS:")
        print(booth_status["peers"])
    if booth_status.get("status"):
        print("DAEMON STATUS:")
        print(booth_status["status"])
