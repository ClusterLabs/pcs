# pylint: disable=too-many-lines
from collections.abc import Iterable
from functools import partial
from typing import Mapping
import sys

from pcs.common import file_type_codes
from pcs.common.file import RawFileError
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE
from pcs.common.reports import codes
from pcs.common.str_tools import (
    format_list,
    format_optional,
    format_plural,
    indent,
)

INSTANCE_SUFFIX = "@{0}"
NODE_PREFIX = "{0}: "

_type_translation = {
    "acl_group": "ACL group",
    "acl_permission": "ACL permission",
    "acl_role": "ACL role",
    "acl_target": "ACL user",
    # Pacemaker-2.0 deprecated masters. Masters are now called promotable
    # clones. We treat masters as clones. Do not report we were doing something
    # with a master, say we were doing it with a clone instead.
    "master": "clone",
    "primitive": "resource",
}
_type_articles = {
    "ACL group": "an",
    "ACL user": "an",
    "ACL role": "an",
    "ACL permission": "an",
}
_file_operation_translation = {
    RawFileError.ACTION_CHMOD: "change permissions of",
    RawFileError.ACTION_CHOWN: "change ownership of",
    RawFileError.ACTION_READ: "read",
    RawFileError.ACTION_REMOVE: "remove",
    RawFileError.ACTION_WRITE: "write",
}
_file_role_translation = {
    file_type_codes.BOOTH_CONFIG: "Booth configuration",
    file_type_codes.BOOTH_KEY: "Booth key",
    file_type_codes.COROSYNC_AUTHKEY: "Corosync authkey",
    file_type_codes.PCS_DR_CONFIG: "disaster-recovery configuration",
    file_type_codes.PACEMAKER_AUTHKEY: "Pacemaker authkey",
    file_type_codes.PCSD_ENVIRONMENT_CONFIG: "pcsd configuration",
    file_type_codes.PCSD_SSL_CERT: "pcsd SSL certificate",
    file_type_codes.PCSD_SSL_KEY: "pcsd SSL key",
    file_type_codes.PCS_KNOWN_HOSTS: "known-hosts",
    file_type_codes.PCS_SETTINGS_CONF: "pcs configuration",
}
_file_role_to_option_translation: Mapping[str, str] = {
    file_type_codes.BOOTH_CONFIG: "--booth-conf",
    file_type_codes.BOOTH_KEY: "--booth-key",
    file_type_codes.CIB: "-f",
    file_type_codes.COROSYNC_CONF: "--corosync_conf",
}

def warn(message):
    sys.stdout.write(format_message(message, "Warning: "))

def format_message(message, prefix):
    return "{0}{1}\n".format(prefix, message)

def error(message):
    sys.stderr.write(format_message(message, "Error: "))
    return SystemExit(1)

def format_fencing_level_target(target_type, target_value):
    if target_type == TARGET_TYPE_ATTRIBUTE:
        return "{0}={1}".format(target_value[0], target_value[1])
    return target_value

def format_file_action(action):
    return _file_operation_translation.get(action, action)

def format_file_role(role):
    return _file_role_translation.get(role, role)

def is_iterable_not_str(value):
    return isinstance(value, Iterable) and not isinstance(value, str)

def service_operation_started(operation, info):
    return "{operation} {service}{instance_suffix}...".format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        **info
    )

def service_operation_error(operation, info):
    return (
        "{node_prefix}Unable to {operation} {service}{instance_suffix}:"
        " {reason}"
    ).format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        node_prefix=format_optional(info["node"], NODE_PREFIX),
        **info
    )

def service_operation_success(operation, info):
    return "{node_prefix}{service}{instance_suffix} {operation}".format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        node_prefix=format_optional(info["node"], NODE_PREFIX),
        **info
    )

def service_operation_skipped(operation, info):
    return (
        "{node_prefix}not {operation} {service}{instance_suffix}: {reason}"
    ).format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        node_prefix=format_optional(info["node"], NODE_PREFIX),
        **info
    )

def type_to_string(type_name, article=False):
    if not type_name:
        return ""
    # get a translation or make a type_name a string
    translated = _type_translation.get(type_name, "{0}".format(type_name))
    if not article:
        return translated
    return "{article} {type}".format(
        article=_type_articles.get(translated, "a"),
        type=translated
    )

def typelist_to_string(type_list, article=False):
    if not type_list:
        return ""
    # use set to drop duplicate items:
    # * master is translated to clone
    # * i.e. "clone, master" is translated to "clone, clone"
    # * so we want to drop the second clone
    new_list = sorted({
        # get a translation or make a type_name a string
        _type_translation.get(type_name, "{0}".format(type_name))
        for type_name in type_list
    })
    types = "/".join(new_list)
    if not article:
        return types
    return "{article} {types}".format(
        article=_type_articles.get(new_list[0], "a"),
        types=types
    )

def skip_reason_to_string(reason):
    translate = {
        "not_live_cib": "the command does not run on a live cluster (e.g. -f "
            "was used)"
        ,
        "unreachable": "pcs is unable to connect to the node(s)",
    }
    return translate.get(reason, reason)

def id_belongs_to_unexpected_type(info):
    return "'{id}' is not {expected_type}".format(
        id=info["id"],
        expected_type=typelist_to_string(info["expected_types"], article=True)
    )

def object_with_id_in_unexpected_context(info):
    context_type = type_to_string(info["expected_context_type"])
    if info.get("expected_context_id", ""):
        context = "{_expected_context_type} '{expected_context_id}'".format(
            _expected_context_type=context_type,
            **info
        )
    else:
        context = "'{_expected_context_type}'".format(
            _expected_context_type=context_type,
        )
    return "{_type} '{id}' exists but does not belong to {_context}".format(
        _context=context,
        _type=type_to_string(info["type"]),
        **info
    )

def id_not_found(info):
    desc = format_optional(typelist_to_string(info["expected_types"]), "{0} ")
    if not info["context_type"] or not info["context_id"]:
        return "{desc}'{id}' does not exist".format(desc=desc, id=info["id"])

    return (
        "there is no {desc}'{id}' in the {context_type} '{context_id}'".format(
            desc=desc,
            id=info["id"],
            context_type=info["context_type"],
            context_id=info["context_id"],
        )
    )

def resource_running_on_nodes(info):
    role_label_map = {
        "Started": "running",
    }
    state_info = {}
    for state, node_list in info["roles_with_nodes"].items():
        state_info.setdefault(
            role_label_map.get(state, state.lower()),
            []
        ).extend(node_list)

    return "resource '{resource_id}' is {detail_list}".format(
        resource_id=info["resource_id"],
        detail_list="; ".join(sorted([
            "{run_type} on node{s} {node_list}".format(
                run_type=run_type,
                s="s" if len(node_list) > 1 else "",
                node_list=format_list(node_list)
            )
            for run_type, node_list in state_info.items()
        ]))
    )

def build_node_description(node_types):
    if not node_types:
        return  "Node"

    label = "{0} node".format

    if isinstance(node_types, str):
        return label(node_types)

    if len(node_types) == 1:
        return label(node_types[0])

    return "nor " + " or ".join([label(ntype) for ntype in node_types])

#Each value (a callable taking report_item.info) returns a message.
#Force text will be appended if necessary.
#If it is necessary to put the force text inside the string then the callable
#must take the force_text parameter.
CODE_TO_MESSAGE_BUILDER_MAP = {
    codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE: lambda info:
        "{node}: Succeeded"
        .format(**info)
    ,

    codes.UNABLE_TO_READ_COROSYNC_CONFIG: lambda info:
        "Unable to read {path}: {reason}"
        .format(**info)
    ,

    codes.COROSYNC_NODES_MISSING:
        "No nodes have been specified"
    ,

    codes.COROSYNC_TOO_MANY_LINKS_OPTIONS: lambda info:
        (
            "Cannot specify options for more links ({links_options_count}) "
            "than how many is defined by number of addresses per node "
            "({links_count})"
        ).format(**info)
    ,

    codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT: lambda info:
        (
            "Cluster is using {actual_transport} transport which does not "
            "support {_action} links"
        ).format(
            _action=("adding" if info["add_or_not_remove"] else "removing"),
            **info
        )
    ,

    codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_NO_LINKS_SPECIFIED: lambda info:
        "Cannot {_action} links, no links to {_action} specified".format(
            _action=("add" if info["add_or_not_remove"] else "remove"),
        )
    ,

    codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS: lambda info:
        (
            "Cannot {_action} {links_change_count} link{_s_change}, there "
            "would be {links_new_count} link{_s_new} defined which is "
            "{_more_less} than allowed number of {links_limit_count} "
            "link{_s_limit}"
        ).format(
            _action=("add" if info["add_or_not_remove"] else "remove"),
            _more_less=("more" if info["add_or_not_remove"] else "less"),
            _s_change=("" if info["links_change_count"] == 1 else "s"),
            _s_new=("" if info["links_new_count"] == 1 else "s"),
            _s_limit=("" if info["links_limit_count"] == 1 else "s"),
            **info
        )
    ,

    codes.COROSYNC_LINK_ALREADY_EXISTS_CANNOT_ADD: lambda info:
        "Cannot add link '{link_number}', it already exists".format(**info)
    ,

    codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE: lambda info:
        (
            "Cannot remove non-existent link{_s} {_to_remove}, existing links: "
            "{_existing}"
        ).format(
            _s=("s" if len(info["link_list"]) > 1 else ""),
            _to_remove=format_list(info["link_list"]),
            _existing=format_list(info["existing_link_list"]),
            **info
        )
    ,

    codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE: lambda info:
        (
            "Cannot set options for non-existent link '{link_number}', "
            "existing links: {_link_list}"
        ).format(
            _link_list=format_list(info["existing_link_list"]),
            **info
        )
    ,

    codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS: lambda info:
        (
            "The {actual_transport} transport does not support '{option_type}' "
            "options, use {_required_transports} transport"
        ).format(
            _required_transports=format_list(info["required_transport_list"]),
            **info
        )
    ,

    codes.QDEVICE_ALREADY_DEFINED:
        "quorum device is already defined"
    ,

    codes.QDEVICE_NOT_DEFINED:
        "no quorum device is defined in this cluster"
    ,

    codes.QDEVICE_REMOVE_OR_CLUSTER_STOP_NEEDED: (
        "You need to stop the cluster or remove qdevice from the cluster to"
        " continue"
    ),

    codes.QDEVICE_CLIENT_RELOAD_STARTED:
        "Reloading qdevice configuration on nodes..."
    ,

    codes.QDEVICE_ALREADY_INITIALIZED: lambda info:
        "Quorum device '{model}' has been already initialized"
        .format(**info)
    ,

    codes.QDEVICE_NOT_INITIALIZED: lambda info:
        "Quorum device '{model}' has not been initialized yet"
        .format(**info)
    ,

    codes.QDEVICE_INITIALIZATION_SUCCESS: lambda info:
        "Quorum device '{model}' initialized"
        .format(**info)
    ,

    codes.QDEVICE_INITIALIZATION_ERROR: lambda info:
        "Unable to initialize quorum device '{model}': {reason}"
        .format(**info)
    ,

    codes.QDEVICE_CERTIFICATE_DISTRIBUTION_STARTED:
        "Setting up qdevice certificates on nodes..."
    ,

    codes.QDEVICE_CERTIFICATE_ACCEPTED_BY_NODE: lambda info:
        "{node}: Succeeded"
        .format(**info)
    ,

    codes.QDEVICE_CERTIFICATE_REMOVAL_STARTED:
        "Removing qdevice certificates from nodes..."
    ,

    codes.QDEVICE_CERTIFICATE_REMOVED_FROM_NODE: lambda info:
        "{node}: Succeeded"
        .format(**info)
    ,

    codes.QDEVICE_CERTIFICATE_IMPORT_ERROR: lambda info:
        "Unable to import quorum device certificate: {reason}"
        .format(**info)
    ,

    codes.QDEVICE_CERTIFICATE_SIGN_ERROR: lambda info:
        "Unable to sign quorum device certificate: {reason}"
        .format(**info)
    ,

    codes.QDEVICE_DESTROY_SUCCESS: lambda info:
        "Quorum device '{model}' configuration files removed"
        .format(**info)
    ,

    codes.QDEVICE_DESTROY_ERROR: lambda info:
        "Unable to destroy quorum device '{model}': {reason}"
        .format(**info)
    ,

    codes.QDEVICE_NOT_RUNNING: lambda info:
        "Quorum device '{model}' is not running"
        .format(**info)
    ,

    codes.QDEVICE_GET_STATUS_ERROR: lambda info:
        "Unable to get status of quorum device '{model}': {reason}"
        .format(**info)
    ,

    codes.QDEVICE_USED_BY_CLUSTERS: lambda info:
        "Quorum device is currently being used by cluster(s): {cluster_list}"
        .format(cluster_list=", ".join(info["clusters"]))
    ,

    codes.ID_ALREADY_EXISTS: lambda info:
        "'{id}' already exists"
        .format(**info)
    ,

    codes.ID_BELONGS_TO_UNEXPECTED_TYPE: id_belongs_to_unexpected_type,

    codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT:
        object_with_id_in_unexpected_context
    ,

    codes.ID_NOT_FOUND: id_not_found,

    codes.STONITH_RESOURCES_DO_NOT_EXIST: lambda info:
        "Stonith resource(s) '{stonith_id_list}' do not exist"
        .format(
            stonith_id_list="', '".join(info["stonith_ids"]),
            **info
        )
    ,

    codes.CIB_LOAD_ERROR: "unable to get cib",

    codes.CIB_LOAD_ERROR_SCOPE_MISSING: lambda info:
        "unable to get cib, scope '{scope}' not present in cib"
        .format(**info)
    ,

    codes.CIB_LOAD_ERROR_BAD_FORMAT: lambda info:
       "unable to get cib, {reason}"
       .format(**info)
    ,

    codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION:
        "Unable to load CIB to get guest and remote nodes from it, "
        "those nodes cannot be considered in configuration validation"
    ,

    codes.CIB_CANNOT_FIND_MANDATORY_SECTION: lambda info:
        "Unable to get {section} section of cib"
        .format(**info)
    ,

    codes.CIB_PUSH_ERROR: lambda info:
        "Unable to update cib\n{reason}\n{pushed_cib}"
        .format(**info)
    ,

    codes.CIB_DIFF_ERROR: lambda info:
        "Unable to diff CIB: {reason}\n{cib_new}"
        .format(**info)
    ,

    codes.CIB_SIMULATE_ERROR: lambda info:
        "Unable to simulate changes in CIB{_reason}"
        .format(
            _reason=format_optional(info["reason"], ": {0}"),
            **info
        )
    ,

    codes.CIB_PUSH_FORCED_FULL_DUE_TO_CRM_FEATURE_SET: lambda info:
        (
            "Replacing the whole CIB instead of applying a diff, a race "
            "condition may happen if the CIB is pushed more than once "
            "simultaneously. To fix this, upgrade pacemaker to get "
            "crm_feature_set at least {required_set}, current is {current_set}."
        ).format(**info)
    ,

    codes.CIB_SAVE_TMP_ERROR: lambda info:
        "Unable to save CIB to a temporary file: {reason}"
        .format(**info)
    ,

    codes.CRM_MON_ERROR: lambda info:
        "error running crm_mon, is pacemaker running?{_reason}"
        .format(
            _reason=(
                ("\n" + "\n".join(indent(info["reason"].strip().splitlines())))
                if info["reason"].strip()
                else ""
            ),
            **info
        )
    ,

    codes.BAD_CLUSTER_STATE_FORMAT:
        "cannot load cluster status, xml does not conform to the schema"
    ,

    codes.WAIT_FOR_IDLE_NOT_SUPPORTED:
        "crm_resource does not support --wait, please upgrade pacemaker"
    ,

    codes.WAIT_FOR_IDLE_NOT_LIVE_CLUSTER:
        "Cannot use '-f' together with '--wait'"
    ,

    codes.WAIT_FOR_IDLE_TIMED_OUT: lambda info:
        "waiting timeout\n\n{reason}"
        .format(**info)
    ,

    codes.WAIT_FOR_IDLE_ERROR: lambda info:
        "{reason}"
        .format(**info)
    ,

    codes.RESOURCE_BUNDLE_ALREADY_CONTAINS_A_RESOURCE: lambda info:
        (
            "bundle '{bundle_id}' already contains resource '{resource_id}'"
            ", a bundle may contain at most one resource"
        ).format(**info)
    ,

    codes.RESOURCE_CLEANUP_ERROR: lambda info:
        (
             (
                "Unable to forget failed operations of resource: {resource}"
                "\n{reason}"
             )
             if info["resource"] else
             "Unable to forget failed operations of resources\n{reason}"
        ).format(**info)
    ,

    codes.RESOURCE_REFRESH_ERROR: lambda info:
        (
             "Unable to delete history of resource: {resource}\n{reason}"
             if info["resource"] else
             "Unable to delete history of resources\n{reason}"
        ).format(**info)
    ,

    codes.RESOURCE_REFRESH_TOO_TIME_CONSUMING: lambda info:
        (
             "Deleting history of all resources on all nodes will execute more "
             "than {threshold} operations in the cluster, which may "
             "negatively impact the responsiveness of the cluster. "
             "Consider specifying resource and/or node"
       ).format(**info)
    ,

    codes.RESOURCE_OPERATION_INTERVAL_DUPLICATION: lambda info: (
        "multiple specification of the same operation with the same interval:\n"
        +"\n".join([
            "{0} with intervals {1}".format(name, ", ".join(intervals))
            for name, intervals_list in info["duplications"].items()
            for intervals in intervals_list
        ])
    ),

    codes.RESOURCE_OPERATION_INTERVAL_ADAPTED: lambda info:
        (
            "changing a {operation_name} operation interval"
                " from {original_interval}"
                " to {adapted_interval} to make the operation unique"
        ).format(**info)
    ,

    codes.RESOURCE_RUNNING_ON_NODES:  resource_running_on_nodes,

    codes.RESOURCE_DOES_NOT_RUN: lambda info:
        "resource '{resource_id}' is not running on any node"
        .format(**info)
    ,

    codes.RESOURCE_IS_UNMANAGED: lambda info:
        "'{resource_id}' is unmanaged"
        .format(**info)
    ,

    codes.RESOURCE_IS_GUEST_NODE_ALREADY: lambda info:
        "the resource '{resource_id}' is already a guest node"
        .format(**info)
    ,

    codes.MULTIPLE_RESULTS_FOUND: lambda info:
        "more than one {result_type}{search_description} found: {what_found}"
        .format(
            what_found=format_list(info["result_identifier_list"]),
            search_description="" if not info["search_description"]
                else " for '{0}'".format(info["search_description"])
            ,
            result_type=info["result_type"]
        )
    ,

    codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND: lambda info:
        "unable to get local node name from pacemaker: {reason}"
        .format(**info)
    ,

    codes.SERVICE_START_STARTED: partial(service_operation_started, "Starting"),
    codes.SERVICE_START_ERROR: partial(service_operation_error, "start"),
    codes.SERVICE_START_SUCCESS: partial(service_operation_success, "started"),
    codes.SERVICE_START_SKIPPED: partial(service_operation_skipped, "starting"),

    codes.SERVICE_STOP_STARTED: partial(service_operation_started, "Stopping"),
    codes.SERVICE_STOP_ERROR: partial(service_operation_error, "stop"),
    codes.SERVICE_STOP_SUCCESS: partial(service_operation_success, "stopped"),

    codes.SERVICE_ENABLE_STARTED: partial(
        service_operation_started, "Enabling"
    ),
    codes.SERVICE_ENABLE_ERROR: partial(service_operation_error, "enable"),
    codes.SERVICE_ENABLE_SUCCESS: partial(service_operation_success, "enabled"),
    codes.SERVICE_ENABLE_SKIPPED: partial(
        service_operation_skipped, "enabling"
    ),

    codes.SERVICE_DISABLE_STARTED:
        partial(service_operation_started, "Disabling")
     ,
    codes.SERVICE_DISABLE_ERROR: partial(service_operation_error, "disable"),
    codes.SERVICE_DISABLE_SUCCESS: partial(
        service_operation_success, "disabled"
    ),

    codes.SERVICE_KILL_ERROR: lambda info:
        "Unable to kill {_service_list}: {reason}"
        .format(
            _service_list=", ".join(info["services"]),
            **info
        )
    ,

    codes.SERVICE_KILL_SUCCESS: lambda info:
        "{_service_list} killed"
        .format(
            _service_list=", ".join(info["services"]),
            **info
        )
    ,

    codes.UNABLE_TO_GET_AGENT_METADATA: lambda info:
        (
            "Agent '{agent}' is not installed or does not provide valid"
            " metadata: {reason}"
        ).format(**info)
    ,

    codes.INVALID_RESOURCE_AGENT_NAME: lambda info:
        (
            "Invalid resource agent name '{name}'."
            " Use standard:provider:type when standard is 'ocf' or"
            " standard:type otherwise."
            " List of standards and providers can be obtained by using commands"
            " 'pcs resource standards' and 'pcs resource providers'"
        )
        .format(**info)
    ,

    codes.INVALID_STONITH_AGENT_NAME: lambda info:
        (
            "Invalid stonith agent name '{name}'."
            " List of agents can be obtained by using command"
            " 'pcs stonith list'. Do not use the 'stonith:' prefix. Agent name"
            " cannot contain the ':' character."
        )
        .format(**info)
    ,

    codes.AGENT_NAME_GUESS_FOUND_MORE_THAN_ONE: lambda info:
        (
            "Multiple agents match '{agent}'"
            ", please specify full name: {possible_agents_str}"
        ).format(**info)
    ,

    codes.AGENT_NAME_GUESS_FOUND_NONE: lambda info:
        "Unable to find agent '{agent}', try specifying its full name"
        .format(**info)
    ,

    codes.AGENT_NAME_GUESSED: lambda info:
        "Assumed agent name '{guessed_name}' (deduced from '{entered_name}')"
        .format(**info)
    ,

    codes.OMITTING_NODE: lambda info:
        "Omitting node '{node}'"
        .format(**info)
    ,

    codes.SBD_CHECK_STARTED: "Running SBD pre-enabling checks...",

    codes.SBD_CHECK_SUCCESS: lambda info:
        "{node}: SBD pre-enabling checks done"
        .format(**info)
    ,

    codes.SBD_CONFIG_DISTRIBUTION_STARTED: "Distributing SBD config...",

    codes.SBD_CONFIG_ACCEPTED_BY_NODE: lambda info:
        "{node}: SBD config saved"
        .format(**info)
    ,

    codes.UNABLE_TO_GET_SBD_CONFIG: lambda info:
        "Unable to get SBD configuration from node '{node}'{reason_suffix}"
        .format(
            reason_suffix=format_optional(info["reason"], ": {0}"),
            **info
        )
    ,

    codes.SBD_ENABLING_STARTED: lambda info:
        "Enabling SBD service..."
        .format(**info)
    ,

    codes.SBD_DISABLING_STARTED: "Disabling SBD service...",

    codes.SBD_DEVICE_INITIALIZATION_STARTED: lambda info:
        "Initializing device{_s} {_device_list}..."
        .format(
            _s=("s" if len(info["device_list"]) > 1 else ""),
            _device_list=format_list(info["device_list"])
        )
    ,

    codes.SBD_DEVICE_INITIALIZATION_SUCCESS: lambda info:
        "{_device_pl} initialized successfully"
        .format(
            _device_pl=format_plural(info["device_list"], "Device")
        )
    ,

    codes.SBD_DEVICE_INITIALIZATION_ERROR: lambda info:
        (
            "Initialization of device{_s} {_device_list} failed: {reason}"
        ).format(
            _s=("s" if len(info["device_list"]) > 1 else ""),
            _device_list=format_list(info["device_list"]),
            **info
        )
    ,

    codes.SBD_DEVICE_LIST_ERROR: lambda info:
        "Unable to get list of messages from device '{device}': {reason}"
        .format(**info)
    ,

    codes.SBD_DEVICE_MESSAGE_ERROR: lambda info:
        "Unable to set message '{message}' for node '{node}' on device "
        "'{device}': {reason}"
        .format(**info)
    ,

    codes.SBD_DEVICE_DUMP_ERROR: lambda info:
        "Unable to get SBD headers from device '{device}': {reason}"
        .format(**info)
    ,

    codes.FILES_DISTRIBUTION_STARTED: lambda info:
        "Sending {_description}{_where}".format(
            _where=(
                "" if not info["node_list"]
                else " to " + format_list(info["node_list"])
            ),
            _description=format_list(info["file_list"])
        )
    ,

    codes.FILES_DISTRIBUTION_SKIPPED: lambda info:
        (
            "Distribution of {_files} to {_nodes} was skipped because "
            "{_reason}. Please, distribute the file(s) manually."
        ).format(
            _files=format_list(info["file_list"]),
            _nodes=format_list(info["node_list"]),
            _reason=skip_reason_to_string(info["reason_type"])
        )
    ,

    codes.CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_FOR_NEW_GROUP: lambda info:
        (
            "Group '{group_id}' does not exist and therefore does not contain "
            "'{adjacent_resource_id}' resource to put resources next to"
        )
        .format(**info)
    ,
    codes.CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP: lambda info:
        (
            "There is no resource '{adjacent_resource_id}' in the group "
            "'{group_id}', cannot put resources next to it in the group"
        )
        .format(**info)
    ,
    codes.CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP: lambda info:
        "{_resources} already exist{_s} in '{group_id}'"
        .format(
            _resources=format_list(info["resource_list"]),
            _s="" if len(info["resource_list"]) > 1 else "s",
            **info
        )
    ,
    codes.CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF: lambda info:
        "Cannot put resource '{resource_id}' next to itself".format(**info)
    ,
    codes.CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE: lambda info:
        "Resources specified more than once: {_resources}"
        .format(
            _resources=format_list(info["resource_list"]),
        )
    ,
    codes.CANNOT_GROUP_RESOURCE_NO_RESOURCES: lambda info:
        "No resources to add"
    ,
    codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE: lambda info:
        (
            "'{resource_id}' is {_type_article} resource, {_type} resources "
            "cannot be put into a group"
        ).format(
            _type_article=type_to_string(info["resource_type"], article=True),
            _type=type_to_string(info["resource_type"], article=False),
            **info
        )
    ,
}
