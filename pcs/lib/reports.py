from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItem, ReportItemSeverity


def common_error(text):
    # TODO replace by more specific reports
    """
    unspecified error with text message, do not use unless absolutely necessary
    """
    return ReportItem.error(
        report_codes.COMMON_ERROR,
        info={"text": text}
    )

def common_info(text):
    # TODO replace by more specific reports
    """
    unspecified info with text message, do not use unless absolutely necessary
    """
    return ReportItem.info(
        report_codes.COMMON_INFO,
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
    return ReportItem(
        report_codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
        severity,
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
    )

def required_option_is_missing(name):
    """
    required option has not been specified, command cannot continue
    """
    return ReportItem.error(
        report_codes.REQUIRED_OPTION_IS_MISSING,
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
    return ReportItem(
        report_codes.INVALID_OPTION,
        severity,
        forceable,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "allowed": sorted(allowed_options),
        }
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
    return ReportItem(
        report_codes.INVALID_OPTION_VALUE,
        severity,
        info={
            "option_value": option_value,
            "option_name": option_name,
            "allowed_values": allowed_values,
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
        report_codes.EMPTY_ID,
        info={
            "id": id,
            "id_description": id_description,
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
        info={
            "id": id,
            "id_description": id_description,
            "is_first_char": is_first_char,
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
        info={"timeout": timeout}
    )

def invalid_score(score):
    """
    specified score value is not valid
    score specified score value
    """
    return ReportItem.error(
        report_codes.INVALID_SCORE,
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
    )

def run_external_process_started(command, stdin):
    """
    information about running an external process
    command string the external process command
    stdin string passed to the external process via its stdin
    """
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_STARTED,
        info={
            "command": command,
            "stdin": stdin,
        }
    )

def run_external_process_finished(command, retval, stdout, stderr):
    """
    information about result of running an external process
    command string the external process command
    retval external process's return (exit) code
    stdout string external process's stdout
    stderr string external process's stderr
    """
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
        info={
            "command": command,
            "return_value": retval,
            "stdout": stdout,
            "stderr": stderr,
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
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_STARTED,
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
    )

def corosync_config_accepted_by_node(node):
    """
    corosync configuration has been accepted by a node
    node string node address / name
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
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
        info={"node": node},
        forceable=forceable
    )

def corosync_not_running_check_started():
    """
    we are about to make sure corosync is not running on nodes
    """
    return ReportItem.info(
        report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED,
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
        info={"node": node}
    )

def corosync_running_on_node_fail(node):
    """
    corosync is running on a node, which is not ok
    node string node address / name
    """
    return ReportItem.error(
        report_codes.COROSYNC_RUNNING_ON_NODE,
        info={"node": node}
    )

def corosync_quorum_get_status_error(reason):
    """
    unable to get runtime status of quorum on local node
    string reason an error message
    """
    return ReportItem.error(
        report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
        info={
            "reason": reason,
        }
    )

def corosync_quorum_set_expected_votes_error(reason):
    """
    unable to set expcted votes in a live cluster
    string reason an error message
    """
    return ReportItem.error(
        report_codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR,
        info={
            "reason": reason,
        }
    )

def corosync_config_reloaded():
    """
    corosync configuration has been reloaded
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_RELOADED,
    )

def corosync_config_reload_error(reason):
    """
    an error occured when reloading corosync configuration
    reason string an error message
    """
    return ReportItem.error(
        report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
        info={"reason": reason}
    )

def corosync_config_read_error(path, reason):
    """
    an error occured when reading corosync configuration file from disk
    reason string an error message
    """
    return ReportItem.error(
        report_codes.UNABLE_TO_READ_COROSYNC_CONFIG,
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
    )

def corosync_config_parser_unexpected_closing_brace():
    """
    corosync config cannot be parsed due to unexpected closing brace
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
    )

def corosync_config_parser_other_error():
    """
    corosync config cannot be parsed, the cause is not specified
    It is better to use more specific error if possible.
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF,
    )

def corosync_options_incompatible_with_qdevice(options):
    """
    cannot set specified corosync options when qdevice is in use
    iterable options incompatible options names
    """
    return ReportItem.error(
        report_codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE,
        info={
            "options_names": options,
        }
    )

def qdevice_already_defined():
    """
    qdevice is already set up in a cluster, when it was expected not to be
    """
    return ReportItem.error(
        report_codes.QDEVICE_ALREADY_DEFINED,
    )

def qdevice_not_defined():
    """
    qdevice is not set up in a cluster, when it was expected to be
    """
    return ReportItem.error(
        report_codes.QDEVICE_NOT_DEFINED,
    )

def qdevice_remove_or_cluster_stop_needed():
    """
    operation cannot be executed, qdevice removal or cluster stop is needed
    """
    return ReportItem.error(
        report_codes.QDEVICE_REMOVE_OR_CLUSTER_STOP_NEEDED,
    )

def qdevice_client_reload_started():
    """
    qdevice client configuration is about to be reloaded on nodes
    """
    return ReportItem.info(
        report_codes.QDEVICE_CLIENT_RELOAD_STARTED,
    )

def qdevice_already_initialized(model):
    """
    cannot create qdevice on local host, it has been already created
    string model qdevice model
    """
    return ReportItem.error(
        report_codes.QDEVICE_ALREADY_INITIALIZED,
        info={
            "model": model,
        }
    )

def qdevice_not_initialized(model):
    """
    cannot work with qdevice on local host, it has not been created yet
    string model qdevice model
    """
    return ReportItem.error(
        report_codes.QDEVICE_NOT_INITIALIZED,
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
        info={
            "model": model,
            "reason": reason,
        }
    )

def qdevice_certificate_distribution_started():
    """
    Qdevice certificates are about to be set up on nodes
    """
    return ReportItem.info(
        report_codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED,
    )

def qdevice_certificate_accepted_by_node(node):
    """
    Qdevice certificates have been saved to a node
    string node node on which certificates have been saved
    """
    return ReportItem.info(
        report_codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE,
        info={"node": node}
    )

def qdevice_certificate_removal_started():
    """
    Qdevice certificates are about to be removed from nodes
    """
    return ReportItem.info(
        report_codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED,
    )

def qdevice_certificate_removed_from_node(node):
    """
    Qdevice certificates have been removed from a node
    string node node on which certificates have been deleted
    """
    return ReportItem.info(
        report_codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE,
        info={"node": node}
    )

def qdevice_certificate_import_error(reason):
    """
    an error occured when importing qdevice certificate to a node
    string reason an error message
    """
    return ReportItem.error(
        report_codes.QDEVICE_CERTIFICATE_IMPORT_ERROR,
        info={
            "reason": reason,
        }
    )

def qdevice_certificate_sign_error(reason):
    """
    an error occured when signing qdevice certificate
    string reason an error message
    """
    return ReportItem.error(
        report_codes.QDEVICE_CERTIFICATE_SIGN_ERROR,
        info={
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
        info={
            "model": model,
            "reason": reason,
        }
    )

def qdevice_not_running(model):
    """
    qdevice is expected to be running but is not running
    string model qdevice model
    """
    return ReportItem.error(
        report_codes.QDEVICE_NOT_RUNNING,
        info={
            "model": model,
        }
    )

def qdevice_get_status_error(model, reason):
    """
    unable to get runtime status of qdevice
    string model qdevice model
    string reason an error message
    """
    return ReportItem.error(
        report_codes.QDEVICE_GET_STATUS_ERROR,
        info={
            "model": model,
            "reason": reason,
        }
    )

def qdevice_used_by_clusters(
    clusters, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Qdevice is currently being used by clusters, cannot stop it unless forced
    """
    return ReportItem(
        report_codes.QDEVICE_USED_BY_CLUSTERS,
        severity,
        info={
            "clusters": clusters,
        },
        forceable=forceable
    )

def cman_unsupported_command():
    """
    requested library command is not available as local cluster is CMAN based
    """
    return ReportItem.error(
        report_codes.CMAN_UNSUPPORTED_COMMAND,
    )

def id_already_exists(id):
    """
    specified id already exists in CIB and cannot be used for a new CIB object
    id string existing id
    """
    return ReportItem.error(
        report_codes.ID_ALREADY_EXISTS,
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
        info={
            "resource_id": resource_id,
        }
    )

def cib_load_error(reason):
    """
    cannot load cib from cibadmin, cibadmin exited with non-zero code
    string reason error description
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR,
        info={
            "reason": reason,
        }
    )

def cib_load_error_scope_missing(scope, reason):
    """
    cannot load cib from cibadmin, specified scope is missing in the cib
    scope string requested cib scope
    string reason error description
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR_SCOPE_MISSING,
        info={
            "scope": scope,
            "reason": reason,
        }
    )

def cib_load_error_invalid_format():
    """
    cib does not conform to the schema
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
    )

def cib_missing_mandatory_section(section_name):
    """
    CIB is missing a section which is required to be present
    section_name string name of the missing section (element name or path)
    """
    return ReportItem.error(
        report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
        info={
            "section": section_name,
        }
    )

def cib_push_error(reason, pushed_cib):
    """
    cannot push cib to cibadmin, cibadmin exited with non-zero code
    string reason error description
    string pushed_cib cib which failed to be pushed
    """
    return ReportItem.error(
        report_codes.CIB_PUSH_ERROR,
        info={
            "reason": reason,
            "pushed_cib": pushed_cib,
        }
    )

def cluster_state_cannot_load(reason):
    """
    cannot load cluster status from crm_mon, crm_mon exited with non-zero code
    string reason error description
    """
    return ReportItem.error(
        report_codes.CRM_MON_ERROR,
        info={
            "reason": reason,
        }
    )

def cluster_state_invalid_format():
    """
    crm_mon xml output does not conform to the schema
    """
    return ReportItem.error(
        report_codes.BAD_CLUSTER_STATE_FORMAT,
    )

def resource_wait_not_supported():
    """
    crm_resource does not support --wait
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_NOT_SUPPORTED,
    )

def resource_wait_timed_out(reason):
    """
    waiting for resources (crm_resource --wait) failed, timeout expired
    string reason error description
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_TIMED_OUT,
        info={
            "reason": reason,
        }
    )

def resource_wait_error(reason):
    """
    waiting for resources (crm_resource --wait) failed
    string reason error description
    """
    return ReportItem.error(
        report_codes.RESOURCE_WAIT_ERROR,
        info={
            "reason": reason,
        }
    )

def resource_cleanup_error(reason, resource=None, node=None):
    """
    an error occured when deleting resource history in pacemaker
    string reason error description
    string resource resource which has been cleaned up
    string node node which has been cleaned up
    """
    return ReportItem.error(
        report_codes.RESOURCE_CLEANUP_ERROR,
        info={
            "reason": reason,
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
        info={"node": node}
    )

def pacemaker_local_node_name_not_found(reason):
    """
    we are unable to figure out pacemaker's local node's name
    reason string error message
    """
    return ReportItem.error(
        report_codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND,
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
        forceable=(None if warning else report_codes.FORCE_ACTIVE_RRP)
    )

def cman_ignored_option(option):
    """
    specified option is ignored as CMAN clusters do not support it
    options string option name
    """
    return ReportItem.warning(
        report_codes.IGNORED_CMAN_UNSUPPORTED_OPTION,
        info={'option_name': option}
    )

def rrp_addresses_transport_mismatch():
    """
    RRP defined by network addresses is not allowed when udp transport is used
    """
    return ReportItem.error(
        report_codes.NON_UDP_TRANSPORT_ADDR_MISMATCH,
    )

def cman_udpu_restart_required():
    """
    warn user it is required to restart CMAN cluster for changes to take effect
    """
    return ReportItem.warning(
        report_codes.CMAN_UDPU_RESTART_REQUIRED,
    )

def cman_broadcast_all_rings():
    """
    broadcast enabled in all rings, CMAN doesn't support 1 ring only broadcast
    """
    return ReportItem.warning(
        report_codes.CMAN_BROADCAST_ALL_RINGS,
    )

def service_start_started(service, instance=None):
    """
    system service is being started
    string service service name or description
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_START_STARTED,
        info={
            "service": service,
            "instance": instance,
        }
    )

def service_start_error(service, reason, node=None, instance=None):
    """
    system service start failed
    string service service name or description
    string reason error message
    string node node on which service has been requested to start
    string instance instance of service
    """
    return ReportItem.error(
        report_codes.SERVICE_START_ERROR,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance,
        }
    )

def service_start_success(service, node=None, instance=None):
    """
    system service was started successfully
    string service service name or description
    string node node on which service has been requested to start
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_START_SUCCESS,
        info={
            "service": service,
            "node": node,
            "instance": instance,
        }
    )

def service_start_skipped(service, reason, node=None, instance=None):
    """
    starting system service was skipped, no error occured
    string service service name or description
    string reason why the start has been skipped
    string node node on which service has been requested to start
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_START_SKIPPED,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance,
        }
    )

def service_stop_started(service, instance=None):
    """
    system service is being stopped
    string service service name or description
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_STOP_STARTED,
        info={
            "service": service,
            "instance": instance,
        }
    )

def service_stop_error(service, reason, node=None, instance=None):
    """
    system service stop failed
    string service service name or description
    string reason error message
    string node node on which service has been requested to stop
    string instance instance of service
    """
    return ReportItem.error(
        report_codes.SERVICE_STOP_ERROR,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance,
        }
    )

def service_stop_success(service, node=None, instance=None):
    """
    system service was stopped successfully
    string service service name or description
    string node node on which service has been requested to stop
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_STOP_SUCCESS,
        info={
            "service": service,
            "node": node,
            "instance": instance,
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
        info={
            "services": services,
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
        info={
            "services": services,
        }
    )

def service_enable_started(service, instance=None):
    """
    system service is being enabled
    string service service name or description
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_ENABLE_STARTED,
        info={
            "service": service,
            "instance": instance,
        }
    )

def service_enable_error(service, reason, node=None, instance=None):
    """
    system service enable failed
    string service service name or description
    string reason error message
    string node node on which service was enabled
    string instance instance of service
    """
    return ReportItem.error(
        report_codes.SERVICE_ENABLE_ERROR,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance,
        }
    )

def service_enable_success(service, node=None, instance=None):
    """
    system service was enabled successfully
    string service service name or description
    string node node on which service has been enabled
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_ENABLE_SUCCESS,
        info={
            "service": service,
            "node": node,
            "instance": instance,
        }
    )

def service_enable_skipped(service, reason, node=None, instance=None):
    """
    enabling system service was skipped, no error occured
    string service service name or description
    string reason why the enabling has been skipped
    string node node on which service has been requested to enable
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_ENABLE_SKIPPED,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance
        }
    )

def service_disable_started(service, instance=None):
    """
    system service is being disabled
    string service service name or description
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_DISABLE_STARTED,
        info={
            "service": service,
            "instance": instance,
        }
    )

def service_disable_error(service, reason, node=None, instance=None):
    """
    system service disable failed
    string service service name or description
    string reason error message
    string node node on which service was disabled
    string instance instance of service
    """
    return ReportItem.error(
        report_codes.SERVICE_DISABLE_ERROR,
        info={
            "service": service,
            "reason": reason,
            "node": node,
            "instance": instance,
        }
    )

def service_disable_success(service, node=None, instance=None):
    """
    system service was disabled successfully
    string service service name or description
    string node node on which service was disabled
    string instance instance of service
    """
    return ReportItem.info(
        report_codes.SERVICE_DISABLE_SUCCESS,
        info={
            "service": service,
            "node": node,
            "instance": instance,
        }
    )


def unable_to_get_agent_metadata(
    agent, reason, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    There were some issues trying to get metadata of agent

    string agent agent which metadata were unable to obtain
    string reason reason of failure
    """
    return ReportItem(
        report_codes.UNABLE_TO_GET_AGENT_METADATA,
        severity,
        info={
            "agent": agent,
            "reason": reason
        },
        forceable=forceable
    )

def invalid_resource_agent_name(name):
    """
    The entered resource agent name is not valid.
    This name has the internal structure. The code needs to work with parts of
    this structure and fails if parts can not be obtained.

    string name is entered name
    """
    return ReportItem.error(
        report_codes.INVALID_RESOURCE_AGENT_NAME,
        info={
            "name": name,
        }
    )

def agent_name_guessed(entered_name, guessed_name):
    """
    Resource agent name was deduced from the entered name.
    Pcs supports the using of abbreviated resource agent name (e.g.
    ocf:heartbeat:Delay => Delay) when it can be clearly deduced.

    string entered_name is entered name
    string guessed_name is deduced name
    """
    return ReportItem.info(
        report_codes.AGENT_NAME_GUESSED,
        info={
            "entered_name": entered_name,
            "guessed_name": guessed_name,
        }
    )

def agent_name_guess_found_more_than_one(agent, possible_agents):
    """
    More than one agents found based on the search string, specify one of them
    string agent searched name of an agent
    iterable possible_agents full names of agents matching the search
    """
    return ReportItem.error(
        report_codes.AGENT_NAME_GUESS_FOUND_MORE_THAN_ONE,
        info={
            "agent": agent,
            "possible_agents": possible_agents,
            "possible_agents_str": ", ".join(sorted(possible_agents)),
        }
    )


def agent_name_guess_found_none(agent):
    """
    Specified agent doesn't exist
    string agent name of the agent which doesn't exist
    """
    return ReportItem.error(
        report_codes.AGENT_NAME_GUESS_FOUND_NONE,
        info={"agent": agent}
    )


def omitting_node(node):
    """
    warning that specified node will be omitted in following actions

    node -- node name
    """
    return ReportItem.warning(
        report_codes.OMITTING_NODE,
        info={"node": node}
    )


def sbd_check_started():
    """
    info that SBD pre-enabling checks started
    """
    return ReportItem.info(
        report_codes.SBD_CHECK_STARTED,
    )


def sbd_check_success(node):
    """
    info that SBD pre-enabling check finished without issues on specified node

    node -- node name
    """
    return ReportItem.info(
        report_codes.SBD_CHECK_SUCCESS,
        info={"node": node}
    )


def sbd_config_distribution_started():
    """
    distribution of SBD configuration started
    """
    return ReportItem.info(
        report_codes.SBD_CONFIG_DISTRIBUTION_STARTED,
    )


def sbd_config_accepted_by_node(node):
    """
    info that SBD configuration has been saved successfully on specified node

    node -- node name
    """
    return ReportItem.info(
        report_codes.SBD_CONFIG_ACCEPTED_BY_NODE,
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
    )


def sbd_disabling_started():
    """
    disabling SBD service started
    """
    return ReportItem.info(
        report_codes.SBD_DISABLING_STARTED,
    )


def invalid_response_format(node):
    """
    error message that response in invalid format has been received from
    specified node

    node -- node name
    """
    return ReportItem.error(
        report_codes.INVALID_RESPONSE_FORMAT,
        info={"node": node}
    )


def sbd_not_installed(node):
    """
    sbd is not installed on specified node

    node -- node name
    """
    return ReportItem.error(
        report_codes.SBD_NOT_INSTALLED,
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
        info={
            "node": node,
            "watchdog": watchdog
        }
    )


def invalid_watchdog_path(watchdog):
    """
    watchdog path is not absolut path

    watchdog -- watchdog device path
    """
    return ReportItem.error(
        report_codes.WATCHDOG_INVALID,
        info={"watchdog": watchdog}
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
    )


def cib_alert_recipient_already_exists(
    alert_id, recipient_value, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Recipient with specified value already exists in alert with id 'alert_id'

    alert_id -- id of alert to which recipient belongs
    recipient_value -- value of recipient
    """
    return ReportItem(
        report_codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS,
        severity,
        info={
            "recipient": recipient_value,
            "alert": alert_id
        },
        forceable=forceable
    )


def cib_alert_recipient_invalid_value(recipient_value):
    """
    Invalid recipient value.

    recipient_value -- recipient value
    """
    return ReportItem.error(
        report_codes.CIB_ALERT_RECIPIENT_VALUE_INVALID,
        info={"recipient": recipient_value}
    )

def cib_alert_not_found(alert_id):
    """
    Alert with specified id doesn't exist.

    alert_id -- id of alert
    """
    return ReportItem.error(
        report_codes.CIB_ALERT_NOT_FOUND,
        info={"alert": alert_id}
    )


def cib_upgrade_successful():
    """
    Upgrade of CIB schema was successful.
    """
    return ReportItem.info(
        report_codes.CIB_UPGRADE_SUCCESSFUL,
    )


def cib_upgrade_failed(reason):
    """
    Upgrade of CIB schema failed.

    reason -- reason of failure
    """
    return ReportItem.error(
        report_codes.CIB_UPGRADE_FAILED,
        info={"reason": reason}
    )


def unable_to_upgrade_cib_to_required_version(
    current_version, required_version
):
    """
    Unable to upgrade CIB to minimal required schema version.

    current_version -- current version of CIB schema
    required_version -- required version of CIB schema
    """
    return ReportItem.error(
        report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION,
        info={
            "required_version": "{0}.{1}.{2}".format(*required_version),
            "current_version": "{0}.{1}.{2}".format(*current_version)
        }
    )

def file_already_exists(
        file_role, file_path, severity=ReportItemSeverity.ERROR,
        forceable=None, node=None
    ):
    return ReportItem(
        report_codes.FILE_ALREADY_EXISTS,
        severity,
        info={
            "file_role": file_role,
            "file_path": file_path,
            "node": node,
        },
        forceable=forceable,
    )

def file_does_not_exist(file_role, file_path=""):
    return ReportItem.error(
        report_codes.FILE_DOES_NOT_EXIST,
        info={
            "file_role": file_role,
            "file_path": file_path,
        },
    )

def file_io_error(
    file_role, file_path="", reason="", operation="work with",
    severity=ReportItemSeverity.ERROR
):
    return ReportItem(
        report_codes.FILE_IO_ERROR,
        severity,
        info={
            "file_role": file_role,
            "file_path": file_path,
            "reason": reason,
            "operation": operation
        },
    )

def unable_to_determine_user_uid(user):
    return ReportItem.error(
        report_codes.UNABLE_TO_DETERMINE_USER_UID,
        info={
            "user": user
        }
    )

def unable_to_determine_group_gid(group):
    return ReportItem.error(
        report_codes.UNABLE_TO_DETERMINE_GROUP_GID,
        info={
            "group": group
        }
    )

def unsupported_operation_on_non_systemd_systems():
    return ReportItem.error(
        report_codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS,
    )

def live_environment_required(forbidden_options):
    return ReportItem.error(
        report_codes.LIVE_ENVIRONMENT_REQUIRED,
        info={
            "forbidden_options": forbidden_options,
        }
    )


def quorum_cannot_disable_atb_due_to_sbd(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Quorum option auto_tie_breaker cannot be disbled due to SBD.
    """
    return ReportItem(
        report_codes.COROSYNC_QUORUM_CANNOT_DISABLE_ATB_DUE_TO_SBD,
        severity,
        forceable=forceable
    )


def sbd_requires_atb():
    """
    Warning that ATB will be enabled in order to make SBD fencing effective.
    """
    return ReportItem.warning(
        report_codes.SBD_REQUIRES_ATB,
    )


def acl_role_is_already_assigned_to_target(role_id, target_id):
    """
    Error that ACL target or group has already assigned role.
    """
    return ReportItem.error(
        report_codes.CIB_ACL_ROLE_IS_ALREADY_ASSIGNED_TO_TARGET,
        info={
            "role_id": role_id,
            "target_id": target_id,
        }
    )


def acl_role_is_not_assigned_to_target(role_id, target_id):
    """
    Error that acl role is not assigned to target or group
    """
    return ReportItem.error(
        report_codes.CIB_ACL_ROLE_IS_NOT_ASSIGNED_TO_TARGET,
        info={
            "role_id": role_id,
            "target_id": target_id,
        }
    )


def acl_target_already_exists(target_id):
    """
    Error that target with specified id aleready axists in configuration.
    """
    return ReportItem.error(
        report_codes.CIB_ACL_TARGET_ALREADY_EXISTS,
        info={
            "target_id": target_id,
        }
    )


def cluster_conf_invalid_format(reason):
    """
    cluster.conf parsing error
    """
    return ReportItem.error(
        report_codes.CLUSTER_CONF_LOAD_ERROR_INVALID_FORMAT,
        info={
            "reason": reason,
        }
    )


def cluster_conf_read_error(path, reason):
    """
    Unable to read cluster.conf
    """
    return ReportItem.error(
        report_codes.CLUSTER_CONF_READ_ERROR,
        info={
            "path": path,
            "reason": reason,
        }
    )
