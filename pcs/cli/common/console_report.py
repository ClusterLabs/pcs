# pylint: disable=too-many-lines, no-name-in-module
# no-name-in-module diabled because of issue in Travis CI:a
#   pcs/cli/common/console_report.py:3:0: E0611: No name 'Iterable' in module
#   'collections' (no-name-in-module)

from collections import defaultdict, Iterable
from functools import partial
import sys

from pcs.common import (
    env_file_role_codes,
    report_codes as codes,
)

from pcs.common.fencing_topology import TARGET_TYPE_ATTRIBUTE

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
_file_role_translation = {
    env_file_role_codes.BOOTH_CONFIG: "Booth configuration",
    env_file_role_codes.BOOTH_KEY: "Booth key",
    env_file_role_codes.COROSYNC_AUTHKEY: "Corosync authkey",
    env_file_role_codes.PACEMAKER_AUTHKEY: "Pacemaker authkey",
    env_file_role_codes.PCSD_ENVIRONMENT_CONFIG: "pcsd configuration",
    env_file_role_codes.PCSD_SSL_CERT: "pcsd SSL certificate",
    env_file_role_codes.PCSD_SSL_KEY: "pcsd SSL key",
    env_file_role_codes.PCS_SETTINGS_CONF: "pcs configuration",
}

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

def stdout_stderr_to_string(stdout, stderr, prefix=""):
    new_lines = [prefix] if prefix else []
    for line in stdout.splitlines() + stderr.splitlines():
        if line.strip():
            new_lines.append(line)
    return "\n".join(new_lines)

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

def invalid_options(info):
    template = "invalid {_desc}option{_plural_options} {_option_names_list},"
    if not info["allowed"] and not info["allowed_patterns"]:
        template += " there are no options allowed"
    elif not info["allowed_patterns"]:
        template += " allowed option{_plural_allowed} {_allowed_values}"
    elif not info["allowed"]:
        template += (
            " allowed are options matching patterns: {_allowed_patterns_values}"
        )
    else:
        template += (
            " allowed option{_plural_allowed} {_allowed_values}"
            " and"
            " options matching patterns: {_allowed_patterns_values}"
        )
    return template.format(
        _desc=format_optional(info["option_type"], "{0} "),
        _allowed_values=format_list(info["allowed"]),
        _allowed_patterns_values=format_list(info["allowed_patterns"]),
        _option_names_list=format_list(info["option_names"]),
        _plural_options=("s:" if len(info["option_names"]) > 1 else ""),
        _plural_allowed=("s are:" if len(info["allowed"]) > 1 else " is"),
        **info
    )

def invalid_option_value(info):
    if info["cannot_be_empty"]:
        template = "{option_name} cannot be empty"
    elif info["forbidden_characters"]:
        template = (
            "{option_name} cannot contain {forbidden_characters} characters"
        )
    else:
        template = "'{option_value}' is not a valid {option_name} value"
    if info["allowed_values"]:
        template += ", use {_hint}"
    return template.format(
        _hint=(
            # "allowed_values" value is overloaded:
            # * it can be a list -> it expreses possible option values
            # * it can be a string -> it is a textual description of the value
            format_list(info["allowed_values"])
            if is_iterable_not_str(info["allowed_values"])
            else info["allowed_values"]
        ),
        **info
    )

def corosync_bad_node_addresses_count(info):
    if info["min_count"] == info["max_count"]:
        template = (
            "{max_count} address{_s_allowed} must be specified for a node, "
            "{actual_count} address{_s_specified} specified{_node_desc}"
        )
    else:
        template = (
            "At least {min_count} and at most {max_count} address{_s_allowed} "
            "must be specified for a node, {actual_count} "
            "address{_s_specified} specified{_node_desc}"
        )
    node_template = " for node '{}'"
    return template.format(
        _node_desc=(
            node_template.format(info["node_name"])
            if "node_name" in info
            else
            node_template.format(info["node_index"])
            if "node_index" in info
            else ""
        ),
        _s_allowed=("es" if info["max_count"] > 1 else ""),
        _s_specified=("es" if info["actual_count"] > 1 else ""),
        **info
    )

def corosync_node_address_count_mismatch(info):
    count_node = defaultdict(list)
    for node_name, count in info["node_addr_count"].items():
        count_node[count].append(node_name)
    parts = ["All nodes must have the same number of addresses"]
    # List most common number of addresses first.
    for count, nodes in sorted(
        count_node.items(),
        key=lambda pair: len(pair[1]),
        reverse=True
    ):
        parts.append(
            "node{s} {nodes} {have} {count} address{es}".format(
            s=("s" if len(nodes) > 1 else ""),
            nodes=format_list(nodes),
            have=("have" if len(nodes) > 1 else "has"),
            count=count,
            es=("es" if count > 1 else "")
        ))
    return "; ".join(parts)

def corosync_link_does_not_exist_cannot_update(info):
    template = "Cannot set options for non-existent link '{link_number}'"
    if info.get("existing_link_list"):
        template += ", existing links: {_link_list}"
        return template.format(
            _link_list=format_list(info["existing_link_list"]),
            **info
        )
    if info.get("link_count"):
        template += ", {link_count} link{_s_are} defined starting with link 0"
        return template.format(
            _s_are=("s are" if info["link_count"] > 1 else " is"),
            **info
        )
    return template.format(**info)

def service_version_mismatch(info):
    version_host = defaultdict(list)
    for host_name, version in info["hosts_version"].items():
        version_host[version].append(host_name)
    parts = [
        "Hosts do not have the same version of '{}'".format(info["service"])
    ]
    # List most common versions first.
    for version, hosts in sorted(
        version_host.items(),
        key=lambda pair: len(pair[1]),
        reverse=True
    ):
        parts.append(
            "host{s} {hosts} {have} version {version}".format(
            s=("s" if len(hosts) > 1 else ""),
            hosts=format_list(hosts),
            have=("have" if len(hosts) > 1 else "has"),
            version=version
        ))
    return "; ".join(parts)

def resource_move_ban_clear_master_resource_not_promotable(info):
    return (
        "when specifying --master you must use the promotable clone id{_id}"
        .format(
            _id=format_optional(info["promotable_id"], " ({0})"),
        )
    )

def resource_move_ban_pcmk_success(info):
    new_lines = []
    for line in info["stdout"].splitlines() + info["stderr"].splitlines():
        if not line.strip():
            continue
        line = line.replace(
            "WARNING: Creating rsc_location constraint",
            "Warning: Creating location constraint"
        )
        line = line.replace(
            " using the clear option or by editing the CIB with an "
                "appropriate tool",
            ""
        )
        new_lines.append(line)
    return "\n".join(new_lines)

def build_node_description(node_types):
    if not node_types:
        return  "Node"

    label = "{0} node".format

    if isinstance(node_types, str):
        return label(node_types)

    if len(node_types) == 1:
        return label(node_types[0])

    return "nor " + " or ".join([label(ntype) for ntype in node_types])

def format_list(item_list, optional_transformations=None):
    if not optional_transformations:
        optional_transformations = {}

    return ", ".join(sorted([
        "'{0}'".format(optional_transformations.get(item, item))
        for item in item_list
    ]))

#Each value (a callable taking report_item.info) returns a message.
#Force text will be appended if necessary.
#If it is necessary to put the force text inside the string then the callable
#must take the force_text parameter.
CODE_TO_MESSAGE_BUILDER_MAP = {

    codes.EMPTY_RESOURCE_SET_LIST: "Resource set list is empty",

    codes.REQUIRED_OPTIONS_ARE_MISSING: lambda info:
        "required {desc}option{s} {option_names_list} {are} missing"
        .format(
            desc=format_optional(info["option_type"], "{0} "),
            option_names_list=format_list(info["option_names"]),
            s=("s" if len(info["option_names"]) > 1 else ""),
            are=(
                "are" if len(info["option_names"]) > 1
                else "is"
            )
        )
    ,

    codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL: lambda info:
        (
            "If {_opt_desc}option '{option_name}' is enabled, "
            "{_pre_desc}option '{prerequisite_name}' must be enabled as well"
        ).format(
            _opt_desc=format_optional(info.get("option_type"), "{0} "),
            _pre_desc=format_optional(info.get("prerequisite_type"), "{0} "),
            **info
        )
    ,

    codes.PREREQUISITE_OPTION_MUST_BE_DISABLED: lambda info:
        (
            "If {_opt_desc}option '{option_name}' is enabled, "
            "{_pre_desc}option '{prerequisite_name}' must be disabled"
        ).format(
            _opt_desc=format_optional(info.get("option_type"), "{0} "),
            _pre_desc=format_optional(info.get("prerequisite_type"), "{0} "),
            **info
        )
    ,

    codes.PREREQUISITE_OPTION_MUST_NOT_BE_SET: lambda info:
        (
            "Cannot set {_opt_desc}option '{option_name}' because "
            "{_pre_desc}option '{prerequisite_name}' is already set"
        ).format(
            _opt_desc=format_optional(info.get("option_type"), "{0} "),
            _pre_desc=format_optional(info.get("prerequisite_type"), "{0} "),
            **info
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

    codes.INVALID_OPTIONS: invalid_options,

    codes.INVALID_OPTION_VALUE: invalid_option_value,

    codes.INVALID_OPTION_TYPE: lambda info:
        #value on key "allowed_types" is overloaded:
        # * it can be a list - then it express possible option types
        # * it can be a string - then it is verbal description of the type
        "specified {option_name} is not valid, use {_hint}"
        .format(
            _hint=(
                format_list(info["allowed_types"])
                if is_iterable_not_str(info["allowed_types"])
                else info["allowed_types"]
            ),
            **info
        )
    ,

    codes.INVALID_USERDEFINED_OPTIONS: lambda info:
        (
            "invalid {desc}option{plural_options} {option_names_list}, "
            "{allowed_description}"
        ).format(
            desc=format_optional(info["option_type"], "{0} "),
            option_names_list=format_list(info["option_names"]),
            plural_options=("s:" if len(info["option_names"]) > 1 else ""),
            **info
        )
    ,

    codes.DEPRECATED_OPTION: lambda info:
        (
            "{desc}option '{option_name}' is deprecated and should not be "
            "used, use {hint} instead"
        ).format(
            desc=format_optional(info["option_type"], "{0} "),
            hint=(
                ", ".join(sorted(info["replaced_by"])) if (
                    isinstance(info["replaced_by"], Iterable)
                    and
                    not isinstance(info["replaced_by"], str)
                ) else info["replaced_by"]
            ),
            **info
        )
    ,

    codes.MUTUALLY_EXCLUSIVE_OPTIONS: lambda info:
        # "{desc}options {option_names} are muttually exclusive".format(
        "Only one of {desc}options {option_names} can be used".format(
            desc=format_optional(info["option_type"], "{0} "),
            option_names=(
                format_list(sorted(info["option_names"])[:-1])
                +
                " and '{0}'".format(sorted(info["option_names"])[-1])
            )
        )
    ,

    codes.EMPTY_ID: lambda info:
        "{id_description} cannot be empty"
        .format(**info)
    ,

    codes.INVALID_CIB_CONTENT: lambda info:
        "invalid cib: \n{0}"
        .format(info["report"])
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

    codes.NODE_COMMUNICATION_RETRYING: lambda info:
        (
            "Unable to connect to '{node}' via address '{failed_address}' and "
            "port '{failed_port}'. Retrying request '{request}' via address "
            "'{next_address}' and port '{next_port}'"
        ).format(**info)
    ,

    codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES: lambda info:
        "Unable to connect to '{node}' via any of its addresses".format(**info)
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
            " try running 'pcs host auth {node}'"
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
        (
            "{node}: Connection timeout, try setting higher timeout in "
            "--request-timeout option ({reason})"
        ).format(**info)
    ,

    codes.NODE_COMMUNICATION_PROXY_IS_SET:
        "Proxy is set in environment variables, try disabling it"
    ,

    codes.DEFAULTS_CAN_BE_OVERRIDEN:
        "Defaults do not apply to resources which override them with their "
        "own defined values"
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
        "{_node}Unable to get quorum status: {reason}"
        .format(
            _node=format_optional(info["node"], "{}: "),
            **info
        )
    ,

    codes.COROSYNC_QUORUM_SET_EXPECTED_VOTES_ERROR: lambda info:
        "Unable to set expected votes: {reason}"
        .format(**info)
    ,

    codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC:
        "No exec_NAME options are specified, so heuristics are effectively "
            "disabled"
    ,

    codes.COROSYNC_CONFIG_RELOADED: lambda info:
        "{_node}Corosync configuration reloaded".format(
            _node=format_optional(info["node"], "{}: "),
            **info
        )
    ,

    codes.COROSYNC_CONFIG_RELOAD_ERROR: lambda info:
        "{_node}Unable to reload corosync configuration: {reason}"
        .format(
            _node=format_optional(info["node"], "{}: "),
            **info,
        )
    ,

    codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE: lambda info:
       (
           "{node}: Corosync is not running, therefore reload of the corosync "
           "configuration is not possible"
       ).format(**info)
    ,

    codes.UNABLE_TO_READ_COROSYNC_CONFIG: lambda info:
        "Unable to read {path}: {reason}"
        .format(**info)
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_AFTER_OPENING_BRACE:
        "Unable to parse corosync config: extra characters after {"
    ,

    codes
    .PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_BEFORE_OR_AFTER_CLOSING_BRACE:
        "Unable to parse corosync config: extra characters before or after }"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE:
        "Unable to parse corosync config: a line is not opening or closing "
        "a section or key: value"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE:
        "Unable to parse corosync config: missing closing brace"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_MISSING_SECTION_NAME_BEFORE_OPENING_BRACE:
        "Unable to parse corosync config: missing a section name before {"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE:
        "Unable to parse corosync config: unexpected closing brace"
    ,

    codes.PARSE_ERROR_COROSYNC_CONF:
        "Unable to parse corosync config"
    ,

    codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES: lambda info:
        "Some nodes are missing names in corosync.conf, "
        +
        ("unable to continue" if info["fatal"] else "those nodes were omitted")
    ,

    codes.COROSYNC_CONFIG_NO_NODES_DEFINED: "No nodes found in corosync.conf",

    codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK: lambda info:
        (
            "Address '{address}' cannot be used in {_link} "
            "because the link uses {expected_address_type} addresses"
        ).format(
            _link=format_optional(info["link_number"], "link '{}'", "the link"),
            **info
        )
    ,

    codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT:
        corosync_bad_node_addresses_count
    ,

    codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS: lambda info:
        (
            "Using both IPv4 and IPv6 in one link is not allowed; please, use "
            "either IPv4 or IPv6{_links}"
        ).format(
            _links=(
                " in links {}".format(format_list(info["link_numbers"]))
                if info["link_numbers"]
                else ""
            )
        )
    ,

    codes.COROSYNC_LINK_NUMBER_DUPLICATION: lambda info:
        "Link numbers must be unique, duplicate link numbers: {_nums}".format(
            _nums=format_list(info["link_number_list"])
        )
    ,

    codes.NODE_ADDRESSES_ALREADY_EXIST: lambda info:
        (
            "Node address{_es} {_addrs} {_are} already used by existing nodes; "
            "please, use other address{_es}"
        ).format(
            _addrs=format_list(info["address_list"]),
            _es=("es" if len(info["address_list"]) > 1 else ""),
            _are=("are" if len(info["address_list"]) > 1 else "is"),
        )
    ,

    codes.NODE_ADDRESSES_CANNOT_BE_EMPTY: lambda info:
        (
            "Empty address set for node{_s} {_nodes}, "
            "an address cannot be empty"
        ).format(
            _s=("s" if len(info["node_name_list"]) > 1 else ""),
            _nodes=format_list(info["node_name_list"])
        )
    ,

    codes.NODE_ADDRESSES_DUPLICATION: lambda info:
        "Node addresses must be unique, duplicate addresses: {_addrs}".format(
            _addrs=format_list(info["address_list"])
        )
    ,

    codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH:
        corosync_node_address_count_mismatch
    ,

    codes.NODE_NAMES_ALREADY_EXIST: lambda info:
        (
            "Node name{_s} {_names} {_are} already used by existing nodes; "
            "please, use other name{_s}"
        ).format(
            _names=format_list(info["name_list"]),
            _s=("s" if len(info["name_list"]) > 1 else ""),
            _are=("are" if len(info["name_list"]) > 1 else "is"),
        )
    ,

    codes.NODE_NAMES_DUPLICATION: lambda info:
        "Node names must be unique, duplicate names: {_names}".format(
            _names=format_list(info["name_list"])
        )
    ,

    codes.COROSYNC_NODES_MISSING:
        "No nodes have been specified"
    ,

    codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE: lambda info:
        "These options cannot be set when the cluster uses a quorum device: {0}"
        .format(", ".join(sorted(info["options_names"])))
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

    codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE:
        corosync_link_does_not_exist_cannot_update
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

    codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED: lambda info:
        (
            "Resource '{resource_id}' has no enabled monitor operations."
            " Re-run with '--monitor' to enable them."
        )
        .format(**info)
    ,

    codes.NODE_ADDRESSES_UNRESOLVABLE: lambda info:
        "Unable to resolve addresses: {_addrs}".format(
            _addrs=format_list(info["address_list"])
        )
    ,

    codes.NODE_NOT_FOUND: lambda info:
        "{desc} '{node}' does not appear to exist in configuration".format(
            desc=build_node_description(info["searched_types"]),
            node=info["node"]
        )
    ,

    codes.NODE_REMOVE_IN_PACEMAKER_FAILED: lambda info:
        # TODO: Tests
        (
            "{_node}Unable to remove node(s) {_node_list} from pacemaker"
            "{_reason_part}"
        ).format(
            _node=format_optional(info["node"], "{}: "),
            _reason_part=format_optional(info["reason"], ": {0}"),
            _node_list=format_list(info["node_list_to_remove"]),
            **info
        )
    ,

    codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER: lambda info:
        (
            "node '{node}' seems to be still in the cluster"
            "; this command should be used only with nodes that have been"
            " removed from the cluster"
        )
        .format(**info)
    ,

    codes.MULTIPLE_RESULTS_FOUND: lambda info:
        "multiple {result_type} {search_description} found: {what_found}"
        .format(
            what_found=format_list(info["result_identifier_list"]),
            search_description="" if not info["search_description"]
                else "for '{0}'".format(info["search_description"])
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

    codes.FILE_DISTRIBUTION_SUCCESS: lambda info:
        "{node}: successful distribution of the file '{file_description}'"
        .format(
            **info
        )
    ,

    codes.FILE_DISTRIBUTION_ERROR: lambda info:
        "{node}: unable to distribute file '{file_description}': {reason}"
        .format(
            **info
        )
    ,

    codes.FILES_REMOVE_FROM_NODES_STARTED: lambda info:
        "Requesting remove {_description}{_where}".format(
            _where=(
                "" if not info["node_list"]
                else " from " + format_list(info["node_list"])
            ),
            _description=format_list(info["file_list"])
        )
    ,

    codes.FILES_REMOVE_FROM_NODES_SKIPPED: lambda info:
        (
            "Removing {_files} from {_nodes} was skipped because {_reason}. "
            "Please, remove the file(s) manually."
        ).format(
            _files=format_list(info["file_list"]),
            _nodes=format_list(info["node_list"]),
            _reason=skip_reason_to_string(info["reason_type"])
        )
    ,

    codes.FILE_REMOVE_FROM_NODE_SUCCESS: lambda info:
        "{node}: successful removal of the file '{file_description}'"
        .format(
            **info
        )
    ,


    codes.FILE_REMOVE_FROM_NODE_ERROR: lambda info:
        "{node}: unable to remove file '{file_description}': {reason}"
        .format(
            **info
        )
    ,

    codes.SERVICE_COMMANDS_ON_NODES_STARTED: lambda info:
        "Requesting {_description}{_where}".format(
            _where=(
                "" if not info["node_list"]
                else " on " + format_list(info["node_list"])
            ),
            _description=format_list(info["action_list"])
        )
    ,

    codes.SERVICE_COMMANDS_ON_NODES_SKIPPED: lambda info:
        (
            "Running action(s) {_actions} on {_nodes} was skipped because "
            "{_reason}. Please, run the action(s) manually."
        ).format(
            _actions=format_list(info["action_list"]),
            _nodes=format_list(info["node_list"]),
            _reason=skip_reason_to_string(info["reason_type"])
        )
    ,

    codes.SERVICE_COMMAND_ON_NODE_SUCCESS: lambda info:
        "{node}: successful run of '{service_command_description}'"
        .format(
            **info
        )
    ,

    codes.SERVICE_COMMAND_ON_NODE_ERROR: lambda info:
        (
            "{node}: service command failed:"
            " {service_command_description}: {reason}"
        )
        .format(
            **info
        )
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
        (
            (
                "Cluster uses SBD with shared storage so SBD devices must be "
                "specified for all nodes, no device specified for node '{node}'"
            )
            if info["sbd_enabled_in_cluster"] else
            "No SBD device specified for node '{node}'"
        ).format(**info)
    ,

    codes.SBD_TOO_MANY_DEVICES_FOR_NODE: lambda info:
        (
            "At most {max_devices} SBD devices can be specified for a node, "
            "'{_devices}' specified for node '{node}'"
        )
        .format(
            _devices="', '".join(info["device_list"]),
            **info
        )
    ,

    codes.SBD_NOT_INSTALLED: lambda info:
        "SBD is not installed on node '{node}'"
        .format(**info)
    ,

    codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS: lambda info:
        (
            "Cluster is not configured to use SBD, cannot specify SBD "
            "option(s) {__options} for node '{node}'"
        ).format(
            __options=format_list(info["options"]),
            **info
        )
    ,

    codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE: lambda info:
        "Cluster is not configured to use SBD with shared storage, cannot "
        "specify SBD devices for node '{node}'"
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
        "{_node}{_file_role} file '{file_path}' already exists"
        .format(
            _node=format_optional(info["node"], NODE_PREFIX),
            _file_role=format_file_role(info["file_role"]),
            **info
        )
    ,

    codes.FILE_DOES_NOT_EXIST: lambda info:
        "{_file_role} file '{file_path}' does not exist"
        .format(
            _file_role=format_file_role(info["file_role"]),
            **info
        )
    ,

    codes.FILE_IO_ERROR: lambda info:
        "Unable to {operation} {_file_role}{_file_path}: {reason}"
        .format(
            _file_path=format_optional(info["file_path"], " '{0}'"),
            _file_role=format_file_role(info["file_role"]),
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
        .format(
            forbidden_options=format_list(info["forbidden_options"], {
                "BOOTH_CONF": "--booth-conf",
                "BOOTH_KEY": "--booth-key",
                "CIB": "-f",
                "COROSYNC_CONF": "--corosync_conf",
            })
        )
    ,

    codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE:
        "Node(s) must be specified if -f is used"
    ,

    codes.COROSYNC_NODE_CONFLICT_CHECK_SKIPPED: lambda info:
        (
            "Unable to check if there is a conflict with nodes set in corosync "
            "because {_reason}"
        ).format(
            _reason=skip_reason_to_string(info["reason_type"])
        )
    ,

    codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD:
        "Unable to disable auto_tie_breaker, SBD fencing would have no effect"
    ,

    codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD:
        "auto_tie_breaker quorum option will be enabled to make SBD fencing "
        "effective. Cluster has to be offline to be able to make this change."
    ,

    codes.USE_COMMAND_NODE_ADD_REMOTE: lambda info:
        (
            "this command is not sufficient for creating a remote connection,"
            " use 'pcs cluster node add-remote'"
        )
    ,
    codes.USE_COMMAND_NODE_ADD_GUEST: lambda info:
        (
            "this command is not sufficient for creating a guest node, use"
            " 'pcs cluster node add-guest'"
        )
    ,
    codes.USE_COMMAND_NODE_REMOVE_GUEST: lambda info:
        (
            "this command is not sufficient for removing a guest node, use"
            " 'pcs cluster node remove-guest'"
        )
    ,

    codes.TMP_FILE_WRITE: lambda info:
        (
            "Writing to a temporary file {file_path}:\n"
            "--Debug Content Start--\n{content}\n--Debug Content End--\n"
        ).format(**info)
    ,
    codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE:
        "Unable to perform operation on any available node/host, therefore it "
        "is not possible to continue"
    ,
    codes.HOST_NOT_FOUND: lambda info:
        (
            "Host{_s} {_hosts_comma} {_are} not known to pcs, try to "
            "authenticate the host{_s} using 'pcs host auth {_hosts_space}' "
            "command"
        ).format(
            _hosts_comma=format_list(info["host_list"]),
            _hosts_space=" ".join(sorted(info["host_list"])),
            _s=("s" if len(info["host_list"]) > 1 else ""),
            _are=("are" if len(info["host_list"]) > 1 else "is")
        )
    ,
    codes.NONE_HOST_FOUND: "None of hosts is known to pcs.",
    codes.HOST_ALREADY_AUTHORIZED: lambda info:
        "{host_name}: Already authorized".format(**info)
    ,
    codes.CLUSTER_DESTROY_STARTED: lambda info:
        "Destroying cluster on hosts: {_hosts}...".format(
            _hosts=format_list(info["host_name_list"])
        )
    ,
    codes.CLUSTER_DESTROY_SUCCESS: lambda info:
        "{node}: Successfully destroyed cluster".format(**info)
    ,
    codes.CLUSTER_ENABLE_STARTED: lambda info:
        "Enabling cluster on hosts: {_hosts}...".format(
            _hosts=format_list(info["host_name_list"])
        )
    ,
    codes.CLUSTER_ENABLE_SUCCESS: lambda info:
        "{node}: Cluster enabled".format(**info)
    ,
    codes.CLUSTER_START_STARTED: lambda info:
        "Starting cluster on hosts: {_hosts}...".format(
            _hosts=format_list(info["host_name_list"])
        )
    ,
    codes.CLUSTER_START_SUCCESS: lambda info:
        "{node}: Cluster started".format(**info)
    ,
    codes.SERVICE_NOT_INSTALLED: lambda info:
        "{node}: Required cluster services not installed: {_services}".format(
            _services=format_list(info["service_list"]),
            **info
        )
    ,

    codes.HOST_ALREADY_IN_CLUSTER_CONFIG: lambda info:
        (
            "{host_name}: Cluster configuration files found, the host "
            "seems to be in a cluster already"
        ).format(**info)
    ,

    codes.HOST_ALREADY_IN_CLUSTER_SERVICES: lambda info:
        (
            "{host_name}: Running cluster services: {_services}, the host "
            "seems to be in a cluster already"
        ).format(
            _services=format_list(info["service_list"]),
            **info
        )
    ,

    codes.SERVICE_VERSION_MISMATCH: service_version_mismatch,

    codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START:
        "Cannot specify '--wait' without specifying '--start'"
    ,
    codes.WAIT_FOR_NODE_STARTUP_STARTED: lambda info:
        "Waiting for nodes to start: {_nodes}...".format(
            _nodes=format_list(info["node_name_list"])
        )
    ,
    codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT: "Waiting timeout",
    codes.WAIT_FOR_NODE_STARTUP_ERROR:
        "Unable to verify all nodes have started"
    ,
    codes.PCSD_VERSION_TOO_OLD: lambda info:
        (
            "{node}: Old version of pcsd is running on the node, therefore it "
            "is unable to perform the action"
        ).format(**info)
    ,
    codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED: lambda info:
        "Synchronizing pcsd SSL certificates on nodes {_nodes}...".format(
            _nodes=format_list(info["node_name_list"])
        )
    ,
    codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS: lambda info:
        "{node}: Success".format(**info)
    ,
    codes.CLUSTER_WILL_BE_DESTROYED:
        "Some nodes are already in a cluster. Enforcing this will destroy "
        "existing cluster on those nodes. You should remove the nodes from "
        "their clusters instead to keep the clusters working properly"
    ,
    codes.CLUSTER_SETUP_SUCCESS:
        "Cluster has been successfully set up."
    ,
    codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST: lambda info:
        "No addresses specified for host '{host_name}', using '{address}'"
        .format(**info)
    ,
    codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE: lambda info:
        (
            "Resource '{inner_resource_id}' will not be accessible by the "
            "cluster inside bundle '{bundle_id}', at least one of bundle "
            "options 'control-port' or 'ip-range-start' has to be specified"
        ).format(**info)
    ,
    codes.USING_DEFAULT_WATCHDOG: lambda info:
        (
            "No watchdog has been specified for node '{node}'. Using default "
            "watchdog '{watchdog}'"
        ).format(**info)
    ,
    codes.CANNOT_REMOVE_ALL_CLUSTER_NODES:
        (
            "No nodes would be left in the cluster, if you intend to destroy "
            "the whole cluster, run 'pcs cluster destroy --all' instead"
        )
    ,
    codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE:
        "Unable to connect to any remaining cluster node"
    ,
    codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE: lambda info:
        (
            "Remaining cluster nodes {_nodes} are unreachable, run 'pcs "
            "cluster sync' on some now online node once they become available"
        ).format(
            _nodes=format_list(info["node_list"]),
        )
    ,
    codes.NODES_TO_REMOVE_UNREACHABLE: lambda info:
        (
            "Removed nodes {_nodes} are unreachable, therefore it is not "
            "possible to deconfigure them. Run 'pcs cluster destroy' on them "
            "when available."
        ).format(
            _nodes=format_list(info["node_list"]),
        )
    ,
    codes.NODE_USED_AS_TIE_BREAKER: lambda info:
        (
            "Node '{node}' with id '{node_id}' is used as a tie breaker for "
            "a qdevice, run 'pcs quorum device update model "
            "tie_breaker=<node id>' to change it"
        ).format(**info)
    ,
    codes.COROSYNC_QUORUM_WILL_BE_LOST:
        "This action will cause a loss of the quorum"
    ,
    codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK:
        (
            "Unable to determine whether this action will cause a loss of the "
            "quorum"
        )
    ,
    codes.SBD_LIST_WATCHDOG_ERROR: lambda info:
        "Unable to query available watchdogs from sbd: {reason}".format(**info)
    ,
    codes.SBD_WATCHDOG_NOT_SUPPORTED: lambda info:
        (
            "{node}: Watchdog '{watchdog}' is not supported (it may be a "
            "software watchdog)"
        ).format(**info)
    ,
    codes.SBD_WATCHDOG_VALIDATION_INACTIVE:
        "Not validating the watchdog"
    ,
    codes.SBD_WATCHDOG_TEST_ERROR: lambda info:
        "Unable to initialize test of the watchdog: {reason}".format(**info)
    ,
    codes.SBD_WATCHDOG_TEST_MULTUPLE_DEVICES:
        "Multiple watchdog devices available, therefore, watchdog which should "
        "be tested has to be specified. To list available watchdog devices use "
        "command 'pcs stonith sbd watchdog list'"
    ,
    codes.SBD_WATCHDOG_TEST_FAILED:
        "System should have been reset already"
    ,
    codes.SYSTEM_WILL_RESET:
        "System will reset shortly"
    ,
    codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE: lambda info:
        (
            "Bundle '{bundle_id}' uses unsupported container type, therefore "
            "it is not possible to set its container options. Supported "
            "container types are: {_container_types}"
        ).format(
            _container_types=format_list(info["supported_container_types"]),
            **info,
        )
    ,
    codes.FENCE_HISTORY_COMMAND_ERROR: lambda info:
        "Unable to {command_label} fence history: {reason}".format(**info)
    ,
    codes.FENCE_HISTORY_NOT_SUPPORTED:
        "Fence history is not supported, please upgrade pacemaker"
    ,
    codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE: lambda info:
        (
            "Value '{_val}' of option '{_attr}' is not unique across "
            "'{_agent}' resources. Following resources are configured "
            "with the same value of the instance attribute: {_res_id_list}"
        ).format(
            _val=info["instance_attr_value"],
            _attr=info["instance_attr_name"],
            _agent=info["agent_name"],
            _res_id_list=format_list(info["resource_id_list"]),
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

    codes.CANNOT_MOVE_RESOURCE_BUNDLE: "cannot move bundle resources",
    codes.CANNOT_MOVE_RESOURCE_CLONE: "cannot move cloned resources",
    codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE:
        resource_move_ban_clear_master_resource_not_promotable
    ,
    codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_NOT_MASTER: lambda info:
        (
            "to move promotable clone resources you must use --master and the "
            "promotable clone id ({promotable_id})"
        ).format(**info)
    ,
    codes.CANNOT_MOVE_RESOURCE_STOPPED_NO_NODE_SPECIFIED:
        # Use both "moving" and "banning" to let user know using "ban" instead
        # of "move" will not help
        "You must specify a node when moving/banning a stopped resource"
    ,
    codes.RESOURCE_MOVE_PCMK_ERROR: lambda info:
        # Pacemaker no longer prints crm_resource specific options since commit
        # 8008a5f0c0aa728fbce25f60069d622d0bcbbc9f. There is no need to
        # translate them or anything else anymore.
        stdout_stderr_to_string(
            info["stdout"],
            info["stderr"],
            prefix="cannot move resource '{resource_id}'".format(**info)
        )
    ,
    codes.RESOURCE_MOVE_PCMK_SUCCESS: resource_move_ban_pcmk_success,

    codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE:
        resource_move_ban_clear_master_resource_not_promotable
    ,
    codes.CANNOT_BAN_RESOURCE_STOPPED_NO_NODE_SPECIFIED:
        # Use both "moving" and "banning" to let user know using "move" instead
        # of "ban" will not help
        "You must specify a node when moving/banning a stopped resource"
    ,
    codes.RESOURCE_BAN_PCMK_ERROR: lambda info:
        # Pacemaker no longer prints crm_resource specific options since commit
        # 8008a5f0c0aa728fbce25f60069d622d0bcbbc9f. There is no need to
        # translate them or anything else anymore.
        stdout_stderr_to_string(
            info["stdout"],
            info["stderr"],
            prefix="cannot ban resource '{resource_id}'".format(**info)
        )
    ,
    codes.RESOURCE_BAN_PCMK_SUCCESS: resource_move_ban_pcmk_success,

    codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE:
        resource_move_ban_clear_master_resource_not_promotable
    ,
    codes.RESOURCE_UNMOVE_UNBAN_PCMK_EXPIRED_NOT_SUPPORTED:
        "--expired is not supported, please upgrade pacemaker"
    ,
    codes.RESOURCE_UNMOVE_UNBAN_PCMK_ERROR: lambda info:
        stdout_stderr_to_string(
            info["stdout"],
            info["stderr"],
            prefix="cannot clear resource '{resource_id}'".format(**info)
        )
    ,
    codes.RESOURCE_UNMOVE_UNBAN_PCMK_SUCCESS: lambda info:
        stdout_stderr_to_string(info["stdout"], info["stderr"])
    ,
}
