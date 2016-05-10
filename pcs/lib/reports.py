from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItem

def required_option_is_missing(name):
    return ReportItem.error(
        report_codes.REQUIRED_OPTION_IS_MISSING,
        "required attribute '{name}' is missing",
        info={
            "name": name
        },
    )

def resource_for_constraint_is_multiinstance(
    resource_id, parent_type, parent_id
):
    template = (
        "{resource_id} is a clone resource, you should use the"
        +" clone id: {parent_id} when adding constraints"
    )
    if parent_type != "clone":
        template = (
            "{resource_id} is a master/slave resource, you should use the"
            +" master id: {parent_id} when adding constraints"
        )

    return ReportItem.error(
        report_codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
        template,
        forceable=True,
        info={
            'resource_id': resource_id,
            'parent_type': parent_type,
            'parent_id': parent_id,
        },
    )

def empty_resource_set_list():
    return ReportItem.error(
        report_codes.EMPTY_RESOURCE_SET_LIST,
        "Resource set list is empty",
    )


def resource_does_not_exist(resource_id):
    return ReportItem.error(
        report_codes.RESOURCE_DOES_NOT_EXIST,
        "Resource '{resource_id}' does not exist",
        info={
            'resource_id': resource_id,
        },
    )

def invalid_option(allowed_options, option_name):
    return ReportItem.error(
        report_codes.INVALID_OPTION,
        "invalid option '{option}', allowed options are: {allowed}",
        info={
            'option': option_name,
            'allowed_raw': sorted(allowed_options),
            'allowed': ", ".join(sorted(allowed_options))
        },
    )

def invalid_option_value(allowed_values, option_name, option_value):
    return ReportItem.error(
        report_codes.INVALID_OPTION_VALUE,
        "invalid value '{option_value}' of option '{option_name}',"
            +" allowed values are: {allowed_values}",
        info={
            'option_value': option_value,
            'option_name': option_name,
            'allowed_values_raw': allowed_values,
            'allowed_values': ", ".join(allowed_values)
        },
    )

def duplicate_constraints_exist(type, constraint_info_list):
    return ReportItem.error(
        report_codes.DUPLICATE_CONSTRAINTS_EXIST,
        "duplicate constraint already exists",
        forceable=True,
        info={
            'type': type,
            'constraint_info_list': constraint_info_list,
        },
    )

def multiple_score_options():
    return ReportItem.error(
        report_codes.MULTIPLE_SCORE_OPTIONS,
        "you cannot specify multiple score options",
    )

def invalid_score(score):
    return ReportItem.error(
        report_codes.INVALID_SCORE,
        "invalid score '{score}', use integer or INFINITY or -INFINITY",
        info={
            "score": score,
        }
    )

def run_external_process_started(argv, stdin):
    msg = "Running: {argv}"
    if stdin:
        msg += "\n--Debug Input Start--\n{stdin}\n--Debug Input End--"
    msg += "\n"
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_STARTED,
        msg,
        info={
            "argv": argv,
            "stdin": stdin,
        }
    )

def run_external_process_finished(argv, retval, stdout):
    return ReportItem.debug(
        report_codes.RUN_EXTERNAL_PROCESS_FINISHED,
        "Finished running: {argv}\nReturn value: {return_value}"
        + "\n--Debug Output Start--\n{stdout}\n--Debug Output End--\n",
        info={
            "argv": argv,
            "return_value": retval,
            "stdout": stdout,
        }
    )

def node_communication_started(target, data):
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
    return ReportItem.debug(
        report_codes.NODE_COMMUNICATION_NOT_CONNECTED,
        "Unable to connect to {node} ({reason})",
        info={
            "node": node,
            "reason": reason,
        }
    )

def corosync_config_distribution_started():
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED,
        "Sending updated corosync.conf to nodes..."
    )

def corosync_config_accepted_by_node(node):
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
        "{node}: Succeeded",
        info={"node": node}
    )

def corosync_config_reloaded():
    return ReportItem.info(
        report_codes.COROSYNC_CONFIG_RELOADED,
        "Corosync configuration reloaded"
    )
