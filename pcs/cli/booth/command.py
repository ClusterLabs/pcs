from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import group_by_keywords, prepare_options


def config_setup(lib, arg_list, modifiers):
    """
    create booth config
    """
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

    lib.booth.config_setup(booth_config, modifiers["force"])

def config_destroy(lib, arg_list, modifiers):
    """
    destroy booth config
    """
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_destroy(ignore_config_load_problems=modifiers["force"])


def config_show(lib, arg_list, modifiers):
    """
    print booth config
    """
    if len(arg_list) > 1:
        raise CmdLineInputError()
    node = None if not arg_list else arg_list[0]

    print(lib.booth.config_text(node_name=node).rstrip())


def config_ticket_add(lib, arg_list, modifiers):
    """
    add ticket to current configuration
    """
    if not arg_list:
        raise CmdLineInputError
    lib.booth.config_ticket_add(
        arg_list[0],
        prepare_options(arg_list[1:]),
        allow_unknown_options=modifiers["force"]
    )

def config_ticket_remove(lib, arg_list, modifiers):
    """
    add ticket to current configuration
    """
    if len(arg_list) != 1:
        raise CmdLineInputError
    lib.booth.config_ticket_remove(arg_list[0])

def ticket_operation(lib_call, arg_list, modifiers):
    site_ip = None
    if len(arg_list) == 2:
        site_ip = arg_list[1]
    elif len(arg_list) != 1:
        raise CmdLineInputError()

    ticket = arg_list[0]
    lib_call(ticket, site_ip)

def ticket_revoke(lib, arg_list, modifiers):
    ticket_operation(lib.booth.ticket_revoke, arg_list, modifiers)

def ticket_grant(lib, arg_list, modifiers):
    ticket_operation(lib.booth.ticket_grant, arg_list, modifiers)

def create_in_cluster(lib, arg_list, modifiers):
    if len(arg_list) != 2 or arg_list[0] != "ip":
        raise CmdLineInputError()
    lib.booth.create_in_cluster(
        ip=arg_list[1],
        allow_absent_resource_agent=modifiers["force"]
    )

def get_remove_from_cluster(resource_remove):
    #TODO resource_remove is provisional hack until resources are not moved to
    #lib
    def remove_from_cluster(lib, arg_list, modifiers):
        if arg_list:
            raise CmdLineInputError()

        lib.booth.remove_from_cluster(
            resource_remove,
            modifiers["force"],
        )

    return remove_from_cluster

def get_restart(resource_restart):
    #TODO resource_restart is provisional hack until resources are not moved to
    #lib
    def restart(lib, arg_list, modifiers):
        if arg_list:
            raise CmdLineInputError()

        lib.booth.restart(resource_restart, modifiers["force"])

    return restart

def sync(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_sync(skip_offline_nodes=modifiers["skip_offline_nodes"])


def enable(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.enable()


def disable(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.disable()


def start(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.start()


def stop(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.stop()


def pull(lib, arg_list, modifiers):
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.pull(arg_list[0])


def status(lib, arg_list, modifiers):
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
