from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.cli.resource.parse_args import(
    parse_create_simple as parse_resource_create_args
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import prepare_options

def _node_add_remote_separate_host_and_name(arg_list):
    node_host = arg_list[0]
    if len(arg_list) == 1:
        node_name = node_host
        rest_args = []
    elif "=" in arg_list[1] or arg_list[1] in ["op", "meta"]:
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
        skip_offline_nodes=modifiers["skip_offline_nodes"],
        allow_incomplete_distribution=force,
        allow_pacemaker_remote_service_fail=force,
        allow_invalid_operation=force,
        allow_invalid_instance_attributes=force,
        use_default_operations=not modifiers["no-default-ops"],
        wait=modifiers["wait"],
    )

def create_node_remove_remote(remove_resource):
    def node_remove_remote(lib, arg_list, modifiers):
        if not arg_list:
            raise CmdLineInputError()
        lib.cluster.node_remove_remote(
            arg_list[0],
            remove_resource,
            skip_offline_nodes=modifiers["skip_offline_nodes"],
            allow_remove_multiple_nodes=modifiers["force"],
            allow_pacemaker_remote_service_fail=modifiers["force"],
        )
    return node_remove_remote

def node_add_guest(lib, arg_list, modifiers):
    if len(arg_list) < 2:
        raise CmdLineInputError()


    node_name = arg_list[0]
    resource_id = arg_list[1]
    meta_options = prepare_options(arg_list[2:])

    lib.cluster.node_add_guest(
        node_name,
        resource_id,
        meta_options,
        skip_offline_nodes=modifiers["skip_offline_nodes"],
        allow_incomplete_distribution=modifiers["force"],
        allow_pacemaker_remote_service_fail=modifiers["force"],
        wait=modifiers["wait"],
    )

def node_remove_guest(lib, arg_list, modifiers):
    if not arg_list:
        raise CmdLineInputError()

    lib.cluster.node_remove_guest(
        arg_list[0],
        skip_offline_nodes=modifiers["skip_offline_nodes"],
        allow_remove_multiple_nodes=modifiers["force"],
        allow_pacemaker_remote_service_fail=modifiers["force"],
        wait=modifiers["wait"],
    )

def node_clear(lib, arg_list, modifiers):
    if len(arg_list) != 1:
        raise CmdLineInputError()

    lib.cluster.node_clear(
        arg_list[0],
        allow_clear_cluster_node=modifiers["force"]
    )
