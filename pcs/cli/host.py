from typing import Any
from urllib.parse import urlparse

from pcs import (
    settings,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
    ensure_unique_args,
    split_list_by_any_keywords,
)
from pcs.common.auth import HostAuthData, HostWithTokenAuthData
from pcs.common.host import Destination
from pcs.common.str_tools import format_list


def _parse_host_options(host: str, options: Argv) -> Destination:
    ADDR_OPT_KEYWORD = "addr"  # pylint: disable=invalid-name
    supported_options = {ADDR_OPT_KEYWORD}
    parsed_options = KeyValueParser(options).get_unique()
    unknown_options = set(parsed_options.keys()) - supported_options
    if unknown_options:
        raise CmdLineInputError(
            f"Unknown options {format_list(unknown_options)} for host '{host}'"
        )
    return _parse_addr(parsed_options.get(ADDR_OPT_KEYWORD, host))


def _parse_addr(addr: str) -> Destination:
    if addr.count(":") > 1 and not addr.startswith("["):
        # if IPv6 without port put it in parentheses
        addr = f"[{addr}]"
    # adding protocol so urlparse will parse hostname/ip and port correctly
    url = urlparse(f"http://{addr}")

    common_exception = CmdLineInputError(
        f"Invalid port number in address '{addr}', use 1..65535"
    )
    # Reading the port attribute will raise a ValueError if an invalid port is
    # specified in the URL.
    try:
        port = url.port
    except ValueError:
        raise common_exception from None
    # urlparse allow 0 as valid port number, pcs does not
    if port == 0:
        raise common_exception
    return Destination(
        addr=url.hostname or "",
        port=port if port else settings.pcsd_default_port,
    )


def auth_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -u - username
      * -p - password
      * --token - auth token
      * --request-timeout - timeout for HTTP requests
    """
    modifiers.ensure_only_supported("-u", "-p", "--request-timeout", "--token")
    if not argv:
        raise CmdLineInputError("No host specified")
    host_dict = {
        host: [_parse_host_options(host, opts)]
        for host, opts in split_list_by_any_keywords(argv, "host name").items()
    }
    token = modifiers.get("--token")
    if token:
        token_value = utils.get_token_from_file(str(token))
        lib.auth.auth_hosts_token_no_sync(
            {
                host_name: HostWithTokenAuthData(token_value, dest_list)
                for host_name, dest_list in host_dict.items()
            }
        )
        return

    username, password = utils.get_user_and_pass()
    lib.auth.auth_hosts(
        {
            host_name: HostAuthData(username, password, dest_list)
            for host_name, dest_list in host_dict.items()
        }
    )


def deauth_cmd(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --request-timeout - timeout for HTTP requests
    """
    modifiers.ensure_only_supported("--request-timeout")
    ensure_unique_args(argv)

    if not argv:
        lib.auth.deauth_all_local_hosts()
    else:
        lib.auth.deauth_hosts(argv)
