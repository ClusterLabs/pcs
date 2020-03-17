from pcs.common.reports import (
    codes as report_codes,
    ReportItem,
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
