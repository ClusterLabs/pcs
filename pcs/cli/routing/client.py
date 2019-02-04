from pcs import client
from pcs.cli.common.routing import create_router


client_cmd = create_router(
    {
        "local-auth": client.local_auth_cmd,
    },
    ["client"],
)
