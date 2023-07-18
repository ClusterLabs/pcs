# pylint: disable=too-many-lines
import datetime
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import xml.dom.minidom
from typing import (
    Any,
    Callable,
    Iterable,
    List,
    Mapping,
    Optional,
    cast,
)

import pcs.lib.pacemaker.live as lib_pacemaker
from pcs import (
    settings,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import (
    ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE,
    CmdLineInputError,
    raise_command_replaced,
)
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
)
from pcs.cli.common.tools import print_to_stderr
from pcs.cli.file import metadata as file_metadata
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.messages import report_item_msg_from_dto
from pcs.cli.reports.output import warn
from pcs.common import file as pcs_file
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncNodeDto,
)
from pcs.common.interface import dto
from pcs.common.node_communicator import (
    HostNotFound,
    Request,
    RequestData,
)
from pcs.common.str_tools import (
    format_list,
    indent,
)
from pcs.common.tools import format_os_error
from pcs.lib import sbd as lib_sbd
from pcs.lib.commands.remote_node import _destroy_pcmk_remote_env
from pcs.lib.communication.nodes import CheckAuth
from pcs.lib.communication.tools import RunRemotelyBase
from pcs.lib.communication.tools import run as run_com_cmd
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.corosync import qdevice_net
from pcs.lib.corosync.live import (
    QuorumStatusException,
    QuorumStatusFacade,
)
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.utils import parallel_for_nodes

# pylint: disable=too-many-branches, too-many-statements


def _corosync_conf_local_cmd_call(
    corosync_conf_path: parse_args.ModifierValueType,
    lib_cmd: Callable[[bytes], bytes],
) -> None:
    """
    Call a library command that requires modifications of a corosync.conf file
    supplied as an argument

    The lib command needs to take the corosync.conf file content as its first
    argument

        lib_cmd -- the lib command to be called
    """
    corosync_conf_file = pcs_file.RawFile(
        file_metadata.for_file_type(
            file_type_codes.COROSYNC_CONF, corosync_conf_path
        )
    )

    try:
        corosync_conf_file.write(
            lib_cmd(
                corosync_conf_file.read(),
            ),
            can_overwrite=True,
        )
    except pcs_file.RawFileError as e:
        raise CmdLineInputError(
            reports.messages.FileIoError(
                e.metadata.file_type_code,
                e.action,
                e.reason,
                file_path=e.metadata.path,
            ).message
        ) from e


def cluster_cib_upgrade_cmd(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    utils.cluster_upgrade()


def cluster_disable_cmd(lib, argv, modifiers):
    """
    Options:
      * --all - disable all cluster nodes
      * --request-timeout - timeout for HTTP requests - effective only when at
        least one node has been specified or --all has been used
    """
    del lib
    modifiers.ensure_only_supported("--all", "--request-timeout")
    if modifiers.get("--all"):
        if argv:
            utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
        disable_cluster_all()
    else:
        disable_cluster(argv)


def cluster_enable_cmd(lib, argv, modifiers):
    """
    Options:
      * --all - enable all cluster nodes
      * --request-timeout - timeout for HTTP requests - effective only when at
        least one node has been specified or --all has been used
    """
    del lib
    modifiers.ensure_only_supported("--all", "--request-timeout")
    if modifiers.get("--all"):
        if argv:
            utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
        enable_cluster_all()
    else:
        enable_cluster(argv)


def cluster_stop_cmd(lib, argv, modifiers):
    """
    Options:
      * --force - no error when possible quorum loss
      * --request-timeout - timeout for HTTP requests - effective only when at
        least one node has been specified
      * --pacemaker - stop pacemaker, only effective when no node has been
        specified
      * --corosync - stop corosync, only effective when no node has been
        specified
      * --all - stop all cluster nodes
    """
    del lib
    modifiers.ensure_only_supported(
        "--wait",
        "--request-timeout",
        "--pacemaker",
        "--corosync",
        "--all",
        "--force",
    )
    if modifiers.get("--all"):
        if argv:
            utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
        stop_cluster_all()
    else:
        stop_cluster(argv)


def cluster_start_cmd(lib, argv, modifiers):
    """
    Options:
      * --wait
      * --request-timeout - timeout for HTTP requests, have effect only if at
        least one node have been specified
      * --all - start all cluster nodes
    """
    del lib
    modifiers.ensure_only_supported(
        "--wait", "--request-timeout", "--all", "--corosync_conf"
    )
    if modifiers.get("--all"):
        if argv:
            utils.err(ERR_NODE_LIST_AND_ALL_MUTUALLY_EXCLUSIVE)
        start_cluster_all()
    else:
        start_cluster(argv)


def authkey_corosync(lib, argv, modifiers):
    """
    Options:
      * --force - skip check for authkey length
      * --request-timeout - timeout for HTTP requests
      * --skip-offline - skip unreachable nodes
    """
    modifiers.ensure_only_supported(
        "--force", "--skip-offline", "--request-timeout"
    )
    if len(argv) > 1:
        raise CmdLineInputError()
    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)
    corosync_authkey = None
    if argv:
        try:
            with open(argv[0], "rb") as file:
                corosync_authkey = file.read()
        except OSError as e:
            utils.err(
                "Unable to read file '{0}': {1}".format(
                    argv[0], format_os_error(e)
                )
            )
    lib.cluster.corosync_authkey_change(
        corosync_authkey=corosync_authkey,
        force_flags=force_flags,
    )


def sync_nodes(lib, argv, modifiers):
    """
    Options:
      * --request-timeout - timeout for HTTP requests
    """
    del lib
    modifiers.ensure_only_supported("--request-timeout")
    if argv:
        raise CmdLineInputError()

    config = utils.getCorosyncConf()
    nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade(conf_text=config)
    )
    if not nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if report_list:
        process_library_reports(report_list)

    for node in nodes:
        utils.setCorosyncConfig(node, config)

    warn(
        "Corosync configuration has been synchronized, please reload corosync "
        "daemon using 'pcs cluster reload corosync' command."
    )


def start_cluster(argv):
    """
    Commandline options:
      * --wait
      * --request-timeout - timeout for HTTP requests, have effect only if at
        least one node have been specified
    """
    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True

    if argv:
        nodes = set(argv)  # unique
        start_cluster_nodes(nodes)
        if wait:
            wait_for_nodes_started(nodes, wait_timeout)
        return

    if not utils.hasCorosyncConf():
        utils.err("cluster is not currently configured on this node")

    print_to_stderr("Starting Cluster...")
    service_list = ["corosync"]
    if utils.need_to_handle_qdevice_service():
        service_list.append("corosync-qdevice")
    service_list.append("pacemaker")
    for service in service_list:
        utils.start_service(service)
    if wait:
        wait_for_nodes_started([], wait_timeout)


def start_cluster_all():
    """
    Commandline options:
      * --wait
      * --request-timeout - timeout for HTTP requests
    """
    wait = False
    wait_timeout = None
    if "--wait" in utils.pcs_options:
        wait_timeout = utils.validate_wait_get_timeout(False)
        wait = True

    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    if not all_nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if report_list:
        process_library_reports(report_list)

    start_cluster_nodes(all_nodes)
    if wait:
        wait_for_nodes_started(all_nodes, wait_timeout)


def start_cluster_nodes(nodes):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    # Large clusters take longer time to start up. So we make the timeout longer
    # for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option (see utils.sendHTTPRequest).
    timeout = int(
        settings.default_request_timeout * math.ceil(len(nodes) / 8.0)
    )
    utils.read_known_hosts_file()  # cache known hosts
    node_errors = parallel_for_nodes(
        utils.startCluster, nodes, quiet=True, timeout=timeout
    )
    if node_errors:
        utils.err(
            "unable to start all nodes\n" + "\n".join(node_errors.values())
        )


def is_node_fully_started(node_status):
    """
    Commandline options: no options
    """
    return (
        "online" in node_status
        and "pending" in node_status
        and node_status["online"]
        and not node_status["pending"]
    )


def wait_for_local_node_started(stop_at, interval):
    """
    Commandline options: no options
    """
    try:
        while True:
            time.sleep(interval)
            node_status = lib_pacemaker.get_local_node_status(
                utils.cmd_runner()
            )
            if is_node_fully_started(node_status):
                return 0, "Started"
            if datetime.datetime.now() > stop_at:
                return 1, "Waiting timeout"
    except LibraryError as e:
        return (
            1,
            "Unable to get node status: {0}".format(
                # pylint: disable=no-member
                "\n".join(
                    report_item_msg_from_dto(
                        cast(reports.ReportItemDto, item).message
                    ).message
                    for item in e.args
                )
            ),
        )


def wait_for_remote_node_started(node, stop_at, interval):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    while True:
        time.sleep(interval)
        code, output = utils.getPacemakerNodeStatus(node)
        # HTTP error, permission denied or unable to auth
        # there is no point in trying again as it won't get magically fixed
        if code in [1, 3, 4]:
            return 1, output
        if code == 0:
            try:
                node_status = json.loads(output)
                if is_node_fully_started(node_status):
                    return 0, "Started"
            except (ValueError, KeyError):
                # this won't get fixed either
                return 1, "Unable to get node status"
        if datetime.datetime.now() > stop_at:
            return 1, "Waiting timeout"


def wait_for_nodes_started(node_list, timeout=None):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP request, effective only if
        node_list is not empty list
    """
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = datetime.datetime.now() + datetime.timedelta(seconds=timeout)
    print_to_stderr("Waiting for node(s) to start...")
    if not node_list:
        code, output = wait_for_local_node_started(stop_at, interval)
        if code != 0:
            utils.err(output)
        else:
            print_to_stderr(output)
    else:
        utils.read_known_hosts_file()  # cache known hosts
        node_errors = parallel_for_nodes(
            wait_for_remote_node_started, node_list, stop_at, interval
        )
        if node_errors:
            utils.err("unable to verify all nodes have started")


def stop_cluster_all():
    """
    Commandline options:
      * --force - no error when possible quorum loss
      * --request-timeout - timeout for HTTP requests
    """
    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    if not all_nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if report_list:
        process_library_reports(report_list)

    stop_cluster_nodes(all_nodes)


def stop_cluster_nodes(nodes):
    """
    Commandline options:
      * --force - no error when possible quorum loss
      * --request-timeout - timeout for HTTP requests
    """
    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    unknown_nodes = set(nodes) - set(all_nodes)
    if unknown_nodes:
        if report_list:
            process_library_reports(report_list)
        utils.err(
            "nodes '%s' do not appear to exist in configuration"
            % "', '".join(sorted(unknown_nodes))
        )

    utils.read_known_hosts_file()  # cache known hosts
    stopping_all = set(nodes) >= set(all_nodes)
    if "--force" not in utils.pcs_options and not stopping_all:
        error_list = []
        for node in nodes:
            retval, data = utils.get_remote_quorumtool_output(node)
            if retval != 0:
                error_list.append(node + ": " + data)
                continue
            try:
                quorum_status_facade = QuorumStatusFacade.from_string(data)
                if not quorum_status_facade.is_quorate:
                    # Get quorum status from a quorate node, non-quorate nodes
                    # may provide inaccurate info. If no node is quorate, there
                    # is no quorum to be lost and therefore no error to be
                    # reported.
                    continue
                if quorum_status_facade.stopping_nodes_cause_quorum_loss(nodes):
                    utils.err(
                        "Stopping the node(s) will cause a loss of the quorum"
                        + ", use --force to override"
                    )
                else:
                    # We have the info, no need to print errors
                    error_list = []
                    break
            except QuorumStatusException:
                if not utils.is_node_offline_by_quorumtool_output(data):
                    error_list.append(node + ": Unable to get quorum status")
                # else the node seems to be stopped already
        if error_list:
            utils.err(
                "Unable to determine whether stopping the nodes will cause "
                + "a loss of the quorum, use --force to override\n"
                + "\n".join(error_list)
            )

    was_error = False
    node_errors = parallel_for_nodes(
        utils.repeat_if_timeout(utils.stopPacemaker), nodes, quiet=True
    )
    accessible_nodes = [node for node in nodes if node not in node_errors]
    if node_errors:
        utils.err(
            "unable to stop all nodes\n" + "\n".join(node_errors.values()),
            exit_after_error=not accessible_nodes,
        )
        was_error = True

    for node in node_errors:
        print_to_stderr(
            "{0}: Not stopping cluster - node is unreachable".format(node)
        )

    node_errors = parallel_for_nodes(
        utils.stopCorosync, accessible_nodes, quiet=True
    )
    if node_errors:
        utils.err(
            "unable to stop all nodes\n" + "\n".join(node_errors.values())
        )
    if was_error:
        utils.err("unable to stop all nodes")


def enable_cluster(argv):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests, effective only if at
        least one node has been specified
    """
    if argv:
        enable_cluster_nodes(argv)
        return

    try:
        utils.enableServices()
    except LibraryError as e:
        process_library_reports(e.args)


def disable_cluster(argv):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests, effective only if at
        least one node has been specified
    """
    if argv:
        disable_cluster_nodes(argv)
        return

    try:
        utils.disableServices()
    except LibraryError as e:
        process_library_reports(e.args)


def enable_cluster_all():
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    if not all_nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if report_list:
        process_library_reports(report_list)

    enable_cluster_nodes(all_nodes)


def disable_cluster_all():
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    all_nodes, report_list = get_existing_nodes_names(
        utils.get_corosync_conf_facade()
    )
    if not all_nodes:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if report_list:
        process_library_reports(report_list)

    disable_cluster_nodes(all_nodes)


def enable_cluster_nodes(nodes):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    error_list = utils.map_for_error_list(utils.enableCluster, nodes)
    if error_list:
        utils.err("unable to enable all nodes\n" + "\n".join(error_list))


def disable_cluster_nodes(nodes):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    error_list = utils.map_for_error_list(utils.disableCluster, nodes)
    if error_list:
        utils.err("unable to disable all nodes\n" + "\n".join(error_list))


def destroy_cluster(argv):
    """
    Commandline options:
      * --request-timeout - timeout for HTTP requests
    """
    if argv:
        utils.read_known_hosts_file()  # cache known hosts
        # stop pacemaker and resources while cluster is still quorate
        nodes = argv
        node_errors = parallel_for_nodes(
            utils.repeat_if_timeout(utils.stopPacemaker), nodes, quiet=True
        )
        # proceed with destroy regardless of errors
        # destroy will stop any remaining cluster daemons
        node_errors = parallel_for_nodes(
            utils.destroyCluster, nodes, quiet=True
        )
        if node_errors:
            utils.err(
                "unable to destroy cluster\n" + "\n".join(node_errors.values())
            )


def stop_cluster(argv):
    """
    Commandline options:
      * --force - no error when possible quorum loss
      * --request-timeout - timeout for HTTP requests - effective only when at
        least one node has been specified
      * --pacemaker - stop pacemaker, only effective when no node has been
        specified
    """
    if argv:
        stop_cluster_nodes(argv)
        return

    if "--force" not in utils.pcs_options:
        # corosync 3.0.1 and older:
        # - retval is 0 on success if a node is not in a partition with quorum
        # - retval is 1 on error OR on success if a node has quorum
        # corosync 3.0.2 and newer:
        # - retval is 0 on success if a node has quorum
        # - retval is 1 on error
        # - retval is 2 on success if a node is not in a partition with quorum
        output, dummy_retval = utils.run(["corosync-quorumtool", "-p", "-s"])
        try:
            if QuorumStatusFacade.from_string(
                output
            ).stopping_local_node_cause_quorum_loss():
                utils.err(
                    "Stopping the node will cause a loss of the quorum"
                    + ", use --force to override"
                )
        except QuorumStatusException:
            if not utils.is_node_offline_by_quorumtool_output(output):
                utils.err(
                    "Unable to determine whether stopping the node will cause "
                    + "a loss of the quorum, use --force to override"
                )
            # else the node seems to be stopped already, proceed to be sure

    stop_all = (
        "--pacemaker" not in utils.pcs_options
        and "--corosync" not in utils.pcs_options
    )
    if stop_all or "--pacemaker" in utils.pcs_options:
        stop_cluster_pacemaker()
    if stop_all or "--corosync" in utils.pcs_options:
        stop_cluster_corosync()


def stop_cluster_pacemaker():
    """
    Commandline options: no options
    """
    print_to_stderr("Stopping Cluster (pacemaker)...")
    utils.stop_service("pacemaker")


def stop_cluster_corosync():
    """
    Commandline options: no options
    """
    print_to_stderr("Stopping Cluster (corosync)...")
    service_list = []
    if utils.need_to_handle_qdevice_service():
        service_list.append("corosync-qdevice")
    service_list.append("corosync")
    for service in service_list:
        utils.stop_service(service)


def kill_cluster(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    if argv:
        raise CmdLineInputError()
    modifiers.ensure_only_supported()
    dummy_output, dummy_retval = kill_local_cluster_services()


#    if dummy_retval != 0:
#        print "Error: unable to execute killall -9"
#        print output
#        sys.exit(1)


def kill_local_cluster_services():
    """
    Commandline options: no options
    """
    all_cluster_daemons = [
        # Daemons taken from cluster-clean script in pacemaker
        "pacemaker-attrd",
        "pacemaker-based",
        "pacemaker-controld",
        "pacemaker-execd",
        "pacemaker-fenced",
        "pacemaker-remoted",
        "pacemaker-schedulerd",
        "pacemakerd",
        "dlm_controld",
        "gfs_controld",
        # Corosync daemons
        "corosync-qdevice",
        "corosync",
    ]
    return utils.run([settings.killall_executable, "-9"] + all_cluster_daemons)


def cluster_push(lib, argv, modifiers):
    """
    Options:
      * --wait
      * --config - push only configuration section of CIB
      * -f - CIB file
    """
    # pylint: disable=too-many-locals,
    del lib
    modifiers.ensure_only_supported("--wait", "--config", "-f")
    if len(argv) > 2:
        raise CmdLineInputError()

    filename = None
    scope = None
    timeout = None
    diff_against = None

    if modifiers.get("--wait"):
        timeout = utils.validate_wait_get_timeout()
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope":
                if modifiers.get("--config"):
                    utils.err("Cannot use both scope and --config")
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            elif arg_name == "diff-against":
                diff_against = arg_value
            else:
                raise CmdLineInputError()
    if modifiers.get("--config"):
        scope = "configuration"
    if diff_against and scope:
        utils.err("Cannot use both scope and diff-against")
    if not filename:
        raise CmdLineInputError()

    try:
        new_cib_dom = xml.dom.minidom.parse(filename)
        if scope and not new_cib_dom.getElementsByTagName(scope):
            utils.err(
                "unable to push cib, scope '%s' not present in new cib" % scope
            )
    except (EnvironmentError, xml.parsers.expat.ExpatError) as e:
        utils.err("unable to parse new cib: %s" % e)

    if diff_against:
        runner = utils.cmd_runner()
        command = [
            settings.crm_diff,
            "--original",
            diff_against,
            "--new",
            filename,
            "--no-version",
        ]
        patch, stderr, retval = runner.run(command)
        #  0 (CRM_EX_OK) - success with no difference
        #  1 (CRM_EX_ERROR) - success with difference
        # 64 (CRM_EX_USAGE) - usage error
        # 65 (CRM_EX_DATAERR) - XML fragments not parseable
        if retval > 1:
            utils.err("unable to diff the CIBs:\n" + stderr)
        if retval == 0:
            print_to_stderr(
                "The new CIB is the same as the original CIB, nothing to push."
            )
            sys.exit(0)

        command = [
            settings.cibadmin,
            "--patch",
            "--xml-pipe",
        ]
        output, stderr, retval = runner.run(command, patch)
        if retval != 0:
            utils.err("unable to push cib\n" + stderr + output)

    else:
        command = ["cibadmin", "--replace", "--xml-file", filename]
        if scope:
            command.append("--scope=%s" % scope)
        output, retval = utils.run(command)
        # 103 (CRM_EX_OLD) - update older than existing config
        if retval == 103:
            utils.err(
                "Unable to push to the CIB because pushed configuration "
                "is older than existing one. If you are sure you want to "
                "push this configuration, try to use --config to replace only "
                "configuration part instead of whole CIB. Otherwise get current"
                " configuration by running command 'pcs cluster cib' and update"
                " that."
            )
        elif retval != 0:
            utils.err("unable to push cib\n" + output)

    print_to_stderr("CIB updated")

    if not modifiers.is_specified("--wait"):
        return
    cmd = ["crm_resource", "--wait"]
    if timeout:
        cmd.extend(["--timeout", str(timeout)])
    output, retval = utils.run(cmd)
    if retval != 0:
        msg = []
        if retval == settings.pacemaker_wait_timeout_status:
            msg.append("waiting timeout")
        if output:
            msg.append("\n" + output)
        utils.err("\n".join(msg).strip())


def cluster_edit(lib, argv, modifiers):
    """
    Options:
      * --config - edit configuration section of CIB
      * -f - CIB file
      * --wait
    """
    modifiers.ensure_only_supported("--config", "--wait", "-f")
    if "EDITOR" in os.environ:
        if len(argv) > 1:
            raise CmdLineInputError()

        scope = None
        scope_arg = ""
        for arg in argv:
            if "=" not in arg:
                raise CmdLineInputError()
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope" and not modifiers.get("--config"):
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope_arg = arg
                    scope = arg_value
            else:
                raise CmdLineInputError()
        if modifiers.get("--config"):
            scope = "configuration"
            # Leave scope_arg empty as cluster_push will pick up a --config
            # option from utils.pcs_options
            scope_arg = ""

        editor = os.environ["EDITOR"]
        cib = utils.get_cib(scope)
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".pcs") as tempcib:
            tempcib.write(cib)
            tempcib.flush()
            try:
                subprocess.call([editor, tempcib.name])
            except OSError:
                utils.err("unable to open file with $EDITOR: " + editor)

            tempcib.seek(0)
            newcib = "".join(tempcib.readlines())
            if newcib == cib:
                print_to_stderr("CIB not updated, no changes detected")
            else:
                cluster_push(
                    lib,
                    [arg for arg in [tempcib.name, scope_arg] if arg],
                    modifiers.get_subset("--wait", "--config", "-f"),
                )

    else:
        utils.err("$EDITOR environment variable is not set")


def get_cib(lib, argv, modifiers):
    """
    Options:
      * --config show configuration section of CIB
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("--config", "-f")
    if len(argv) > 2:
        raise CmdLineInputError()

    filename = None
    scope = None
    for arg in argv:
        if "=" not in arg:
            filename = arg
        else:
            arg_name, arg_value = arg.split("=", 1)
            if arg_name == "scope" and not modifiers.get("--config"):
                if not utils.is_valid_cib_scope(arg_value):
                    utils.err("invalid CIB scope '%s'" % arg_value)
                else:
                    scope = arg_value
            else:
                raise CmdLineInputError()
    if modifiers.get("--config"):
        scope = "configuration"

    if not filename:
        print(utils.get_cib(scope).rstrip())
    else:
        output = utils.get_cib(scope)
        if not output:
            utils.err("No data in the CIB")
        try:
            with open(filename, "w") as cib_file:
                cib_file.write(output)
        except EnvironmentError as e:
            utils.err(
                "Unable to write to file '%s', %s" % (filename, e.strerror)
            )


class RemoteAddNodes(RunRemotelyBase):
    def __init__(self, report_processor, target, data):
        super().__init__(report_processor)
        self._target = target
        self._data = data
        self._success = False

    def get_initial_request_list(self):
        return [
            Request(
                self._target,
                RequestData(
                    "remote/cluster_add_nodes",
                    [("data_json", json.dumps(self._data))],
                ),
            )
        ]

    def _process_response(self, response):
        node_label = response.request.target.label
        report_item = self._get_response_report(response)
        if report_item is not None:
            self._report(report_item)
            return

        try:
            output = json.loads(response.data)
            for report_dict in output["report_list"]:
                self._report(
                    reports.ReportItem(
                        severity=reports.ReportItemSeverity(
                            report_dict["severity"],
                            report_dict["forceable"],
                        ),
                        message=reports.messages.LegacyCommonMessage(
                            report_dict["code"],
                            report_dict["info"],
                            report_dict["report_text"],
                        ),
                    )
                )
            if output["status"] == "success":
                self._success = True
            elif output["status"] != "error":
                print_to_stderr("Error: {}".format(output["status_msg"]))

        except (KeyError, json.JSONDecodeError):
            self._report(
                reports.ReportItem.warning(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )

    def on_complete(self):
        return self._success


def node_add_outside_cluster(lib, argv, modifiers):
    """
    Options:
      * --wait - wait until new node will start up, effective only when --start
        is specified
      * --start - start new node
      * --enable - enable new node
      * --force - treat validation issues and not resolvable addresses as
        warnings instead of errors
      * --skip-offline - skip unreachable nodes
      * --no-watchdog-validation - do not validatate watchdogs
      * --request-timeout - HTTP request timeout
    """
    del lib
    modifiers.ensure_only_supported(
        "--wait",
        "--start",
        "--enable",
        "--force",
        "--skip-offline",
        "--no-watchdog-validation",
        "--request-timeout",
    )
    if len(argv) < 2:
        raise CmdLineInputError(
            "Usage: pcs cluster node add-outside <cluster node> <node name> "
            "[addr=<node address>]... [watchdog=<watchdog path>] "
            "[device=<SBD device path>]... [--start [--wait[=<n>]]] [--enable] "
            "[--no-watchdog-validation]"
        )

    cluster_node, *argv = argv
    node_dict = _parse_add_node(argv)

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)
    cmd_data = dict(
        nodes=[node_dict],
        wait=modifiers.get("--wait"),
        start=modifiers.get("--start"),
        enable=modifiers.get("--enable"),
        no_watchdog_validation=modifiers.get("--no-watchdog-validation"),
        force_flags=force_flags,
    )

    lib_env = utils.get_lib_env()
    report_processor = lib_env.report_processor
    target_factory = lib_env.get_node_target_factory()
    report_list, target_list = target_factory.get_target_list_with_reports(
        [cluster_node],
        skip_non_existing=False,
        allow_skip=False,
    )
    report_processor.report_list(report_list)
    if report_processor.has_errors:
        raise LibraryError()

    com_cmd = RemoteAddNodes(report_processor, target_list[0], cmd_data)
    was_successful = run_com_cmd(lib_env.get_node_communicator(), com_cmd)

    if not was_successful:
        raise LibraryError()


def node_remove(lib, argv, modifiers):
    """
    Options:
      * --force - continue even though the action may cause qourum loss
      * --skip-offline - skip unreachable nodes
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported(
        "--force",
        "--skip-offline",
        "--request-timeout",
    )
    if not argv:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    lib.cluster.remove_nodes(argv, force_flags=force_flags)


def cluster_uidgid(lib, argv, modifiers, silent_list=False):
    """
    Options: no options
    """
    # pylint: disable=too-many-locals,
    del lib
    modifiers.ensure_only_supported()
    if not argv:
        found = False
        uid_gid_files = os.listdir(settings.corosync_uidgid_dir)
        for ug_file in uid_gid_files:
            uid_gid_dict = utils.read_uid_gid_file(ug_file)
            if "uid" in uid_gid_dict or "gid" in uid_gid_dict:
                line = "UID/GID: uid="
                if "uid" in uid_gid_dict:
                    line += uid_gid_dict["uid"]
                line += " gid="
                if "gid" in uid_gid_dict:
                    line += uid_gid_dict["gid"]

                print(line)
                found = True
        if not found and not silent_list:
            print_to_stderr("No uidgids configured")
        return

    command = argv.pop(0)
    uid = ""
    gid = ""

    if command in {"add", "delete", "remove"} and argv:
        for arg in argv:
            if arg.find("=") == -1:
                utils.err(
                    "uidgid options must be of the form uid=<uid> gid=<gid>"
                )

            (key, value) = arg.split("=", 1)
            if key not in {"uid", "gid"}:
                utils.err(
                    "%s is not a valid key, you must use uid or gid" % key
                )

            if key == "uid":
                uid = value
            if key == "gid":
                gid = value
        if uid == "" and gid == "":
            utils.err("you must set either uid or gid")

        if command == "add":
            utils.write_uid_gid_file(uid, gid)
        elif command in {"delete", "remove"}:
            file_removed = utils.remove_uid_gid_file(uid, gid)
            if not file_removed:
                utils.err(
                    "no uidgid files with uid=%s and gid=%s found" % (uid, gid)
                )
    elif command == "rm":
        # To be removed in the next significant version
        raise_command_replaced(
            [
                "pcs cluster uidgid delete",
                "pcs cluster uidgid remove",
            ],
            pcs_version="0.11",
        )
    else:
        raise CmdLineInputError()


def cluster_get_corosync_conf(lib, argv, modifiers):
    """
    Options:
      * --request-timeout - timeout for HTTP requests, effetive only when at
        least one node has been specified
    """
    del lib
    modifiers.ensure_only_supported("--request-timeout")
    if len(argv) > 1:
        raise CmdLineInputError()

    if not argv:
        print(utils.getCorosyncConf().rstrip())
        return

    node = argv[0]
    retval, output = utils.getCorosyncConfig(node)
    if retval != 0:
        utils.err(output)
    else:
        print(output.rstrip())


def cluster_reload(lib, argv, modifiers):
    """
    Options: no options
    """
    del lib
    modifiers.ensure_only_supported()
    if len(argv) != 1 or argv[0] != "corosync":
        raise CmdLineInputError()

    output, retval = utils.reloadCorosync()
    if retval != 0 or "invalid option" in output:
        utils.err(output.rstrip())
    print_to_stderr("Corosync reloaded")


# Completely tear down the cluster & remove config files
# Code taken from cluster-clean script in pacemaker
def cluster_destroy(lib, argv, modifiers):
    """
    Options:
      * --all - destroy cluster on all cluster nodes => destroy whole cluster
      * --request-timeout - timeout of HTTP requests, effective only with --all
    """
    # pylint: disable=bare-except
    del lib
    modifiers.ensure_only_supported("--all", "--request-timeout", "--force")
    if argv:
        raise CmdLineInputError()
    if utils.is_run_interactive():
        warn(
            "It is recommended to run 'pcs cluster stop' before "
            "destroying the cluster."
        )
        if not utils.get_continue_confirmation_or_force(
            "This would kill all cluster processes and then PERMANENTLY remove "
            "cluster state and configuration",
            modifiers.get("--force"),
        ):
            return
    if modifiers.get("--all"):
        # load data
        cib = None
        lib_env = utils.get_lib_env()
        try:
            cib = lib_env.get_cib()
        except LibraryError:
            warn(
                "Unable to load CIB to get guest and remote nodes from it, "
                "those nodes will not be deconfigured."
            )
        corosync_nodes, report_list = get_existing_nodes_names(
            utils.get_corosync_conf_facade()
        )
        if not corosync_nodes:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.CorosyncConfigNoNodesDefined()
                )
            )
        if report_list:
            process_library_reports(report_list)

        # destroy remote and guest nodes
        if cib is not None:
            try:
                all_remote_nodes, report_list = get_existing_nodes_names(
                    cib=cib
                )
                if report_list:
                    process_library_reports(report_list)
                if all_remote_nodes:
                    _destroy_pcmk_remote_env(
                        lib_env,
                        all_remote_nodes,
                        skip_offline_nodes=True,
                        allow_fails=True,
                    )
            except LibraryError as e:
                process_library_reports(e.args)

        # destroy full-stack nodes
        destroy_cluster(corosync_nodes)
    else:
        print_to_stderr("Shutting down pacemaker/corosync services...")
        for service in ["pacemaker", "corosync-qdevice", "corosync"]:
            try:
                utils.stop_service(service)
            except LibraryError:
                # It is safe to ignore error since we want it not to be running
                # anyways.
                pass
        print_to_stderr("Killing any remaining services...")
        kill_local_cluster_services()
        try:
            utils.disableServices()
        except:
            # previously errors were suppressed in here, let's keep it that way
            # for now
            pass
        try:
            service_manager = utils.get_service_manager()
            service_manager.disable(
                lib_sbd.get_sbd_service_name(service_manager)
            )
        except:
            # it's not a big deal if sbd disable fails
            pass

        print_to_stderr("Removing all cluster configuration files...")
        dummy_output, dummy_retval = utils.run(
            [
                settings.rm_executable,
                "-f",
                settings.corosync_conf_file,
                settings.corosync_authkey_file,
                settings.pacemaker_authkey_file,
                settings.pcsd_dr_config_location,
            ]
        )
        state_files = [
            "cib-*",
            "cib.*",
            "cib.xml*",
            "core.*",
            "cts.*",
            "hostcache",
            "pe*.bz2",
        ]
        for name in state_files:
            dummy_output, dummy_retval = utils.run(
                [
                    settings.find_executable,
                    settings.pacemaker_local_state_dir,
                    "-name",
                    name,
                    "-exec",
                    settings.rm_executable,
                    "-f",
                    "{}",
                    ";",
                ]
            )
        try:
            qdevice_net.client_destroy()
        except:
            # errors from deleting other files are suppressed as well
            # we do not want to fail if qdevice was not set up
            pass


def cluster_verify(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --full - more verbose output
    """
    modifiers.ensure_only_supported("-f", "--full")
    if argv:
        raise CmdLineInputError()

    lib.cluster.verify(verbose=modifiers.get("--full"))


def cluster_report(lib, argv, modifiers):
    """
    Options:
      * --force - overwrite existing file
      * --from - timestamp
      * --to - timestamp
    """
    del lib
    modifiers.ensure_only_supported("--force", "--from", "--to")
    if len(argv) != 1:
        raise CmdLineInputError()

    outfile = argv[0]
    dest_outfile = outfile + ".tar.bz2"
    if os.path.exists(dest_outfile):
        if not modifiers.get("--force"):
            utils.err(
                dest_outfile + " already exists, use --force to overwrite"
            )
        else:
            try:
                os.remove(dest_outfile)
            except OSError as e:
                utils.err(
                    "Unable to remove " + dest_outfile + ": " + e.strerror
                )
    crm_report_opts = []

    crm_report_opts.append("-f")
    if modifiers.is_specified("--from"):
        crm_report_opts.append(modifiers.get("--from"))
        if modifiers.is_specified("--to"):
            crm_report_opts.append("-t")
            crm_report_opts.append(modifiers.get("--to"))
    else:
        yesterday = datetime.datetime.now() - datetime.timedelta(1)
        crm_report_opts.append(yesterday.strftime("%Y-%m-%d %H:%M"))

    crm_report_opts.append(outfile)
    output, retval = utils.run([settings.crm_report] + crm_report_opts)
    if retval != 0 and (
        "ERROR: Cannot determine nodes; specify --nodes or --single-node"
        in output
    ):
        utils.err("cluster is not configured on this node")
    newoutput = ""
    for line in output.split("\n"):
        if (
            line.startswith("cat:")
            or line.startswith("grep")
            or line.startswith("tail")
        ):
            continue
        if "We will attempt to remove" in line:
            continue
        if "-p option" in line:
            continue
        if "However, doing" in line:
            continue
        if "to diagnose" in line:
            continue
        if "--dest" in line:
            line = line.replace("--dest", "<dest>")
        newoutput = newoutput + line + "\n"
    if retval != 0:
        utils.err(newoutput)
    print_to_stderr(newoutput)


def send_local_configs(
    node_name_list, clear_local_cluster_permissions=False, force=False
):
    """
    Commandline options:
      * --request-timeout - timeout of HTTP requests
    """
    # pylint: disable=bare-except
    pcsd_data = {
        "nodes": node_name_list,
        "force": force,
        "clear_local_cluster_permissions": clear_local_cluster_permissions,
    }
    err_msgs = []
    output, retval = utils.run_pcsdcli("send_local_configs", pcsd_data)
    if retval == 0 and output["status"] == "ok" and output["data"]:
        try:
            for node_name in node_name_list:
                node_response = output["data"][node_name]
                if node_response["status"] == "notauthorized":
                    err_msgs.append(
                        (
                            "Unable to authenticate to {0}, try running 'pcs "
                            "host auth {0}'"
                        ).format(node_name)
                    )
                if node_response["status"] not in ["ok", "not_supported"]:
                    err_msgs.append(
                        "Unable to set pcsd configs on {0}".format(node_name)
                    )
        except:
            err_msgs.append("Unable to communicate with pcsd")
    else:
        err_msgs.append("Unable to set pcsd configs")
    return err_msgs


def cluster_auth_cmd(lib, argv, modifiers):
    """
    Options:
      * --corosync_conf - corosync.conf file
      * --request-timeout - timeout of HTTP requests
      * -u - username
      * -p - password
    """
    # pylint: disable=too-many-locals,
    del lib
    modifiers.ensure_only_supported(
        "--corosync_conf", "--request-timeout", "-u", "-p"
    )
    if argv:
        raise CmdLineInputError()
    lib_env = utils.get_lib_env()
    target_factory = lib_env.get_node_target_factory()
    cluster_node_list = lib_env.get_corosync_conf().get_nodes()
    cluster_node_names = []
    missing_name = False
    for node in cluster_node_list:
        if node.name:
            cluster_node_names.append(node.name)
        else:
            missing_name = True
    if missing_name:
        warn(
            "Skipping nodes which do not have their name defined in "
            "corosync.conf, use the 'pcs host auth' command to authenticate "
            "them"
        )
    target_list = []
    not_authorized_node_name_list = []
    for node_name in cluster_node_names:
        try:
            target_list.append(target_factory.get_target(node_name))
        except HostNotFound:
            print_to_stderr("{}: Not authorized".format(node_name))
            not_authorized_node_name_list.append(node_name)
    com_cmd = CheckAuth(lib_env.report_processor)
    com_cmd.set_targets(target_list)
    not_authorized_node_name_list.extend(
        run_and_raise(lib_env.get_node_communicator(), com_cmd)
    )
    if not_authorized_node_name_list:
        print(
            "Nodes to authorize: {}".format(
                ", ".join(not_authorized_node_name_list)
            )
        )
        username, password = utils.get_user_and_pass()
        not_auth_node_list = []
        for node_name in not_authorized_node_name_list:
            for node in cluster_node_list:
                if node.name == node_name:
                    if node.addrs_plain():
                        not_auth_node_list.append(node)
                    else:
                        print_to_stderr(
                            f"{node.name}: No addresses defined in "
                            "corosync.conf, use the 'pcs host auth' command to "
                            "authenticate the node"
                        )
        nodes_to_auth_data = {
            node.name: dict(
                username=username,
                password=password,
                dest_list=[
                    dict(
                        addr=node.addrs_plain()[0],
                        port=settings.pcsd_default_port,
                    )
                ],
            )
            for node in not_auth_node_list
        }
        utils.auth_hosts(nodes_to_auth_data)
    else:
        print_to_stderr("Sending cluster config files to the nodes...")
        msgs = send_local_configs(cluster_node_names, force=True)
        for msg in msgs:
            warn(msg)


def _parse_node_options(
    node, options, additional_options=(), additional_repeatable_options=()
):
    """
    Commandline options: no options
    """
    # pylint: disable=invalid-name
    ADDR_OPT_KEYWORD = "addr"
    supported_options = {ADDR_OPT_KEYWORD} | set(additional_options)
    repeatable_options = {ADDR_OPT_KEYWORD} | set(additional_repeatable_options)
    parsed_options = parse_args.prepare_options(options, repeatable_options)
    unknown_options = set(parsed_options.keys()) - supported_options
    if unknown_options:
        raise CmdLineInputError(
            "Unknown options '{}' for node '{}'".format(
                "', '".join(sorted(unknown_options)), node
            )
        )
    parsed_options["name"] = node
    if ADDR_OPT_KEYWORD in parsed_options:
        parsed_options["addrs"] = parsed_options[ADDR_OPT_KEYWORD]
        del parsed_options[ADDR_OPT_KEYWORD]
    return parsed_options


TRANSPORT_KEYWORD = "transport"
TRANSPORT_DEFAULT_SECTION = "__default__"
LINK_KEYWORD = "link"


def _parse_transport(transport_args):
    """
    Commandline options: no options
    """
    if not transport_args:
        raise CmdLineInputError(
            "{} type not defined".format(TRANSPORT_KEYWORD.capitalize())
        )
    transport_type, *transport_options = transport_args

    keywords = {"compression", "crypto", LINK_KEYWORD}
    parsed_options = parse_args.group_by_keywords(
        transport_options,
        keywords,
        implicit_first_keyword=TRANSPORT_DEFAULT_SECTION,
    )
    options = {
        section: parse_args.prepare_options(
            parsed_options.get_args_flat(section)
        )
        for section in keywords | {TRANSPORT_DEFAULT_SECTION}
        if section != LINK_KEYWORD
    }
    options[LINK_KEYWORD] = [
        parse_args.prepare_options(link_options)
        for link_options in parsed_options.get_args_groups(LINK_KEYWORD)
    ]

    return transport_type, options


def cluster_setup(lib, argv, modifiers):
    """
    Options:
      * --wait - only effective when used with --start
      * --start - start cluster
      * --enable - enable cluster
      * --force - some validation issues and unresolvable addresses are treated
        as warnings
      * --no-keys-sync - do not create and distribute pcsd ssl cert and key,
        corosync and pacemaker authkeys
      * --no-cluster-uuid - do not generate a cluster UUID during setup
      * --corosync_conf - corosync.conf file path, do not talk to cluster nodes
    """
    # pylint: disable=too-many-locals
    is_local = modifiers.is_specified("--corosync_conf")

    allowed_options_common = ["--force", "--no-cluster-uuid"]
    allowed_options_live = [
        "--wait",
        "--start",
        "--enable",
        "--no-keys-sync",
    ]
    allowed_options_local = ["--corosync_conf", "--overwrite"]
    modifiers.ensure_only_supported(
        *(
            allowed_options_common
            + allowed_options_live
            + allowed_options_local
        ),
    )
    if is_local and modifiers.is_specified_any(allowed_options_live):
        raise CmdLineInputError(
            (
                "Cannot specify any of {banned} when '--corosync_conf' is "
                "specified"
            ).format(banned=format_list(allowed_options_live))
        )
    if not is_local and modifiers.is_specified("--overwrite"):
        raise CmdLineInputError(
            "Cannot specify '--overwrite' when '--corosync_conf' is not "
            "specified"
        )

    if len(argv) < 2:
        raise CmdLineInputError()
    cluster_name, *argv = argv
    keywords = [TRANSPORT_KEYWORD, "totem", "quorum"]
    parsed_args = parse_args.group_by_keywords(
        argv, keywords, implicit_first_keyword="nodes"
    )
    parsed_args.ensure_unique_keywords()
    nodes = [
        _parse_node_options(node, options)
        for node, options in parse_args.split_list_by_any_keywords(
            parsed_args.get_args_flat("nodes"), "node name"
        ).items()
    ]

    transport_type = None
    transport_options = {}

    if parsed_args.has_keyword(TRANSPORT_KEYWORD):
        transport_type, transport_options = _parse_transport(
            parsed_args.get_args_flat(TRANSPORT_KEYWORD)
        )

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)

    if not is_local:
        lib.cluster.setup(
            cluster_name,
            nodes,
            transport_type=transport_type,
            transport_options=transport_options.get(
                TRANSPORT_DEFAULT_SECTION, {}
            ),
            link_list=transport_options.get(LINK_KEYWORD, []),
            compression_options=transport_options.get("compression", {}),
            crypto_options=transport_options.get("crypto", {}),
            totem_options=parse_args.prepare_options(
                parsed_args.get_args_flat("totem")
            ),
            quorum_options=parse_args.prepare_options(
                parsed_args.get_args_flat("quorum")
            ),
            wait=modifiers.get("--wait"),
            start=modifiers.get("--start"),
            enable=modifiers.get("--enable"),
            no_keys_sync=modifiers.get("--no-keys-sync"),
            no_cluster_uuid=modifiers.is_specified("--no-cluster-uuid"),
            force_flags=force_flags,
        )
        return

    corosync_conf_data = lib.cluster.setup_local(
        cluster_name,
        nodes,
        transport_type=transport_type,
        transport_options=transport_options.get(TRANSPORT_DEFAULT_SECTION, {}),
        link_list=transport_options.get(LINK_KEYWORD, []),
        compression_options=transport_options.get("compression", {}),
        crypto_options=transport_options.get("crypto", {}),
        totem_options=parse_args.prepare_options(
            parsed_args.get_args_flat("totem")
        ),
        quorum_options=parse_args.prepare_options(
            parsed_args.get_args_flat("quorum")
        ),
        no_cluster_uuid=modifiers.is_specified("--no-cluster-uuid"),
        force_flags=force_flags,
    )

    corosync_conf_file = pcs_file.RawFile(
        file_metadata.for_file_type(
            file_type_codes.COROSYNC_CONF, modifiers.get("--corosync_conf")
        )
    )
    overwrite = modifiers.is_specified("--overwrite")
    try:
        corosync_conf_file.write(corosync_conf_data, can_overwrite=overwrite)
    except pcs_file.FileAlreadyExists as e:
        utils.err(
            reports.messages.FileAlreadyExists(
                e.metadata.file_type_code,
                e.metadata.path,
            ).message
            + ", use --overwrite to overwrite existing file(s)"
        )
    except pcs_file.RawFileError as e:
        utils.err(
            reports.messages.FileIoError(
                e.metadata.file_type_code,
                e.action,
                e.reason,
                file_path=e.metadata.path,
            ).message
        )


def config_update(
    lib: Any, argv: List[str], modifiers: parse_args.InputModifiers
) -> None:
    """
    Options:
      * --corosync_conf - corosync.conf file path, do not talk to cluster nodes
    """
    modifiers.ensure_only_supported("--corosync_conf")
    parsed_args = parse_args.group_by_keywords(
        argv,
        ["transport", "compression", "crypto", "totem"],
    )
    if not modifiers.is_specified("--corosync_conf"):
        lib.cluster.config_update(
            parse_args.prepare_options(parsed_args.get_args_flat("transport")),
            parse_args.prepare_options(
                parsed_args.get_args_flat("compression")
            ),
            parse_args.prepare_options(parsed_args.get_args_flat("crypto")),
            parse_args.prepare_options(parsed_args.get_args_flat("totem")),
        )
        return

    _corosync_conf_local_cmd_call(
        modifiers.get("--corosync_conf"),
        lambda corosync_conf_content: lib.cluster.config_update_local(
            corosync_conf_content,
            parse_args.prepare_options(parsed_args.get_args_flat("transport")),
            parse_args.prepare_options(
                parsed_args.get_args_flat("compression")
            ),
            parse_args.prepare_options(parsed_args.get_args_flat("crypto")),
            parse_args.prepare_options(parsed_args.get_args_flat("totem")),
        ),
    )


def _format_options(label: str, options: Mapping[str, str]) -> List[str]:
    output = []
    if options:
        output.append(f"{label}:")
        output.extend(
            indent([f"{opt}: {val}" for opt, val in sorted(options.items())])
        )
    return output


def _format_nodes(nodes: Iterable[CorosyncNodeDto]) -> List[str]:
    output = ["Nodes:"]
    for node in sorted(nodes, key=lambda node: node.name):
        node_attrs = [
            f"Link {addr.link} address: {addr.addr}"
            for addr in sorted(node.addrs, key=lambda addr: addr.link)
        ] + [f"nodeid: {node.nodeid}"]
        output.extend(indent([f"{node.name}:"] + indent(node_attrs)))
    return output


def config_show(
    lib: Any, argv: List[str], modifiers: parse_args.InputModifiers
) -> None:
    """
    Options:
      * --corosync_conf - corosync.conf file path, do not talk to cluster nodes
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported(
        "--corosync_conf", output_format_supported=True
    )
    if argv:
        raise CmdLineInputError()
    output_format = modifiers.get_output_format()
    corosync_conf_dto = lib.cluster.get_corosync_conf_struct()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        if corosync_conf_dto.quorum_device is not None:
            warn(
                "Quorum device configuration detected but not yet supported by "
                "this command."
            )
        output = " \\\n".join(_config_get_cmd(corosync_conf_dto))
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(dto.to_dict(corosync_conf_dto))
    else:
        output = "\n".join(_config_get_text(corosync_conf_dto))
    print(output)


def _config_get_text(corosync_conf: CorosyncConfDto) -> List[str]:
    lines = [f"Cluster Name: {corosync_conf.cluster_name}"]
    if corosync_conf.cluster_uuid:
        lines.append(f"Cluster UUID: {corosync_conf.cluster_uuid}")
    lines.append("Transport: {}".format(corosync_conf.transport.lower()))
    lines.extend(_format_nodes(corosync_conf.nodes))
    if corosync_conf.links_options:
        lines.append("Links:")
        for linknum, link_options in sorted(
            corosync_conf.links_options.items()
        ):
            lines.extend(
                indent(_format_options(f"Link {linknum}", link_options))
            )

    lines.extend(
        _format_options("Transport Options", corosync_conf.transport_options)
    )
    lines.extend(
        _format_options(
            "Compression Options", corosync_conf.compression_options
        )
    )
    lines.extend(
        _format_options("Crypto Options", corosync_conf.crypto_options)
    )
    lines.extend(_format_options("Totem Options", corosync_conf.totem_options))
    lines.extend(
        _format_options("Quorum Options", corosync_conf.quorum_options)
    )
    if corosync_conf.quorum_device:
        lines.append(f"Quorum Device: {corosync_conf.quorum_device.model}")
        lines.extend(
            indent(
                _format_options(
                    "Options", corosync_conf.quorum_device.generic_options
                )
            )
        )
        lines.extend(
            indent(
                _format_options(
                    "Model Options",
                    corosync_conf.quorum_device.model_options,
                )
            )
        )
        lines.extend(
            indent(
                _format_options(
                    "Heuristics",
                    corosync_conf.quorum_device.heuristics_options,
                )
            )
        )
    return lines


def _corosync_node_to_cmd_line(node: CorosyncNodeDto) -> str:
    return " ".join(
        [node.name]
        + [
            f"addr={addr.addr}"
            for addr in sorted(node.addrs, key=lambda addr: addr.link)
        ]
    )


def _section_to_lines(
    options: Mapping[str, str], keyword: Optional[str] = None
) -> List[str]:
    output: List[str] = []
    if options:
        if keyword:
            output.append(keyword)
        output.extend(
            indent([f"{key}={val}" for key, val in sorted(options.items())])
        )
    return indent(output)


def _config_get_cmd(corosync_conf: CorosyncConfDto) -> List[str]:
    lines = [f"pcs cluster setup {corosync_conf.cluster_name}"]
    lines += indent(
        [
            _corosync_node_to_cmd_line(node)
            for node in sorted(
                corosync_conf.nodes, key=lambda node: node.nodeid
            )
        ]
    )
    transport = [
        "transport",
        str(corosync_conf.transport.value).lower(),
    ] + _section_to_lines(corosync_conf.transport_options)
    for _, link in sorted(corosync_conf.links_options.items()):
        transport.extend(_section_to_lines(link, "link"))
    transport.extend(
        _section_to_lines(corosync_conf.compression_options, "compression")
    )
    transport.extend(_section_to_lines(corosync_conf.crypto_options, "crypto"))
    lines.extend(indent(transport))
    lines.extend(_section_to_lines(corosync_conf.totem_options, "totem"))
    lines.extend(_section_to_lines(corosync_conf.quorum_options, "quorum"))
    if not corosync_conf.cluster_uuid:
        lines.extend(indent(["--no-cluster-uuid"]))
    return lines


def _parse_add_node(argv):
    # pylint: disable=invalid-name
    DEVICE_KEYWORD = "device"
    WATCHDOG_KEYWORD = "watchdog"
    hostname, *argv = argv
    node_dict = _parse_node_options(
        hostname,
        argv,
        additional_options={DEVICE_KEYWORD, WATCHDOG_KEYWORD},
        additional_repeatable_options={DEVICE_KEYWORD},
    )
    if DEVICE_KEYWORD in node_dict:
        node_dict[f"{DEVICE_KEYWORD}s"] = node_dict[DEVICE_KEYWORD]
        del node_dict[DEVICE_KEYWORD]
    return node_dict


def node_add(lib, argv, modifiers):
    """
    Options:
      * --wait - wait until new node will start up, effective only when --start
        is specified
      * --start - start new node
      * --enable - enable new node
      * --force - treat validation issues and not resolvable addresses as
        warnings instead of errors
      * --skip-offline - skip unreachable nodes
      * --no-watchdog-validation - do not validatate watchdogs
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported(
        "--wait",
        "--start",
        "--enable",
        "--force",
        "--skip-offline",
        "--no-watchdog-validation",
        "--request-timeout",
    )
    if not argv:
        raise CmdLineInputError()

    node_dict = _parse_add_node(argv)

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    lib.cluster.add_nodes(
        nodes=[node_dict],
        wait=modifiers.get("--wait"),
        start=modifiers.get("--start"),
        enable=modifiers.get("--enable"),
        no_watchdog_validation=modifiers.get("--no-watchdog-validation"),
        force_flags=force_flags,
    )


def remove_nodes_from_cib(lib, argv, modifiers):
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if not argv:
        raise CmdLineInputError("No nodes specified")
    lib.cluster.remove_nodes_from_cib(argv)


def link_add(lib, argv, modifiers):
    """
    Options:
      * --force - treat validation issues and not resolvable addresses as
        warnings instead of errors
      * --skip-offline - skip unreachable nodes
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported(
        "--force", "--request-timeout", "--skip-offline"
    )
    if not argv:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    parsed = parse_args.group_by_keywords(
        argv, {"options"}, implicit_first_keyword="nodes"
    )
    parsed.ensure_unique_keywords()

    lib.cluster.add_link(
        parse_args.prepare_options(parsed.get_args_flat("nodes")),
        parse_args.prepare_options(parsed.get_args_flat("options")),
        force_flags=force_flags,
    )


def link_remove(lib, argv, modifiers):
    """
    Options:
      * --skip-offline - skip unreachable nodes
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported("--request-timeout", "--skip-offline")
    if not argv:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    lib.cluster.remove_links(argv, force_flags=force_flags)


def link_update(lib, argv, modifiers):
    """
    Options:
      * --force - treat validation issues and not resolvable addresses as
        warnings instead of errors
      * --skip-offline - skip unreachable nodes
      * --request-timeout - HTTP request timeout
    """
    modifiers.ensure_only_supported(
        "--force", "--request-timeout", "--skip-offline"
    )
    if len(argv) < 2:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)
    if modifiers.get("--skip-offline"):
        force_flags.append(reports.codes.SKIP_OFFLINE_NODES)

    linknumber = argv[0]
    parsed = parse_args.group_by_keywords(
        argv[1:], {"options"}, implicit_first_keyword="nodes"
    )
    parsed.ensure_unique_keywords()

    lib.cluster.update_link(
        linknumber,
        parse_args.prepare_options(parsed.get_args_flat("nodes")),
        parse_args.prepare_options(parsed.get_args_flat("options")),
        force_flags=force_flags,
    )


def generate_uuid(
    lib: Any, argv: List[str], modifiers: parse_args.InputModifiers
):
    """
    Options:
      * --force - allow to rewrite an existing UUID in corosync.conf
      * --corosync_conf - corosync.conf file path, do not talk to cluster nodes
    """
    modifiers.ensure_only_supported("--force", "--corosync_conf")
    if argv:
        raise CmdLineInputError()

    force_flags = []
    if modifiers.get("--force"):
        force_flags.append(reports.codes.FORCE)

    if not modifiers.is_specified("--corosync_conf"):
        lib.cluster.generate_cluster_uuid(force_flags=force_flags)
        return

    _corosync_conf_local_cmd_call(
        modifiers.get("--corosync_conf"),
        lambda corosync_conf_content: lib.cluster.generate_cluster_uuid_local(
            corosync_conf_content, force_flags=force_flags
        ),
    )
