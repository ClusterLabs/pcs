from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItem, ReportItemSeverity


def booth_lack_of_sites(site_list):
    return ReportItem.error(
        report_codes.BOOTH_LACK_OF_SITES,
        "lack of sites for booth configuration (need 2 at least):"
            " sites {sites_string}"
        ,
        info={
            "sites": site_list,
            "sites_string": ", ".join(site_list) if site_list else "missing",
        }
    )

def booth_even_paticipants_num(number):
    return ReportItem.error(
        report_codes.BOOTH_EVEN_PARTICIPANTS_NUM,
        "odd number of participants ({number})",
        info={
            "number": number,
        }
    )

def booth_address_duplication(duplicate_addresses):
    return ReportItem.error(
        report_codes.BOOTH_ADDRESS_DUPLICATION,
        "duplicate address for booth configuration: {addresses_string}"
        ,
        info={
            "addresses": duplicate_addresses,
            "addresses_string": ", ".join(duplicate_addresses),
        }
    )

def booth_config_unexpected_lines(line_list):
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
        "unexpected line appeard in config: \n{lines_string}",
        info={
            "line_list": line_list,
            "lines_string": "\n".join(line_list)
        }
    )

def booth_config_invalid_content(reason):
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_INVALID_CONTENT,
        "booth config has invalid content: '{reason}'",
        info={
            "reason": reason,
        }
    )

def booth_invalid_name(name):
    return ReportItem.error(
        report_codes.BOOTH_INVALID_NAME,
        "booth name '{name}' is not valid",
        info={
            "name": name,
        }
    )

def booth_ticket_name_invalid(ticket_name):
    return ReportItem.error(
        report_codes.BOOTH_TICKET_NAME_INVALID,
        "booth ticket name '{ticket_name}' is not valid,"
            " use alphanumeric chars or dash"
        ,
        info={
            "ticket_name": ticket_name,
        }
    )

def booth_ticket_duplicate(ticket_name):
    return ReportItem.error(
        report_codes.BOOTH_TICKET_DUPLICATE,
        "booth ticket name '{ticket_name}' already exists in configuration",
        info={
            "ticket_name": ticket_name,
        }
    )

def booth_ticket_does_not_exist(ticket_name):
    return ReportItem.error(
        report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
        "booth ticket name '{ticket_name}' does not exist",
        info={
            "ticket_name": ticket_name,
        }
    )

def booth_already_created(config_file_path):
    return ReportItem.error(
        report_codes.BOOTH_ALREADY_CREATED,
        "booth for config '{config_file_path}' is already created",
        info={
            "config_file_path": config_file_path,
        }
    )

def booth_not_exists_in_cib(config_file_path):
    return ReportItem.error(
        report_codes.BOOTH_NOT_EXISTS_IN_CIB,
        "booth for config '{config_file_path}' not found in cib",
        info={
            "config_file_path": config_file_path,
        }
    )

def booth_config_is_used(config_file_path, detail=""):
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_IS_USED,
        "booth for config '{config_file_path}' is used{detail_string}",
        info={
            "config_file_path": config_file_path,
            "detail": detail,
            "detail_string": " {0}".format(detail) if detail else "",
        }
    )

def booth_multiple_times_in_cib(
    config_file_path, severity=ReportItemSeverity.ERROR
):
    return ReportItem(
        report_codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
        severity,
        "found more than one booth for config '{config_file_path}' in cib",
        info={
            "config_file_path": config_file_path,
        },
        forceable=report_codes.FORCE_BOOTH_REMOVE_FROM_CIB
            if severity == ReportItemSeverity.ERROR else None
    )


def booth_distributing_config(name=None):
    """
    Sending booth config to all nodes in cluster.

    name -- name of booth instance
    """
    return ReportItem.info(
        report_codes.BOOTH_DISTRIBUTING_CONFIG,
        "Sending booth config{0} to all cluster nodes.".format(
            " ({name})" if name and name != "booth" else ""
        ),
        info={"name": name}
    )


def booth_config_saved(node, name_list=None):
    """
    Booth config has been saved on specified node.

    node -- name of node
    name_list -- list of names of booth instance
    """
    if name_list:
        name = ", ".join(name_list)
        if name == "booth":
            msg = "{node}: Booth config saved."
        else:
            msg = "{node}: Booth config(s) ({name}) saved."
    else:
        msg = "{node}: Booth config saved."
        name = None
    return ReportItem.info(
        report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
        msg,
        info={
            "node": node,
            "name": name,
            "name_list": name_list
        }
    )


def booth_config_unable_to_read(
    name, severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    Unable to read from specified booth instance config.

    name -- name of booth instance
    severity -- severity of report item
    forceable -- is this report item forceable? by what category?
    """
    if name and name != "booth":
        msg = "Unable to read booth config ({name})."
    else:
        msg = "Unable to read booth config."
    return ReportItem(
        report_codes.BOOTH_CONFIG_READ_ERROR,
        severity,
        msg,
        info={"name": name},
        forceable=forceable
    )


def booth_config_not_saved(node, reason, name=None):
    """
    Saving booth config failed on specified node.

    node -- node name
    reason -- reason of failure
    name -- name of booth instance
    """
    if name and name != "booth":
        msg = "Unable to save booth config ({name}) on node '{node}': {reason}"
    else:
        msg = "Unable to save booth config on node '{node}': {reason}"
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_WRITE_ERROR,
        msg,
        info={
            "node": node,
            "name": name,
            "reason": reason
        }
    )


def booth_sending_local_configs_to_node(node):
    """
    Sending all local booth configs to node

    node -- node name
    """
    return ReportItem.info(
        report_codes.BOOTH_CONFIGS_SAVING_ON_NODE,
        "{node}: Saving booth config(s)...",
        info={"node": node}
    )


def booth_fetching_config_from_node(node, config=None):
    if config or config == 'booth':
        msg = "Fetching booth config from node '{node}'..."
    else:
        msg = "Fetching booth config '{config}' from node '{node}'..."
    return ReportItem.info(
        report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
        msg,
        info={
            "node": node,
            "config": config,
        }
    )


def booth_unsupported_file_location(file):
    return ReportItem.warning(
        report_codes.BOOTH_UNSUPORTED_FILE_LOCATION,
        "skipping file {file}: unsupported file location",
        info={"file": file}
    )


def booth_daemon_status_error(reason):
    return ReportItem.error(
        report_codes.BOOTH_DAEMON_STATUS_ERROR,
        "unable to get status of booth daemon: {reason}",
        info={"reason": reason}
    )


def booth_tickets_status_error():
    return ReportItem.error(
        report_codes.BOOTH_TICKET_STATUS_ERROR,
        "unable to get status of booth tickets"
    )


def booth_peers_status_error():
    return ReportItem.error(
        report_codes.BOOTH_PEERS_STATUS_ERROR,
        "unable to get status of booth peers"
    )

def booth_correct_config_not_found_in_cib(operation):
    return ReportItem.error(
        report_codes.BOOTH_CORRECT_CONFIG_NOT_FOUND_IN_CIB,
        "correct booth configuration not found,"
        " can not {operation} ticket to implicit site,"
        " please specify site parameter",
        info={
            "operation": operation,
        }
    )

def booth_ticket_operation_failed(operation, reason, site_ip, ticket):
    return ReportItem.error(
        report_codes.BOOTH_TICKET_OPERATION_FAILED,
        "unable to {operation} booth ticket '{ticket}' for site '{site_ip}', "
            "reason: {reason}"
        ,
        info={
            "operation": operation,
            "reason": reason,
            "site_ip": site_ip,
            "ticket": ticket,
        }
    )
