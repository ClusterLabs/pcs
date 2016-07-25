from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re
import os
import binascii

from pcs.lib import reports as lib_reports
from pcs.lib.booth import reports
from pcs.common import report_codes
from pcs.common.tools import merge_dicts
from pcs.lib.errors import LibraryError, ReportItemSeverity
from pcs.settings import booth_config_dir as BOOTH_CONFIG_DIR


def validate_participants(site_list, arbitrator_list):
    report = []

    if len(site_list) < 2:
        report.append(reports.booth_lack_of_sites(site_list))

    participants_list = site_list + arbitrator_list

    if len(participants_list) % 2 == 0:
        report.append(reports.booth_even_paticipants_num(
            len(participants_list)
        ))

    address_set = set()
    duplicate_addresses = []
    for address in participants_list:
        if address in address_set:
            duplicate_addresses.append(address)
        else:
            address_set.add(address)
    if duplicate_addresses:
        report.append(reports.booth_address_duplication(duplicate_addresses))

    if report:
        raise LibraryError(*report)

def generate_key():
    return binascii.hexlify(os.urandom(32))

def build(booth_configuration):
    return "\n".join(
        [
            "site = {0}".format(site)
            for site in sorted(booth_configuration["sites"])
        ]
        +
        [
            "arbitrator = {0}".format(arbitrator)
            for arbitrator in sorted(booth_configuration["arbitrators"])
        ]
        +
        [
            "authfile = {0}".format(booth_configuration["authfile"])
        ]
        +
        [
            'ticket = "{0}"'.format(ticket)
            for ticket in sorted(booth_configuration.get("tickets", []))
        ]
    )

def parse(content):
    keywords = {
        "site": [],
        "arbitrator": [],
        "ticket": [],
        "authfile": [],
    }
    pattern = re.compile(
        r"^\s*({0})\s*=(.*)".format("|".join(keywords.keys()))
    )
    unexpected_lines = []
    for line in content.splitlines():
        match = pattern.search(line)
        if match:
            if match.group(1) in list(keywords.keys()):
                value = match.group(2).strip()
                if match.group(1) == "ticket":
                    value = value.strip('"')
                keywords[match.group(1)].append(value)
                continue
        unexpected_lines.append(line)
    if unexpected_lines:
        raise LibraryError(
            reports.booth_config_unexpected_lines(unexpected_lines)
        )

    parsed_config = {
        "sites": keywords["site"],
        "arbitrators": keywords["arbitrator"],
        "tickets": keywords["ticket"],
    }

    if len(keywords["authfile"]) > 1:
        raise LibraryError(
            reports.booth_config_invalid_content("multiple authfile")
        )

    if keywords["authfile"]:
        parsed_config["authfile"] = keywords["authfile"][0]

    return parsed_config

def add_ticket(booth_configuration, ticket_name):
    validate_ticket_name(ticket_name)
    validate_ticket_unique(booth_configuration["tickets"], ticket_name)
    return merge_dicts(
        booth_configuration,
        {"tickets": sorted(booth_configuration["tickets"] + [ticket_name])}
    )

def remove_ticket(booth_configuration, ticket_name):
    validate_ticket_exists(booth_configuration["tickets"], ticket_name)
    return merge_dicts(
        booth_configuration,
        {
            "tickets": [
                t for t in booth_configuration["tickets"] if t != ticket_name
            ]
        }
    )

def validate_ticket_name(ticket_name):
    if not re.compile(r"^[\w-]+$").search(ticket_name):
        raise LibraryError(reports.booth_ticket_name_invalid(ticket_name))

def validate_ticket_unique(booth_configuration_tickets, ticket_name):
    if ticket_name in booth_configuration_tickets:
        raise LibraryError(reports.booth_ticket_duplicate(ticket_name))

def validate_ticket_exists(booth_configuration_tickets, ticket_name):
    if ticket_name not in booth_configuration_tickets:
        raise LibraryError(reports.booth_ticket_does_not_exist(ticket_name))


def get_all_configs():
    """
    Returns list of all file names (without suffix) ending with '.conf' in
    booth configuration directory.
    """
    return [
        file for file in os.listdir(BOOTH_CONFIG_DIR) if file.endswith(".conf")
    ]


def _read_config(file_name):
    """
    Read specified booth config from default booth config directory.

    file_name -- string, name of file
    """
    with open(os.path.join(BOOTH_CONFIG_DIR, file_name), "r") as file:
        return file.read()


def read_configs(reporter, skip_wrong_config=False):
    """
    Returns content of all configs present on local system in dictionary,
    where key is name of config and value is its content.

    reporter -- report processor
    skip_wrong_config -- if True skip local configs that are unreadable
    """
    report_list = []
    output = {}
    for file_name in get_all_configs():
        try:
            output[file_name] = _read_config(file_name)
        except EnvironmentError:
            report_list.append(reports.booth_config_unable_to_read(
                file_name,
                (
                    ReportItemSeverity.WARNING if skip_wrong_config
                    else ReportItemSeverity.ERROR
                ),
                (
                    None if skip_wrong_config
                    else report_codes.SKIP_UNREADABLE_CONFIG
                )
            ))
    reporter.process_list(report_list)
    return output


def read_authfiles_from_configs(reporter, config_content_list):
    """
    Returns content of authfiles of configs specified in config_content_list in
    dictionary where key is path to authfile and value is its content as bytes

    reporter -- report processor
    config_content_list -- list of configs content
    """
    output = {}
    for config in config_content_list:
        authfile_path = parse(config).get("authfile", None)
        if authfile_path:
            output[os.path.basename(authfile_path)] = read_authfile(
                reporter, authfile_path
            )
    return output


def read_authfile(reporter, path):
    """
    Returns content of specified authfile as bytes. None if file is not in
    default booth directory or there was some IO error.

    reporter -- report processor
    path -- path to the authfile to be read
    """
    if not path:
        return None
    if os.path.dirname(os.path.abspath(path)) != BOOTH_CONFIG_DIR:
        reporter.process(reports.booth_unsupported_file_location(path))
        return None
    try:
        with open(path, "rb") as file:
            return file.read()
    except EnvironmentError as e:
        reporter.process(lib_reports.file_io_error(
            "authfile", path, str(e), ReportItemSeverity.WARNING
        ))
        return None
