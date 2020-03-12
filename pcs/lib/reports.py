# pylint: disable=too-many-lines
from functools import partial

from pcs.common.reports import codes as report_codes
from pcs.common.reports import ReportItem, ReportItemSeverity

def forceable_error(force_code, report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "error" and  "warning".
    the pair with function "warning".

    string force_code is code for forcing error
    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=force_code,
        severity=ReportItemSeverity.ERROR,
        **kwargs
    )

def warning(report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "error" and  "forceable_error".

    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=None,
        severity=ReportItemSeverity.WARNING,
        **kwargs
    )

def error(report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "forceable_error" and "forceable_error".

    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=None,
        severity=ReportItemSeverity.ERROR,
        **kwargs
    )

def get_problem_creator(force_code=None, is_forced=False):
    """
    Returns report creator wraper (forceable_error or warning).

    This is experimental shortcut for decision if ReportItem will be
    either forceable_error or warning.

    string force_code is code for forcing error. It could be usefull to prepare
        it for whole module by using functools.partial.
    bool warn_only is flag for selecting wrapper
    """
    if not force_code:
        return error
    if is_forced:
        return warning
    return partial(forceable_error, force_code)

def _key_numeric(item):
    return (int(item), item) if item.isdigit() else (-1, item)


def duplicate_constraints_exist(
    constraint_type, constraint_info_list,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    when creating a constraint it was detected the constraint already exists
    constraint_type string "rsc_colocation", "rsc_order", "rsc_ticket"
    constraint_info_list list of structured constraint data according to type
    severity report item severity
    forceable is this report item forceable? by what category?
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

def corosync_config_accepted_by_node(node):
    """
    corosync configuration has been accepted by a node
    node string node address / name
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
        info={"node": node}
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

def id_already_exists(id):
    # pylint says 'id' is wrong
    # pylint: disable=invalid-name, redefined-builtin
    """
    specified id already exists in CIB and cannot be used for a new CIB object
    id string existing id
    """
    return ReportItem.error(
        report_codes.ID_ALREADY_EXISTS,
        info={"id": id}
    )

def id_belongs_to_unexpected_type(id, expected_types, current_type):
    # pylint says 'id' is wrong
    # pylint: disable=invalid-name, redefined-builtin
    """
    Specified id exists but for another element than expected.
    For example user wants to create resource in group that is specifies by id.
    But id does not belong to group.
    """
    return ReportItem.error(
        report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
        info={
            "id": id,
            "expected_types": expected_types,
            "current_type": current_type,
        }
    )

def object_with_id_in_unexpected_context(
    object_type, object_id, expected_context_type, expected_context_id
):
    """
    Object specified by object_type (tag) and object_id exists but not inside
    given context (expected_context_type, expected_context_id).
    """
    return ReportItem.error(
        report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
        info={
            "type": object_type,
            "id": object_id,
            "expected_context_type": expected_context_type,
            "expected_context_id": expected_context_id,
        }
    )


def id_not_found(id, expected_types, context_type="", context_id=""):
    # pylint says 'id' is wrong
    # pylint: disable=invalid-name, redefined-builtin
    """
    specified id does not exist in CIB, user referenced a nonexisting id

    string id -- specified id
    list expected_types -- list of id's roles - expected types with the id
    string context_type -- context_id's role / type
    string context_id -- specifies the search area
    """
    return ReportItem.error(
        report_codes.ID_NOT_FOUND,
        info={
            "id": id,
            "expected_types": sorted(expected_types),
            "context_type": context_type,
            "context_id": context_id,
        }
    )

def resource_bundle_already_contains_a_resource(bundle_id, resource_id):
    """
    The bundle already contains a resource, another one caanot be added

    string bundle_id -- id of the bundle
    string resource_id -- id of the resource already contained in the bundle
    """
    return ReportItem.error(
        report_codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE,
        info={
            "bundle_id": bundle_id,
            "resource_id": resource_id,
        }
    )

def stonith_resources_do_not_exist(
    stonith_ids, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified stonith resource doesn't exist (e.g. when creating in constraints)
    iterable stoniths -- list of specified stonith id
    """
    return ReportItem(
        report_codes.STONITH_RESOURCES_DO_NOT_EXIST,
        severity,
        info={
            "stonith_ids": sorted(stonith_ids),
        },
        forceable=forceable
    )

def resource_running_on_nodes(
    resource_id, roles_with_nodes, severity=ReportItemSeverity.INFO
):
    """
    Resource is running on some nodes. Taken from cluster state.

    string resource_id represent the resource
    list of tuple roles_with_nodes contain pairs (role, node)
    """
    return ReportItem(
        report_codes.RESOURCE_RUNNING_ON_NODES,
        severity,
        info={
            "resource_id": resource_id,
            "roles_with_nodes": roles_with_nodes,
        }
    )

def resource_does_not_run(resource_id, severity=ReportItemSeverity.INFO):
    """
    Resource is not running on any node. Taken from cluster state.

    string resource_id represent the resource
    """
    return ReportItem(
        report_codes.RESOURCE_DOES_NOT_RUN,
        severity,
        info={
            "resource_id": resource_id,
        }
    )

def resource_is_guest_node_already(resource_id):
    """
    The resource is already used as guest node (i.e. has meta attribute
    remote-node).

    string resource_id -- id of the resource that is guest node
    """
    return ReportItem.error(
        report_codes.RESOURCE_IS_GUEST_NODE_ALREADY,
        info={
            "resource_id": resource_id,
        }
    )

def resource_is_unmanaged(resource_id):
    """
    The resource the user works with is unmanaged (e.g. in enable/disable)

    string resource_id -- id of the unmanaged resource
    """
    return ReportItem.warning(
        report_codes.RESOURCE_IS_UNMANAGED,
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

def cib_load_error_get_nodes_for_validation(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Unable to load CIB, unable to get remote and guest nodes for validation
    """
    return ReportItem(
        report_codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION,
        severity,
        forceable=forceable
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

def cib_load_error_invalid_format(reason):
    """
    cib does not conform to the schema
    """
    return ReportItem.error(
        report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
        info={
            "reason": reason,
        }
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

def cib_save_tmp_error(reason):
    """
    cannot save CIB into a temporary file
    string reason error description
    """
    return ReportItem.error(
        report_codes.CIB_SAVE_TMP_ERROR,
        info={
            "reason": reason,
        }
    )

def cib_diff_error(reason, cib_old, cib_new):
    """
    cannot obtain a diff of CIBs
    string reason -- error description
    string cib_old -- the CIB to be diffed against
    string cib_new -- the CIB diffed against the old cib
    """
    return ReportItem.error(
        report_codes.CIB_DIFF_ERROR,
        info={
            "reason": reason,
            "cib_old": cib_old,
            "cib_new": cib_new,
        }
    )

def cib_simulate_error(reason):
    """
    cannot simulate effects a CIB would have on a live cluster

    string reason -- error description
    """
    return ReportItem.error(
        report_codes.CIB_SIMULATE_ERROR,
        info={
            "reason": reason,
        }
    )

def cib_push_forced_full_due_to_crm_feature_set(required_set, current_set):
    """
    Pcs uses the "push full CIB" approach so race conditions may occur.

    pcs.common.tools.Version required_set -- crm_feature_set required for diff
    pcs.common.tools.Version current_set -- actual CIB crm_feature_set
    """
    return ReportItem.warning(
        report_codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET,
        info={
            "required_set": str(required_set),
            "current_set": str(current_set),
        }
    )

def cluster_state_cannot_load(reason: str):
    """
    cannot load cluster status from crm_mon, crm_mon exited with non-zero code

    reason -- description of the error
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

def wait_for_idle_not_supported():
    """
    crm_resource does not support --wait
    """
    return ReportItem.error(
        report_codes.WAIT_FOR_IDLE_NOT_SUPPORTED,
    )

def wait_for_idle_timed_out(reason):
    """
    waiting for resources (crm_resource --wait) failed, timeout expired
    string reason error description
    """
    return ReportItem.error(
        report_codes.WAIT_FOR_IDLE_TIMED_OUT,
        info={
            "reason": reason,
        }
    )

def wait_for_idle_error(reason):
    """
    waiting for resources (crm_resource --wait) failed
    string reason error description
    """
    return ReportItem.error(
        report_codes.WAIT_FOR_IDLE_ERROR,
        info={
            "reason": reason,
        }
    )

def wait_for_idle_not_live_cluster():
    """
    cannot wait for the cluster if not running with a live cluster
    """
    return ReportItem.error(
        report_codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER,
    )

def resource_cleanup_error(reason, resource=None, node=None):
    """
    An error occured when deleting resource failed operations in pacemaker

    string reason -- error description
    string resource -- resource which has been cleaned up
    string node -- node which has been cleaned up
    """
    return ReportItem.error(
        report_codes.RESOURCE_CLEANUP_ERROR,
        info={
            "reason": reason,
            "resource": resource,
            "node": node,
        }
    )

def resource_refresh_error(reason, resource=None, node=None):
    """
    An error occured when deleting resource history in pacemaker

    string reason -- error description
    string resource -- resource which has been cleaned up
    string node -- node which has been cleaned up
    """
    return ReportItem.error(
        report_codes.RESOURCE_REFRESH_ERROR,
        info={
            "reason": reason,
            "resource": resource,
            "node": node,
        }
    )

def resource_refresh_too_time_consuming(threshold):
    """
    Resource refresh would execute more than threshold operations in a cluster

    int threshold -- current threshold for trigerring this error
    """
    return ReportItem.error(
        report_codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING,
        info={"threshold": threshold},
        forceable=report_codes.FORCE_LOAD_THRESHOLD
    )

def resource_operation_interval_duplication(duplications):
    """
    More operations with same name and same interval apeared.
    Each operation with the same name (e.g. monitoring) need to have unique
    interval.
    dict duplications see resource operation interval duplication
        in pcs/lib/exchange_formats.md
    """
    return ReportItem.error(
        report_codes.RESOURCE_OPERATION_INTERVAL_DUPLICATION,
        info={
            "duplications": duplications,
        }
    )

def resource_operation_interval_adapted(
    operation_name, original_interval, adapted_interval
):
    """
    Interval of resource operation was adopted to operation (with the same name)
        intervals were unique.
    Each operation with the same name (e.g. monitoring) need to have unique
    interval.

    """
    return ReportItem.warning(
        report_codes.RESOURCE_OPERATION_INTERVAL_ADAPTED,
        info={
            "operation_name": operation_name,
            "original_interval": original_interval,
            "adapted_interval": adapted_interval,
        }
    )

def multiple_result_found(
    result_type, result_identifier_list, search_description="",
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Multiple result was found when something was looked for. E.g. resource for
    remote node.

    string result_type specifies what was looked for, e.g. "resource"
    list result_identifier_list contains identifiers of results
        e.g. resource ids
    string search_description e.g. name of remote_node
    """
    return ReportItem(
        report_codes.MULTIPLE_RESULTS_FOUND,
        severity,
        info={
            "result_type": result_type,
            "result_identifier_list": result_identifier_list,
            "search_description": search_description,
        },
        forceable=forceable
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
            "services": sorted(services),
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
            "services": sorted(services),
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

def invalid_stonith_agent_name(name):
    """
    The entered stonith agent name is not valid.
    string name -- entered stonith agent name
    """
    return ReportItem.error(
        report_codes.INVALID_STONITH_AGENT_NAME,
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


# TODO: use generic service reports
def sbd_enabling_started():
    """
    enabling SBD service started
    """
    return ReportItem.info(
        report_codes.SBD_ENABLING_STARTED,
    )


# TODO: use generic service reports
def sbd_disabling_started():
    """
    disabling SBD service started
    """
    return ReportItem.info(
        report_codes.SBD_DISABLING_STARTED,
    )


def sbd_device_initialization_started(device_list):
    """
    initialization of SBD device(s) started
    """
    return ReportItem.info(
        report_codes.SBD_DEVICE_INITIALIZATION_STARTED,
        info={
            "device_list": device_list,
        }
    )


def sbd_device_initialization_success(device_list):
    """
    initialization of SBD device(s) successed
    """
    return ReportItem.info(
        report_codes.SBD_DEVICE_INITIALIZATION_SUCCESS,
        info={
            "device_list": device_list,
        }
    )


def sbd_device_initialization_error(device_list, reason):
    """
    initialization of SBD device failed
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_INITIALIZATION_ERROR,
        info={
            "device_list": device_list,
            "reason": reason,
        }
    )


def sbd_device_list_error(device, reason):
    """
    command 'sbd list' failed
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_LIST_ERROR,
        info={
            "device": device,
            "reason": reason,
        }
    )


def sbd_device_message_error(device, node, message, reason):
    """
    unable to set message 'message' on shared block device 'device'
    for node 'node'.
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_MESSAGE_ERROR,
        info={
            "device": device,
            "node": node,
            "message": message,
            "reason": reason,
        }
    )


def sbd_device_dump_error(device, reason):
    """
    command 'sbd dump' failed
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_DUMP_ERROR,
        info={
            "device": device,
            "reason": reason,
        }
    )

def files_distribution_started(file_list, node_list=None):
    """
    files are about to be sent to nodes

    iterable of strings file_list -- files to be sent
    iterable of strings node_list -- node names where the files are being sent
    """
    file_list = file_list if file_list else []
    return ReportItem.info(
        report_codes.FILES_DISTRIBUTION_STARTED,
        info={
            "file_list": file_list,
            "node_list": node_list,
        }
    )

def files_distribution_skipped(reason_type, file_list, node_list):
    """
    Files distribution skipped due to unreachable nodes or not live cluster

    string reason_type -- why was the action skipped (unreachable, not_live_cib)
    iterable of strings file_list -- contains description of files
    iterable of strings node_list -- where the files should have been sent to
    """
    return ReportItem.info(
        report_codes.FILES_DISTRIBUTION_SKIPPED,
        info={
            "reason_type": reason_type,
            "file_list": file_list,
            "node_list": node_list,
        }
    )
