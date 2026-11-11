import json
import sys
from typing import Any, cast

from pcs import settings, utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv, InputModifiers
from pcs.cli.reports import output
from pcs.cli.reports.processor import report_and_exit_on_error
from pcs.common import file as pcs_file
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.auth import config as auth_config
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.interface.config import ParserErrorException
from pcs.lib.node import get_existing_nodes_names


def pcsd_deauth(lib, argv, modifiers):
    """
    Options: No options
    """
    del lib
    modifiers.ensure_only_supported()
    filepath = settings.pcsd_users_conf_location
    if not argv:
        try:
            with open(filepath, "w") as users_file:
                users_file.write(json.dumps([]))
        except OSError as e:
            utils.err(
                "Unable to edit data in {file}: {err}".format(
                    file=filepath, err=e
                )
            )
        return

    try:
        tokens_to_remove = set(argv)
        new_data = []
        with open(filepath, "r+") as users_file:
            old_data = json.loads(users_file.read())
            removed_tokens = set()
            for old_item in old_data:
                if old_item["token"] in tokens_to_remove:
                    removed_tokens.add(old_item["token"])
                else:
                    new_data.append(old_item)
            tokens_not_found = sorted(tokens_to_remove - removed_tokens)
            if tokens_not_found:
                utils.err(
                    "Following tokens were not found: '{tokens}'".format(
                        tokens="', '".join(tokens_not_found)
                    )
                )
            if removed_tokens:
                users_file.seek(0)
                users_file.truncate()
                users_file.write(json.dumps(new_data, indent=2))
    except KeyError as e:
        utils.err(
            "Unable to parse data in {file}: missing key {key}".format(
                file=filepath, key=e
            )
        )
    except ValueError as e:
        utils.err(
            "Unable to parse data in {file}: {err}".format(file=filepath, err=e)
        )
    except OSError as e:
        utils.err(
            "Unable to edit data in {file}: {err}".format(file=filepath, err=e)
        )


def accept_token_cmd(lib, argv, modifiers):
    del lib
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError("1 argument required")
    token = utils.get_token_from_file(argv[0])
    pcs_users_config = FileInstance.for_pcs_users_config()
    facade = auth_config.facade.Facade([])
    try:
        if pcs_users_config.raw_file.exists():
            facade = cast(
                auth_config.facade.Facade, pcs_users_config.read_to_facade()
            )
    except auth_config.parser.ParserError as e:
        output.warn(
            "Unable to parse file '{}': {}".format(
                pcs_users_config.raw_file.metadata.path, e.msg
            )
        )
    except JsonParserException:
        output.warn(
            "Unable to parse file '{}': not valid json".format(
                pcs_users_config.raw_file.metadata.path,
            )
        )
    except ParserErrorException:
        output.warn(
            "Unable to parse file '{}'".format(
                pcs_users_config.raw_file.metadata.path,
            )
        )
    except pcs_file.RawFileError as e:
        output.warn(
            "Unable to read file '{}': {}".format(
                pcs_users_config.raw_file.metadata.path,
                e.reason,
            )
        )
    facade.add_entry(SUPERUSER, token)
    try:
        pcs_users_config.write_facade(facade, can_overwrite=True)
    except pcs_file.RawFileError as e:
        raise output.error(raw_file_error_report(e).message.message) from e


def _check_nodes(node_list, prefix=""):
    """
    Print pcsd status on node_list, return if there is any pcsd not online

    Commandline options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    online_code = 0
    status_desc_map = {online_code: "Online", 3: "Unable to authenticate"}
    status_list = []

    def report(node, returncode, _output):
        del _output
        print(
            "{0}{1}: {2}".format(
                prefix, node, status_desc_map.get(returncode, "Offline")
            )
        )
        status_list.append(returncode)

    utils.read_known_hosts_file()  # cache known hosts
    utils.run_parallel(
        utils.create_task_list(report, utils.checkAuthorization, node_list)
    )

    return any(status != online_code for status in status_list)


def pcsd_status_cmd(
    lib: Any,
    argv: Argv,
    modifiers: InputModifiers,
    dont_exit: bool = False,
) -> None:
    """
    Options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    # If no arguments get current cluster node status, otherwise get listed
    # nodes status
    modifiers.ensure_only_supported("--request-timeout")
    bad_nodes = False
    if not argv:
        nodes, report_list = get_existing_nodes_names(
            utils.get_corosync_conf_facade()
        )
        if not nodes and not dont_exit:
            report_list.append(
                ReportItem.error(
                    reports.messages.CorosyncConfigNoNodesDefined()
                )
            )
        if report_list:
            report_and_exit_on_error(lib.env.report_processor, report_list)
        bad_nodes = _check_nodes(nodes, "  ")
    else:
        bad_nodes = _check_nodes(argv, "  ")
    if bad_nodes and not dont_exit:
        sys.exit(2)
