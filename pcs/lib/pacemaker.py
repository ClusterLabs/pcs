from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os.path
from lxml import etree

from pcs import settings
from pcs.common.tools import join_multilines
from pcs.lib import reports
from pcs.lib.errors import LibraryError
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
    stdout, stderr, retval = runner.run(
        [__exec("crm_mon"), "--one-shot", "--as-xml", "--inactive"]
    )
    if retval != 0:
        raise CrmMonErrorException(
            reports.cluster_state_cannot_load(join_multilines([stderr, stdout]))
        )
    return stdout

def get_cib_xml(runner, scope=None):
    command = [__exec("cibadmin"), "--local", "--query"]
    if scope:
        command.append("--scope={0}".format(scope))
    stdout, stderr, retval = runner.run(command)
    if retval != 0:
        if retval == __EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT and scope:
            raise LibraryError(
                reports.cib_load_error_scope_missing(
                    scope,
                    join_multilines([stderr, stdout])
                )
            )
        else:
            raise LibraryError(
                reports.cib_load_error(join_multilines([stderr, stdout]))
            )
    return stdout

def get_cib(xml):
    try:
        return etree.fromstring(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid):
        raise LibraryError(reports.cib_load_error_invalid_format())

def replace_cib_configuration_xml(runner, xml, cib_upgraded=False):
    cmd = [__exec("cibadmin"), "--replace",  "--verbose", "--xml-pipe"]
    if not cib_upgraded:
        cmd += ["--scope", "configuration"]
    stdout, stderr, retval = runner.run(cmd, stdin_string=xml)
    if retval != 0:
        raise LibraryError(reports.cib_push_error(stderr, stdout))

def replace_cib_configuration(runner, tree, cib_upgraded=False):
    #etree returns bytes: b'xml'
    #python 3 removed .encode() from bytes
    #run(...) calls subprocess.Popen.communicate which calls encode...
    #so here is bytes to str conversion
    xml = etree.tostring(tree).decode()
    return replace_cib_configuration_xml(runner, xml, cib_upgraded)

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
    raise LibraryError(reports.node_not_found(node_name))

def resource_cleanup(runner, resource=None, node=None, force=False):
    if not force and not node and not resource:
        summary = ClusterState(get_cluster_status_xml(runner)).summary
        operations = summary.nodes.attrs.count * summary.resources.attrs.count
        if operations > __RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD:
            raise LibraryError(
                reports.resource_cleanup_too_time_consuming(
                    __RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD
                )
            )

    cmd = [__exec("crm_resource"), "--cleanup"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])

    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise LibraryError(
            reports.resource_cleanup_error(
                join_multilines([stderr, stdout]),
                resource,
                node
            )
        )
    # usefull output (what has been done) goes to stderr
    return join_multilines([stdout, stderr])

def nodes_standby(runner, node_list=None, all_nodes=False):
    return __nodes_standby_unstandby(runner, True, node_list, all_nodes)

def nodes_unstandby(runner, node_list=None, all_nodes=False):
    return __nodes_standby_unstandby(runner, False, node_list, all_nodes)

def has_resource_wait_support(runner):
    # returns 1 on success so we don't care about retval
    stdout, stderr, dummy_retval = runner.run(
        [__exec("crm_resource"), "-?"]
    )
    # help goes to stderr but we check stdout as well if that gets changed
    return "--wait" in stderr or "--wait" in stdout

def ensure_resource_wait_support(runner):
    if not has_resource_wait_support(runner):
        raise LibraryError(reports.resource_wait_not_supported())

def wait_for_resources(runner, timeout=None):
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
                reports.resource_wait_timed_out(
                    join_multilines([stderr, stdout])
                )
            )
        else:
            raise LibraryError(
                reports.resource_wait_error(
                    join_multilines([stderr, stdout])
                )
            )

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
                    report.append(reports.node_not_found(node))
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
        stdout, stderr, retval = runner.run(cmd)
        if retval != 0:
            report.append(
                reports.common_error(join_multilines([stderr, stdout]))
            )
    if report:
        raise LibraryError(*report)

def __get_local_node_name(runner):
    # It would be possible to run "crm_node --name" to get the name in one call,
    # but it returns false names when cluster is not running (or we are on
    # a remote node). Getting node id first is reliable since it fails in those
    # cases.
    stdout, dummy_stderr, retval = runner.run(
        [__exec("crm_node"), "--cluster-id"]
    )
    if retval != 0:
        raise LibraryError(
            reports.pacemaker_local_node_name_not_found("node id not found")
        )
    node_id = stdout.strip()

    stdout, dummy_stderr, retval = runner.run(
        [__exec("crm_node"), "--name-for-id={0}".format(node_id)]
    )
    if retval != 0:
        raise LibraryError(
            reports.pacemaker_local_node_name_not_found("node name not found")
        )
    node_name = stdout.strip()

    if node_name == "(null)":
        raise LibraryError(
            reports.pacemaker_local_node_name_not_found("node name is null")
        )
    return node_name
