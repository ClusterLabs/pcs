from typing import Any

import pcs.cli.cluster.command as cluster_command
from pcs import (
    cluster,
    pcsd,
    status,
    usage,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
)
from pcs.cli.common.routing import create_router
from pcs.cli.reports.output import deprecation_warning
from pcs.utils import exit_on_cmdline_input_error


def certkey(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs pcsd certkey' instead."
    )
    try:
        return pcsd.pcsd_certkey_cmd(lib, argv, modifiers)
    except CmdLineInputError as e:
        return exit_on_cmdline_input_error(e, "pcsd", ["certkey"])


def pcsd_status(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs pcsd status' or 'pcs status pcsd' instead."
    )
    try:
        return pcsd.pcsd_status_cmd(lib, argv, modifiers)
    except CmdLineInputError as e:
        return exit_on_cmdline_input_error(e, "pcsd", ["status"])


cluster_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.cluster(argv)),
        "setup": cluster.cluster_setup,
        "config": create_router(
            {
                "show": cluster.config_show,
                "update": cluster.config_update,
                "uuid": create_router(
                    {
                        "generate": cluster.generate_uuid,
                    },
                    ["cluster", "config", "uuid"],
                ),
            },
            ["cluster", "config"],
            default_cmd="show",
        ),
        "authkey": create_router(
            {"corosync": cluster.authkey_corosync},
            ["cluster", "authkey"],
        ),
        "sync": create_router(
            {
                "corosync": cluster.sync_nodes,
            },
            ["cluster", "sync"],
            default_cmd="corosync",
        ),
        "status": status.cluster_status,
        # TODO remove, deprecated command
        # replaced with 'pcs pcsd status' and 'pcs status pcsd'
        "pcsd-status": pcsd_status,
        # TODO remove, deprecated command
        # replaced with 'pcs pcsd certkey'
        "certkey": certkey,
        "auth": cluster.cluster_auth_cmd,
        "start": cluster.cluster_start_cmd,
        "stop": cluster.cluster_stop_cmd,
        "kill": cluster.kill_cluster,
        "enable": cluster.cluster_enable_cmd,
        "disable": cluster.cluster_disable_cmd,
        "cib": cluster.get_cib,
        "cib-push": cluster.cluster_push,
        "cib-upgrade": cluster.cluster_cib_upgrade_cmd,
        "edit": cluster.cluster_edit,
        "link": create_router(
            {
                "add": cluster.link_add,
                "delete": cluster.link_remove,
                "remove": cluster.link_remove,
                "update": cluster.link_update,
            },
            ["cluster", "link"],
        ),
        "node": create_router(
            {
                "add": cluster.node_add,
                "add-guest": cluster_command.node_add_guest,
                "add-outside": cluster.node_add_outside_cluster,
                "add-remote": cluster_command.node_add_remote,
                "clear": cluster_command.node_clear,
                "delete": cluster.node_remove,
                "delete-guest": cluster_command.node_remove_guest,
                "delete-remote": cluster_command.node_remove_remote,
                "remove": cluster.node_remove,
                "remove-guest": cluster_command.node_remove_guest,
                "remove-remote": cluster_command.node_remove_remote,
            },
            ["cluster", "node"],
        ),
        "uidgid": cluster.cluster_uidgid,
        "corosync": cluster.cluster_get_corosync_conf,
        "reload": cluster.cluster_reload,
        "destroy": cluster.cluster_destroy,
        "verify": cluster.cluster_verify,
        "report": cluster.cluster_report,
        "remove_nodes_from_cib": cluster.remove_nodes_from_cib,
    },
    ["cluster"],
)
