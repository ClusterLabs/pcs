from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItem, ReportItemSeverity


def booth_lack_of_sites(site_list):
    """
    Less than 2 booth sites entered. But it does not make sense.
    list site_list contains currently entered sites
    """
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

def booth_even_peers_num(number):
    """
    Booth requires odd number of peers. But even number of peers was entered.
    integer number determines how many peers was entered
    """
    return ReportItem.error(
        report_codes.BOOTH_EVEN_PEERS_NUM,
        "odd number of peers is required (entered {number} peers)",
        info={
            "number": number,
        }
    )

def booth_address_duplication(duplicate_addresses):
    """
    Address of each peer must unique. But address duplication appeared.
    set duplicate_addresses contains addreses entered multiple times
    """
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
    """
    Booth config have defined structure. But line out of structure definition
        appeared.
    list line_list contains lines out of defined structure
    """
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_UNEXPECTED_LINES,
        "unexpected line appeard in config: \n{lines_string}",
        info={
            "line_list": line_list,
            "lines_string": "\n".join(line_list)
        }
    )

def booth_invalid_name(name, reason):
    """
    Booth instance name have rules. For example it cannot contain illegal
        characters like '/'. But some of rules was violated.
    string name is entered booth instance name
    """
    return ReportItem.error(
        report_codes.BOOTH_INVALID_NAME,
            "booth name '{name}' is not valid ({reason})"
        ,
        info={
            "name": name,
            "reason": reason,
        }
    )

def booth_ticket_name_invalid(ticket_name):
    """
    Name of booth ticket may consists of alphanumeric characters or dash.
        Entered ticket name violating this rule.
    string ticket_name is entered booth ticket name
    """
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
    """
    Each booth ticket name must be uniqe. But duplicate booth ticket name
        was entered.
    string ticket_name is entered booth ticket name
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_DUPLICATE,
        "booth ticket name '{ticket_name}' already exists in configuration",
        info={
            "ticket_name": ticket_name,
        }
    )

def booth_ticket_does_not_exist(ticket_name):
    """
    Some operations (like ticket remove) expect the ticket name in booth
        configuration. But the ticket name not found in booth configuration.
    string ticket_name is entered booth ticket name
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_DOES_NOT_EXIST,
        "booth ticket name '{ticket_name}' does not exist",
        info={
            "ticket_name": ticket_name,
        }
    )

def booth_already_in_cib(name):
    """
    Each booth instance should be in a cib once maximally. Existence of booth
        instance in cib detected during creating new one.
    string name is booth instance name
    """
    return ReportItem.error(
        report_codes.BOOTH_ALREADY_IN_CIB,
        "booth instance '{name}' is already created as cluster resource",
        info={
            "name": name,
        }
    )

def booth_not_exists_in_cib(config_file_path):
    """
    Remove booth instance from cib required. But no such instance found in cib.
    string config_file_path
    """
    return ReportItem.error(
        report_codes.BOOTH_NOT_EXISTS_IN_CIB,
        "booth for config '{config_file_path}' not found in cib",
        info={
            "config_file_path": config_file_path,
        }
    )

def booth_config_is_used(config_file_path, detail=""):
    """
    Booth config use detected during destroy request.
    string config_file_path
    string detail provide more details (for example booth instance is used as
        cluster resource or is started/enabled under systemd)
    """
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
    """
    Each booth instance should be in a cib once maximally. But multiple
        occurences detected. For example during remove booth instance from cib.
        Notify user about this fact is required. When operation is forced
        user should be notified about multiple occurences.
    string config_file_path
    ReportItemSeverity severit should be ERROR or WARNING (depends on context)
        is flag for next report processing
        Because of severity coupling with ReportItem is it specified here.
    """
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


def booth_config_saved(node=None, name_list=None):
    """
    Booth config has been saved on specified node.

    node -- name of node
    name_list -- list of names of booth instance
    """
    if name_list:
        name = ", ".join(name_list)
        if name == "booth":
            msg = "Booth config saved."
        else:
            msg = "Booth config(s) ({name}) saved."
    else:
        msg = "Booth config saved."
        name = None
    return ReportItem.info(
        report_codes.BOOTH_CONFIGS_SAVED_ON_NODE,
        msg if node is None else "{node}: " + msg,
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


def booth_tickets_status_error(reason=None):
    return ReportItem.error(
        report_codes.BOOTH_TICKET_STATUS_ERROR,
        "unable to get status of booth tickets",
        info={
            "reason": reason,
        }
    )


def booth_peers_status_error(reason=None):
    return ReportItem.error(
        report_codes.BOOTH_PEERS_STATUS_ERROR,
        "unable to get status of booth peers",
        info={
            "reason": reason,
        }
    )

def booth_cannot_determine_local_site_ip():
    """
    Some booth operations are performed on specific site and requires to specify
        site ip. When site specification omitted pcs can try determine local ip.
        But determine local site ip failed.
    """
    return ReportItem.error(
        report_codes.BOOTH_CANNOT_DETERMINE_LOCAL_SITE_IP,
        "cannot determine local site ip, please specify site parameter",
        info={}
    )

def booth_ticket_operation_failed(operation, reason, site_ip, ticket_name):
    """
    Pcs uses external booth tools for some ticket_name operations. For example grand
        and revoke. But the external command failed.
    string operatin determine what was intended perform with ticket_name
    string reason is taken from external booth command
    string site_ip specifiy what site had to run the command
    string ticket_name specify with which ticket had to run the command
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_OPERATION_FAILED,
        "unable to {operation} booth ticket_name '{ticket_name}' for site '{site_ip}', "
            "reason: {reason}"
        ,
        info={
            "operation": operation,
            "reason": reason,
            "site_ip": site_ip,
            "ticket_name": ticket_name,
        }
    )
