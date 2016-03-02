from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import utils
import error_codes
from errors import ReportItem
from errors import LibraryError
from library_status_info import ClusterState


_PACEMAKER_WAIT_TIMEOUT_STATUS = 62

def nodes_standby(node_list=None, all_nodes=False):
    return _nodes_standby_unstandby(True, node_list, all_nodes)

def nodes_unstandby(node_list=None, all_nodes=False):
    return _nodes_standby_unstandby(False, node_list, all_nodes)

def get_valid_timeout_seconds(timeout_candidate):
    if not _has_resource_wait_support():
        raise LibraryError(ReportItem.error(
            error_codes.RESOURCE_WAIT_NOT_SUPPORTED,
            "crm_resource does not support --wait, please upgrade pacemaker"
        ))

    if timeout_candidate is None:
        return None

    wait_timeout = _get_timeout_seconds(timeout_candidate)
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
        if retval == _PACEMAKER_WAIT_TIMEOUT_STATUS:
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

def _has_resource_wait_support():
    # returns 1 on success so we don't care about retval
    output, dummy_retval = utils.run(["crm_resource", "-?"])
    return "--wait" in output

def _get_timeout_seconds(timeout, return_unknown=False):
    if timeout.isdigit():
        return int(timeout)
    suffix_multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
    }
    for suffix, multiplier in suffix_multiplier.items():
        if timeout.endswith(suffix) and timeout[:-len(suffix)].isdigit():
            return int(timeout[:-len(suffix)]) * multiplier
    return timeout if return_unknown else None
