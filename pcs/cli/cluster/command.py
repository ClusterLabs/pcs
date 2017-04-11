from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.resource.parse_args import(
    parse_create_simple as parse_resource_create_args
)
from pcs.cli.common.errors import CmdLineInputError

def _node_add_remote_separate_host_and_name(arg_list):
    node_host = arg_list[0]
    if "=" in arg_list[1] or arg_list[1] in ["op", "meta"]:
        node_name = node_host
        rest_args = arg_list[1:]
    else:
        node_name = arg_list[1]
        rest_args = arg_list[2:]

    return node_host, node_name, rest_args

def node_add_remote(lib, arg_list, modifiers):
    if not arg_list:
        raise CmdLineInputError()

    node_host, node_name, rest_args = _node_add_remote_separate_host_and_name(
        arg_list
    )

    parts = parse_resource_create_args(rest_args)
    force = modifiers["force"]

    lib.cluster.node_add_remote(
        node_host,
        node_name,
        parts["op"],
        parts["meta"],
        parts["options"],
        allow_incomplete_distribution=force,
        allow_pacemaker_remote_service_fail=force,
        allow_invalid_operation=force,
        allow_invalid_instance_attributes=force,
        wait=modifiers["wait"],
    )
