from lxml import etree
import os.path

from pcs import settings
from pcs.common.tools import (
    join_multilines,
    xml_fromstring
)
from pcs.lib import reports
from pcs.lib.cib.tools import get_pacemaker_version_by_which_cib_was_validated
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.state import ClusterState
from pcs.lib.tools import write_tmpfile
from pcs.lib.xml_tools import etree_to_str


__EXITCODE_WAIT_TIMEOUT = 124
__EXITCODE_CIB_SCOPE_VALID_BUT_NOT_PRESENT = 105
__RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD = 100

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
def get_cib_xml_cmd_results(runner, scope=None):
    command = [__exec("cibadmin"), "--local", "--query"]
    if scope:
        command.append("--scope={0}".format(scope))
    stdout, stderr, returncode = runner.run(command)
    return stdout, stderr, returncode

def get_cib_xml(runner, scope=None):
    stdout, stderr, retval = get_cib_xml_cmd_results(runner, scope)
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
    return xml_fromstring(xml)

def get_cib(xml):
    try:
        return parse_cib_xml(xml)
    except (etree.XMLSyntaxError, etree.DocumentInvalid) as e:
        raise LibraryError(reports.cib_load_error_invalid_format(str(e)))

def verify(runner, verbose=False):
    crm_verify_cmd = [__exec("crm_verify")]
    if verbose:
        crm_verify_cmd.append("-V")

    #With the `crm_verify` command it is not possible simply use the environment
    #variable CIB_file because `crm_verify` simply tries to connect to cib file
    #via tool that can fail because: Update does not conform to the configured
    #schema
    #So we use the explicit flag `--xml-file`.
    cib_tmp_file = runner.env_vars.get("CIB_file", None)
    if cib_tmp_file is None:
        crm_verify_cmd.append("--live-check")
    else:
        crm_verify_cmd.extend(["--xml-file", cib_tmp_file])
    #the tuple (stdout, stderr, returncode) is returned here
    return runner.run(crm_verify_cmd)

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
    return replace_cib_configuration_xml(runner, etree_to_str(tree))

def push_cib_diff_xml(runner, cib_diff_xml):
    cmd = [
        __exec("cibadmin"),
        "--patch",
        "--verbose",
        "--xml-pipe",
    ]
    stdout, stderr, retval = runner.run(cmd, stdin_string=cib_diff_xml)
    if retval != 0:
        raise LibraryError(reports.cib_push_error(stderr, stdout))

def diff_cibs_xml(runner, reporter, cib_old_xml, cib_new_xml):
    """
    Return xml diff of two CIBs
    CommandRunner runner
    string cib_old_xml -- original CIB
    string cib_new_xml -- modified CIB
    """
    try:
        cib_old_tmp_file = write_tmpfile(cib_old_xml)
        reporter.process(
            reports.tmp_file_write(cib_old_tmp_file.name, cib_old_xml)
        )
        cib_new_tmp_file = write_tmpfile(cib_new_xml)
        reporter.process(
            reports.tmp_file_write(cib_new_tmp_file.name, cib_new_xml)
        )
    except EnvironmentError as e:
        raise LibraryError(reports.cib_save_tmp_error(str(e)))
    command = [
        __exec("crm_diff"),
        "--original",
        cib_old_tmp_file.name,
        "--new",
        cib_new_tmp_file.name,
        "--no-version",
    ]
    #  0 (CRM_EX_OK) - success with no difference
    #  1 (CRM_EX_ERROR) - success with difference
    # 64 (CRM_EX_USAGE) - usage error
    # 65 (CRM_EX_DATAERR) - XML fragments not parseable
    stdout, stderr, retval = runner.run(command)
    if retval == 0:
        return ""
    if retval > 1:
        raise LibraryError(
            reports.cib_diff_error(stderr.strip(), cib_old_xml, cib_new_xml)
        )
    return stdout.strip()

def ensure_cib_version(runner, cib, version):
    """
    This method ensures that specified cib is verified by pacemaker with
    version 'version' or newer. If cib doesn't correspond to this version,
    method will try to upgrade cib.
    Returns cib which was verified by pacemaker version 'version' or later.
    Raises LibraryError on any failure.

    CommandRunner runner -- runner
    etree cib -- cib tree
    pcs.common.tools.Version version -- required cib version
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
    # If we are already on the latest schema available, cibadmin exits with 0.
    # That is fine. We do not know here what version is required anyway. The
    # caller knows that and is responsible for dealing with it.
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
    stdout, stderr, retval = runner.run([__exec("crm_node"), "--name"])
    if retval != 0:
        raise LibraryError(
            reports.pacemaker_local_node_name_not_found(
                join_multilines([stderr, stdout])
            )
        )
    return stdout.strip()

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

def remove_node(runner, node_name):
    stdout, stderr, retval = runner.run([
        __exec("crm_node"),
        "--force",
        "--remove",
        node_name,
    ])
    if retval != 0:
        raise LibraryError(
            reports.node_remove_in_pacemaker_failed(
                [node_name],
                reason=join_multilines([stderr, stdout])
            )
        )

### resources

def resource_cleanup(
    runner, resource=None, node=None, operation=None, interval=None
):
    cmd = [__exec("crm_resource"), "--cleanup"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])
    if operation:
        cmd.extend(["--operation", operation])
    if interval:
        cmd.extend(["--interval", interval])

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

def resource_refresh(runner, resource=None, node=None, full=False, force=None):
    if not force and not node and not resource:
        summary = ClusterState(get_cluster_status_xml(runner)).summary
        operations = summary.nodes.attrs.count * summary.resources.attrs.count
        if operations > __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD:
            raise LibraryError(
                reports.resource_refresh_too_time_consuming(
                    __RESOURCE_REFRESH_OPERATION_COUNT_THRESHOLD
                )
            )

    cmd = [__exec("crm_resource"), "--refresh"]
    if resource:
        cmd.extend(["--resource", resource])
    if node:
        cmd.extend(["--node", node])
    if full:
        cmd.extend(["--force"])

    stdout, stderr, retval = runner.run(cmd)

    if retval != 0:
        raise LibraryError(
            reports.resource_refresh_error(
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
