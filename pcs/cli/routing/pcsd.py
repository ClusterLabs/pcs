from pcs import (
    pcsd,
    usage,
)
from pcs.cli.common.routing import create_router


pcsd_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.pcsd(argv)),
        "accept_token": pcsd.accept_token_cmd,
        "deauth": pcsd.pcsd_deauth,
        "certkey": pcsd.pcsd_certkey_cmd,
        "status": pcsd.pcsd_status_cmd,
        "sync-certificates": pcsd.pcsd_sync_certs,
    },
    ["pcsd"],
)
