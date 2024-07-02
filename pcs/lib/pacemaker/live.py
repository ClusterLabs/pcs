import os.path
import re
from typing import (
    Mapping,
    Optional,
    Union,
    cast,
)

from lxml import etree
from lxml.etree import _Element

from pcs import settings
from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.str_tools import join_multilines
from pcs.common.tools import (
    Version,
    format_os_error,
    xml_fromstring,
)
from pcs.common.types import (
    CibRuleInEffectStatus,
    StringCollection,
    StringSequence,
)
from pcs.lib import tools
from pcs.lib.cib.tools import get_pacemaker_version_by_which_cib_was_validated
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.pacemaker import api_result
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.resource_agent import ResourceAgentName
from pcs.lib.xml_tools import etree_to_str

__EXITCODE_NOT_CONNECTED = 102
__EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT = 105
__EXITCODE_WAIT_TIMEOUT = 124
__RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD = 100


class PacemakerNotConnectedException(LibraryError):
    pass


class FenceHistoryCommandErrorException(Exception):
    pass


### status


def get_cluster_status_xml_raw(runner: CommandRunner) -> tuple[str, str, int]:
    """
    Run pacemaker tool to get XML status. This function doesn't do any
    processing. Usually, using get_cluster_status_dom is preferred instead.
    """
    return runner.run(
        [
            settings.crm_mon_exec,
            "--one-shot",
            "--inactive",
            "--output-as",
            "xml",
        ]
    )


def _get_cluster_status_xml(runner: CommandRunner) -> str:
    """
    Get pacemaker XML status. Using get_cluster_status_dom is preferred instead.
    """
    stdout, stderr, retval = get_cluster_status_xml_raw(runner)
    if retval == 0:
        return stdout

    # We parse error messages from XML. If we didn't get an XML, we pass it to
    # the exception as a plaintext. If we got an XML but it doesn't conform to
    # the schema, we raise an error.
    try:
        status = _get_status_from_api_result(_get_api_result_dom(stdout))
        message = join_multilines([status.message] + list(status.errors))
    except etree.XMLSyntaxError:
        message = join_multilines([stderr, stdout])
    except etree.DocumentInvalid as e:
        raise LibraryError(
            ReportItem.error(reports.messages.BadClusterStateFormat())
        ) from e
    klass = (
        PacemakerNotConnectedException
        if retval == __EXITCODE_NOT_CONNECTED
        else LibraryError
    )
    raise klass(ReportItem.error(reports.messages.CrmMonError(message)))


def get_cluster_status_dom(runner: CommandRunner) -> _Element:
    try:
        return _get_api_result_dom(_get_cluster_status_xml(runner))
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.BadClusterStateFormat())
        ) from e


def get_cluster_status_text(
    runner: CommandRunner,
    hide_inactive_resources: bool,
    verbose: bool,
) -> tuple[str, list[str]]:
    cmd = [settings.crm_mon_exec, "--one-shot"]
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
        raise LibraryError(
            ReportItem.error(
                reports.messages.CrmMonError(join_multilines([stderr, stdout]))
            )
        )
    warnings: list[str] = []
    if stderr.strip():
        warnings = [
            line
            for line in stderr.strip().splitlines()
            if verbose or not line.startswith("DEBUG: ")
        ]

    return stdout.strip(), warnings


def get_ticket_status_text(runner: CommandRunner) -> tuple[str, str, int]:
    stdout, stderr, retval = runner.run([settings.crm_ticket_exec, "--details"])
    return stdout.strip(), stderr.strip(), retval


### cib


def has_cib_xml() -> bool:
    return os.path.exists(os.path.join(settings.cib_dir, "cib.xml"))


def get_cib_xml_cmd_results(
    runner: CommandRunner, scope: Optional[str] = None
) -> tuple[str, str, int]:
    command = [settings.cibadmin_exec, "--local", "--query"]
    if scope:
        command.append(f"--scope={scope}")
    stdout, stderr, returncode = runner.run(command)
    return stdout, stderr, returncode


def get_cib_xml(runner: CommandRunner, scope: Optional[str] = None) -> str:
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


def parse_cib_xml(xml: str) -> _Element:
    return xml_fromstring(xml)


def get_cib(xml: str) -> _Element:
    try:
        return parse_cib_xml(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibLoadErrorBadFormat(str(e)))
        ) from e


def verify(
    runner: CommandRunner, verbose: bool = False
) -> tuple[str, str, int, bool]:
    crm_verify_cmd = [settings.crm_verify_exec]
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
        # limited to only two -V options.
        if verbose:
            can_be_more_verbose = False
        stderr = "".join(new_lines)
    return stdout, stderr, returncode, can_be_more_verbose


def replace_cib_configuration_xml(runner: CommandRunner, xml: str) -> None:
    cmd = [
        settings.cibadmin_exec,
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


def replace_cib_configuration(runner: CommandRunner, tree: _Element) -> None:
    return replace_cib_configuration_xml(runner, etree_to_str(tree))


def push_cib_diff_xml(runner: CommandRunner, cib_diff_xml: str) -> None:
    cmd = [
        settings.cibadmin_exec,
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
    runner: CommandRunner,
    reporter: ReportProcessor,
    cib_old_xml: str,
    cib_new_xml: str,
) -> str:
    """
    Return xml diff of two CIBs

    cib_old_xml -- original CIB
    cib_new_xml -- modified CIB
    """
    with (
        tools.get_tmp_cib(reporter, cib_old_xml) as cib_old_tmp_file,
        tools.get_tmp_cib(reporter, cib_new_xml) as cib_new_tmp_file,
    ):
        stdout, stderr, retval = runner.run(
            [
                settings.crm_diff_exec,
                "--original",
                cib_old_tmp_file.name,
                "--new",
                cib_new_tmp_file.name,
                "--no-version",
            ]
        )
    #  0 (CRM_EX_OK) - success with no difference
    #  1 (CRM_EX_ERROR) - success with difference
    # 64 (CRM_EX_USAGE) - usage error
    # 65 (CRM_EX_DATAERR) - XML fragments not parseable
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


def ensure_cib_version(
    runner: CommandRunner,
    cib: _Element,
    version: Version,
    fail_if_version_not_met: bool = True,
) -> tuple[_Element, bool]:
    """
    Make sure CIB complies to specified schema version (or newer), upgrade CIB
    if necessary. Raise on error. Raise if CIB cannot be upgraded enough to
    meet the required version unless fail_if_version_not_met is set to False.
    Return tuple(upgraded_cib, was_upgraded)

    version -- required cib version
    fail_if_version_not_met -- allows a 'nice to have' cib upgrade
    """
    version_pre_upgrade = get_pacemaker_version_by_which_cib_was_validated(cib)
    if version_pre_upgrade >= version:
        return cib, False

    _upgrade_cib(runner)
    new_cib_xml = get_cib_xml(runner)

    try:
        new_cib = parse_cib_xml(new_cib_xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(
            ReportItem.error(reports.messages.CibUpgradeFailed(str(e)))
        ) from e

    version_post_upgrade = get_pacemaker_version_by_which_cib_was_validated(
        new_cib
    )
    if version_post_upgrade >= version or not fail_if_version_not_met:
        return new_cib, version_post_upgrade > version_pre_upgrade

    raise LibraryError(
        ReportItem.error(
            reports.messages.CibUpgradeFailedToMinimalRequiredVersion(
                str(version_post_upgrade), str(version)
            )
        )
    )


def _upgrade_cib(runner: CommandRunner) -> None:
    """
    Upgrade CIB to the latest schema available locally or clusterwise.
    """
    stdout, stderr, retval = runner.run(
        [settings.cibadmin_exec, "--upgrade", "--force"]
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


def simulate_cib_xml(
    runner: CommandRunner, cib_xml: str
) -> tuple[str, str, str]:
    """
    Run crm_simulate to get effects the cib would have on the live cluster

    cib_xml -- CIB XML to simulate
    """
    try:
        with (
            tools.get_tmp_file(None) as new_cib_file,
            tools.get_tmp_file(None) as transitions_file,
        ):
            cmd = [
                settings.crm_simulate_exec,
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
                    ReportItem.error(
                        reports.messages.CibSimulateError(stderr.strip())
                    )
                )
            new_cib_file.seek(0)
            transitions_file.seek(0)
            transitions = transitions_file.read()
            new_cib = new_cib_file.read()
            return stdout, transitions, new_cib
    except OSError as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CibSimulateError(format_os_error(e))
            )
        ) from e


def simulate_cib(
    runner: CommandRunner, cib: _Element
) -> tuple[str, _Element, _Element]:
    """
    Run crm_simulate to get effects the cib would have on the live cluster

    cib -- cib tree to simulate
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
        ) from e


### wait for idle


def wait_for_idle(runner: CommandRunner, timeout: int) -> None:
    """
    Run waiting command. Raise LibraryError if command failed.

    timeout -- waiting timeout in seconds, wait indefinitely if less than 1
    """
    args = [settings.crm_resource_exec, "--wait"]
    if timeout > 0:
        args.append(f"--timeout={timeout}")
    stdout, stderr, retval = runner.run(args)
    if retval != 0:
        # Useful info goes to stderr - not only error messages, a list of
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


def get_local_node_name(runner: CommandRunner) -> str:
    stdout, stderr, retval = runner.run([settings.crm_node_exec, "--name"])
    if retval != 0:
        klass = (
            PacemakerNotConnectedException
            if retval == __EXITCODE_NOT_CONNECTED
            else LibraryError
        )
        raise klass(
            ReportItem.error(
                reports.messages.PacemakerLocalNodeNameNotFound(
                    join_multilines([stderr, stdout])
                )
            )
        )
    return stdout.strip()


def get_local_node_status(runner: CommandRunner) -> dict[str, Union[bool, str]]:
    try:
        cluster_status = ClusterState(get_cluster_status_dom(runner))
        node_name = get_local_node_name(runner)
    except PacemakerNotConnectedException:
        return {"offline": True}
    for node_status in cluster_status.node_section.nodes:
        if node_status.attrs.name == node_name:
            result: dict[str, Union[bool, str]] = {
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


def remove_node(runner: CommandRunner, node_name: str) -> None:
    stdout, stderr, retval = runner.run(
        [
            settings.crm_node_exec,
            "--force",
            "--remove",
            node_name,
        ]
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


def resource_restart(
    runner: CommandRunner,
    resource: str,
    node: Optional[str] = None,
    timeout: Optional[str] = None,
) -> None:
    """
    Ask pacemaker to restart a resource

    resource -- id of the resource to be restarted
    node -- name of the node to limit the restart to
    timeout -- abort if the command doesn't finish in this time (integer + unit)
    """
    cmd = [settings.crm_resource_exec, "--restart", "--resource", resource]
    if node:
        cmd.extend(["--node", node])
    if timeout:
        cmd.extend(["--timeout", timeout])

    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceRestartError(
                    join_multilines([stderr, stdout]), resource, node
                )
            )
        )


def resource_cleanup(
    runner: CommandRunner,
    resource: Optional[str] = None,
    node: Optional[str] = None,
    operation: Optional[str] = None,
    interval: Optional[str] = None,
    strict: bool = False,
) -> str:
    cmd = [settings.crm_resource_exec, "--cleanup"]
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
    # useful output (what has been done) goes to stderr
    return join_multilines([stdout, stderr])


def resource_refresh(
    runner: CommandRunner,
    resource: Optional[str] = None,
    node: Optional[str] = None,
    strict: bool = False,
    force: bool = False,
) -> str:
    if not force and not node and not resource:
        summary = ClusterState(get_cluster_status_dom(runner)).summary
        operations = summary.nodes.attrs.count * summary.resources.attrs.count
        if operations > __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD:
            raise LibraryError(
                ReportItem(
                    reports.item.ReportItemSeverity.error(reports.codes.FORCE),
                    reports.messages.ResourceRefreshTooTimeConsuming(
                        __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD
                    ),
                )
            )

    cmd = [settings.crm_resource_exec, "--refresh"]
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
    # useful output (what has been done) goes to stderr
    return join_multilines([stdout, stderr])


def resource_move(
    runner: CommandRunner,
    resource_id: str,
    node: Optional[str] = None,
    promoted: bool = False,
    lifetime: Optional[str] = None,
) -> tuple[str, str, int]:
    return _resource_move_ban_clear(
        runner,
        "--move",
        resource_id,
        node=node,
        promoted=promoted,
        lifetime=lifetime,
    )


def resource_ban(
    runner: CommandRunner,
    resource_id: str,
    node: Optional[str] = None,
    promoted: bool = False,
    lifetime: Optional[str] = None,
) -> tuple[str, str, int]:
    return _resource_move_ban_clear(
        runner,
        "--ban",
        resource_id,
        node=node,
        promoted=promoted,
        lifetime=lifetime,
    )


def resource_unmove_unban(
    runner: CommandRunner,
    resource_id: str,
    node: Optional[str] = None,
    promoted: bool = False,
    expired: bool = False,
) -> tuple[str, str, int]:
    return _resource_move_ban_clear(
        runner,
        "--clear",
        resource_id,
        node=node,
        promoted=promoted,
        expired=expired,
    )


def has_resource_unmove_unban_expired_support(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(
        runner, settings.crm_resource_exec, ["--expired"]
    )


def _resource_move_ban_clear(
    runner: CommandRunner,
    action: str,
    resource_id: str,
    node: Optional[str] = None,
    promoted: bool = False,
    lifetime: Optional[str] = None,
    expired: bool = False,
) -> tuple[str, str, int]:
    command = [
        settings.crm_resource_exec,
        action,
        "--resource",
        resource_id,
    ]
    if node:
        command.extend(["--node", node])
    if promoted:
        command.extend(["--promoted"])
    if lifetime:
        command.extend(["--lifetime", lifetime])
    if expired:
        command.extend(["--expired"])
    stdout, stderr, retval = runner.run(command)
    return stdout, stderr, retval


### fence history


def is_fence_history_supported_status(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(
        runner, settings.crm_mon_exec, ["--fence-history"]
    )


def is_fence_history_supported_management(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(
        runner,
        settings.stonith_admin_exec,
        ["--history", "--broadcast", "--cleanup"],
    )


def fence_history_cleanup(
    runner: CommandRunner, node: Optional[str] = None
) -> str:
    return _run_fence_history_command(runner, "--cleanup", node)


def fence_history_text(
    runner: CommandRunner, node: Optional[str] = None
) -> str:
    return _run_fence_history_command(runner, "--verbose", node)


def fence_history_update(runner: CommandRunner) -> str:
    # Pacemaker always prints "gather fencing-history from all nodes" even if a
    # node is specified. However, --history expects a value, so we must provide
    # it. Otherwise "--broadcast" would be considered a value of "--history".
    return _run_fence_history_command(runner, "--broadcast", node=None)


def _run_fence_history_command(
    runner: CommandRunner, command: str, node: Optional[str] = None
) -> str:
    stdout, stderr, retval = runner.run(
        [
            settings.stonith_admin_exec,
            "--history",
            node if node else "*",
            command,
        ]
    )
    if retval != 0:
        raise FenceHistoryCommandErrorException(
            join_multilines([stderr, stdout])
        )
    return stdout.strip()


### tools


def has_rule_in_effect_status_tool() -> bool:
    return os.path.isfile(settings.crm_rule_exec)


def get_rule_in_effect_status(
    runner: CommandRunner, cib_xml: str, rule_id: str
) -> CibRuleInEffectStatus:
    """
    Figure out if a rule is in effect, expired or not yet in effect

    runner -- a class for running external processes
    cib_xml -- CIB containing rules
    rule_id -- ID of the rule to be checked
    """
    # TODO Once crm_rule is capable of evaluating more than one rule per go, we
    # should make use of it. Running the tool for each rule may really slow pcs
    # down.
    translation_map = {
        0: CibRuleInEffectStatus.IN_EFFECT,
        110: CibRuleInEffectStatus.EXPIRED,
        111: CibRuleInEffectStatus.NOT_YET_IN_EFFECT,
        # 105:non-existent
        # 112: undetermined (rule is too complicated for current implementation)
    }
    dummy_stdout, dummy_stderr, retval = runner.run(
        [
            settings.crm_rule_exec,
            "--check",
            "--rule",
            rule_id,
            "--xml-text",
            "-",
        ],
        stdin_string=cib_xml,
    )
    return translation_map.get(retval, CibRuleInEffectStatus.UNKNOWN)


def _get_api_result_dom(xml: str) -> _Element:
    # raises etree.XMLSyntaxError and etree.DocumentInvalid
    rng = settings.pacemaker_api_result_schema
    dom = xml_fromstring(xml)
    if os.path.isfile(rng):
        etree.RelaxNG(file=rng).assertValid(dom)
    return dom


def _get_status_from_api_result(dom: _Element) -> api_result.Status:
    errors = []
    status_el = cast(_Element, dom.find("./status"))
    errors_el = status_el.find("errors")
    if errors_el is not None:
        errors = [
            str((error_el.text or "")).strip()
            for error_el in errors_el.iterfind("error")
        ]
    return api_result.Status(
        code=int(str(status_el.get("code"))),
        message=str(status_el.get("message")),
        errors=errors,
    )


def _is_in_pcmk_tool_help(
    runner: CommandRunner, tool: str, text_list: StringCollection
) -> bool:
    stdout, stderr, dummy_retval = runner.run([tool, "--help-all"])
    # Help goes to stderr but we check stdout as well if that gets changed. Use
    # generators in all to return early.
    return all(text in stderr for text in text_list) or all(
        text in stdout for text in text_list
    )


def is_getting_resource_digest_supported(runner: CommandRunner) -> bool:
    return _is_in_pcmk_tool_help(
        runner, settings.crm_resource_exec, ["--digests"]
    )


def get_resource_digests(
    runner: CommandRunner,
    resource_id: str,
    node_name: str,
    resource_options: dict[str, str],
    crm_meta_attributes: Optional[dict[str, Optional[str]]] = None,
) -> dict[str, Optional[str]]:
    """
    Get set of digests for a resource using crm_resource utility. There are 3
    types of digests: all, nonreloadable and nonprivate. Resource can have one
    or more digests types depending on the resource parameters.

    resource_id -- resource id
    node_name -- name of the node where resource is running
    resource_options -- resource options with updated values
    crm_meta_attributes -- parameters of a monitor operation
    """
    # pylint: disable=too-many-locals
    if crm_meta_attributes is None:
        crm_meta_attributes = {}
    command = [
        settings.crm_resource_exec,
        "--digests",
        "--resource",
        resource_id,
        "--node",
        node_name,
        "--output-as",
        "xml",
        *[f"{key}={value}" for key, value in resource_options.items()],
        *[
            f"CRM_meta_{key}={value}"
            for key, value in crm_meta_attributes.items()
            if value is not None
        ],
    ]
    stdout, stderr, retval = runner.run(command)

    def error_exception(message: str) -> LibraryError:
        return LibraryError(
            ReportItem.error(
                reports.messages.UnableToGetResourceOperationDigests(message)
            )
        )

    try:
        dom = _get_api_result_dom(stdout)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise error_exception(join_multilines([stderr, stdout])) from e

    if retval != 0:
        status = _get_status_from_api_result(dom)
        raise error_exception(
            join_multilines([status.message] + list(status.errors))
        )

    digests = {}
    for digest_type in ["all", "nonprivate", "nonreloadable"]:
        xpath_result = cast(
            list[str],
            dom.xpath(
                "./digests/digest[@type=$digest_type]/@hash",
                digest_type=digest_type,
            ),
        )
        digests[digest_type] = xpath_result[0] if xpath_result else None
    if not any(digests.values()):
        raise error_exception(join_multilines([stderr, stdout]))
    return digests


def _validate_stonith_instance_attributes_via_pcmk(
    cmd_runner: CommandRunner,
    agent_name: ResourceAgentName,
    instance_attributes: Mapping[str, str],
) -> tuple[Optional[bool], str]:
    cmd = [
        settings.stonith_admin_exec,
        "--validate",
        "--output-as",
        "xml",
        "--agent",
        agent_name.type,
    ]
    return _handle_instance_attributes_validation_via_pcmk(
        cmd_runner,
        cmd,
        "./validate/command/output",
        instance_attributes,
    )


def _validate_resource_instance_attributes_via_pcmk(
    cmd_runner: CommandRunner,
    agent_name: ResourceAgentName,
    instance_attributes: Mapping[str, str],
) -> tuple[Optional[bool], str]:
    cmd = [
        settings.crm_resource_exec,
        "--validate",
        "--output-as",
        "xml",
        "--class",
        agent_name.standard,
        "--agent",
        agent_name.type,
    ]
    if agent_name.provider:
        cmd.extend(["--provider", agent_name.provider])
    return _handle_instance_attributes_validation_via_pcmk(
        cmd_runner,
        cmd,
        "./resource-agent-action/command/output",
        instance_attributes,
    )


def _handle_instance_attributes_validation_via_pcmk(
    cmd_runner: CommandRunner,
    cmd: StringSequence,
    data_xpath: str,
    instance_attributes: Mapping[str, str],
) -> tuple[Optional[bool], str]:
    full_cmd = list(cmd)
    for key, value in sorted(instance_attributes.items()):
        full_cmd.extend(["--option", f"{key}={value}"])
    stdout, dummy_stderr, return_value = cmd_runner.run(full_cmd)
    try:
        # dom = _get_api_result_dom(stdout)
        dom = xml_fromstring(stdout)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        return None, str(e)
    result = "\n".join(
        "\n".join(
            line.strip() for line in item.text.split("\n") if line.strip()
        )
        for item in dom.iterfind(data_xpath)
        if item.get("source") == "stderr" and item.text
    ).strip()
    return return_value == 0, result


def validate_resource_instance_attributes_via_pcmk(
    cmd_runner: CommandRunner,
    resource_agent_name: ResourceAgentName,
    instance_attributes: Mapping[str, str],
) -> tuple[Optional[bool], str]:
    if resource_agent_name.is_stonith:
        return _validate_stonith_instance_attributes_via_pcmk(
            cmd_runner,
            resource_agent_name,
            instance_attributes,
        )
    return _validate_resource_instance_attributes_via_pcmk(
        cmd_runner,
        resource_agent_name,
        instance_attributes,
    )
