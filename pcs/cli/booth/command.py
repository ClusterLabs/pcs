from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import group_by_keywords, prepare_options


DEFAULT_BOOTH_NAME = "booth"

def __get_name(modifiers):
    return  modifiers["name"] if modifiers["name"] else DEFAULT_BOOTH_NAME

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

    print(lib.booth.config_text(DEFAULT_BOOTH_NAME, node), end="")


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
    lib_call(__get_name(modifiers), ticket, site_ip)

def ticket_revoke(lib, arg_list, modifiers):
    ticket_operation(lib.booth.ticket_revoke, arg_list, modifiers)

def ticket_grant(lib, arg_list, modifiers):
    ticket_operation(lib.booth.ticket_grant, arg_list, modifiers)

def get_create_in_cluster(resource_create, resource_remove):
    #TODO resource_remove is provisional hack until resources are not moved to
    #lib
    def create_in_cluster(lib, arg_list, modifiers):
        if len(arg_list) != 2 or arg_list[0] != "ip":
            raise CmdLineInputError()
        ip = arg_list[1]

        lib.booth.create_in_cluster(
            __get_name(modifiers),
            ip,
            resource_create,
            resource_remove,
        )
    return create_in_cluster

def get_remove_from_cluster(resource_remove):
    #TODO resource_remove is provisional hack until resources are not moved to
    #lib
    def remove_from_cluster(lib, arg_list, modifiers):
        if arg_list:
            raise CmdLineInputError()

        lib.booth.remove_from_cluster(
            __get_name(modifiers),
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

        lib.booth.restart(
            __get_name(modifiers),
            resource_restart,
            modifiers["force"],
        )

    return restart

def sync(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.config_sync(
        DEFAULT_BOOTH_NAME,
        skip_offline_nodes=modifiers["skip_offline_nodes"]
    )


def enable(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.enable(DEFAULT_BOOTH_NAME)


def disable(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.disable(DEFAULT_BOOTH_NAME)


def start(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.start(DEFAULT_BOOTH_NAME)


def stop(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    lib.booth.stop(DEFAULT_BOOTH_NAME)


def pull(lib, arg_list, modifiers):
    if len(arg_list) != 1:
        raise CmdLineInputError()
    lib.booth.pull(arg_list[0], DEFAULT_BOOTH_NAME)


def status(lib, arg_list, modifiers):
    if arg_list:
        raise CmdLineInputError()
    booth_status = lib.booth.status(DEFAULT_BOOTH_NAME)
    if booth_status.get("ticket"):
        print("TICKETS:")
        print(booth_status["ticket"])
    if booth_status.get("peers"):
        print("PEERS:")
        print(booth_status["peers"])
    if booth_status.get("status"):
        print("DAEMON STATUS:")
        print(booth_status["status"])

