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
from pcs.lib.cib.tools import get_pacemaker_version_by_which_cib_was_validated
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ClusterState


__EXITCODE_WAIT_TIMEOUT = 62
__EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT = 6
__RESOURCE_CLEANUP_OPERATION_COUNT_THRESHOLD = 100

class CrmMonErrorException(LibraryError):
    pass


### status

def get_cluster_status_xml(runner):
    stdout, stderr, retval = runner.run(
        [__exec("crm_mon"), "--one-shot", "--as-xml", "--inactive"]
    )
    if retval != 0:
        raise CrmMonErrorException(
            reports.cluster_state_cannot_load(join_multilines([stderr, stdout]))
        )
    return stdout

### cib

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

def parse_cib_xml(xml):
    return etree.fromstring(xml)

def get_cib(xml):
    try:
        return parse_cib_xml(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid):
        raise LibraryError(reports.cib_load_error_invalid_format())

def replace_cib_configuration_xml(runner, xml):
    cmd = [
        __exec("cibadmin"),
        "--replace",
        "--verbose",
        "--xml-pipe",
        "--scope", "configuration",
    ]
    stdout, stderr, retval = runner.run(cmd, stdin_string=xml)
    if retval != 0:
        raise LibraryError(reports.cib_push_error(stderr, stdout))

def replace_cib_configuration(runner, tree):
    #etree returns bytes: b'xml'
    #python 3 removed .encode() from bytes
    #run(...) calls subprocess.Popen.communicate which calls encode...
    #so here is bytes to str conversion
    xml = etree.tostring(tree).decode()
    return replace_cib_configuration_xml(runner, xml)

def ensure_cib_version(runner, cib, version):
    """
    This method ensures that specified cib is verified by pacemaker with
    version 'version' or newer. If cib doesn't correspond to this version,
    method will try to upgrade cib.
    Returns cib which was verified by pacemaker version 'version' or later.
    Raises LibraryError on any failure.

    CommandRunner runner
    etree cib cib tree
    tuple version tuple of integers (<major>, <minor>, <revision>)
    """
    current_version = get_pacemaker_version_by_which_cib_was_validated(cib)
    if current_version >= version:
        return None

    _upgrade_cib(runner)
    new_cib_xml = get_cib_xml(runner)

    try:
        new_cib = parse_cib_xml(new_cib_xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(reports.cib_upgrade_failed(str(e)))

    current_version = get_pacemaker_version_by_which_cib_was_validated(new_cib)
    if current_version >= version:
        return new_cib

    raise LibraryError(reports.unable_to_upgrade_cib_to_required_version(
        current_version, version
    ))

def _upgrade_cib(runner):
    """
    Upgrade CIB to the latest schema available locally or clusterwise.
    CommandRunner runner
    """
    stdout, stderr, retval = runner.run(
        [__exec("cibadmin"), "--upgrade", "--force"]
    )
    if retval != 0:
        raise LibraryError(
            reports.cib_upgrade_failed(join_multilines([stderr, stdout]))
        )

### wait for idle

def has_wait_for_idle_support(runner):
    # returns 1 on success so we don't care about retval
    stdout, stderr, dummy_retval = runner.run(
        [__exec("crm_resource"), "-?"]
    )
    # help goes to stderr but we check stdout as well if that gets changed
    return "--wait" in stderr or "--wait" in stdout

def ensure_wait_for_idle_support(runner):
    if not has_wait_for_idle_support(runner):
        raise LibraryError(reports.wait_for_idle_not_supported())

def wait_for_idle(runner, timeout=None):
    """
    Run waiting command. Raise LibraryError if command failed.

    runner is preconfigured object for running external programs
    string timeout is waiting timeout
    """
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
                reports.wait_for_idle_timed_out(
                    join_multilines([stderr, stdout])
                )
            )
        else:
            raise LibraryError(
                reports.wait_for_idle_error(
                    join_multilines([stderr, stdout])
                )
            )

### nodes

def get_local_node_name(runner):
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

def get_local_node_status(runner):
    try:
        cluster_status = ClusterState(get_cluster_status_xml(runner))
    except CrmMonErrorException:
        return {"offline": True}
    node_name = get_local_node_name(runner)
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

### resources

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

### tools

# shortcut for getting a full path to a pacemaker executable
def __exec(name):
    return os.path.join(settings.pacemaker_binaries, name)

