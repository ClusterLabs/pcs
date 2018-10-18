from pcs import settings, utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError


def client_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        utils.exit_on_cmdline_input_errror(None, "client", "")

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "local-auth":
            local_auth_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "client", sub_cmd)


def local_auth_cmd(lib, argv, modifiers):
    """
    Options:
      * -u - username
      * -p - password
      * --request-timeout - timeout for HTTP requests
    """
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
