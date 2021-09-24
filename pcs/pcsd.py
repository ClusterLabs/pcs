import json
import os
import sys
from typing import (
    Any,
    Sequence,
)

from pcs import settings, utils
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import print_to_stderr
from pcs.common import reports
from pcs.common.reports.item import ReportItem
import pcs.common.ssl
from pcs.lib.node import get_existing_nodes_names


def pcsd_certkey_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - overwrite existing file
    """
    del lib
    modifiers.ensure_only_supported("--force")
    if len(argv) != 2:
        raise CmdLineInputError()

    certfile = argv[0]
    keyfile = argv[1]

    try:
        with open(certfile, "rb") as myfile:
            cert = myfile.read()
        with open(keyfile, "rb") as myfile:
            key = myfile.read()
    except IOError as e:
        utils.err(e)
    errors = pcs.common.ssl.check_cert_key(certfile, keyfile)
    if errors:
        for err in errors:
            utils.err(err, False)
        sys.exit(1)

    if not modifiers.get("--force") and (
        os.path.exists(settings.pcsd_cert_location)
        or os.path.exists(settings.pcsd_key_location)
    ):
        utils.err(
            "certificate and/or key already exists, use --force to overwrite"
        )

    try:
        try:
            os.chmod(settings.pcsd_cert_location, 0o600)
        except OSError:  # If the file doesn't exist, we don't care
            pass

        try:
            os.chmod(settings.pcsd_key_location, 0o600)
        except OSError:  # If the file doesn't exist, we don't care
            pass

        with os.fdopen(
            os.open(
                settings.pcsd_cert_location,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            ),
            "wb",
        ) as myfile:
            myfile.write(cert)

        with os.fdopen(
            os.open(
                settings.pcsd_key_location,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                0o600,
            ),
            "wb",
        ) as myfile:
            myfile.write(key)

    except IOError as e:
        utils.err(e)

    print_to_stderr(
        "Certificate and key updated, you may need to restart pcsd for new "
        "settings to take effect"
    )


def pcsd_sync_certs(lib, argv, modifiers):
    """
    Options:
      * --skip-offline - skip offline nodes
    """
    modifiers.ensure_only_supported("--skip-offline")
    if argv:
        raise CmdLineInputError()
    lib.pcsd.synchronize_ssl_certificate(
        skip_offline=modifiers.get("--skip-offline")
    )


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
        except EnvironmentError as e:
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
    except EnvironmentError as e:
        utils.err(
            "Unable to edit data in {file}: {err}".format(file=filepath, err=e)
        )


def accept_token_cmd(lib, argv, modifiers):
    del lib
    modifiers.ensure_only_supported()
    if len(argv) != 1:
        raise CmdLineInputError("1 argument required")
    utils.set_token_to_accept(utils.get_token_from_file(argv[0]))


def _check_nodes(node_list, prefix=""):
    """
    Print pcsd status on node_list, return if there is any pcsd not online

    Commandline options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    online_code = 0
    status_desc_map = {online_code: "Online", 3: "Unable to authenticate"}
    status_list = []

    def report(node, returncode, output):
        del output
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
    argv: Sequence[str],
    modifiers: InputModifiers,
    dont_exit: bool = False,
) -> None:
    """
    Options:
      * --request-timeout - HTTP timeout for node authorization check
    """
    # If no arguments get current cluster node status, otherwise get listed
    # nodes status
    del lib
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
            process_library_reports(report_list)
        bad_nodes = _check_nodes(nodes, "  ")
    else:
        bad_nodes = _check_nodes(argv, "  ")
    if bad_nodes and not dont_exit:
        sys.exit(2)
