from pcs import (
    host,
    usage,
)
from pcs.cli.common.routing import create_router


host_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.host(argv),
        "auth": host.auth_cmd,
        "deauth": host.deauth_cmd,
    },
    ["host"]
)
