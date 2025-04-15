import contextlib
import os.path
from typing import (
    Iterable,
    List,
    Mapping,
    NamedTuple,
)

from lxml.etree import _Element

from pcs import settings
from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.common.node_communicator import Communicator
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.services.interfaces import ServiceManagerInterface
from pcs.common.status_dto import ResourcesStatusDto
from pcs.common.str_tools import (
    format_list,
    indent,
)
from pcs.common.types import (
    CibRuleInEffectStatus,
    StringSequence,
)
from pcs.lib.booth import status as booth_status
from pcs.lib.booth.env import BoothEnv
from pcs.lib.cib import nvpair
from pcs.lib.cib.constraint.location import get_all_as_dtos
from pcs.lib.cib.resource import stonith
from pcs.lib.cib.rule.in_effect import get_rule_evaluator
from pcs.lib.cib.tools import (
    get_constraints,
    get_crm_config,
    get_resources,
)
from pcs.lib.communication.nodes import CheckReachability
from pcs.lib.communication.tools import run as run_communication
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.node_communication import NodeTargetLibFactory
from pcs.lib.pacemaker.live import (
    BadApiResultFormat,
    get_cib_verification_errors,
    get_cluster_status_text,
    get_cluster_status_xml_raw,
    get_ticket_status_text,
)
from pcs.lib.pacemaker.status import (
    ClusterStatusParser,
    ClusterStatusParsingError,
    cluster_status_parsing_error_to_report,
)
from pcs.lib.resource_agent.const import STONITH_ACTION_REPLACED_BY
from pcs.lib.sbd import get_sbd_service_name


class _ServiceStatus(NamedTuple):
    service: str
    display_always: bool
    enabled: bool
    running: bool


def pacemaker_status_xml(env: LibraryEnvironment) -> str:
    """
    Return pacemaker status in pacemaker-native XML string
    """
    stdout, _, retval = get_cluster_status_xml_raw(env.cmd_runner())
    if retval == 0:
        return stdout
    raise LibraryError(output=stdout)


def resources_status(env: LibraryEnvironment) -> ResourcesStatusDto:
    """
    Return pacemaker status of configured resources as DTO

    env -- LibraryEnvironment
    """
    status_xml = env.get_cluster_state()

    parser = ClusterStatusParser(status_xml)
    try:
        dto = parser.status_xml_to_dto()
    except ClusterStatusParsingError as e:
        raise LibraryError(cluster_status_parsing_error_to_report(e)) from e

    env.report_processor.report_list(parser.get_warnings())

    return dto


def full_cluster_status_plaintext(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    hide_inactive_resources: bool = False,
    verbose: bool = False,
) -> str:
    """
    Return full cluster status as plaintext

    env -- LibraryEnvironment
    hide_inactive_resources -- if True, do not display non-running resources
    verbose -- if True, display more info
    """
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements

    # validation
    if not env.is_cib_live and env.is_corosync_conf_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentNotConsistent(
                    [file_type_codes.CIB],
                    [file_type_codes.COROSYNC_CONF],
                )
            )
        )
    if env.is_cib_live and not env.is_corosync_conf_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentNotConsistent(
                    [file_type_codes.COROSYNC_CONF],
                    [file_type_codes.CIB],
                )
            )
        )

    # initialization
    runner = env.cmd_runner()
    report_processor = env.report_processor
    live = env.is_cib_live and env.is_corosync_conf_live
    is_sbd_running = False

    # load status, cib, corosync.conf
    status_text, warning_list = get_cluster_status_text(
        runner, hide_inactive_resources, verbose
    )
    corosync_conf = None
    # If we are live on a remote node, we have no corosync.conf.
    # TODO Use the new file framework so the path is not exposed.
    if not live or os.path.exists(settings.corosync_conf_file):
        corosync_conf = env.get_corosync_conf()
    cib = env.get_cib()
    # get messages from crm_verify
    crm_verify_messages = []
    try:
        crm_verify_messages = get_cib_verification_errors(runner)
    except BadApiResultFormat as e:
        # do not fail the whole command just because we cannot load this
        report_processor.report(
            reports.ReportItem.debug(
                reports.messages.BadPcmkApiResponseFormat(
                    str(e.original_exception), e.pacemaker_response
                )
            )
        )
    # get extra info for verbose output
    if verbose:
        (
            ticket_status_text,
            ticket_status_stderr,
            ticket_status_retval,
        ) = get_ticket_status_text(runner)
    # get extra info if live
    if live:
        service_manager = env.service_manager
        with contextlib.suppress(LibraryError):
            is_sbd_running = service_manager.is_running(
                get_sbd_service_name(service_manager)
            )
        local_services_status = _get_local_services_status(service_manager)
        if verbose and corosync_conf:
            node_name_list, node_names_report_list = get_existing_nodes_names(
                corosync_conf
            )
            report_processor.report_list(node_names_report_list)
            node_reachability = _get_node_reachability(
                env.get_node_target_factory(),
                env.get_node_communicator(),
                report_processor,
                node_name_list,
            )

    # check stonith configuration
    warning_list = list(warning_list)
    warning_list.extend(_stonith_warnings(cib, is_sbd_running))
    warning_list.extend(
        _move_constraints_warnings(cib, runner, report_processor)
    )
    warning_list.extend(
        _booth_authfile_warning(env.report_processor, env.get_booth_env(None))
    )
    warning_list.extend(crm_verify_messages)

    # put it all together
    if report_processor.has_errors:
        raise LibraryError()

    cluster_name = (
        corosync_conf.get_cluster_name()
        if corosync_conf
        else nvpair.get_value(
            "cluster_property_set", get_crm_config(cib), "cluster-name", ""
        )
    )
    parts = []
    parts.append(f"Cluster name: {cluster_name}")
    if warning_list:
        parts.extend(["", "WARNINGS:"] + warning_list + [""])
    parts.append(status_text)
    if verbose:
        parts.extend(["", "Tickets:"])
        if ticket_status_retval != 0:
            ticket_warning_parts = [
                "WARNING: Unable to get information about tickets"
            ]
            if ticket_status_stderr:
                ticket_warning_parts.extend(
                    indent(ticket_status_stderr.splitlines())
                )
            parts.extend(indent(ticket_warning_parts))
        else:
            parts.extend(indent(ticket_status_text.splitlines()))
    if live:
        if verbose and corosync_conf:
            parts.extend(["", "PCSD Status:"])
            parts.extend(
                indent(
                    _format_node_reachability(node_name_list, node_reachability)
                )
            )
        parts.extend(["", "Daemon Status:"])
        parts.extend(
            indent(_format_local_services_status(local_services_status))
        )
    return "\n".join(parts)


def _stonith_warnings(cib: _Element, is_sbd_running: bool) -> List[str]:
    warning_list = []

    is_stonith_enabled = stonith.is_stonith_enabled(get_crm_config(cib))
    (
        stonith_all,
        stonith_with_action,
        stonith_with_method_cycle,
    ) = stonith.get_misconfigured_resources(get_resources(cib))

    if is_stonith_enabled and not stonith_all and not is_sbd_running:
        warning_list.append(
            "No stonith devices and stonith-enabled is not false"
        )

    if stonith_with_action:
        warning_list.append(
            (
                "Following stonith devices have the 'action' option set, "
                "it is recommended to set {0} instead: {1}"
            ).format(
                format_list(list(STONITH_ACTION_REPLACED_BY)),
                format_list(
                    [str(x.get("id", "")) for x in stonith_with_action]
                ),
            )
        )

    if stonith_with_method_cycle:
        warning_list.append(
            "Following stonith devices have the 'method' option set "
            "to 'cycle' which is potentially dangerous, please consider using "
            "'onoff': {0}".format(
                format_list(
                    [str(x.get("id", "")) for x in stonith_with_method_cycle]
                ),
            )
        )

    return warning_list


def _move_constraints_warnings(
    cib: _Element, runner: CommandRunner, report_processor: ReportProcessor
) -> List[str]:
    warning_list: List[str] = []
    rule_evaluator = get_rule_evaluator(cib, runner, report_processor, True)
    constraint_el = get_constraints(cib)

    location_constraints, _ = get_all_as_dtos(constraint_el, rule_evaluator)

    resource_ids = {
        constraint_dto.resource_id
        for constraint_dto in location_constraints
        if constraint_dto.resource_id
        and constraint_dto.attributes.constraint_id.startswith("cli-")
        and (
            not constraint_dto.attributes.rules
            or not all(
                rule.in_effect == CibRuleInEffectStatus.EXPIRED
                for rule in constraint_dto.attributes.rules
            )
        )
    }

    if resource_ids:
        warning_list.append(
            "Following resources have been moved and their move constraints "
            f"are still in place: {format_list(resource_ids)}"
        )
        warning_list.append(
            "Run 'pcs constraint location' or 'pcs resource clear "
            "<resource id>' to view or remove the constraints, respectively"
        )
    return warning_list


def _booth_authfile_warning(
    report_processor: ReportProcessor, env: BoothEnv
) -> List[str]:
    warning_list: List[str] = []
    report_msg = booth_status.check_authfile_misconfiguration(
        env, report_processor
    )
    if report_msg:
        if isinstance(report_msg, reports.messages.BoothAuthfileNotUsed):
            warning_list.append(
                "Booth is configured to use an authfile, but authfile is not "
                "enabled. Run 'pcs booth enable-authfile --name "
                f"{env.instance_name}' to enable usage of booth autfile."
            )
        elif isinstance(
            report_msg, reports.messages.BoothUnsupportedOptionEnableAuthfile
        ):
            warning_list.append(
                "Unsupported option 'enable-authfile' is set in booth "
                "configuration. Run 'pcs booth enable-booth-clean --name "
                f"{env.instance_name}' to remove the option."
            )
    return warning_list


def _get_local_services_status(
    service_manager: ServiceManagerInterface,
) -> List[_ServiceStatus]:
    service_def = [
        # (service name, display even if not enabled nor running)
        ("corosync", True),
        ("pacemaker", True),
        ("pacemaker_remote", False),
        ("pcsd", True),
        (get_sbd_service_name(service_manager), False),
    ]
    service_status_list = []
    for service, display_always in service_def:
        with contextlib.suppress(LibraryError):
            service_status_list.append(
                _ServiceStatus(
                    service,
                    display_always,
                    service_manager.is_enabled(service),
                    service_manager.is_running(service),
                )
            )
    return service_status_list


def _format_local_services_status(
    service_status_list: Iterable[_ServiceStatus],
) -> List[str]:
    return [
        "{service}: {active}/{enabled}".format(
            service=status.service,
            active=("active" if status.running else "inactive"),
            enabled=("enabled" if status.enabled else "disabled"),
        )
        for status in service_status_list
        if status.display_always or status.enabled or status.running
    ]


def _get_node_reachability(
    node_target_factory: NodeTargetLibFactory,
    node_communicator: Communicator,
    report_processor: ReportProcessor,
    node_name_list: StringSequence,
) -> Mapping[str, str]:
    # we are not interested in reports telling the user which nodes are
    # unknown since we display that info in the list of nodes
    (
        dummy_report_list,
        target_list,
    ) = node_target_factory.get_target_list_with_reports(node_name_list)
    com_cmd = CheckReachability(report_processor)
    com_cmd.set_targets(target_list)
    return run_communication(node_communicator, com_cmd)


def _format_node_reachability(
    node_name_list: StringSequence, node_reachability: Mapping[str, str]
) -> List[str]:
    translate = {
        CheckReachability.REACHABLE: "Online",
        CheckReachability.UNAUTH: "Unable to authenticate",
        CheckReachability.UNREACHABLE: "Offline",
    }
    return [
        "{node}: {status}".format(
            node=node_name,
            status=translate[
                node_reachability.get(node_name, CheckReachability.UNAUTH)
            ],
        )
        for node_name in sorted(node_name_list)
    ]
