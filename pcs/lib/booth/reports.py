from pcs.common.reports import (
    codes as report_codes,
    ReportItem,
    ReportItemSeverity,
)


def booth_ticket_name_invalid(ticket_name):
    """
    Name of booth ticket may consists of alphanumeric characters or dash.
        Entered ticket name violating this rule.
    string ticket_name is entered booth ticket name
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_NAME_INVALID,
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
        info={
            "name": name,
        }
    )

def booth_not_exists_in_cib(name):
    """
    Remove booth instance from cib required. But no such instance found in cib.
    string name is booth instance name
    """
    return ReportItem.error(
        report_codes.BOOTH_NOT_EXISTS_IN_CIB,
        info={
            "name": name,
        }
    )

def booth_config_is_used(name, detail=""):
    """
    Booth config use detected during destroy request.
    string name is booth instance name
    string detail provide more details (for example booth instance is used as
        cluster resource or is started/enabled under systemd)
    """
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_IS_USED,
        info={
            "name": name,
            "detail": detail,
        }
    )

def booth_multiple_times_in_cib(
    name, severity=ReportItemSeverity.ERROR
):
    """
    Each booth instance should be in a cib once maximally. But multiple
        occurences detected. For example during remove booth instance from cib.
        Notify user about this fact is required. When operation is forced
        user should be notified about multiple occurences.
    string name is booth instance name
    ReportItemSeverity severit should be ERROR or WARNING (depends on context)
        is flag for next report processing
        Because of severity coupling with ReportItem is it specified here.
    """
    return ReportItem(
        report_codes.BOOTH_MULTIPLE_TIMES_IN_CIB,
        severity,
        info={
            "name": name,
        },
        forceable=report_codes.FORCE_BOOTH_REMOVE_FROM_CIB
            if severity == ReportItemSeverity.ERROR else None
    )


def booth_config_distribution_started():
    """
    booth configuration is about to be sent to nodes
    """
    return ReportItem.info(
        report_codes.BOOTH_CONFIG_DISTRIBUTION_STARTED,
    )


def booth_config_accepted_by_node(node=None, name_list=None):
    """
    Booth config has been saved on specified node.

    node -- name of node
    name_list -- list of names of booth instance
    """
    return ReportItem.info(
        report_codes.BOOTH_CONFIG_ACCEPTED_BY_NODE,
        info={
            "node": node,
            "name_list": sorted(name_list) if name_list else ""
        }
    )


def booth_config_distribution_node_error(node, reason, name=None):
    """
    Saving booth config failed on specified node.

    node -- node name
    reason -- reason of failure
    name -- name of booth instance
    """
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_DISTRIBUTION_NODE_ERROR,
        info={
            "node": node,
            "name": name,
            "reason": reason
        }
    )


def booth_fetching_config_from_node_started(node, config=None):
    """
    fetching of booth config from specified node started

    node -- node from which config is fetching
    config -- config name
    """
    return ReportItem.info(
        report_codes.BOOTH_FETCHING_CONFIG_FROM_NODE,
        info={
            "node": node,
            "config": config,
        }
    )


def booth_unsupported_file_location(file_path, expected_dir, file_type_code):
    """
    a booth file (config, authfile) is not in the expected dir, skipping it

    string file_path -- the actual path of the file
    string expected_dir -- where the file is supposed to be
    string file_type_code -- item from pcs.common.file_type_codes
    """
    return ReportItem.warning(
        report_codes.BOOTH_UNSUPPORTED_FILE_LOCATION,
        info={
            "file_path": file_path,
            "expected_dir": expected_dir,
            "file_type_code": file_type_code,
        }
    )


def booth_daemon_status_error(reason):
    """
    Unable to get status of booth daemon because of error.

    reason -- reason
    """
    return ReportItem.error(
        report_codes.BOOTH_DAEMON_STATUS_ERROR,
        info={"reason": reason}
    )


def booth_tickets_status_error(reason=None):
    """
    Unable to get status of booth tickets because of error.

    reason -- reason
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_STATUS_ERROR,
        info={
            "reason": reason,
        }
    )


def booth_peers_status_error(reason=None):
    """
    Unable to get status of booth peers because of error.

    reason -- reason
    """
    return ReportItem.error(
        report_codes.BOOTH_PEERS_STATUS_ERROR,
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
        info={}
    )

def booth_ticket_operation_failed(operation, reason, site_ip, ticket_name):
    """
    Pcs uses external booth tools for some ticket_name operations. For example
        grand and revoke. But the external command failed.
    string operatin determine what was intended perform with ticket_name
    string reason is taken from external booth command
    string site_ip specifiy what site had to run the command
    string ticket_name specify with which ticket had to run the command
    """
    return ReportItem.error(
        report_codes.BOOTH_TICKET_OPERATION_FAILED,
        info={
            "operation": operation,
            "reason": reason,
            "site_ip": site_ip,
            "ticket_name": ticket_name,
        }
    )
