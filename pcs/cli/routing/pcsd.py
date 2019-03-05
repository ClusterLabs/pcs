from pcs import (
    pcsd,
    usage,
)
from pcs.cli.common.routing import create_router


pcsd_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.pcsd(argv),
        "deauth": pcsd.pcsd_deauth,
        "certkey": pcsd.pcsd_certkey,
        "sync-certificates": pcsd.pcsd_sync_certs,
    },
    ["pcsd"]
)
