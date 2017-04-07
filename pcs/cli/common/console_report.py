from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from collections import Iterable
from functools import partial
import sys

from pcs.common import report_codes as codes
from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE
from pcs.common.tools import is_string

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

def format_optional(value, template, empty_case=""):
    return empty_case if not value else template.format(value)

def format_fencing_level_target(target_type, target_value):
    if target_type == TARGET_TYPE_ATTRIBUTE:
        return "{0}={1}".format(target_value[0], target_value[1])
    return target_value

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

def id_belongs_to_unexpected_type(info):
    translate_expected = {
        "acl_group": "an acl group",
        "acl_target": "an acl user",
        "group": "a group",
    }
    return "'{id}' is not {expected_type}".format(
        id=info["id"],
        expected_type="/".join([
            translate_expected.get(tag, "{0}".format(tag))
            for tag in info["expected_types"]
        ]),
    )

def id_not_found(info):
    desc = format_optional(info["id_description"], "{0} ")
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
                node_list=", ".join(
                    ["'{0}'".format(node) for node in node_list]
                )
            )
            for run_type, node_list in state_info.items()
        ]))
    )


#Each value (a callable taking report_item.info) returns a message.
#Force text will be appended if necessary.
#If it is necessary to put the force text inside the string then the callable
#must take the force_text parameter.
CODE_TO_MESSAGE_BUILDER_MAP = {

    codes.COMMON_ERROR: lambda info: info["text"],

    codes.COMMON_INFO: lambda info: info["text"],

    codes.EMPTY_RESOURCE_SET_LIST: "Resource set list is empty",

    codes.REQUIRED_OPTION_IS_MISSING: lambda info:
        "required {desc}option{s} {option_names_list} {are} missing"
        .format(
            desc=format_optional(info["option_type"], "{0} "),
            option_names_list=", ".join(sorted([
                "'{0}'".format(name)
                for name in info["option_names"]
            ])),
            s=("s" if len(info["option_names"]) > 1 else ""),
            are=(
                "are" if len(info["option_names"]) > 1
                else "is"
            )
        )
    ,

    codes.PREREQUISITE_OPTION_IS_MISSING: lambda info:
        (
            "If {opt_desc}option '{option_name}' is specified, "
            "{pre_desc}option '{prerequisite_name}' must be specified as well"
        ).format(
            opt_desc=format_optional(info.get("option_type"), "{0} "),
            pre_desc=format_optional(info.get("prerequisite_type"), "{0} "),
            **info
        )
    ,

    codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING: lambda info:
        "{desc}option {option_names_list} has to be specified"
        .format(
            desc=format_optional(info.get("option_type"), "{0} "),
            option_names_list=" or ".join(sorted([
                "'{0}'".format(name)
                for name in info["option_names"]
            ])),
        )
    ,

    codes.INVALID_OPTION: lambda info:
        (
            "invalid {desc}option{s} {option_names_list},"
            " allowed option{are} {allowed_values}"
        ).format(
            desc=format_optional(info["option_type"], "{0} "),
            allowed_values=", ".join(sorted(info["allowed"])),
            option_names_list=", ".join(sorted([
                "'{0}'".format(name)
                for name in info["option_names"]
            ])),
            s=("s:" if len(info["option_names"]) > 1 else ""),
            are=("s are:" if len(info["allowed"]) > 1 else " is"),
            **info
        )
    ,

    codes.INVALID_OPTION_VALUE: lambda info:
        #value on key "allowed_values" is overloaded:
        # * it can be a list - then it express possible option values
        # * it can be a string - then it is verbal description of value
        "'{option_value}' is not a valid {option_name} value, use {hint}"
        .format(
            hint=(
                ", ".join(sorted(info["allowed_values"])) if (
                    isinstance(info["allowed_values"], Iterable)
                    and
                    not is_string(info["allowed_values"])
                ) else info["allowed_values"]
            ),
            **info
        )
    ,

    codes.INVALID_OPTION_TYPE: lambda info:
        #value on key "allowed_types" is overloaded:
        # * it can be a list - then it express possible option types
        # * it can be a string - then it is verbal description of the type
        "specified {option_name} is not valid, use {hint}"
        .format(
            hint=(
                ", ".join(sorted(info["allowed_types"])) if (
                    isinstance(info["allowed_types"], Iterable)
                    and
                    not is_string(info["allowed_types"])
                ) else info["allowed_types"]
            ),
            **info
        )
    ,

    codes.MUTUALLY_EXCLUSIVE_OPTIONS: lambda info:
        # "{desc}options {option_names} are muttually exclusive".format(
        "Only one of {desc}options {option_names} can be used".format(
            desc=format_optional(info["option_type"], "{0} "),
            option_names = ", ".join([
                "'{0}'".format(name)
                for name in sorted(info["option_names"])[:-1]
            ]) + " and '{0}'".format(sorted(info["option_names"])[-1])
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
        "Running: {command}\nEnvironment:{env_part}\n{stdin_part}".format(
            stdin_part=format_optional(
                info["stdin"],
                "--Debug Input Start--\n{0}\n--Debug Input End--\n"
            ),
            env_part=(
                "" if not info["environment"] else "\n" + "\n".join([
                    "  {0}={1}".format(key, val)
                    for key, val in sorted(info["environment"].items())
                ])
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

    codes.NODE_COMMUNICATION_DEBUG_INFO: lambda info:
        (
            "Communication debug info for calling: {target}\n"
            "--Debug Communication Info Start--\n"
            "{data}\n"
            "--Debug Communication Info End--\n"
        ).format(**info)
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

    codes.NODE_COMMUNICATION_ERROR_TIMED_OUT: lambda info:
        "{node}: Connection timeout ({reason})"
        .format(**info)
    ,

    codes.NODE_COMMUNICATION_PROXY_IS_SET:
        "Proxy is set in environment variables, try disabling it"
    ,

    codes.CANNOT_ADD_NODE_IS_IN_CLUSTER: lambda info:
        "cannot add the node '{node}' because it is in a cluster"
        .format(**info)
    ,

    codes.CANNOT_ADD_NODE_IS_RUNNING_SERVICE: lambda info:
        (
            "cannot add the node '{node}' because it is running service"
            " '{service}'{guess}"
        ).format(
            guess=(
                "" if info["service"] not in ["pacemaker", "pacemaker_remote"]
                else " (is not the node already in a cluster?)"
            ),
            **info
        )
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

    codes.ID_BELONGS_TO_UNEXPECTED_TYPE: id_belongs_to_unexpected_type,

    codes.ID_NOT_FOUND: id_not_found,

    codes.STONITH_RESOURCES_DO_NOT_EXIST: lambda info:
        "Stonith resource(s) '{stonith_id_list}' do not exist"
        .format(
            stonith_id_list="', '".join(info["stonith_ids"]),
            **info
        )
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

    codes.CIB_FENCING_LEVEL_ALREADY_EXISTS: lambda info:
        (
            "Fencing level for '{target}' at level '{level}' "
            "with device(s) '{device_list}' already exists"
        ).format(
            device_list=",".join(info["devices"]),
            target=format_fencing_level_target(
                info["target_type"], info["target_value"]
            ),
            **info
        )
    ,

    codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST: lambda info:
        "Fencing level {part_target}{part_level}{part_devices}does not exist"
        .format(
            part_target=(
                "for '{0}' ".format(format_fencing_level_target(
                    info["target_type"], info["target_value"]
                ))
                if info["target_type"] and info["target_value"]
                else ""
            ),
            part_level=format_optional(info["level"], "at level '{0}' "),
            part_devices=format_optional(
                ",".join(info["devices"]) if info["devices"] else "",
                "with device(s) '{0}' "
            )
        )
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

    codes.CIB_SAVE_TMP_ERROR: lambda info:
        "Unable to save CIB to a temporary file: {reason}"
        .format(**info)
    ,

    codes.CRM_MON_ERROR:
        "error running crm_mon, is pacemaker running?"
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

    codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED: lambda info:
        (
            "Resource '{resource_id}' has no enabled monitor operations."
            " Re-run with '--monitor' to enable them."
        )
        .format(**info)
    ,

    codes.NODE_NOT_FOUND: lambda info:
        "Node '{node}' does not appear to exist in configuration"
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
        "Initializing device(s) {devices}..."
        .format(devices=", ".join(info["device_list"]))
    ,

    codes.SBD_DEVICE_INITIALIZATION_SUCCESS:
        "Device(s) initialized successfuly",

    codes.SBD_DEVICE_INITIALIZATION_ERROR: lambda info:
        "Initialization of device(s) failed: {reason}"
        .format(**info)
    ,

    codes.SBD_DEVICE_LIST_ERROR: lambda info:
        "Unable to get list of messages from device '{device}': {reason}"
        .format(**info)
    ,

    codes.SBD_DEVICE_MESSAGE_ERROR: lambda info:
        "Unable to set message '{message}' for node '{node}' on device "
        "'{device}'"
        .format(**info)
    ,

    codes.SBD_DEVICE_DUMP_ERROR: lambda info:
        "Unable to get SBD headers from device '{device}': {reason}"
        .format(**info)
    ,

    codes.SBD_DEVICE_PATH_NOT_ABSOLUTE: lambda info:
        "Device path '{device}'{on_node} is not absolute"
        .format(
            on_node=format_optional(
                info["node"], " on node '{0}'".format(info["node"])
            ),
            **info
        )
    ,

    codes.SBD_DEVICE_DOES_NOT_EXIST: lambda info:
        "{node}: device '{device}' not found"
        .format(**info)
    ,

    codes.SBD_DEVICE_IS_NOT_BLOCK_DEVICE: lambda info:
        "{node}: device '{device}' is not a block device"
        .format(**info)
    ,

    codes.INVALID_RESPONSE_FORMAT: lambda info:
        "{node}: Invalid format of response"
        .format(**info)
    ,

    codes.SBD_NO_DEVICE_FOR_NODE: lambda info:
        "No device defined for node '{node}'"
        .format(**info)
    ,

    codes.SBD_TOO_MANY_DEVICES_FOR_NODE: lambda info:
        (
            "More than {max_devices} devices defined for node '{node}' "
            "(devices: {devices})"
        )
        .format(devices=", ".join(info["device_list"]), **info)
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

    codes.CIB_UPGRADE_SUCCESSFUL:
        "CIB has been upgraded to the latest schema version."
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

    codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE:
        "Node(s) must be specified if -f is used"
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
