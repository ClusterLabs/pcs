from typing import (
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import (
    ReportItemList,
    ReportItemSeverity,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.node import (
    PacemakerNode,
    get_node_names,
)
from pcs.lib.cib.resource import (
    guest_node,
    remote_node,
)
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync.node import CorosyncNode
from pcs.lib.xml_tools import get_root


def get_existing_nodes_names(
    corosync_conf: Optional[CorosyncConfigFacade] = None,
    cib: Optional[_Element] = None,
    error_on_missing_name: bool = False,
) -> Tuple[List[str], ReportItemList]:
    return __get_nodes_names(
        *__get_nodes(corosync_conf, cib), error_on_missing_name
    )


def get_pacemaker_node_names(cib: _Element) -> Set[str]:
    return get_node_names(cib) | set(get_existing_nodes_names(None, cib)[0])


def get_existing_nodes_names_addrs(
    corosync_conf=None, cib=None, error_on_missing_name=False
) -> tuple[list[str], list[str], ReportItemList]:
    corosync_nodes, remote_and_guest_nodes = __get_nodes(corosync_conf, cib)
    names, report_list = __get_nodes_names(
        corosync_nodes, remote_and_guest_nodes, error_on_missing_name
    )
    return (
        names,
        __get_nodes_addrs(corosync_nodes, remote_and_guest_nodes),
        report_list,
    )


def __get_nodes(
    corosync_conf: Optional[CorosyncConfigFacade] = None,
    cib: Optional[_Element] = None,
) -> Tuple[Iterable[CorosyncNode], Iterable[PacemakerNode]]:
    corosync_nodes = corosync_conf.get_nodes() if corosync_conf else []
    remote_and_guest_nodes: Iterable[PacemakerNode] = []
    if cib is not None:
        cib_root = get_root(cib)
        remote_and_guest_nodes = remote_node.find_node_list(
            cib_root
        ) + guest_node.find_node_list(cib_root)
    return corosync_nodes, remote_and_guest_nodes


def __get_nodes_names(
    corosync_nodes: Iterable[CorosyncNode],
    remote_and_guest_nodes: Iterable[PacemakerNode],
    error_on_missing_name: bool = False,
) -> Tuple[List[str], ReportItemList]:
    report_list: ReportItemList = []
    corosync_names = []
    name_missing_in_corosync = False

    for node in corosync_nodes:
        if node.name:
            corosync_names.append(node.name)
        else:
            name_missing_in_corosync = True

    # Just a generic report for now. It may be expanded to provide more info
    # about each node missing a name later if needed.
    if name_missing_in_corosync:
        report_list.append(
            ReportItem(
                severity=(
                    ReportItemSeverity.error()
                    if error_on_missing_name
                    else ReportItemSeverity.warning()
                ),
                message=reports.messages.CorosyncConfigMissingNamesOfNodes(
                    fatal=error_on_missing_name,
                ),
            )
        )

    return (
        corosync_names + [node.name for node in remote_and_guest_nodes],
        report_list,
    )


def __get_nodes_addrs(
    corosync_nodes: Iterable[CorosyncNode],
    remote_and_guest_nodes: Iterable[PacemakerNode],
) -> list[str]:
    nodes_addrs = [node.addr for node in remote_and_guest_nodes]
    for node in corosync_nodes:
        nodes_addrs += node.addrs_plain()
    return nodes_addrs
