from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import utils
import error_codes
from errors import ReportItem
from errors import LibraryError
from library_status_info import ClusterState


__PACEMAKER_EXIT_CODE_WAIT_TIMEOUT = 62

class PacemakerException(Exception):
    pass

class PacemakerNotRunningException(PacemakerException):
    pass

def get_cluster_status_xml():
    output, retval = utils.run(
        ["crm_mon", "--one-shot", "--as-xml", "--inactive"]
    )
    if retval != 0:
        raise PacemakerNotRunningException()
    return output

def get_local_node_status():
    try:
        cluster_status = ClusterState(get_cluster_status_xml())
    except PacemakerNotRunningException:
        return {"offline": True}
    node_name = __get_local_node_name()
    for node_status in cluster_status.node_section.nodes:
        if node_status.attrs.name == node_name:
            result = {
                "offline": False,
            }
            for attr in (
                'id', 'name', 'type', 'online', 'standby', 'standby_onfail',
                'maintenance', 'pending', 'unclean', 'shutdown', 'expected_up',
                'is_dc', 'resources_running',
            ):
                result[attr] = getattr(node_status.attrs, attr)
            return result
    raise LibraryError(ReportItem.error(
        error_codes.NODE_NOT_FOUND,
        "node '{node}' does not appear to exist in configuration",
        info={"node": node_name}
    ))

def nodes_standby(node_list=None, all_nodes=False):
    return _nodes_standby_unstandby(True, node_list, all_nodes)

def nodes_unstandby(node_list=None, all_nodes=False):
    return _nodes_standby_unstandby(False, node_list, all_nodes)

def get_valid_timeout_seconds(timeout_candidate):
    if not utils._has_resource_wait_support():
        raise LibraryError(ReportItem.error(
            error_codes.RESOURCE_WAIT_NOT_SUPPORTED,
            "crm_resource does not support --wait, please upgrade pacemaker"
        ))

    if timeout_candidate is None:
        return None

    wait_timeout = utils.get_timeout_seconds(timeout_candidate)
    if wait_timeout is None:
        raise LibraryError(ReportItem.error(
            error_codes.INVALID_TIMEOUT_VALUE,
            "'{timeout}' is not a valid number of seconds to wait",
            info={"timeout": timeout_candidate}
        ))
    return wait_timeout

def wait_for_resources(timeout=None):
    args = ["crm_resource", "--wait"]
    if timeout is not None:
        args.append("--timeout={0}".format(timeout))
    output, retval = utils.run(args)
    if retval != 0:
        if retval == __PACEMAKER_EXIT_CODE_WAIT_TIMEOUT:
            raise LibraryError(ReportItem.error(
                error_codes.RESOURCE_WAIT_TIMED_OUT,
                "waiting timeout\n\n{details}",
                info={"details": output.strip()}
            ))
        else:
            raise LibraryError(ReportItem.error(
                error_codes.RESOURCE_WAIT_ERROR,
                "{details}",
                info={"details": output.strip()}
            ))

def _nodes_standby_unstandby(standby=True, node_list=None, all_nodes=False):
    # TODO once we switch to editing CIB instead of running crm_stanby, we
    # cannot always relly on getClusterState. If we're not editing a CIB from
    # a live cluster, there is no status.
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

    # TODO Edit CIB directly instead of running commands for each node; be aware
    # remote nodes might not be in the CIB yet so we need to put them there.
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

def __get_local_node_name():
    def __get_error(reason):
        ReportItem.error(
            error_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
            "unable to get local node name from pacemaker: {reason}",
            info={"reason": reason}
        )

    # It would be possible to run "crm_node --name" to get the name in one call,
    # but it returns false names when cluster is not running (or we are on
    # a remote node). Getting node id first is reliable since it fails in those
    # cases.
    output, retval = utils.run(["crm_node", "--cluster-id"])
    if retval != 0:
        raise LibraryError(__get_error("node id not found"))
    node_id = output.strip()

    output, retval = utils.run(
        ["crm_node", "--name-for-id={0}".format(node_id)]
    )
    if retval != 0:
        raise LibraryError(__get_error("node name not found"))
    node_name = output.strip()

    if node_name == "(null)":
        raise LibraryError(__get_error("node name is null"))
    return node_name
