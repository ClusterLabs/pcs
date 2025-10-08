from pcs import (
    usage,
)
from pcs.cli import host
from pcs.cli.common.routing import create_router

host_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.host(argv)),
        "auth": host.auth_cmd,
        "deauth": host.deauth_cmd,
    },
    ["host"],
)
