from typing import (
    Iterable,
    List,
    Mapping,
    NamedTuple,
)
from xml.etree.ElementTree import Element

from pcs.common import file_type_codes
from pcs.common.node_communicator import Communicator
from pcs.common.reports import ReportProcessor
from pcs.common.tools import (
    format_list,
    indent,
)
from pcs.lib import reports
from pcs.lib.cib import stonith
from pcs.lib.cib.tools import get_crm_config, get_resources
from pcs.lib.communication.nodes import CheckReachability
from pcs.lib.communication.tools import run as run_communication
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import (
    CommandRunner,
    is_service_enabled,
    is_service_running,
)
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.node_communication import NodeTargetLibFactory
from pcs.lib.pacemaker.live import (
    get_cluster_status_text,
    get_ticket_status_text,
)
from pcs.lib.resource_agent import STONITH_ACTION_REPLACED_BY
from pcs.lib.sbd import get_sbd_service_name

class _ServiceStatus(NamedTuple):
    service: str
    display_always: bool
    enabled: bool
    running: bool

def full_cluster_status_plaintext(
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

    # validation
    if not env.is_cib_live and env.is_corosync_conf_live:
        raise LibraryError(
            reports.live_environment_not_consistent(
                [file_type_codes.CIB],
                [file_type_codes.COROSYNC_CONF],
            )
        )
    if env.is_cib_live and not env.is_corosync_conf_live:
        raise LibraryError(
            reports.live_environment_not_consistent(
                [file_type_codes.COROSYNC_CONF],
                [file_type_codes.CIB],
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
    corosync_conf = env.get_corosync_conf()
    cib = env.get_cib()
    if verbose:
        ticket_status_text, ticket_status_stderr, ticket_status_retval = (
            get_ticket_status_text(runner)
        )
    # get extra info if live
    if live:
        try:
            is_sbd_running = is_service_running(runner, get_sbd_service_name())
        except LibraryError:
            pass
        local_services_status = _get_local_services_status(runner)
        if verbose:
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

    # put it all together
    if report_processor.has_errors:
        raise LibraryError()

    parts = []
    parts.append(f"Cluster name: {corosync_conf.get_cluster_name()}")
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
        if verbose:
            parts.extend(["", "PCSD Status:"])
            parts.extend(indent(
                _format_node_reachability(node_name_list, node_reachability)
            ))
        parts.extend(["", "Daemon Status:"])
        parts.extend(indent(
            _format_local_services_status(local_services_status)
        ))
    return "\n".join(parts)

def _stonith_warnings(
    cib: Element,
    is_sbd_running: bool
) -> List[str]:
    warning_list = []

    is_stonith_enabled = stonith.is_stonith_enabled(get_crm_config(cib))
    stonith_all, stonith_with_action, stonith_with_method_cycle = (
        stonith.get_misconfigured_resources(get_resources(cib))
    )

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
                format_list(STONITH_ACTION_REPLACED_BY),
                format_list([x.get("id", "") for x in stonith_with_action]),
            )
        )

    if stonith_with_method_cycle:
        warning_list.append(
            "Following stonith devices have the 'method' option set "
            "to 'cycle' which is potentially dangerous, please consider using "
            "'onoff': {0}".format(
                format_list([
                    x.get("id", "") for x in stonith_with_method_cycle
                ]),
            )
        )

    return warning_list

def _get_local_services_status(
    runner: CommandRunner
) -> List[_ServiceStatus]:
    service_def = [
        # (service name, display even if not enabled nor running)
        ("corosync", True),
        ("pacemaker", True),
        ("pacemaker_remote", False),
        ("pcsd", True),
        (get_sbd_service_name(), False),
    ]
    service_status_list = []
    for service, display_always in service_def:
        try:
            service_status_list.append(_ServiceStatus(
                service,
                display_always,
                is_service_enabled(runner, service),
                is_service_running(runner, service),
            ))
        except LibraryError:
            pass
    return service_status_list

def _format_local_services_status(
    service_status_list: Iterable[_ServiceStatus],
) -> List[str]:
    return [
        "{service}: {active}/{enabled}".format(
            service=status.service,
            active=("active" if status.running else "inactive"),
            enabled=("enabled" if status.enabled else "disabled")
        )
        for status in service_status_list
        if status.display_always or status.enabled or status.running
    ]

def _get_node_reachability(
    node_target_factory: NodeTargetLibFactory,
    node_communicator: Communicator,
    report_processor: ReportProcessor,
    node_name_list: Iterable[str],
) -> Mapping[str, str]:
    # we are not interested in reports telling the user which nodes are
    # unknown since we display that info in the list of nodes
    dummy_report_list, target_list = (
        node_target_factory.get_target_list_with_reports(node_name_list)
    )
    com_cmd = CheckReachability(report_processor)
    com_cmd.set_targets(target_list)
    return run_communication(node_communicator, com_cmd)

def _format_node_reachability(
    node_name_list: Iterable[str],
    node_reachability: Mapping[str, str]
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
            ]
        )
        for node_name in sorted(node_name_list)
    ]
