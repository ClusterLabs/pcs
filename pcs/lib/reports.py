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
