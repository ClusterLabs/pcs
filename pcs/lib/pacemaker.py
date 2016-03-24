from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
from lxml import etree

from pcs import settings
from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem
from pcs.lib.pacemaker_state import ClusterState


__EXITCODE_WAIT_TIMEOUT = 62
__EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT = 6
__RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD = 100

class CrmMonErrorException(LibraryError):
    pass

# syntactic sugar for getting a full path to a pacemaker executable
def __exec(name):
    return os.path.join(settings.pacemaker_binaries, name)

def get_cluster_status_xml(runner):
    output, retval = runner.run(
        [__exec("crm_mon"), "--one-shot", "--as-xml", "--inactive"]
    )
    if retval != 0:
        raise CrmMonErrorException(ReportItem.error(
            error_codes.CRM_MON_ERROR,
            "error running crm_mon, is pacemaker running?",
            info={
                "external_exitcode": retval,
                "external_output": output,
            }
        ))
    return output

def get_cib_xml(runner, scope=None):
    command = [__exec("cibadmin"), "--local", "--query"]
    if scope:
        command.append("--scope={0}".format(scope))
    output, retval = runner.run(command)
    if retval != 0:
        if retval == __EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT and scope:
            raise LibraryError(ReportItem.error(
                error_codes.CIB_LOAD_ERROR_SCOPE_MISSING,
                "unable to get cib, scope '{scope}' not present in cib",
                info={
                    "scope": scope,
                    "external_exitcode": retval,
                    "external_output": output,
                }
            ))
        else:
            raise LibraryError(ReportItem.error(
                error_codes.CIB_LOAD_ERROR,
                "unable to get cib",
                info={
                    "external_exitcode": retval,
                    "external_output": output,
                }
            ))
    return output

def get_cib(xml):
    try:
        return etree.fromstring(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid):
        raise LibraryError(ReportItem.error(
            error_codes.CIB_LOAD_ERROR_BAD_FORMAT,
            "unable to get cib"
        ))

def replace_cib_configuration(runner, tree):
    #etree returns bytes: b'xml'
    #python 3 removed .encode() from bytes
    #run(...) calls subprocess.Popen.communicate which calls encode...
    #so here is bytes to str conversion
    xml = etree.tostring(tree).decode()
    output, retval = runner.run(
        [
            __exec("cibadmin"),
            "--replace", "--scope", "configuration", "--verbose", "--xml-pipe"
        ],
        stdin_string=xml
    )
    if retval != 0:
        raise LibraryError(ReportItem.error(
            error_codes.CIB_PUSH_ERROR,
            "Unable to update cib\n{external_output}",
            info={
                "external_exitcode": retval,
                "external_output": output,
            }
        ))

def get_local_node_status(runner):
    try:
        cluster_status = ClusterState(get_cluster_status_xml(runner))
    except CrmMonErrorException:
        return {"offline": True}
    node_name = __get_local_node_name(runner)
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

def resource_cleanup(runner, resource=None, node=None, force=False):
    if not force and not node and not resource:
        summary = ClusterState(get_cluster_status_xml(runner)).summary
        operations = summary.nodes.attrs.count * summary.resources.attrs.count
        if operations > __RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD:
            raise LibraryError(ReportItem.error(
                error_codes.RESOURCE_CLEANUP_TOO_TIME_CONSUMING,
                "Cleaning up all resources on all nodes will execute more "
                    + "than {threshold} operations in the cluster, which may "
                    + "negatively impact the responsiveness of the cluster. "
                    + "Consider specifying resource and/or node"
                ,
                info={"threshold":__RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD},
                forceable=True
            ))

    cmd = [__exec("crm_resource"), "--cleanup"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])

    output, retval = runner.run(cmd)

    if retval != 0:
        if resource is not None:
            text = "Unable to cleanup resource: {resource}\n{external_output}"
        else:
            text = (
                "Unexpected error occured. 'crm_resource -C' err_code: "
                + "{external_exitcode}\n{external_output}"
            )
        raise LibraryError(ReportItem.error(
            error_codes.RESOURCE_CLEANUP_ERROR,
            text,
            info={
                "external_exitcode": retval,
                "external_output": output,
                "resource": resource,
                "node": node,
            }
        ))
    return output

def nodes_standby(runner, node_list=None, all_nodes=False):
    return __nodes_standby_unstandby(runner, True, node_list, all_nodes)

def nodes_unstandby(runner, node_list=None, all_nodes=False):
    return __nodes_standby_unstandby(runner, False, node_list, all_nodes)

def has_resource_wait_support(runner):
    # returns 1 on success so we don't care about retval
    output, dummy_retval = runner.run([__exec("crm_resource"), "-?"])
    return "--wait" in output

def ensure_resource_wait_support(runner):
    if not has_resource_wait_support(runner):
        raise LibraryError(ReportItem.error(
            error_codes.RESOURCE_WAIT_NOT_SUPPORTED,
            "crm_resource does not support --wait, please upgrade pacemaker"
        ))

def wait_for_resources(runner, timeout=None):
    args = [__exec("crm_resource"), "--wait"]
    if timeout is not None:
        args.append("--timeout={0}".format(timeout))
    output, retval = runner.run(args)
    if retval != 0:
        if retval == __EXITCODE_WAIT_TIMEOUT:
            raise LibraryError(ReportItem.error(
                error_codes.RESOURCE_WAIT_TIMED_OUT,
                "waiting timeout\n\n{external_output}",
                info={
                    "external_exitcode": retval,
                    "external_output": output.strip(),
                }
            ))
        else:
            raise LibraryError(ReportItem.error(
                error_codes.RESOURCE_WAIT_ERROR,
                "{external_output}",
                info={
                    "external_exitcode": retval,
                    "external_output": output.strip(),
                }
            ))

def __nodes_standby_unstandby(
    runner, standby=True, node_list=None, all_nodes=False
):
    if node_list or all_nodes:
        # TODO once we switch to editing CIB instead of running crm_stanby, we
        # cannot always relly on getClusterState. If we're not editing a CIB
        # from a live cluster, there is no status.
        state = ClusterState(get_cluster_status_xml(runner)).node_section.nodes
        known_nodes = [node.attrs.name for node in state]

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
    cmd_template = [__exec("crm_standby")]
    cmd_template.extend(["-v", "on"] if standby else ["-D"])
    cmd_list = []
    if node_list:
        for node in node_list:
            cmd_list.append(cmd_template + ["-N", node])
    else:
        cmd_list.append(cmd_template)
    report = []
    for cmd in cmd_list:
        output, retval = runner.run(cmd)
        if retval != 0:
            report.append(ReportItem.error(
                error_codes.COMMON_ERROR,
                output
            ))
    if report:
        raise LibraryError(*report)

def __get_local_node_name(runner):
    def __get_error(reason):
        return ReportItem.error(
            error_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
            "unable to get local node name from pacemaker: {reason}",
            info={"reason": reason}
        )

    # It would be possible to run "crm_node --name" to get the name in one call,
    # but it returns false names when cluster is not running (or we are on
    # a remote node). Getting node id first is reliable since it fails in those
    # cases.
    output, retval = runner.run([__exec("crm_node"), "--cluster-id"])
    if retval != 0:
        raise LibraryError(__get_error("node id not found"))
    node_id = output.strip()

    output, retval = runner.run(
        [__exec("crm_node"), "--name-for-id={0}".format(node_id)]
    )
    if retval != 0:
        raise LibraryError(__get_error("node name not found"))
    node_name = output.strip()

    if node_name == "(null)":
        raise LibraryError(__get_error("node name is null"))
    return node_name
