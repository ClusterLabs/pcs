from pcs import settings, utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.routing import create_router


def local_auth_cmd(lib, argv, modifiers):
    """
    Options:
      * -u - username
      * -p - password
      * --request-timeout - timeout for HTTP requests
    """
    del lib
    modifiers.ensure_only_supported("-u", "-p", "--request-timeout")
    if len(argv) > 1:
        raise CmdLineInputError()
    port = argv[0] if argv else settings.pcsd_default_port
    username, password = utils.get_user_and_pass()
    utils.auth_hosts(
        {
            "localhost": {
                "username": username,
                "password": password,
                "dest_list": [{"addr": "localhost", "port": port}]
            }
        }
    )


client_cmd = create_router(
    {
        "local-auth": local_auth_cmd,
    },
    ["client"],
)
