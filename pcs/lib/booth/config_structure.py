from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

import pcs.lib.reports as common_reports
from pcs.lib.booth import reports
from pcs.lib.errors import LibraryError, ReportItemSeverity as severities
from pcs.common import report_codes
from collections import namedtuple

GLOBAL_KEYS = (
    "transport",
    "port",
    "name",
    "authfile",
    "maxtimeskew",
    "site",
    "arbitrator",
    "site-user",
    "site-group",
    "arbitrator-user",
    "arbitrator-group",
    "debug",
    "ticket",
)
TICKET_KEYS = (
    "acquire-after",
    "attr-prereq",
    "before-acquire-handler",
    "expire",
    "renewal-freq",
    "retries",
    "timeout",
    "weights",
)

class ConfigItem(namedtuple("ConfigItem", "key value details")):
    def __new__(cls, key, value, details=None):
        details = details if details else []
        return super(ConfigItem, cls).__new__(cls, key, value, details)

def validate_peers(site_list, arbitrator_list):
    report = []

    if len(site_list) < 2:
        report.append(reports.booth_lack_of_sites(site_list))

    peer_list = site_list + arbitrator_list

    if len(peer_list) % 2 == 0:
        report.append(reports.booth_even_peers_num(len(peer_list)))

    address_set = set()
    duplicate_addresses = set()
    for address in peer_list:
        if address in address_set:
            duplicate_addresses.add(address)
        else:
            address_set.add(address)
    if duplicate_addresses:
        report.append(reports.booth_address_duplication(duplicate_addresses))

    if report:
        raise LibraryError(*report)

def take_peers(booth_configuration):
    return (
        pick_list_by_key(booth_configuration, "site"),
        pick_list_by_key(booth_configuration, "arbitrator"),
    )

def pick_list_by_key(booth_configuration, key):
    return [item.value for item in booth_configuration if item.key == key]

def remove_ticket(booth_configuration, ticket_name):
    validate_ticket_exists(booth_configuration, ticket_name)
    return [
        config_item for config_item in booth_configuration
        if config_item.key != "ticket" or config_item.value != ticket_name
    ]

def add_ticket(
    report_processor, booth_configuration, ticket_name, options,
    allow_unknown_options
):
    validate_ticket_name(ticket_name)
    validate_ticket_unique(booth_configuration, ticket_name)
    validate_ticket_options(report_processor, options, allow_unknown_options)
    return booth_configuration + [
        ConfigItem("ticket", ticket_name, [
            ConfigItem(key, value) for key, value in options.items()
        ])
    ]

def validate_ticket_exists(booth_configuration, ticket_name):
    if not ticket_exists(booth_configuration, ticket_name):
        raise LibraryError(reports.booth_ticket_does_not_exist(ticket_name))

def validate_ticket_unique(booth_configuration, ticket_name):
    if ticket_exists(booth_configuration, ticket_name):
        raise LibraryError(reports.booth_ticket_duplicate(ticket_name))

def validate_ticket_options(report_processor, options, allow_unknown_options):
    reports = []
    for key in sorted(options):
        if key in GLOBAL_KEYS:
            reports.append(
                common_reports.invalid_option(key, TICKET_KEYS, "booth ticket")
            )

        elif key not in TICKET_KEYS:
            reports.append(
                common_reports.invalid_option(
                    key, TICKET_KEYS,
                    "booth ticket",
                    severity=(
                        severities.WARNING if allow_unknown_options
                        else severities.ERROR
                    ),
                    forceable=(
                        None if allow_unknown_options
                        else report_codes.FORCE_OPTIONS
                    ),
                )
            )

        if not options[key].strip():
            reports.append(common_reports.invalid_option_value(
                key,
                options[key],
                "no-empty",
            ))

    report_processor.process_list(reports)

def ticket_exists(booth_configuration, ticket_name):
    return any(
        value for key, value, _ in booth_configuration
        if key == "ticket" and value == ticket_name
    )

def validate_ticket_name(ticket_name):
    if not re.compile(r"^[\w-]+$").search(ticket_name):
        raise LibraryError(reports.booth_ticket_name_invalid(ticket_name))

def set_authfile(booth_configuration, auth_file):
    return [ConfigItem("authfile", auth_file)] + [
        config_item for config_item in booth_configuration
        if config_item.key != "authfile"
    ]

def get_authfile(booth_configuration):
    for key, value, _ in reversed(booth_configuration):
        if key == "authfile":
            return value
    return None
