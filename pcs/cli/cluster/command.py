from typing import (
    Any,
    Optional,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
)
from pcs.cli.resource.parse_args import (
    parse_primitive as parse_primitive_resource,
)


def _node_add_remote_separate_name_and_addr(
    arg_list: Argv,
) -> tuple[str, Optional[str], list[str]]:
    """
    Commandline options: no options
    """
    node_name = arg_list[0]
    if len(arg_list) == 1:
        node_addr = None
        rest_args = []
    elif "=" in arg_list[1] or arg_list[1] in ["op", "meta"]:
        node_addr = None
        rest_args = arg_list[1:]
    else:
        node_addr = arg_list[1]
        rest_args = arg_list[2:]
    return node_name, node_addr, rest_args


def node_add_remote(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --wait
      * --force - allow incomplete distribution of files, allow pcmk remote
        service to fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      * --no-default-ops - do not use default operations
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
        "--no-default-ops",
    )
    if not arg_list:
        raise CmdLineInputError()

    node_name, node_addr, rest_args = _node_add_remote_separate_name_and_addr(
        arg_list
    )

    parts = parse_primitive_resource(rest_args)
    force = modifiers.get("--force")

    lib.remote_node.node_add_remote(
        node_name,
        node_addr,
        parts.operations,
        parts.meta_attrs,
        parts.instance_attrs,
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_incomplete_distribution=force,
        allow_pacemaker_remote_service_fail=force,
        allow_invalid_operation=force,
        allow_invalid_instance_attributes=force,
        use_default_operations=not modifiers.get("--no-default-ops"),
        wait=modifiers.get("--wait"),
    )


def create_node_remove_remote(remove_resource):  # type:ignore
    def node_remove_remote(
        lib: Any, arg_list: Argv, modifiers: InputModifiers
    ) -> None:
        """
        Options:
          * --force - allow multiple nodes removal, allow pcmk remote service
            to fail, don't stop a resource before its deletion (this is side
            effect of old resource delete command used here)
          * --skip-offline - skip offline nodes
          * --request-timeout - HTTP request timeout
          For tests:
          * --corosync_conf
          * -f
        """
        modifiers.ensure_only_supported(
            "--force",
            "--skip-offline",
            "--request-timeout",
            "--corosync_conf",
            "-f",
        )
        if len(arg_list) != 1:
            raise CmdLineInputError()
        lib.remote_node.node_remove_remote(
            arg_list[0],
            remove_resource,
            skip_offline_nodes=modifiers.get("--skip-offline"),
            allow_remove_multiple_nodes=modifiers.get("--force"),
            allow_pacemaker_remote_service_fail=modifiers.get("--force"),
        )

    return node_remove_remote


def node_add_guest(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --wait
      * --force - allow incomplete distribution of files, allow pcmk remote
        service to fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
    )
    if len(arg_list) < 2:
        raise CmdLineInputError()

    node_name = arg_list[0]
    resource_id = arg_list[1]
    meta_options = KeyValueParser(arg_list[2:]).get_unique()

    lib.remote_node.node_add_guest(
        node_name,
        resource_id,
        meta_options,
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_incomplete_distribution=modifiers.get("--force"),
        allow_pacemaker_remote_service_fail=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )


def node_remove_guest(
    lib: Any, arg_list: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --wait
      * --force - allow multiple nodes removal, allow pcmk remote service to
        fail
      * --skip-offline - skip offline nodes
      * --request-timeout - HTTP request timeout
      For tests:
      * --corosync_conf
      * -f
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--force",
        "--skip-offline",
        "--request-timeout",
        "--corosync_conf",
        "-f",
    )
    if len(arg_list) != 1:
        raise CmdLineInputError()

    lib.remote_node.node_remove_guest(
        arg_list[0],
        skip_offline_nodes=modifiers.get("--skip-offline"),
        allow_remove_multiple_nodes=modifiers.get("--force"),
        allow_pacemaker_remote_service_fail=modifiers.get("--force"),
        wait=modifiers.get("--wait"),
    )


def node_clear(lib: Any, arg_list: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --force - allow to clear a cluster node
    """
    modifiers.ensure_only_supported("--force")
    if len(arg_list) != 1:
        raise CmdLineInputError()

    lib.cluster.node_clear(
        arg_list[0], allow_clear_cluster_node=modifiers.get("--force")
    )
