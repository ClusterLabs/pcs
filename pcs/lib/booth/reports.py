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

def booth_config_dir_does_not_exists(path):
    return ReportItem.error(
        report_codes.BOOTH_CONFIG_DIR_DOES_NOT_EXISTS,
        "booth configuration dir not exists (is booth installed?)",
        info={
            "dir": path,
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

def booth_invalid_name(name):
    return ReportItem.error(
        report_codes.BOOTH_INVALID_NAME,
        "booth name '{name}' is not valid",
        info={
            "name": name,
        }
    )
