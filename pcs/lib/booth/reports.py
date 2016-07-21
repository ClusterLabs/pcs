from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItem


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
