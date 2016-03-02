from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import utils
import error_codes
from errors import ReportItem
from errors import LibraryError
from library_status_info import ClusterState


def _nodes_standby_unstadby(standby=True, node_list=None, all_nodes=False):
    known_nodes = [
        node.attrs.name
        for node in ClusterState(utils.getClusterStateXml()).node_section.nodes
    ]

    if all_nodes:
        node_list = known_nodes
    elif node_list:
        report = []
        for node in node_list:
            if node not in known_nodes:
                report.append(ReportItem.error(
                    error_codes.NODE_NOT_FOUND,
                    "node '{node}' does not appear to exist in configuration",
                    info={"node": node}
                ))
        if report:
            raise LibraryError(*report)

    # TODO edit CIB directly instead of running commands for each node
    cmd_template = ["crm_standby"]
    cmd_template.extend(["-v", "on"] if standby else ["-D"])
    cmd_list = []
    if node_list:
        for node in node_list:
            cmd_list.append(cmd_template + ["-N", node])
    else:
        cmd_list.append(cmd_template)
    report = []
    for cmd in cmd_list:
        output, retval = utils.run(cmd)
        if retval != 0:
            report.append(ReportItem.error(
                error_codes.COMMON_ERROR,
                output
            ))
    if report:
        raise LibraryError(*report)

def nodes_standby(node_list=None, all_nodes=False):
    return _nodes_standby_unstadby(True, node_list, all_nodes)

def nodes_unstandby(node_list=None, all_nodes=False):
    return _nodes_standby_unstadby(False, node_list, all_nodes)
