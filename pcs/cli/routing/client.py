from pcs import usage
from pcs.cli import client
from pcs.cli.common.routing import create_router

client_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: print(usage.client(argv)),
        "local-auth": client.local_auth_cmd,
    },
    ["client"],
)
