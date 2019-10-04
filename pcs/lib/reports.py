# pylint: disable=too-many-lines
from functools import partial

from pcs.common import report_codes
from pcs.lib.errors import ReportItem, ReportItemSeverity

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

def resource_for_constraint_is_multiinstance(
    resource_id, parent_type, parent_id,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    when setting up a constraint a resource in a type of a clone was specified
    resource_id string specified resource
    parent_type string type of a clone (clone, bundle...)
    parent_id string clone resource id
    severity string report item severity
    forceable mixed is this report item forceable? by what category?
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

def empty_resource_set_list():
    """
    an empty resource set has been specified, which is not allowed by cib schema
    """
    return ReportItem.error(
        report_codes.EMPTY_RESOURCE_SET_LIST,
    )

def required_options_are_missing(
    option_names, option_type=None,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    required option has not been specified, command cannot continue
    list name is/are required but was not entered
    option_type describes the option
    severity report item severity
    forceable is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.REQUIRED_OPTIONS_ARE_MISSING,
        severity,
        forceable=forceable,
        info={
            "option_names": sorted(option_names),
            "option_type": option_type,
        }
    )

def prerequisite_option_is_missing(
    option_name, prerequisite_name, option_type="", prerequisite_type=""
):
    """
    if the option_name is specified, the prerequisite_option must be specified

    string option_name -- an option which depends on the prerequisite_option
    string prerequisite_name -- the prerequisite option
    string option_type -- describes the option
    string prerequisite_type -- describes the prerequisite_option
    """
    return ReportItem.error(
        report_codes.PREREQUISITE_OPTION_IS_MISSING,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "prerequisite_name": prerequisite_name,
            "prerequisite_type": prerequisite_type,
        }
    )

def prerequisite_option_must_be_enabled_as_well(
    option_name, prerequisite_name, option_type="", prerequisite_type=""
):
    """
    If the option_name is enabled, the prerequisite_option must be also enabled

    string option_name -- an option which depends on the prerequisite_option
    string prerequisite_name -- the prerequisite option
    string option_type -- describes the option
    string prerequisite_type -- describes the prerequisite_option
    """
    return ReportItem.error(
        report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "prerequisite_name": prerequisite_name,
            "prerequisite_type": prerequisite_type,
        }
    )

def prerequisite_option_must_be_disabled(
    option_name, prerequisite_name, option_type="", prerequisite_type=""
):
    """
    If the option_name is enabled, the prerequisite_option must be disabled

    string option_name -- an option which depends on the prerequisite_option
    string prerequisite_name -- the prerequisite option
    string option_type -- describes the option
    string prerequisite_type -- describes the prerequisite_option
    """
    return ReportItem.error(
        report_codes.PREREQUISITE_OPTION_MUST_BE_DISABLED,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "prerequisite_name": prerequisite_name,
            "prerequisite_type": prerequisite_type,
        }
    )

def prerequisite_option_must_not_be_set(
    option_name, prerequisite_name, option_type="", prerequisite_type=""
):
    """
    The option_name cannot be set because the prerequisite_name is already set

    string option_name -- an option which depends on the prerequisite_option
    string prerequisite_name -- the prerequisite option
    string option_type -- describes the option
    string prerequisite_type -- describes the prerequisite_option
    """
    return ReportItem.error(
        report_codes.PREREQUISITE_OPTION_MUST_NOT_BE_SET,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "prerequisite_name": prerequisite_name,
            "prerequisite_type": prerequisite_type,
        }
    )

def required_option_of_alternatives_is_missing(
    option_names, option_type=None
):
    """
    at least one option has to be specified
    iterable option_names -- options from which at least one has to be specified
    string option_type -- describes the option
    """
    severity = ReportItemSeverity.ERROR
    forceable = None
    return ReportItem(
        report_codes.REQUIRED_OPTION_OF_ALTERNATIVES_IS_MISSING,
        severity,
        forceable=forceable,
        info={
            "option_names": sorted(option_names),
            "option_type": option_type,
        }
    )

def invalid_options(
    option_names, allowed_options, option_type, allowed_option_patterns=None,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified option names are not valid, usualy an error or a warning

    list option_names -- specified invalid option names
    list allowed_options -- possible allowed option names
    string option_type -- describes the option
    list allowed_option_patterns -- allowed user defind options patterns
    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.INVALID_OPTIONS,
        severity,
        forceable,
        info={
            "option_names": sorted(option_names),
            "option_type": option_type,
            "allowed": sorted(allowed_options),
            "allowed_patterns": sorted(allowed_option_patterns or []),
        }
    )

def invalid_userdefined_options(option_names, option_type, allowed_characters):
    """
    specified option names defined by a user are not valid

    This is different than invalid_options. In this case, the options are
    supposed to be defined by a user. This report carries information that the
    option names do not meet requirements, i.e. contain not allowed characters.
    Invalid_options is used when the options are predefined by pcs (or
    underlying tools).

    list option_names -- specified invalid option names
    string allowed_characters -- which characters are allowed in the names
    string option_type -- describes the option
    """
    return ReportItem.error(
        report_codes.INVALID_USERDEFINED_OPTIONS,
        info={
            "option_names": sorted(option_names),
            "option_type": option_type,
            "allowed_characters": allowed_characters,
        }
    )

def invalid_option_type(option_name, allowed_types):
    """
    specified value is not of a valid type for the option
    string option_name -- option name whose value is not of a valid type
    list|string allowed_types -- list of allowed types or string description
    """
    return ReportItem.error(
        report_codes.INVALID_OPTION_TYPE,
        info={
            "option_name": option_name,
            "allowed_types": allowed_types,
        },
    )

def invalid_option_value(
    option_name, option_value, allowed_values, cannot_be_empty=False,
    forbidden_characters=None,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified value is not valid for the option, usualy an error or a warning

    string option_name -- specified option name whose value is not valid
    string option_value -- specified value which is not valid
    mixed allowed_options -- a list of allowed values or a string description
    bool cannot_be_empty -- the value is empty and that is not allowed
    iterable forbidden_characters -- characters the value cannot contain
    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.INVALID_OPTION_VALUE,
        severity,
        info={
            "option_value": option_value,
            "option_name": option_name,
            "allowed_values": allowed_values,
            "cannot_be_empty": cannot_be_empty,
            "forbidden_characters": forbidden_characters,
        },
        forceable=forceable
    )

def deprecated_option(
    option_name, replaced_by_options, option_type,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Specified option name is deprecated and has been replaced by other option(s)

    string option_name -- the deprecated option
    iterable replaced_by_options -- new option(s) to be used instead
    string option_type -- option description
    string severity -- report item severity
    string forceable -- a category by which the report is forceable
    """
    return ReportItem(
        report_codes.DEPRECATED_OPTION,
        severity,
        info={
            "option_name": option_name,
            "option_type": option_type,
            "replaced_by": sorted(replaced_by_options),
        },
        forceable=forceable
    )

def mutually_exclusive_options(option_names, option_type):
    """
    entered options can not coexist
    set option_names contain entered mutually exclusive options
    string option_type describes the option
    """
    return ReportItem.error(
        report_codes.MUTUALLY_EXCLUSIVE_OPTIONS,
        info={
            "option_names": sorted(option_names),
            "option_type": option_type,
        },
    )

def invalid_cib_content(report):
    """
    Given cib content is not valid.
    string report -- is human readable explanation of a cib invalidity. For
        example a stderr of `crm_verify`.
    """
    return ReportItem.error(
        report_codes.INVALID_CIB_CONTENT,
        info={
            "report": report,
        }
    )



def invalid_id_is_empty(id, id_description):
    # pylint says 'id' is wrong
    # pylint: disable=invalid-name, redefined-builtin
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
    # pylint says 'id' is wrong
    # pylint: disable=invalid-name, redefined-builtin
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

def run_external_process_started(command, stdin, environment):
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
            "environment": environment,
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


def node_communication_debug_info(target, data):
    """
    Node communication debug info from pycurl
    """
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_DEBUG_INFO,
        info={
            "target": target,
            "data": data,
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


def node_communication_no_more_addresses(node, request):
    """
    request failed and there are no more addresses to try it again
    """
    return ReportItem.warning(
        report_codes.NODE_COMMUNICATION_NO_MORE_ADDRESSES,
        info={
            "node": node,
            "request": request,
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

def node_communication_command_unsuccessful(
    node, command, reason, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    node rejected a request for another reason with a plain text explanation
    node string node address / name
    reason string decription of the error
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
        severity,
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
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


def node_communication_error_timed_out(
    node, command, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Communication with node timed out.
    """
    return ReportItem(
        report_codes.NODE_COMMUNICATION_ERROR_TIMED_OUT,
        severity,
        info={
            "node": node,
            "command": command,
            "reason": reason,
        },
        forceable=forceable
    )

def node_communication_proxy_is_set(node=None, address=None):
    """
    Warning when connection failed and there is proxy set in environment
    variables
    """
    return ReportItem.warning(
        report_codes.NODE_COMMUNICATION_PROXY_IS_SET,
        info={
            "node": node,
            "address": address,
        }
    )


def node_communication_retrying(
    node, failed_address, failed_port, next_address, next_port, request
):
    """
    Request failed due communication error connecting via specified address,
    therefore trying another address if there is any.
    """
    return ReportItem.warning(
        report_codes.NODE_COMMUNICATION_RETRYING,
        info={
            "node": node,
            "failed_address": failed_address,
            "failed_port": failed_port,
            "next_address": next_address,
            "next_port": next_port,
            "request": request,
        }
    )


def defaults_can_be_overriden():
    """
    Warning when settings defaults (op_defaults, rsc_defaults...)
    """
    return ReportItem.warning(report_codes.DEFAULTS_CAN_BE_OVERRIDEN)

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

def corosync_quorum_get_status_error(
    reason, node=None, severity=ReportItemSeverity.ERROR,
):
    """
    unable to get runtime status of quorum

    string reason -- an error message
    string node -- a node where the error occurred, local node if not specified
    string severity -- report item severity
    """
    return ReportItem(
        report_codes.COROSYNC_QUORUM_GET_STATUS_ERROR,
        severity,
        info={
            "reason": reason,
            "node": node,
        }
    )

def corosync_quorum_heuristics_enabled_with_no_exec():
    """
    no exec_ is specified, therefore heuristics are effectively disabled
    """
    return ReportItem.warning(
        report_codes.COROSYNC_QUORUM_HEURISTICS_ENABLED_WITH_NO_EXEC
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

def corosync_config_reloaded(node=None):
    """
    corosync configuration has been reloaded

    node string -- node label on which operation has been executed
    """
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_RELOADED,
        info=dict(
            node=node,
        )
    )

def corosync_config_reload_error(
    reason, node=None, severity=ReportItemSeverity.ERROR
):
    """
    an error occured when reloading corosync configuration

    reason string -- an error message
    node string -- node label
    severity ReportItemSeverity -- severity of the report
    """
    return ReportItem(
        report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
        severity,
        info={
            "reason": reason,
            "node": node,
        }
    )

def corosync_config_reload_not_possible(node):
    """
    corosync configuration cannot be reloaded because corosync is not running
    on the specified node

    node string -- node label on which confi
    """
    return ReportItem.warning(
        report_codes.COROSYNC_CONFIG_RELOAD_NOT_POSSIBLE,
        info=dict(
            node=node,
        )
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

def corosync_config_parser_missing_section_name_before_opening_brace():
    """
    corosync config cannot be parsed due to a section name missing before {
    """
    # pylint: disable=line-too-long
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_SECTION_NAME_BEFORE_OPENING_BRACE,
    )

def corosync_config_parser_extra_characters_after_opening_brace():
    """
    corosync config cannot be parsed due to extra characters after {
    """
    # pylint: disable=line-too-long
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_AFTER_OPENING_BRACE,
    )

def corosync_config_parser_extra_characters_before_or_after_closing_brace():
    """
    corosync config cannot be parsed due to extra characters before or after }
    """
    # pylint: disable=line-too-long
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_EXTRA_CHARACTERS_BEFORE_OR_AFTER_CLOSING_BRACE,
    )

def corosync_config_parser_line_is_not_section_nor_key_value():
    """
    corosync config cannot be parsed due to a line is not a section nor key:val
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE
    )

def corosync_config_parser_other_error():
    """
    corosync config cannot be parsed, the cause is not specified
    It is better to use more specific error if possible.
    """
    return ReportItem.error(
        report_codes.PARSE_ERROR_COROSYNC_CONF,
    )

def corosync_config_cannot_save_invalid_names_values(sections, names, values):
    """
    cannot save corosync.conf - it contains forbidden characters which break it

    iterable sections -- bad names of sections
    iterable names -- bad names of attributes
    iterable values -- tuples (attribute_name, its_bad_value)
    """
    return ReportItem.error(
        report_codes.COROSYNC_CONFIG_CANNOT_SAVE_INVALID_NAMES_VALUES,
        info={
            "section_name_list": sections,
            "attribute_name_list": names,
            "attribute_value_pairs": values,
        }
    )

def corosync_config_missing_names_of_nodes(fatal=False):
    """
    Some nodes in corosync.conf do not have their name set, they will be omitted

    bool fatal -- if True, pcs cannot continue
    """
    return ReportItem(
        report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
        severity=(
            ReportItemSeverity.ERROR if fatal else ReportItemSeverity.WARNING
        ),
        info={
            "fatal": fatal,
        }
    )

def corosync_config_no_nodes_defined():
    """
    No nodes found in corosync.conf
    """
    return ReportItem.error(
        report_codes.COROSYNC_CONFIG_NO_NODES_DEFINED,
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

def corosync_bad_node_addresses_count(
    actual_count, min_count, max_count, node_name=None, node_index=None
):
    """
    Wrong number of addresses set for a corosync node.

    int actual_count -- how many addresses set for a node
    int min_count -- minimal allowed addresses count
    int max_count -- maximal allowed addresses count
    string node_name -- optionally specify node name
    string node_index -- optionally specify node index (helps to identify a node
        if a name is missing)
    """
    return ReportItem.error(
        report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
        info={
            "actual_count": actual_count,
            "min_count": min_count,
            "max_count": max_count,
            "node_name": node_name,
            "node_index": node_index,
        }
    )

def corosync_ip_version_mismatch_in_links(link_numbers=None):
    """
    Mixing IPv4 and IPv6 in one or more links, which is not allowed

    iterable link_numbers -- numbers of links with mismatched IP versions
    """
    return ReportItem.error(
        report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
        info={
            "link_numbers": link_numbers,
        }
    )

def corosync_address_ip_version_wrong_for_link(
    address, expected_address_type, link_number=None
):
    """
    Cannot use an address in a link as it does not match the link's IP version.

    string address -- a provided address
    string expected_address_type -- an address type used in a link
    int link_number -- number of the link
    """
    return ReportItem.error(
        report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
        info=dict(
            address=address,
            expected_address_type=expected_address_type,
            link_number=link_number,
        )
    )

def corosync_link_number_duplication(number_list):
    """
    Trying to set one link_number for more links, link numbers must be unique

    iterable number_list -- list of nonunique link numbers
    """
    return ReportItem.error(
        report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
        info={
            "link_number_list": sorted(number_list, key=_key_numeric),
        }
    )

def corosync_node_address_count_mismatch(node_addr_count):
    """
    Nodes do not have the same number of addresses

    dict node_addr_count -- key: node name, value: number of addresses
    """
    return ReportItem.error(
        report_codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH,
        info={
            "node_addr_count": node_addr_count,
        }
    )

def node_addresses_already_exist(address_list):
    """
    Trying add node(s) with addresses already used by other nodes

    iterable address_list -- list of specified already existing addresses
    """
    return ReportItem.error(
        report_codes.NODE_ADDRESSES_ALREADY_EXIST,
        info={
            "address_list": sorted(address_list),
        }
    )

def node_addresses_cannot_be_empty(node_name_list):
    """
    Trying to set an empty node address or remove a node address in an update

    iterable node_name_list -- list of node names with empty addresses
    """
    return ReportItem.error(
        report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
        info={
            "node_name_list": sorted(node_name_list),
        }
    )

def node_addresses_duplication(address_list):
    """
    Trying to set one address for more nodes or links, addresses must be unique

    iterable address_list -- list of nonunique addresses
    """
    return ReportItem.error(
        report_codes.NODE_ADDRESSES_DUPLICATION,
        info={
            "address_list": sorted(address_list),
        }
    )

def node_names_already_exist(name_list):
    """
    Trying add node(s) with name(s) already used by other nodes

    iterable name_list -- list of specified already used node names
    """
    return ReportItem.error(
        report_codes.NODE_NAMES_ALREADY_EXIST,
        info={
            "name_list": sorted(name_list),
        }
    )

def node_names_duplication(name_list):
    """
    Trying to set one node name for more nodes, node names must be unique

    iterable name_list -- list of nonunique node names
    """
    return ReportItem.error(
        report_codes.NODE_NAMES_DUPLICATION,
        info={
            "name_list": sorted(name_list),
        }
    )

def corosync_nodes_missing():
    """
    No nodes have been specified
    """
    return ReportItem.error(
        report_codes.COROSYNC_NODES_MISSING,
        info={
        }
    )

def corosync_too_many_links_options(links_options_count, links_count):
    """
    Options for more links than defined by nodes' addresses have been specified

    int links_options_count -- options for how many links have been specified
    int links_count -- for how many links is defined
    """
    return ReportItem.error(
        report_codes.COROSYNC_TOO_MANY_LINKS_OPTIONS,
        info={
            "links_options_count": links_options_count,
            "links_count": links_count,
        }
    )

def corosync_cannot_add_remove_links_bad_transport(
    actual_transport, required_transports, add_or_not_remove
):
    """
    Cannot add or remove corosync links, used transport does not allow that

    string actual_transport -- transport used in the cluster
    list required_transports -- transports allowing links to be added / removed
    bool add_or_not_remove -- True for add, False for remove
    """
    return ReportItem.error(
        report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT,
        info={
            "add_or_not_remove": add_or_not_remove,
            "actual_transport": actual_transport,
            "required_transport_list": sorted(required_transports),
        }
    )

def corosync_cannot_add_remove_links_no_links_specified(add_or_not_remove):
    """
    Cannot add or remove links, no links were specified

    bool add_or_not_remove -- True for add, False for remove
    """
    return ReportItem.error(
        report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_NO_LINKS_SPECIFIED,
        info={
            "add_or_not_remove": add_or_not_remove,
        }
    )

def corosync_cannot_add_remove_links_too_many_few_links(
    links_change_count, links_new_count, links_limit_count, add_or_not_remove
):
    """
    Cannot add or remove links, link count would exceed allowed limits

    int links_change_count -- how many links to add / remove
    int links_new_count -- how many links would be defined after the action
    int links_limit_count -- maximal / minimal number of links allowed
    bool add_or_not_remove -- True for add, False for remove
    """
    return ReportItem.error(
        report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS,
        info={
            "links_change_count": links_change_count,
            "links_new_count": links_new_count,
            "links_limit_count": links_limit_count,
            "add_or_not_remove": add_or_not_remove,
        }
    )

def corosync_link_already_exists_cannot_add(link_number):
    """
    Cannot add a link with specified linknumber as it already exists
    """
    return ReportItem.error(
        report_codes.COROSYNC_LINK_ALREADY_EXISTS_CANNOT_ADD,
        info={
            "link_number": link_number,
        }
    )

def corosync_link_does_not_exist_cannot_remove(
    link_number_list, existing_link_list
):
    """
    Cannot remove links which don't exist

    iterable link_number_list -- links to remove which don't exist
    iterable existing_link_list -- linknumbers of existing links
    """
    return ReportItem.error(
        report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
        info={
            "link_list": sorted(link_number_list, key=_key_numeric),
            "existing_link_list": sorted(existing_link_list, key=_key_numeric),
        }
    )

def corosync_link_does_not_exist_cannot_update(
    link_number, link_count=None, existing_link_list=None
):
    """
    Cannot set options for the defined link because the link does not exist

    integer link_number -- number of the link to be updated
    integer link_count -- how many links exists
    iterable existing_link_list -- linknumbers of existing links
    """
    assert link_count is None or existing_link_list is None
    return ReportItem.error(
        report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE,
        info={
            "link_number": link_number,
            "link_count": link_count,
            "existing_link_list": (
                sorted(existing_link_list) if existing_link_list
                else existing_link_list
            )
        }
    )

def corosync_transport_unsupported_options(
    option_type, actual_transport, required_transports
):
    """
    A type of options is not supported with the given transport
    """
    return ReportItem.error(
        report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
        info={
            "option_type": option_type,
            "actual_transport": actual_transport,
            "required_transport_list": required_transports,
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

def cannot_group_resource_adjacent_resource_for_new_group(
    adjacent_resource_id, group_id
):
    """
    Cannot put resources next to an adjacent resource in a group, because the
    group does not exist yet and therefore cannot contain the adjacent resource

    string adjacent_resource_id -- id of an adjacent resource
    string group_id -- id of the group resources cannot be put into
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_FOR_NEW_GROUP,
        info={
            "adjacent_resource_id": adjacent_resource_id,
            "group_id": group_id,
        }
    )

def cannot_group_resource_adjacent_resource_not_in_group(
    adjacent_resource_id, group_id
):
    """
    Cannot put resources next to an adjacent resource in a group, because the
    adjacent resource does not belong to the group

    string adjacent_resource_id -- id of an adjacent resource
    string group_id -- id of the group resources cannot be put into
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_ADJACENT_RESOURCE_NOT_IN_GROUP,
        info={
            "adjacent_resource_id": adjacent_resource_id,
            "group_id": group_id,
        }
    )

def cannot_group_resource_already_in_the_group(resource_list, group_id):
    """
    Cannot put resources into a group, they are already there

    iterable resource_list -- ids of resources which cannot be put into a group
    string group_id -- id of the group the resource cannot be put into
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_ALREADY_IN_THE_GROUP,
        info={
            "resource_list": sorted(resource_list),
            "group_id": group_id,
        }
    )

def cannot_group_resource_more_than_once(resource_list):
    """
    Cannot put the same resources into a group more than once

    iterable resource_list -- ids of resources specified more than once
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_MORE_THAN_ONCE,
        info={
            "resource_list": sorted(resource_list),
        }
    )

def cannot_group_resource_no_resources():
    """
    Cannot put resources into a group, no resources were specified
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_NO_RESOURCES
    )

def cannot_group_resource_next_to_itself(resource_id):
    """
    Cannot put a resource into a group next to itself

    string resource_id -- id of the resource which cannot be put into a group
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_NEXT_TO_ITSELF,
        info={
            "resource_id": resource_id,
        }
    )

def cannot_group_resource_wrong_type(resource_id, resource_type):
    """
    Cannot put a resource into a group as the resource is not a primitive

    string resource_id -- id of the element which cannot be put into a group
    string resource_type -- tag of the element which cannot be put into a group
    """
    return ReportItem.error(
        report_codes.CANNOT_GROUP_RESOURCE_WRONG_TYPE,
        info={
            "resource_id": resource_id,
            "resource_type": resource_type,
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

def resource_managed_no_monitor_enabled(resource_id):
    """
    The resource which was set to managed mode has no monitor operations enabled

    string resource_id -- id of the resource
    """
    return ReportItem.warning(
        report_codes.RESOURCE_MANAGED_NO_MONITOR_ENABLED,
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

def cib_simulate_error(reason, cib):
    """
    cannot simulate effects a CIB would have on a live cluster

    string reason -- error description
    string cib -- the CIB whose effects were to be simulated
    """
    return ReportItem.error(
        report_codes.CIB_SIMULATE_ERROR,
        info={
            "reason": reason,
            "cib": cib,
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

def node_not_found(
    node, searched_types=None, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified node does not exist
    node string specified node
    searched_types list|string
    """
    return ReportItem(
        report_codes.NODE_NOT_FOUND,
        severity,
        info={
            "node": node,
            "searched_types": searched_types if searched_types else []
        },
        forceable=forceable
    )

def node_to_clear_is_still_in_cluster(
    node, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    specified node is still in cluster and `crm_node --remove` should be not
    used

    node string specified node
    """
    return ReportItem(
        report_codes.NODE_TO_CLEAR_IS_STILL_IN_CLUSTER,
        severity,
        info={
            "node": node,
        },
        forceable=forceable
    )

def node_remove_in_pacemaker_failed(
    node_list_to_remove, node=None, reason=None
):
    """
    Removing nodes from pacemaker failed.

    iterable node_list_to_remove -- nodes which should be removed
    string node -- node on which operation was performed
    string reason -- reason of failure
    """
    return ReportItem.error(
        report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
        info={
            "node": node,
            "node_list_to_remove": node_list_to_remove,
            "reason": reason,
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

def file_distribution_success(node, file_description):
    """
    a file has been successfuly distributed to a node

    string node -- name of a destination node
    string file_description -- name (code) of a sucessfully put file
    """
    return ReportItem.info(
        report_codes.FILE_DISTRIBUTION_SUCCESS,
        info={
            "node": node,
            "file_description": file_description,
        },
    )

def file_distribution_error(
    node, file_description, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    cannot put a file to a specific node

    string node -- name of a destination node
    string file_description -- code of a file
    string reason -- an error message
    """
    return ReportItem(
        report_codes.FILE_DISTRIBUTION_ERROR,
        severity,
        info={
            "node": node,
            "file_description": file_description,
            "reason": reason,
        },
        forceable=forceable
    )

def files_remove_from_nodes_started(file_list, node_list=None):
    """
    files are about to be removed from nodes

    iterable of strings file_list -- files to be sent
    iterable of strings node_list -- node names the files are being removed from
    """
    file_list = file_list if file_list else []
    return ReportItem.info(
        report_codes.FILES_REMOVE_FROM_NODES_STARTED,
        info={
            "file_list": file_list,
            "node_list": node_list,
        }
    )

def files_remove_from_nodes_skipped(reason_type, file_list, node_list):
    """
    Files removal skipped due to unreachable nodes or not live cluster

    string reason_type -- why was the action skipped (unreachable, not_live_cib)
    iterable of strings file_list -- contains description of files
    iterable of strings node_list -- node names the files are being removed from
    """
    return ReportItem.info(
        report_codes.FILES_REMOVE_FROM_NODES_SKIPPED,
        info={
            "reason_type": reason_type,
            "file_list": file_list,
            "node_list": node_list,
        }
    )

def file_remove_from_node_success(node, file_description):
    """
    files was successfuly removed nodes

    string node -- name of destination node
    string file_description -- name (code) of sucessfully put files
    """
    return ReportItem.info(
        report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
        info={
            "node": node,
            "file_description": file_description,
        },
    )

def file_remove_from_node_error(
    node, file_description, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    cannot remove files from specific nodes

    string node -- name of destination node
    string file_description -- is file code
    string reason -- is error message
    """
    return ReportItem(
        report_codes.FILE_REMOVE_FROM_NODE_ERROR,
        severity,
        info={
            "node": node,
            "file_description": file_description,
            "reason": reason,
        },
        forceable=forceable
    )

def service_commands_on_nodes_started(action_list, node_list=None):
    """
    node was requested for actions
    """
    action_list = action_list if action_list else []
    return ReportItem.info(
        report_codes.SERVICE_COMMANDS_ON_NODES_STARTED,
        info={
            "action_list": action_list,
            "node_list": node_list,
        }
    )

def service_commands_on_nodes_skipped(reason_type, action_list, node_list):
    """
    Service actions skipped due to unreachable nodes or not live cluster

    string reason_type -- why was the action skipped (unreachable, not_live_cib)
    list action_list -- contains description of service actions
    list node_list -- destinations where the action should have been executed
    """
    return ReportItem.info(
        report_codes.SERVICE_COMMANDS_ON_NODES_SKIPPED,
        info={
            "reason_type": reason_type,
            "action_list": action_list,
            "node_list": node_list,
        }
    )

def service_command_on_node_success(node, service_command_description):
    """
    files was successfuly distributed on nodes

    string service_command_description -- name (code) of sucessfully service
        command
    """
    return ReportItem.info(
        report_codes.SERVICE_COMMAND_ON_NODE_SUCCESS,
        info={
            "node": node,
            "service_command_description": service_command_description,
        },
    )

def service_command_on_node_error(
    node, service_command_description, reason,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    action on nodes failed

    string service_command_description -- name (code) of sucessfully service
        command
    string reason -- is error message
    """
    return ReportItem(
        report_codes.SERVICE_COMMAND_ON_NODE_ERROR,
        severity,
        info={
            "node": node,
            "service_command_description": service_command_description,
            "reason": reason,
        },
        forceable=forceable
    )


def invalid_response_format(node, severity=ReportItemSeverity.ERROR):
    """
    error message that response in invalid format has been received from
    specified node

    node -- node name
    """
    return ReportItem(
        report_codes.INVALID_RESPONSE_FORMAT,
        severity,
        info={"node": node}
    )

def sbd_not_used_cannot_set_sbd_options(options, node):
    """
    The cluster is not using SBD, cannot specify SBD options

    iterable options -- list of specified not allowed SBD options
    string node -- node name
    """
    return ReportItem.error(
        report_codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
        info={
            "node": node,
            "options": sorted(options)
        }
    )

def sbd_with_devices_not_used_cannot_set_device(node):
    """
    The cluster is not using SBD with devices, cannot specify a device.

    node -- node name
    """
    return ReportItem.error(
        report_codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE,
        info={
            "node": node,
        }
    )

def sbd_no_device_for_node(node, sbd_enabled_in_cluster=False):
    """
    No SBD device defined for a node when it should be

    string node -- node name
    bool sbd_enabled_in_cluster -- additional context for displaying the error
    """
    return ReportItem.error(
        report_codes.SBD_NO_DEVICE_FOR_NODE,
        info={
            "node": node,
            "sbd_enabled_in_cluster": sbd_enabled_in_cluster,
        }
    )

def sbd_too_many_devices_for_node(node, device_list, max_devices):
    """
    More than allowed number of SBD devices specified for a node

    string node -- node name
    list device_list -- list of SND devices specified for the node
    int max_devices -- maximum number of SBD devices
    """
    return ReportItem.error(
        report_codes.SBD_TOO_MANY_DEVICES_FOR_NODE,
        info={
            "node": node,
            "device_list": sorted(device_list),
            "max_devices": max_devices,
        }
    )

def sbd_device_path_not_absolute(device, node=None):
    """
    path of SBD device is not absolute
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_PATH_NOT_ABSOLUTE,
        info={
            "device": device,
            "node": node,
        }
    )


def sbd_device_does_not_exist(device, node):
    """
    specified device on node doesn't exist
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_DOES_NOT_EXIST,
        info={
            "device": device,
            "node": node,
        }
    )


def sbd_device_is_not_block_device(device, node):
    """
    specified device on node is not block device
    """
    return ReportItem.error(
        report_codes.SBD_DEVICE_IS_NOT_BLOCK_DEVICE,
        info={
            "device": device,
            "node": node,
        }
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
        },
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

    pcs.common.tools.Version current_version -- current version of CIB schema
    pcs.common.tools.Version required_version -- required version of CIB schema
    """
    return ReportItem.error(
        report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION,
        info={
            "required_version": str(required_version),
            "current_version": str(current_version)
        }
    )

def file_already_exists(
        file_type_code, file_path, severity=ReportItemSeverity.ERROR,
        forceable=None, node=None
    ):
    return ReportItem(
        report_codes.FILE_ALREADY_EXISTS,
        severity,
        info={
            "file_type_code": file_type_code,
            "file_path": file_path,
            "node": node,
        },
        forceable=forceable,
    )

def file_io_error(
    file_type_code, operation, reason, file_path="",
    severity=ReportItemSeverity.ERROR, forceable=None,
):
    """
    Unable to work with a file

    string file_type_code -- file type, item of pcs.common.file_type_codes
    string operation -- failed action, item of pcs.common.file.RawFileError
    string reason -- an error message
    string file_path -- file path, optional for cases when unknown (GhostFiles)
    """
    return ReportItem(
        report_codes.FILE_IO_ERROR,
        severity,
        info={
            "file_type_code": file_type_code,
            "file_path": file_path,
            "reason": reason,
            "operation": operation
        },
        forceable=forceable,
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
    """
    The command cannot operate in a non-live cluster (mocked / ghost files)

    iterable forbidden_options -- list of pcs.common.file_type_codes items which
        were given and are forbidden in the command
    """
    return ReportItem.error(
        report_codes.LIVE_ENVIRONMENT_REQUIRED,
        info={
            "forbidden_options": sorted(forbidden_options),
        }
    )

def live_environment_required_for_local_node():
    """
    The operation cannot be performed on CIB in file (not live cluster) if no
        node name is specified i.e. working with the local node
    """
    return ReportItem.error(
        report_codes.LIVE_ENVIRONMENT_REQUIRED_FOR_LOCAL_NODE,
    )

def live_environment_not_consistent(mocked_files, required_files):
    """
    The command cannot operate with mixed live / non-live cluster configs

    iterable mocked_files -- given mocked files (pcs.common.file_type_codes)
    iterable required_files -- files that must be mocked as well
    """
    return ReportItem.error(
        report_codes.LIVE_ENVIRONMENT_NOT_CONSISTENT,
        info={
            "mocked_files": sorted(mocked_files),
            "required_files": sorted(required_files),
        },
    )

def corosync_node_conflict_check_skipped(reason_type):
    """
    A command has been run with -f, can't check corosync.conf for node conflicts

    string reason_type -- why was the action skipped (unreachable, not_live_cib)
    """
    return ReportItem.info(
        report_codes.COROSYNC_NODE_CONFLICT_CHECK_SKIPPED,
        info={
            "reason_type": reason_type,
        }
    )

def corosync_quorum_atb_cannot_be_disabled_due_to_sbd(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Quorum option auto_tie_breaker cannot be disabled due to SBD.
    """
    return ReportItem(
        report_codes.COROSYNC_QUORUM_ATB_CANNOT_BE_DISABLED_DUE_TO_SBD,
        severity,
        forceable=forceable
    )


def corosync_quorum_atb_will_be_enabled_due_to_sbd():
    """
    Quorum option auto_tie_breaker will be enabled due to a user action in
    order to make SBD fencing effective. The cluster has to be stopped to make
    this change.
    """
    return ReportItem.warning(
        report_codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD
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


def fencing_level_already_exists(level, target_type, target_value, devices):
    """
    Fencing level already exists, it cannot be created
    """
    return ReportItem.error(
        report_codes.CIB_FENCING_LEVEL_ALREADY_EXISTS,
        info={
            "level": level,
            "target_type": target_type,
            "target_value": target_value,
            "devices": sorted(devices),
        }
    )

def fencing_level_does_not_exist(level, target_type, target_value, devices):
    """
    Fencing level does not exist, it cannot be updated or deleted
    """
    return ReportItem.error(
        report_codes.CIB_FENCING_LEVEL_DOES_NOT_EXIST,
        info={
            "level": level,
            "target_type": target_type,
            "target_value": target_value,
            "devices": devices,
        }
    )

def use_command_node_add_remote(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Advise the user for more appropriate command.
    """
    return ReportItem(
        report_codes.USE_COMMAND_NODE_ADD_REMOTE,
        severity,
        info={},
        forceable=forceable
    )

def use_command_node_add_guest(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Advise the user for more appropriate command.
    """
    return ReportItem(
        report_codes.USE_COMMAND_NODE_ADD_GUEST,
        severity,
        info={},
        forceable=forceable
    )

def use_command_node_remove_guest(
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Advise the user for more appropriate command.
    """
    return ReportItem(
        report_codes.USE_COMMAND_NODE_REMOVE_GUEST,
        severity,
        info={},
        forceable=forceable
    )

def tmp_file_write(file_path, content):
    """
    It has been written into a temporary file
    string file_path -- the file path
    string content -- content which has been written
    """
    return ReportItem.debug(
        report_codes.TMP_FILE_WRITE,
        info={
            "file_path": file_path,
            "content": content,
        }
    )

def node_addresses_unresolvable(
    address_list,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Unable to resolve addresses of cluster nodes to be added

    iterable address -- a list of unresolvable addresses
    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.NODE_ADDRESSES_UNRESOLVABLE,
        severity,
        forceable,
        info={
            "address_list": sorted(address_list),
        }
    )

def unable_to_perform_operation_on_any_node():
    """
    This report is raised whenever
    pcs.lib.communication.tools.OneByOneStrategyMixin strategy mixin is used
    for network communication and operation failed on all available hosts and
    because of this it is not possible to continue.
    """
    return ReportItem.error(
        report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE,
    )


def host_not_found(
    host_list, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Hosts with names in host_list are not included in pcs known hosts,
    therefore it is not possible to communicate with them.
    """
    return ReportItem(
        report_codes.HOST_NOT_FOUND,
        severity,
        info=dict(
            host_list=sorted(host_list),
        ),
        forceable=forceable,
    )

def none_host_found():
    return ReportItem.error(report_codes.NONE_HOST_FOUND)

def host_already_authorized(host_name):
    return ReportItem.info(
        report_codes.HOST_ALREADY_AUTHORIZED,
        info=dict(
            host_name=host_name,
        )
    )


def cluster_destroy_started(host_name_list):
    return ReportItem.info(
        report_codes.CLUSTER_DESTROY_STARTED,
        info=dict(
            host_name_list=sorted(host_name_list),
        ),
    )


def cluster_destroy_success(node):
    return ReportItem.info(
        report_codes.CLUSTER_DESTROY_SUCCESS,
        info=dict(
            node=node,
        ),
    )


def cluster_enable_started(host_name_list):
    return ReportItem.info(
        report_codes.CLUSTER_ENABLE_STARTED,
        info=dict(
            host_name_list=sorted(host_name_list),
        ),
    )


def cluster_enable_success(node):
    return ReportItem.info(
        report_codes.CLUSTER_ENABLE_SUCCESS,
        info=dict(
            node=node,
        ),
    )


def cluster_start_started(host_name_list):
    return ReportItem.info(
        report_codes.CLUSTER_START_STARTED,
        info=dict(
            host_name_list=sorted(host_name_list),
        ),
    )


def cluster_start_success(node):
    return ReportItem.info(
        report_codes.CLUSTER_START_SUCCESS,
        info=dict(
            node=node,
        ),
    )


def service_not_installed(
    node, service_list, severity=ReportItemSeverity.ERROR, forceable=None
):
    return ReportItem(
        report_codes.SERVICE_NOT_INSTALLED,
        severity,
        info=dict(
            node=node,
            service_list=sorted(service_list),
        ),
        forceable=forceable,
    )

def host_already_in_cluster_config(
    host_name, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    A host, which is being added to a cluster, already has cluster configs
    string host_name -- a name of the host which is in a cluster already
    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
        severity,
        info=dict(
            host_name=host_name,
        ),
        forceable=forceable,
    )

def host_already_in_cluster_services(
    host_name, service_list, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    A host, which is being added to a cluster, already runs cluster daemons
    string host_name -- a name of the host which is in a cluster already
    iterable service_list -- list of cluster daemons running on the host
    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
        severity,
        info=dict(
            host_name=host_name,
            service_list=sorted(service_list),
        ),
        forceable=forceable,
    )

def service_version_mismatch(
    service, hosts_version,
    severity=ReportItemSeverity.ERROR, forceable=None,
):
    return ReportItem(
        report_codes.SERVICE_VERSION_MISMATCH,
        severity,
        info=dict(
            service=service,
            hosts_version=hosts_version,
        ),
        forceable=forceable,
    )


def wait_for_node_startup_started(node_name_list):
    return ReportItem.info(
        report_codes.WAIT_FOR_NODE_STARTUP_STARTED,
        info=dict(
            node_name_list=sorted(node_name_list),
        )
    )


def wait_for_node_startup_timed_out():
    return ReportItem.error(report_codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT)


def wait_for_node_startup_error():
    return ReportItem.error(report_codes.WAIT_FOR_NODE_STARTUP_ERROR)

def wait_for_node_startup_without_start():
    """
    User requested waiting for nodes to start without instructing pcs to start
    the nodes
    """
    return ReportItem.error(report_codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START)

def pcsd_version_too_old(node):
    return ReportItem.error(
        report_codes.PCSD_VERSION_TOO_OLD,
        info=dict(
            node=node,
        )
    )

def pcsd_ssl_cert_and_key_distribution_started(node_name_list):
    """
    We are about to distribute pcsd SSL certificate and key to nodes

    iterable node_name_list -- node names to distribute to
    """
    return ReportItem.info(
        report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
        info={
            "node_name_list": sorted(node_name_list),
        }
    )

def pcsd_ssl_cert_and_key_set_success(node):
    """
    Pcsd SSL certificate and key have been succesfuly saved on a node

    string node -- node name
    """
    return ReportItem.info(
        report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS,
        info={
            "node": node,
        }
    )

def cluster_will_be_destroyed():
    """
    If the user continues with force, cluster will be destroyed on some hosts
    """
    return ReportItem.error(
        report_codes.CLUSTER_WILL_BE_DESTROYED,
        forceable=report_codes.FORCE_ALREADY_IN_CLUSTER,
    )


def cluster_setup_success():
    return ReportItem.info(report_codes.CLUSTER_SETUP_SUCCESS)

def using_known_host_address_for_host(host_name, address):
    """
    When no address was specified for a host, its known-host address was used
    """
    return ReportItem.info(
        report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
        info={
            "host_name": host_name,
            "address": address
        }
    )

def resource_in_bundle_not_accessible(
    bundle_id, inner_resource_id,
    severity=ReportItemSeverity.ERROR, forceable=report_codes.FORCE_OPTIONS,
):
    return ReportItem(
        report_codes.RESOURCE_IN_BUNDLE_NOT_ACCESSIBLE,
        severity,
        info=dict(
            bundle_id=bundle_id,
            inner_resource_id=inner_resource_id,
        ),
        forceable=forceable,
    )

def using_default_watchdog(watchdog, node):
    """
    No watchdog has been specified for the node, therefore pcs will use
    a default watchdog.
    """
    return ReportItem.info(
        report_codes.USING_DEFAULT_WATCHDOG,
        info=dict(
            watchdog=watchdog,
            node=node,
        )
    )

def cannot_remove_all_cluster_nodes():
    """
    It is not possible to remove all cluster nodes using 'pcs cluster node
    remove' command. 'pcs cluster destroy --all' should be used in such case.
    """
    return ReportItem.error(
        report_codes.CANNOT_REMOVE_ALL_CLUSTER_NODES,
    )

def unable_to_connect_to_any_remaining_node():
    """
    All ramaining cluster nodes are unreachable, therefore it is not possible
    to remove nodes from the cluster.
    """
    return ReportItem.error(
        report_codes.UNABLE_TO_CONNECT_TO_ANY_REMAINING_NODE,
    )

def unable_to_connect_to_all_remaining_node(node_list):
    """
    Some of remaining cluster nodes are unreachable. 'pcs cluster sync' should
    be executed on now online nodes when the offline nodes come back online.

    iterable node_list -- names of nodes which are staying in the cluster and
        are currently unreachable
    """
    return ReportItem.warning(
        report_codes.UNABLE_TO_CONNECT_TO_ALL_REMAINING_NODE,
        info=dict(
            node_list=sorted(node_list),
        )
    )

def nodes_to_remove_unreachable(node_list):
    """
    Nodes which should be removed are currently unreachable. 'pcs cluster
    destroy' should be executed on these nodes when they come back online.

    iterable node_list -- names of nodes which are being removed from the
        cluster but they are currently unreachable
    """
    return ReportItem.warning(
        report_codes.NODES_TO_REMOVE_UNREACHABLE,
        info=dict(
            node_list=sorted(node_list),
        )
    )

def node_used_as_tie_breaker(node, node_id):
    """
    Node which should be removed is currently used as a tie breaker for a
    qdevice, therefore it is not possible to remove it from the cluster.

    string node -- node name
    string nide_id -- node id
    """
    return ReportItem.error(
        report_codes.NODE_USED_AS_TIE_BREAKER,
        info=dict(
            node=node,
            node_id=node_id,
        )
    )

def corosync_quorum_will_be_lost(
    severity=ReportItemSeverity.ERROR, forceable=None,
):
    """
    Ongoing action will cause loss of the quorum in the cluster.

    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.COROSYNC_QUORUM_WILL_BE_LOST,
        severity,
        forceable=forceable,
    )

def corosync_quorum_loss_unable_to_check(
    severity=ReportItemSeverity.ERROR, forceable=None,
):
    """
    It is not possible to check if ongoing action will cause loss of the quorum

    string severity -- report item severity
    mixed forceable -- is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.COROSYNC_QUORUM_LOSS_UNABLE_TO_CHECK,
        severity,
        forceable=forceable,
    )

def sbd_list_watchdog_error(reason):
    """
    Unable to get list of available watchdogs from sbd. Sbd cmd reutrned non 0.

    string reason -- stderr of command
    """
    return ReportItem.error(
        report_codes.SBD_LIST_WATCHDOG_ERROR,
        info=dict(
            reason=reason,
        )
    )


def sbd_watchdog_not_supported(node, watchdog):
    """
    Specified watchdog is not supported in sbd (softdog?).

    string node -- node name
    string watchdog -- watchdog path
    """
    return ReportItem.error(
        report_codes.SBD_WATCHDOG_NOT_SUPPORTED,
        info=dict(
            node=node,
            watchdog=watchdog,
        ),
    )


def sbd_watchdog_validation_inactive():
    """
    Warning message about not validating watchdog.
    """
    return ReportItem.warning(
        report_codes.SBD_WATCHDOG_VALIDATION_INACTIVE,
    )


def sbd_watchdog_test_error(reason):
    """
    Sbd test watchdog exited with an error.
    """
    return ReportItem.error(
        report_codes.SBD_WATCHDOG_TEST_ERROR,
        info=dict(
            reason=reason,
        )
    )


def sbd_watchdog_test_multiple_devices():
    """
    No watchdog device has been specified for test. Because of multiple
    available watchdogs, watchdog device to test has to be specified.
    """
    return ReportItem.error(
        report_codes.SBD_WATCHDOG_TEST_MULTUPLE_DEVICES,
    )


def sbd_watchdog_test_failed():
    """
    System has not been reset.
    """
    return ReportItem.error(
        report_codes.SBD_WATCHDOG_TEST_FAILED,
    )


def system_will_reset():
    return ReportItem.info(
        report_codes.SYSTEM_WILL_RESET,
    )


def resource_bundle_unsupported_container_type(
    bundle_id, supported_container_types
):
    return ReportItem.error(
        report_codes.RESOURCE_BUNDLE_UNSUPPORTED_CONTAINER_TYPE,
        info=dict(
            bundle_id=bundle_id,
            supported_container_types=sorted(supported_container_types),
        ),
    )

def fence_history_command_error(reason, command_label):
    """
    pacemaker command for working with fence history returned an error
    string reason -- output of the pacemaker command
    string command_label -- label of the command - what it should have achieved
    """
    return ReportItem.error(
        report_codes.FENCE_HISTORY_COMMAND_ERROR,
        info={
            "reason": reason,
            "command_label": command_label,
        }
    )

def fence_history_not_supported():
    """
    pacemaker does not support the fence history feature
    """
    return ReportItem.error(
        report_codes.FENCE_HISTORY_NOT_SUPPORTED
    )

def resource_instance_attr_value_not_unique(
    instance_attr_name, instance_attr_value, agent_name, resource_id_list,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Value of a resource instance attribute is not unique in the configuration
    when creating/updating a resource

    instance_attr_name string -- name of attr which should be unique
    instance_attr_value string -- value which is already used by some resources
    agent_name string -- resource agent name of resource
    resource_id_list list of string -- resource ids which already have the
        instance_attr_name set to instance_attr_value
    severity string -- report item severity
    forceable mixed
    """
    return ReportItem(
        report_codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE,
        severity,
        info=dict(
            instance_attr_name=instance_attr_name,
            instance_attr_value=instance_attr_value,
            agent_name=agent_name,
            resource_id_list=resource_id_list,
        ),
        forceable=forceable,
    )

def cannot_move_resource_bundle(resource_id):
    """
    User is trying to move a bundle resource which is not possible

    string resource_id -- id of the resource to be moved
    """
    return ReportItem.error(
        report_codes.CANNOT_MOVE_RESOURCE_BUNDLE,
        info={
            "resource_id": resource_id,
        }
    )

def cannot_move_resource_clone(resource_id):
    """
    User is trying to move a clone resource which is not possible

    string resource_id -- id of the resource to be moved
    """
    return ReportItem.error(
        report_codes.CANNOT_MOVE_RESOURCE_CLONE,
        info={
            "resource_id": resource_id,
        }
    )

def cannot_move_resource_promotable_not_master(resource_id, promotable_id):
    """
    User is trying to move a promotable clone without limiting it to master role

    string resource_id -- id of the resource to be moved
    string promotable_id -- id of relevant parent promotable resource
    """
    return ReportItem.error(
        report_codes.CANNOT_MOVE_RESOURCE_PROMOTABLE_NOT_MASTER,
        info={
            "resource_id": resource_id,
            "promotable_id": promotable_id,
        }
    )

def cannot_move_resource_master_resource_not_promotable(
    resource_id, promotable_id=None
):
    """
    User is trying to move a non-promotable resource and limit it to master role

    string resource_id -- id of the resource to be moved
    string promotable_id -- id of relevant parent promotable resource
    """
    return ReportItem.error(
        report_codes.CANNOT_MOVE_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE,
        info={
            "resource_id": resource_id,
            "promotable_id": promotable_id,
        }
    )

def cannot_move_resource_stopped_no_node_specified(resource_id):
    """
    When moving a stopped resource, a node to move it to must be specified

    string resource_id -- id of the resource to be moved
    """
    return ReportItem.error(
        report_codes.CANNOT_MOVE_RESOURCE_STOPPED_NO_NODE_SPECIFIED,
        info={
            "resource_id": resource_id,
        }
    )

def resource_move_pcmk_error(resource_id, stdout, stderr):
    """
    crm_resource exited with an error when moving a resource

    string resource_id -- id of the resource to be moved
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.error(
        report_codes.RESOURCE_MOVE_PCMK_ERROR,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def resource_move_pcmk_success(resource_id, stdout, stderr):
    """
    crm_resource exited successfully when moving a resource

    string resource_id -- id of the resource to be moved
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.info(
        report_codes.RESOURCE_MOVE_PCMK_SUCCESS,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def cannot_ban_resource_master_resource_not_promotable(
    resource_id, promotable_id=None
):
    """
    User is trying to ban a non-promotable resource and limit it to master role

    string resource_id -- id of the resource to be banned
    string promotable_id -- id of relevant parent promotable resource
    """
    return ReportItem.error(
        report_codes.CANNOT_BAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE,
        info={
            "resource_id": resource_id,
            "promotable_id": promotable_id,
        }
    )

def cannot_ban_resource_stopped_no_node_specified(resource_id):
    """
    When banning a stopped resource, a node to ban it on must be specified

    string resource_id -- id of the resource to be banned
    """
    return ReportItem.error(
        report_codes.CANNOT_BAN_RESOURCE_STOPPED_NO_NODE_SPECIFIED,
        info={
            "resource_id": resource_id,
        }
    )

def resource_ban_pcmk_error(resource_id, stdout, stderr):
    """
    crm_resource exited with an error when banning a resource

    string resource_id -- id of the resource to be banned
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.error(
        report_codes.RESOURCE_BAN_PCMK_ERROR,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def resource_ban_pcmk_success(resource_id, stdout, stderr):
    """
    crm_resource exited successfully when banning a resource

    string resource_id -- id of the resource to be banned
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.info(
        report_codes.RESOURCE_BAN_PCMK_SUCCESS,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def cannot_unmove_unban_resource_master_resource_not_promotable(
    resource_id, promotable_id=None
):
    """
    User is trying to unmove/unban master of a non-promotable resource

    string resource_id -- id of the resource to be unmoved/unbanned
    string promotable_id -- id of relevant parent promotable resource
    """
    return ReportItem.error(
        report_codes.CANNOT_UNMOVE_UNBAN_RESOURCE_MASTER_RESOURCE_NOT_PROMOTABLE
        ,
        info={
            "resource_id": resource_id,
            "promotable_id": promotable_id,
        }
    )

def resource_unmove_unban_pcmk_expired_not_supported():
    """
    crm_resource does not support --expired when unmoving/unbanning a resource
    """
    return ReportItem.error(
        report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_EXPIRED_NOT_SUPPORTED,
    )

def resource_unmove_unban_pcmk_error(resource_id, stdout, stderr):
    """
    crm_resource exited with an error when unmoving/unbanning a resource

    string resource_id -- id of the resource to be unmoved/unbanned
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.error(
        report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_ERROR,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def resource_unmove_unban_pcmk_success(resource_id, stdout, stderr):
    """
    crm_resource exited successfully when clearing unmoving/unbanning a resource

    string resource_id -- id of the resource to be unmoved/unbanned
    string stdout -- stdout of crm_resource
    string stderr -- stderr of crm_resource
    """
    return ReportItem.info(
        report_codes.RESOURCE_UNMOVE_UNBAN_PCMK_SUCCESS,
        info={
            "resource_id": resource_id,
            "stdout": stdout,
            "stderr": stderr,
        }
    )

def parse_error_json_file(
    file_type_code, line_number, column_number, position, reason, full_msg,
    file_path=None, severity=ReportItemSeverity.ERROR, forceable=None,
):
    # pylint: disable=too-many-arguments
    """
    Unable to parse a file with JSON data

    string file_type_code -- item from pcs.common.file_type_codes
    int line_number -- the line where parsing failed
    int column_number -- the column where parsing failed
    int position -- the start index of the file where parsing failed
    string reason -- the unformatted error message
    string full_msg -- full error message including above int attributes
    string file_path -- path to the parsed file if available
    """
    return ReportItem(
        report_codes.PARSE_ERROR_JSON_FILE,
        severity,
        info={
            "file_type_code": file_type_code,
            "line_number": line_number,
            "column_number": column_number,
            "position": position,
            "reason": reason,
            "full_msg": full_msg,
            "file_path": file_path,
        },
        forceable=forceable
    )

def resource_disable_affects_other_resources(
    disabled_resource_list,
    affected_resource_list,
    crm_simulate_plaintext_output
):
    """
    User requested disabling resources without affecting other resources but
    some resources would be affected

    iterable disabled_resource_list -- list of resources to disable
    iterable affected_resource_list -- other affected resources
    string crm_simulate_plaintext_output -- plaintext output from pacemaker
    """
    return ReportItem.error(
        report_codes.RESOURCE_DISABLE_AFFECTS_OTHER_RESOURCES,
        info={
            "disabled_resource_list": sorted(disabled_resource_list),
            "affected_resource_list": sorted(affected_resource_list),
            "crm_simulate_plaintext_output": crm_simulate_plaintext_output,
        }
    )
