from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import Iterable

from pcs.common import report_codes
from pcs.lib.errors import ReportItem, ReportItemSeverity


def common_error(text):
    # TODO replace by more specific reports
    """
    unspecified error with text message, do not use unless absolutely necessary
    """
    return ReportItem.error(
        report_codes.COMMON_ERROR,
        "{text}",
        info={"text": text}
    )

def common_info(text):
    # TODO replace by more specific reports
    """
    unspecified info with text message, do not use unless absolutely necessary
    """
    return ReportItem.info(
        report_codes.COMMON_INFO,
        "{text}",
        info={"text": text}
    )

def resource_for_constraint_is_multiinstance(
    resource_id, parent_type, parent_id,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    when setting up a constraint a resource in a clone or a master was specified
    resource_id string specified resource
    parent_type string "clone" or "master"
    parent_id clone or master resource id
    severity report item severity
    forceable is this report item forceable? by what cathegory?
    """
    template = (
        "{resource_id} is a clone resource, you should use the"
        + " clone id: {parent_id} when adding constraints"
    )
    if parent_type == "master":
        template = (
            "{resource_id} is a master/slave resource, you should use the"
            + " master id: {parent_id} when adding constraints"
        )

    return ReportItem(
        report_codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
        severity,
        template,
        info={
            "resource_id": resource_id,
            "parent_type": parent_type,
            "parent_id": parent_id,
        },
        forceable=forceable
    )

def duplicate_constraints_exist(
    constraint_type, constraint_info_list,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    when creating a constraint it was detected the constraint already exists
    constraint_type string "rsc_colocation", "rsc_order", "rsc_ticket"
    constraint_info_list list of structured constraint data according to type
    severity report item severity
    forceable is this report item forceable? by what cathegory?
    """
    return ReportItem(
        report_codes.DUPLICATE_CONSTRAINTS_EXIST,
        severity,
        "duplicate constraint already exists",
        info={
            "constraint_type": constraint_type,
            "constraint_info_list": constraint_info_list,
        },
        forceable=forceable
    )

def empty_resource_set_list():
    """
    an empty resource set has been specified, which is not allowed by cib schema
    """
    return ReportItem.error(
        report_codes.EMPTY_RESOURCE_SET_LIST,
        "Resource set list is empty",
    )

def required_option_is_missing(name):
    """
    required option has not been specified, command cannot continue
    """
    return ReportItem.error(
        report_codes.REQUIRED_OPTION_IS_MISSING,
        "required option '{option_name}' is missing",
        info={
            "option_name": name
        }
    )

def invalid_option(
    option_name, allowed_options, option_type,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified option name is not valid, usualy an error or a warning
    option_name specified invalid option name
    allowed_options iterable of possible allowed option names
    option_type decsribes the option
    severity report item severity
    forceable is this report item forceable? by what cathegory?
    """
    msg = "invalid option '{option_name}', allowed options are: {allowed_str}"
    info = {
        "option_name": option_name,
        "option_type": option_type,
        "allowed": sorted(allowed_options),
        "allowed_str": ", ".join(sorted(allowed_options)),
    }
    if option_type:
        msg = ("invalid {option_type} option '{option_name}'"
            + ", allowed options are: {allowed_str}")
    return ReportItem(
        report_codes.INVALID_OPTION, severity, msg, forceable, info
    )

def invalid_option_value(
    option_name, option_value, allowed_values,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified value is not valid for the option, usualy an error or a warning
    option_name specified option name whose value is not valid
    option_value specified value which is not valid
    allowed_options list of allowed values or string description
    severity report item severity
    forceable is this report item forceable? by what cathegory?
    """
    allowed_iterable = (
        isinstance(allowed_values, Iterable)
        and
        not isinstance(allowed_values, "".__class__)
    )
    allowed_str = (", ".join(allowed_values) if allowed_iterable
        else allowed_values)
    return ReportItem(
        report_codes.INVALID_OPTION_VALUE,
        severity,
        "'{option_value}' is not a valid {option_name} value"
            + ", use {allowed_values_str}",
        info={
            "option_value": option_value,
            "option_name": option_name,
            "allowed_values": allowed_values,
            "allowed_values_str": allowed_str,
        },
        forceable=forceable
    )

def invalid_id_is_empty(id, id_description):
    """
    empty string was specified as an id, which is not valid
    id string specified id
    id_description string decribe id's role
    """
    return ReportItem.error(
        report_codes.INVALID_ID,
        "{id_description} cannot be empty",
        info={
            "id": id,
            "id_description": id_description,
            "reason": "empty",
        }
    )

def invalid_id_bad_char(id, id_description, bad_char, is_first_char):
    """
    specified id is not valid as it contains a forbidden character
    id string specified id
    id_description string decribe id's role
    bad_char forbidden character
    is_first_char is it the first character which is forbidden?
    """
    return ReportItem.error(
        report_codes.INVALID_ID,
        (
            "invalid {{id_description}} '{{id}}', '{{invalid_character}}' "
            + "is not a valid{0}character for a {{id_description}}"
        ).format(" first " if is_first_char else " "),
        info={
            "id": id,
            "id_description": id_description,
            "reason": "invalid{0}character".format(
                " first " if is_first_char else " "
            ),
            "invalid_character": bad_char,
        }
    )

def invalid_timeout(timeout):
    """
    specified timeout is not valid (number or other format e.g. 2min)
    timeout string specified invalid timeout
    """
    return ReportItem.error(
        report_codes.INVALID_TIMEOUT_VALUE,
        "'{timeout}' is not a valid number of seconds to wait",
        info={"timeout": timeout}
    )

def invalid_score(score):
    """
    specified score value is not valid
    score specified score value
    """
    return ReportItem.error(
        report_codes.INVALID_SCORE,
        "invalid score '{score}', use integer or INFINITY or -INFINITY",
        info={
            "score": score,
        }
    )

def multiple_score_options():
    """
    more than one of mutually exclusive score options has been set
    (score, score-attribute, score-attribute-mangle in rules or colocation sets)
    """
    return ReportItem.error(
        report_codes.MULTIPLE_SCORE_OPTIONS,
        "you cannot specify multiple score options",
    )

def run_external_process_started(command, stdin):
    """
    information about running an external process
    command string the external process command
    stdin string passed to the external process via its stdin
    """
    msg = "Running: {command}"
    if stdin:
        msg += "\n--Debug Input Start--\n{stdin}\n--Debug Input End--"
    msg += "\n"
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_STARTED,
        msg,
        info={
            "command": command,
            "stdin": stdin,
        }
    )

def run_external_process_finished(command, retval, stdout):
    """
    information about result of running an external process
    command string the external process command
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
        "Finished running: {command}\nReturn value: {return_value}"
        + "\n--Debug Output Start--\n{stdout}\n--Debug Output End--\n",
        info={
            "command": command,
            "return_value": retval,
            "stdout": stdout,
        }
    )

def run_external_process_error(command, reason):
    """
    attempt to run an external process failed
    command string the external process command
    reason string error description
    """
    return ReportItem.error(
        report_codes.RUN_EXTERNAL_PROCESS_ERROR,
        "unable to run command {command}: {reason}",
        info={
            "command": command,
            "reason": reason
        }
    )

def node_communication_started(target, data):
    """
    request is about to be sent to a remote node, debug info
    target string where the request is about to be sent to
    data string request's data
    """
    msg = "Sending HTTP Request to: {target}"
    if data:
        msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
    msg += "\n"
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_STARTED,
        msg,
        info={
            "target": target,
            "data": data,
        }
    )

def node_communication_finished(target, retval, data):
    """
    remote node request has been finished, debug info
    target string where the request was sent to
    retval response return code
    data response data
    """
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_FINISHED,
        "Finished calling: {target}\nResponse Code: {response_code}"
        + "\n--Debug Response Start--\n{response_data}\n--Debug Response End--"
        + "\n",
        info={
            "target": target,
            "response_code": retval,
            "response_data": data
        }
    )

def node_communication_not_connected(node, reason):
    """
    an error occured when connecting to a remote node, debug info
    node string node address / name
    reason string decription of the error
    """
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
        "Unable to connect to {node} ({reason})",
        info={
            "node": node,
            "reason": reason,
        }
    )

def node_communication_error_not_authorized(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    node rejected a request as we are not authorized
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED,
        severity,
        "Unable to authenticate to {node} ({reason}), try running 'pcs cluster auth'",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def node_communication_error_permission_denied(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    node rejected a request as we do not have permissions to run the request
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED,
        severity,
        "{node}: Permission denied ({reason})",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def node_communication_error_unsupported_command(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    node rejected a request as it does not support the request
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND,
        severity,
        "{node}: Unsupported command ({reason}), try upgrading pcsd",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def node_communication_command_unsuccessful(node, command, reason):
    """
    node rejected a request for another reason with a plain text explanation
    node string node address / name
    reason string decription of the error
    """
    return ReportItem.error(
        report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
        "{node}: {reason}",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        }
    )

def node_communication_error_other_error(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    node rejected a request for another reason (may be faulty node)
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR,
        severity,
        "Error connecting to {node} ({reason})",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def node_communication_error_unable_to_connect(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    we were unable to connect to a node
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
        severity,
        "Unable to connect to {node} ({reason})",
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def corosync_config_distribution_started():
    """
    corosync configuration is about to be sent to nodes
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
        "Sending updated corosync.conf to nodes..."
    )

def corosync_config_accepted_by_node(node):
    """
    corosync configuration has been accepted by a node
    node string node address / name
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
        "{node}: Succeeded",
        info={"node": node}
    )

def corosync_config_distribution_node_error(
    node,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    communication error occured when saving corosync configuration to a node
    node string faulty node address / name
    """
    return ReportItem(
        report_codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR,
        severity,
        "{node}: Unable to set corosync config",
        info={"node": node},
        forceable=forceable
    )

def corosync_not_running_check_started():
    """
    we are about to make sure corosync is not running on nodes
    """
    return ReportItem.info(
        report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED,
        "Checking corosync is not running on nodes..."
    )

def corosync_not_running_check_node_error(
    node,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    communication error occured when checking corosync is not running on a node
    node string faulty node address / name
    """
    return ReportItem(
        report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
        severity,
        "{node}: Unable to check if corosync is not running",
        info={"node": node},
        forceable=forceable
    )

def corosync_not_running_on_node_ok(node):
    """
    corosync is not running on a node, which is ok
    node string node address / name
    """
    return ReportItem.info(
        report_codes.COROSYNC_NOT_RUNNING_ON_NODE,
        "{node}: corosync is not running",
        info={"node": node}
    )

def corosync_running_on_node_fail(node):
    """
    corosync is running on a node, which is not ok
    node string node address / name
    """
    return ReportItem.error(
        report_codes.COROSYNC_RUNNING_ON_NODE,
        "{node}: corosync is running",
        info={"node": node}
    )

def corosync_config_reloaded():
    """
    corosync configuration has been reloaded
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_RELOADED,
        "Corosync configuration reloaded"
    )

def corosync_config_reload_error(reason):
    """
    an error occured when reloading corosync configuration
    reason string an error message
    """
    return ReportItem.error(
        report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
        "Unable to reload corosync configuration: {reason}",
        info={"reason": reason}
    )

def corosync_config_read_error(path, reason):
    """
    an error occured when reading corosync configuration file from disk
    reason string an error message
    """
    return ReportItem.error(
        report_codes.UNABLE_TO_READ_COROSYNC_CONFIG,
        "Unable to read {path}: {reason}",
        info={
            "path": path,
            "reason": reason,
        }
    )

def corosync_config_parser_missing_closing_brace():
    """
    corosync config cannot be parsed due to missing closing brace
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
        "Unable to parse corosync config: missing closing brace"
    )

def corosync_config_parser_unexpected_closing_brace():
    """
    corosync config cannot be parsed due to unexpected closing brace
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
        "Unable to parse corosync config: unexpected closing brace"
    )

def corosync_config_parser_other_error():
    """
    corosync config cannot be parsed, the cause is not specified
    It is better to use more specific error if possible.
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF,
        "Unable to parse corosync config"
    )

def qdevice_already_defined():
    """
    qdevice is already set up in a cluster, when it was expected not to be
    """
    return ReportItem.error(
        report_codes.QDEVICE_ALREADY_DEFINED,
        "quorum device is already defined"
    )

def qdevice_not_defined():
    """
    qdevice is not set up in a cluster, when it was expected to be
    """
    return ReportItem.error(
        report_codes.QDEVICE_NOT_DEFINED,
        "no quorum device is defined in this cluster"
    )

def qdevice_remove_or_cluster_stop_needed():
    """
    operation cannot be executed, qdevice removal or cluster stop is needed
    """
    return ReportItem.error(
        report_codes.QDEVICE_REMOVE_OR_CLUSTER_STOP_NEEDED,
        "You need to stop the cluster or remove qdevice from cluster to continue"
    )

def qdevice_already_initialized(model):
    """
    cannot create qdevice on local host, it has been already created
    string model qdevice model
    """
    return ReportItem.error(
        report_codes.QDEVICE_ALREADY_INITIALIZED,
        "Quorum device '{model}' has been already initialized",
        info={
            "model": model,
        }
    )

def qdevice_initialization_success(model):
    """
    qdevice was successfully initialized on local host
    string model qdevice model
    """
    return ReportItem.info(
        report_codes.QDEVICE_INITIALIZATION_SUCCESS,
        "Quorum device '{model}' initialized",
        info={
            "model": model,
        }
    )

def qdevice_initialization_error(model, reason):
    """
    an error occured when creating qdevice on local host
    string model qdevice model
    string reason an error message
    """
    return ReportItem.error(
        report_codes.QDEVICE_INITIALIZATION_ERROR,
        "Unable to initialize quorum device '{model}': {reason}",
        info={
            "model": model,
            "reason": reason,
        }
    )

def qdevice_destroy_success(model):
    """
    qdevice configuration successfully removed from local host
    string model qdevice model
    """
    return ReportItem.info(
        report_codes.QDEVICE_DESTROY_SUCCESS,
        "Quorum device '{model}' configuration files removed",
        info={
            "model": model,
        }
    )

def qdevice_destroy_error(model, reason):
    """
    an error occured when removing qdevice configuration from local host
    string model qdevice model
    string reason an error message
    """
    return ReportItem.error(
        report_codes.QDEVICE_DESTROY_ERROR,
        "Unable to destroy quorum device '{model}': {reason}",
        info={
            "model": model,
            "reason": reason,
        }
    )

def cman_unsupported_command():
    """
    requested library command is not available as local cluster is CMAN based
    """
    return ReportItem.error(
        report_codes.CMAN_UNSUPPORTED_COMMAND,
        "This command is not supported on CMAN clusters"
    )

def id_already_exists(id):
    """
    specified id already exists in CIB and cannot be used for a new CIB object
    id string existing id
    """
    return ReportItem.error(
        report_codes.ID_ALREADY_EXISTS,
        "'{id}' already exists",
        info={"id": id}
    )

def id_not_found(id, id_description):
    """
    specified id does not exist in CIB, user referenced a nonexisting id
    use "resource_does_not_exist" if id is a resource id
    id string specified id
    id_description string decribe id's role
    """
    return ReportItem.error(
        report_codes.ID_NOT_FOUND,
        ("{id_description} " if id_description else "") + "'{id}' does not exist",
        info={
            "id": id,
            "id_description": id_description,
        }
    )

def resource_does_not_exist(resource_id):
    """
    specified resource does not exist (e.g. when creating in constraints)
    resource_id string specified resource id
    """
    return ReportItem.error(
        report_codes.RESOURCE_DOES_NOT_EXIST,
        "Resource '{resource_id}' does not exist",
        info={
            "resource_id": resource_id,
        }
    )

def cib_load_error(retval, stdout):
    """
    cannot load cib from cibadmin, cibadmin exited with non-zero code
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR,
        "unable to get cib",
        info={
            "return_value": retval,
            "stdout": stdout,
        }
    )

def cib_load_error_scope_missing(scope, retval, stdout):
    """
    cannot load cib from cibadmin, specified scope is missing in the cib
    scope string requested cib scope
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR_SCOPE_MISSING,
        "unable to get cib, scope '{scope}' not present in cib",
        info={
            "scope": scope,
            "return_value": retval,
            "stdout": stdout,
        }
    )

def cib_load_error_invalid_format():
    """
    cib does not conform to the schema
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
        "unable to get cib, xml does not conform to the schema"
    )

def cib_missing_mandatory_section(section_name):
    """
    CIB is missing a section which is required to be present
    section_name string name of the missing section (element name or path)
    """
    return ReportItem.error(
        report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
        "Unable to get {section} section of cib",
        info={
            "section": section_name,
        }
    )

def cib_push_error(retval, stdout):
    """
    cannot push cib to cibadmin, cibadmin exited with non-zero code
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.CIB_PUSH_ERROR,
        "Unable to update cib\n{stdout}",
        info={
            "return_value": retval,
            "stdout": stdout,
        }
    )

def cluster_state_cannot_load(retval, stdout):
    """
    cannot load cluster status from crm_mon, crm_mon exited with non-zero code
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.CRM_MON_ERROR,
        "error running crm_mon, is pacemaker running?",
        info={
            "return_value": retval,
            "stdout": stdout,
        }
    )

def cluster_state_invalid_format():
    """
    crm_mon xml output does not conform to the schema
    """
    return ReportItem.error(
        report_codes.BAD_CLUSTER_STATE_FORMAT,
        "cannot load cluster status, xml does not conform to the schema"
    )

def resource_wait_not_supported():
    """
    crm_resource does not support --wait
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_NOT_SUPPORTED,
        "crm_resource does not support --wait, please upgrade pacemaker"
    )

def resource_wait_timed_out(retval, stdout):
    """
    waiting for resources (crm_resource --wait) failed, timeout expired
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_TIMED_OUT,
        "waiting timeout\n\n{stdout}",
        info={
            "return_value": retval,
            "stdout": stdout,
        }
    )

def resource_wait_error(retval, stdout):
    """
    waiting for resources (crm_resource --wait) failed
    retval external process's return (exit) code
    stdout string external process's stdout
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_ERROR,
        "{stdout}",
        info={
            "return_value": retval,
            "stdout": stdout,
        }
    )

def resource_cleanup_error(retval, stdout, resource=None, node=None):
    """
    an error occured when deleting resource history in pacemaker
    retval external process's return (exit) code
    stdout string external process's stdout
    resource string resource which has been cleaned up
    node string node which has been cleaned up
    """
    if resource:
        text = "Unable to cleanup resource: {resource}\n{stdout}"
    else:
        text = (
            "Unexpected error occured. 'crm_resource -C' err_code: "
            + "{return_value}\n{stdout}"
        )
    return ReportItem.error(
        report_codes.RESOURCE_CLEANUP_ERROR,
        text,
        info={
            "return_value": retval,
            "stdout": stdout,
            "resource": resource,
            "node": node,
        }
    )

def resource_cleanup_too_time_consuming(threshold):
    """
    resource cleanup will execute more than threshold operations in a cluster
    threshold current threshold for trigerring this error
    """
    return ReportItem.error(
        report_codes.RESOURCE_CLEANUP_TOO_TIME_CONSUMING,
        "Cleaning up all resources on all nodes will execute more "
            + "than {threshold} operations in the cluster, which may "
            + "negatively impact the responsiveness of the cluster. "
            + "Consider specifying resource and/or node"
        ,
        info={"threshold": threshold},
        forceable=report_codes.FORCE_LOAD_THRESHOLD
    )

def node_not_found(node):
    """
    specified node does not exist
    node string specified node
    """
    return ReportItem.error(
        report_codes.NODE_NOT_FOUND,
        "node '{node}' does not appear to exist in configuration",
        info={"node": node}
    )

def pacemaker_local_node_name_not_found(reason):
    """
    we are unable to figure out pacemaker's local node's name
    reason string error message
    """
    return ReportItem.error(
        report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
        "unable to get local node name from pacemaker: {reason}",
        info={"reason": reason}
    )

def rrp_active_not_supported(warning=False):
    """
    active RRP mode is not supported, require user confirmation
    warning set to True if user confirmed he/she wants to proceed
    """
    return ReportItem(
        report_codes.RRP_ACTIVE_NOT_SUPPORTED,
        ReportItemSeverity.WARNING if warning else ReportItemSeverity.ERROR,
        "using a RRP mode of 'active' is not supported or tested",
        forceable=(None if warning else report_codes.FORCE_ACTIVE_RRP)
    )

def cman_ignored_option(option):
    """
    specified option is ignored as CMAN clusters do not support it
    options string option name
    """
    return ReportItem.warning(
        report_codes.IGNORED_CMAN_UNSUPPORTED_OPTION,
        '{option_name} ignored as it is not supported on CMAN clusters',
        info={'option_name': option}
    )

def rrp_addresses_transport_mismatch():
    # TODO this knows too much about cmdline and needs to be fixed once
    # client code is moved to library, probably by CmdLineInputError in cli
    """
    RRP defined by network addresses is not allowed when udp transport is used
    """
    return ReportItem.error(
        report_codes.NON_UDP_TRANSPORT_ADDR_MISMATCH,
        "--addr0 and --addr1 can only be used with --transport=udp"
    )

def cman_udpu_restart_required():
    """
    warn user it is required to restart CMAN cluster for changes to take effect
    """
    return ReportItem.warning(
        report_codes.CMAN_UDPU_RESTART_REQUIRED,
        "Using udpu transport on a CMAN cluster, "
            + "cluster restart is required after node add or remove"
    )

def cman_broadcast_all_rings():
    """
    broadcast enabled in all rings, CMAN doesn't support 1 ring only broadcast
    """
    return ReportItem.warning(
        report_codes.CMAN_BROADCAST_ALL_RINGS,
        "Enabling broadcast for all rings as CMAN does not support "
            + "broadcast in only one ring"
    )

def service_start_started(service):
    """
    system service is being started
    string service service name or description
    """
    return ReportItem.info(
        report_codes.SERVICE_START_STARTED,
        "Starting {service}...",
        info={
            "service": service,
        }
    )

def service_start_error(service, reason):
    """
    system service start failed
    string service service name or description
    string reason error message
    """
    return ReportItem.error(
        report_codes.SERVICE_START_ERROR,
        "Unable to start {service}: {reason}",
        info={
            "service": service,
            "reason": reason,
        }
    )

def service_start_success(service):
    """
    system service was started successfully
    string service service name or description
    """
    return ReportItem.info(
        report_codes.SERVICE_START_SUCCESS,
        "{service} started",
        info={
            "service": service,
        }
    )

def service_stop_started(service):
    """
    system service is being stopped
    string service service name or description
    """
    return ReportItem.info(
        report_codes.SERVICE_STOP_STARTED,
        "Stopping {service}...",
        info={
            "service": service,
        }
    )

def service_stop_error(service, reason):
    """
    system service stop failed
    string service service name or description
    string reason error message
    """
    return ReportItem.error(
        report_codes.SERVICE_STOP_ERROR,
        "Unable to stop {service}: {reason}",
        info={
            "service": service,
            "reason": reason,
        }
    )

def service_stop_success(service):
    """
    system service was stopped successfully
    string service service name or description
    """
    return ReportItem.info(
        report_codes.SERVICE_STOP_SUCCESS,
        "{service} stopped",
        info={
            "service": service,
        }
    )

def service_kill_error(services, reason):
    """
    system services kill failed
    iterable services services name or description
    string reason error message
    """
    return ReportItem.error(
        report_codes.SERVICE_KILL_ERROR,
        "Unable to kill {services_str}: {reason}",
        info={
            "services": services,
            "services_str": ", ".join(services),
            "reason": reason,
        }
    )

def service_kill_success(services):
    """
    system services were killed successfully
    iterable services services name or description
    """
    return ReportItem.info(
        report_codes.SERVICE_KILL_SUCCESS,
        "{services_str} killed",
        info={
            "services": services,
            "services_str": ", ".join(services),
        }
    )

def service_enable_error(service, reason, node=None):
    """
    system service enable failed
    string service service name or description
    string reason error message
    string node node on which service was enabled
    """
    msg = "Unable to enable {service}: {reason}"
    return ReportItem.error(
        report_codes.SERVICE_ENABLE_ERROR,
        msg if node is None else "{node}: " + msg,
        info={
            "service": service,
            "reason": reason,
            "node": node,
        }
    )

def service_enable_success(service, node=None):
    """
    system service was enabled successfully
    string service service name or description
    string node node on which service was enabled
    """
    msg = "{service} enabled"
    return ReportItem.info(
        report_codes.SERVICE_ENABLE_SUCCESS,
        msg if node is None else "{node}: " + msg,
        info={
            "service": service,
            "node": node,
        }
    )

def service_disable_error(service, reason, node=None):
    """
    system service disable failed
    string service service name or description
    string reason error message
    string node node on which service was disabled
    """
    msg = "Unable to disable {service}: {reason}"
    return ReportItem.error(
        report_codes.SERVICE_DISABLE_ERROR,
        msg if node is None else "{node}: " + msg,
        info={
            "service": service,
            "reason": reason,
            "node": node,
        }
    )

def service_disable_success(service, node=None):
    """
    system service was disabled successfully
    string service service name or description
    string node node on which service was disabled
    """
    msg = "{service} disabled"
    return ReportItem.info(
        report_codes.SERVICE_DISABLE_SUCCESS,
        msg if node is None else "{node}: " + msg,
        info={
            "service": service,
            "node": node,
        }
    )


def invalid_metadata_format(severity=ReportItemSeverity.ERROR, forceable=None):
    """
    Invalid format of metadata
    """
    return ReportItem(
        report_codes.INVALID_METADATA_FORMAT,
        severity,
        "Invalid metadata format",
        forceable=forceable
    )


def unable_to_get_agent_metadata(
    agent, reason, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    There were some issues trying to get metadata of agent

    agent -- agent which metadata were unable to obtain
    reason -- reason of failure
    """
    return ReportItem(
        report_codes.UNABLE_TO_GET_AGENT_METADATA,
        severity,
        "Unable to get metadata of '{agent}': {reason}",
        info={
            "agent": agent,
            "reason": reason
        },
        forceable=forceable
    )


def agent_not_found(agent, severity=ReportItemSeverity.ERROR, forceable=None):
    """
    Specified agent doesn't exist

    agent -- name of agent which doesn't exist
    """
    return ReportItem(
        report_codes.AGENT_NOT_FOUND,
        severity,
        "Agent '{agent}' not found",
        info={"agent": agent},
        forceable=forceable
    )


def agent_not_supported(
    agent, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Specified agent is not supported

    agent -- name of agent which is not supported
    """
    return ReportItem(
        report_codes.UNSUPPORTED_AGENT,
        severity,
        "Agent '{agent}' is not supported",
        info={"agent": agent},
        forceable=forceable
    )


def resource_agent_general_error(agent=None):
    """
    General not specific error of resource or fence agent.

    agent -- agent name
    """
    msg = "Unspecified problem of resource/fence agent"
    return ReportItem.error(
        report_codes.AGENT_GENERAL_ERROR,
        msg if agent is None else msg + " '{agent}'",
        info={"agent": agent}
    )


def omitting_node(node):
    """
    warning that specified node will be omitted in following actions

    node -- node name
    """
    return ReportItem.warning(
        report_codes.OMITTING_NODE,
        "Omitting node '{node}'",
        info={"node": node}
    )


def sbd_check_started():
    """
    info that SBD pre-enabling checks started
    """
    return ReportItem.info(
        report_codes.SBD_CHECK_STARTED,
        "Running SBD pre-enabling checks..."
    )


def sbd_check_success(node):
    """
    info that SBD pre-enabling check finished without issues on specified node

    node -- node name
    """
    return ReportItem.info(
        report_codes.SBD_CHECK_SUCCESS,
        "{node}: SBD pre-enabling checks done",
        info={"node": node}
    )


def sbd_config_distribution_started():
    """
    distribution of SBD configuration started
    """
    return ReportItem.info(
        report_codes.SBD_CONFIG_DISTRIBUTION_STARTED,
        "Distributing SBD config..."
    )


def sbd_config_accepted_by_node(node):
    """
    info that SBD configuration has been saved successfully on specified node

    node -- node name
    """
    return ReportItem.info(
        report_codes.SBD_CONFIG_ACCEPTED_BY_NODE,
        "{node}: SBD config saved",
        info={"node": node}
    )


def unable_to_get_sbd_config(node, reason, severity=ReportItemSeverity.ERROR):
    """
    unable to get SBD config from specified node (communication or parsing
    error)

    node -- node name
    reason -- reason of failure
    """
    return ReportItem(
        report_codes.UNABLE_TO_GET_SBD_CONFIG,
        severity,
        "Unable to get SBD configuration from node '{node}': {reason}",
        info={
            "node": node,
            "reason": reason
        }
    )


def sbd_enabling_started():
    """
    enabling SBD service started
    """
    return ReportItem.info(
        report_codes.SBD_ENABLING_STARTED,
        "Enabling SBD service..."
    )


def sbd_disabling_started():
    """
    disabling SBD service started
    """
    return ReportItem.info(
        report_codes.SBD_DISABLING_STARTED,
        "Disabling SBD service..."
    )


def invalid_response_format(node):
    """
    error message that response in invalid format has been received from
    specified node

    node -- node name
    """
    return ReportItem.error(
        report_codes.INVALID_RESPONSE_FORMAT,
        "{node}: Invalid format of response",
        info={"node": node}
    )


def sbd_not_installed(node):
    """
    sbd is not installed on specified node

    node -- node name
    """
    return ReportItem.error(
        report_codes.SBD_NOT_INSTALLED,
        "SBD is not installed on node '{node}'",
        info={"node": node}
    )


def watchdog_not_found(node, watchdog):
    """
    watchdog doesn't exist on specified node

    node -- node name
    watchdog -- watchdog device path
    """
    return ReportItem.error(
        report_codes.WATCHDOG_NOT_FOUND,
        "Watchdog '{watchdog}' does not exist on node '{node}'",
        info={
            "node": node,
            "watchdog": watchdog
        }
    )


def unable_to_get_sbd_status(node, reason):
    """
    there was (communication or parsing) failure during obtaining status of SBD
    from specified node

    node -- node name
    reason -- reason of failure
    """
    return ReportItem.warning(
        report_codes.UNABLE_TO_GET_SBD_STATUS,
        "Unable to get status of SBD from node '{node}': {reason}",
        info={
            "node": node,
            "reason": reason
        }
    )

def cluster_restart_required_to_apply_changes():
    """
    warn user a cluster needs to be manually restarted to use new configuration
    """
    return ReportItem.warning(
        report_codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES,
        "Cluster restart is required in order to apply these changes."
    )
