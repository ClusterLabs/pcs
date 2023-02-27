from pcs import (
    quorum,
    usage,
)
from pcs.cli.common.routing import create_router

quorum_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.quorum(argv)),
        "config": quorum.quorum_config_cmd,
        "expected-votes": quorum.quorum_expected_votes_cmd,
        "status": quorum.quorum_status_cmd,
        "device": create_router(
            {
                "add": quorum.quorum_device_add_cmd,
                "heuristics": create_router(
                    {
                        "delete": quorum.quorum_device_heuristics_remove_cmd,
                        "remove": quorum.quorum_device_heuristics_remove_cmd,
                    },
                    ["quorum", "device", "heuristics"],
                ),
                "delete": quorum.quorum_device_remove_cmd,
                "remove": quorum.quorum_device_remove_cmd,
                "status": quorum.quorum_device_status_cmd,
                "update": quorum.quorum_device_update_cmd,
                # used by ha_cluster system role
                "check_local_qnetd_certs": quorum.check_local_qnetd_certs_cmd,
                "setup_local_qnetd_certs": quorum.setup_local_qnetd_certs_cmd,
            },
            ["quorum", "device"],
        ),
        # TODO switch to new architecture
        "unblock": quorum.quorum_unblock_cmd,
        "update": quorum.quorum_update_cmd,
    },
    ["quorum"],
    default_cmd="config",
)
