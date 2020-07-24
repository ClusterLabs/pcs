import os.path
import re
from typing import (
    Iterable,
    List,
    Optional,
    Tuple,
)

from lxml import etree

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.tools import format_os_error, xml_fromstring
from pcs.common.str_tools import join_multilines
from pcs.lib.cib.tools import get_pacemaker_version_by_which_cib_was_validated
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.tools import write_tmpfile
from pcs.lib.xml_tools import etree_to_str


__EXITCODE_WAIT_TIMEOUT = 124
__EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT = 105
__RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD = 100


class CrmMonErrorException(LibraryError):
    pass


class FenceHistoryCommandErrorException(Exception):
    pass


### status


def get_cluster_status_xml(runner):
    stdout, stderr, retval = runner.run(
        [__exec("crm_mon"), "--one-shot", "--as-xml", "--inactive"]
    )
    if retval != 0:
        raise CrmMonErrorException(
            ReportItem.error(
                reports.messages.CrmMonError(join_multilines([stderr, stdout]))
            )
        )
    return stdout


def get_cluster_status_text(
    runner: CommandRunner, hide_inactive_resources: bool, verbose: bool,
) -> Tuple[str, List[str]]:
    cmd = [__exec("crm_mon"), "--one-shot"]
    if not hide_inactive_resources:
        cmd.append("--inactive")
    if verbose:
        cmd.extend(["--show-detail", "--show-node-attributes", "--failcounts"])
        # by default, pending and failed actions are displayed
        # with verbose==True, we display the whole history
        if is_fence_history_supported_status(runner):
            cmd.append("--fence-history=3")
    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise CrmMonErrorException(
            ReportItem.error(
                reports.messages.CrmMonError(join_multilines([stderr, stdout]))
            )
        )
    warnings: List[str] = []
    if stderr.strip():
        warnings = [
            line
            for line in stderr.strip().splitlines()
            if verbose or not line.startswith("DEBUG: ")
        ]

    return stdout.strip(), warnings


def get_ticket_status_text(runner: CommandRunner) -> Tuple[str, str, int]:
    stdout, stderr, retval = runner.run([__exec("crm_ticket"), "--details"])
    return stdout.strip(), stderr.strip(), retval


### cib


def get_cib_xml_cmd_results(runner, scope=None):
    command = [__exec("cibadmin"), "--local", "--query"]
    if scope:
        command.append("--scope={0}".format(scope))
    stdout, stderr, returncode = runner.run(command)
    return stdout, stderr, returncode


def get_cib_xml(runner, scope=None):
    stdout, stderr, retval = get_cib_xml_cmd_results(runner, scope)
    if retval != 0:
        if retval == __EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT and scope:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.CibLoadErrorScopeMissing(
                        scope, join_multilines([stderr, stdout])
                    )
                )
            )
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibLoadError(join_multilines([stderr, stdout]))
            )
        )
    return stdout


def parse_cib_xml(xml):
    return xml_fromstring(xml)


def get_cib(xml):
    try:
        return parse_cib_xml(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibLoadErrorBadFormat(str(e)))
        )


def verify(runner, verbose=False):
    crm_verify_cmd = [__exec("crm_verify")]
    # Currently, crm_verify can suggest up to two -V options but it accepts
    # more than two. We stick with two -V options if verbose mode was enabled.
    if verbose:
        crm_verify_cmd.extend(["-V", "-V"])
    # With the `crm_verify` command it is not possible simply use the
    # environment variable CIB_file because `crm_verify` simply tries to
    # connect to cib file via tool that can fail because: Update does not
    # conform to the configured schema
    # So we use the explicit flag `--xml-file`.
    cib_tmp_file = runner.env_vars.get("CIB_file", None)
    if cib_tmp_file is None:
        crm_verify_cmd.append("--live-check")
    else:
        crm_verify_cmd.extend(["--xml-file", cib_tmp_file])
    stdout, stderr, returncode = runner.run(crm_verify_cmd)
    can_be_more_verbose = False
    if returncode != 0:
        # remove lines with -V options
        rx_v_option = re.compile(r".*-V( -V)* .*more detail.*")
        new_lines = []
        for line in stderr.splitlines(keepends=True):
            if rx_v_option.match(line):
                can_be_more_verbose = True
                continue
            new_lines.append(line)
        # pcs has only one verbose option and cannot be more verbose like
        # `crm_verify` with more -V options. Decision has been made that pcs is
        # limited to only two -V opions.
        if verbose:
            can_be_more_verbose = False
        stderr = "".join(new_lines)
    return stdout, stderr, returncode, can_be_more_verbose


def replace_cib_configuration_xml(runner, xml):
    cmd = [
        __exec("cibadmin"),
        "--replace",
        "--verbose",
        "--xml-pipe",
        "--scope",
        "configuration",
    ]
    stdout, stderr, retval = runner.run(cmd, stdin_string=xml)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(reports.messages.CibPushError(stderr, stdout))
        )


def replace_cib_configuration(runner, tree):
    return replace_cib_configuration_xml(runner, etree_to_str(tree))


def push_cib_diff_xml(runner, cib_diff_xml):
    cmd = [
        __exec("cibadmin"),
        "--patch",
        "--verbose",
        "--xml-pipe",
    ]
    stdout, stderr, retval = runner.run(cmd, stdin_string=cib_diff_xml)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(reports.messages.CibPushError(stderr, stdout))
        )


def diff_cibs_xml(
    runner: CommandRunner, reporter: ReportProcessor, cib_old_xml, cib_new_xml,
):
    """
    Return xml diff of two CIBs

    runner
    reporter
    string cib_old_xml -- original CIB
    string cib_new_xml -- modified CIB
    """
    try:
        cib_old_tmp_file = write_tmpfile(cib_old_xml)
        reporter.report(
            ReportItem.debug(
                reports.messages.TmpFileWrite(
                    cib_old_tmp_file.name, cib_old_xml
                )
            )
        )
        cib_new_tmp_file = write_tmpfile(cib_new_xml)
        reporter.report(
            ReportItem.debug(
                reports.messages.TmpFileWrite(
                    cib_new_tmp_file.name, cib_new_xml
                )
            )
        )
    except EnvironmentError as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibSaveTmpError(str(e)))
        )
    command = [
        __exec("crm_diff"),
        "--original",
        cib_old_tmp_file.name,
        "--new",
        cib_new_tmp_file.name,
        "--no-version",
    ]
    #  0 (CRM_EX_OK) - success with no difference
    #  1 (CRM_EX_ERROR) - success with difference
    # 64 (CRM_EX_USAGE) - usage error
    # 65 (CRM_EX_DATAERR) - XML fragments not parseable
    stdout, stderr, retval = runner.run(command)
    if retval == 0:
        return ""
    if retval > 1:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibDiffError(
                    stderr.strip(), cib_old_xml, cib_new_xml
                )
            )
        )
    return stdout.strip()


def ensure_cib_version(runner, cib, version):
    """
    This method ensures that specified cib is verified by pacemaker with
    version 'version' or newer. If cib doesn't correspond to this version,
    method will try to upgrade cib.
    Returns cib which was verified by pacemaker version 'version' or later.
    Raises LibraryError on any failure.

    CommandRunner runner -- runner
    etree cib -- cib tree
    pcs.common.tools.Version version -- required cib version
    """
    current_version = get_pacemaker_version_by_which_cib_was_validated(cib)
    if current_version >= version:
        return None

    _upgrade_cib(runner)
    new_cib_xml = get_cib_xml(runner)

    try:
        new_cib = parse_cib_xml(new_cib_xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibUpgradeFailed(str(e)))
        )

    current_version = get_pacemaker_version_by_which_cib_was_validated(new_cib)
    if current_version >= version:
        return new_cib

    raise LibraryError(
        ReportItem.error(
            reports.messages.CibUpgradeFailedToMinimalRequiredVersion(
                str(current_version), str(version)
            )
        )
    )


def _upgrade_cib(runner):
    """
    Upgrade CIB to the latest schema available locally or clusterwise.
    CommandRunner runner
    """
    stdout, stderr, retval = runner.run(
        [__exec("cibadmin"), "--upgrade", "--force"]
    )
    # If we are already on the latest schema available, cibadmin exits with 0.
    # That is fine. We do not know here what version is required anyway. The
    # caller knows that and is responsible for dealing with it.
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibUpgradeFailed(
                    join_multilines([stderr, stdout])
                )
            )
        )


def simulate_cib_xml(runner, cib_xml):
    """
    Run crm_simulate to get effects the cib would have on the live cluster

    CommandRunner runner -- runner
    string cib_xml -- CIB XML to simulate
    """
    try:
        new_cib_file = write_tmpfile(None)
        transitions_file = write_tmpfile(None)
    except OSError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibSimulateError(format_os_error(e))
            )
        )

    cmd = [
        __exec("crm_simulate"),
        "--simulate",
        "--save-output",
        new_cib_file.name,
        "--save-graph",
        transitions_file.name,
        "--xml-pipe",
    ]
    stdout, stderr, retval = runner.run(cmd, stdin_string=cib_xml)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(reports.messages.CibSimulateError(stderr.strip()))
        )

    try:
        new_cib_file.seek(0)
        transitions_file.seek(0)
        new_cib_xml = new_cib_file.read()
        transitions_xml = transitions_file.read()
        new_cib_file.close()
        transitions_file.close()
        return stdout, transitions_xml, new_cib_xml
    except OSError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibSimulateError(format_os_error(e))
            )
        )


def simulate_cib(runner, cib):
    """
    Run crm_simulate to get effects the cib would have on the live cluster

    CommandRunner runner -- runner
    etree cib -- cib tree to simulate
    """
    cib_xml = etree_to_str(cib)
    try:
        plaintext_result, transitions_xml, new_cib_xml = simulate_cib_xml(
            runner, cib_xml
        )
        return (
            plaintext_result.strip(),
            xml_fromstring(transitions_xml),
            xml_fromstring(new_cib_xml),
        )
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibSimulateError(str(e)))
        )


### wait for idle


def has_wait_for_idle_support(runner):
    return __is_in_crm_resource_help(runner, "--wait")


def ensure_wait_for_idle_support(runner):
    if not has_wait_for_idle_support(runner):
        raise LibraryError(
            ReportItem.error(reports.messages.WaitForIdleNotSupported())
        )


def wait_for_idle(runner, timeout=None):
    """
    Run waiting command. Raise LibraryError if command failed.

    runner is preconfigured object for running external programs
    string timeout is waiting timeout
    """
    args = [__exec("crm_resource"), "--wait"]
    if timeout is not None:
        args.append("--timeout={0}".format(timeout))
    stdout, stderr, retval = runner.run(args)
    if retval != 0:
        # Usefull info goes to stderr - not only error messages, a list of
        # pending actions in case of timeout goes there as well.
        # We use stdout just to be sure if that's get changed.
        if retval == __EXITCODE_WAIT_TIMEOUT:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.WaitForIdleTimedOut(
                        join_multilines([stderr, stdout])
                    )
                )
            )
        raise LibraryError(
            ReportItem.error(
                reports.messages.WaitForIdleError(
                    join_multilines([stderr, stdout])
                )
            )
        )


### nodes


def get_local_node_name(runner):
    stdout, stderr, retval = runner.run([__exec("crm_node"), "--name"])
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.PacemakerLocalNodeNameNotFound(
                    join_multilines([stderr, stdout])
                )
            )
        )
    return stdout.strip()


def get_local_node_status(runner):
    try:
        cluster_status = ClusterState(get_cluster_status_xml(runner))
    except CrmMonErrorException:
        return {"offline": True}
    node_name = get_local_node_name(runner)
    for node_status in cluster_status.node_section.nodes:
        if node_status.attrs.name == node_name:
            result = {
                "offline": False,
            }
            for attr in (
                "id",
                "name",
                "type",
                "online",
                "standby",
                "standby_onfail",
                "maintenance",
                "pending",
                "unclean",
                "shutdown",
                "expected_up",
                "is_dc",
                "resources_running",
            ):
                result[attr] = getattr(node_status.attrs, attr)
            return result
    raise LibraryError(
        ReportItem.error(reports.messages.NodeNotFound(node_name))
    )


def remove_node(runner, node_name):
    stdout, stderr, retval = runner.run(
        [__exec("crm_node"), "--force", "--remove", node_name,]
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.NodeRemoveInPacemakerFailed(
                    node_list_to_remove=[node_name],
                    reason=join_multilines([stderr, stdout]),
                )
            )
        )


### resources


def resource_cleanup(
    runner: CommandRunner,
    resource: Optional[str] = None,
    node: Optional[str] = None,
    operation: Optional[str] = None,
    interval: Optional[str] = None,
    strict: bool = False,
):
    cmd = [__exec("crm_resource"), "--cleanup"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])
    if operation:
        cmd.extend(["--operation", operation])
    if interval:
        cmd.extend(["--interval", interval])
    if strict:
        cmd.extend(["--force"])

    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceCleanupError(
                    join_multilines([stderr, stdout]), resource, node
                )
            )
        )
    # usefull output (what has been done) goes to stderr
    return join_multilines([stdout, stderr])


def resource_refresh(
    runner: CommandRunner,
    resource: Optional[str] = None,
    node: Optional[str] = None,
    strict: bool = False,
    force: bool = False,
):
    if not force and not node and not resource:
        summary = ClusterState(get_cluster_status_xml(runner)).summary
        operations = summary.nodes.attrs.count * summary.resources.attrs.count
        if operations > __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD:
            raise LibraryError(
                ReportItem(
                    reports.item.ReportItemSeverity.error(
                        reports.codes.FORCE_LOAD_THRESHOLD
                    ),
                    reports.messages.ResourceRefreshTooTimeConsuming(
                        __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD
                    ),
                )
            )

    cmd = [__exec("crm_resource"), "--refresh"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])
    if strict:
        cmd.extend(["--force"])

    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceRefreshError(
                    join_multilines([stderr, stdout]), resource, node
                )
            )
        )
    # usefull output (what has been done) goes to stderr
    return join_multilines([stdout, stderr])


def resource_move(runner, resource_id, node=None, main=False, lifetime=None):
    return _resource_move_ban_clear(
        runner,
        "--move",
        resource_id,
        node=node,
        main=main,
        lifetime=lifetime,
    )


def resource_ban(runner, resource_id, node=None, main=False, lifetime=None):
    return _resource_move_ban_clear(
        runner,
        "--ban",
        resource_id,
        node=node,
        main=main,
        lifetime=lifetime,
    )


def resource_unmove_unban(
    runner, resource_id, node=None, main=False, expired=False
):
    return _resource_move_ban_clear(
        runner,
        "--clear",
        resource_id,
        node=node,
        main=main,
        expired=expired,
    )


def has_resource_unmove_unban_expired_support(runner):
    return __is_in_crm_resource_help(runner, "--expired")


def _resource_move_ban_clear(
    runner,
    action,
    resource_id,
    node=None,
    main=False,
    lifetime=None,
    expired=False,
):
    command = [
        __exec("crm_resource"),
        action,
        "--resource",
        resource_id,
    ]
    if node:
        command.extend(["--node", node])
    if main:
        command.extend(["--main"])
    if lifetime:
        command.extend(["--lifetime", lifetime])
    if expired:
        command.extend(["--expired"])
    stdout, stderr, retval = runner.run(command)
    return stdout, stderr, retval


### fence history


def is_fence_history_supported_status(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(runner, "crm_mon", ["--fence-history"])


def is_fence_history_supported_management(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(
        runner, "stonith_admin", ["--history", "--broadcast", "--cleanup"]
    )


def fence_history_cleanup(runner, node=None):
    return _run_fence_history_command(runner, "--cleanup", node)


def fence_history_text(runner, node=None):
    return _run_fence_history_command(runner, "--verbose", node)


def fence_history_update(runner):
    # Pacemaker always prints "gather fencing-history from all nodes" even if a
    # node is specified. However, --history expects a value, so we must provide
    # it. Otherwise "--broadcast" would be considered a value of "--history".
    return _run_fence_history_command(runner, "--broadcast", node=None)


def _run_fence_history_command(runner, command, node=None):
    stdout, stderr, retval = runner.run(
        [__exec("stonith_admin"), "--history", node if node else "*", command]
    )
    if retval != 0:
        raise FenceHistoryCommandErrorException(
            join_multilines([stderr, stdout])
        )
    return stdout.strip()


### tools

# shortcut for getting a full path to a pacemaker executable
def __exec(name):
    return os.path.join(settings.pacemaker_binaries, name)


def __is_in_crm_resource_help(runner, text):
    # returns 1 on success so we don't care about retval
    stdout, stderr, dummy_retval = runner.run([__exec("crm_resource"), "-?"])
    # help goes to stderr but we check stdout as well if that gets changed
    return text in stderr or text in stdout


def _is_in_pcmk_tool_help(
    runner: CommandRunner, tool: str, text_list: Iterable[str]
) -> bool:
    stdout, stderr, dummy_retval = runner.run([__exec(tool), "--help-all"])
    # Help goes to stderr but we check stdout as well if that gets changed. Use
    # generators in all to return early.
    return all(text in stderr for text in text_list) or all(
        text in stdout for text in text_list
    )
