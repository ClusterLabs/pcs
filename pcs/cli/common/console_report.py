from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
from functools import partial

from pcs.common import report_codes as codes
from collections import Iterable

INSTANCE_SUFFIX = "@{0}"
NODE_PREFIX = "{0}: "

def warn(message):
    sys.stdout.write(format_message(message, "Warning: "))

def format_message(message, prefix):
    return "{0}{1}\n".format(prefix, message)

def error(message):
    sys.stderr.write(format_message(message, "Error: "))
    return SystemExit(1)

def indent(line_list, indent_step=2):
    """
    return line list where each line of input is prefixed by N spaces
    list of string line_list are original lines
    int indent_step is count of spaces for line prefix
    """
    return [
        "{0}{1}".format(" "*indent_step, line) if line else line
        for line in line_list
    ]

def format_optional(value, template):
    return  "" if not value else template.format(value)

def service_operation_started(operation, info):
    return "{operation}{service}{instance_suffix}...".format(
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

def service_opration_success(operation, info):
    return "{node_prefix}{service}{instance_suffix} {operation}".format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        node_prefix=format_optional(info["node"], NODE_PREFIX),
        **info
    )

def service_operation_skipped(operation, info):
    return (
        "{node_prefix}not {operation}{service}{instance_suffix} - {reason}"
    ).format(
        operation=operation,
        instance_suffix=format_optional(info["instance"], INSTANCE_SUFFIX),
        node_prefix=format_optional(info["node"], NODE_PREFIX),
        **info
    )


#Each value (callable taking report_item.info) returns string template.
#Optionaly the template can contain placehodler {force} for next processing.
#Placeholder {force} will be appended if is necessary and if is not presset
CODE_TO_MESSAGE_BUILDER_MAP = {

    codes.COMMON_ERROR: lambda info: info["text"],

    codes.COMMON_INFO: lambda info: info["text"],

    codes.EMPTY_RESOURCE_SET_LIST: "Resource set list is empty",

    codes.REQUIRED_OPTION_IS_MISSING: lambda info:
        "required option '{option_name}' is missing"
        .format(**info)
    ,

    codes.INVALID_OPTION: lambda info:
        "invalid {desc}option '{option_name}', allowed options are: {allowed_values}"
        .format(
            desc=format_optional(info["option_type"], "{0} "),
            allowed_values=", ".join(info["allowed"]),
            **info
        )
    ,

    codes.INVALID_OPTION_VALUE: lambda info:
        "'{option_value}' is not a valid {option_name} value, use {hint}"
        .format(
            hint=(
                ", ".join(info["allowed_values"])
                if (
                    isinstance(info["allowed_values"], Iterable)
                    and
                    not isinstance(info["allowed_values"], "".__class__)
                )
                else info["allowed_values"]
            ),
            **info
        )
    ,

    codes.EMPTY_ID: lambda info:
        "{id_description} cannot be empty"
    .format(**info)
    ,

    codes.INVALID_ID: lambda info:
        (
            "invalid {id_description} '{id}', '{invalid_character}' "
            "is not a valid {desc}character for a {id_description}"
        ).format(
            desc="first " if info["is_first_char"] else "",
            **info
        )
    ,

    codes.INVALID_TIMEOUT_VALUE: lambda info:
        "'{timeout}' is not a valid number of seconds to wait"
        .format(**info)
    ,


    codes.INVALID_SCORE: lambda info:
        "invalid score '{score}', use integer or INFINITY or -INFINITY"
        .format(**info)
    ,


    codes.MULTIPLE_SCORE_OPTIONS: "you cannot specify multiple score options",


    codes.RUN_EXTERNAL_PROCESS_STARTED: lambda info:
        "Running: {command}\n{stdin_part}".format(
            stdin_part=format_optional(
                info["stdin"],
                "--Debug Input Start--\n{0}\n--Debug Input End--\n"
            ),
            **info
        )
    ,

    codes.RUN_EXTERNAL_PROCESS_FINISHED: lambda info:
        (
            "Finished running: {command}\n"
            "Return value: {return_value}\n"
            "--Debug Stdout Start--\n"
            "{stdout}\n"
            "--Debug Stdout End--\n"
            "--Debug Stderr Start--\n"
            "{stderr}\n"
            "--Debug Stderr End--\n"
        ).format(**info)
    ,

    codes.RUN_EXTERNAL_PROCESS_ERROR: lambda info:
        "unable to run command {command}: {reason}"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_STARTED: lambda info:
        "Sending HTTP Request to: {target}\n{data_part}".format(
            data_part=format_optional(
                info["data"],
                "--Debug Input Start--\n{0}\n--Debug Input End--\n"
            ),
            **info
        )
    ,

    codes.NODE_COMMUNICATION_FINISHED: lambda info:
        (
            "Finished calling: {target}\n"
            "Response Code: {response_code}\n"
            "--Debug Response Start--\n"
            "{response_data}\n"
            "--Debug Response End--\n"
        ).format(**info)
    ,

    codes.NODE_COMMUNICATION_NOT_CONNECTED: lambda info:
        "Unable to connect to {node} ({reason})"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_ERROR_NOT_AUTHORIZED: lambda info:
        (
            "Unable to authenticate to {node} ({reason}),"
            " try running 'pcs cluster auth'"
        )
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_ERROR_PERMISSION_DENIED: lambda info:
        "{node}: Permission denied ({reason})"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_ERROR_UNSUPPORTED_COMMAND: lambda info:
        "{node}: Unsupported command ({reason}), try upgrading pcsd"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL: lambda info:
        "{node}: {reason}"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_ERROR: lambda info:
        "Error connecting to {node} ({reason})"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT: lambda info:
        "Unable to connect to {node} ({reason})"
        .format(**info)
    ,

    codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED:
        "Sending updated corosync.conf to nodes..."
    ,

    codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE: lambda info:
        "{node}: Succeeded"
        .format(**info)
    ,

    codes.COROSYNC_CONFIG_DISTRIBUTION_NODE_ERROR: lambda info:
        "{node}: Unable to set corosync config"
        .format(**info)
    ,

    codes.COROSYNC_NOT_RUNNING_CHECK_STARTED:
        "Checking corosync is not running on nodes..."
    ,

    codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR: lambda info:
        "{node}: Unable to check if corosync is not running"
        .format(**info)
    ,

    codes.COROSYNC_NOT_RUNNING_ON_NODE: lambda info:
        "{node}: corosync is not running"
        .format(**info)
    ,

    codes.COROSYNC_RUNNING_ON_NODE: lambda info:
        "{node}: corosync is running"
        .format(**info)
    ,

    codes.COROSYNC_QUORUM_GET_STATUS_ERROR: lambda info:
        "Unable to get quorum status: {reason}"
        .format(**info)
    ,

    codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR: lambda info:
        "Unable to set expected votes: {reason}"
        .format(**info)
    ,

    codes.COROSYNC_CONFIG_RELOADED: "Corosync configuration reloaded",

    codes.COROSYNC_CONFIG_RELOAD_ERROR: lambda info:
        "Unable to reload corosync configuration: {reason}"
        .format(**info)
    ,

    codes.UNABLE_TO_READ_COROSYNC_CONFIG: lambda info:
        "Unable to read {path}: {reason}"
        .format(**info)
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE:
        "Unable to parse corosync config: missing closing brace"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE:
        "Unable to parse corosync config: unexpected closing brace"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF:
        "Unable to parse corosync config"
    ,

    codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE: lambda info:
        "These options cannot be set when the cluster uses a quorum device: {0}"
        .format(", ".join(sorted(info["options_names"])))
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

    codes.CMAN_UNSUPPORTED_COMMAND:
        "This command is not supported on CMAN clusters"
    ,

    codes.ID_ALREADY_EXISTS: lambda info:
        "'{id}' already exists"
        .format(**info)
    ,

    codes.ID_NOT_FOUND: lambda info:
        "{desc}'{id}' does not exist"
        .format(
            desc=format_optional(info["id_description"], "{0} "),
            **info
        )
    ,

    codes.RESOURCE_DOES_NOT_EXIST: lambda info:
        "Resource '{resource_id}' does not exist"
        .format(**info)
    ,

    codes.CIB_ACL_ROLE_IS_ALREADY_ASSIGNED_TO_TARGET: lambda info:
        "Role '{role_id}' is already asigned to '{target_id}'"
        .format(**info)
    ,

    codes.CIB_ACL_ROLE_IS_NOT_ASSIGNED_TO_TARGET: lambda info:
        "Role '{role_id}' is not assigned to '{target_id}'"
        .format(**info)
    ,

    codes.CIB_ACL_TARGET_ALREADY_EXISTS: lambda info:
        "'{target_id}' already exists"
        .format(**info)
    ,

    codes.CIB_LOAD_ERROR: "unable to get cib",

    codes.CIB_LOAD_ERROR_SCOPE_MISSING: lambda info:
        "unable to get cib, scope '{scope}' not present in cib"
        .format(**info)
    ,

    codes.CIB_LOAD_ERROR_BAD_FORMAT:
       "unable to get cib, xml does not conform to the schema"
    ,

    codes.CIB_CANNOT_FIND_MANDATORY_SECTION: lambda info:
        "Unable to get {section} section of cib"
        .format(**info)
    ,

    codes.CIB_PUSH_ERROR: lambda info:
        "Unable to update cib\n{reason}\n{pushed_cib}"
        .format(**info)
    ,

    codes.CRM_MON_ERROR:
        "error running crm_mon, is pacemaker running?"
    ,

    codes.BAD_CLUSTER_STATE_FORMAT:
        "cannot load cluster status, xml does not conform to the schema"
    ,

    codes.RESOURCE_WAIT_NOT_SUPPORTED:
        "crm_resource does not support --wait, please upgrade pacemaker"
    ,

    codes.RESOURCE_WAIT_TIMED_OUT: lambda info:
        "waiting timeout\n\n{reason}"
        .format(**info)
    ,

    codes.RESOURCE_WAIT_ERROR: lambda info:
        "{reason}"
        .format(**info)
    ,

    codes.RESOURCE_CLEANUP_ERROR: lambda info:
        (
             "Unable to cleanup resource: {resource}\n{reason}"
             if info["resource"] else
             "Unexpected error occured. 'crm_resource -C' error:\n{reason}"
        ).format(**info)
    ,

    codes.RESOURCE_CLEANUP_TOO_TIME_CONSUMING: lambda info:
        (
             "Cleaning up all resources on all nodes will execute more "
             "than {threshold} operations in the cluster, which may "
             "negatively impact the responsiveness of the cluster. "
             "Consider specifying resource and/or node"
       ).format(**info)
    ,

    codes.NODE_NOT_FOUND: lambda info:
        "node '{node}' does not appear to exist in configuration"
        .format(**info)
    ,

    codes.PACEMAKER_LOCAL_NODE_NAME_NOT_FOUND: lambda info:
        "unable to get local node name from pacemaker: {reason}"
        .format(**info)
    ,

    codes.RRP_ACTIVE_NOT_SUPPORTED:
        "using a RRP mode of 'active' is not supported or tested"
    ,

    codes.IGNORED_CMAN_UNSUPPORTED_OPTION: lambda info:
        "{option_name} ignored as it is not supported on CMAN clusters"
        .format(**info)
    ,

    codes.NON_UDP_TRANSPORT_ADDR_MISMATCH:
        "--addr0 and --addr1 can only be used with --transport=udp"
    ,

    codes.CMAN_UDPU_RESTART_REQUIRED: (
        "Using udpu transport on a CMAN cluster,"
        " cluster restart is required after node add or remove"
    ),

    codes.CMAN_BROADCAST_ALL_RINGS: (
        "Enabling broadcast for all rings as CMAN does not support"
        " broadcast in only one ring"
    ),

    codes.SERVICE_START_STARTED: partial(service_operation_started, "Starting"),
    codes.SERVICE_START_ERROR: partial(service_operation_error, "start"),
    codes.SERVICE_START_SUCCESS: partial(service_opration_success, "started"),
    codes.SERVICE_START_SKIPPED: partial(service_operation_skipped, "starting"),

    codes.SERVICE_STOP_STARTED: partial(service_operation_started, "Stopping"),
    codes.SERVICE_STOP_ERROR: partial(service_operation_error, "stop"),
    codes.SERVICE_STOP_SUCCESS: partial(service_opration_success, "stopped"),

    codes.SERVICE_ENABLE_STARTED: partial(
        service_operation_started, "Enabling"
    ),
    codes.SERVICE_ENABLE_ERROR: partial(service_operation_error, "enable"),
    codes.SERVICE_ENABLE_SUCCESS: partial(service_opration_success, "enabled"),
    codes.SERVICE_ENABLE_SKIPPED: partial(
        service_operation_skipped, "enabling"
    ),

    codes.SERVICE_DISABLE_STARTED:
        partial(service_operation_started, "Disabling")
     ,
    codes.SERVICE_DISABLE_ERROR: partial(service_operation_error, "disable"),
    codes.SERVICE_DISABLE_SUCCESS: partial(service_opration_success, "disabled"),

    codes.SERVICE_KILL_ERROR: lambda info:
        "Unable to kill {service_list}: {reason}"
        .format(
            service_list=", ".join(info["services"]),
            **info
        )
    ,

    codes.SERVICE_KILL_SUCCESS: lambda info:
        "{services_list} killed"
        .format(
            service_list=", ".join(info["services"]),
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
            " Use standard:provider:type or standard:type."
            " List of standards and providers can be obtained by using commands"
            " 'pcs resource standards' and 'pcs resource providers'"
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

    codes.INVALID_RESPONSE_FORMAT: lambda info:
        "{node}: Invalid format of response"
        .format(**info)
    ,

    codes.SBD_NOT_INSTALLED: lambda info:
        "SBD is not installed on node '{node}'"
        .format(**info)
    ,

    codes.WATCHDOG_NOT_FOUND: lambda info:
        "Watchdog '{watchdog}' does not exist on node '{node}'"
        .format(**info)
    ,

    codes.WATCHDOG_INVALID: lambda info:
        "Watchdog path '{watchdog}' is invalid."
        .format(**info)
    ,

    codes.UNABLE_TO_GET_SBD_STATUS: lambda info:
        "Unable to get status of SBD from node '{node}'{reason_suffix}"
        .format(
            reason_suffix=format_optional(info["reason"], ": {0}"),
            **info
        )
    ,

    codes.CLUSTER_RESTART_REQUIRED_TO_APPLY_CHANGES:
        "Cluster restart is required in order to apply these changes."
    ,

    codes.CIB_ALERT_RECIPIENT_ALREADY_EXISTS: lambda info:
        "Recipient '{recipient}' in alert '{alert}' already exists"
        .format(**info)
    ,

    codes.CIB_ALERT_RECIPIENT_VALUE_INVALID: lambda info:
        "Recipient value '{recipient}' is not valid."
        .format(**info)
    ,

    codes.CIB_ALERT_NOT_FOUND: lambda info:
        "Alert '{alert}' not found."
        .format(**info)
    ,

    codes.CIB_UPGRADE_SUCCESSFUL: lambda info:
        "CIB has been upgraded to the latest schema version."
        .format(**info)
    ,

    codes.CIB_UPGRADE_FAILED: lambda info:
        "Upgrading of CIB to the latest schema failed: {reason}"
        .format(**info)
    ,

    codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION: lambda info:
        (
            "Unable to upgrade CIB to required schema version"
            " {required_version} or higher. Current version is"
            " {current_version}. Newer version of pacemaker is needed."
        )
        .format(**info)
    ,

    codes.FILE_ALREADY_EXISTS: lambda info:
        "{node_prefix}{role_prefix}file {file_path} already exists"
        .format(
             node_prefix=format_optional(info["node"], NODE_PREFIX),
            role_prefix=format_optional(info["file_role"], "{0} "),
            **info
        )
    ,

    codes.FILE_DOES_NOT_EXIST: lambda info:
        "{file_role} file {file_path} does not exist"
        .format(**info)
    ,

    codes.FILE_IO_ERROR: lambda info:
        "unable to {operation} {file_role}{path_desc}: {reason}"
        .format(
            path_desc=format_optional(info["file_path"], " '{0}'"),
            **info
        )
    ,

    codes.UNABLE_TO_DETERMINE_USER_UID: lambda info:
        "Unable to determine uid of user '{user}'"
        .format(**info)
    ,

    codes.UNABLE_TO_DETERMINE_GROUP_GID: lambda info:
        "Unable to determine gid of group '{group}'"
        .format(**info)
    ,

    codes.UNSUPPORTED_OPERATION_ON_NON_SYSTEMD_SYSTEMS:
        "unsupported operation on non systemd systems"
    ,

    codes.LIVE_ENVIRONMENT_REQUIRED: lambda info:
        "This command does not support {forbidden_options}"
        .format(forbidden_options=", ".join(info["forbidden_options"]))
    ,

    codes.COROSYNC_QUORUM_CANNOT_DISABLE_ATB_DUE_TO_SBD: lambda info:
        "unable to disable auto_tie_breaker: SBD fencing will have no effect"
        .format(**info)
    ,

    codes.SBD_REQUIRES_ATB: lambda info:
        "auto_tie_breaker quorum option will be enabled to make SBD fencing "
        "effective. Cluster has to be offline to be able to make this change."
    ,

    codes.CLUSTER_CONF_LOAD_ERROR_INVALID_FORMAT: lambda info:
        "unable to get cluster.conf: {reason}"
        .format(**info)
    ,

    codes.CLUSTER_CONF_READ_ERROR: lambda info:
        "Unable to read {path}: {reason}"
        .format(**info)
    ,
}
