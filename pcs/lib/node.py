from typing import (
    Iterable,
    Optional,
    Tuple,
)
from xml.etree.ElementTree import Element

from pcs.lib import reports
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.cib.resource import remote_node, guest_node
from pcs.lib.corosync.config_facade import ConfigFacade as CorosyncConfigFacade
from pcs.lib.corosync.node import CorosyncNode
from pcs.lib.errors import ReportItemList
from pcs.lib.xml_tools import get_root


def get_existing_nodes_names(
    corosync_conf: Optional[CorosyncConfigFacade] = None,
    cib: Optional[Element] = None,
    error_on_missing_name: bool = False
) -> Tuple[Iterable[str], ReportItemList]:
    return __get_nodes_names(
        *__get_nodes(corosync_conf, cib),
        error_on_missing_name
    )

def get_existing_nodes_names_addrs(
    corosync_conf=None, cib=None, error_on_missing_name=False
):
    corosync_nodes, remote_and_guest_nodes = __get_nodes(corosync_conf, cib)
    names, report_list = __get_nodes_names(
        corosync_nodes, remote_and_guest_nodes, error_on_missing_name
    )
    return (
        names,
        __get_nodes_addrs(corosync_nodes, remote_and_guest_nodes),
        report_list
    )

def __get_nodes(
    corosync_conf: Optional[CorosyncConfigFacade] = None,
    cib: Optional[Element] = None
) -> Tuple[Iterable[CorosyncNode], Iterable[PacemakerNode]]:
    corosync_nodes = corosync_conf.get_nodes() if corosync_conf else []
    remote_and_guest_nodes: Iterable[PacemakerNode] = []
    if cib is not None:
        cib_root = get_root(cib)
        remote_and_guest_nodes = (
            remote_node.find_node_list(cib_root)
            +
            guest_node.find_node_list(cib_root)
        )
    return corosync_nodes, remote_and_guest_nodes

def __get_nodes_names(
    corosync_nodes: Iterable[CorosyncNode],
    remote_and_guest_nodes: Iterable[PacemakerNode],
    error_on_missing_name: bool = False
) -> Tuple[Iterable[str], ReportItemList]:
    report_list = []
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
            reports.corosync_config_missing_names_of_nodes(
                fatal=error_on_missing_name
            )
        )

    return (
        corosync_names + [node.name for node in remote_and_guest_nodes],
        report_list
    )

def __get_nodes_addrs(corosync_nodes, remote_and_guest_nodes):
    nodes_addrs = [node.addr for node in remote_and_guest_nodes]
    for node in corosync_nodes:
        nodes_addrs += node.addrs_plain()
    return nodes_addrs
