from __future__ import (
    absolute_import,
    division,
    print_function,
)

try:
    # python2
    from urlparse import urlparse
except ImportError:
    # python3
    from urllib.parse import urlparse

from pcs import (
    settings,
    usage,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def host_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        utils.exit_on_cmdline_input_errror(None, "host", "")
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.host([" ".join(argv_next)] if argv_next else [])
        elif sub_cmd == "auth":
            auth_cmd(lib, argv_next, modifiers)
        elif sub_cmd == "deauth":
            deauth_cmd(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "host", sub_cmd)


def _parse_host_options(host, options):
    ADDR_OPT_KEYWORD = "addr"
    supported_options = set([ADDR_OPT_KEYWORD])
    parsed_options = parse_args.prepare_options(options)
    unknown_options = set(parsed_options.keys()) - supported_options
    if unknown_options:
        raise CmdLineInputError(
            "Unknown options {} for host '{}'".format(
                ", ".join(unknown_options), host
            )
        )
    addr, port = _parse_addr(parsed_options.get(ADDR_OPT_KEYWORD, host))
    return {"dest_list": [dict(addr=addr, port=port)]}


def _parse_addr(addr):
    if addr.count(":") > 1 and not addr.startswith("["):
        # if IPv6 without port put it in parentheses
        addr = "[{0}]".format(addr)
    # adding protocol so urlparse will parse hostname/ip and port correctly
    url = urlparse("http://{0}".format(addr))
    return url.hostname, (url.port if url.port else settings.pcsd_default_port)


def _split_by_hosts(argv):
    if "=" in argv[0]:
        raise CmdLineInputError(
            "Invalid character '=' in host name '{}'".format(argv[0])
        )
    cur_host = None
    hosts = {}
    for arg in argv:
        if "=" in arg:
            hosts[cur_host].append(arg)
        else:
            cur_host = arg
            if cur_host in hosts:
                raise CmdLineInputError(
                    "Host '{}' defined multiple times".format(cur_host)
                )
            hosts[cur_host] = []
    return hosts


def _get_user_pass():
    if "-u" in utils.pcs_options:
        username = utils.pcs_options["-u"]
    else:
        username = utils.get_terminal_input('Username: ')

    if "-p" in utils.pcs_options:
        password = utils.pcs_options["-p"]
    else:
        password = utils.get_terminal_password()
    return username, password


def auth_cmd(lib, argv, modifiers):
    if not argv:
        raise CmdLineInputError("No host specified")
    host_dict = {
        host: _parse_host_options(host, opts)
        for host, opts in _split_by_hosts(argv).items()
    }
    username, password = _get_user_pass()
    for host_info in host_dict.values():
        host_info.update(dict(username=username, password=password))
    utils.auth_hosts(host_dict)


def deauth_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        remove_hosts = utils.read_known_hosts_file().keys()
    else:
        remove_hosts = argv
    output, retval = utils.run_pcsdcli(
        'remove_known_hosts',
        {'host_names': remove_hosts}
    )
    if retval == 0 and output['status'] == 'access_denied':
        utils.err('Access denied')
    if retval == 0 and output['status'] == 'ok' and output['data']:
        try:
            if output["data"]["hosts_not_found"]:
                utils.err("Following hosts were not found: '{hosts}'".format(
                    hosts="', '".join(output["data"]["hosts_not_found"])
                ))
            if not output['data']['sync_successful']:
                utils.err(
                    "Some nodes had a newer known-hosts than the local node. "
                        + "Local node's known-hosts were updated. "
                        + "Please repeat the action if needed."
                )
            if output['data']['sync_nodes_err']:
                utils.err(
                    (
                        "Unable to synchronize and save known-hosts on nodes: "
                        + "{0}. Run 'pcs host auth {1}' to make sure the nodes "
                        + "are authorized."
                    ).format(
                        ", ".join(output['data']['sync_nodes_err']),
                        " ".join(output['data']['sync_nodes_err'])
                    )
                )
        except (ValueError, KeyError):
            utils.err('Unable to communicate with pcsd')
        return
    utils.err('Unable to communicate with pcsd')
