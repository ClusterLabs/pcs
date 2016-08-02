from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.common.tools import merge_dicts
from pcs.lib.booth import reports
from pcs.lib.errors import LibraryError


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


def add_ticket(booth_configuration, ticket_name):
    validate_ticket_name(ticket_name)
    validate_ticket_unique(booth_configuration["tickets"], ticket_name)
    return merge_dicts(
        booth_configuration,
        {"tickets": sorted(booth_configuration["tickets"] + [ticket_name])}
    )


def validate_ticket_exists(booth_configuration_tickets, ticket_name):
    if ticket_name not in booth_configuration_tickets:
        raise LibraryError(reports.booth_ticket_does_not_exist(ticket_name))


def validate_ticket_unique(booth_configuration_tickets, ticket_name):
    if ticket_name in booth_configuration_tickets:
        raise LibraryError(reports.booth_ticket_duplicate(ticket_name))


def validate_ticket_name(ticket_name):
    if not re.compile(r"^[\w-]+$").search(ticket_name):
        raise LibraryError(reports.booth_ticket_name_invalid(ticket_name))

def from_supported_parts(supported_parts):
    return supported_parts

def get_supported_part(parsed_config):
    return parsed_config

def set_authfile(parsed_config, auth_file):
    return merge_dicts(parsed_config, {"authfile": auth_file})

def get_authfile(parsed_config):
    return parsed_config.get("authfile", None)
