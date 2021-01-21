from pcs import (
    pcsd,
    usage,
)
from pcs.cli.common.errors import raise_command_replaced
from pcs.cli.common.routing import create_router


pcsd_cmd = create_router(
    {
        "help": lambda lib, argv, modifiers: usage.pcsd(argv),
        "accept_token": pcsd.accept_token_cmd,
        "deauth": pcsd.pcsd_deauth,
        "certkey": pcsd.pcsd_certkey,
        "sync-certificates": pcsd.pcsd_sync_certs,
        # removed commands
        # These print error messages which point users to the changes section in
        # pcs manpage.
        # To be removed in the next significant version.
        "clear-auth": lambda lib, argv, modifiers: raise_command_replaced(
            "pcs host deauth", "pcs pcsd deauth"
        ),
    },
    ["pcsd"],
)
